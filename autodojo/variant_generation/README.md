# AutoDojo — Variant Generation

The AutoDojo optimization engine. See the [AutoDojo paper](https://arxiv.org/abs/2606.15057) for the method,
threat model, and prompt design.

Run from the artifact root with `PYTHONPATH=autodojo/src:autodojo/variant_generation`; API keys
are read from the environment or a `.env` file (`OPENROUTER_API_KEY`).

## Optimize (`optimize_variants.py`)

```bash
# Bare-agent eval
python autodojo/variant_generation/optimize_variants.py \
    --suite banking --n-variants 5 --iterations 8 \
    --eval-asr --target-model vllm_parsed --target-model-id Qwen3-8B \
    --analyzer-prompt analyzer_banking --injection-prompt injection_task_iterative_banking

# Defended eval (the defense runs in the evaluation loop)
python autodojo/variant_generation/optimize_variants.py \
    --suite banking --n-variants 5 --iterations 8 \
    --eval-asr --target-model vllm_parsed --target-model-id Qwen3-8B \
    --analyzer-prompt analyzer_banking --injection-prompt injection_task_iterative_banking \
    --defense datafilter --run-defense
```

Output is written to `variants/{suite}/{model}/{defense}/injections.json` (`{model}` = `--target-model` id verbatim, so a provider prefix nests; `{defense}` = `--defense` or `no_defense`). Set `AUTODOJO_OUTPUT_DIR` to write the produced `injections.json` under a different root instead of `variants/` — e.g. an external defense plugin keeping its caches out of this tree. Seed caches are still read from `variants/`.

### Flags

| Flag | Default | Purpose |
|---|---|---|
| `--suite` | (required, repeatable) | `banking`, `travel`, `slack`, `github`, `shopping`, `dailylife` |
| `--n-variants` | `5` | Top variants kept per (injection_task, vector) |
| `--filter-granularity` | `sentence` | Deberta filters (`protectai`/`piguard`/`promptguard`): `sentence` drops flagged sentences; `document` redacts the whole tool message |
| `--iterations` | `8` | Optimization iterations per pair |
| `--model` | `google/gemini-3.1-pro-preview` | Optimizer (analyzer + rewriter) LLM |
| `--provider` | `openrouter` | LLM provider |
| `--eval-asr` | off | Enable on-the-fly ASR evaluation |
| `--target-model` | `vllm_parsed` | Target model for ASR evaluation |
| `--target-model-id` | (none) | Model id for `vllm_parsed` (e.g. `Qwen3-8B`) |
| `--defense` | (none) | Defense run during eval (requires `--run-defense`) |
| `--run-defense` | off | Run `--defense` in the eval loop |
| `--parallel-eval` | off | Evaluate independent `(user_task, injection)` pairs concurrently (speedup). Only for stateless prompt-level defenses (no-defense, `spotlighting`, `reminder`, `sandwich`, `repeat_user_prompt`, `tool_filter`); fails fast otherwise. The allow-list is `PARALLEL_EVAL_SAFE_DEFENSES` in `agent_pipeline.py`; an external defense plugin may add its own name once its element is concurrency-safe |
| `--eval-concurrency` | `8` | Thread-pool size for `--parallel-eval`; size to the target provider's rate limit |
| `--analyzer-prompt` | `analyzer` | Analyzer prompt in `prompts/` |
| `--injection-prompt` | `injection_task_iterative` | Rewriter prompt in `prompts/` |
| `--no-stratified` / `--no-analyzer` | off | Disable stratified eval / analyzer |
| `--top-k-leaderboard` | `3` | Leaderboard entries shown to the LLM |
| `--store-traces` | off | Save failure_class + tool_calls in output |
| `--dry-run` | off | Print prompts; no LLM calls; no files |
| `--max-injection-tasks` / `--vectors` | all | Limit to first M tasks / specific vector(s) |
| `--use-cache` / `--resume` | off | Skip / resume an existing cell cache |
| `--verbose` | off | Print full prompts, outputs, eval details |

## Benchmark optimized injections

The caches are consumed by the `autodojo` attack via `AUTODOJO_CACHE`. The shipped cells are the
ROPE (`routed`) caches for the three AgentDyn suites, replayed through the defense harness (see
the [root README](../../README.md)). A cell produced by the optimizer can also be delivered
through the fork's own benchmark CLI:

```bash
AUTODOJO_CACHE=autodojo/variant_generation/variants/{suite}/{model}/{defense}/injections.json \
AUTODOJO_VARIANT=0 \
PYTHONPATH=autodojo/src python -m agentdojo.scripts.benchmark \
    --model openai/gpt-4o-mini --suite banking \
    --attack autodojo --defense datafilter \
    --injection-attack-name <run_label> --logdir runs
```

`AUTODOJO_VARIANT` is the 0-indexed variant (0…n_variants-1); benchmarking falls back to `injection_task.GOAL` when a cell has no variant. For `--defense drift` / `--defense progent`, the precomputed injection-independent caches live in `drift/cache/` and `progent/cache/` (`--drift-cache-dir` / `--progent-cache-dir`).

## Prompts (`prompts/`)

| File | |
|---|---|
| `defense_families.yaml` | Family-level defense block substituted at `$defense_families` — the only defense knowledge any prompt receives |
| `analyzer.yaml` / `analyzer_<suite>.yaml` | Generic / per-suite analyzer |
| `injection_task_iterative.yaml` / `injection_task_iterative_<suite>.yaml` | Generic / per-suite rewriter |
| `topicattack_attack_prompt_transfer.txt` | TopicAttack conversation template |

Templates use `string.Template` (`$var`) syntax.

## Cache format

One cache per (suite, target model, defense) cell at `variants/{suite}/{model}/{defense}/injections.json`:

```json
{
  "suite": "banking", "n_variants": 5, "method": "iterative_optimization",
  "iterations": 8, "model": "google/gemini-3.1-pro-preview",
  "defense": "datafilter", "defense_run": true,
  "injection_tasks": {
    "injection_task_0": {
      "injection_address_change": {
        "original": "<GOAL>",
        "variants": ["<injection text>", "..."],
        "trajectory": [{"text": "...", "asr": 0.5, "iteration": 3}]
      }
    }
  }
}
```
