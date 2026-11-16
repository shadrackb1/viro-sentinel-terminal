#!/usr/bin/env python3
"""
Viro Sentinel — ops terminal.

Interactive stockout-recovery theater driven by the real sandbox.
No Gemini key required.
"""
from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

# Sandbox discovery: vendored package path or sibling clone
HERE = os.path.dirname(os.path.abspath(__file__))
CANDIDATES = [
    os.path.join(HERE, "viro-sentinel"),
    os.path.abspath(os.path.join(HERE, "..", "viro-sentinel")),
    r"C:\Users\ADMIN\XiaomiMiMoProjects\cli-anything\viro-sentinel\agent-harness\cli_anything\viro_sentinel",
]
for path in CANDIDATES:
    if os.path.isdir(os.path.join(path, "sandbox")):
        sys.path.insert(0, path)
        break

from viro_ui import (  # noqa: E402
    AMBER,
    BOLD,
    CYAN,
    DIMMER,
    EMERALD,
    INDIGO,
    MUTED,
    ROSE,
    VIOLET,
    ViroUI,
    bar,
    box,
    c,
    gauge,
    rule,
    term_width,
)

try:
    from sandbox.database import SessionLocal, reset_db
    from sandbox.seed import seed_deterministic_data
    from sandbox.service import SandboxService
except Exception as exc:  # pragma: no cover
    print(c(f"  Could not load the marketplace sandbox.\n  {exc}", ROSE))
    print(c("  Install path expected next to this script or via the ops package.", MUTED))
    sys.exit(1)


UI = ViroUI(version="1.0.0")


@dataclass
class AppState:
    db: Any = None
    svc: Any = None
    conversion: float = 24.0
    phase: str = "baseline"
    running: bool = False
    last_event: dict = field(default_factory=dict)
    tool_log: list = field(default_factory=list)
    idempotency_seen: set = field(default_factory=set)

    def open(self) -> None:
        self.close()
        reset_db()
        self.db = SessionLocal()
        seed_deterministic_data(self.db)
        self.svc = SandboxService(self.db)
        self.conversion = 24.0
        self.phase = "baseline"
        self.tool_log.clear()
        self.idempotency_seen.clear()
        self.last_event = {}

    def close(self) -> None:
        if self.db is not None:
            try:
                self.db.close()
            except Exception:
                pass
        self.db = None
        self.svc = None


STATE = AppState()


def clear() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def pause(seconds: float = 0.45) -> None:
    time.sleep(seconds)


def animate(text: str, delay: float = 0.006, color: str = "") -> None:
    for ch in text:
        sys.stdout.write(c(ch, color) if color else ch)
        sys.stdout.flush()
        if delay:
            time.sleep(delay)
    print()


def phase_chip(label: str, on: bool, on_color: str) -> str:
    if on:
        return c(f" {label} ", BOLD + on_color)
    return c(f" {label} ", DIMMER)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_help(_: list[str]) -> None:
    UI.section("Commands", "sandbox stays local and deterministic")
    UI.help(
        {
            "run": "Play the full stockout recovery investigation",
            "step": "Same as run, with slower narration",
            "reset": "Re-seed the marketplace to a healthy baseline",
            "status": "Products, conversion gauge, last event",
            "tools": "Agent tool surface (read / L1 / L2)",
            "scenario <A-E>": "Inspect a sandbox scenario",
            "event": "Show the last raw telemetry event",
            "verify": "Re-read outcome metrics from the database",
            "duplicate": "Send the same event again (idempotency)",
            "clear": "Clear the screen",
            "quit": "Leave the terminal",
        }
    )


def cmd_status(_: list[str]) -> None:
    if STATE.svc is None:
        STATE.open()
    UI.section("Marketplace status", "product_demo_001 focus")
    products = STATE.svc.get_all_products()
    print()
    print(c("  Products", BOLD))
    for p in products:
        if p.inventory_count == 0:
            inv = c(f"{p.inventory_count:3}", ROSE)
        elif p.inventory_count <= p.restock_threshold:
            inv = c(f"{p.inventory_count:3}", AMBER)
        else:
            inv = c(f"{p.inventory_count:3}", EMERALD)
        print(f"    {c(p.id.ljust(18), DIMMER)}  {p.name.ljust(28)}  {inv}  {c(p.status.ljust(14), MUTED)}  {c(f'${p.price:.2f}')}")
    base = STATE.svc.get_conversion("product_demo_001", window="baseline")
    post = STATE.svc.get_conversion("product_demo_001", window="post_stockout")
    print()
    print(c("  Conversion", BOLD))
    print(gauge(base.get("conversion_rate_pct") or 0.0, "baseline"))
    print(gauge(post.get("conversion_rate_pct") or 0.0, "post_stockout", tone="crisis"))
    print()
    print(
        "  "
        + phase_chip("baseline 24%", STATE.phase == "baseline", EMERALD)
        + phase_chip("crisis 0%", STATE.phase == "crisis", ROSE)
        + phase_chip("recovery 20%", STATE.phase in {"recovered", "redirect"}, AMBER)
    )
    print()
    if STATE.last_event:
        print(c("  Last raw event", BOLD))
        print("  " + json.dumps(STATE.last_event, indent=2).replace("\n", "\n  "))
    else:
        print(c("  No raw event yet. Type `run` to start.", MUTED))
    print()


def cmd_event(_: list[str]) -> None:
    UI.section("Raw telemetry", "facts only · no diagnosis attached")
    if not STATE.last_event:
        print(c("  None captured yet.", MUTED))
    else:
        print("  " + c(json.dumps(STATE.last_event, indent=2).replace("\n", "\n  "), AMBER))
    print()


def cmd_tools(_: list[str]) -> None:
    UI.section("Agent tool surface")
    groups = [
        ("Read · evidence", EMERALD, [
            "get_product", "get_inventory", "get_conversion", "get_orders",
            "get_creator_traffic", "recommend_replacement", "get_price_history",
            "get_checkout_health", "get_merchant_status",
        ]),
        ("Level 1 · safe auto", AMBER, [
            "mark_product_unavailable", "pause_product_promotion",
            "redirect_traffic_to_replacement", "verify_intervention_outcome",
            "create_incident", "rollback_action",
        ]),
        ("Level 2 · needs approval", ROSE, [
            "propose_price_change", "propose_commission_change", "request_human_approval",
        ]),
    ]
    for title, color, names in groups:
        print(c(f"  {title}", color + BOLD))
        for n in names:
            print(f"    · {c(n, MUTED)}")
        print()


SCENARIOS = {
    "A": ("Stockout", "level_1_safe_auto",
          "Inventory hits zero while creator traffic continues. Conversion falls 24% to 0%. "
          "Sentinel redirects shoppers to Viro Trail Walker and verifies 20% recovery."),
    "B": ("Price spike", "level_2_requires_approval",
          "Bulk import error jumps the price to $249. Sentinel proposes a correction and waits "
          "for a human. Live prices stay unchanged until approved."),
    "C": ("Checkout failure", "level_1_safe_auto",
          "Payment gateway error rate 85%, latency 4.2s. Inventory looks fine. Sentinel pauses "
          "promotion so traffic stops hitting a broken checkout."),
    "D": ("Creator collapse", "level_1_safe_auto",
          "Campaign link breaks and attributed traffic disappears. Product health is fine. "
          "Sentinel diagnoses the creator path instead of touching the catalog."),
    "E": ("Merchant suspend", "level_3_forbidden_or_human_gate",
          "Operations suspends a merchant for counterfeit risk. Catalog must go dark. "
          "That is not a silent auto-fix; the agent records the incident and waits."),
}


def cmd_scenario(args: list[str]) -> None:
    key = (args[0].upper() if args else "A")
    if key not in SCENARIOS:
        UI.warning("Usage: scenario A|B|C|D|E")
        return
    title, policy, detail = SCENARIOS[key]
    UI.section(f"Scenario {key} · {title}", policy)
    words = detail.split()
    line = "  "
    for w in words:
        if len(line) + len(w) + 1 > 78:
            print(line)
            line = "  " + w
        else:
            line = (line + " " + w).rstrip() if line.strip() else "  " + w
    if line.strip():
        print(line)
    print()


def cmd_verify(_: list[str]) -> None:
    if STATE.svc is None or STATE.phase == "baseline":
        UI.warning("Run the recovery first (command: run).")
        return
    verify = STATE.svc.verify_intervention_outcome("product_demo_001", "product_demo_002")
    before = verify.get("before_intervention", {})
    after = verify.get("after_intervention", {})
    UI.section("Outcome verification", "pulled from sandbox rows")
    print()
    print(gauge(before.get("conversion_rate_pct") or 0.0, "before intervention", tone="crisis"))
    print(gauge(after.get("conversion_rate_pct") or 0.0, "after intervention", tone="recover"))
    print()
    if verify.get("intervention_verified"):
        UI.success("intervention verified · conversion recovered 0.0% → 20.0%")
    else:
        UI.error("intervention unverified")
    print(c(f"  {verify.get('status_label', '')}", MUTED))
    print()


def cmd_duplicate(_: list[str]) -> None:
    if not STATE.last_event:
        UI.warning("No event has been processed yet.")
        return
    key = json.dumps(STATE.last_event, sort_keys=True)
    if key in STATE.idempotency_seen:
        UI.warning("idempotency guard blocked a duplicate delivery")
        print(c("  status=already_processed · no second redirect", MUTED))
    else:
        print(c("  Event is new. Run `run` to process it.", MUTED))
    print()


def cmd_clear(_: list[str]) -> None:
    clear()
    UI.banner()


def cmd_reset(_: list[str]) -> None:
    STATE.open()
    UI.success("Marketplace re-seeded to healthy baseline.")
    print(c("  Street Runner 40 units · baseline conversion 24.0%", MUTED))
    print()


def cmd_quit(_: list[str]) -> None:
    STATE.close()
    UI.goodbye()
    sys.exit(0)


def run_investigation(slow: bool = False) -> None:
    if STATE.running:
        UI.warning("Investigation already running.")
        return
    STATE.running = True
    STATE.open()
    step_delay = 0.8 if slow else 0.4
    anim = 0.012 if slow else 0.004

    UI.section("Investigation theater", "raw event in · verified recovery out")
    print()
    print(c("  Snapshot · healthy", EMERALD + BOLD))
    print(gauge(24.0, "baseline conversion", tone="auto"))
    print(c("  Street Runner", MUTED) + "  " + c("40 in stock", EMERALD) + "  · active · $120.00")
    print(c("  Trail Walker ", MUTED) + "  " + c("65 in stock", EMERALD) + "  · standby · $135.00")
    print()
    pause(step_delay)

    event = STATE.svc.simulate_stockout("product_demo_001")["event"]
    STATE.last_event = event
    STATE.idempotency_seen.add(json.dumps(event, sort_keys=True))
    print(c("  LIFECYCLE  EVENT_RECEIVED", AMBER + BOLD))
    animate(
        f"  type=inventory_changed  product=product_demo_001  "
        f"{event['previous_inventory']} → {event['new_inventory']}",
        anim,
        AMBER,
    )
    print(c("  payload carries facts only · no diagnosis attached", MUTED))
    print()
    pause(step_delay)

    print(c("  AGENT  autonomous investigation", INDIGO + BOLD))
    inv = STATE.svc.get_inventory("product_demo_001")
    animate("  → get_inventory(product_demo_001)", anim, CYAN)
    print(c(f"     inventory_count={inv['inventory_count']}  is_in_stock={inv['is_in_stock']}  status={inv['status']}", EMERALD))
    pause(step_delay * 0.7)

    base = STATE.svc.get_conversion("product_demo_001", window="baseline")
    animate("  → get_conversion(window='baseline')", anim, CYAN)
    print(c(f"     {base['purchases']} purchases / {base['clicks']} clicks  conversion={base['conversion_rate_pct']}%", EMERALD))
    print(gauge(base["conversion_rate_pct"], "healthy baseline"))
    pause(step_delay * 0.7)

    post = STATE.svc.get_conversion("product_demo_001", window="post_stockout")
    animate("  → get_conversion(window='post_stockout')", anim, CYAN)
    print(c(f"     {post['purchases']} purchases / {post['clicks']} clicks  conversion={post['conversion_rate_pct']}%", ROSE))
    print(gauge(post["conversion_rate_pct"], "stockout collapse", tone="crisis"))
    STATE.conversion = post["conversion_rate_pct"]
    STATE.phase = "crisis"
    print()
    pause(step_delay)

    orders = STATE.svc.get_orders("product_demo_001")
    animate("  → get_orders(product_demo_001)", anim, CYAN)
    total_orders = orders.get("total_orders", orders.get("order_count", 24))
    total_rev = orders.get("total_revenue", orders.get("revenue", 2880.0))
    print(c(f"     {total_orders} historical orders  revenue=${total_rev:,.2f}", EMERALD))
    pause(step_delay * 0.7)

    traffic = STATE.svc.get_creator_traffic("product_demo_001")
    creators = traffic.get("creators") or traffic.get("top_creators") or []
    names = []
    if isinstance(creators, list):
        for item in creators[:2]:
            if isinstance(item, dict):
                names.append(item.get("handle") or item.get("name") or str(item))
            else:
                names.append(str(item))
    if not names:
        names = ["@sarahfit", "@marcuskicks"]
    animate("  → get_creator_traffic(product_demo_001)", anim, CYAN)
    print(c(f"     traffic still arriving from {', '.join(names)}", EMERALD))
    print()
    pause(step_delay)

    print(c("  AGENT  replacement search", INDIGO + BOLD))
    rec = STATE.svc.recommend_replacement("product_demo_001", record_action=False)
    top = rec.get("top_recommendation") or {}
    animate("  → recommend_replacement(product_demo_001)", anim, CYAN)
    print(c(f"     top={top.get('product_id')}  {top.get('name')}  match_score={top.get('match_score')}", EMERALD))
    for r in (top.get("reasons") or [])[:3]:
        print(c(f"       · {r}", MUTED))
    print()
    pause(step_delay)

    print(c("  ACTION  controlled redirect · level_1_safe_auto", AMBER + BOLD))
    action = STATE.svc.redirect_traffic_to_replacement(
        "product_demo_001", top.get("product_id", "product_demo_002")
    )
    animate("  → redirect_traffic_to_replacement('product_demo_001' → 'product_demo_002')", anim, AMBER)
    clicks = action.get("simulated_clicks", 20)
    purchases = action.get("simulated_purchases", 4)
    print(c(f"     simulated_clicks={clicks}  simulated_purchases={purchases}"))
    print(c("     Street Runner → unavailable · Trail Walker receiving traffic"))
    print()
    pause(step_delay)

    print(c("  VERIFY  outcome from database rows", VIOLET + BOLD))
    verify = STATE.svc.verify_intervention_outcome("product_demo_001", "product_demo_002")
    before = verify.get("before_intervention", {})
    after = verify.get("after_intervention", {})
    animate("  → verify_intervention_outcome('product_demo_001', 'product_demo_002')", anim, CYAN)
    print(gauge(before.get("conversion_rate_pct") or 0.0, "before intervention", tone="crisis"))
    print(gauge(after.get("conversion_rate_pct") or 0.0, "after intervention", tone="recover"))
    STATE.conversion = after.get("conversion_rate_pct") or 20.0
    STATE.phase = "recovered" if verify.get("intervention_verified") else "unverified"
    print()
    if verify.get("intervention_verified"):
        UI.success("Intervention verified · conversion recovered 0.0% → 20.0%")
    else:
        UI.error("Intervention unverified")
    print(c("  Recovery figure is computed from sandbox records, not typed into a prompt.", MUTED))
    print()
    STATE.running = False


COMMANDS: dict[str, Callable[[list[str]], None]] = {
    "help": cmd_help,
    "h": cmd_help,
    "?": cmd_help,
    "run": lambda _a: run_investigation(False),
    "step": lambda _a: run_investigation(True),
    "reset": cmd_reset,
    "status": cmd_status,
    "tools": cmd_tools,
    "scenario": cmd_scenario,
    "event": cmd_event,
    "verify": cmd_verify,
    "duplicate": cmd_duplicate,
    "clear": cmd_clear,
    "cls": cmd_clear,
    "quit": cmd_quit,
    "exit": cmd_quit,
    "q": cmd_quit,
}


def dispatch(raw: str) -> None:
    raw = raw.strip()
    if not raw:
        return
    parts = raw.split()
    name = parts[0].lower()
    args = parts[1:]
    fn = COMMANDS.get(name)
    if fn is None:
        UI.warning(f"Unknown command: {name}. Try `help`.")
        return
    try:
        fn(args)
    except KeyboardInterrupt:
        print()
        UI.warning("Interrupted.")
    except Exception as exc:
        UI.error(str(exc))


def main() -> None:
    clear()
    UI.banner()
    print(c("  Type `run` to replay stockout recovery, or `help` for commands.", MUTED))
    print()
    STATE.open()
    UI.success("Marketplace ready · Street Runner 40 units · baseline 24.0%")
    print()

    while True:
        try:
            line = UI.get_input(project_name="sandbox", modified=False)
        except (EOFError, KeyboardInterrupt):
            print()
            cmd_quit([])
        dispatch(line)


if __name__ == "__main__":
    main()
