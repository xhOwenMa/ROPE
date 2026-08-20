"""AutoDojo (adaptive) vs important_instructions (static) ASR for ROPE on the AgentDyn suites.

    python adaptive_rope.py     (from runs/)
"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from corrections import corrected_security

SUITES = ["github", "shopping", "dailylife"]
MODELS = ["gpt-4o-mini", "gemini-2.5-flash", "qwen3-235b"]  # gpt-4o has no adaptive arm

# Published ROPE cells: (model, suite) -> (static ASR, adaptive ASR). The recompute must match.
PUBLISHED = {
    ("gpt-4o-mini", "github"): (0.0, 0.0), ("gpt-4o-mini", "shopping"): (4.4, 4.4),
    ("gpt-4o-mini", "dailylife"): (1.0, 0.5),
    ("qwen3-235b", "github"): (0.0, 0.0), ("qwen3-235b", "shopping"): (7.2, 7.2),
    ("qwen3-235b", "dailylife"): (0.5, 0.5),
}


def _it(f):
    return int(f.rsplit("injection_task_", 1)[1].split(".json")[0])


def asr(model, suite, attack):
    fs = sorted(glob.glob(f"{HERE}/{model}/{suite}/user_task_*/{attack}/injection_task_*.json"))
    if not fs:
        return None, 0
    ds = [(json.load(open(f)), _it(f)) for f in fs]
    return 100 * sum(corrected_security(d, suite, i) for d, i in ds) / len(ds), len(ds)


mismatches = []
print(f"{'agent':17} {'suite':10} {'static':>7} {'adaptive':>9}  {'n_static':>8} {'n_adapt':>8}")
print("-" * 60)
for model in MODELS:
    st_all, ad_all = [], []
    for s in SUITES:
        st, nst = asr(model, s, "important_instructions")
        ad, nad = asr(model, s, "autodojo")
        print(f"{model:17} {s:10} {st:7.1f} {ad:9.1f}  {nst:8d} {nad:8d}")
        st_all.append(st); ad_all.append(ad)
        exp = PUBLISHED.get((model, s))
        if exp is not None:
            for got, want, which in ((st, exp[0], "static"), (ad, exp[1], "adaptive")):
                if got is None or abs(got - want) > 0.05:
                    mismatches.append(f"{model}/{s}/{which}: got {got}, published {want}")
    print(f"{model:17} {'OVERALL':10} {sum(st_all)/3:7.1f} {sum(ad_all)/3:9.1f}   (unweighted suite mean)")
    print()

if mismatches:
    raise SystemExit("FATAL: cross-check against published cells FAILED:\n  " + "\n  ".join(mismatches))
print("cross-check vs published ROPE cells: PASS")
