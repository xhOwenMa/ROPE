# ROPE: Routed Origin Policy Enforcement

Source code of our paper:

> **ROPE: Routed Origin Policy Enforcement against Indirect Prompt Injection**
> by Xinhang Ma, Chaowei Xiao, William Yeoh, Ning Zhang, Yevgeniy Vorobeychik

## Abstract

Indirect prompt injection (IPI) plants instructions in the content a tool-using LLM agent reads, steering the agent into harmful tool calls. The strongest defenses are system-level, leveraging techniques such as task-conditional tool screening to prevent execution of malicious tools, and information-flow control to avoid tool execution with untrusted parameters. However, as agents grow more capable, users delegate more to automation. Consequently, tool execution sequences and parameter values are increasingly determined at runtime and cannot be reliably screened using information contained solely in the user query without significant utility loss. We present ROPE (Routed Origin Policy Enforcement), which is anchored in a structural notion of trust: a value may reach a state-changing tool only if it traces unforgeably to the user, a source the user explicitly named, or the user's own authoritative records. Enforcement is then a deterministic origin check over an audited set of sensitive tool parameters, and the only reliance on a language model involves solely the trusted user request, out of the attacker's reach. Our approach admits two provable guarantees: 1) at every step of a trajectory, no value whose only origin is attacker-writable content reaches an origin-guarded parameter, and 2) no rewording of an injection changes an admission decision. Through extensive experimental evaluation, we show that across four agent models on open-ended agent suites, ROPE holds attack success rate to 1.6–2.6% while retaining 82–100% of undefended clean utility, significantly exceeding state-of-the-art system-level defenses in utility while attaining comparable or better security on complex dynamic workflows. Further, we show that optimizing the injection against ROPE is largely ineffective, while long-horizon attacks that defeat prior system-level defenses achieve zero success rate in our case.

## Repository layout

| Path | Contents |
|---|---|
| `src/rope/` | The defense: router, per-task scope, policy compiler, origin tracker, runtime guard. |
| `src/rope/scopes/_floor/<suite>.json` | The audited sensitive-tool/parameter table per suite (shared by all routers). |
| `src/rope/scopes/<router>/<suite>.json` | Cached per-task scopes for the three evaluated routers (`opus`, `gemini-3-flash`, `gpt-oss-20b`) — offline replay of the paper's router outputs. |
| `src/common/` | LLM completion cache used by the router (trusted-input calls only). |
| `autodojo/` | The main benchmark harness and adaptive attack: it directly supports all six evaluated suites: `banking`, `slack`, `travel` (three of AgentDojo's four) and `github`, `shopping`, `dailylife` (from AgentDyn). |
| `agentlab/` | The long-horizon benchmark: AgentLAB's Task-Injection attack and its published attack traces, plus the replay driver. See `agentlab/README.md`. |
| `runs/` | ROPE run logs (JSON) for all four agent models, and the scripts that recompute every reported ROPE number from them. |

## Setup

Python 3.12 with `openai`, `pydantic`, `jsonschema`, `pyyaml` (and `google-genai` for the native
Gemini path). From the repository root:

```bash
export PYTHONPATH=$PWD/autodojo/src:$PWD/src
```

## Reproduce the reported numbers from the shipped logs (no API access needed)

```bash
cd runs
python aggregate.py         # CU / UA / ASR per suite + overalls
python adaptive_rope.py     # static vs adaptive ASR (AutoDojo attack)
python longhorizon_rope.py  # long-horizon (AgentLAB Task-Injection)
```

`runs/<model>/<suite>/user_task_*/` holds one JSON per evaluated cell: `none/` (clean),
`important_instructions/` (static attack), `autodojo/` (adaptive attack), and
`agentlab_longhorizon/` (long-horizon staged attack).

**Scoring corrections.** Three benchmark oracles are unsound for execution-blocking defenses.
`runs/corrections.py` dispatches the three effect-based rescorings — slack IT5,
dailylife IT7, github IT1 — and the aggregators apply them; each module's docstring documents the
artifact and the fix. CU/UA are never touched.

## Run the defense

```bash
# main-result configuration (cached opus router, strict matching, unclamped):
python -m rope.run_eval --suite github --attack important_instructions
python -m rope.run_eval --suite github --attack none            # clean utility
python -m rope.run_eval --suite github --defense passthrough    # no-defense baseline

# cheaper routers from the router study, optionally clamped to the audited floor:
python -m rope.run_eval --suite github --router gemini-3-flash --clamp

# live router (recompute the scope at run time with any OpenAI-compatible model):
python -m rope.run_eval --suite github --router live --router-model openai/gpt-4o-mini --clamp

# adaptive attack: replay the cached AutoDojo-optimized injections
AUTODOJO_CACHE=$PWD/autodojo/variant_generation/variants/github/openai/gpt-4o-mini/routed/injections.json \
  python -m rope.run_eval --suite github --attack autodojo

# long-horizon attack: replay AgentLAB's cached traces (see agentlab/README.md)
python agentlab/run_eval.py --suite banking --user-task user_task_0 --injection-task injection_task_0
```

Environment variables: `OPENROUTER_API_KEY` (agent model and live router; all reported runs call
the agent models through OpenRouter),
`ROPE_AGENT_MODEL` (default `openai/gpt-4o-mini`),
`ROPE_PIPELINE_TAG` to tag the run logs (must contain an AgentDojo model name so the attack templates resolve).

The cached routers make the defense fully deterministic and API-free on the routing side: `opus`
covers all six suites; `gemini-3-flash` and `gpt-oss-20b` cover the AgentDyn suites (the router
study's scope). To evaluate your own router, cache it once and reuse it like a built-in:

```bash
python -m rope.cache_router --router my-router --router-model <llm-id> --suite github
python -m rope.run_eval     --router my-router --suite github --attack important_instructions
```

## Acknowledgments

This repository vendors or builds on: [AgentDojo](https://github.com/ethz-spylab/agentdojo) and [AgentDyn](https://github.com/SaFo-Lab/AgentDyn) (benchmark suites), [AutoDojo](https://arxiv.org/abs/2606.15057) (adaptive attack), and AgentLAB (long-horizon benchmark and Task-Injection attack traces). See the respective papers for details.

## References

If you find this work useful, we appreciate if you can kindly cite:

```bibtex
@article{rope,
  title={ROPE: Routed Origin Policy Enforcement against Indirect Prompt Injection},
  author={Ma, Xinhang and Xiao, Chaowei and Yeoh, William and Zhang, Ning and Vorobeychik, Yevgeniy},
  journal={arXiv preprint},
  year={2026}
}
```
