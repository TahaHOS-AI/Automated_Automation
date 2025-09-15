# file: app/graph/compile.py

import subprocess
import os
from typing import List, Dict, Any
from langgraph.graph import StateGraph, END
import pathlib
import json
from app.graph.planner import planner_node
from app.graph.plan_validator import plan_validator_node
from app.graph.generator import generator_node
from app.graph.validator import validator_node
from app.graph.state import State


def run_script(state: State) -> State:
    """Run the generated Python script directly."""
    script_path = state.get("script_path")
    if not script_path:
        state["result"] = {"passed": False, "error": "No script generated"}
        return state

    print(f"(runner_node) -> Running script: {script_path}")

    try:
        # Run the Python script directly
        proc = subprocess.run(["python", script_path], capture_output=True, text=True, timeout=60)

        state["result"] = {
            "passed": proc.returncode == 0,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "exit_code": proc.returncode,
            "script_path": script_path
        }

        if proc.returncode == 0:
            print("(runner_node) -> Script executed successfully!")
        else:
            print(f"(runner_node) -> Script failed with exit code: {proc.returncode}")

    except subprocess.TimeoutExpired:
        state["result"] = {
            "passed": False,
            "error": "Script timed out after 60 seconds",
            "stdout": "",
            "stderr": "Timeout",
            "exit_code": -1,
            "script_path": script_path
        }
        print("(runner_node) -> Script timed out")

    except Exception as e:
        state["result"] = {
            "passed": False,
            "error": f"Failed to run script: {str(e)}",
            "stdout": "",
            "stderr": str(e),
            "exit_code": -1,
            "script_path": script_path
        }
        print(f"(runner_node) -> Error running script: {e}")

    return state


graph = StateGraph(State)
graph.add_node("planner", planner_node)
graph.add_node("plan_validator", plan_validator_node)
graph.add_node("generator", generator_node)
graph.add_node("validator", validator_node)
graph.add_node("runner", run_script)

graph.set_entry_point("planner")
graph.add_edge("planner", "plan_validator")
graph.add_edge("plan_validator", "generator")
graph.add_edge("generator", "validator")
graph.add_edge("validator", "runner")
graph.add_edge("runner", END)

app = graph.compile()

# Test just the planner node
def test_planner_only():
    """Test only the planner node without the full graph."""
    from app.graph.planner import planner_node

    initial_state: State = {
        "objective": "Login to LinkedIn and verify dashboard loads"
        # 'objective': 'Navigate to example.com and verify the title is "Example Domain"'
    }

    result_state = planner_node(initial_state)
    print("Planner Output:")
    print(json.dumps(result_state["plan"], indent=2))
    return result_state

# Test minimal graph with just planner
def test_planner_graph():
    """Test a minimal graph with only the planner node."""
    planner_graph = StateGraph(State)
    planner_graph.add_node("planner", planner_node)
    planner_graph.set_entry_point("planner")
    planner_graph.add_edge("planner", END)

    mini_app = planner_graph.compile()

    initial_state: State = {
        "objective": "Login to LinkedIn and verify dashboard loads"
    }

    result = mini_app.invoke(initial_state)
    print("Planner Graph Output:")
    print(json.dumps(result["plan"], indent=2))
    return result

# Test the full graph with demonstrate=False (LLM generation mode)
def test_full_graph_demonstrate_false():
    # Get user input for objective
    print("🤖 Automated Browser Automation System")
    print("=" * 50)

    objective = input("🎯 Enter your automation objective: ").strip()
    if not objective:
        print("❌ No objective provided. Exiting.")
        return

    demonstrate = input("🎮 Use demonstration mode? (y/n): ").lower().startswith('y')

    initial_state: State = {
        "objective": objective,
        "plan": [],
        "result": {},
        "demonstrate": demonstrate,
        "credentials": {}
    }

    print(f"\n=== Testing Full Graph ===")
    print(f"Objective: {initial_state['objective']}")
    print(f"Demonstrate: {initial_state['demonstrate']}")
    print()

    final_state = app.invoke(initial_state)

    print("\n" + "="*60)
    print("🎉 EXECUTION COMPLETE!")
    print("="*60)

    if "execution_folder" in final_state:
        print(f"📁 Files saved in: {final_state['execution_folder']}")
        print("📋 Contents:")
        import os
        for item in os.listdir(final_state["execution_folder"]):
            print(f"   • {item}")

    print("\n📊 Final State:")
    print(json.dumps(final_state, indent=2))
    return final_state

if __name__ == "__main__":
    # Uncomment one of these to test:

    # Test planner node directly
    # test_planner_only()

    # Test planner in minimal graph
    # test_planner_graph()

    # Test full graph with demonstrate=False (LLM generation)
    test_full_graph_demonstrate_false()
