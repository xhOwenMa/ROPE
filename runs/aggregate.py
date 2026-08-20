"""Aggregate the runs/<model>/<suite> trees -> CU/UA/ASR per suite + AgentDyn/AgentDojo overall
(unweighted suite mean).

Usage:
    python aggregate.py                 # every model that has a run dir here
    python aggregate.py gpt-4o          # just one model
A model is summarised only over the suites it actually has (e.g. gpt-4o = AgentDyn suites only).
"""
import json, glob, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
AGENTDYN = ["github", "shopping", "dailylife"]
AGENTDOJO = ["banking", "slack", "travel"]

from corrections import corrected_security   # dispatcher: slack-IT5 / dailylife-IT7 / github-IT1 effect corrections

def _it_index(fpath):
    return int(fpath.rsplit("injection_task_", 1)[1].split(".json")[0])

def agg(model, suite):
    # ASR goes through the shared effect-based correction dispatcher, so every reported ASR here is
    # already effect-corrected (no raw/effect ambiguity). CU/UA are unaffected.
    base = f"{HERE}/{model}/{suite}"
    cl = sorted(glob.glob(f"{base}/user_task_*/none/none.json"))
    at = sorted(glob.glob(f"{base}/user_task_*/important_instructions/injection_task_*.json"))
    if not cl or not at:
        return None
    cu = [bool(json.load(open(f)).get("utility")) for f in cl]
    ua, sec = [], []
    for f in at:
        d = json.load(open(f))
        ua.append(bool(d.get("utility"))); sec.append(corrected_security(d, suite, _it_index(f)))
    return (100*sum(cu)/len(cu), 100*sum(ua)/len(ua), 100*sum(sec)/len(sec), len(cu), len(at))

# Published ROPE per-suite values (CU, UA, ASR), to validate the recompute against.
PAPER = {
    "gpt-4o-mini": {"banking": (50.0, 42.4, 0.0), "slack": (66.7, 45.7, 4.8), "travel": (60.0, 48.6, 6.4),
                    "github": (60.0, 52.8, 0.0), "shopping": (35.0, 36.1, 4.4), "dailylife": (35.0, 21.0, 1.0)},
    "gemini-2.5-flash": {"shopping": (15.0, 13.3, 3.9), "github": (20.0, 27.8, 0.0), "dailylife": (40.0, 21.5, 1.0),
                         "banking": (50.0, 49.3, 0.0), "slack": (85.7, 51.4, 6.7), "travel": (40.0, 54.3, 4.3)},
    "gpt-4o": {"github": (65.0, 65.6, 0.0), "shopping": (50.0, 43.3, 6.1), "dailylife": (45.0, 26.0, 1.0)},
    "qwen3-235b": {"github": (65.0, 61.1, 0.0), "shopping": (40.0, 43.3, 7.2), "dailylife": (55.0, 34.5, 0.5)},
}

def report(model):
    paper = PAPER.get(model, {})
    print(f"==== {model} ====")
    print(f"{'suite':10} {'CU':>6} {'UA':>6} {'ASR':>6}   | {'paper CU/UA/ASR':>16}  match?")
    for s in AGENTDYN + AGENTDOJO:
        r = agg(model, s)
        if r is None:
            continue
        cu, ua, asr, nc, na = r
        if s in paper:
            p = paper[s]
            ok = (round(cu, 1), round(ua, 1), round(asr, 1)) == p
            ps, m = f"{p[0]:5.1f}/{p[1]:4.1f}/{p[2]:4.1f}", ("=" if ok else "MISMATCH")
        else:
            ps, m = " " * 16, "(no paper ref)"
        print(f"{s:10} {cu:6.1f} {ua:6.1f} {asr:6.1f}   | {ps}  {m}")
    for grp, suites in [("AgentDyn", AGENTDYN), ("AgentDojo", AGENTDOJO)]:
        rs = [agg(model, s) for s in suites]
        if any(r is None for r in rs):
            continue
        print(f"  {grp} Overall: CU {sum(r[0] for r in rs)/3:.1f}  UA {sum(r[1] for r in rs)/3:.1f}"
              f"  ASR {sum(r[2] for r in rs)/3:.1f}")
    print()

if __name__ == "__main__":
    models = sys.argv[1:] or [m for m in PAPER if os.path.isdir(f"{HERE}/{m}")]
    for m in models:
        report(m)
