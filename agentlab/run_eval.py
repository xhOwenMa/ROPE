"""Driver: replay AgentLAB's long-horizon Task-Injection attack against ROPE.

`agentlab/src` is a copy of the `autodojo` fork with AgentLAB's additive pieces overlaid -- the
carrier-document suite YAML and the `long_horizon` attack (`src/agentdojo/attacks/
long_horizon_eval.py`). It is put FIRST on sys.path so `import agentdojo` resolves here and the
suites carry the carrier documents the attack fills. The attack replays AgentLAB's published
per-pair attack traces (`res/long_horizon/`), so there is no attacker-LLM cost; only the agent
LLM is called (it still costs API money -- check before running a whole suite).

  # one banking case, ROPE (cached opus router, main configuration):
  python run_eval.py --suite banking --user-task user_task_0 --injection-task injection_task_0

  python run_eval.py --suite banking --defense passthrough    # the no-defense arm
  python run_eval.py --suite banking --attack none            # clean utility

To recompute the paper's long-horizon numbers from the shipped logs instead (no API access),
run ../runs/longhorizon_rope.py.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
# The AgentLAB overlay fork must SHADOW autodojo/ (which PYTHONPATH may already carry).
sys.path.insert(0, str(HERE / "src"))
sys.path.insert(1, str(ROOT / "src"))

import agentdojo.attacks.long_horizon_eval  # noqa: E402,F401  (registers the long_horizon attack)
from agentdojo.attacks.attack_registry import load_attack  # noqa: E402
from agentdojo.benchmark import (  # noqa: E402
    benchmark_suite_with_injections,
    benchmark_suite_without_injections,
)
from agentdojo.logging import OutputLogger  # noqa: E402
from agentdojo.task_suite.load_suites import get_suite  # noqa: E402

from rope.run_eval import PIPELINE_TAG, build_pipeline  # noqa: E402

# AgentLAB's traces were generated against v1.2.1 suites; load suites at the same version so the
# (user_task, injection_task) ids and tool sequences line up with the cached traces.
BENCHMARK_VERSION = "v1.2.1"
SUITES = ["banking", "travel", "slack"]


def discover_pairs(snippet_model: str, suite: str) -> list[tuple[str, str]]:
    """The (user_task, injection_task) pairs that have a cached trace for this model+suite.

    Coverage is PARTIAL for some suites (AgentLAB only ran a subset of the grid), so we iterate
    exactly these pairs -- a full user x injection cartesian would hit missing files."""
    root = HERE / "res" / "long_horizon" / snippet_model / suite / BENCHMARK_VERSION
    if not root.is_dir():
        raise FileNotFoundError(f"no cached traces at {root}")
    pairs = []
    for d in sorted(root.iterdir()):
        if not (d / "newest_injection.json").is_file():
            continue
        name = d.name  # user_task_<i>_injection_task_<j>
        if "_injection_task_" not in name:
            raise ValueError(f"unexpected trace dir name: {name}")
        ut, it = name.split("_injection_task_")
        pairs.append((ut, "injection_task_" + it))
    if not pairs:
        raise FileNotFoundError(f"no trace pairs found under {root}")
    return pairs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", choices=SUITES, required=True)
    ap.add_argument("--defense", choices=["routed", "passthrough"], default="routed")
    ap.add_argument("--router", default="opus")
    ap.add_argument("--clamp", action="store_true")
    ap.add_argument("--snippet-model", default="gpt-4o",
                    help="cached trace folder under res/long_horizon/ to replay")
    ap.add_argument("--attack", choices=["none", "long_horizon"], default="long_horizon")
    ap.add_argument("--user-task", action="append", default=None)
    ap.add_argument("--injection-task", action="append", default=None)
    ap.add_argument("--logdir", type=Path, default=None, help="default: agentlab/runs/<defense>")
    ap.add_argument("--force-rerun", action="store_true")
    ap.add_argument("--temperature", type=float, default=0.0)
    args = ap.parse_args()

    # the long_horizon attack reads res/long_horizon/<LH_SNIPPET_MODEL>/<suite>/v1.2.1/...
    os.environ["LH_SNIPPET_MODEL"] = args.snippet_model
    logdir = args.logdir or (HERE / "runs" / args.defense)
    logdir.mkdir(parents=True, exist_ok=True)

    # pipe.name must contain an agentdojo model name: the long_horizon attack templates its
    # snippets by the agent model (set ROPE_PIPELINE_TAG to match a non-default agent model).
    pipe = build_pipeline(args.defense, args.suite, args.router, clamp=args.clamp,
                          temperature=args.temperature, name=PIPELINE_TAG)
    suite = get_suite(BENCHMARK_VERSION, args.suite)
    print(f"pipeline: {pipe.name} | suite={args.suite} | attack={args.attack} | "
          f"snippet_model={args.snippet_model}")
    util_vals: list[bool] = []
    sec_vals: list[bool] = []
    skipped: list[str] = []
    with OutputLogger(str(logdir), live=None):
        if args.attack == "none":
            results = benchmark_suite_without_injections(
                pipe, suite, user_tasks=args.user_task, logdir=logdir,
                force_rerun=args.force_rerun, benchmark_version=BENCHMARK_VERSION)
            util_vals = list(results["utility_results"].values())
        else:
            # Only the (user_task, injection_task) pairs with a cached trace (partial coverage).
            pairs = discover_pairs(args.snippet_model, args.suite)
            if args.user_task:
                pairs = [(u, i) for (u, i) in pairs if u in args.user_task]
            if args.injection_task:
                pairs = [(u, i) for (u, i) in pairs if i in args.injection_task]
            if not pairs:
                raise ValueError("no cached trace pairs match the requested user/injection filter")
            attack = load_attack(args.attack, suite, pipe)
            print(f"running {len(pairs)} cached trace pairs")
            # Per-pair isolation: a single malformed UPSTREAM cached trace must not take down the
            # whole suite arm. Not swallowed -- the failing pair is printed loudly, tallied, and a
            # non-empty skip list makes the run exit non-zero so it is SEEN.
            for ut, it in pairs:
                try:
                    results = benchmark_suite_with_injections(
                        pipe, suite, attack, user_tasks=(ut,), injection_tasks=(it,),
                        logdir=logdir, force_rerun=args.force_rerun,
                        benchmark_version=BENCHMARK_VERSION)
                except Exception as e:  # noqa: BLE001 -- isolate one bad cached trace, report loudly
                    print(f"  SKIPPED {ut}/{it}: {type(e).__name__}: {e}", flush=True)
                    skipped.append(f"{ut}/{it}")
                    continue
                util_vals += list(results["utility_results"].values())
                sec_vals += list(results["security_results"].values())
            if skipped:
                print(f"[{args.suite}] SKIPPED {len(skipped)} pairs (malformed cached trace): "
                      + ", ".join(skipped))
    if util_vals:
        print(f"[{args.suite}] benign utility: {100 * sum(util_vals) / len(util_vals):.1f}% "
              f"({len(util_vals)} cases)")
    if sec_vals:
        print(f"[{args.suite}] ASR: {100 * sum(sec_vals) / len(sec_vals):.1f}% "
              f"(security==True means attack succeeded) ({len(sec_vals)} cases)")
    if skipped:
        # fail-loud at the process level: a malformed cached trace was skipped, not hidden.
        raise SystemExit(f"{len(skipped)} pair(s) skipped due to malformed cached traces: {skipped}")


if __name__ == "__main__":
    main()
