# ********************************************************************** #
#                               Asterism                                 #
# ********************************************************************** #
#
# Copyright (C) 2022 Jonathan Saussereau
#
# This file is part of Asterism.
# Asterism is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Asterism is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Asterism. If not, see <https://www.gnu.org/licenses/>.
#

import os
import sys
import queue
import fcntl
import curses
import select
import subprocess

# Add local libs to path
current_dir = os.path.dirname(os.path.abspath(__file__))
lib_path = os.path.join(current_dir, "lib")
sys.path.append(lib_path)

from run_parallel import Running_arch
import ansi_to_curses

STD_BUF = "stdbuf -oL "

def set_nonblocking(fd):
    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

def progress_bar(window, id, progress, bar_width, title, title_size, status="", selected=False):
    title = title.ljust(title_size)
    bar_width = bar_width - 2 - title_size
    bar_length = int(bar_width * progress / 100.0)
    percentage = f'{progress:.0f}%'
    comment = f"({status})"

    try:
        button = "[*]" if selected else "[ ]"
        window.addstr(id, 0, f'{button} {title} [')
        window.addstr(id, len(button) + len(title) + 3, '#' * bar_length, curses.color_pair(1))
        window.addstr(id, len(button) + len(title) + 3 + bar_length, ' ' * (bar_width - bar_length), curses.color_pair(1))
        window.addstr(id, len(button) + len(title) + 3 + bar_width + 1, f'] {percentage}')
        
        comment_position = len(button) + len(title) + 3 + bar_width + 9
        if status == "failed":
            window.addstr(id, comment_position, comment, curses.color_pair(2))
        elif status == "running":
            window.addstr(id, comment_position, comment, curses.color_pair(3))
        elif status == "done":
            window.addstr(id, comment_position, comment, curses.color_pair(4))
        elif status == "queued":
            window.addstr(id, comment_position, comment, curses.color_pair(5))
        else:
            window.addstr(id, comment_position, comment, curses.color_pair(1))
    except curses.error as e:
        print(f"curses.error: {e}")

def update_help(help_win):
    help_win.erase()
    
    # Define the text with attributes
    help_text = [
        ("q", "Quit"),
        ("PageUp/PageDown", "Switch Process"),
        ("Up/Down", "Scroll Log"),
        ("Home/End", "Scroll to Top/Bottom")
    ]

    help_win.attron(curses.color_pair(10))
    help_win.addstr(" ")
    
    for i, (key, description) in enumerate(help_text):
        if i > 0:
            help_win.addstr(" | ")
        help_win.attron(curses.color_pair(10) | curses.A_BOLD)
        help_win.addstr(key)
        help_win.attroff(curses.A_BOLD)  # Remove attributes
        help_win.addstr(": ")
        help_win.addstr(description)
    
    help_win.addstr(" ")
    help_win.attroff(curses.color_pair(10) | curses.A_BOLD) 
    help_win.refresh()

def curses_main(stdscr, job_list, nb_jobs):
    curses.curs_set(0)  # Hide cursor

    curses.start_color()
    curses.use_default_colors()

    # Define color pairs
    curses.init_pair(1, -1, -1) 
    curses.init_pair(2, curses.COLOR_RED, -1)
    curses.init_pair(3, curses.COLOR_YELLOW, -1)
    curses.init_pair(4, curses.COLOR_GREEN, -1)
    curses.init_pair(5, curses.COLOR_BLUE, -1)
    curses.init_pair(10, curses.COLOR_BLACK, curses.COLOR_WHITE)

    height, width = stdscr.getmaxyx()

    header_height = 2

    # Adjust window positions
    progress_height = len(job_list)
    separator_height = 1
    help_height = 2  # Height for the help window
    logs_height = height - progress_height - separator_height - help_height - header_height

    header_win = curses.newwin(header_height, width, 0, 0)
    progress_win = curses.newwin(progress_height, width, header_height, 0)
    separator_win = curses.newwin(separator_height, width, header_height + progress_height, 0)
    logs_win = curses.newwin(logs_height, width, header_height + progress_height + separator_height, 0)
    help_win = curses.newwin(help_height, width, height - help_height, 0)

    log_histories = [[] for _ in job_list]
    log_positions = [0] * len(job_list)
    autoscroll = [True] * len(job_list)

    running_job_list = []
    retired_job_list = []

    def run_job(job):
        process = subprocess.Popen(
            STD_BUF + job.command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
            text=True
        )
        set_nonblocking(process.stdout)
        set_nonblocking(process.stderr)

        job.process = process
        job.status = "running"
        running_job_list.append(job)

    def queue_job(job):
        job.status = "queued"
        job_queue.put(job)

    def retire_job(job, progress=100):
        running_job_list.remove(job)
        job.progress = progress
        retired_job_list.append(job)

    job_queue = queue.Queue()

    for job in job_list:
        if len(running_job_list) < nb_jobs:
            run_job(job)
        else:
            queue_job(job)

    selected_job_index = 0

    def update_logs():
        logs_win.erase()
        history = log_histories[selected_job_index]
        for line in history[log_positions[selected_job_index]:log_positions[selected_job_index] + logs_height]:
            try:
                line = ansi_to_curses.add_ansi_str(logs_win, line)
            except curses.error:
                pass
        logs_win.refresh()

    max_title_length = max(len(job.display_name) for job in job_list)

    while True:
        # Add a separator   
        header_win.erase()
        header_win.addstr(0, (width - len(" Asterism ")) // 2, " Asterism ", curses.color_pair(10) | curses.A_BOLD)
        header_win.hline(1, 0, '-', width)
        header_win.refresh()

        progress_win.erase()
        for id, job in enumerate(job_list):
            height, width = progress_win.getmaxyx()

            if job in retired_job_list:
                progress = job.progress
            elif not job in running_job_list or job.process is None:
                progress = 0
            else:
                progress = job.get_progress()
                if job.process.poll() is not None:
                    if job.process.returncode == 0:
                        job.status = "done"
                    else:
                        job.status = "failed"
                        if progress is None:
                            progress = 0
                    
                    retire_job(job, progress)
                    if not job_queue.empty():
                        run_job(job_queue.get())

            progress_bar(
                id=id,
                window=progress_win, 
                progress=progress, 
                bar_width=(width - 25),
                title=job.display_name, 
                title_size=max_title_length, 
                status=job.status,
                selected=(id == selected_job_index)
            )  
        progress_win.refresh()

        # Add a separator
        separator_win.erase()
        separator_win.hline(0, 0, '-', width)
        separator_win.refresh()

        process = job_list[selected_job_index].process

        try:
            read_ready, _, _ = select.select([process.stdout, process.stderr], [], [], 0.1)

            for pipe in read_ready:
                while True:
                    line = pipe.readline()
                    if line:
                        log_histories[selected_job_index].append(line)
                        # Automatically scroll if at the bottom
                        if autoscroll[selected_job_index]:
                            log_positions[selected_job_index] = max(0, len(log_histories[selected_job_index]) - logs_height)
                            update_logs()
                    else:
                        break
        except:
            pass

        stdscr.nodelay(True)
        key = stdscr.getch()
        if key == ord('q'):
            break
        elif key == curses.KEY_PPAGE:  # Page Up
            if selected_job_index > 0:
                selected_job_index -= 1
                log_positions[selected_job_index] = max(0, len(log_histories[selected_job_index]) - logs_height)
                autoscroll[selected_job_index] = True
                update_logs()
        elif key == curses.KEY_NPAGE:  # Page Down
            if selected_job_index < len(job_list) - 1:
                selected_job_index += 1
                log_positions[selected_job_index] = max(0, len(log_histories[selected_job_index]) - logs_height)
                autoscroll[selected_job_index] = True
                update_logs()
        elif key == curses.KEY_UP:  # Scroll Up
            if log_positions[selected_job_index] > 0:
                log_positions[selected_job_index] = max(0, log_positions[selected_job_index] - 1)
                autoscroll[selected_job_index] = False
                update_logs()
        elif key == curses.KEY_DOWN:  # Scroll Down
            if log_positions[selected_job_index] + logs_height < len(log_histories[selected_job_index]):
                log_positions[selected_job_index] = min(len(log_histories[selected_job_index]) - logs_height, log_positions[selected_job_index] + 1)
                autoscroll[selected_job_index] = False
                update_logs()
        elif key == curses.KEY_HOME:  # Home
            log_positions[selected_job_index] = 0
            autoscroll[selected_job_index] = False
            update_logs()
        elif key == curses.KEY_END:  # End
            log_positions[selected_job_index] = max(0, len(log_histories[selected_job_index]) - logs_height)
            autoscroll[selected_job_index] = True
            update_logs()

        update_help(help_win)

    try:
        log_histories[selected_job_index].append("\nProcess completed. Press any key to exit.")
    except curses.error:
        pass
    update_logs()
    logs_win.refresh()
    logs_win.getkey()

def show_progress(job_list, nb_jobs):
    curses.wrapper(curses_main, job_list, nb_jobs)
