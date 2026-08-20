from __future__ import annotations

import warnings as _warnings
from types import MethodType

from agentdojo.agent_pipeline.agent_pipeline import AgentPipeline, load_system_message
from agentdojo.agent_pipeline.basic_elements import InitQuery, SystemMessage
from agentdojo.agent_pipeline.base_pipeline_element import BasePipelineElement
from agentdojo.agent_pipeline.tool_execution import ToolsExecutionLoop, ToolsExecutor, tool_result_to_str

from rope import origin as _origin
from rope import policy_synthesis as _ps
from rope.clamp import clamp_taskscope
from rope.enforce import Enforcer
from rope.router import route_and_scope


class OriginTrackerElement(BasePipelineElement):
    """Thin wrapper around origin.OriginTracker so it has the type the tools loop expects."""

    def __init__(self, origin_map: dict) -> None:
        self._tracker = _origin.OriginTracker(origin_map)

    def query(self, query, runtime, env=None, messages=(), extra_args=None):
        return self._tracker.query(query, runtime, env, messages, extra_args or {})


class RoutedPolicyBootstrap(BasePipelineElement):
    """For each task: get this task's TaskScope (cached router or live) -> (optional clamp) -> compile
    against the audited floor -> install in the Enforcer -> guard the runtime."""

    def __init__(self, suite_name: str, floor: dict, origin_map: dict, *,
                 cached_scopes: dict | None = None, live_router_complete=None,
                 live_examples: str = "", live_trusted_facts: str = "",
                 clamp: bool = False, policy_mode: str = "routed") -> None:
        self.suite_name = suite_name
        self.floor = floor                          # the audited global state-changing-tool table
        self.origin_map = origin_map                # shared with OriginTrackerElement; cleared per task
        self.cached_scopes = cached_scopes          # {prompt: TaskScope}; None => live router
        self.live = live_router_complete            # llm_complete(system, user)->str; None => cached
        self.live_examples = live_examples
        self.live_trusted_facts = live_trusted_facts
        self.clamp = clamp
        self.policy_mode = policy_mode
        self.enforcer = Enforcer()
        self._tools_initialized = False
        if (cached_scopes is None) == (live_router_complete is None):
            raise ValueError("provide exactly one of cached_scopes (cached router) or live_router_complete (live)")

    def query(self, query, runtime, env=None, messages=(), extra_args=None):
        extra_args = {} if extra_args is None else extra_args
        if not self._tools_initialized:
            self.enforcer.update_available_tools([
                {"name": t.name, "description": t.description,
                 "args": t.parameters.model_json_schema().get("properties", {})}
                for t in runtime.functions.values()
            ])
            self._tools_initialized = True

        self.enforcer.set_user_query(query)
        self.origin_map.clear()
        prompt_ids = _origin.tokenize_identifiers(query)

        # ── get this task's scope (cached lookup or live router) ────────────────
        if self.cached_scopes is not None:
            scope = self.cached_scopes.get(query)
            if scope is None:
                _warnings.warn(f"no cached scope for prompt {query[:60]!r}; state-changing tools blocked")
                bucket, policy = "unknown-default", {}
            else:
                bucket = scope.bucket
        else:
            scope = route_and_scope(query, self.floor, self.live,
                                    examples=self.live_examples, trusted_facts=self.live_trusted_facts)
            bucket = scope.bucket

        # ── (optional clamp) + compile against the floor ────────────────────────
        if scope is not None:
            if self.clamp:
                scope = clamp_taskscope(self.suite_name, scope)
            policy = _ps.compile_policy(self.floor, scope, origin_map=self.origin_map,
                                        prompt_ids=prompt_ids, policy_mode=self.policy_mode)
        self.enforcer.update_security_policy(policy)
        benign = [t.name for t in runtime.functions.values() if t.name not in self.floor]
        self.enforcer.update_always_allowed_tools(benign)
        extra_args["router_bucket"] = bucket

        if getattr(runtime.run_function, "__name__", "") != "guarded_run_function":
            original_run_function = runtime.run_function
            enforcer = self.enforcer

            def guarded_run_function(self_runtime, call_env, function_name, args):
                try:
                    enforcer.check_tool_call(function_name, args)
                except Exception as e:
                    return "", str(e)
                return original_run_function(call_env, function_name, args)

            runtime.run_function = MethodType(guarded_run_function, runtime)

        return query, runtime, env, messages, extra_args


def build_passthrough_pipeline(llm, *, name: str = "passthrough"):
    """No-defense pipeline (the 'none' baseline)."""
    loop = ToolsExecutionLoop([ToolsExecutor(tool_result_to_str), llm])
    pipe = AgentPipeline([SystemMessage(load_system_message(None)), InitQuery(), llm, loop])
    pipe.name = name
    return pipe


def build_routed_pipeline(llm, *, suite_name, floor, cached_scopes=None, live_router_complete=None,
                          live_examples="", live_trusted_facts="", clamp=False,
                          policy_mode="routed", name=None):
    """The routed defense. Provide either cached_scopes (a cached router) or live_router_complete."""
    origin_map: dict = {}
    bootstrap = RoutedPolicyBootstrap(
        suite_name, floor, origin_map, cached_scopes=cached_scopes,
        live_router_complete=live_router_complete, live_examples=live_examples,
        live_trusted_facts=live_trusted_facts, clamp=clamp, policy_mode=policy_mode)
    loop = ToolsExecutionLoop([ToolsExecutor(tool_result_to_str), OriginTrackerElement(origin_map), llm])
    pipe = AgentPipeline([SystemMessage(load_system_message(None)), InitQuery(), bootstrap, llm, loop])
    pipe.name = name or f"routed-{suite_name}"
    return pipe
