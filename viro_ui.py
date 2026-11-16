"""Viro Sentinel terminal UI — branded chrome, no third-party product names."""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path


def _supports_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return True  # CLI tools usually color by default; Python TTY check is optional


COLOR = _supports_color()

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

# Mission-control palette (matches the Ops Theater page)
INK = "\033[38;5;255m"
MUTED = "\033[38;5;245m"
DIMMER = "\033[38;5;240m"
INDIGO = "\033[38;5;111m"
AMBER = "\033[38;5;214m"
EMERALD = "\033[38;5;78m"
ROSE = "\033[38;5;203m"
CYAN = "\033[38;5;80m"
VIOLET = "\033[38;5;141m"

H = "─"
V = "│"
TL, TR, BL, BR = "╭", "╮", "╰", "╯"


def c(text: str, *codes: str) -> str:
    if not COLOR or not codes:
        return text
    return "".join(codes) + text + RESET


def vis_len(text: str) -> int:
    return len(re.sub(r"\033\[[^m]*m", "", text))


def term_width(default: int = 78) -> int:
    try:
        return max(40, shutil.get_terminal_size((default, 24)).columns - 2)
    except Exception:
        return default


def rule(width: int | None = None, ch: str = H) -> str:
    return c(ch * (width or term_width()), DIMMER)


def box(lines: list[str], width: int | None = None, pad: int = 1) -> str:
    width = width or term_width()
    inner = max(10, width - 2 - pad * 2)
    out = [c(f"{TL}{H * (inner + pad * 2)}{TR}", DIMMER)]
    for line in lines:
        visible = vis_len(line)
        fill = inner + pad * 2 - visible
        if fill < 0:
            line = line[: inner + pad * 2]
            fill = 0
        out.append(c(f"{V}", DIMMER) + " " * pad + line + " " * fill + " " * pad + c(f"{V}", DIMMER))
    out.append(c(f"{BL}{H * (inner + pad * 2)}{BR}", DIMMER))
    return "\n".join(out)


def bar(value: float, maximum: float = 40.0, width: int = 28, tone: str = "auto") -> str:
    value = max(0.0, min(maximum, value))
    filled = int(round((value / maximum) * width))
    empty = width - filled
    if tone == "crisis" or (tone == "auto" and value <= 1):
        color = ROSE
    elif tone == "recover" or (tone == "auto" and 15 <= value < 24):
        color = AMBER
    else:
        color = EMERALD
    return c("█" * filled + "░" * empty, color)


def gauge(value: float, label: str = "", tone: str = "auto") -> str:
    pct = f"{value:5.1f}%"
    return f"  {bar(value, tone=tone)}  {c(pct, BOLD)}  {c(label, MUTED)}"


class ViroUI:
    """Pretty terminal chrome for Viro Sentinel."""

    def __init__(self, version: str = "1.0.0") -> None:
        self.version = version
        self.name = "Viro Sentinel"

    def banner(self) -> None:
        accent = c("◆", VIOLET + BOLD)
        title = f"  {accent}  {c('VIRO SENTINEL', INDIGO + BOLD)}  {c('·', DIMMER)}  {c('ops terminal', MUTED)}"
        sub = f"  {c('autonomous stockout recovery', MUTED)}  {c('|', DIMMER)}  {c('sandbox · verified outcomes', MUTED)}"
        ver = f"  {c(f'v{self.version}', DIMMER)}  {c('type', DIMMER)} {c('help', CYAN)} {c('for commands', DIMMER)}"
        print(box([title, "", sub, ver]))
        print()

    def prompt(self, context: str = "", modified: bool = False) -> str:
        icon = c("◆", VIOLET)
        name = c("sentinel", INDIGO + BOLD)
        ctx = ""
        if context:
            mark = c("*", AMBER) if modified else ""
            ctx = f" {c('[', DIMMER)}{c(context + mark, MUTED)}{c(']', DIMMER)}"
        return f"{icon} {name}{ctx} {c('❯', DIMMER)} "

    def help(self, commands: dict[str, str]) -> None:
        print(c("  Commands", INDIGO + BOLD))
        width = max(len(k) for k in commands) + 2
        for key, desc in commands.items():
            print(f"    {c(key.ljust(width), CYAN)}  {desc}")
        print()

    def success(self, msg: str) -> None:
        print(f"  {c('✓', EMERALD + BOLD)} {msg}")

    def error(self, msg: str) -> None:
        print(f"  {c('✗', ROSE + BOLD)} {msg}")

    def warning(self, msg: str) -> None:
        print(f"  {c('!', AMBER + BOLD)} {msg}")

    def info(self, msg: str) -> None:
        print(f"  {c('·', CYAN)} {msg}")

    def status(self, key: str, value: str) -> None:
        print(f"  {c(key.ljust(16), DIMMER)}  {value}")

    def section(self, title: str, subtitle: str = "") -> None:
        print()
        print(f"  {c(title, INDIGO + BOLD)}")
        if subtitle:
            print(f"  {c(subtitle, MUTED)}")
        print(f"  {c(H * min(64, term_width() - 4), DIMMER)}")

    def table(self, headers: list[str], rows: list[list[str]]) -> None:
        cols = len(headers)
        widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                widths[i] = max(widths[i], len(str(cell)))
        header_line = "  " + "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
        print(c(header_line, DIMMER))
        print("  " + "  ".join(H * widths[i] for i in range(cols)))
        for row in rows:
            print("  " + "  ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(row)))

    def goodbye(self) -> None:
        print()
        print(box([f"  {c('Stay watchful.', INDIGO + BOLD)}  {c('— Viro Sentinel', DIMMER)}"]))
        print()

    def get_input(self, session=None, project_name: str = "", modified: bool = False) -> str:
        return input(self.prompt(project_name, modified))
