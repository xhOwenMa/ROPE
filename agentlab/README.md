# Long-horizon benchmark (AgentLAB Task-Injection)

From [AgentLAB](https://github.com/TanqiuJiang/AgentLAB) 

## Layout

| Path | Contents |
|---|---|
| `src/` | A copy of the `autodojo` fork with AgentLAB's additive pieces overlaid: the carrier-document suite YAML and the attack (`src/agentdojo/attacks/long_horizon_eval.py`). The driver puts it first on `sys.path` so it shadows `autodojo/`. |
| `res/long_horizon/<trace-set>/<suite>/v1.2.1/<utask>_<itask>/` | AgentLAB's per-pair attack traces; `newest_injection.json` is what the driver replays. Coverage is a partial grid (banking 144, slack 85, travel 25 pairs), so the driver iterates exactly the cached pairs. |
| `run_eval.py` | Replay driver: runs the cached traces through ROPE (or the undefended agent). |

## Replay

Replaying calls the agent LLM (API cost); the attacker side is fully cached. From the repository
root, with the [setup](../README.md) done:

```bash
python agentlab/run_eval.py --suite banking --user-task user_task_0 --injection-task injection_task_0
python agentlab/run_eval.py --suite banking --defense passthrough   # the no-defense arm
python agentlab/run_eval.py --suite banking --attack none           # clean utility
```

`--snippet-model` selects the trace set under `res/long_horizon/` (default `gpt-4o`); the attack
templates its snippets by the agent model, so set `ROPE_PIPELINE_TAG` to match a non-default
agent model. The per-case ROPE logs behind the paper's long-horizon table are shipped under
`../runs/<model>/<suite>/user_task_*/agentlab_longhorizon/`; recompute the table's ROPE rows from
them, with no API access, via `../runs/longhorizon_rope.py`.
