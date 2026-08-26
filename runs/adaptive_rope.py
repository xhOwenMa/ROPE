"""ROPE under the AutoDojo adaptive attack vs the static attack, on both benchmarks.

    python adaptive_rope.py

gpt-4o has no adaptive arm and is skipped.
"""
from _scope import (AGENTDOJO, AGENTDYN, attack_files, clean_files, it_index, load, rate)
from corrections import corrected_security

MODELS = ["gpt-4o-mini", "gemini-2.5-flash", "qwen3-235b"]


def cu(model, suites):
    return sum(rate([bool(load(f).get("utility")) for f in clean_files(model, s)])
               for s in suites) / len(suites)


def cell(model, suite, attack):
    files = attack_files(model, suite, attack)
    if not files:
        raise SystemExit(f"FATAL: no {attack} runs for {model}/{suite}")
    ua, sec = [], []
    for f in files:
        d = load(f)
        ua.append(bool(d.get("utility")))
        sec.append(corrected_security(d, suite, it_index(f)))
    return rate(ua), rate(sec), len(files)


print("== AgentDyn ==")
print(f"{'agent':17} {'suite':10} {'ASR static':>11} {'ASR adapt':>10} {'UA static':>10} {'UA adapt':>9} {'n':>6}")
for m in MODELS:
    cols = [[], [], [], []]
    for s in AGENTDYN:
        (u0, a0, n), (u1, a1, _) = cell(m, s, "important_instructions"), cell(m, s, "autodojo")
        print(f"{m:17} {s:10} {a0:11.1f} {a1:10.1f} {u0:10.1f} {u1:9.1f} {n:6d}")
        for col, v in zip(cols, (a0, a1, u0, u1)):
            col.append(v)
    a0, a1, u0, u1 = (sum(c) / 3 for c in cols)
    print(f"{m:17} {'OVERALL':10} {a0:11.1f} {a1:10.1f} {u0:10.1f} {u1:9.1f}"
          f"   CU {cu(m, AGENTDYN):.1f}\n")

print("== AgentDojo, adaptive attack ==")
print(f"{'agent':17} {'CU':>6} {'UA':>6} {'ASR':>6}")
for m in MODELS:
    rs = [cell(m, s, "autodojo") for s in AGENTDOJO]
    print(f"{m:17} {cu(m, AGENTDOJO):6.1f} {sum(r[0] for r in rs) / 3:6.1f} {sum(r[1] for r in rs) / 3:6.1f}")
