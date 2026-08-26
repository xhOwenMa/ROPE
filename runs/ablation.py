"""Policy ablation: the per-task router replaced by two fixed policies.

    python ablation.py
"""
from _scope import attack_files, clean_files, it_index, load, rate
from corrections import corrected_security

SUITES = ["shopping", "github", "dailylife"]
POLICIES = ["always-fully-specified", "always-action-open"]


def agg(policy, suite):
    tree = f"ablation/{policy}"
    clean = clean_files(tree, suite)
    attacked = attack_files(tree, suite, "important_instructions")
    if not clean or not attacked:
        raise SystemExit(f"FATAL: missing ablation runs for {policy}/{suite}")
    ua, sec = [], []
    for f in attacked:
        d = load(f)
        ua.append(bool(d.get("utility")))
        sec.append(corrected_security(d, suite, it_index(f)))
    return rate([bool(load(f).get("utility")) for f in clean]), rate(ua), rate(sec)


print(f"{'suite':11} {'policy':24} {'CU':>6} {'UA':>6} {'ASR':>6}")
totals = {p: [] for p in POLICIES}
for suite in SUITES:
    for p in POLICIES:
        r = agg(p, suite)
        totals[p].append(r)
        print(f"{suite:11} {p:24} {r[0]:6.1f} {r[1]:6.1f} {r[2]:6.1f}")
    print()
for p in POLICIES:
    rs = totals[p]
    print(f"{'OVERALL':11} {p:24} " + " ".join(f"{sum(r[i] for r in rs) / 3:6.1f}" for i in range(3)))
