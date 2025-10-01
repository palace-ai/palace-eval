import itertools
import re
import sys
import threading
import time
from builtins import print as builtin_print
from contextlib import contextmanager
from typing import List, Optional

import emoji
from wcwidth import wcswidth

try:
    from IPython import get_ipython
    from IPython.display import clear_output, display

    IN_NOTEBOOK = get_ipython() is not None
except ImportError:
    IN_NOTEBOOK = False


def print(
    *args: List[str],
    sep: str = " ",
    end: str = "\n",
    box: bool = False,
    box_title: Optional[str] = None,
    wrap_width: int = 100,
    builtin: bool = False,
):
    if builtin:
        builtin_print(*args, sep=sep, end=end)
        return

    # Mapping of style and color names to ANSI SGR parameters
    color_map = {
        "black": "30",
        "red": "31",
        "green": "32",
        "yellow": "33",
        "blue": "34",
        "magenta": "35",
        "cyan": "36",
        "white": "37",
        "bright_black": "90",
        "bright_red": "91",
        "bright_green": "92",
        "bright_yellow": "93",
        "bright_blue": "94",
        "bright_magenta": "95",
        "bright_cyan": "96",
        "bright_white": "97",
        "on_black": "40",
        "on_red": "41",
        "on_green": "42",
        "on_yellow": "43",
        "on_blue": "44",
        "on_magenta": "45",
        "on_cyan": "46",
        "on_white": "47",
        "on_bright_black": "100",
        "on_bright_red": "101",
        "on_bright_green": "102",
        "on_bright_yellow": "103",
        "on_bright_blue": "104",
        "on_bright_magenta": "105",
        "on_bright_cyan": "106",
        "on_bright_white": "107",
        "bold": "1",
        "dim": "2",
        "italic": "3",
        "underline": "4",
        "blink": "5",
        "reverse": "7",
        "strike": "9",
    }

    # Join all args into a single string and replace shortcodes with actual emojis
    raw = sep.join(str(arg) for arg in args)
    text = emoji.emojize(raw, language="alias")

    i, n = 0, len(text)
    output = ["\033[0m"]  # Reset at start so no sticky styles

    while i < n:
        if text[i] == "[" and (i == 0 or text[i - 1] != "\\"):
            j = text.find("]", i)
            if j == -1:
                output.append(text[i])
                i += 1
                continue

            tag = text[i + 1 : j].lower().strip()
            parts = tag.split()

            if tag == "/" or all(part in color_map for part in parts):
                i = j + 1
                if tag == "/":  # closing tag: reset all styles
                    output.append("\033[0m")
                else:  # parse color/style tag
                    bg_nums = [color_map[p] for p in parts if p.startswith("on_")]
                    fg_nums = [color_map[p] for p in parts if not p.startswith("on_")]
                    all_nums = bg_nums + fg_nums
                    if all_nums:
                        output.append(f"\033[{';'.join(all_nums)}m")
                continue
            else:
                output.append(text[i : j + 1])
                i = j + 1
                continue
        else:
            output.append(text[i])
            i += 1

    # Reset at end if any SGR codes emitted
    if any(s.startswith("\033[") for s in output):
        output.append("\033[0m")

    formatted_text = "".join(output)

    if box:

        def _real_len(s):
            return wcswidth(re.sub(r"\x1b\[[0-9;]*m", "", s))

        def _split_visible_chunks(string, chunk_len):
            tokens = re.findall(r"\033\[[0-9;]*m|.", string)
            chunks, chunk, width = [], "", 0
            for t in tokens:
                w = 0 if t.startswith("\033[") else wcswidth(t)
                if width + w > chunk_len:
                    chunks.append(chunk)
                    chunk, width = "", 0
                chunk += t
                width += w
            if chunk:
                chunks.append(chunk)
            return chunks

        # wrap lines according to wrap_width
        formatted_lines = formatted_text.splitlines()
        wrapped_lines = []
        for line in formatted_lines:
            chunks = _split_visible_chunks(line, wrap_width)
            wrapped_lines.extend(chunks if chunks else [""])

        max_length = max(_real_len(line) for line in wrapped_lines)

        box_title = (
            f" {emoji.emojize(box_title, language='alias')} " if box_title else ""
        )
        box_width = max(max_length, wcswidth(box_title) - 2)

        horizontal_line = "─" * (box_width + 4)
        top_border = (
            f"╭─\033[1m{box_title}\033[0m{horizontal_line[wcswidth(box_title) + 1 :]}╮"
        )
        bottom_border = f"╰{horizontal_line}╯"

        boxed_output = [top_border]
        boxed_output.append(f"│  {' ' * box_width}  │")

        for wrapped_line in wrapped_lines:
            padding = box_width - _real_len(wrapped_line)
            boxed_output.append(f"│  {wrapped_line}{' ' * padding}  │")
        boxed_output.append(f"│  {' ' * box_width}  │")
        boxed_output.append(bottom_border)

        formatted_text = "\n".join(boxed_output)

    # Use builtin print to avoid recursion
    builtin_print(formatted_text, end=end, flush=True)


@contextmanager
def loading_icon_v1():
    spinner = itertools.cycle(
        [
            "⢀⠀",
            "⡀⠀",
            "⠄⠀",
            "⢂⠀",
            "⡂⠀",
            "⠅⠀",
            "⢃⠀",
            "⡃⠀",
            "⠍⠀",
            "⢋⠀",
            "⡋⠀",
            "⠍⠁",
            "⢋⠁",
            "⡋⠁",
            "⠍⠉",
            "⠋⠉",
            "⠋⠉",
            "⠉⠙",
            "⠉⠙",
            "⠉⠩",
            "⠈⢙",
            "⠈⡙",
            "⢈⠩",
            "⡀⢙",
            "⠄⡙",
            "⢂⠩",
            "⡂⢘",
            "⠅⡘",
            "⢃⠨",
            "⡃⢐",
            "⠍⡐",
            "⢋⠠",
            "⡋⢀",
            "⠍⡁",
            "⢋⠁",
            "⡋⠁",
            "⠍⠉",
            "⠋⠉",
            "⠋⠉",
            "⠉⠙",
            "⠉⠙",
            "⠉⠩",
            "⠈⢙",
            "⠈⡙",
            "⠈⠩",
            "⠀⢙",
            "⠀⡙",
            "⠀⠩",
            "⠀⢘",
            "⠀⡘",
            "⠀⠨",
            "⠀⢐",
            "⠀⡐",
            "⠀⠠",
            "⠀⢀",
            "⠀⡀",
            "⠀⠀",
            "⠀⠀",
            "⠀⠀",
            "⠀⠀",
        ]
    )
    animation_interval = 0.075
    done = False
    start_time = time.time()

    def animate():
        if IN_NOTEBOOK:
            while not done:
                elapsed_time = time.time() - start_time
                builtin_print(
                    f"\r{next(spinner)}  {elapsed_time:.1f}s", end="", flush=True
                )
                time.sleep(animation_interval)
        else:
            sys.stdout.write("\033[s")
            while not done:
                elapsed_time = time.time() - start_time
                sys.stdout.write(f"\033[u{next(spinner)}  {elapsed_time:.1f}s")
                sys.stdout.flush()
                time.sleep(animation_interval)
            sys.stdout.write("\033[u \033[u")
            sys.stdout.flush()

    # Start the animation in a separate thread
    thread = threading.Thread(target=animate)
    thread.start()

    try:
        yield  # This is where the calling code will execute
    finally:
        # Signal the animation to stop
        done = True
        # Wait for the animation thread to finish
        thread.join()
        if IN_NOTEBOOK:
            builtin_print("\r", end="", flush=True)  # Clear the spinner in Jupyter
        else:
            sys.stdout.write("\r")
            sys.stdout.flush()


class LoadingIcon:
    def __init__(self, spinner, animation_interval):
        self.spinner = spinner
        self.animation_interval = animation_interval
        self.done = False
        self.start_time = time.time()
        self.description = ""
        self.lock = threading.Lock()
        self.last_length = 0

    def status(self, text):
        with self.lock:
            self.description = text

    def animate(self):
        if IN_NOTEBOOK:
            while not self.done:
                elapsed_time = time.time() - self.start_time
                with self.lock:
                    desc = self.description
                    output = f"\r{next(self.spinner)}  ({elapsed_time:.1f}s)  {desc}"
                    self.last_length = len(output) - 1
                builtin_print(output, end="", flush=True)
                time.sleep(self.animation_interval)
            builtin_print("\r" + " " * self.last_length + "\r", end="", flush=True)
        else:
            sys.stdout.write("\033[s")
            while not self.done:
                elapsed_time = time.time() - self.start_time
                with self.lock:
                    desc = self.description
                    output = (
                        f"\033[u{next(self.spinner)}  ({elapsed_time:.1f}s)  {desc}"
                    )
                    self.last_length = len(output) - 1
                sys.stdout.write(output)
                sys.stdout.flush()
                time.sleep(self.animation_interval)
            sys.stdout.write("\033[u" + " " * self.last_length + "\033[u")
            sys.stdout.flush()


@contextmanager
def loading():
    spinner = itertools.cycle(
        [
            "⢀⠀",
            "⡀⠀",
            "⠄⠀",
            "⢂⠀",
            "⡂⠀",
            "⠅⠀",
            "⢃⠀",
            "⡃⠀",
            "⠍⠀",
            "⢋⠀",
            "⡋⠀",
            "⠍⠁",
            "⢋⠁",
            "⡋⠁",
            "⠍⠉",
            "⠋⠉",
            "⠋⠉",
            "⠉⠙",
            "⠉⠙",
            "⠉⠩",
            "⠈⢙",
            "⠈⡙",
            "⢈⠩",
            "⡀⢙",
            "⠄⡙",
            "⢂⠩",
            "⡂⢘",
            "⠅⡘",
            "⢃⠨",
            "⡃⢐",
            "⠍⡐",
            "⢋⠠",
            "⡋⢀",
            "⠍⡁",
            "⢋⠁",
            "⡋⠁",
            "⠍⠉",
            "⠋⠉",
            "⠋⠉",
            "⠉⠙",
            "⠉⠙",
            "⠉⠩",
            "⠈⢙",
            "⠈⡙",
            "⠈⠩",
            "⠀⢙",
            "⠀⡙",
            "⠀⠩",
            "⠀⢘",
            "⠀⡘",
            "⠀⠨",
            "⠀⢐",
            "⠀⡐",
            "⠀⠠",
            "⠀⢀",
            "⠀⡀",
            "⠀⠀",
            "⠀⠀",
            "⠀⠀",
            "⠀⠀",
        ]
    )
    animation_interval = 0.075

    loading_icon_obj = LoadingIcon(spinner, animation_interval)
    thread = threading.Thread(target=loading_icon_obj.animate)
    thread.start()

    try:
        yield loading_icon_obj
    finally:
        loading_icon_obj.done = True
        thread.join()
