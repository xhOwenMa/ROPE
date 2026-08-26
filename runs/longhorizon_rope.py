"""ROPE under AgentLAB's long-horizon Task-Injection replay.

    python longhorizon_rope.py

The replayed cases cover the suites unevenly, so this table pools per case rather than by the
unweighted suite mean used elsewhere. lh_cells.json holds the cells present in every arm; pooling
over exactly those keeps the rows comparable across defenses.
"""
import glob

from _scope import AGENTDOJO, HERE, load

CELLS = load(f"{HERE}/lh_cells.json")
MODELS = ["gpt-4o-mini", "gemini-2.5-flash", "qwen3-235b"]


def agg(model):
    per_suite, sec_hit, ua_hit, n_tot, cu_hit, cu_tot = {}, 0, 0, 0, 0, 0
    for suite in AGENTDOJO:
        logs = {}
        for f in glob.glob(f"{HERE}/{model}/{suite}/user_task_*/agentlab_longhorizon/injection_task_*.json"):
            d = load(f)
            if "security" not in d:          # errored replay, never part of the matched set
                continue
            logs[(d["user_task_id"], d["injection_task_id"])] = (bool(d["security"]), bool(d["utility"]))
        keys = [tuple(k) for k in CELLS[model][suite]]
        missing = [k for k in keys if k not in logs]
        if missing:
            raise SystemExit(f"FATAL: {model}/{suite} matched cells missing from the logs: {missing}")
        per_suite[suite] = 100 * sum(logs[k][0] for k in keys) / len(keys)
        sec_hit += sum(logs[k][0] for k in keys)
        ua_hit += sum(logs[k][1] for k in keys)
        n_tot += len(keys)

        tasks = sorted({ut for ut, _ in keys})
        clean = {f.split(f"{suite}/")[1].split("/")[0]: bool(load(f).get("utility"))
                 for f in glob.glob(f"{HERE}/{model}/{suite}/user_task_*/none/none.json")}
        absent = [t for t in tasks if t not in clean]
        if absent:
            raise SystemExit(f"FATAL: {model}/{suite} matched user tasks missing a clean log: {absent}")
        cu_hit += sum(clean[t] for t in tasks)
        cu_tot += len(tasks)
    return 100 * cu_hit / cu_tot, 100 * ua_hit / n_tot, per_suite, 100 * sec_hit / n_tot, n_tot


header = (f"{'model':18} {'CU':>6} {'UA':>6} | {'banking':>7} {'slack':>6} {'travel':>6} | "
          f"{'Overall':>7} {'n':>4}")
print(header)
print("-" * len(header))
for model in MODELS:
    cu, ua, per, overall, n = agg(model)
    print(f"{model:18} {cu:6.1f} {ua:6.1f} | {per['banking']:7.1f} {per['slack']:6.1f} "
          f"{per['travel']:6.1f} | {overall:7.1f} {n:4d}")
