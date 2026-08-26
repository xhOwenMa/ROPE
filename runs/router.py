"""Cheaper-router comparison, with and without the enforcement clamp.

    python router.py

Only the router varies. "opus" is the main result tree; the other two have their own trees, each
with a clamped arm. Cells with no clamped run print "--".
"""
import os

from _scope import HERE, attack_files, clean_files, it_index, load, rate
from corrections import corrected_security

SUITES = ["github", "shopping", "dailylife"]
# label -> (unclamped tree, clamped tree or None)
ROUTERS = {"Opus 4.8": ("gpt-4o-mini", None),
           "Gemini-3-Flash": ("router/gemini-3-flash", "router/gemini-3-flash-clamp"),
           "gpt-oss-20b": ("router/gpt-oss-20b", "router/gpt-oss-20b-clamp")}


def agg(tree, suite):
    clean = clean_files(tree, suite)
    attacked = attack_files(tree, suite, "important_instructions")
    if not clean or not attacked:
        return None
    sec = [corrected_security(load(f), suite, it_index(f)) for f in attacked]
    return rate([bool(load(f).get("utility")) for f in clean]), rate(sec)


print(f"{'suite':11} {'router':16} {'CU':>6} {'ASR':>6} {'+clamp':>7}")
totals = {r: [[], []] for r in ROUTERS}
for suite in SUITES:
    for label, (tree, ctree) in ROUTERS.items():
        r = agg(tree, suite)
        if r is None:
            raise SystemExit(f"FATAL: missing runs for {label}/{suite} ({tree})")
        clamped = agg(ctree, suite) if ctree and os.path.isdir(f"{HERE}/{ctree}/{suite}") else None
        totals[label][0].append(r[0])
        totals[label][1].append(r[1])
        cs = f"{clamped[1]:7.1f}" if clamped else f"{'--':>7}"
        print(f"{suite:11} {label:16} {r[0]:6.1f} {r[1]:6.1f} {cs}")
    print()
print(f"{'OVERALL':11}")
for label, (cus, asrs) in totals.items():
    print(f"{'':11} {label:16} {sum(cus) / 3:6.1f} {sum(asrs) / 3:6.1f}")
