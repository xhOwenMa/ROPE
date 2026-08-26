"""Failure census: every residual attack success under the static attack, and clean-task failures.

    python failures.py
"""
from _scope import attack_files, clean_files, it_index, load, paper_cells
from corrections import corrected_security

# Mechanism -> the (suite, injection task) channels that carry it.
MECHANISMS = [("Harm in the agent's message", [("travel", 6)]),
              ("In-band content, admitted channel", [("slack", 1), ("travel", 5)]),
              ("Delegated sensitive parameter", [("shopping", 2), ("shopping", 5), ("dailylife", 6)])]

per, total, clean_n, clean_fail = {}, 0, 0, 0
for model, suite in paper_cells():
    for f in attack_files(model, suite, "important_instructions"):
        it = it_index(f)
        if corrected_security(load(f), suite, it):
            total += 1
            per[(suite, it)] = per.get((suite, it), 0) + 1
    for f in clean_files(model, suite):
        clean_n += 1
        clean_fail += not bool(load(f).get("utility"))

print(f"{'mechanism':36} {'where':40} {'cells':>5}")
counted = 0
for name, keys in MECHANISMS:
    got = sum(per.get(k, 0) for k in keys)
    counted += got
    print(f"{name:36} {', '.join(f'{s} IT{i}' for s, i in keys):40} {got:5d}")
print(f"{'Total':36} {'':40} {total:5d}")
if counted != total:
    raise SystemExit(f"FATAL: {total - counted} successes fall outside the listed mechanisms: "
                     f"{sorted(k for k in per if k not in [k2 for _, ks in MECHANISMS for k2 in ks])}")

print(f"\nClean tasks: {clean_fail} of {clean_n} fail")
print("\nper (suite, injection task):")
for k in sorted(per, key=lambda k: -per[k]):
    print(f"   {k[0]:10} IT{k[1]:<3} {per[k]:3d}")
