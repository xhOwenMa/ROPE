"""Driver for the complete routed defense.

Defaults = our MAIN-RESULT configuration: routed defense, the cached **opus** router, strict
decisive-unit matching (the origin.py default; no env var), UNCLAMPED.

  # main result (opus cached router), one suite:
  python -m rope.run_eval --suite github --attack important_instructions
  python -m rope.run_eval --suite github --attack none                 # clean utility

  # a different cached router, or the live router, optionally clamped:
  python -m rope.run_eval --suite github --router gemini-3-flash --clamp
  python -m rope.run_eval --suite github --router live --router-model openai/gpt-4o-mini --clamp

  python -m rope.run_eval --suite github --defense passthrough         # the no-defense baseline
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import openai

from agentdojo.agent_pipeline.llms.openai_llm import OpenAILLM
from agentdojo.attacks.attack_registry import load_attack
from agentdojo.benchmark import benchmark_suite_with_injections, benchmark_suite_without_injections
from agentdojo.logging import OutputLogger
from agentdojo.task_suite.load_suites import get_suite

from common.llm_cache import LLMCache, cached_chat_completer
from rope import pipeline as _pipeline
from rope.fewshot import fewshot, trusted_facts
from rope.scopes_io import CACHED_ROUTERS, load_floor, load_router_scopes

WORK = Path(__file__).resolve().parents[2]
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
BENCHMARK_VERSION = os.environ.get("ROPE_BENCHMARK_VERSION", "v1.2.2")
SUITES = ["github", "shopping", "dailylife", "banking", "travel", "slack"]
TARGET_MODEL = os.environ.get("ROPE_AGENT_MODEL", "openai/gpt-4o-mini")
# pipe.name must contain a key of agentdojo.models.MODEL_NAMES (for the important_instructions attack).
PIPELINE_TAG = os.environ.get("ROPE_PIPELINE_TAG", "gpt-4o-mini-2024-07-18-openrouter")
DEFAULT_CACHE = WORK / "cache" / "llm_completions.json"


def _agent_llm(temperature: float):
    """Return (agent_llm, openrouter_client_or_None). google path wires only the agent LLM."""
    if os.environ.get("ROPE_AGENT_API") == "google":
        from google import genai as _genai
        from agentdojo.agent_pipeline.llms.google_llm import GoogleLLM
        gclient = _genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
        return GoogleLLM(TARGET_MODEL, gclient, temperature=temperature), None
    client = openai.OpenAI(api_key=os.environ["OPENROUTER_API_KEY"], base_url=OPENROUTER_BASE_URL)
    return OpenAILLM(client, TARGET_MODEL, temperature=temperature), client


def build_pipeline(defense, suite, router, *, clamp=False, router_model=None, live_few_shot=True,
                   cache_path=None, use_cache=True, temperature=0.0, name=None):
    llm, client = _agent_llm(temperature)
    if defense == "passthrough":
        return _pipeline.build_passthrough_pipeline(llm, name=name or PIPELINE_TAG)
    if defense != "routed":
        raise ValueError(f"unknown defense: {defense} (use routed|passthrough)")
    if router in CACHED_ROUTERS:
        floor, scopes = load_router_scopes(router, suite)
        return _pipeline.build_routed_pipeline(llm, suite_name=suite, floor=floor, cached_scopes=scopes,
                                               clamp=clamp, name=name)
    if router == "live":
        floor = load_floor(suite)
        rclient = client or openai.OpenAI(api_key=os.environ["OPENROUTER_API_KEY"], base_url=OPENROUTER_BASE_URL)
        rmodel = router_model or TARGET_MODEL
        completer = cached_chat_completer(rclient, rmodel, LLMCache(cache_path or DEFAULT_CACHE, enabled=use_cache))
        # SAME prompt as the §router experiment: append the leave-suite-out few-shot + trusted facts
        # (the only difference from a cached router is that the scope is computed now instead of read).
        examples = fewshot(suite) if live_few_shot else ""
        facts = trusted_facts(suite) if live_few_shot else ""
        return _pipeline.build_routed_pipeline(llm, suite_name=suite, floor=floor,
                                               live_router_complete=completer, live_examples=examples,
                                               live_trusted_facts=facts, clamp=clamp, name=name)
    raise ValueError(f"unknown router: {router} (use one of {CACHED_ROUTERS} or 'live')")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", choices=SUITES, required=True)
    ap.add_argument("--defense", choices=["routed", "passthrough"], default="routed")
    ap.add_argument("--router", default="opus",
                    help=f"cached router ({', '.join(CACHED_ROUTERS)}) or 'live'; default opus (main result)")
    ap.add_argument("--router-model", default=None, help="LLM id for --router live (default: agent model)")
    ap.add_argument("--live-zero-shot", action="store_true",
                    help="--router live without the few-shot/trusted-facts blocks (ablation; default uses them)")
    ap.add_argument("--clamp", action="store_true", help="clamp router overrides to the audited floor")
    ap.add_argument("--attack", choices=["none", "important_instructions", "autodojo"], default="none",
                    help="autodojo replays the cached adaptive-attack injections (set AUTODOJO_CACHE)")
    ap.add_argument("--user-task", action="append", default=None)
    ap.add_argument("--injection-task", action="append", default=None)
    ap.add_argument("--logdir", type=Path, default=WORK / "src" / "rope" / "runs")
    ap.add_argument("--force-rerun", action="store_true")
    ap.add_argument("--cache-path", type=Path, default=DEFAULT_CACHE)
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--temperature", type=float, default=0.0)
    args = ap.parse_args()

    clamp_tag = "-clamp" if args.clamp else ""
    name = f"{PIPELINE_TAG}-rope-{args.defense if args.defense == 'passthrough' else args.router}{clamp_tag}"
    pipe = build_pipeline(args.defense, args.suite, args.router, clamp=args.clamp,
                          router_model=args.router_model, live_few_shot=not args.live_zero_shot,
                          cache_path=args.cache_path, use_cache=not args.no_cache,
                          temperature=args.temperature, name=name)
    suite = get_suite(BENCHMARK_VERSION, args.suite)
    print(f"pipeline: {pipe.name} | agent={TARGET_MODEL} | suite={args.suite} | "
          f"defense={args.defense} | router={args.router} | clamp={args.clamp} | attack={args.attack}")
    with OutputLogger(str(args.logdir), live=None):
        if args.attack == "none":
            results = benchmark_suite_without_injections(
                pipe, suite, user_tasks=args.user_task, logdir=args.logdir,
                force_rerun=args.force_rerun, benchmark_version=BENCHMARK_VERSION)
        else:
            attack = load_attack(args.attack, suite, pipe)
            results = benchmark_suite_with_injections(
                pipe, suite, attack, user_tasks=args.user_task, injection_tasks=args.injection_task,
                logdir=args.logdir, force_rerun=args.force_rerun, benchmark_version=BENCHMARK_VERSION)
    util = list(results["utility_results"].values())
    if util:
        print(f"[{args.suite}] utility: {100 * sum(util) / len(util):.1f}% ({len(util)} cases)")
    if args.attack != "none":
        sec = list(results["security_results"].values())
        if sec:
            print(f"[{args.suite}] ASR: {100 * sum(sec) / len(sec):.1f}% ({len(sec)} cases)")


if __name__ == "__main__":
    main()
