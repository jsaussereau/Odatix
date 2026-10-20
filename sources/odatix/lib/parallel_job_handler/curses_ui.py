# ********************************************************************** #
#                                Odatix                                  #
# ********************************************************************** #
#
# Copyright (C) 2022 Jonathan Saussereau
#
# This file is part of Odatix.
# Odatix is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Odatix is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Odatix. If not, see <https://www.gnu.org/licenses/>.
#

import curses
import os
import re
import signal
import sys
import time

from .ansi_to_curses import AnsiToCursesConverter
from .utils import get_elapsed_time_str
from ._vendor.clipboard import copy_to_clipboard
from ._vendor.system import can_open_path_in_explorer, open_path_in_explorer
from ._vendor import printc


DOUBLE_CLICK_DELAY = 0.4

# Cursor modes, cycled with the "c" key.
CURSOR_MODES = ("mouse+", "mouse", "raw")

# Height of the help popup: title, column headers, one row per key of
# update_help_popup and the closing hint. Smaller terminals cut the list.
HELP_POPUP_HEIGHT = 26

# How long the status message replacing the help bar stays up after a copy.
STATUS_MESSAGE_DELAY = 2.0

NORMAL = 1
RED = 2
YELLOW = 3
GREEN = 4
BLUE = 5
CYAN = 6
BLACK = 7
WHITE = 8
GREY = 9

REVERSE = 10
REVERSE_RED = 12
REVERSE_YELLOW = 13
REVERSE_GREEN = 14
REVERSE_BLUE = 15
REVERSE_CYAN = 16
REVERSE_BLACK = 17
REVERSE_WHITE = 18
REVERSE_GREY = 19

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


def _visible_text_len(text):
    return len(ANSI_ESCAPE_RE.sub("", str(text)))


def _plain_log_line(handler, raw_line):
    """A log line as the user sees it: formatter applied, ANSI codes removed."""
    line = raw_line
    if handler.formatter is not None:
        line = handler.formatter.replace_in_line(line)
    return ANSI_ESCAPE_RE.sub("", str(line))


class LogSelection:
    """A text selection made inside the log window, in log coordinates.

    Positions are (line, column) with `line` an index in the job log history and
    `column` a column of that line once the ANSI codes are stripped. Keeping the
    selection in log coordinates rather than screen coordinates is what lets it
    cover lines scrolled out of sight and the part of a line that runs past the
    right edge of the window.
    """

    def __init__(self, job_index, position):
        self.job_index = job_index
        self.anchor = position
        self.cursor = position
        self.dragging = True
        # Direction the pointer is pushing outside the window, so the view keeps
        # scrolling as long as the button is held there.
        self.edge = (0, 0)

    def bounds(self):
        if self.anchor <= self.cursor:
            return self.anchor, self.cursor
        return self.cursor, self.anchor

    def is_empty(self):
        return self.anchor == self.cursor

    def line_span(self, line, line_length):
        """Selected columns of `line`, as a (start, end) pair, or None."""
        (start_line, start_col), (end_line, end_col) = self.bounds()
        if not start_line <= line <= end_line:
            return None
        start = start_col if line == start_line else 0
        # A line selected through to the next one is highlighted to its end, and
        # empty lines still get one cell so the selection stays readable.
        end = end_col if line == end_line else max(line_length, start + 1)
        if end <= start:
            return None
        return start, end

    def text(self, handler, history):
        (start_line, _), (end_line, _) = self.bounds()
        lines = []
        for line in range(max(0, start_line), min(len(history), end_line + 1)):
            plain = _plain_log_line(handler, history[line])
            span = self.line_span(line, len(plain))
            lines.append("" if span is None else plain[span[0] : span[1]])
        return "\n".join(lines)


def progress_bar(handler, window, id, progress, elapsed_time, title, title_size, width, status="",
                 selected=False, real_id=None, hovered=False):
    reserved_space = handler.theme.get('reserved_space')
    spacer = handler.theme.get('spacer')
    ellipsis = handler.theme.get('ellipsis')

    if width > 100:
        display_time = True
    else:
        display_time = False
        reserved_space = reserved_space - (len(elapsed_time) + len(spacer))

    bar_width = width - title_size - reserved_space
    if bar_width < 4:
        bar_width = 4
        title_size = width - bar_width - reserved_space
        if title_size < 0:
            title_size = 0

        if len(title) > title_size:
            title = title[: title_size - len(ellipsis)] + ellipsis
        else:
            title = title.ljust(title_size)
    else:
        title = title.ljust(title_size)

    bar_length = int(bar_width * progress / 100.0)

    if real_id is None:
        real_id = handler.job_index_start + id

    # The hovered row is bold as a whole. attron covers the addstr calls that
    # take no attribute of their own; the ones that pass a color pair get the
    # bold added explicitly through `hover_attr`.
    hover_attr = curses.A_BOLD if (hovered and not handler.showing_help) else 0
    if hover_attr:
        window.attron(hover_attr)

    try:
        if real_id == handler.selected_job_index and handler.theme.get('selected_reverse') and handler.job_count > 1:
            window.attron(curses.color_pair(NORMAL) | curses.A_REVERSE)
            attr = curses.A_REVERSE | curses.A_BOLD
            offset = REVERSE
        else:
            attr = hover_attr
            offset = 0

        attr = attr | curses.A_DIM if handler.showing_help else attr

        ballot = handler.theme.get('ballot_check') if selected else handler.theme.get('ballot_empty')
        window.addstr(id, 0, f"{ballot}")
        pos = len(ballot)

        if real_id == handler.selected_job_index and handler.theme.get('selected_bold') and handler.job_count > 1:
            window.attron(curses.color_pair(NORMAL) | curses.A_BOLD)
            attr = attr | curses.A_BOLD
        window.addstr(id, pos, f"{title}")
        if not hover_attr:
            window.attroff(curses.A_BOLD)
        pos = pos + len(title)

        border_left = handler.theme.get('border_left')
        window.addstr(id, pos, f"{border_left}")
        pos = pos + len(border_left)

        if handler.theme.get('colored_bar'):
            if status == "failed" or status == "killed" or status == "canceled":
                color = curses.color_pair(RED + offset)
            elif status == "running":
                color = curses.color_pair(WHITE + offset)
            elif status == "exporting":
                color = curses.color_pair(CYAN + offset)
            elif status == "success":
                color = curses.color_pair(GREEN + offset)
            elif status == "queued" or status == "paused":
                color = curses.color_pair(BLUE + offset)
            elif status == "starting":
                color = curses.color_pair(CYAN + offset)
            else:
                color = curses.color_pair(NORMAL + offset)
        else:
            color = 0
        window.addstr(id, pos, handler.theme.get('progress_full') * bar_length, attr | color | hover_attr)

        if handler.theme.get('dim_empty_bar'):
            dim = curses.color_pair(GREY + offset)
        else:
            dim = 0
        window.addstr(id, pos + bar_length, handler.theme.get('progress_empty') * (bar_width - bar_length), attr | dim | hover_attr)
        pos = pos + bar_width

        border_right = handler.theme.get('border_right')
        window.addstr(id, pos, border_right + " ", attr)
        pos = pos + len(border_right)

        percentage = f"{progress:3.0f}%"
        window.addstr(id, pos, percentage + spacer, attr)
        pos = pos + len(percentage) + len(spacer)

        if display_time:
            window.addstr(id, pos, elapsed_time + spacer, attr | curses.color_pair(GREY + offset) | hover_attr)
            pos = pos + len(elapsed_time) + len(spacer)

        if status == "failed" or status == "killed" or status == "canceled":
            window.addstr(id, pos, status, curses.color_pair(RED + offset) | attr | hover_attr)
        elif status == "running":
            window.addstr(id, pos, status, curses.color_pair(YELLOW + offset) | attr | hover_attr)
        elif status == "exporting":
            window.addstr(id, pos, status, curses.color_pair(CYAN + offset) | attr | hover_attr)
        elif status == "success":
            window.addstr(id, pos, status, curses.color_pair(GREEN + offset) | attr | hover_attr)
        elif status == "queued" or status == "paused":
            window.addstr(id, pos, status, curses.color_pair(BLUE + offset) | attr | hover_attr)
        elif status == "starting":
            window.addstr(id, pos, status, curses.color_pair(CYAN + offset) | attr | hover_attr)
        else:
            window.addstr(id, pos, status, curses.color_pair(NORMAL + offset) | attr | hover_attr)
        pos = pos + len(status)

        remainder = width - pos
        if remainder > 0:
            window.addstr(id, pos, " " * remainder, attr)
    except curses.error:
        pass

    window.attroff(curses.A_REVERSE)
    window.attroff(curses.A_BOLD)


def _resource_guard_label(handler, short=False):
    """
    Where auto-pause stands. `short` leaves out how many jobs it holds: the
    job counts of the header already say how many are paused.
    """
    try:
        unavailable = handler.resource_guard_unavailable()
    except Exception:
        unavailable = None
    if unavailable:
        return "unavailable"
    if not getattr(handler, "resource_guard_enabled", False):
        return "off"
    try:
        paused = int(handler.resource_guard_paused_count())
    except Exception:
        paused = 0
    return "on ({} paused)".format(paused) if paused > 0 and not short else "on"


def _job_counts_texts(retired, total, running, paused):
    """The job counts of the header, from the most to the least detailed."""
    if total <= 0:
        return ["waiting for jobs", "no jobs yet"]
    noun = "job" if total == 1 else "jobs"
    if retired >= total and running == 0 and paused == 0:
        return ["{}/{} {} done!".format(retired, total, noun), "{}/{} done!".format(retired, total)]
    queued = max(0, total - retired - running - paused)
    details = [
        "{} {}".format(count, label)
        for count, label in ((running, "running"), (paused, "paused"), (queued, "queued"))
        if count
    ] or ["0 running"]
    texts = [
        "{}/{} {} done - {}".format(retired, total, noun, ", ".join(details)),
        "{}/{} done, {}".format(retired, total, ", ".join(details)),
    ]
    if paused:
        texts.append("{}/{} done, {} paused".format(retired, total, paused))
    texts.append("{}/{} done".format(retired, total))
    return texts


HEADER_TITLE = " Odatix "


def header_layout(width, version, nb_jobs, guard_long, guard_short, counts_texts, session_label=None):
    """
    What the header of the monitor shows in `width` columns, and where.

    Nothing overlaps, whatever the width: the parts are dropped or shortened
    by priority, the least useful first. The session and the job counts come
    first, then auto-pause, then the number of parallel jobs and the version.
    The " Odatix " title is only drawn in the middle when there is room left
    for it.

    Returns:
        tuple: (left text, right text, column of the title or None). The left
        text starts at column 1, the right text ends one column before the edge.
    """
    room = max(0, int(width) - 2)
    session = "session {}".format(session_label) if session_label else None

    def parts(*items):
        return [item for item in items if item]

    # Richest first. Each level gives up something the previous one showed:
    # the version, then wording, then the number of parallel jobs, then the
    # detail of the job counts.
    lefts = [
        ("   ", parts(session, "v{}".format(version), "parallel jobs: {}".format(nb_jobs), "auto-pause: " + guard_long)),
        ("   ", parts(session, "parallel jobs: {}".format(nb_jobs), "auto-pause: " + guard_long)),
        ("  ", parts(session, "parallel: {}".format(nb_jobs), "auto-pause: " + guard_short)),
    ]
    candidates = [(sep, left, right) for sep, left in lefts for right in counts_texts[:2]]
    minimal = parts(session, "auto-pause: " + guard_short)
    candidates.extend(("  ", minimal, right) for right in counts_texts)
    for separator, left_parts, right in candidates:
        left = separator.join(left_parts)
        if len(left) + len(right) + 2 <= room:
            break
    else:
        # Too narrow for everything that matters: the session and the counts,
        # the session cut short when even that does not fit.
        separator, right = "  ", counts_texts[-1]
        left = separator.join(parts(session, "auto-pause: " + guard_short))
        if len(left) + len(right) + 2 > room:
            left = session or ""
        budget = room - len(right) - 2
        if len(left) > budget:
            left = left[: max(0, budget - 1)] + "~" if budget > 1 else ""
        if len(right) > room:
            right = right[:room]

    title_x = None
    left_end = 1 + len(left)
    right_start = int(width) - 1 - len(right)
    x = (int(width) - len(HEADER_TITLE)) // 2
    if x >= left_end + 2 and x + len(HEADER_TITLE) <= right_start - 2:
        title_x = x
    return left, right, title_x


def update_header(handler, header_win, active_jobs_count, retired_jobs_count, total_jobs_count, width, paused_jobs_count=0):
    nb_jobs = int(getattr(handler, "nb_jobs", 1))
    left_text, text, title_x = header_layout(
        width,
        version=handler.version,
        nb_jobs=nb_jobs,
        guard_long=_resource_guard_label(handler),
        guard_short=_resource_guard_label(handler, short=True),
        counts_texts=_job_counts_texts(retired_jobs_count, total_jobs_count, active_jobs_count, paused_jobs_count),
        session_label=getattr(handler, "session_label", None),
    )
    try:
        header_win.hline(0, 0, " ", width, curses.color_pair(NORMAL) | curses.A_REVERSE)
        header_win.addstr(0, 1, left_text, curses.color_pair(NORMAL) | curses.A_REVERSE)
    except curses.error:
        pass
    try:
        header_win.addstr(0, max(0, width - len(text) - 1), text, curses.color_pair(NORMAL) | curses.A_REVERSE)
    except curses.error:
        pass
    if title_x is not None:
        try:
            header_win.addstr(0, title_x, HEADER_TITLE, curses.color_pair(NORMAL) | curses.A_REVERSE | curses.A_BOLD)
        except curses.error:
            pass

    header_win.refresh()


def update_progress_window(handler, progress_win, hover_job=-1):
    rows, width = progress_win.getmaxyx()
    if handler.showing_help:
        progress_win.attron(curses.A_DIM)

    progress_win.erase()

    # The pinned jobs come first and never scroll away: what runs a run is what
    # tells the rest of the list what it is doing there. A separator marks
    # where they end and the scrolled jobs begin. Jobs scrolled off above the
    # visible window would normally be counted on separator_top_win, but once
    # there are pinned jobs that separator has nothing left to say (it sits
    # above the pinned jobs, not above the scrolled ones) so the "N more"
    # message is shown here instead.
    visible = handler.visible_jobs(rows=rows)
    pinned_count = sum(1 for _, job in visible if job.pinned)
    row = 0
    for i, (real_id, job) in enumerate(visible):
        if i == pinned_count and pinned_count > 0:
            try:
                dim = handler.showing_help and curses.A_DIM
                text = build_separator_text(handler, handler.job_index_start, 0, width)
                progress_win.addstr(row, 0, text, dim)
            except curses.error:
                pass
            row += 1
        selected = (handler.selected_job_index == real_id)
        elapsed_time = get_elapsed_time_str(job.start_time, job.stop_time)
        try:
            progress_bar(
                handler=handler,
                id=row,
                real_id=real_id,
                window=progress_win,
                progress=job.progress,
                elapsed_time=elapsed_time,
                title=job.display_name,
                title_size=handler.max_title_length,
                width=width,
                status=job.status,
                selected=selected,
                hovered=(real_id == hover_job),
            )
        except curses.error:
            pass
        row += 1
    progress_win.refresh()
    progress_win.attroff(curses.A_DIM)


def build_separator_text(handler, val, ref, width):
    remaining = max(0, int(val) - int(ref))
    if remaining == 0:
        return handler.theme.get("bar") * (width - 1)
    message = f"{remaining} more"
    padding = 4
    return handler.theme.get("bar") * padding + message + handler.theme.get("bar") * (width - len(message) - padding - 1)


def separator_resize_handle(handler):
    """Marker shown on the separator under the pointer: it can be dragged."""
    if handler.theme.get("bar") == "-":
        return "[ drag to resize ]"
    return " ⇕ "


def update_separator(handler, separator_win, val, ref, width, hover=False):
    dim = handler.showing_help and curses.A_DIM
    separator_win.erase()
    separator_text = build_separator_text(handler, val, ref, width)
    try:
        if hover and not handler.showing_help:
            handle = separator_resize_handle(handler)
            if len(handle) < width - 1:
                start = (width - len(handle)) // 2
                separator_win.addstr(0, 0, separator_text[:start], curses.A_BOLD)
                separator_win.addstr(0, start, handle, curses.A_REVERSE)
                separator_win.addstr(0, start + len(handle), separator_text[start + len(handle):],
                                     curses.A_BOLD)
            else:
                separator_win.addstr(0, 0, separator_text, curses.A_BOLD)
        else:
            separator_win.addstr(0, 0, separator_text, dim)
    except curses.error:
        pass
    separator_win.refresh()


def update_help(bottom_bar, cursor_mode=None):
    bottom_bar.erase()

    help_text = [
        ("d", "Detach"),
        ("q", "Quit"),
        ("h", "Help Menu"),
        ("c", "Cursor Mode" if cursor_mode is None else "Cursor Mode ({})".format(cursor_mode)),
    ]

    bottom_bar.attron(curses.color_pair(NORMAL) | curses.A_REVERSE)
    try:
        bottom_bar.addstr(" ")
    except curses.error:
        pass

    for i, (key, description) in enumerate(help_text):
        try:
            if i > 0:
                bottom_bar.addstr(" | ")
            bottom_bar.attron(curses.color_pair(NORMAL) | curses.A_REVERSE | curses.A_BOLD)
            bottom_bar.addstr(key)
            bottom_bar.attroff(curses.A_BOLD)
            bottom_bar.addstr(": ")
            bottom_bar.addstr(description)
        except curses.error:
            pass

    try:
        bottom_bar.addstr(" ")
    except curses.error:
        pass
    bottom_bar.attroff(curses.color_pair(NORMAL) | curses.A_REVERSE | curses.A_BOLD)
    bottom_bar.refresh()


def update_copy_help(bottom_bar):
    """Replaces the help bar while a log selection is being made."""
    bottom_bar.erase()
    bottom_bar.attron(curses.color_pair(NORMAL) | curses.A_REVERSE)
    parts = [("y", " or "), ("right click", ": copy selection")]
    try:
        bottom_bar.addstr(" Press ")
        for key, tail in parts:
            bottom_bar.attron(curses.A_BOLD)
            bottom_bar.addstr(key)
            bottom_bar.attroff(curses.A_BOLD)
            bottom_bar.addstr(tail)
        bottom_bar.addstr(" | ")
        bottom_bar.attron(curses.A_BOLD)
        bottom_bar.addstr("Esc")
        bottom_bar.attroff(curses.A_BOLD)
        bottom_bar.addstr(": clear ")
    except curses.error:
        pass
    bottom_bar.attroff(curses.color_pair(NORMAL) | curses.A_REVERSE | curses.A_BOLD)
    bottom_bar.refresh()


def update_status_message(bottom_bar, message):
    """Temporarily replaces the help bar, e.g. to confirm a copy."""
    bottom_bar.erase()
    bottom_bar.attron(curses.color_pair(NORMAL) | curses.A_REVERSE)
    try:
        bottom_bar.addstr(" " + message + " ")
    except curses.error:
        pass
    bottom_bar.attroff(curses.color_pair(NORMAL) | curses.A_REVERSE)
    bottom_bar.refresh()


def exit_prompt_parts(width, can_detach):
    """
    What "q" asks while jobs remain, as (text, bold) pieces fitting `width`.

    Leaving is what "q" is for, so the first choice is the one that leaves the
    jobs alone; killing them takes a key of its own, never the one just typed.
    """
    if can_detach:
        variants = [
            [(" Jobs are still running: ", False), ("d", True), (" leave them running and quit | ", False),
             ("k", True), (" kill them all and close the session | ", False), ("Esc", True), (" stay ", False)],
            [(" Jobs still running: ", False), ("d", True), (" quit, keep them | ", False),
             ("k", True), (" kill all, close session | ", False), ("Esc", True), (" stay ", False)],
            [(" ", False), ("d", True), (": keep jobs | ", False), ("k", True), (": kill all | ", False),
             ("Esc", True), (": stay ", False)],
        ]
    else:
        variants = [
            [(" Jobs are still running: ", False), ("k", True), (" kill them all and quit | ", False),
             ("Esc", True), (" stay ", False)],
            [(" ", False), ("k", True), (": kill all, quit | ", False), ("Esc", True), (": stay ", False)],
        ]
    for parts in variants:
        if sum(len(text) for text, _bold in parts) <= max(0, width - 1):
            return parts
    return variants[-1]


def show_exit_confirmation(bottom_bar, can_detach=True):
    """
    Ask what "q" should do while jobs are still running.

    Returns:
        str: "detach" (quit, the jobs keep running in their session), "kill"
        (kill every job, and close the session), "cancel", or None when the
        key pressed answers nothing (asked again).
    """
    try:
        bottom_bar.erase()
        width = bottom_bar.getmaxyx()[1]
        for text, bold in exit_prompt_parts(width, can_detach):
            attr = curses.color_pair(NORMAL) | curses.A_REVERSE | (curses.A_BOLD if bold else 0)
            bottom_bar.addstr(text, attr)
        bottom_bar.refresh()
    except curses.error:
        pass

    key = bottom_bar.getch()
    curses.flushinp()
    if key in (ord("k"), ord("K")):
        return "kill"
    if can_detach and key in (ord("d"), ord("D"), ord("q"), ord("Q")):
        return "detach"
    if key in (27, ord("n"), ord("N")):
        return "cancel"
    return None


def update_exit(bottom_bar):
    try:
        bottom_bar.erase()
        bottom_bar.addstr(" Exiting... ", curses.color_pair(NORMAL) | curses.A_REVERSE)
        bottom_bar.refresh()
    except curses.error:
        pass


def on_quit_after_finished(handler):
    callback = getattr(handler, "on_quit_after_finished", None)
    if callback is None:
        return
    try:
        callback()
    except Exception:
        # Best effort hook: quitting the monitor should still succeed.
        return


FINISHED_POPUP_OPTIONS = [
    ("Stay in the monitor", "stay"),
    ("Close the session and quit", "close"),
    ("Keep the session open and quit", "detach"),
]

# Without a session to keep alive (local run), quitting simply leaves the monitor.
FINISHED_POPUP_OPTIONS_NO_SESSION = [
    ("Stay in the monitor", "stay"),
    ("Quit", "close"),
]


def finished_popup_options(handler):
    if callable(getattr(handler, "on_quit_after_finished", None)):
        return FINISHED_POPUP_OPTIONS
    return FINISHED_POPUP_OPTIONS_NO_SESSION


# Geometry shared between the drawing and the mouse handling of the finished popup.
FINISHED_POPUP_FIRST_OPTION_Y = 4
FINISHED_POPUP_OPTION_X = 3


def finished_popup_close_button(popup_width):
    """Return (y, x_start, x_end) of the clickable close button, in popup coordinates."""
    x = popup_width - 5
    return 1, x, x + 2


def finished_popup_summary(retired_jobs_count, total_jobs_count, failed_jobs_count=0):
    """What the end-of-run popup says about the jobs."""
    if total_jobs_count <= 0:
        return ""
    succeeded = max(0, retired_jobs_count - failed_jobs_count)
    summary = "{}/{} job(s) succeeded".format(succeeded, total_jobs_count)
    if failed_jobs_count:
        summary += ", {} failed".format(failed_jobs_count)
    return summary


def update_finished_popup(popup_win, popup_width, popup_height, options, selected, retired_jobs_count, total_jobs_count,
                          failed_jobs_count=0):
    popup_win.erase()
    popup_win.box()

    def addstr(y, x, text, attr=0):
        if y < 1 or y > popup_height - 2:
            return
        try:
            popup_win.addstr(y, x, text[: max(0, popup_width - x - 1)], attr)
        except curses.error:
            pass

    title = " All jobs completed "
    addstr(1, max(1, (popup_width - len(title)) // 2), title, curses.A_BOLD | curses.A_REVERSE)

    close_y, close_x, _ = finished_popup_close_button(popup_width)
    addstr(close_y, close_x, " X ", curses.A_BOLD | curses.color_pair(REVERSE_RED))

    summary = finished_popup_summary(retired_jobs_count, total_jobs_count, failed_jobs_count)
    if summary:
        attr = curses.color_pair(RED) if failed_jobs_count else curses.A_DIM
        addstr(2, max(1, (popup_width - len(summary)) // 2), summary, attr)

    for i, (label, _) in enumerate(options):
        text = " {}. {} ".format(i + 1, label)
        text = text.ljust(popup_width - 2 * FINISHED_POPUP_OPTION_X)
        attr = curses.A_BOLD | highlight_attr() if i == selected else curses.color_pair(NORMAL)
        addstr(FINISHED_POPUP_FIRST_OPTION_Y + i, FINISHED_POPUP_OPTION_X, text, attr)

    hint = "Up/Down + Enter, 1-{}, or click | Esc: stay".format(len(options))
    if len(hint) > popup_width - 2:
        hint = "1-{} or Enter | Esc: stay".format(len(options))
    addstr(popup_height - 2, max(1, (popup_width - len(hint)) // 2), hint, curses.A_DIM)
    popup_win.refresh()


def finished_popup_option_at(popup_width, popup_height, options, y, x):
    """Return the index of the option under the popup-relative position, or -1."""
    index = y - FINISHED_POPUP_FIRST_OPTION_Y
    if not 0 <= index < len(options):
        return -1
    if y > popup_height - 2:
        return -1
    if not FINISHED_POPUP_OPTION_X <= x < popup_width - FINISHED_POPUP_OPTION_X:
        return -1
    return index


def show_finished_popup(stdscr, options, retired_jobs_count, total_jobs_count, failed_jobs_count=0):
    """Blocking popup shown once every job is done.

    Returns "stay", "detach" (quit, leave the session running) or "close"
    (quit and shut the session down). The last option is the default.
    """
    height, width = stdscr.getmaxyx()
    popup_height = min(FINISHED_POPUP_FIRST_OPTION_Y + len(options) + 3, max(3, height - 2))
    popup_width = min(56, max(24, width - 4))
    start_y = max(0, (height - popup_height) // 2)
    start_x = max(0, (width - popup_width) // 2)

    try:
        popup_win = curses.newwin(popup_height, popup_width, start_y, start_x)
    except curses.error:
        return "stay"

    popup_win.keypad(True)
    popup_win.timeout(-1)
    curses.flushinp()

    selected = 1
    while True:
        update_finished_popup(popup_win, popup_width, popup_height, options, selected, retired_jobs_count, total_jobs_count,
                              failed_jobs_count)
        key = popup_win.getch()

        if key == curses.KEY_UP:
            selected = (selected - 1) % len(options)
        elif key == curses.KEY_DOWN:
            selected = (selected + 1) % len(options)
        elif key in (curses.KEY_ENTER, 10, 13):
            return options[selected][1]
        elif ord("1") <= key < ord("1") + len(options):
            return options[key - ord("1")][1]
        elif key in (27, ord("q"), ord("Q")):
            return "stay"
        elif key == curses.KEY_RESIZE:
            return "stay"
        elif key == curses.KEY_MOUSE:
            try:
                _, mouse_x, mouse_y, _, button = curses.getmouse()
            except curses.error:
                continue

            # Mouse coordinates are absolute: bring them back into popup space.
            rel_y = mouse_y - start_y
            rel_x = mouse_x - start_x

            index = finished_popup_option_at(popup_width, popup_height, options, rel_y, rel_x)
            if index >= 0:
                # Highlight what is under the pointer, whatever the event.
                selected = index

            if not (button & curses.BUTTON1_CLICKED or button & curses.BUTTON1_PRESSED
                    or button & curses.BUTTON1_DOUBLE_CLICKED):
                continue

            close_y, close_x_start, close_x_end = finished_popup_close_button(popup_width)
            if rel_y == close_y and close_x_start <= rel_x <= close_x_end:
                return "stay"
            if index >= 0:
                return options[index][1]
            if not (0 <= rel_y < popup_height and 0 <= rel_x < popup_width):
                # A click outside the popup dismisses it, like the other dialogs.
                return "stay"


def update_logs(handler, logs_win, selected_job, logs_height, width):
    history = selected_job.log_history
    log_length = len(history)

    if logs_win is None or logs_height <= 0:
        handler.previous_log_size = log_length
        return

    max_log_position = max(0, log_length - logs_height)
    if selected_job.autoscroll:
        selected_job.log_position = max_log_position
    else:
        selected_job.log_position = max(0, min(int(selected_job.log_position), max_log_position))

    x_offset = int(getattr(selected_job, "log_x_offset", 0))

    # Keep a right bound to avoid scrolling past the longest available line.
    if width > 0:
        max_visible_len = int(getattr(selected_job, "_max_visible_log_len", 0))
        cache_size = int(getattr(selected_job, "_max_visible_log_len_cache_size", -1))
        if max_visible_len <= 0 or cache_size != log_length or selected_job.log_changed:
            max_visible_len = 0
            for raw_line in history:
                line = raw_line
                if handler.formatter is not None:
                    line = handler.formatter.replace_in_line(line)
                max_visible_len = max(max_visible_len, _visible_text_len(line))
            selected_job._max_visible_log_len = max_visible_len
            selected_job._max_visible_log_len_cache_size = log_length
        max_offset = max(0, max_visible_len - width) + 1
        if x_offset > max_offset:
            x_offset = max_offset
            selected_job.log_x_offset = x_offset
    else:
        selected_job.log_x_offset = 0
        x_offset = 0

    if log_length < handler.previous_log_size:
        for i in range(log_length, handler.previous_log_size):
            try:
                logs_win.move(i, 0)
                logs_win.clrtoeol()
            except curses.error:
                pass

    handler.converter.reset_format()

    for i, line in enumerate(history[selected_job.log_position : selected_job.log_position + logs_height]):
        try:
            logs_win.move(i, 0)
            if handler.formatter is not None:
                line = handler.formatter.replace_in_line(line)
            handler.converter.add_ansi_str(logs_win, line, width=width, dim=handler.showing_help, x_offset=x_offset)
        except curses.error:
            pass

    selection = getattr(handler, "log_selection", None)
    if selection is not None and selection.job_index == handler.selected_job_index and not selection.is_empty():
        for i in range(logs_height):
            line = selected_job.log_position + i
            if line >= log_length:
                break
            span = selection.line_span(line, len(_plain_log_line(handler, history[line])))
            if span is None:
                continue
            start = max(0, span[0] - x_offset)
            end = min(span[1] - x_offset, width)
            if end <= start:
                continue
            try:
                logs_win.chgat(i, start, end - start, curses.A_REVERSE)
            except curses.error:
                pass

    logs_win.refresh()
    handler.previous_log_size = log_length


def help_popup_keys():
    """Every key the help popup lists, as (key, alternate key, description)."""
    help_text = [
        ("q"          , "Quit (asks before killing jobs)"),
        ("d"          , "Detach: quit, jobs keep running"),
        ("PageDown  n", "Select next job"),
        ("PageUp    p", "Select previous job"),
        ("Up         ", "Scroll log up"),
        ("Down       ", "Scroll log down"),
        ("Left/Right", "Scroll log sideways"),
        ("Home/End"   , "Scroll to top/bottom"),
        ("+/-"        , "Change progress window size"),
        (">/<      ./,", "More / fewer parallel jobs"),
        ("a"          , "Toggle auto-pause on overload"),
        ("Space"      , "Pause selected job"),
        ("k"          , "Kill selected job"),
        ("s"          , "Start/resume selected job"),
        ("r"          , "Re-run selected job (same job directory)"),
        ("t"          , "Switch theme"),
        ("c"          , "Change cursor mode"),
        ("y  R-click", "Copy log selection"),
        ("h         ?", "Show help"),
    ]

    if can_open_path_in_explorer():
        help_text.insert(-2, ("o", "Open current job work path"))
    return help_text


#: First row of the key list in the help popup, under the title and the column headers.
HELP_FIRST_ROW = 4


def help_popup_rows(popup_height):
    """How many keys the help popup has room for."""
    return max(0, popup_height - 2 - HELP_FIRST_ROW)


def update_help_popup(popup_win, popup_width, popup_height, offset=0, ascii_only=False):
    """
    Draw the help popup, its list scrolled down by `offset` keys.

    A list taller than the popup scrolls (Up/Down), and says that it goes on
    above or below rather than being cut without a word.

    Returns:
        int: the offset actually used, clamped to what the list allows.
    """
    help_text = help_popup_keys()
    rows = help_popup_rows(popup_height)
    offset = max(0, min(int(offset), max(0, len(help_text) - rows)))

    popup_win.erase()
    popup_win.box()

    try:
        close_x = popup_width - 5
        popup_win.addstr(1, close_x, " X ", curses.A_BOLD | curses.color_pair(REVERSE_RED))
    except curses.error:
        pass

    if popup_height > 2:
        try:
            text = " Help Menu "
            popup_win.addstr(1, (popup_width - len(text)) // 2, text, curses.A_BOLD | curses.A_REVERSE)
        except curses.error:
            pass
        if popup_height > 5:
            try:
                popup_win.addstr(3, 3, "Key      Alt", curses.A_BOLD)
                popup_win.addstr(3, 17, "Description", curses.A_BOLD)
                if offset > 0:
                    more = "^ more" if ascii_only else "\u25b2 more"
                    popup_win.addstr(3, max(17, popup_width - len(more) - 3), more, curses.A_DIM)
                for i, (key, desc) in enumerate(help_text[offset:offset + rows], start=HELP_FIRST_ROW):
                    popup_win.addstr(i, 3, f"{key}", curses.color_pair(CYAN))
                    popup_win.addstr(i, 17, f"{desc}"[: max(0, popup_width - 18)])
            except curses.error:
                pass
    below = offset + rows < len(help_text)
    try:
        if below or offset > 0:
            text = "Up/Down: scroll | q, h: close"
            if below:
                text = ("v more | " if ascii_only else "\u25bc more | ") + text
        else:
            text = "Press 'q' or 'h' to close"
        text = text[: max(0, popup_width - 2)]
        popup_win.addstr(max(popup_height - 2, 1), max(1, (popup_width - len(text)) // 2), text, curses.A_DIM)
    except curses.error:
        pass
    popup_win.refresh()
    return offset


def read_escape_sequence(stdscr, timeout=50, max_length=12):
    """Reads whatever follows an ESC byte, without blocking."""
    sequence = ""
    stdscr.nodelay(True)
    try:
        for _ in range(max_length):
            code = stdscr.getch()
            if code == -1:
                break
            if 0 <= code < 128:
                sequence += chr(code)
                if len(sequence) > 1 and sequence[-1].isalpha():
                    break
    except curses.error:
        pass
    finally:
        stdscr.nodelay(False)
        stdscr.timeout(timeout)
    return sequence


def click_on_job(handler, progress_win, y, x):
    if progress_win.enclose(y, x):
        relative_y = y - progress_win.getbegyx()[0]
        rows = progress_win.getmaxyx()[0]
        visible = handler.visible_jobs(rows=rows)
        pinned_count = sum(1 for _, job in visible if job.pinned)
        if pinned_count > 0:
            if relative_y == pinned_count:
                return -1  # clicked on the pinned/scrollable separator
            if relative_y > pinned_count:
                relative_y -= 1
        if 0 <= relative_y < len(visible):
            return visible[relative_y][0]
    return -1


def no_color():
    """Whether colors are turned off (https://no-color.org): bold and reverse video stay."""
    return os.environ.get("NO_COLOR", "") != ""


def init_colors():
    """Define the color pairs of the monitor, all of them plain under NO_COLOR."""
    try:
        if not curses.has_colors():
            return  # vt100 and the like: bold and reverse video only
        curses.start_color()
        curses.use_default_colors()
    except curses.error:
        return
    light = AnsiToCursesConverter.LIGHT_OFFSET
    pairs = {
        NORMAL: (-1, -1),
        RED: (curses.COLOR_RED, -1),
        YELLOW: (curses.COLOR_YELLOW, -1),
        GREEN: (curses.COLOR_GREEN, -1),
        BLUE: (curses.COLOR_BLUE, -1),
        CYAN: (curses.COLOR_CYAN, -1),
        BLACK: (curses.COLOR_BLACK, -1),
        WHITE: (curses.COLOR_WHITE, -1),
        GREY: (curses.COLOR_BLACK + light, -1),
        REVERSE: (curses.COLOR_BLACK, curses.COLOR_WHITE + light),
        REVERSE_RED: (-1, curses.COLOR_RED + light),
        REVERSE_YELLOW: (-1, curses.COLOR_YELLOW + light),
        REVERSE_GREEN: (-1, curses.COLOR_GREEN + light),
        REVERSE_BLUE: (-1, curses.COLOR_BLUE + light),
        REVERSE_CYAN: (-1, curses.COLOR_CYAN + light),
        REVERSE_BLACK: (-1, curses.COLOR_BLACK + light),
        REVERSE_WHITE: (-1, curses.COLOR_WHITE + light),
        REVERSE_GREY: (-1, curses.COLOR_BLACK),
    }
    plain = no_color()
    for pair, (foreground, background) in pairs.items():
        if plain:
            foreground, background = -1, -1
        try:
            curses.init_pair(pair, foreground, background)
        except (curses.error, ValueError):
            # A terminal with 8 colors has no "light" ones.
            try:
                curses.init_pair(pair, foreground % 8 if foreground > 0 else foreground,
                                 background % 8 if background > 0 else background)
            except (curses.error, ValueError):
                pass


def highlight_attr():
    """What marks the selected option of a popup: a reverse color, or reverse video without colors."""
    return curses.color_pair(REVERSE) | (curses.A_REVERSE if no_color() else 0)


def curses_main(handler, stdscr):
    # Hide the cursor where the terminal can: vt100 cannot, and still shows
    # the monitor well enough.
    try:
        curses.curs_set(0)
    except curses.error:
        pass

    # Enable mouse actions (disable selection)
    from ._vendor.curses_helper import (
        disable_selection,
        enable_selection,
    )
    disable_selection()

    init_colors()

    height, width = stdscr.getmaxyx()
    old_width = width
    old_height = height

    # Adjust window positions
    header_height = 1
    separator_height = 1
    help_height = 1
    header_win = None
    separator_top_win = None
    progress_win = None
    separator_middle_win = None
    logs_win = None
    bottom_bar = None
    popup_win = None

    def _max_progress_height(screen_height):
        # Header + top separator + progress + middle separator + logs + help bar.
        return max(1, int(screen_height) - header_height - 2 * separator_height - help_height)

    def _max_useful_progress_height():
        # Total rows needed to show every job: pinned + scrollable + the separator
        # row between them (only present when both groups are non-empty).
        pinned_count = len(handler.pinned_job_list)
        scrollable_count = handler.scrollable_count
        return pinned_count + scrollable_count + (1 if pinned_count and scrollable_count else 0)

    def _clamp_progress_height(desired_height, screen_height):
        return max(1, min(int(desired_height), _max_progress_height(screen_height), _max_useful_progress_height()))

    def scroll_room():
        """How many rows are left for the jobs that scroll, once the pinned ones (and their
        separator, when there also are scrolled jobs) are drawn."""
        pinned_count = len(handler.pinned_job_list)
        reserved = pinned_count + (1 if pinned_count and handler.scrollable_count else 0)
        return max(1, progress_height - reserved)

    def sync_progress_indices():
        # The window scrolls over the jobs that are not pinned: the pinned ones
        # are drawn above it, whatever it is showing (see visible_jobs).
        scrollable = handler.scrollable_count
        if scrollable <= 0:
            handler.job_index_start = 0
            handler.job_index_end = 0
            return

        room = scroll_room()
        max_start = max(0, scrollable - 1)
        handler.job_index_start = max(0, min(handler.job_index_start, max_start))
        # If there is more room than jobs left below the current start, pull the
        # start back up (revealing jobs hidden above) so the window fills all the
        # way to the bottom instead of leaving blank rows there.
        shortfall = (handler.job_index_start + room) - scrollable
        if shortfall > 0:
            handler.job_index_start = max(0, handler.job_index_start - shortfall)
        handler.job_index_end = min(scrollable, handler.job_index_start + room)
        if handler.job_index_end <= handler.job_index_start:
            handler.job_index_end = handler.job_index_start + 1

    # The height the user gave the progress window (+/-, dragging the
    # separator), or None for the default: as many rows as there are jobs, up
    # to half the screen. It is what every resize starts from again, so a
    # window shrunk to almost nothing grows back once the terminal does.
    wanted_height = None

    def _wanted_progress_height(screen_height):
        if wanted_height is not None:
            return _clamp_progress_height(wanted_height, screen_height)
        return _clamp_progress_height(min(screen_height // 2, handler.job_count), screen_height)

    progress_height = _wanted_progress_height(height)
    logs_height = max(0, height - progress_height - 2 * separator_height - help_height - header_height)
    popup_width = min(50, width - 4)
    popup_height = max(3, min(HELP_POPUP_HEIGHT, height - 2))
    start_x = (width - popup_width) // 2
    start_y = (height - popup_height) // 2
    sync_progress_indices()
    last_job_count = handler.job_count

    def keep_selected_visible():
        """Scroll the job list so that the selected job is in sight, if it is one that scrolls."""
        position = handler.scroll_position(handler.selected_job_index)
        if position is None:
            return
        if position < handler.job_index_start:
            handler.job_index_start = position
            sync_progress_indices()
        elif position >= handler.job_index_end:
            handler.job_index_start = position - scroll_room() + 1
            sync_progress_indices()

    def recreate_windows():
        nonlocal header_win, separator_top_win, progress_win, separator_middle_win
        nonlocal logs_win, bottom_bar, popup_win
        nonlocal progress_height, logs_height, popup_width, popup_height, start_x, start_y

        progress_height = _wanted_progress_height(height)
        logs_height = max(0, height - progress_height - 2 * separator_height - help_height - header_height)
        popup_width = min(50, width - 4)
        popup_height = max(3, min(HELP_POPUP_HEIGHT, height - 2))
        start_x = (width - popup_width) // 2
        start_y = (height - popup_height) // 2
        sync_progress_indices()

        header_win = curses.newwin(header_height, width, 0, 0)
        separator_top_win = curses.newwin(separator_height, width, header_height, 0)
        progress_win = curses.newwin(progress_height, width, header_height + separator_height, 0)
        separator_middle_win = curses.newwin(separator_height, width, header_height + separator_height + progress_height, 0)
        logs_win = None
        if logs_height > 0:
            logs_win = curses.newwin(logs_height, width, header_height + separator_height + progress_height + separator_height, 0)
        bottom_bar = curses.newwin(help_height, width, height - help_height, 0)
        popup_win = curses.newwin(popup_height, popup_width, start_y, start_x)
        popup_win.box()

    try:
        recreate_windows()
    except curses.error:
        stdscr.clear()
        try:
            stdscr.addstr(0, 0, "Could not start: window is too small. Press any key to exit", curses.color_pair(RED))
            stdscr.refresh()
        except curses.error:
            pass
        stdscr.getch()
        sys.exit(-1)

    finished = False
    ask_exit = False

    selected_job = handler.job_list[handler.selected_job_index]
    if not hasattr(selected_job, "log_x_offset"):
        selected_job.log_x_offset = 0

    for job in handler.job_list:
        if len(handler.running_job_list) < handler.nb_jobs:
            handler.start_job(job)
        else:
            handler.queue_job(job)

    # Cap the UI loop to ~20 FPS and avoid a tight busy loop.
    stdscr.timeout(50)

    resize = False
    resize_hold = False
    last_click_job = -1
    last_click_time = 0.0
    last_log_click_line = -1
    last_log_click_time = 0.0
    # ncurses collapses every motion report into a bare REPORT_MOUSE_POSITION,
    # whether a button is held or not, so the held state cannot be read off the
    # event: we follow press/release ourselves.
    button1_down = False
    # Set while a press has already been acted on, so the click ncurses may
    # synthesize on release is not acted on a second time.
    press_consumed = False
    # Set when input is still queued: the next cycle then skips the redraw pass
    # and consumes the backlog instead. `pending_key` holds the event that was
    # peeked to find out, since peeking necessarily reads it.
    pending_key = None
    fast_input = False

    cursor_mode = getattr(handler, "cursor_mode", CURSOR_MODES[0])
    if cursor_mode not in CURSOR_MODES:
        cursor_mode = CURSOR_MODES[0]
    hover_job = -1
    hover_separator = False

    # Text selection inside the log window is done by the application itself, so
    # the mouse never has to be handed back to the terminal (which would blind us
    # to hover and clicks) and a selection can reach what the window does not show.
    log_selection = None
    handler.log_selection = None
    status_message = None
    status_message_time = 0.0

    def apply_cursor_mode():
        """Reconfigures the terminal for the current cursor mode."""
        nonlocal hover_job, hover_separator, button1_down, press_consumed, resize_hold
        hover_job = -1
        hover_separator = False
        button1_down = False
        press_consumed = False
        resize_hold = False
        handler.cursor_mode = cursor_mode
        if cursor_mode == "raw":
            enable_selection()
            handler.selection_enabled = True
        else:
            # Motion reports are only worth their cost in "mouse+" mode, which is
            # the only one drawing hover feedback.
            disable_selection(track_motion=(cursor_mode == "mouse+"))
            handler.selection_enabled = False

    apply_cursor_mode()

    def redraw_logs():
        update_logs(handler, logs_win, selected_job, logs_height, width)

    def log_point_at(y, x):
        """(line, column, edge) of a pointer position, clamped into the window.

        `edge` says in which direction the pointer sits outside the window, which
        is what drives auto-scrolling while a selection is being dragged.
        """
        top, left = logs_win.getbegyx()
        rows, cols = logs_win.getmaxyx()
        edge_y = -1 if y < top else (1 if y >= top + rows else 0)
        edge_x = -1 if x < left else (1 if x >= left + cols else 0)
        row = min(max(y - top, 0), max(rows - 1, 0))
        col = min(max(x - left, 0), max(cols - 1, 0))
        line = int(selected_job.log_position) + row
        line = max(0, min(line, max(0, len(selected_job.log_history) - 1)))
        column = int(getattr(selected_job, "log_x_offset", 0)) + col
        return line, column, (edge_y, edge_x)

    def start_log_selection(y, x):
        nonlocal log_selection
        if logs_win is None:
            return
        line, column, _ = log_point_at(y, x)
        log_selection = LogSelection(handler.selected_job_index, (line, column))
        handler.log_selection = log_selection
        selected_job.autoscroll = False
        redraw_logs()

    def select_log_line(line):
        """Selects a whole log line, as a double click in the logs does."""
        nonlocal log_selection
        if logs_win is None:
            return
        history = selected_job.log_history
        if not 0 <= line < len(history):
            return
        length = len(_plain_log_line(handler, history[line]))
        log_selection = LogSelection(handler.selected_job_index, (line, 0))
        log_selection.cursor = (line, max(length, 1))
        # The selection is complete: no drag follows a double click.
        log_selection.dragging = False
        handler.log_selection = log_selection
        selected_job.autoscroll = False
        redraw_logs()

    def extend_log_selection(y, x):
        if log_selection is None or logs_win is None:
            return
        line, column, edge = log_point_at(y, x)
        log_selection.edge = edge
        log_selection.cursor = (line, column)
        redraw_logs()

    def scroll_log_selection():
        """Keeps scrolling while the pointer is held outside the window."""
        if log_selection is None or not log_selection.dragging:
            return
        edge_y, edge_x = log_selection.edge
        if not edge_y and not edge_x:
            return
        moved = False
        if edge_y < 0 and selected_job.log_position > 0:
            selected_job.log_position = max(0, selected_job.log_position - 1)
            moved = True
        elif edge_y > 0 and selected_job.log_position + logs_height < len(selected_job.log_history):
            selected_job.log_position += 1
            moved = True
        offset = int(getattr(selected_job, "log_x_offset", 0))
        if edge_x < 0 and offset > 0:
            selected_job.log_x_offset = max(0, offset - 2)
            moved = True
        elif edge_x > 0:
            selected_job.log_x_offset = offset + 2
            moved = True
        if not moved:
            return
        # Drag the free end of the selection along with the view.
        line, column = log_selection.cursor
        if edge_y:
            line = int(selected_job.log_position) + (0 if edge_y < 0 else max(0, logs_height - 1))
            line = max(0, min(line, max(0, len(selected_job.log_history) - 1)))
        if edge_x:
            offset = int(getattr(selected_job, "log_x_offset", 0))
            column = offset if edge_x < 0 else offset + max(0, width - 1)
        log_selection.cursor = (line, column)
        selected_job.autoscroll = False
        redraw_logs()

    def clear_log_selection():
        nonlocal log_selection
        if log_selection is None:
            return
        log_selection = None
        handler.log_selection = None
        redraw_logs()

    def copy_log_selection():
        nonlocal status_message, status_message_time, bottom_bar_drawn
        if log_selection is None or log_selection.is_empty():
            return
        job_index = log_selection.job_index
        if not 0 <= job_index < len(handler.job_list):
            return
        text = log_selection.text(handler, handler.job_list[job_index].log_history)
        lines = text.count("\n") + 1
        target = copy_to_clipboard(text)
        if target is None:
            status_message = "Could not reach any clipboard (install xclip, wl-copy or xsel)"
        else:
            status_message = "Copied {} line{} to the clipboard".format(lines, "" if lines == 1 else "s")
        status_message_time = time.time()
        bottom_bar_drawn = False

    help_static_drawn = False
    bottom_bar_drawn = False
    bottom_bar_selection = False
    finished_popup_shown = False
    finished_popup_pending = False
    finished_draw_cycles = 0

    handler.showing_help = False
    help_offset = 0

    paused_jobs_count = 0

    def get_runtime_counters():
        nonlocal paused_jobs_count
        counts = handler.runtime_counts()
        active_jobs_count = int(counts["running"])
        paused_jobs_count = int(counts["paused"])
        queued_jobs_count = int(counts["queued"])
        retired_jobs_count = int(counts["retired"])
        total_jobs_count = int(counts["total"])

        # A paused job is not over: it waits for someone to resume it.
        finished_now = active_jobs_count == 0 and queued_jobs_count == 0 and paused_jobs_count == 0
        if total_jobs_count > 0:
            finished_now = finished_now and retired_jobs_count >= total_jobs_count

        # "-E" in a session shared with other runs: what closes the monitor is
        # the end of the jobs of this run, not of the whole session.
        watched = handler.watched_jobs_over()
        if handler.auto_exit and watched is not None:
            finished_now = watched

        return active_jobs_count, queued_jobs_count, retired_jobs_count, total_jobs_count, finished_now

    while True:
        if handler._request_curses_exit:
            handler.monitor_exit = "shutdown"
            update_exit(bottom_bar)
            handler.terminate_all_jobs()
            return False

        height, width = stdscr.getmaxyx()

        # While events are still queued, skip the whole redraw/bookkeeping
        # pass and consume them first. Under load a full cycle costs far more
        # than 50 ms, and handling a single event per cycle makes the pointer
        # lag behind by the whole backlog: hover trails, and a release read
        # seconds late leaves a drag or a selection stuck.
        if not fast_input:
            try:
                with handler._lock:
                    handler.process_pending_commands(max_commands=200)
            except Exception as e:
                try:
                    if 0 <= handler.selected_job_index < len(handler.job_list):
                        handler.job_list[handler.selected_job_index].log_history.append(
                            printc.colors.RED + f"API command error: {e}" + printc.colors.ENDC
                        )
                except Exception:
                    pass


            # Jobs added while the monitor is attached: grow the progress window so the
            # new ones are visible, unless it already takes more than half the screen.
            current_job_count = handler.job_count
            if current_job_count > last_job_count:
                grown = progress_height
                for _ in range(current_job_count - last_job_count):
                    if grown > height // 2:
                        break
                    grown = _clamp_progress_height(grown + 1, height)
                if wanted_height is not None:
                    wanted_height = max(wanted_height, grown)
                else:
                    grown = _wanted_progress_height(height)
                if grown != progress_height:
                    progress_height = grown
                    sync_progress_indices()
                    resize = True
            last_job_count = current_job_count

            if height != old_height or width != old_width or resize:
                try:
                    recreate_windows()
                    keep_selected_visible()
                    update_logs(handler, logs_win, selected_job, logs_height, width)
                except curses.error:
                    try:
                        stdscr.clear()
                        stdscr.addstr(0, 0, "Window is too small!", curses.color_pair(RED))
                        stdscr.refresh()
                    except curses.error:
                        pass

                old_width = width
                old_height = height
                resize = False
                help_static_drawn = False
                bottom_bar_drawn = False

            with handler._lock:
                handler._update_jobs_state(
                    selected_job=selected_job,
                    on_selected_retired=lambda: update_logs(handler, logs_win, selected_job, logs_height, width),
                )
                handler._check_resource_guard_unlocked()

            sync_progress_indices()

            active_jobs_count, queued_jobs_count, retired_jobs_count, total_jobs_count, finished_now = get_runtime_counters()
            finished = finished or finished_now

            # The session was stopped from elsewhere: nothing left to watch.
            if getattr(handler, "session_gone", False):
                handler.monitor_exit = "gone"
                return False

            # Completion is announced below, once the final progress/logs have been drawn.
            if finished and total_jobs_count > 0 and not finished_popup_shown and not handler.auto_exit:
                finished_popup_pending = True

            if not handler.showing_help:
                help_static_drawn = False

                update_header(handler, header_win, active_jobs_count, retired_jobs_count, total_jobs_count, width,
                              paused_jobs_count)
                update_separator(handler, separator_top_win, 0 if handler.pinned_job_list else handler.job_index_start, 0, width)

                # Keep the local selected_job reference synchronized with handler state.
                # This is required when job objects are replaced (e.g. daemon attach mode).
                if handler.job_count > 0:
                    handler.selected_job_index = max(0, min(handler.selected_job_index, handler.job_count - 1))
                    refreshed_selected_job = handler.job_list[handler.selected_job_index]
                    if refreshed_selected_job is not selected_job:
                        selected_job = refreshed_selected_job
                        selected_job.log_position = max(0, len(selected_job.log_history) - logs_height)
                        selected_job.autoscroll = True
                        selected_job.log_x_offset = 0
                        update_logs(handler, logs_win, selected_job, logs_height, width)

                update_progress_window(handler, progress_win, hover_job=hover_job)
                update_separator(handler, separator_middle_win, handler.scrollable_count, handler.job_index_end, width,
                                 hover=hover_separator)
            elif not help_static_drawn:
                # Draw a single dimmed snapshot behind the popup, then keep it stable
                # while help is open to avoid flicker from continuous progress redraws.
                update_header(handler, header_win, active_jobs_count, retired_jobs_count, total_jobs_count, width,
                              paused_jobs_count)
                update_separator(handler, separator_top_win, 0 if handler.pinned_job_list else handler.job_index_start, 0, width)
                update_progress_window(handler, progress_win)
                update_separator(handler, separator_middle_win, handler.scrollable_count, handler.job_index_end, width)
                update_logs(handler, logs_win, selected_job, logs_height, width)
                help_static_drawn = True

            with handler._lock:
                handler.read_process_output()

            if not handler.showing_help and selected_job.autoscroll and selected_job.log_changed:
                selected_job.log_position = max(0, len(selected_job.log_history) - logs_height)
                update_logs(handler, logs_win, selected_job, logs_height, width)

            if not handler.showing_help and width != old_width:
                update_logs(handler, logs_win, selected_job, logs_height, width)
            old_width = width

            # Announce completion once, and let the user pick what to do next.
            # Wait for a couple of full redraw cycles so the final progress bars and
            # log lines are visible behind the popup.
            if finished_popup_pending and not handler.showing_help:
                finished_draw_cycles += 1
                if finished_draw_cycles >= 2:
                    finished_popup_pending = False
                    finished_popup_shown = True

                    # Dim the whole background behind the popup, like the help menu does.
                    handler.showing_help = True
                    update_header(handler, header_win, active_jobs_count, retired_jobs_count, total_jobs_count, width,
                              paused_jobs_count)
                    update_separator(handler, separator_top_win, 0 if handler.pinned_job_list else handler.job_index_start, 0, width)
                    update_progress_window(handler, progress_win)
                    update_separator(handler, separator_middle_win, handler.scrollable_count, handler.job_index_end, width)
                    update_logs(handler, logs_win, selected_job, logs_height, width)

                    try:
                        failed_jobs_count = sum(
                            1 for job in handler.job_list if job.status in ("failed", "killed", "canceled")
                        )
                        choice = show_finished_popup(
                            stdscr, finished_popup_options(handler), retired_jobs_count, total_jobs_count,
                            failed_jobs_count,
                        )
                    finally:
                        handler.showing_help = False

                    if choice == "detach":
                        handler.monitor_exit = "detach"
                        return True
                    if choice == "close":
                        handler.monitor_exit = "close"
                        on_quit_after_finished(handler)
                        return True
                    # "stay": redraw the whole screen behind the popup.
                    try:
                        stdscr.clear()
                        stdscr.refresh()
                    except curses.error:
                        pass
                    resize = True
                    help_static_drawn = False
                    stdscr.timeout(50)
                    curses.flushinp()
                    fast_input = False
                    pending_key = None
                    continue

        if pending_key is not None:
            key = pending_key
            pending_key = None
        else:
            key = stdscr.getch()

        # A selection dragged past the edge of the window keeps scrolling while
        # the button is held there, even if the pointer no longer moves.
        scroll_log_selection()

        def update_selected_job():
            clear_log_selection()
            job = handler.job_list[handler.selected_job_index]
            job.log_position = max(0, len(job.log_history) - logs_height)
            job.autoscroll = True
            job.log_x_offset = 0
            return job

        def scroll_up_logs(selected):
            if selected.log_position > 0:
                selected.log_position = max(0, selected.log_position - 3)
                selected.autoscroll = False
                update_logs(handler, logs_win, selected, logs_height, width)

        def scroll_down_logs(selected):
            if selected.log_position + logs_height < len(selected.log_history):
                selected.log_position = min(len(selected.log_history) - logs_height, selected.log_position + 3)
                selected.autoscroll = False
                update_logs(handler, logs_win, selected, logs_height, width)

        def scroll_left_logs(selected):
            current = int(getattr(selected, "log_x_offset", 0))
            selected.log_x_offset = max(0, current - 4)
            update_logs(handler, logs_win, selected, logs_height, width)

        def scroll_right_logs(selected):
            current = int(getattr(selected, "log_x_offset", 0))
            selected.log_x_offset = current + 4
            update_logs(handler, logs_win, selected, logs_height, width)

        def scroll_up_progress():
            if handler.job_index_start > 0:
                handler.job_index_start -= 1
                sync_progress_indices()

        def scroll_down_progress():
            if handler.job_index_end < handler.scrollable_count:
                handler.job_index_start += 1
                sync_progress_indices()

        def scroll_to_selected():
            """Bring the selected job into the window, if it is one that scrolls."""
            position = handler.scroll_position(handler.selected_job_index)
            if position is None:
                return
            if position < handler.job_index_start:
                handler.job_index_start = position
                sync_progress_indices()
            elif position >= handler.job_index_end:
                handler.job_index_start = position - scroll_room() + 1
                sync_progress_indices()

        if not handler.showing_help:
            if key == curses.KEY_MOUSE:
                try:
                    _, x, y, _, button = curses.getmouse()
                except curses.error:
                    x = y = button = None

                # A pure motion report carries no bit inside ALL_MOUSE_EVENTS.
                motion_only = button is not None and not (button & curses.ALL_MOUSE_EVENTS)

                # Follow the button state on the events that actually carry it.
                # "press acted on" is tracked alongside so the click ncurses may
                # synthesize when the button comes back up is not acted on twice.
                press_down = False
                if button is not None and not motion_only:
                    if button & curses.BUTTON1_PRESSED:
                        button1_down = True
                        press_down = True
                        press_consumed = True
                    elif button & (curses.BUTTON1_CLICKED | curses.BUTTON1_DOUBLE_CLICKED):
                        button1_down = False
                        press_down = not press_consumed
                        press_consumed = False
                    elif button & curses.BUTTON1_RELEASED:
                        button1_down = False
                        press_consumed = False

                # A right click anywhere copies the current selection: it is
                # the gesture most terminals use for the clipboard, and it never
                # collides with the left button state tracked above.
                if button is not None and button & (curses.BUTTON3_PRESSED | curses.BUTTON3_CLICKED):
                    copy_log_selection()

                if resize_hold:
                    if not button1_down:
                        resize_hold = False
                    elif button is not None:
                        y = min(y, height - 2)
                        relative_y = y - (header_height + separator_height)
                        new_progress_height = _clamp_progress_height(relative_y, height)
                        if new_progress_height != progress_height:
                            progress_height = wanted_height = new_progress_height
                            sync_progress_indices()
                            keep_selected_visible()
                            resize = True

                if log_selection is not None and log_selection.dragging:
                    if not button1_down:
                        log_selection.dragging = False
                        log_selection.edge = (0, 0)
                        if log_selection.is_empty():
                            clear_log_selection()
                    elif button is not None:
                        extend_log_selection(y, x)

                if cursor_mode == "mouse+" and button is not None:
                    dragging = resize_hold or (log_selection is not None and log_selection.dragging)
                    hover_separator = resize_hold or (not dragging and separator_middle_win.enclose(y, x))
                    hover_job = -1 if dragging else click_on_job(handler, progress_win, y, x)

                if button is None or motion_only:
                    pass
                elif press_down:
                    now = time.time()
                    # Act on the press: whether ncurses reports a press or a
                    # click depends on timing, and waiting for the release
                    # loses the event whenever it reports a plain release.
                    if separator_middle_win.enclose(y, x):
                        resize_hold = True
                    elif logs_win is not None and logs_win.enclose(y, x):
                        # Pressing in the logs starts a selection of our own: the
                        # terminal never gets the mouse back, so hover and clicks
                        # keep working while text can still be selected and copied.
                        line = log_point_at(y, x)[0]
                        double_click = (
                            last_log_click_line == line and now - last_log_click_time <= DOUBLE_CLICK_DELAY
                        )
                        last_log_click_line = -1 if double_click else line
                        last_log_click_time = now
                        if double_click:
                            select_log_line(line)
                        else:
                            start_log_selection(y, x)
                    else:
                        clear_log_selection()
                        job_index = click_on_job(handler, progress_win, y, x)
                        if job_index >= 0:
                            handler.selected_job_index = job_index
                            selected_job = update_selected_job()
                            update_logs(handler, logs_win, selected_job, logs_height, width)

                            double_click = (
                                last_click_job == job_index and now - last_click_time <= DOUBLE_CLICK_DELAY
                            )
                            last_click_job = job_index
                            last_click_time = now

                            if double_click and can_open_path_in_explorer():
                                last_click_job = -1
                                try:
                                    open_path_in_explorer(handler.job_list[job_index].tmp_dir)
                                except NotImplementedError:
                                    pass
                elif button & curses.BUTTON4_PRESSED:
                    if progress_win.enclose(y, x):
                        if handler.job_index_start > 0:
                            scroll_up_progress()
                    elif logs_win is not None and logs_win.enclose(y, x):
                        scroll_up_logs(selected_job)
                elif button & curses.BUTTON5_PRESSED:
                    if progress_win.enclose(y, x):
                        if handler.job_index_end < handler.scrollable_count:
                            scroll_down_progress()
                    elif logs_win is not None and logs_win.enclose(y, x):
                        scroll_down_logs(selected_job)

            elif key == curses.KEY_PPAGE or key == ord("p") or key == ord("P"):
                if handler.selected_job_index > 0:
                    handler.selected_job_index -= 1
                scroll_to_selected()
                selected_job = update_selected_job()
                update_logs(handler, logs_win, selected_job, logs_height, width)

            elif key == curses.KEY_NPAGE or key == ord("n") or key == ord("N"):
                if handler.selected_job_index < len(handler.job_list) - 1:
                    handler.selected_job_index += 1
                scroll_to_selected()
                selected_job = update_selected_job()
                update_logs(handler, logs_win, selected_job, logs_height, width)

            elif key == curses.KEY_UP:
                scroll_up_logs(selected_job)

            elif key == curses.KEY_DOWN:
                scroll_down_logs(selected_job)

            elif key == curses.KEY_LEFT:
                scroll_left_logs(selected_job)

            elif key == curses.KEY_RIGHT:
                scroll_right_logs(selected_job)

            elif key == ord("d") or key == ord("D"):
                handler.monitor_exit = "detach"
                return True

            elif key == curses.KEY_HOME:
                selected_job.log_position = 0
                selected_job.autoscroll = False
                selected_job.log_x_offset = 0
                update_logs(handler, logs_win, selected_job, logs_height, width)

            elif key == curses.KEY_END:
                selected_job.log_position = max(0, len(selected_job.log_history) - logs_height)
                selected_job.autoscroll = True
                update_logs(handler, logs_win, selected_job, logs_height, width)

            elif key == ord("+") or key == ord("="):
                new_progress_height = _clamp_progress_height(progress_height + 1, height)
                if new_progress_height != progress_height:
                    progress_height = wanted_height = new_progress_height
                    sync_progress_indices()
                    keep_selected_visible()
                    resize = True

            elif key == ord("-") or key == ord("_"):
                new_progress_height = _clamp_progress_height(progress_height - 1, height)
                if new_progress_height != progress_height:
                    progress_height = wanted_height = new_progress_height
                    sync_progress_indices()
                    # The selected job stays in sight: its log is the one shown.
                    keep_selected_visible()
                    resize = True

            elif key == ord(">") or key == ord("."):
                handler.set_nb_jobs(int(getattr(handler, "nb_jobs", 1)) + 1)

            elif key == ord("<") or key == ord(","):
                handler.set_nb_jobs(int(getattr(handler, "nb_jobs", 1)) - 1)

            elif key == ord("a") or key == ord("A"):
                handler.set_resource_guard(not getattr(handler, "resource_guard_enabled", False))

            elif key == ord("c") or key == ord("C"):
                cursor_mode = CURSOR_MODES[(CURSOR_MODES.index(cursor_mode) + 1) % len(CURSOR_MODES)]
                apply_cursor_mode()
                bottom_bar_drawn = False

            elif key == ord('k') or key == ord('K'):
                handler.kill_or_cancel_job(handler.selected_job_index)

            elif key == ord(' '):
                handler.pause_job(handler.selected_job_index)

            elif key == ord('s') or key == ord('S'):
                handler.start_or_resume_job(handler.selected_job_index)

            elif key == ord('r') or key == ord('R'):
                handler.restart_job(handler.selected_job_index)

            elif key == ord('o') or key == ord('O'):
                if can_open_path_in_explorer():
                    handler.open_job_path(handler.selected_job_index)

            elif key == ord("y") or key == ord("Y"):
                copy_log_selection()

            elif key == 27:
                # Only a bare Escape counts: anything else is an escape sequence
                # we have no binding for and must be swallowed whole.
                sequence = read_escape_sequence(stdscr)
                if sequence:
                    pass
                elif log_selection is not None:
                    clear_log_selection()
                elif handler.auto_exit and finished:
                    handler.monitor_exit = "auto"
                    return True

            elif key == ord("t") or key == ord("T"):
                handler.next_theme()

            elif key in [ord("h"), ord("H"), ord("?")]:
                handler.showing_help = True
                help_offset = 0
                help_static_drawn = False

            else:
                if handler.auto_exit and finished:
                    handler.monitor_exit = "auto"
                    return True
                if key == ord("q") or key == ord("Q"):
                    if not finished and hasattr(handler, "_sync_snapshot"):
                        try:
                            handler._sync_snapshot(force=True)
                        except Exception:
                            pass

                        active_jobs_count, queued_jobs_count, retired_jobs_count, total_jobs_count, finished_now = get_runtime_counters()
                        finished = finished or finished_now

                    if finished:
                        handler.monitor_exit = "close"
                        on_quit_after_finished(handler)
                        return True
                    ask_exit = True
                    bottom_bar_drawn = False

        else:
            if key == curses.KEY_MOUSE:
                _, mouse_x, mouse_y, _, button = curses.getmouse()
                close_x = start_x + popup_width - 5
                close_y = start_y + 1

                clicked = button is not None and button & (curses.BUTTON1_CLICKED | curses.BUTTON1_PRESSED)
                if clicked and mouse_y == close_y and close_x <= mouse_x <= close_x + 2:
                    handler.showing_help = False
                    if logs_win is not None:
                        logs_win.erase()
                    update_logs(handler, logs_win, selected_job, logs_height, width)

            elif key in (curses.KEY_UP, curses.KEY_PPAGE):
                help_offset = max(0, help_offset - (1 if key == curses.KEY_UP else help_popup_rows(popup_height)))

            elif key in (curses.KEY_DOWN, curses.KEY_NPAGE):
                help_offset += 1 if key == curses.KEY_DOWN else help_popup_rows(popup_height)

            elif key in [ord('h'), ord('H'), ord('?'), ord('q'), ord('Q')]:
                handler.showing_help = False
                if logs_win is not None:
                    logs_win.erase()
                update_logs(handler, logs_win, selected_job, logs_height, width)

        if ask_exit:
            can_detach = callable(getattr(handler, "on_quit_after_finished", None))
            answer = show_exit_confirmation(bottom_bar, can_detach=can_detach)
            if answer == "kill":
                handler.monitor_exit = "kill"
                handler.monitor_exit_counts = handler.runtime_counts()
                update_exit(bottom_bar)
                handler.terminate_all_jobs()
                return False
            if answer == "detach":
                handler.monitor_exit = "detach"
                return True
            if answer == "cancel":
                ask_exit = False
                bottom_bar_drawn = False
        else:
            if status_message is not None and time.time() - status_message_time >= STATUS_MESSAGE_DELAY:
                status_message = None
                bottom_bar_drawn = False
            has_selection = log_selection is not None and not log_selection.is_empty()
            if has_selection != bottom_bar_selection:
                bottom_bar_selection = has_selection
                bottom_bar_drawn = False
            if not bottom_bar_drawn:
                # The bottom bar is static: redrawing it on every cycle would
                # cancel any text selection the user is making in "raw" mode.
                if status_message is not None:
                    update_status_message(bottom_bar, status_message)
                elif bottom_bar_selection:
                    update_copy_help(bottom_bar)
                else:
                    update_help(bottom_bar, cursor_mode)
                bottom_bar_drawn = True

        # Draw help popup last so it always stays above logs/progress redraws.
        if handler.showing_help and not fast_input:
            help_offset = update_help_popup(popup_win, popup_width, popup_height, offset=help_offset,
                                            ascii_only=handler.theme.get("bar") == "-")

        # Look ahead: if another event is already waiting, run the next cycle in
        # fast mode so the queue is drained at input speed rather than at redraw
        # speed. Mouse motion reports arrive in bursts and are cheap to discard.
        stdscr.nodelay(True)
        try:
            pending_key = stdscr.getch()
        except curses.error:
            pending_key = -1
        finally:
            stdscr.nodelay(False)
            stdscr.timeout(50)
        if pending_key == -1:
            pending_key = None
        fast_input = pending_key is not None


def run(handler):
    from ._vendor.curses_helper import enable_selection

    try:
        curses.wrapper(lambda stdscr: curses_main(handler, stdscr))
    finally:
        # Make sure the terminal does not stay in mouse tracking mode after exit.
        enable_selection()
