# file: app/graph/compile.py

import subprocess
import os
from typing import List, Dict, Any
from langgraph.graph import StateGraph, END
import pathlib
import json
from app.graph.planner import planner_node
from app.graph.generator import generator_node
from app.graph.validator import validator_node
from app.graph.state import State


def run_pytest(state: State) -> State:
    # base path under your project root
    artifacts_root = pathlib.Path(__file__).resolve().parents[2] / "artifacts"
    artifacts_root.mkdir(parents=True, exist_ok=True)

    report_dir = artifacts_root / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    allure_dir = artifacts_root / "allure-results"
    allure_dir.mkdir(parents=True, exist_ok=True)

    test_file = state.get("script_path")
    if not test_file:
        state["result"] = {"passed": False, "error": "No script generated"}
        return state

    cmd = [
        "pytest", test_file,
        "--maxfail=1", "--disable-warnings", "-q",
        "--tracing=on", f"--output={report_dir}", f"--alluredir={allure_dir}"
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True)

    # collect traces
    trace_files = []
    for root, _, files in os.walk(report_dir):
        for f in files:
            if f.endswith(".zip"):
                trace_files.append(os.path.join(root, f))

    state["result"] = {
        "passed": proc.returncode == 0,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "exit_code": proc.returncode,
        "report_dir": str(report_dir),
        "trace_paths": [str(p) for p in trace_files],
    }
    return state


graph = StateGraph(State)
graph.add_node("planner", planner_node)
graph.add_node("generator", generator_node)
graph.add_node("validator", validator_node)
graph.add_node("runner", run_pytest)

graph.set_entry_point("planner")
graph.add_edge("planner", "generator")
graph.add_edge("generator", "validator")
graph.add_edge("validator", "runner")
graph.add_edge("runner", END)

app = graph.compile()

if __name__ == "__main__":
    # Example run
    initial_state: State = {
        "objective": "Open example.com and verify the title is 'Example Domain'",
        "plan": [],
        "result": {},
    }
    final_state = app.invoke(initial_state)

    # Pretty-print results (plan + test results)
    print(json.dumps(final_state, indent=2))
