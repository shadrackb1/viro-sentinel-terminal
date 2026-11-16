# -*- coding: utf-8 -*-
# Auto-generated dramatic run brief for Viro Sentinel
import json, os, sys, time
os.system('')
data = json.loads('{"status": "intervention verified", "incident": "stockout \\u00b7 product_demo_001", "product": "Street Runner \\u2192 Trail Walker", "event": "inventory_changed 40\\u21920", "evidence": ["get_inventory: count=0 \\u00b7 is_in_stock=false \\u00b7 out_of_stock", "get_conversion(baseline): 24 purchases / 100 clicks \\u00b7 24.0%", "get_conversion(post_stockout): 0 purchases / 15 clicks \\u00b7 0.0%", "get_orders: 24 orders \\u00b7 revenue=$2,880.00", "get_creator_traffic: @sarahfit + @marcuskicks \\u00b7 traffic hot"], "decision": "Viro Trail Walker", "score": "97.5", "action": "redirect \\u00b7 4/20 clicks", "before_pct": 0.0, "after_pct": 20.0, "formula": "purchases / clicks", "verified": true, "policy": "level_1_safe_auto", "tools": 8, "elapsed": "15.9s"}')
R, B = '\033[0m', '\033[1m'
INK, MUT, DIM = '\033[38;5;255m', '\033[38;5;245m', '\033[38;5;240m'
IND, AMB, EME = '\033[38;5;111m', '\033[38;5;214m', '\033[38;5;78m'
ROS, CYN, VIO = '\033[38;5;203m', '\033[38;5;80m', '\033[38;5;141m'
GLD = '\033[38;5;220m'
def p(text='', *codes):
    print((''.join(codes) + text + R) if codes else text)
def rule(ch='═', n=64, color=DIM):
    p(ch * n, color)
def row(label, value, color=INK):
    p('  │  ' + str(label).ljust(22) + str(value), color)
def typewrite(text, delay=0.012, *codes):
    for ch in text:
        sys.stdout.write((''.join(codes) + ch + R) if codes else ch)
        sys.stdout.flush()
        time.sleep(delay)
    print()
def bar(value, maximum=40.0, width=28):
    value = max(0.0, min(maximum, float(value)))
    filled = int(round(value / maximum * width))
    col = ROS if value <= 1 else (GLD if value >= 20 else EME)
    return '█' * filled + '░' * (width - filled), col
print()
rule()
p('   ◆  RUN COMPLETE  ·  POST-MISSION BRIEF', IND + B)
rule()
print()
typewrite('   Organizing verified sandbox data', 0.025, MUT)
time.sleep(0.35)
print()
before = float(data['before_pct'])
after = float(data['after_pct'])
bfill, bcol = bar(before)
afill, acol = bar(after)
p('   BEFORE INTERVENTION', ROS + B)
p('   ' + bcol + bfill + R + '  ' + format(before, '5.1f') + '%')
p('   AFTER INTERVENTION', EME + B)
p('   ' + acol + afill + R + '  ' + format(after, '5.1f') + '%')
print()
p('   Δ  {:+.1f} pts   formula: {}'.format(after - before, data['formula']), GLD + B)
print()
rule('─', 64, DIM)
p('   ┌─────────────────────────────────────────────────────────────┐', IND)
p('   │  INCIDENT & DECISION', IND + B)
p('   └─────────────────────────────────────────────────────────────┘', IND)
row('incident', data['incident'])
row('product', data['product'])
row('raw event', data['event'], AMB)
row('decision', data['decision'], CYN)
row('match score', data['score'], EME)
row('action', data['action'], AMB)
print()
p('   ┌─────────────────────────────────────────────────────────────┐', CYN)
p('   │  EVIDENCE TRAIL', CYN + B)
p('   └─────────────────────────────────────────────────────────────┘', CYN)
for i, ev in enumerate(data.get('evidence') or [], 1):
    typewrite('   %02d  %s' % (i, ev), 0.008, CYN)
print()
p('   ┌─────────────────────────────────────────────────────────────┐', VIO)
p('   │  GOVERNANCE', VIO + B)
p('   └─────────────────────────────────────────────────────────────┘', VIO)
row('policy', data['policy'])
row('tools used', data['tools'])
row('elapsed', data['elapsed'])
row('verified', 'YES · database rows' if data['verified'] else 'NO', EME if data['verified'] else ROS)
print()
rule()
if data['verified']:
    p('   ✓  INTERVENTION VERIFIED', EME + B)
    p('   Recovery is computed from sandbox records, not invented.', MUT)
else:
    p('   ✗  VERIFICATION INCOMPLETE', ROS + B)
rule()
print()
p('   Close this window when you are done reviewing.', DIM)
print()
os.system('pause')
