# autodojo

The main benchmark harness and adaptive attack: a fork of
[AgentDojo](https://github.com/ethz-spylab/agentdojo) extended with the
[AutoDojo](https://arxiv.org/abs/2606.15057) adaptive-attack optimizer. It directly supports all
six evaluated suites: `banking`, `slack`, `travel` (three of AgentDojo's four) and `github`,
`shopping`, `dailylife` (from [AgentDyn](https://github.com/SaFo-Lab/AgentDyn)).

## Layout

| Path | Contents |
|---|---|
| `src/agentdojo/` | The fork: the six suites, the attacks (`attacks/autodojo_attack.py` delivers cached optimized injections at benchmark time), the agent pipeline, and the benchmark CLI (`scripts/benchmark.py`). |
| `variant_generation/` | The AutoDojo optimization engine, its prompts, and the cached optimized injections (`variants/{suite}/{model}/{defense}/injections.json`). See `variant_generation/README.md`. |

## Use in this artifact

The defense harness imports this fork via `PYTHONPATH` (see the [root README](../README.md)).
The adaptive-attack runs point `AUTODOJO_CACHE` at a cached cell:

```bash
AUTODOJO_CACHE=$PWD/autodojo/variant_generation/variants/github/openai/gpt-4o-mini/routed/injections.json \
  python -m rope.run_eval --suite github --attack autodojo
```

The shipped caches are AutoDojo-optimized injections against ROPE (`routed`) for the three
AgentDyn suites; `runs/adaptive_rope.py` recomputes the paper's static-vs-adaptive numbers from
the shipped logs, with no API access. To optimize fresh injections, see
`variant_generation/README.md`.

`LICENSE` and `CITATION.bib` are upstream AgentDojo's.
