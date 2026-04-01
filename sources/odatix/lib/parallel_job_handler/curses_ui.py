# ********************************************************************** #
#                                Odatix                                  #
# ********************************************************************** #

import curses
import os
import signal
import sys

from odatix.lib.parallel_job_handler.ansi_to_curses import AnsiToCursesConverter
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
            handler.update_exit(bottom_bar)
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
                handler.update_logs(logs_win, selected_job, logs_height, width)
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

        handler.update_header(header_win, active_jobs_count, retired_jobs_count, total_jobs_count, width)
        handler.update_separator(separator_top_win, handler.job_index_start, 0, width)

        with handler._lock:
            handler._update_jobs_state(
                selected_job=selected_job,
                on_selected_retired=lambda: handler.update_logs(logs_win, selected_job, logs_height, width),
            )

        handler.update_progress_window(progress_win, selected_job)
        handler.update_separator(separator_middle_win, handler.job_count, handler.job_index_end, width)

        if handler.showing_help:
            handler.update_help_popup(popup_win, width, height, popup_width, popup_height)

        with handler._lock:
            handler.read_process_output()

        if selected_job.autoscroll and selected_job.log_changed:
            selected_job.log_position = max(0, len(selected_job.log_history) - logs_height)
            handler.update_logs(logs_win, selected_job, logs_height, width)

        if width != old_width:
            handler.update_logs(logs_win, selected_job, logs_height, width)
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
                handler.update_logs(logs_win, selected, logs_height, width)

        def scroll_down_logs(selected):
            if selected.log_position + logs_height < len(selected.log_history):
                selected.log_position = min(len(selected.log_history) - logs_height, selected.log_position + 3)
                selected.autoscroll = False
                handler.update_logs(logs_win, selected, logs_height, width)

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
                    job_index = handler.click_on_job(progress_win, y, x)
                    if job_index >= 0:
                        handler.selected_job_index = job_index
                        selected_job = update_selected_job()
                        handler.update_logs(logs_win, selected_job, logs_height, width)

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
                handler.update_logs(logs_win, selected_job, logs_height, width)

            elif key == curses.KEY_NPAGE or key == ord("n") or key == ord("N"):
                if handler.selected_job_index < len(handler.job_list) - 1:
                    handler.selected_job_index += 1
                if handler.selected_job_index >= handler.job_index_end:
                    scroll_down_progress()
                selected_job = update_selected_job()
                handler.update_logs(logs_win, selected_job, logs_height, width)

            elif key == curses.KEY_UP or key == ord("u") or key == ord("U"):
                scroll_up_logs(selected_job)

            elif key == curses.KEY_DOWN or key == ord("d") or key == ord("D"):
                scroll_down_logs(selected_job)

            elif key == curses.KEY_HOME:
                selected_job.log_position = 0
                selected_job.autoscroll = False
                handler.update_logs(logs_win, selected_job, logs_height, width)

            elif key == curses.KEY_END:
                selected_job.log_position = max(0, len(selected_job.log_history) - logs_height)
                selected_job.autoscroll = True
                handler.update_logs(logs_win, selected_job, logs_height, width)

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
                if selected_job.status == "running":
                    try:
                        if sys.platform == "win32":
                            selected_job.process.send_signal(signal.CTRL_BREAK_EVENT)
                        else:
                            os.killpg(os.getpgid(selected_job.process.pid), signal.SIGTERM)
                        selected_job.status = "killed"
                        handler.retire_job(selected_job, selected_job.progress)
                        selected_job.log_history.append(printc.colors.RED + "Job killed by user" + printc.colors.ENDC)
                    except ProcessLookupError:
                        selected_job.log_history.append(printc.colors.RED + "Failed to kill the job" + printc.colors.ENDC)
                elif selected_job.status == "queued":
                    try:
                        handler.job_queue.queue.remove(selected_job)
                        selected_job.status = "canceled"
                        selected_job.log_history.append(printc.colors.RED + "Job canceled by user" + printc.colors.ENDC)
                    except ValueError:
                        pass

            elif key == ord(' '):
                if selected_job.status == "running":
                    selected_job.pause()

            elif key == ord('s') or key == ord('S'):
                if selected_job.status == "queued":
                    handler.job_queue.queue.remove(selected_job)
                if selected_job.status in ("queued", "canceled"):
                    handler.start_job(selected_job)
                if selected_job.status == "paused":
                    selected_job.resume()

            elif key == ord('o') or key == ord('O'):
                try:
                    open_path_in_explorer(selected_job.tmp_dir)
                except NotImplementedError:
                    pass

            elif key == ord("t") or key == ord("T"):
                handler.theme.next_theme()

            elif key in [ord("h"), ord("H"), ord("?")]:
                handler.showing_help = True
                handler.update_logs(logs_win, selected_job, logs_height, width)

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
                    handler.update_logs(logs_win, selected_job, logs_height, width)

            elif key in [ord('h'), ord('H'), ord('?'), ord('q'), ord('Q')]:
                handler.showing_help = False
                logs_win.erase()
                handler.update_logs(logs_win, selected_job, logs_height, width)

        if ask_exit:
            user_answered, user_confirmed = handler.show_exit_confirmation(bottom_bar)
            if user_answered:
                if user_confirmed:
                    handler.update_exit(bottom_bar)
                    handler.terminate_all_jobs()
                    return False
                ask_exit = False
        else:
            handler.update_help(bottom_bar)


def run(handler):
    curses.wrapper(lambda stdscr: curses_main(handler, stdscr))
