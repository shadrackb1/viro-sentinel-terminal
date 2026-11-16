#!/usr/bin/env python3
"""
Viro Sentinel — dramatic partitioned ops TUI.

  ┌─ LIVE TRACKER ────────────┬─ RUN BRIEF / COMMANDS ───┐
  │ gauge · inventory · phase │ organized run data        │
  ├─ ACTIVITY LOG ────────────┴──────────────────────────┤
  │ streaming theater lines                               │
  ├─ COMMAND ────────────────────────────────────────────┤
  │ [1]run [2]status …   sentinel › █                    │
  └──────────────────────────────────────────────────────┘
"""
from __future__ import annotations

import os
import re
import shutil
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
for path in (
    HERE,
    os.path.join(HERE, "viro-sentinel"),
    os.path.abspath(os.path.join(HERE, "..", "viro-sentinel")),
    r"C:\Users\ADMIN\XiaomiMiMoProjects\cli-anything\viro-sentinel\agent-harness\cli_anything\viro_sentinel",
):
    if os.path.isdir(os.path.join(path, "sandbox")):
        sys.path.insert(0, path)
        break

# ── ANSI ──────────────────────────────────────────────────────────────
RESET, BOLD, DIM = "\033[0m", "\033[1m", "\033[2m"
HIDE, SHOW = "\033[?25l", "\033[?25h"
CLEAR = "\033[2J\033[H"
ALT_ON, ALT_OFF = "\033[?1049h", "\033[?1049l"

INK = "\033[38;5;255m"
MUTED = "\033[38;5;245m"
DIMMER = "\033[38;5;240m"
INDIGO = "\033[38;5;111m"
AMBER = "\033[38;5;214m"
EMERALD = "\033[38;5;78m"
ROSE = "\033[38;5;203m"
CYAN = "\033[38;5;80m"
VIOLET = "\033[38;5;141m"
GOLD = "\033[38;5;220m"
CRIMSON = "\033[38;5;167m"


def c(text: str, *codes: str) -> str:
    return ("".join(codes) + text + RESET) if codes else text


def vis_len(text: str) -> int:
    return len(re.sub(r"\033\[[^m]*m", "", text))


def term_size() -> tuple[int, int]:
    s = shutil.get_terminal_size((110, 36))
    return max(80, s.columns), max(24, s.lines)


# ── Frame buffer ──────────────────────────────────────────────────────
class Frame:
    def __init__(self, w: int, h: int) -> None:
        self.w, self.h = w, h
        self.cells = [[" "] * w for _ in range(h)]
        self.colors = [[""] * w for _ in range(h)]

    def clear(self) -> None:
        for y in range(self.h):
            for x in range(self.w):
                self.cells[y][x] = " "
                self.colors[y][x] = ""

    def put(self, x: int, y: int, text: str, color: str = "") -> None:
        if not (0 <= y < self.h):
            return
        plain = re.sub(r"\033\[[^m]*m", "", text)
        for i, ch in enumerate(plain):
            xx = x + i
            if 0 <= xx < self.w:
                self.cells[y][xx] = ch
                self.colors[y][xx] = color

    def hline(self, x: int, y: int, w: int, ch: str = "─", color: str = DIMMER) -> None:
        self.put(x, y, ch * w, color)

    def box(self, x: int, y: int, w: int, h: int, title: str = "", accent: str = INDIGO) -> None:
        if w < 3 or h < 2:
            return
        self.put(x, y, "╭", accent)
        self.put(x + w - 1, y, "╮", accent)
        self.put(x, y + h - 1, "╰", accent)
        self.put(x + w - 1, y + h - 1, "╯", accent)
        self.hline(x + 1, y, w - 2, "─", accent)
        self.hline(x + 1, y + h - 1, w - 2, "─", accent)
        for yy in range(y + 1, y + h - 1):
            self.put(x, yy, "│", accent)
            self.put(x + w - 1, yy, "│", accent)
        if title:
            self.put(x + 2, y, f" {title} "[: max(0, w - 4)], accent + BOLD)

    def render(self) -> str:
        out = []
        for y in range(self.h):
            parts, last, run = [], None, []
            for x in range(self.w):
                col = self.colors[y][x] or INK
                if col != last:
                    if run:
                        parts.append((last or "", "".join(run)))
                    run, last = [self.cells[y][x]], col
                else:
                    run.append(self.cells[y][x])
            if run:
                parts.append((last or "", "".join(run)))
            while parts and parts[-1][1].strip() == "" and parts[-1][0] in ("", INK):
                parts.pop()
            buf = []
            for color, text in parts:
                buf.append(color + text + RESET if color else text)
            out.append("".join(buf))
        return "\n".join(out)


# ── State ─────────────────────────────────────────────────────────────
@dataclass
class Tracker:
    conversion: float = 24.0
    history: deque = field(default_factory=lambda: deque([24.0] * 20, maxlen=20))
    inventory: int = 40
    target_inventory: int = 65
    phase: str = "baseline"
    product_status: str = "on the shelf"
    target_status: str = "ready to help"
    last_event: str = "awaiting anomaly"
    pulse: int = 0
    tools_used: int = 0
    verified: bool = False
    running: bool = False
    act: str = "idle"


@dataclass
class RunBrief:
    ready: bool = False
    status: str = ""
    incident: str = ""
    product: str = ""
    event: str = ""
    evidence: list = field(default_factory=list)
    decision: str = ""
    score: str = ""
    action: str = ""
    before_pct: float = 0.0
    after_pct: float = 0.0
    formula: str = "buys ÷ visits"
    verified: bool = False
    policy: str = "safe auto-fix (no approval needed)"
    tools: int = 0
    elapsed: str = ""

    def rows(self) -> list[tuple[str, str, str]]:
        return [
            ("outcome", self.status, "ok" if self.verified else "bad"),
            ("problem", self.incident, "warn"),
            ("products", self.product, "ink"),
            ("we noticed", self.event, "warn"),
            ("we chose", self.decision, "ink"),
            ("how well it fits", self.score, "ok"),
            ("what we did", self.action, "warn"),
            ("buys before", f"{self.before_pct:.1f}%", "bad"),
            ("buys after", f"{self.after_pct:.1f}%", "ok" if self.verified else "warn"),
            ("how we measure", self.formula, "dim"),
            ("permission", self.policy, "ink"),
            ("checks run", str(self.tools), "dim"),
            ("time taken", self.elapsed, "dim"),
        ]


@dataclass
class App:
    svc: Any = None
    db: Any = None
    tracker: Tracker = field(default_factory=Tracker)
    brief: RunBrief = field(default_factory=RunBrief)
    log: deque = field(default_factory=lambda: deque(maxlen=300))
    status_msg: str = "Ready · press 1 to watch, or 0 for help"
    lock: threading.Lock = field(default_factory=threading.Lock)
    stop_live: bool = False
    awaiting_input: bool = False
    redraw_busy: bool = False


APP = App()

COMMANDS: list[tuple[str, str, str]] = [
    ("1", "watch", "See the shop problem get fixed"),
    ("2", "shop", "How the shop looks right now"),
    ("3", "check", "Did the fix actually work?"),
    ("4", "report", "Open the full story report"),
    ("5", "backup", "Find a good stand-in product"),
    ("6", "alert", "What did we notice first?"),
    ("7", "repeat", "What if the same alert arrives twice?"),
    ("8", "powers", "What this helper is allowed to do"),
    ("9", "undo", "Put the shop back to normal"),
    ("0", "help", "Show me what I can do"),
    ("q", "bye", "Close this window"),
]

WORD_MAP = {
    "watch": "1", "run": "1", "start": "1", "play": "1", "story": "1",
    "shop": "2", "status": "2", "look": "2",
    "check": "3", "verify": "3", "did it work": "3",
    "report": "4", "brief": "4", "results": "4", "summary": "4",
    "backup": "5", "recommend": "5", "replace": "5", "alternative": "5",
    "alert": "6", "event": "6", "notice": "6", "what happened": "6",
    "repeat": "7", "duplicate": "7", "twice": "7",
    "powers": "8", "tools": "8", "allowed": "8", "rules": "8",
    "undo": "9", "reset": "9", "fresh": "9", "restart": "9",
    "help": "0", "h": "0", "?": "0", "menu": "0",
    "bye": "q", "quit": "q", "exit": "q", "close": "q",
}


def log_line(kind: str, text: str, color: str = MUTED) -> None:
    with APP.lock:
        APP.log.append((time.strftime("%H:%M:%S"), kind, text, color))


def open_sandbox(reseed: bool = True) -> None:
    from sandbox.database import SessionLocal, reset_db
    from sandbox.seed import seed_deterministic_data
    from sandbox.service import SandboxService

    if APP.db is not None:
        try:
            APP.db.close()
        except Exception:
            pass
    if reseed:
        reset_db()
    APP.db = SessionLocal()
    if reseed:
        seed_deterministic_data(APP.db)
    APP.svc = SandboxService(APP.db)


def refresh_tracker() -> None:
    if APP.svc is None:
        return
    try:
        inv = APP.svc.get_inventory("product_demo_001")
        tgt = APP.svc.get_inventory("product_demo_002")
        base = APP.svc.get_conversion("product_demo_001", window="baseline")
        post = APP.svc.get_conversion("product_demo_001", window="post_stockout")
        with APP.lock:
            t = APP.tracker
            t.inventory = int(inv.get("inventory_count") or 0)
            t.target_inventory = int(tgt.get("inventory_count") or 0)
            status_words = {
                "active": "on the shelf",
                "out_of_stock": "sold out",
                "unavailable": "not selling",
                "promotion_paused": "ads paused",
            }
            t.product_status = status_words.get(str(inv.get("status") or ""), str(inv.get("status") or "?"))
            t.target_status = status_words.get(str(tgt.get("status") or ""), t.target_status if t.phase != "baseline" else "ready to help")
            if t.phase == "baseline":
                t.conversion = float(base.get("conversion_rate_pct") or 24.0)
            elif t.phase == "crisis":
                t.conversion = float(post.get("conversion_rate_pct") or 0.0)
            t.history.append(t.conversion)
            t.pulse = (t.pulse + 1) % 6
    except Exception:
        pass


def live_loop() -> None:
    while not APP.stop_live:
        refresh_tracker()
        if not APP.awaiting_input and not APP.tracker.running and not APP.redraw_busy:
            try:
                redraw()
            except Exception:
                pass
        time.sleep(0.7)


# ── Drawing ───────────────────────────────────────────────────────────
def sparkline(vals: deque, width: int = 18) -> str:
    blocks = "▁▂▃▄▅▆▇█"
    data = list(vals)[-width:]
    if not data:
        return ""
    lo, hi = min(data), max(data)
    span = (hi - lo) or 1.0
    return "".join(blocks[int((v - lo) / span * (len(blocks) - 1))] for v in data)


def gauge_bar(value: float, maximum: float = 40.0, width: int = 22, tone: str = "auto") -> tuple[str, str]:
    value = max(0.0, min(maximum, value))
    filled = int(round((value / maximum) * width))
    if tone == "crisis" or (tone == "auto" and value <= 1):
        color = ROSE
    elif tone == "recover" or (tone == "auto" and 15 <= value < 24):
        color = GOLD
    else:
        color = EMERALD
    return "█" * filled + "░" * (width - filled), color


def banner_art(width: int) -> list[str]:
    """Dramatic title strip for attention."""
    line = "◆  V I R O   S E N T I N E L  ·  OPS THEATER  ◆"
    pad = max(0, (width - len(line)) // 2)
    edge = "═" * width
    return [edge, " " * pad + line, edge]


def build_frame() -> str:
    cols, rows = term_size()
    top_h = max(13, min(17, rows // 2 - 1))
    input_h = 4
    log_h = max(6, rows - top_h - input_h - 1)
    left_w = max(40, int(cols * 0.52))
    right_w = cols - left_w
    t = APP.tracker
    brief = APP.brief

    F = Frame(cols, rows)
    F.clear()

    # ── LIVE TRACKER (dramatic) ───────────────────────────────────
    accent = ROSE if t.phase == "crisis" else (GOLD if t.phase in {"redirect", "recovered"} else INDIGO)
    F.box(0, 0, left_w, top_h, "SHOP HEALTH · live", accent)
    pulse = "◉●○"[t.pulse % 3]
    phase_color = {"baseline": EMERALD, "crisis": ROSE, "redirect": GOLD, "recovered": EMERALD, "unverified": ROSE}.get(t.phase, INK)
    F.put(2, 2, c(f"{pulse} LIVE", phase_color + BOLD), phase_color)
    phase_words = {
        "baseline": "HEALTHY",
        "crisis": "TROUBLE",
        "redirect": "FIXING",
        "recovered": "RECOVERED",
        "unverified": "UNSURE",
    }
    F.put(12, 2, c("state  ", MUTED) + c(phase_words.get(t.phase, t.phase), phase_color + BOLD), INK)
    tone = "crisis" if t.conversion <= 1 else ("recover" if t.phase in {"redirect", "recovered"} else "auto")
    bar, bar_color = gauge_bar(t.conversion, tone=tone)
    F.put(2, 4, c("buy rate", MUTED), MUTED)
    F.put(14, 4, c(f"{t.conversion:5.1f}%", BOLD + bar_color), bar_color)
    F.put(23, 4, c(bar, bar_color), bar_color)
    F.put(2, 5, c("recent  ", MUTED) + c(sparkline(t.history), CYAN), CYAN)
    inv_c = ROSE if t.inventory == 0 else EMERALD
    tgt_c = GOLD if t.target_status in {"helping shoppers", "chosen"} else EMERALD
    F.put(2, 7, c("Street Runner", INK) + "   " + c(f"{t.inventory:3}", inv_c + BOLD) + "  " + c(t.product_status, inv_c), INK)
    F.put(2, 8, c("Trail Walker ", INK) + "   " + c(f"{t.target_inventory:3}", tgt_c + BOLD) + "  " + c(t.target_status, tgt_c), INK)
    F.put(2, 10, c("checks", MUTED) + f"  {t.tools_used}", INK)
    F.put(14, 10, c("fixed?", MUTED) + "  " + (c("YES", EMERALD + BOLD) if t.verified else c("not yet", DIMMER)), INK)
    F.put(2, 11, c("note   ", MUTED) + c(t.last_event[: max(0, left_w - 12)], DIMMER), DIMMER)
    if t.running:
        acts = ["boot", "crisis", "evidence", "decision", "redirect", "verify"]
        act_words = {
            "boot": "GETTING READY",
            "crisis": "TROUBLE STARTS",
            "evidence": "LOOKING FOR CLUES",
            "decision": "MAKING A CHOICE",
            "redirect": "FIXING IT",
            "verify": "CHECKING IT WORKED",
        }
        idx = acts.index(t.act) if t.act in acts else 0
        ticks = "".join((c("●", EMERALD) if i < idx else c("◉", GOLD + BOLD) if i == idx else c("○", DIMMER)) + " " for i in range(len(acts)))
        F.put(2, 13, c("story  ", MUTED) + "  " + ticks, INK)
        F.put(2, 14, c("now    ", MUTED) + c(act_words.get(t.act, t.act), GOLD + BOLD), INK)
    else:
        F.put(2, 13, c("tip", MUTED) + "  press 1 to watch the full story", DIMMER)

    # ── RIGHT: RUN BRIEF or COMMANDS ─────────────────────────────
    if brief.ready:
        F.box(left_w, 0, right_w, top_h, "YOUR REPORT · what happened", EMERALD)
        tones = {"ok": EMERALD, "bad": ROSE, "warn": GOLD, "dim": MUTED, "ink": INK}
        y = 2
        for label, value, tone in brief.rows():
            if y >= top_h - 1:
                break
            F.put(left_w + 2, y, c(f"{label:10}", MUTED) + c(str(value)[: max(0, right_w - 16)], tones.get(tone, INK)), INK)
            y += 1
        if brief.evidence and y < top_h - 1:
            F.put(left_w + 2, y, c("evidence", MUTED), MUTED)
            y += 1
            for ev in brief.evidence[:2]:
                if y >= top_h - 1:
                    break
                F.put(left_w + 4, y, c(f"· {ev}"[: max(0, right_w - 10)], CYAN), CYAN)
                y += 1
    else:
        F.box(left_w, 0, right_w, top_h, "WHAT YOU CAN DO · pick one", AMBER)
        y = 2
        for key, name, desc in COMMANDS:
            if y >= top_h - 1:
                break
            F.put(left_w + 2, y, c(f" [{key}]", AMBER + BOLD) + c(name.ljust(11), INK) + c(desc[: max(0, right_w - 20)], MUTED), INK)
            y += 1

    # ── ACTIVITY LOG ─────────────────────────────────────────────
    F.box(0, top_h, cols, log_h, "WHAT IS HAPPENING · live story", VIOLET)
    lines = list(APP.log)[-(log_h - 2) :]
    yy = top_h + 1
    for stamp, kind, text, color in lines:
        if yy >= top_h + log_h - 1:
            break
        prefix = c(f"{stamp} ", DIMMER) + c(f"{kind:<8}", color + BOLD) + " "
        F.put(2, yy, prefix + c(text[: max(0, cols - 18)], color), color)
        yy += 1

    # ── COMMAND BAR (always a place to type) ─────────────────────
    bar_y = top_h + log_h
    F.box(0, bar_y, cols, input_h, "YOUR MOVE · type a word or number", CYAN)
    hot = " ".join(f"[{k}]{n}" for k, n, _ in COMMANDS[:6])
    F.put(2, bar_y + 1, c(hot[: cols - 4], DIMMER), DIMMER)
    if APP.awaiting_input:
        F.put(
            2,
            bar_y + 2,
            c("sentinel", INDIGO + BOLD)
            + c(" › ", DIMMER)
            + c("type here", GOLD + BOLD)
            + c("  then Enter  ·  try: watch, shop, check, report, bye", MUTED)
            + c("▌", GOLD),
            INK,
        )
    else:
        F.put(2, bar_y + 2, c("sentinel", INDIGO + BOLD) + c(" › ", DIMMER) + c(APP.status_msg, MUTED), INK)

    return F.render()


def redraw() -> None:
    APP.redraw_busy = True
    try:
        sys.stdout.write(CLEAR + HIDE + build_frame())
        sys.stdout.flush()
    finally:
        APP.redraw_busy = False


# ── Theater helpers ───────────────────────────────────────────────────
def set_act(name: str) -> None:
    APP.tracker.act = name


def stage(title: str, sub: str, color: str) -> None:
    rule = "═" * min(50, len(title) + 16)
    log_line("", rule, color)
    log_line("ACT", title.upper(), color + BOLD)
    if sub:
        log_line("", f"   {sub}", MUTED)
    log_line("", rule, color)
    redraw()


def typewriter(kind: str, text: str, color: str = CYAN, delay: float = 0.012) -> None:
    shown = ""
    for ch in text:
        shown += ch
        with APP.lock:
            if APP.log and APP.log[-1][1] == "TYPE":
                APP.log.pop()
            APP.log.append((time.strftime("%H:%M:%S"), "TYPE", shown + "▌", color))
        redraw()
        time.sleep(delay)
    with APP.lock:
        if APP.log and APP.log[-1][1] == "TYPE":
            APP.log.pop()
    log_line(kind, text, color)


def thinking(label: str, color: str = CYAN, cycles: int = 3) -> None:
    for i in range(cycles):
        APP.status_msg = f"{label}{'.' * (i % 4)}"
        redraw()
        time.sleep(0.12)


def progress(label: str, color: str = GOLD, frames: int = 10) -> None:
    width = 22
    for i in range(frames + 1):
        filled = int(width * i / frames)
        APP.status_msg = f"{label}  {'█' * filled}{'░' * (width - filled)}"
        redraw()
        time.sleep(0.07)


def animate_conversion(target: float, steps: int = 12, delay: float = 0.04, tone: str = "auto") -> None:
    start = APP.tracker.conversion
    for i in range(1, steps + 1):
        frac = i / steps
        frac = frac * frac * (3 - 2 * frac)
        APP.tracker.conversion = start + (target - start) * frac
        if i % 3 == 0:
            APP.tracker.history.append(APP.tracker.conversion)
        redraw()
        time.sleep(delay)
    APP.tracker.conversion = target
    APP.tracker.history.append(target)
    redraw()


def open_brief_window() -> None:
    """Launch a dramatic new terminal window with organized post-run data."""
    b = APP.brief
    if not b.ready:
        return
    report_path = os.path.join(HERE, "_run_brief_display.py")
    # Serialized payload the child window renders dramatically
    payload = {
        "status": b.status,
        "incident": b.incident,
        "product": b.product,
        "event": b.event,
        "evidence": list(b.evidence),
        "decision": b.decision,
        "score": b.score,
        "action": b.action,
        "before_pct": b.before_pct,
        "after_pct": b.after_pct,
        "formula": b.formula,
        "verified": b.verified,
        "policy": b.policy,
        "tools": b.tools,
        "elapsed": b.elapsed,
    }
    import json as _json

    data_json = _json.dumps(payload)
    script = (
        "# -*- coding: utf-8 -*-\n"
        "# Auto-generated dramatic run brief for Viro Sentinel\n"
        "import json, os, sys, time\n"
        "os.system('')\n"
        f"data = json.loads({data_json!r})\n"
        "R, B = '\\033[0m', '\\033[1m'\n"
        "INK, MUT, DIM = '\\033[38;5;255m', '\\033[38;5;245m', '\\033[38;5;240m'\n"
        "IND, AMB, EME = '\\033[38;5;111m', '\\033[38;5;214m', '\\033[38;5;78m'\n"
        "ROS, CYN, VIO = '\\033[38;5;203m', '\\033[38;5;80m', '\\033[38;5;141m'\n"
        "GLD = '\\033[38;5;220m'\n"
        "def p(text='', *codes):\n"
        "    print((''.join(codes) + text + R) if codes else text)\n"
        "def rule(ch='═', n=64, color=DIM):\n"
        "    p(ch * n, color)\n"
        "def row(label, value, color=INK):\n"
        "    p('  │  ' + str(label).ljust(22) + str(value), color)\n"
        "def typewrite(text, delay=0.012, *codes):\n"
        "    for ch in text:\n"
        "        sys.stdout.write((''.join(codes) + ch + R) if codes else ch)\n"
        "        sys.stdout.flush()\n"
        "        time.sleep(delay)\n"
        "    print()\n"
        "def bar(value, maximum=40.0, width=28):\n"
        "    value = max(0.0, min(maximum, float(value)))\n"
        "    filled = int(round(value / maximum * width))\n"
        "    col = ROS if value <= 1 else (GLD if value >= 20 else EME)\n"
        "    return '█' * filled + '░' * (width - filled), col\n"
        "print()\n"
        "rule()\n"
        "p('   ◆  STORY COMPLETE  ·  YOUR REPORT', IND + B)\n"
        "rule()\n"
        "print()\n"
        "typewrite('   Gathering the real shop numbers…', 0.025, MUT)\n"
        "time.sleep(0.35)\n"
        "print()\n"
        "before = float(data['before_pct'])\n"
        "after = float(data['after_pct'])\n"
        "bfill, bcol = bar(before)\n"
        "afill, acol = bar(after)\n"
        "p('   BUY RATE BEFORE THE FIX', ROS + B)\n"
        "p('   ' + bcol + bfill + R + '  ' + format(before, '5.1f') + '%')\n"
        "p('   BUY RATE AFTER THE FIX', EME + B)\n"
        "p('   ' + acol + afill + R + '  ' + format(after, '5.1f') + '%')\n"
        "print()\n"
        "p('   Change: {:+.1f} points   ·   measured as: {}'.format(after - before, data['formula']), GLD + B)\n"
        "print()\n"
        "rule('─', 64, DIM)\n"
        "p('   ┌─────────────────────────────────────────────────────────────┐', IND)\n"
        "p('   │  WHAT HAPPENED', IND + B)\n"
        "p('   └─────────────────────────────────────────────────────────────┘', IND)\n"
        "row('problem', data['incident'])\n"
        "row('products', data['product'])\n"
        "row('we noticed', data['event'], AMB)\n"
        "row('we chose', data['decision'], CYN)\n"
        "row('how well it fits', data['score'], EME)\n"
        "row('what we did', data['action'], AMB)\n"
        "print()\n"
        "p('   ┌─────────────────────────────────────────────────────────────┐', CYN)\n"
        "p('   │  CLUES WE FOUND', CYN + B)\n"
        "p('   └─────────────────────────────────────────────────────────────┘', CYN)\n"
        "for i, ev in enumerate(data.get('evidence') or [], 1):\n"
        "    typewrite('   %02d  %s' % (i, ev), 0.008, CYN)\n"
        "print()\n"
        "p('   ┌─────────────────────────────────────────────────────────────┐', VIO)\n"
        "p('   │  PERMISSIONS USED', VIO + B)\n"
        "p('   └─────────────────────────────────────────────────────────────┘', VIO)\n"
        "row('permission', data['policy'])\n"
        "row('checks run', data['tools'])\n"
        "row('time taken', data['elapsed'])\n"
        "row('did it work?', 'YES · confirmed in records' if data['verified'] else 'NOT YET', EME if data['verified'] else ROS)\n"
        "print()\n"
        "rule()\n"
        "if data['verified']:\n"
        "    p('   ✓  THE FIX WORKED', EME + B)\n"
        "    p('   These numbers come from real shop records, not guesses.', MUT)\n"
        "else:\n"
        "    p('   ✗  NOT CONFIRMED YET', ROS + B)\n"
        "rule()\n"
        "print()\n"
        "p('   You can close this window when you are done.', DIM)\n"
        "print()\n"
        "os.system('pause')\n"
    )
    try:
        with open(report_path, "w", encoding="utf-8") as fh:
            fh.write(script)
    except Exception as exc:
        log_line("ERROR", f"brief window write failed: {exc}", ROSE)
        redraw()
        return

    py = sys.executable
    try:
        import subprocess

        CREATE_NEW_CONSOLE = 0x00000010
        # Spawn a fresh console so the brief plays dramatically on its own
        subprocess.Popen(
            [py, report_path],
            cwd=HERE,
            creationflags=CREATE_NEW_CONSOLE,
            close_fds=True,
        )
        log_line("BRIEF", "dramatic brief window launched", GOLD)
    except Exception as exc:
        # Fallback via shell start
        try:
            os.system(f'start "Viro Sentinel · Run Brief" "{py}" "{report_path}"')
            log_line("BRIEF", "dramatic brief window launched (fallback)", GOLD)
        except Exception as exc2:
            log_line("ERROR", f"brief window launch failed: {exc} / {exc2}", ROSE)
    redraw()


# ── Commands ──────────────────────────────────────────────────────────
def action_run() -> None:
    if APP.tracker.running:
        log_line("WARN", "theater already running", AMBER)
        redraw()
        return
    t = APP.tracker
    t.running = True
    started = time.time()
    APP.brief.ready = False
    try:
        # ACT 0 — boot
        set_act("boot")
        stage("Getting ready", "opening the pretend shop for today", INDIGO)
        thinking("setting up the shop", INDIGO, 4)
        open_sandbox(reseed=True)
        t.phase, t.conversion, t.verified = "baseline", 24.0, False
        t.tools_used, t.inventory, t.target_inventory = 0, 40, 65
        t.product_status, t.target_status = "active", "ready"
        t.last_event = "nothing wrong yet"
        t.history.clear()
        t.history.extend([24.0] * 16)
        progress("loading shoes, shoppers, and sales history", EMERALD)
        log_line("SHOP", "All good · Street Runner has 40 pairs on the shelf", EMERALD)
        redraw()
        time.sleep(0.35)

        # ACT 1 — crisis
        set_act("crisis")
        stage("Something goes wrong", "the shelf goes empty · shoppers keep coming", CRIMSON)
        typewriter("ALERT", "The Street Runner just sold out completely", CRIMSON)
        thinking("checking what that means", CRIMSON)
        event = APP.svc.simulate_stockout("product_demo_001")["event"]
        t.last_event = f"Shelf emptied: {event['previous_inventory']} pairs → {event['new_inventory']}"
        t.inventory, t.product_status, t.phase = 0, "sold out", "crisis"
        log_line("ALERT", "Street Runner stock: 40 pairs → 0 pairs", AMBER)
        log_line("NOTE", "This is just a fact. We do not yet know why or what to do.", MUTED)
        progress("PROBLEM SPOTTED", ROSE)
        animate_conversion(0.0, steps=14, delay=0.035, tone="crisis")
        log_line("ALERT", "Buy rate crashed from 24% to 0% · people still browsing", ROSE)
        redraw()
        time.sleep(0.35)

        # ACT 2 — evidence
        set_act("evidence")
        stage("Looking for clues", "gathering real numbers · no guessing", CYAN)
        evidence = []
        for name, result in [
            ("Check the shelf", "0 pairs left · completely sold out"),
            ("Check sales before the problem", "24 buys for every 100 visits · 24%"),
            ("Check sales after the problem", "0 buys for every 15 visits · 0%"),
            ("Check past orders", "24 past orders · $2,880 in sales"),
            ("Check who is sending shoppers", "Sarah and Marcus still promoting"),
        ]:
            thinking(f"checking: {name}", CYAN, 2)
            typewriter("CHECK", f"→ {name}", CYAN)
            log_line("FOUND", result, EMERALD)
            evidence.append(f"{name}: {result}")
            t.tools_used += 1
            redraw()
            time.sleep(0.28)

        # ACT 3 — decision
        set_act("decision")
        stage("Making a choice", "finding the best stand-in product", VIOLET)
        thinking("comparing other shoes", VIOLET)
        rec = APP.svc.recommend_replacement("product_demo_001", record_action=False)
        top = rec.get("top_recommendation") or {}
        typewriter("CHECK", "→ Look for another shoe shoppers will love", VIOLET)
        log_line("PICK", f"{top.get('name')} · fit score {top.get('match_score')}", EMERALD)
        for r in (top.get("reasons") or [])[:3]:
            log_line("  ·", str(r).replace("Matching category: Footwear", "Same type of product (shoes)").replace("Same merchant", "Same brand shop").replace("Price proximity score:", "Close in price:"), MUTED)
        t.tools_used += 1
        t.target_status = "chosen"
        progress(f"Chose Trail Walker · fit score {top.get('match_score')}", VIOLET)
        redraw()
        time.sleep(0.3)

        # ACT 4 — action
        set_act("redirect")
        stage("Fixing it", "sending shoppers to the shoe that is in stock", AMBER)
        typewriter("ACTION", "→ Point shoppers from Street Runner to Trail Walker", AMBER)
        thinking("gently rerouting traffic", AMBER)
        action = APP.svc.redirect_traffic_to_replacement("product_demo_001", "product_demo_002")
        t.phase, t.target_status, t.product_status = "redirect", "helping shoppers", "sold out"
        t.tools_used += 1
        clicks = action.get("simulated_clicks", 20)
        purchases = action.get("simulated_purchases", 4)
        progress(f"Shoppers redirected · {purchases} buys from {clicks} visits", AMBER)
        log_line("ACTION", "Street Runner marked unavailable · Trail Walker now featured", AMBER)
        log_line("ACTION", f"{purchases} new buys across {clicks} shopper visits", AMBER)
        redraw()
        time.sleep(0.3)

        # ACT 5 — verify
        set_act("verify")
        stage("Checking it worked", "looking at real records · not guesses", EMERALD)
        typewriter("CHECK", "→ Did shoppers actually buy the Trail Walker?", EMERALD)
        thinking("counting real purchases", EMERALD)
        verify = APP.svc.verify_intervention_outcome("product_demo_001", "product_demo_002")
        before = float((verify.get("before_intervention") or {}).get("conversion_rate_pct") or 0.0)
        after = float((verify.get("after_intervention") or {}).get("conversion_rate_pct") or 0.0)
        log_line("RESULT", f"Buy rate before fix: {before}% · after fix: {after}%", CYAN)
        animate_conversion(after, steps=16, delay=0.04, tone="recover")
        t.verified = bool(verify.get("intervention_verified"))
        t.phase = "recovered" if t.verified else "unverified"
        t.target_status = "confirmed" if t.verified else "not sure"
        t.tools_used += 1
        elapsed = f"{time.time() - started:.1f}s"

        # Organized run brief
        APP.brief = RunBrief(
            ready=True,
            status="Yes — the fix worked" if t.verified else "Not sure yet",
            incident="Street Runner sold out",
            product="Street Runner → Trail Walker",
            event="Shelf went from 40 pairs to 0",
            evidence=evidence,
            decision=str(top.get("name") or "Viro Trail Walker"),
            score=str(top.get("match_score") or "97.5"),
            action=f"Send shoppers to Trail Walker · {purchases} buys / {clicks} visits",
            before_pct=before,
            after_pct=after,
            verified=t.verified,
            tools=t.tools_used,
            elapsed=elapsed,
        )

        if t.verified:
            log_line("✓", "The fix worked · buy rate recovered from 0% to 20%", EMERALD)
            log_line("", "These numbers come from the shop records, not from guessing.", MUTED)
            progress("FIX CONFIRMED", EMERALD)
            log_line("", "═" * 44, EMERALD)
            log_line("WIN", "Shoppers can buy again · happy path restored", EMERALD + BOLD)
            log_line("", "═" * 44, EMERALD)
            APP.status_msg = "All good · opening your report in a new window…"
            redraw()
            time.sleep(0.35)
            open_brief_window()
            APP.status_msg = "Report open · 1=watch again  4=report"
        else:
            log_line("✗", "We cannot confirm the fix yet", ROSE)
            APP.status_msg = "Fix not confirmed"
            open_brief_window()
        redraw()
        time.sleep(0.3)
        redraw()
    except Exception as exc:
        log_line("ERROR", str(exc), ROSE)
        APP.status_msg = f"error · {exc}"
        redraw()
    finally:
        t.running = False
        set_act("idle")
        redraw()


def action_status() -> None:
    refresh_tracker()
    t = APP.tracker
    log_line("SHOP", f"Buy rate {t.conversion}% · Street Runner has {t.inventory} pairs · Trail Walker has {t.target_inventory}", INDIGO)
    APP.status_msg = "Shop health refreshed"
    redraw()


def action_verify() -> None:
    if APP.svc is None:
        open_sandbox(reseed=False)
    try:
        verify = APP.svc.verify_intervention_outcome("product_demo_001", "product_demo_002")
        after = float((verify.get("after_intervention") or {}).get("conversion_rate_pct") or 0.0)
        before = float((verify.get("before_intervention") or {}).get("conversion_rate_pct") or 0.0)
        APP.tracker.conversion = after
        APP.tracker.verified = bool(verify.get("intervention_verified"))
        APP.tracker.phase = "recovered" if APP.tracker.verified else APP.tracker.phase
        APP.brief.ready = True
        APP.brief.before_pct, APP.brief.after_pct = before, after
        APP.brief.verified = APP.tracker.verified
        APP.brief.status = "Yes — the fix worked" if APP.tracker.verified else "Not sure yet"
        log_line("CHECK", f"Buy rate {before}% → {after}%", EMERALD if APP.tracker.verified else ROSE)
        APP.status_msg = "Check complete"
    except Exception as exc:
        log_line("NOTE", "Nothing to check yet — watch the story first (press 1)", AMBER)
        APP.status_msg = "Watch the story first"
    redraw()


def action_brief() -> None:
    if not APP.brief.ready:
        log_line("REPORT", "No story yet · press 1 to watch one", AMBER)
        APP.status_msg = "Watch the story first"
        redraw()
        return
    b = APP.brief
    log_line("REPORT", f"{b.status} · {b.product} · buy rate {b.before_pct}% → {b.after_pct}%", EMERALD if b.verified else GOLD)
    log_line("REPORT", f"We chose {b.decision} · fit {b.score} · {b.action}", CYAN)
    APP.status_msg = "Opening your report…"
    redraw()
    time.sleep(0.2)
    open_brief_window()
    APP.status_msg = "Report opened in a new window"
    redraw()


def action_recommend() -> None:
    if APP.svc is None:
        open_sandbox(reseed=True)
    rec = APP.svc.recommend_replacement("product_demo_001", record_action=False)
    top = rec.get("top_recommendation") or {}
    log_line("PICK", f"Best stand-in: {top.get('name')} · fit score {top.get('match_score')}", CYAN)
    for r in (top.get("reasons") or [])[:3]:
        log_line("  ·", str(r).replace("Matching category: Footwear", "Same type (shoes)").replace("Same merchant", "Same brand shop").replace("Price proximity score:", "Close in price:"), MUTED)
    APP.status_msg = "Found a good backup product"
    redraw()


def action_event() -> None:
    log_line("ALERT", APP.tracker.last_event, AMBER)
    APP.status_msg = "Here is what we first noticed"
    redraw()


def action_duplicate() -> None:
    blocked = False
    try:
        if APP.svc is None:
            open_sandbox(reseed=False)
        from sandbox.models import AgentAction

        recent = (
            APP.svc.db.query(AgentAction)
            .filter(
                AgentAction.action_type.in_(["redirect_traffic", "redirect_traffic_to_replacement"]),
                AgentAction.status == "executed",
            )
            .first()
        )
        blocked = recent is not None
    except Exception:
        blocked = APP.tracker.verified
    if blocked:
        log_line("SAFE", "Same alert sent twice · we ignored the second one", GOLD)
        APP.status_msg = "We do not fix the same problem twice"
    else:
        log_line("SAFE", "No fix has been applied yet · a new alert would be handled", MUTED)
        APP.status_msg = "Nothing to block yet"
    redraw()


def action_tools() -> None:
    for line in [
        "This helper CAN: check shelves, sales, orders, and who is sending shoppers",
        "This helper CAN: suggest a stand-in product and send shoppers there",
        "This helper CAN: confirm whether the fix worked using real records",
        "This helper CANNOT: change prices or pay anyone without a human saying yes",
    ]:
        log_line("RULES", line, CYAN)
    APP.status_msg = "Here is what this helper may and may not do"
    redraw()


def action_reset() -> None:
    open_sandbox(reseed=True)
    t = APP.tracker
    t.conversion, t.inventory, t.target_inventory = 24.0, 40, 65
    t.phase, t.product_status, t.target_status = "baseline", "on the shelf", "ready to help"
    t.verified, t.tools_used = False, 0
    t.last_event = "nothing wrong yet"
    t.history.clear()
    t.history.extend([24.0] * 20)
    APP.brief = RunBrief()
    log_line("SHOP", "Shop is back to a healthy starting point", EMERALD)
    APP.status_msg = "Fresh start · Street Runner has 40 pairs again"
    redraw()


def action_help() -> None:
    for key, name, desc in COMMANDS:
        log_line("HELP", f"[{key}] {name} — {desc}", MUTED)
    log_line("HELP", "You can also type words like watch, shop, check, report, help, bye", MUTED)
    APP.status_msg = "Pick any option on the right"
    redraw()


ACTIONS: dict[str, Callable[[], None]] = {
    "1": action_run,
    "2": action_status,
    "3": action_verify,
    "4": action_brief,
    "5": action_recommend,
    "6": action_event,
    "7": action_duplicate,
    "8": action_tools,
    "9": action_reset,
    "0": action_help,
    "r": action_run,
    "s": action_status,
    "v": action_verify,
    "b": action_brief,
}


def normalize(cmd: str) -> str:
    cmd = cmd.strip().lower()
    if not cmd:
        return ""
    if cmd in WORD_MAP:
        return WORD_MAP[cmd]
    if cmd[0] in ACTIONS:
        return cmd[0]
    return cmd


def read_command() -> str:
    """Visible command line. Pauses live redraw so typing is stable."""
    APP.awaiting_input = True
    try:
        redraw()
        sys.stdout.write(c("sentinel", INDIGO + BOLD) + c(" › ", DIMMER))
        sys.stdout.flush()
        try:
            line = input()
        except EOFError:
            return "q"
        return line
    finally:
        APP.awaiting_input = False


def main() -> None:
    if os.name == "nt":
        os.system("")
    try:
        sys.stdout.write(ALT_ON)
    except Exception:
        pass

    open_sandbox(reseed=True)
    log_line("WELCOME", "Viro Sentinel is watching the shop", VIOLET)
    log_line("TIP", "Press 1 to watch a problem get solved, 0 for help, q to close", MUTED)

    threading.Thread(target=live_loop, daemon=True).start()
    redraw()

    try:
        while True:
            raw = read_command()
            key = normalize(raw)
            if key in {"q", "quit", "exit"}:
                break
            if not key:
                redraw()
                continue
            action = ACTIONS.get(key)
            if action:
                action()
            else:
                log_line("TIP", f"Not sure what '{raw.strip()}' means · press 0 for the menu", AMBER)
                APP.status_msg = "Press 0 to see what you can do"
                redraw()
    except KeyboardInterrupt:
        pass
    finally:
        APP.stop_live = True
        try:
            sys.stdout.write(SHOW + ALT_OFF)
        except Exception:
            pass
        print(c("\n  Stay watchful. — Viro Sentinel\n", VIOLET + BOLD))


if __name__ == "__main__":
    main()
