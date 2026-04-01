# ********************************************************************** #
#                                Odatix                                  #
# ********************************************************************** #

import curses
import os
import signal
import sys

from odatix.lib.parallel_job_handler.ansi_to_curses import AnsiToCursesConverter
from odatix.lib.parallel_job_handler.utils import get_elapsed_time_str
from odatix.lib.utils import open_path_in_explorer
import odatix.lib.printc as printc


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


def progress_bar(handler, window, id, progress, elapsed_time, title, title_size, width, status="", selected=False):
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

    real_id = handler.job_index_start + id

    try:
        if real_id == handler.selected_job_index and handler.theme.get('selected_reverse') and handler.job_count > 1:
            window.attron(curses.color_pair(NORMAL) | curses.A_REVERSE)
            attr = curses.A_REVERSE | curses.A_BOLD
            offset = REVERSE
        else:
            attr = 0
            offset = 0

        attr = attr | curses.A_DIM if handler.showing_help else attr

        ballot = handler.theme.get('ballot_check') if selected else handler.theme.get('ballot_empty')
        window.addstr(id, 0, f"{ballot}")
        pos = len(ballot)

        if real_id == handler.selected_job_index and handler.theme.get('selected_bold') and handler.job_count > 1:
            window.attron(curses.color_pair(NORMAL) | curses.A_BOLD)
            attr = attr | curses.A_BOLD
        window.addstr(id, pos, f"{title}")
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
        window.addstr(id, pos, handler.theme.get('progress_full') * bar_length, attr | color)

        if handler.theme.get('dim_empty_bar'):
            dim = curses.color_pair(GREY + offset)
        else:
            dim = 0
        window.addstr(id, pos + bar_length, handler.theme.get('progress_empty') * (bar_width - bar_length), attr | dim)
        pos = pos + bar_width

        border_right = handler.theme.get('border_right')
        window.addstr(id, pos, border_right + " ", attr)
        pos = pos + len(border_right)

        percentage = f"{progress:3.0f}%"
        window.addstr(id, pos, percentage + spacer, attr)
        pos = pos + len(percentage) + len(spacer)

        if display_time:
            window.addstr(id, pos, elapsed_time + spacer, attr | curses.color_pair(GREY + offset))
            pos = pos + len(elapsed_time) + len(spacer)

        if status == "failed" or status == "killed" or status == "canceled":
            window.addstr(id, pos, status, curses.color_pair(RED + offset) | attr)
        elif status == "running":
            window.addstr(id, pos, status, curses.color_pair(YELLOW + offset) | attr)
        elif status == "success":
            window.addstr(id, pos, status, curses.color_pair(GREEN + offset) | attr)
        elif status == "queued" or status == "paused":
            window.addstr(id, pos, status, curses.color_pair(BLUE + offset) | attr)
        elif status == "starting":
            window.addstr(id, pos, status, curses.color_pair(CYAN + offset) | attr)
        else:
            window.addstr(id, pos, status, curses.color_pair(NORMAL + offset) | attr)
        pos = pos + len(status)

        remainder = width - pos
        if remainder > 0:
            window.addstr(id, pos, " " * remainder, attr)
    except curses.error:
        pass

    window.attroff(curses.A_REVERSE)
    window.attroff(curses.A_BOLD)


def update_header(handler, header_win, active_jobs_count, retired_jobs_count, total_jobs_count, width):
    try:
        header_win.hline(0, 0, " ", width, curses.color_pair(NORMAL) | curses.A_REVERSE)
        header_win.addstr(0, 1, "v" + str(handler.version), curses.color_pair(NORMAL) | curses.A_REVERSE)
    except curses.error:
        pass
    if total_jobs_count == 1:
        if retired_jobs_count == total_jobs_count:
            text = "{}/{} job done!".format(retired_jobs_count, total_jobs_count)
        else:
            text = "{}/{} job done - {} running".format(retired_jobs_count, total_jobs_count, active_jobs_count)
    else:
        if retired_jobs_count == total_jobs_count:
            text = "{}/{} jobs done!".format(retired_jobs_count, total_jobs_count)
        else:
            text = "{}/{} jobs done - {} running".format(retired_jobs_count, total_jobs_count, active_jobs_count)
    try:
        header_win.addstr(0, width - len(text) - 1, text, curses.color_pair(NORMAL) | curses.A_REVERSE)
    except curses.error:
        pass

    try:
        header_win.addstr(
            0, (width - len(" Odatix ")) // 2, " Odatix ", curses.color_pair(NORMAL) | curses.A_REVERSE | curses.A_BOLD
        )
    except curses.error:
        pass

    header_win.refresh()


def update_progress_window(handler, progress_win):
    _, width = progress_win.getmaxyx()
    if handler.showing_help:
        progress_win.attron(curses.A_DIM)

    progress_win.erase()

    for id, job in enumerate(handler.job_list[handler.job_index_start:handler.job_index_end]):
        selected = (handler.selected_job_index == handler.job_index_start + id)
        elapsed_time = get_elapsed_time_str(job.start_time, job.stop_time)
        try:
            progress_bar(
                handler=handler,
                id=id,
                window=progress_win,
                progress=job.progress,
                elapsed_time=elapsed_time,
                title=job.display_name,
                title_size=handler.max_title_length,
                width=width,
                status=job.status,
                selected=selected,
            )
        except curses.error:
            pass
    progress_win.refresh()
    progress_win.attroff(curses.A_DIM)


def update_separator(handler, separator_win, val, ref, width):
    dim = handler.showing_help and curses.A_DIM
    separator_win.erase()
    if val == ref:
        separator_text = handler.theme.get("bar") * (width - 1)
    else:
        message = f"{val - ref} more"
        padding = 4
        separator_text = handler.theme.get("bar") * padding + message + handler.theme.get("bar") * (width - len(message) - padding - 1)
    try:
        separator_win.addstr(0, 0, separator_text, dim)
    except curses.error:
        pass
    separator_win.refresh()


def update_help(bottom_bar):
    bottom_bar.erase()

    help_text = [
        ("q", "Quit"),
        ("h", "Help Menu"),
        ("c", "Cursor Mode"),
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


def show_exit_confirmation(bottom_bar):
    try:
        bottom_bar.erase()
        bottom_bar.addstr(" Kill all jobs and exit: Yes (", curses.color_pair(NORMAL) | curses.A_REVERSE)
        bottom_bar.addstr("y", curses.color_pair(NORMAL) | curses.A_REVERSE | curses.A_BOLD)
        bottom_bar.addstr(") / No (", curses.color_pair(NORMAL) | curses.A_REVERSE)
        bottom_bar.addstr("n", curses.color_pair(NORMAL) | curses.A_REVERSE | curses.A_BOLD)
        bottom_bar.addstr(")? ", curses.color_pair(NORMAL) | curses.A_REVERSE)
        bottom_bar.refresh()
    except curses.error:
        pass

    key = bottom_bar.getch()
    curses.flushinp()
    if key == ord("y") or key == ord("Y"):
        return True, True
    elif key == ord("n") or key == ord("N"):
        return True, False
    else:
        return False, False


def update_exit(bottom_bar):
    try:
        bottom_bar.erase()
        bottom_bar.addstr(" Exiting... ", curses.color_pair(NORMAL) | curses.A_REVERSE)
        bottom_bar.refresh()
    except curses.error:
        pass


def update_logs(handler, logs_win, selected_job, logs_height, width):
    history = selected_job.log_history
    log_length = len(history)

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
            handler.converter.add_ansi_str(logs_win, line, width=width, dim=handler.showing_help)
        except curses.error:
            pass

    logs_win.refresh()
    handler.previous_log_size = log_length


def update_help_popup(popup_win, popup_width, popup_height):
    help_text = [
        ("q"          , "Quit"),
        ("PageUp    n", "Select next job"),
        ("PageDown  p", "Select previous job"),
        ("Up        u", "Scroll log"),
        ("Down      d", "Scroll log"),
        ("Home/End"   , "Scroll to top/bottom"),
        ("+/-"        , "Change progress window zize"),
        ("Space"      , "Pause selected job"),
        ("k"          , "Kill selected job"),
        ("s"          , "Start/resume selected job"),
        ("o"          , "Open current job work path"),
        ("t"          , "Switch theme"),
        ("h         ?", "Show help"),
    ]

    if popup_height <= 7:
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
                for i, (key, desc) in enumerate(help_text, start=4):
                    if i < popup_height - 2:
                        popup_win.addstr(i, 3, f"{key}", curses.color_pair(CYAN))
                        popup_win.addstr(i, 17, f"{desc}")
            except curses.error:
                pass
    try:
        text = "Press 'q' or 'h' to close"
        popup_win.addstr(max(popup_height - 2, 1), (popup_width - len(text)) // 2, text, curses.A_DIM)
    except curses.error:
        pass
    popup_win.refresh()


def click_on_job(handler, progress_win, y, x):
    if progress_win.enclose(y, x):
        relative_y = y - progress_win.getbegyx()[0]
        job_index = handler.job_index_start + relative_y
        if 0 <= job_index < len(handler.job_list):
            return job_index
    return -1


def curses_main(handler, stdscr):
    curses.curs_set(0)  # Hide cursor

    # Enable mouse actions (disable selection)
    from odatix.lib.curses_helper import disable_selection, enable_selection
    disable_selection()

    curses.start_color()
    curses.use_default_colors()

    # Define color pairs
    curses.init_pair(NORMAL, -1, -1)
    curses.init_pair(RED, curses.COLOR_RED, -1)
    curses.init_pair(YELLOW, curses.COLOR_YELLOW, -1)
    curses.init_pair(GREEN, curses.COLOR_GREEN, -1)
    curses.init_pair(BLUE, curses.COLOR_BLUE, -1)
    curses.init_pair(CYAN, curses.COLOR_CYAN, -1)
    curses.init_pair(BLACK, curses.COLOR_BLACK, -1)
    curses.init_pair(WHITE, curses.COLOR_WHITE, -1)
    curses.init_pair(GREY, curses.COLOR_BLACK + AnsiToCursesConverter.LIGHT_OFFSET, -1)

    curses.init_pair(REVERSE, curses.COLOR_BLACK, curses.COLOR_WHITE + AnsiToCursesConverter.LIGHT_OFFSET)
    curses.init_pair(REVERSE_RED, -1, curses.COLOR_RED + AnsiToCursesConverter.LIGHT_OFFSET)
    curses.init_pair(REVERSE_YELLOW, -1, curses.COLOR_YELLOW + AnsiToCursesConverter.LIGHT_OFFSET)
    curses.init_pair(REVERSE_GREEN, -1, curses.COLOR_GREEN + AnsiToCursesConverter.LIGHT_OFFSET)
    curses.init_pair(REVERSE_BLUE, -1, curses.COLOR_BLUE + AnsiToCursesConverter.LIGHT_OFFSET)
    curses.init_pair(REVERSE_CYAN, -1, curses.COLOR_CYAN + AnsiToCursesConverter.LIGHT_OFFSET)
    curses.init_pair(REVERSE_BLACK, -1, curses.COLOR_BLACK + AnsiToCursesConverter.LIGHT_OFFSET)
    curses.init_pair(REVERSE_WHITE, -1, curses.COLOR_WHITE + AnsiToCursesConverter.LIGHT_OFFSET)
    curses.init_pair(REVERSE_GREY, -1, curses.COLOR_BLACK)

    height, width = stdscr.getmaxyx()
    old_width = width
    old_height = height

    # Adjust window positions
    progress_height = handler.job_index_end - handler.job_index_start
    header_height = 1
    separator_height = 1
    help_height = 1
    logs_height = height - progress_height - 2*separator_height - help_height - header_height
    popup_width = min(50, width - 4)
    popup_height = min(19, height - 4)
    popup_height = max(popup_height, 3)
    start_x = (width - popup_width) // 2
    start_y = (height - popup_height) // 2

    try:
        header_win = curses.newwin(header_height, width, 0, 0)
        separator_top_win = curses.newwin(separator_height, width, header_height, 0)
        progress_win = curses.newwin(progress_height, width, header_height + separator_height, 0)
        separator_middle_win = curses.newwin(separator_height, width, header_height + separator_height + progress_height, 0)
        logs_win = curses.newwin(logs_height, width, header_height + separator_height + progress_height + separator_height, 0)
        bottom_bar = curses.newwin(help_height, width, height - help_height, 0)
        popup_win = curses.newwin(popup_height, popup_width, start_y, start_x)
        popup_win.box()
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

    for job in handler.job_list:
        if len(handler.running_job_list) < handler.nb_jobs:
            handler.start_job(job)
        else:
            handler.queue_job(job)

    total_jobs_count = len(handler.job_list)

    stdscr.nodelay(True)

    resize = False
    resize_hold = False

    handler.showing_help = False

    while True:
        if handler._request_curses_exit:
            update_exit(bottom_bar)
            handler.terminate_all_jobs()
            return False

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

        height, width = stdscr.getmaxyx()
        if height != old_height or width != old_width or resize:
            popup_width = min(50, width - 4)
            popup_height = min(20, height - 4)
            popup_height = max(popup_height, 3)
            start_x = (width - popup_width) // 2
            start_y = (height - popup_height) // 2
            try:
                progress_height = handler.job_index_end - handler.job_index_start
                logs_height = height - progress_height - 2*separator_height - help_height - header_height

                separator_top_win = curses.newwin(separator_height, width, header_height, 0)
                progress_win = curses.newwin(progress_height, width, header_height + separator_height, 0)
                separator_middle_win = curses.newwin(separator_height, width, header_height + separator_height + progress_height, 0)
                logs_win = curses.newwin(logs_height, width, header_height + separator_height + progress_height + separator_height, 0)
                bottom_bar = curses.newwin(help_height, width, height - help_height, 0)
                popup_win = curses.newwin(popup_height, popup_width, start_y, start_x)
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

        active_jobs_count = len(handler.running_job_list)
        queued_jobs_count = handler.job_queue.qsize()
        if active_jobs_count == 0 and queued_jobs_count == 0:
            finished = True

        retired_jobs_count = len(handler.retired_job_list)

        update_header(handler, header_win, active_jobs_count, retired_jobs_count, total_jobs_count, width)
        update_separator(handler, separator_top_win, handler.job_index_start, 0, width)

        with handler._lock:
            handler._update_jobs_state(
                selected_job=selected_job,
                on_selected_retired=lambda: update_logs(handler, logs_win, selected_job, logs_height, width),
            )

        update_progress_window(handler, progress_win)
        update_separator(handler, separator_middle_win, handler.job_count, handler.job_index_end, width)

        if handler.showing_help:
            update_help_popup(popup_win, popup_width, popup_height)

        with handler._lock:
            handler.read_process_output()

        if selected_job.autoscroll and selected_job.log_changed:
            selected_job.log_position = max(0, len(selected_job.log_history) - logs_height)
            update_logs(handler, logs_win, selected_job, logs_height, width)

        if width != old_width:
            update_logs(handler, logs_win, selected_job, logs_height, width)
        old_width = width

        key = stdscr.getch()
        curses.flushinp()

        def update_selected_job():
            job = handler.job_list[handler.selected_job_index]
            job.log_position = max(0, len(job.log_history) - logs_height)
            job.autoscroll = True
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

        def scroll_up_progress():
            handler.job_index_start -= 1
            handler.job_index_end -= 1

        def scroll_down_progress():
            handler.job_index_start += 1
            handler.job_index_end += 1

        if not handler.showing_help:
            if key == curses.KEY_MOUSE:
                _, x, y, _, button = curses.getmouse()

                if resize_hold:
                    y = min(y, height - 2)
                    relative_y = y - (header_height + separator_height)
                    new_job_index_end = handler.job_index_start + relative_y

                    if new_job_index_end <= handler.job_index_start:
                        handler.job_index_end = handler.job_index_start + 1
                        resize = True
                    elif new_job_index_end >= handler.job_count:
                        remainder = new_job_index_end - handler.job_count
                        handler.job_index_end = handler.job_count
                        handler.job_index_start = max(0, handler.job_index_start - remainder)
                        resize = True
                    else:
                        handler.job_index_end = new_job_index_end
                        resize = True

                if button & curses.BUTTON1_CLICKED or button & curses.BUTTON1_DOUBLE_CLICKED:
                    job_index = click_on_job(handler, progress_win, y, x)
                    if job_index >= 0:
                        handler.selected_job_index = job_index
                        selected_job = update_selected_job()
                        update_logs(handler, logs_win, selected_job, logs_height, width)

                        if button & curses.BUTTON1_DOUBLE_CLICKED:
                            try:
                                open_path_in_explorer(handler.job_list[job_index].tmp_dir)
                            except NotImplementedError:
                                pass
                elif button & curses.BUTTON1_PRESSED:
                    if separator_middle_win.enclose(y, x):
                        resize_hold = True
                elif button & curses.BUTTON1_RELEASED:
                    resize_hold = False
                elif button & curses.BUTTON4_PRESSED:
                    if progress_win.enclose(y, x):
                        if handler.job_index_start > 0:
                            scroll_up_progress()
                    elif logs_win.enclose(y, x):
                        scroll_up_logs(selected_job)
                elif button & curses.BUTTON5_PRESSED:
                    if progress_win.enclose(y, x):
                        if handler.job_index_end <= len(handler.job_list) - 1:
                            scroll_down_progress()
                    elif logs_win.enclose(y, x):
                        scroll_down_logs(selected_job)

            elif key == curses.KEY_PPAGE or key == ord("p") or key == ord("P"):
                if handler.selected_job_index > 0:
                    handler.selected_job_index -= 1
                if handler.selected_job_index < handler.job_index_start:
                    scroll_up_progress()
                selected_job = update_selected_job()
                update_logs(handler, logs_win, selected_job, logs_height, width)

            elif key == curses.KEY_NPAGE or key == ord("n") or key == ord("N"):
                if handler.selected_job_index < len(handler.job_list) - 1:
                    handler.selected_job_index += 1
                if handler.selected_job_index >= handler.job_index_end:
                    scroll_down_progress()
                selected_job = update_selected_job()
                update_logs(handler, logs_win, selected_job, logs_height, width)

            elif key == curses.KEY_UP or key == ord("u") or key == ord("U"):
                scroll_up_logs(selected_job)

            elif key == curses.KEY_DOWN or key == ord("d") or key == ord("D"):
                scroll_down_logs(selected_job)

            elif key == curses.KEY_HOME:
                selected_job.log_position = 0
                selected_job.autoscroll = False
                update_logs(handler, logs_win, selected_job, logs_height, width)

            elif key == curses.KEY_END:
                selected_job.log_position = max(0, len(selected_job.log_history) - logs_height)
                selected_job.autoscroll = True
                update_logs(handler, logs_win, selected_job, logs_height, width)

            elif key == ord("+") or key == ord("="):
                if logs_height > 0:
                    if handler.job_index_end < handler.job_count:
                        handler.job_index_end += 1
                        resize = True
                    elif handler.job_index_start > 0:
                        handler.job_index_start -= 1
                        resize = True

            elif key == ord("-") or key == ord("_"):
                if handler.selected_job_index < handler.job_index_end - 1:
                    handler.job_index_end -= 1
                    resize = True
                elif handler.job_index_start < handler.job_index_end - 1:
                    handler.job_index_start += 1
                    resize = True

            elif key == ord("c") or key == ord("C"):
                if handler.selection_enabled:
                    disable_selection()
                    handler.selection_enabled = False
                else:
                    enable_selection()
                    handler.selection_enabled = True

            elif key == ord('k') or key == ord('K'):
                handler.kill_or_cancel_job(handler.selected_job_index)

            elif key == ord(' '):
                if selected_job.status == "running":
                    selected_job.pause()

            elif key == ord('s') or key == ord('S'):
                handler.start_or_resume_job(handler.selected_job_index)

            elif key == ord('o') or key == ord('O'):
                handler.open_job_path(handler.selected_job_index)

            elif key == ord("t") or key == ord("T"):
                handler.next_theme()

            elif key in [ord("h"), ord("H"), ord("?")]:
                handler.showing_help = True
                update_logs(handler, logs_win, selected_job, logs_height, width)

            else:
                if handler.auto_exit and finished:
                    return True
                if key == ord("q") or key == ord("Q"):
                    if finished:
                        return True
                    ask_exit = True

        else:
            if key == curses.KEY_MOUSE:
                _, mouse_x, mouse_y, _, button = curses.getmouse()
                close_x = start_x + popup_width - 5
                close_y = start_y + 1

                if button & curses.BUTTON1_CLICKED and mouse_y == close_y and close_x <= mouse_x <= close_x + 2:
                    handler.showing_help = False
                    logs_win.erase()
                    update_logs(handler, logs_win, selected_job, logs_height, width)

            elif key in [ord('h'), ord('H'), ord('?'), ord('q'), ord('Q')]:
                handler.showing_help = False
                logs_win.erase()
                update_logs(handler, logs_win, selected_job, logs_height, width)

        if ask_exit:
            user_answered, user_confirmed = show_exit_confirmation(bottom_bar)
            if user_answered:
                if user_confirmed:
                    update_exit(bottom_bar)
                    handler.terminate_all_jobs()
                    return False
                ask_exit = False
        else:
            update_help(bottom_bar)


def run(handler):
    curses.wrapper(lambda stdscr: curses_main(handler, stdscr))
