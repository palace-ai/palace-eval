from builtins import print as builtin_print

import emoji


def print(*args, sep=" ", end="\n"):
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
            i = j + 1

            # Closing tag: reset all styles
            if tag == "/":
                output.append("\033[0m")
                continue

            # Parse color/style tag
            parts = tag.split()
            bg_nums = [
                color_map[p] for p in parts if p.startswith("on_") and p in color_map
            ]
            fg_nums = [
                color_map[p]
                for p in parts
                if not p.startswith("on_") and p in color_map
            ]
            all_nums = bg_nums + fg_nums

            if all_nums:
                output.append(f"\033[{';'.join(all_nums)}m")
        else:
            output.append(text[i])
            i += 1

    # Reset at end if any SGR codes emitted
    if any(s.startswith("\033[") for s in output):
        output.append("\033[0m")

    # Use builtin print to avoid recursion
    builtin_print("".join(output), end=end, flush=True)
