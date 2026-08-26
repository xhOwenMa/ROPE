"""Cache a router's scopes so later runs need no LLM call.

Runs any router over a suite's task prompts once and persists the per-task TaskScopes to
rope/scopes/<name>/<suite>.json, after which `rope.run_eval --router <name>` reads them
deterministically. Reads only the trusted request per task.

  python -m rope.cache_router --router my-gpt4o --router-model openai/gpt-4o-2024-08-06 --suite github
  python -m rope.run_eval     --router my-gpt4o --suite github --attack important_instructions
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import openai

from agentdojo.task_suite.load_suites import get_suite
from common.llm_cache import LLMCache, cached_chat_completer
from rope import markers as M
from rope.fewshot import fewshot, trusted_facts
from rope.router import route_and_scope
from rope.scopes_io import SCOPES_DIR, load_floor

WORK = Path(__file__).resolve().parents[2]
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
BENCHMARK_VERSION = os.environ.get("ROPE_BENCHMARK_VERSION", "v1.2.2")
DEFAULT_CACHE = WORK / "cache" / "router_cache_completions.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--router", required=True, help="name to save the cached scopes under (the --router value to reuse)")
    ap.add_argument("--router-model", required=True, help="LLM id for the router (OpenAI-compatible, e.g. via OpenRouter)")
    ap.add_argument("--suite", required=True)
    ap.add_argument("--base-url", default=OPENROUTER_BASE_URL, help="OpenAI-compatible endpoint (default OpenRouter)")
    ap.add_argument("--trusted-facts", default=None, help="override trusted account facts (default: the canonical block)")
    ap.add_argument("--examples-file", type=Path, default=None, help="override few-shot examples (default: the canonical leave-suite-out block)")
    ap.add_argument("--zero-shot", action="store_true", help="cache with NO few-shot/trusted-facts (ablation)")
    ap.add_argument("--no-cache", action="store_true", help="do not use the on-disk LLM completion cache")
    ap.add_argument("--force", action="store_true", help="overwrite an existing scopes file")
    args = ap.parse_args()

    if args.router in ("opus", "live"):
        raise SystemExit("refusing to overwrite the reserved router name 'opus'/'live'")
    out = SCOPES_DIR / args.router / f"{args.suite}.json"
    if out.exists() and not args.force:
        raise SystemExit(f"{out} exists; pass --force to overwrite")

    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise SystemExit("OPENROUTER_API_KEY not set")
    client = openai.OpenAI(api_key=key, base_url=args.base_url)
    completer = cached_chat_completer(client, args.router_model,
                                     LLMCache(DEFAULT_CACHE, enabled=not args.no_cache))
    # SAME prompt as the §router experiment by default: leave-suite-out few-shot + trusted facts.
    if args.zero_shot:
        examples, facts = "", ""
    else:
        examples = args.examples_file.read_text() if args.examples_file else fewshot(args.suite)
        facts = args.trusted_facts if args.trusted_facts is not None else trusted_facts(args.suite)

    floor = load_floor(args.suite)
    suite = get_suite(BENCHMARK_VERSION, args.suite)
    prompts = [suite.get_user_task_by_id(uid).PROMPT for uid in suite.user_tasks]
    print(f"caching router={args.router} model={args.router_model} over {len(prompts)} {args.suite} tasks")

    scopes: dict[str, dict] = {}
    for i, prompt in enumerate(prompts):
        scope = route_and_scope(prompt, floor, completer, examples=examples, trusted_facts=facts)
        d = M.scope_to_dict(scope)
        M.scope_from_dict(d)  # sanity: must be loadable back
        scopes[prompt] = d
        print(f"  [{i + 1}/{len(prompts)}] {scope.bucket:16} {prompt[:60]!r}")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(scopes, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {out} ({len(scopes)} scopes) -- use with: python -m rope.run_eval --router {args.router} --suite {args.suite}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
