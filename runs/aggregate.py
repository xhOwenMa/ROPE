"""CU / UA / ASR per suite, plus the unweighted suite mean per benchmark.

    python aggregate.py [model ...]

ASR goes through the effect-based corrections in corrections.py; CU and UA are untouched.
"""
import sys

from _scope import (AGENTDOJO, AGENTDYN, DYN_MODELS, attack_files, clean_files,
                    it_index, load, rate)
from corrections import corrected_security


def agg(model, suite):
    clean = clean_files(model, suite)
    attacked = attack_files(model, suite, "important_instructions")
    if not clean or not attacked:
        return None
    ua, sec = [], []
    for f in attacked:
        d = load(f)
        ua.append(bool(d.get("utility")))
        sec.append(corrected_security(d, suite, it_index(f)))
    return rate([bool(load(f).get("utility")) for f in clean]), rate(ua), rate(sec), len(clean), len(attacked)


def report(model):
    print(f"==== {model} ====")
    print(f"{'suite':10} {'CU':>6} {'UA':>6} {'ASR':>6} {'n_clean':>8} {'n_attacked':>11}")
    for suite in AGENTDYN + AGENTDOJO:
        r = agg(model, suite)
        if r is None:
            continue
        print(f"{suite:10} {r[0]:6.1f} {r[1]:6.1f} {r[2]:6.1f} {r[3]:8d} {r[4]:11d}")
    for group, suites in [("AgentDyn", AGENTDYN), ("AgentDojo", AGENTDOJO)]:
        rs = [agg(model, s) for s in suites]
        if any(r is None for r in rs):
            continue
        print(f"  {group} Overall: CU {sum(r[0] for r in rs) / 3:.1f}  "
              f"UA {sum(r[1] for r in rs) / 3:.1f}  ASR {sum(r[2] for r in rs) / 3:.1f}")
    print()


for m in sys.argv[1:] or DYN_MODELS:
    report(m)
