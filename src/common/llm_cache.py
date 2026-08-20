"""Disk-backed cache for deterministic LLM completions.

Why this exists: the defense's router calls (`Router.classify`, `route_and_scope`) read ONLY the
trusted user task (never injected or runtime content), so their inputs are identical across a
task's clean + every injection run and across reruns. That makes the completions safe to memoize.
Caching:
  (a) freezes one result per (model, prompt, input), removing temp-0 nondeterminism
      so a task is routed identically everywhere (cleaner, reproducible numbers);
  (b) cuts LLM round-trips ~10x on a suite (each user task is otherwise re-asked once per injection);
  (c) leaves an inspectable on-disk record of every routing decision.

The cache key is sha256(model || system || user), so editing a prompt or switching models
invalidates automatically — no manual versioning. The AGENT llm is deliberately NOT routed through
here: its calls depend on injected runtime content and must never be cached. Caching is only sound
because, by the defense's design, just the trusted-task calls flow through a completer.

Storage: one JSON object {key: entry}, rewritten atomically (temp file + os.replace) on each new
miss. Built for sequential / single-process use (the benchmark runs one suite at a time,
max_workers=1). Under accidental concurrency the file stays valid (last writer wins); a few fresh
entries could be lost, never corrupted. A corrupt cache file fails loudly on load (fail-fast) rather
than silently resetting — delete it to rebuild.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Callable


# CANONICAL gemini-via-OpenRouter config: ALWAYS
# pin the google-ai-studio provider and request DYNAMIC thinking (max_tokens -1 = Google's
# native default). Applied only to google/gemini* models; no-op otherwise.
def _gemini_or_eb_kwargs(model_name):
    if not str(model_name).startswith("google/gemini"):
        return {}
    return {"extra_body": {
        "provider": {"order": ["google-ai-studio"], "allow_fallbacks": False},
        "reasoning": {"max_tokens": -1},
    }}



def cache_key(model: str, system: str, user: str) -> str:
    """sha256 over (model, system prompt, user content), NUL-separated so fields can't run together."""
    h = hashlib.sha256()
    for part in (model, system, user):
        h.update(part.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


class LLMCache:
    """A small persistent {key -> completion} store. `enabled=False` turns it into a no-op so callers
    can keep one code path with caching switched off (e.g. a `--no-cache` flag)."""

    def __init__(self, path: str | os.PathLike, enabled: bool = True) -> None:
        self.path = Path(path)
        self.enabled = enabled
        self._store: dict[str, dict] = {}
        if self.enabled and self.path.exists():
            # fail loud on a corrupt cache rather than silently starting fresh
            with self.path.open(encoding="utf-8") as f:
                self._store = json.load(f)

    def get(self, model: str, system: str, user: str) -> str | None:
        if not self.enabled:
            return None
        entry = self._store.get(cache_key(model, system, user))
        return entry["response"] if entry is not None else None

    def put(self, model: str, system: str, user: str, response: str) -> None:
        if not self.enabled:
            return
        self._store[cache_key(model, system, user)] = {
            "model": model,
            "response": response,
            "user_preview": user[:200],  # keeps the cache file human-readable / inspectable
        }
        self._flush()

    def _flush(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._store, f, indent=2, sort_keys=True)
            os.replace(tmp, self.path)  # atomic: a kill mid-write can't truncate the cache
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def __len__(self) -> int:
        return len(self._store)


def cached_chat_completer(client, model: str, cache: LLMCache | None = None,
                          *, temperature: float = 0.0) -> Callable[[str, str], str]:
    """Return an `llm_complete(system, user) -> str` that asks `client` (an OpenAI-style client:
    `client.chat.completions.create(...)`). If `cache` is given AND temperature == 0 (deterministic
    intent), completions are memoized on disk; otherwise every call hits the API. This is the exact
    shape the router calls expect, so it drops straight in.

    NOTE: do not wrap the agent LLM with this — the agent must see fresh runtime content."""
    use_cache = cache is not None and cache.enabled and temperature == 0.0

    def llm_complete(system: str, user: str) -> str:
        if use_cache:
            hit = cache.get(model, system, user)
            if hit is not None:
                return hit
        resp = client.chat.completions.create(
            model=model,
            **_gemini_or_eb_kwargs(model), temperature=temperature,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        )
        text = resp.choices[0].message.content or ""
        if use_cache:
            cache.put(model, system, user, text)
        return text

    return llm_complete
