"""Per-category (under-specification bucket) results for ROPE.

    PYTHONPATH=$PWD/autodojo/src:$PWD/src python runs/buckets.py

AgentDojo uses AutoDojo's published buckets; AgentDyn is not part of that benchmark, so there the
bucket is the one the router emitted. The cached scopes are keyed by request text, hence the suite
loader to map request -> user task id.
"""
import json
import os

from _scope import (AGENTDOJO, AGENTDYN, HERE, attack_files, clean_files, it_index,
                    load, rate, task_id)
from corrections import corrected_security

ROOT = os.path.dirname(HERE)
MODEL = "gpt-4o-mini"
ORDER = ["fully-specified", "param-open", "action-open"]


def dyn_buckets():
    from agentdojo.task_suite.load_suites import get_suite
    version = os.environ.get("ROPE_BENCHMARK_VERSION", "v1.2.1")
    out = {}
    for suite in AGENTDYN:
        by_prompt = {ut.PROMPT.strip(): tid for tid, ut in get_suite(version, suite).user_tasks.items()}
        path = f"{ROOT}/src/rope/scopes/opus/{suite}.json"
        for prompt, scope in load(path).items():
            tid = by_prompt.get(prompt.strip())
            if tid is None:
                raise SystemExit(f"FATAL: scope entry matches no user task in {suite}: {prompt[:70]!r}")
            out[(suite, tid)] = scope["bucket"]
    return out


def dojo_buckets():
    t2b = load(f"{ROOT}/autodojo/variant_generation/user_task_buckets.json")["task_to_bucket"]
    return {(s, f"user_task_{i}"): b for s in AGENTDOJO for i, b in t2b[s].items()}


def table(label, suites, buckets):
    acc = {}
    for suite in suites:
        for f in clean_files(MODEL, suite):
            key = (suite, task_id(f))
            if key not in buckets:
                raise SystemExit(f"FATAL: no bucket for {key}")
            acc.setdefault(buckets[key], {"cu": [], "ua": [], "sec": []})["cu"].append(
                bool(load(f).get("utility")))
        for f in attack_files(MODEL, suite, "important_instructions"):
            d = load(f)
            a = acc[buckets[(suite, task_id(f))]]
            a["ua"].append(bool(d.get("utility")))
            a["sec"].append(corrected_security(d, suite, it_index(f)))
    print(f"=== {label} per-category, ROPE ({MODEL}) ===")
    print(f"{'bucket':17} {'n':>3} {'CU':>6} {'UA':>6} {'ASR':>6}")
    for b in ORDER:
        v = acc[b]
        print(f"{b:17} {len(v['cu']):3d} {rate(v['cu']):6.1f} {rate(v['ua']):6.1f} {rate(v['sec']):6.1f}")
    print()


table("AgentDyn", AGENTDYN, dyn_buckets())
table("AgentDojo", AGENTDOJO, dojo_buckets())
