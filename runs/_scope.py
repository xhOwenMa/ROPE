"""Shared run-tree loading for the aggregators here."""
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

AGENTDYN = ["github", "shopping", "dailylife"]
AGENTDOJO = ["banking", "slack", "travel"]
# The paper reports four agent models on AgentDyn and three on AgentDojo. This tree also holds
# gpt-4o AgentDojo runs, which no reported table covers; paper_cells() is the reported scope.
DYN_MODELS = ["gpt-4o-mini", "gpt-4o", "gemini-2.5-flash", "qwen3-235b"]
DOJO_MODELS = ["gpt-4o-mini", "gemini-2.5-flash", "qwen3-235b"]


def paper_cells():
    for m in DYN_MODELS:
        for s in AGENTDYN:
            yield m, s
    for m in DOJO_MODELS:
        for s in AGENTDOJO:
            yield m, s


def it_index(path):
    return int(path.rsplit("injection_task_", 1)[1].split(".json")[0])


def task_id(path):
    return "user_task_" + path.split("/user_task_")[1].split("/")[0]


def clean_files(tree, suite):
    return sorted(glob.glob(f"{HERE}/{tree}/{suite}/user_task_*/none/none.json"))


def attack_files(tree, suite, attack):
    return sorted(glob.glob(f"{HERE}/{tree}/{suite}/user_task_*/{attack}/injection_task_*.json"))


def load(path):
    with open(path) as fh:
        return json.load(fh)


def rate(flags):
    if not flags:
        raise SystemExit("FATAL: empty cell set")
    return 100 * sum(flags) / len(flags)
