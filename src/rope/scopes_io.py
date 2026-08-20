"""Load cached router scopes + the audited floor for the routed defense.

A "router" turns the trusted request into a per-task TaskScope. We support:
  - CACHED routers (opus, gemini-3-flash, gpt-oss-20b): their per-task scopes are stored as marker
    JSON under scopes/<router>/<suite>.json; we read them at runtime (no LLM call).
  - the LIVE router (run an LLM at runtime): handled in pipeline.py via router.route_and_scope.

The audited FLOOR (the global state-changing-tool table per suite, authored once) lives in
scopes/_floor/<suite>.json and is shared by every router. Marker (de)serialization is in markers.py.
"""

from __future__ import annotations

import json
from pathlib import Path

from rope import markers as _m

SCOPES_DIR = Path(__file__).resolve().parent / "scopes"
CACHED_ROUTERS = ("opus", "gemini-3-flash", "gpt-oss-20b")


def floor_to_dict(floor: dict) -> dict:
    """{tool: {arg: marker-rule}} -> {tool: {arg: marker-str}} (serializable normal form)."""
    return {t: {a: _m.marker_to_str(r) for a, r in am.items()} for t, am in floor.items()}


def floor_from_dict(d: dict) -> dict:
    """Inverse of floor_to_dict: {tool: {arg: marker-str}} -> {tool: {arg: marker-rule}}."""
    return {t: {a: _m.str_to_rule(s) for a, s in am.items()} for t, am in d.items()}


def load_floor(suite: str) -> dict:
    p = SCOPES_DIR / "_floor" / f"{suite}.json"
    if not p.is_file():
        raise FileNotFoundError(f"no floor for suite {suite!r} at {p}")
    return floor_from_dict(json.loads(p.read_text()))


def load_router_scopes(router: str, suite: str):
    """(floor, {prompt: TaskScope}) for a CACHED router; raises if that router has no cache for the suite."""
    floor = load_floor(suite)
    p = SCOPES_DIR / router / f"{suite}.json"
    if not p.is_file():
        raise FileNotFoundError(f"router {router!r} has no cached scopes for suite {suite!r} at {p}")
    raw = json.loads(p.read_text())
    scopes = {prompt: _m.scope_from_dict(d) for prompt, d in raw.items()}
    return floor, scopes
