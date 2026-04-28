from __future__ import annotations

import ctypes
import os
import shutil
import sys
import time
from dataclasses import dataclass
from typing import Callable

if os.name != "nt":
    import termios
    import tty


RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
WHITE = "\033[97m"
GRAY = "\033[90m"
CYAN = "\033[96m"
AMBER = "\033[38;5;214m"
RED = "\033[91m"
GREEN = "\033[92m"
SOFT_CYAN = "\033[38;5;117m"
SOFT_AMBER = "\033[38;5;223m"

ASCII_FALLBACK_BANNER = ["ELLIPTICZERO"]
UNICODE_ELLIPTIC_BANNER = [
    "███████╗██╗     ██╗     ██╗██████╗ ████████╗██╗ ██████╗",
    "██╔════╝██║     ██║     ██║██╔══██╗╚══██╔══╝██║██╔════╝",
    "█████╗  ██║     ██║     ██║██████╔╝   ██║   ██║██║",
    "██╔══╝  ██║     ██║     ██║██╔═══╝    ██║   ██║██║",
    "███████╗███████╗███████╗██║██║        ██║   ██║╚██████╗",
    "╚══════╝╚══════╝╚══════╝╚═╝╚═╝        ╚═╝   ╚═╝ ╚═════╝",
]
UNICODE_ZERO_BANNER = [
    "███████╗███████╗██████╗  ██████╗",
    "╚══███╔╝██╔════╝██╔══██╗██╔═══██╗",
    "  ███╔╝ █████╗  ██████╔╝██║   ██║",
    " ███╔╝  ██╔══╝  ██╔══██╗██║   ██║",
    "███████╗███████╗██║  ██║╚██████╔╝",
    "╚══════╝╚══════╝╚═╝  ╚═╝ ╚═════╝",
]
BOOT_STEPS = [
    (GRAY, GRAY, True),
    (SOFT_CYAN, SOFT_AMBER, False),
    (CYAN, AMBER, False),
]


@dataclass(frozen=True)
class ConsoleTheme:
    width: int = 94
    top_margin: int = 2
    boot_delay_seconds: float = 0.30
    panel_width: int = 82
    horizontal_bias: int = 1


@dataclass(frozen=True)
class MenuOption:
    label: str
    description: str


KeyProvider = Callable[[], str]


class LocalConsoleUI:
    """Cross-platform local console UI helper with a fixed EllipticZero brand banner."""

    def __init__(self, theme: ConsoleTheme | None = None) -> None:
        self.theme = theme or ConsoleTheme()
        self.color_enabled = self._enable_ansi()
        self.unicode_enabled = self._supports_unicode()
        self._boot_played = False
        self.last_menu_index = 0

    def clear(self) -> None:
        if sys.stdout.isatty():
            os.system("cls" if os.name == "nt" else "clear")

    def style(self, text: str, color: str, *, bold: bool = False, dim: bool = False) -> str:
        if not self.color_enabled:
            return text
        prefix = color
        if bold:
            prefix += BOLD
        if dim:
            prefix += DIM
        return f"{prefix}{text}{RESET}"

    def center_text(self, text: str, *, color: str = WHITE, bold: bool = False, dim: bool = False) -> str:
        return self._center(self.style(text, color, bold=bold, dim=dim))

    def separator(self, width: int | None = None) -> str:
        line_width = width or self.theme.panel_width
        return self._center(self.style("-" * line_width, GRAY))

    def panel(self, rows: list[str], *, width: int | None = None) -> list[str]:
        panel_width = width or self.theme.panel_width
        inner_width = panel_width - 4
        border = "+" + "-" * (panel_width - 2) + "+"
        output = [self._center(self.style(border, GRAY))]
        for row in rows:
            fitted = self._fit_visible(row, inner_width)
            padding = max(inner_width - self._visible_length(fitted), 0)
            output.append(
                self._center(
                    self.style("| ", GRAY)
                    + fitted
                    + (" " * padding)
                    + self.style(" |", GRAY)
                )
            )
        output.append(self._center(self.style(border, GRAY)))
        return output

    def status_chip(self, text: str, color: str) -> str:
        return self.style("[", GRAY) + self.style(text, color, bold=True) + self.style("]", GRAY)

    def key_value(self, key: str, value: str, *, value_color: str = WHITE, key_color: str = GRAY) -> str:
        return self.style(key, key_color) + self.style(value, value_color)

    def prompt(self, label: str, *, default: str | None = None) -> str:
        suffix = f" [{default}]" if default is not None else ""
        return input(self.style(f"{label}{suffix} > ", WHITE)).strip()

    def prompt_raw(self, label: str) -> str:
        return input(self.style(label + " ", WHITE))

    def prompt_centered_raw(self, label: str) -> str:
        prompt = self._center(self.style(label + " ", WHITE))
        return input(prompt)

    def pause(self, message: str = "Press Enter to continue...") -> None:
        input(self.style(message, GRAY, dim=True))

    def wait_action(self, hint: str) -> str:
        print(self.center_text(hint, color=GRAY, dim=True))
        while True:
            key = self.read_key()
            if key in {"enter", "escape"}:
                return "return"
            if key == "toggle_language":
                return "toggle_language"

    def hero_banner(self) -> list[str]:
        output = [""] * self.theme.top_margin
        if self.unicode_enabled:
            output.extend(self._render_unicode_banner(CYAN, AMBER))
        else:
            output.extend(self._render_ascii_banner(CYAN, AMBER))
        return output

    def subtitle(self, text: str) -> str:
        return self.center_text(text, color=WHITE, bold=True)

    def render_menu_screen(
        self,
        *,
        header_lines: list[str],
        options: list[MenuOption],
        selected_index: int,
        hint: str = "Use arrow keys and Enter",
    ) -> list[str]:
        lines = list(header_lines)
        lines.append("")
        panel_rows: list[str] = []
        for index, option in enumerate(options):
            active = index == selected_index
            prefix = self.style(">", CYAN, bold=True) if active else " "
            label = self.style(option.label, CYAN if active else WHITE, bold=active)
            description = self.style(option.description, WHITE if active else GRAY, dim=not active)
            label_block = self._pad_visible(self._fit_visible(f"{prefix} {label}", 28), 28)
            panel_rows.append(f"{label_block} | {description}")
        lines.extend(self.panel(panel_rows))
        lines.append(self.center_text(options[selected_index].label, color=CYAN, bold=True))
        lines.append(self.center_text(options[selected_index].description, color=GRAY, dim=True))
        lines.append(self.center_text(hint, color=GRAY, dim=True))
        return lines

    def choose_menu(
        self,
        *,
        header_lines: list[str],
        options: list[MenuOption],
        start_index: int = 0,
        hint: str = "Use arrow keys and Enter",
        allow_escape: bool = True,
        key_provider: KeyProvider | None = None,
    ) -> int | None | str:
        selected = start_index
        read_key = key_provider or self.read_key

        while True:
            self.clear()
            for line in self.render_menu_screen(
                header_lines=header_lines,
                options=options,
                selected_index=selected,
                hint=hint,
            ):
                print(line)

            key = read_key()
            if key in {"up", "left", "k", "w"}:
                selected = (selected - 1) % len(options)
            elif key in {"down", "right", "j", "s"}:
                selected = (selected + 1) % len(options)
            elif key == "toggle_language":
                self.last_menu_index = selected
                return "toggle_language"
            elif key == "enter":
                self.last_menu_index = selected
                return selected
            elif allow_escape and key == "escape":
                self.last_menu_index = selected
                return None

    def play_boot_animation(self) -> None:
        if self._boot_played:
            return
        if not sys.stdout.isatty():
            self._boot_played = True
            return
        if os.environ.get("ELLIPTICZERO_NO_ANIMATION", "").strip() == "1":
            self._boot_played = True
            return

        for left_color, right_color, dim_banner in BOOT_STEPS:
            self.clear()
            print("\n" * self.theme.top_margin, end="")
            rendered = (
                self._render_unicode_banner(left_color, right_color, dim=dim_banner)
                if self.unicode_enabled
                else self._render_ascii_banner(left_color, right_color, dim=dim_banner)
            )
            for line in rendered:
                print(line)
            time.sleep(self.theme.boot_delay_seconds)

        self._boot_played = True

    def read_key(self) -> str:
        if os.name == "nt":
            import msvcrt

            first = msvcrt.getwch()
            if first in {"\x00", "\xe0"}:
                second = msvcrt.getwch()
                return {
                    "H": "up",
                    "P": "down",
                    "K": "left",
                    "M": "right",
                    "<": "toggle_language",
                }.get(second, "unknown")
            if first == "\r":
                return "enter"
            if first == "\x1b":
                return "escape"
            return self._normalize_printable_key(first)

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            first = sys.stdin.read(1)
            if first == "\x1b":
                second = sys.stdin.read(1)
                if second == "O":
                    third = sys.stdin.read(1)
                    if third == "Q":
                        return "toggle_language"
                    return "escape"
                if second != "[":
                    return "escape"
                third = sys.stdin.read(1)
                return {
                    "A": "up",
                    "B": "down",
                    "C": "right",
                    "D": "left",
                }.get(third, self._read_extended_escape(third))
            if first in {"\r", "\n"}:
                return "enter"
            return self._normalize_printable_key(first)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    def table(self, headers: list[str], rows: list[list[str]], widths: list[int]) -> list[str]:
        def fit(value: str, width: int) -> str:
            plain = value.strip()
            if len(plain) <= width:
                return plain.ljust(width)
            if width <= 3:
                return plain[:width]
            return plain[: width - 3] + "..."

        border = "+" + "+".join("-" * (width + 2) for width in widths) + "+"
        output = [self._center(self.style(border, GRAY))]
        output.append(
            self._center(
                self.style(
                "| " + " | ".join(fit(header, width) for header, width in zip(headers, widths, strict=False)) + " |",
                WHITE,
                bold=True,
            )
            )
        )
        output.append(self._center(self.style(border, GRAY)))
        for row in rows:
            output.append(
                self._center(
                    self.style(
                        "| " + " | ".join(fit(cell, width) for cell, width in zip(row, widths, strict=False)) + " |",
                        WHITE,
                    )
                )
            )
        output.append(self._center(self.style(border, GRAY)))
        return output

    def _render_ascii_banner(self, left_color: str, right_color: str, *, dim: bool = False) -> list[str]:
        return [
            self._center(
                self.style("ELLIPTIC", left_color, bold=True, dim=dim)
                + self.style("ZERO", right_color, bold=True, dim=dim)
            )
        ]

    def _render_unicode_banner(self, left_color: str, right_color: str, *, dim: bool = False) -> list[str]:
        output: list[str] = []
        left_width = max(len(line) for line in UNICODE_ELLIPTIC_BANNER)
        right_width = max(len(line) for line in UNICODE_ZERO_BANNER)
        for left_row, right_row in zip(UNICODE_ELLIPTIC_BANNER, UNICODE_ZERO_BANNER, strict=True):
            line = (
                self.style(left_row.ljust(left_width), left_color, bold=True, dim=dim)
                + "   "
                + self.style(right_row.ljust(right_width), right_color, bold=True, dim=dim)
            )
            output.append(self._center(line))
        return output

    def _center(self, text: str) -> str:
        visible_length = self._visible_length(text)
        layout_width = self._layout_width()
        if visible_length >= layout_width:
            return text
        left_padding = ((layout_width - visible_length) // 2) + self.theme.horizontal_bias
        return (" " * left_padding) + text

    def _layout_width(self) -> int:
        terminal_width = shutil.get_terminal_size(fallback=(self.theme.width, 24)).columns
        return max(self.theme.width, terminal_width)

    def _read_extended_escape(self, first_char: str) -> str:
        if not first_char.isdigit():
            return "escape"
        sequence = first_char
        while True:
            next_char = sys.stdin.read(1)
            sequence += next_char
            if next_char.isalpha() or next_char == "~":
                break
        if sequence == "12~":
            return "toggle_language"
        return "escape"

    def _normalize_printable_key(self, value: str) -> str:
        lowered = value.lower()
        if lowered in {"l", "д"}:
            return "toggle_language"
        return lowered

    def _truncate(self, text: str, width: int) -> str:
        if len(text) <= width:
            return text
        if width <= 3:
            return text[:width]
        return text[: width - 3] + "..."

    def _fit_visible(self, text: str, width: int) -> str:
        if self._visible_length(text) <= width:
            return text
        if width <= 3:
            return self._take_visible(text, width)
        return self._take_visible(text, width - 3) + "..."

    def _pad_visible(self, text: str, width: int) -> str:
        padding = max(width - self._visible_length(text), 0)
        return text + (" " * padding)

    def _take_visible(self, text: str, width: int) -> str:
        output: list[str] = []
        visible = 0
        inside = False
        has_ansi = "\033" in text

        for char in text:
            if char == "\033":
                inside = True
                output.append(char)
                continue
            if inside:
                output.append(char)
                if char == "m":
                    inside = False
                continue
            if visible >= width:
                break
            output.append(char)
            visible += 1

        if has_ansi and self.color_enabled and not inside and not "".join(output).endswith(RESET):
            output.append(RESET)
        return "".join(output)

    def _visible_length(self, text: str) -> int:
        return len(self._strip_ansi(text))

    def _strip_ansi(self, text: str) -> str:
        output: list[str] = []
        inside = False
        for char in text:
            if char == "\033":
                inside = True
                continue
            if inside:
                if char == "m":
                    inside = False
                continue
            output.append(char)
        return "".join(output)

    def _enable_ansi(self) -> bool:
        if not sys.stdout.isatty():
            return False
        if os.name != "nt":
            return True
        try:
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.GetStdHandle(-11)
            mode = ctypes.c_uint32()
            if kernel32.GetConsoleMode(handle, ctypes.byref(mode)) == 0:
                return False
            if kernel32.SetConsoleMode(handle, mode.value | 0x0004) == 0:
                return False
            return True
        except Exception:
            return False

    def _supports_unicode(self) -> bool:
        encoding = (sys.stdout.encoding or "").lower()
        return "utf" in encoding
