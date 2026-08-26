"""Per-router override counts against the audited floor.

    PYTHONPATH=$PWD/autodojo/src:$PWD/src python runs/router_deviation.py

Loosen is the only direction that is a security risk; the clamp drops those. Reads the cached
scopes, so no API access is needed.
"""
import os
import sys

from _scope import AGENTDYN, HERE, load

sys.path.insert(0, os.path.join(os.path.dirname(HERE), "src"))
from rope.clamp import _default_markers, _more_permissive  # noqa: E402

SCOPES = os.path.join(os.path.dirname(HERE), "src", "rope", "scopes")
ROUTERS = ["opus", "gemini-3-flash", "gpt-oss-20b"]

print(f"{'router':16} {'loosen':>7} {'tighten':>8}")
for router in ROUTERS:
    loose = tight = 0
    for suite in AGENTDYN:
        path = f"{SCOPES}/{router}/{suite}.json"
        if not os.path.exists(path):
            raise SystemExit(f"FATAL: missing cached scope {path}")
        defaults = _default_markers(suite)
        for _task, scope in load(path).items():
            for tool, args in (scope.get("overrides") or {}).items():
                for arg, marker in args.items():
                    default = defaults.get((tool, arg))
                    if default is None:
                        continue
                    m = marker if isinstance(marker, str) else str(marker)
                    loose += _more_permissive(m, default)
                    tight += _more_permissive(default, m)
    print(f"{router:16} {loose:7d} {tight:8d}")
