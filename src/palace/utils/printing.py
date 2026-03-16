import itertools
import re
import threading
import time
from builtins import print as builtin_print
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

import emoji
from wcwidth import wcswidth

try:
    from IPython.core.getipython import get_ipython

    IN_NOTEBOOK = get_ipython() is not None
except ImportError:
    IN_NOTEBOOK = False


def _write_to_file(path: Path, *values: object, sep: str = " ", end: str = "\n"):
    # strip styling
    unstyled_values = [
        re.sub(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])", "", str(v)) for v in values
    ]

    with open(path, "a", encoding="utf-8") as f:
        f.write(sep.join([str(v) for v in unstyled_values]))
        f.write(end)


def print(
    *values: object,
    sep: str = " ",
    end: str = "\n",
    box: bool = False,
    box_title: Optional[str] = None,
    wrap_width: int = 110,
    file_path: Optional[Path] = None,
    file_only: bool = False,
    builtin: bool = False,
    as_str: bool = False,
) -> None | str:
    """Wraps the builtin `print` with additional styling and functionalities.

    Args:
        sep (str, optional): String inserted between values. Defaults to " ".
        end (str, optional): String appended after the last value. Defaults to "\\n".
        box (bool, optional): Draw a box surrounding the printed text. Defaults to False.
        box_title (Optional[str], optional): Set a header title for the box. Defaults to None.
        wrap_width (int, optional): Automatically wrap lines after the specified length. Defaults to 110.
        file_path (Optional[Path], optional): File path to write the printed text to file.
            When writing to file, all styling is removed. Defaults to None.
        file_only (bool, optional): If True, the text is not printed to the standard output, but only to file. Defaults to False.
        builtin (bool, optional): Use the builtin print, bypassing all styling options. Defaults to False.
    """
    if file_path is not None:
        file_path.parent.mkdir(parents=True, exist_ok=True)

    if builtin:
        if file_path is not None:
            _write_to_file(file_path, values, sep=sep, end=end)
        if not file_only:
            builtin_print(*values, sep=sep, end=end)
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

    def _apply_styles(s):
        i, n = 0, len(s)
        out = []
        active_styles = []
        any_sgr = False

        while i < n:
            if s[i] == "[" and (i == 0 or s[i - 1] != "\\"):
                j = s.find("]", i)
                if j == -1:
                    out.append(s[i])
                    i += 1
                    continue

                tag = s[i + 1 : j].lower().strip()
                parts = tag.split()

                if tag == "/":  # reset all
                    i = j + 1
                    active_styles.clear()
                    out.append("\033[0m")
                    any_sgr = True
                    continue

                if tag.startswith("/") and tag[1:] in color_map:
                    i = j + 1
                    style_to_remove = color_map[tag[1:]]
                    if style_to_remove in active_styles:
                        active_styles.remove(style_to_remove)
                    out.append("\033[0m")
                    if active_styles:
                        out.append(f"\033[{';'.join(active_styles)}m")
                    any_sgr = True
                    continue

                if all(part in color_map for part in parts):
                    i = j + 1
                    codes = [color_map[p] for p in parts]
                    active_styles.extend(codes)
                    seen = set()
                    active_styles = [
                        c for c in active_styles if not (c in seen or seen.add(c))
                    ]
                    out.append(f"\033[{';'.join(codes)}m")
                    any_sgr = True
                    continue

                out.append(s[i : j + 1])
                i = j + 1
                continue
            else:
                out.append(s[i])
                i += 1

        # keep active_styles as the final active SGR codes (do not clear them here)
        if any_sgr:
            out.append("\033[0m")

        return "".join(out), active_styles

    raw = sep.join(str(val) for val in values)
    text = emoji.emojize(raw, language="alias")
    # Many terminals don't combine multi-codepoint emoji sequences, causing
    # glyphs to overflow into adjacent cells. Insert hair spaces after
    # combining characters so the next character remains visible.
    text = text.replace("\ufe0f", "\ufe0f\u200a")
    text = re.sub("([\U0001f3fb-\U0001f3ff])", "\\1\u200a", text)  # skin tones
    text = re.sub("([\U0001f1e6-\U0001f1ff])", "\\1\u200a", text)  # regional indicators
    formatted_text, active_styles = _apply_styles(text)

    if box:

        def _real_len(s):
            clean_s = re.sub(r"\x1b\[[0-9;]*m", "", s)
            clean_s = clean_s.replace("\ufe0f", "").replace("\u200d", "")
            # Skin tone modifiers: wcswidth=0 but render as 2 cells
            clean_s = re.sub("[\U0001f3fb-\U0001f3ff]", "全", clean_s)
            # Regional indicators: wcswidth=1 but render as 1 cell (already correct)
            # Combining keycap: zero-width, renders as 0 cells
            clean_s = clean_s.replace("\u20e3", "")
            return wcswidth(clean_s)

        def _split_visible_chunks(string, chunk_len):
            tokens = re.findall(r"\033\[[0-9;]*m|.", string, re.DOTALL)
            chunks, chunk, width, current_sgr = [], "", 0, ""
            for t in tokens:
                if t.startswith("\033["):
                    if t == "\033[0m":
                        current_sgr = ""
                    else:
                        current_sgr = current_sgr + t
                    chunk += t
                    continue

                w = wcswidth(t)
                if width + w > chunk_len:
                    chunks.append(chunk)
                    chunk = current_sgr + t
                    width = w
                else:
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

        max_length = (
            max(_real_len(line) for line in wrapped_lines) if wrapped_lines != [] else 0
        )

        if box_title:
            title_text = emoji.emojize(box_title, language="alias")
            title_text = title_text.replace("\ufe0f", "\ufe0f\u200a")
            title_text = re.sub("([\U0001f3fb-\U0001f3ff])", "\\1\u200a", title_text)
            title_text = re.sub("([\U0001f1e6-\U0001f1ff])", "\\1\u200a", title_text)
            styled_title, _ = _apply_styles(title_text)
            box_title = f" {styled_title} "
        else:
            box_title = ""
        box_width = max(
            max_length, _real_len(box_title) - 2
        )

        horizontal_line = "─" * (box_width + 4)

        visible_title_width = _real_len(box_title)
        top_border = (
            f"\033[0m╭─\033[1m{box_title}\033[0m"
            f"{horizontal_line[visible_title_width + 1 :]}╮"
        )
        bottom_border = f"\033[0m╰{horizontal_line}╯"
        empty_line = f"\033[0m│  {' ' * box_width}  │"

        boxed_output = [top_border, empty_line]

        prefix = f"\033[{';'.join(active_styles)}m" if active_styles else ""

        for wrapped_line in wrapped_lines:
            padding = box_width - _real_len(wrapped_line)
            boxed_output.append(
                f"\033[0m│  {prefix}{wrapped_line}\033[0m{' ' * padding}  │"
            )

        boxed_output.append(empty_line)
        boxed_output.append(bottom_border)

        formatted_text = "\n".join(boxed_output)

    # Use builtin print to avoid recursion
    if as_str:
        return formatted_text
    if file_path is not None:
        _write_to_file(file_path, formatted_text, end=end)
    if not file_only:
        builtin_print(formatted_text, end=end, flush=True)


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
            print("\033[s", end="")
            while not self.done:
                elapsed_time = time.time() - self.start_time
                print("\033[u" + " " * self.last_length + "\033[u", end="")
                with self.lock:
                    desc = self.description
                    output = f"\033[u{next(self.spinner)}  ({elapsed_time:.1f}s)  {print(desc, as_str=True)}"
                    self.last_length = len(output) - 1
                print(output, end="")
                time.sleep(self.animation_interval)
            print("\033[u" + " " * self.last_length + "\033[u", end="")


@contextmanager
def loading() -> Generator["LoadingIcon", None, None]:
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
    animation_interval = 0.07

    loading_icon_obj = LoadingIcon(spinner, animation_interval)
    thread = threading.Thread(target=loading_icon_obj.animate)
    thread.start()

    try:
        yield loading_icon_obj
    finally:
        loading_icon_obj.done = True
        thread.join()
