# file: app/graph/planner.py

from typing import List, Any, Dict
from langchain_community.chat_models import ChatOllama
from langchain.prompts import ChatPromptTemplate
import json
from app.graph.state import State

# initialize Ollama client
llm = ChatOllama(model="gemma3:1b", temperature=0)

# prompt template
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a planner that decomposes objectives into a JSON plan."),
    ("human", "Objective: {objective}\n\nReturn ONLY JSON in the format:\n"
              "[{{\"id\": 1, \"type\": \"browser_step\"|\"logic_step\", \"goal\": \"...\", \"success_criteria\": \"...\"}}, ...]")
])

def planner_node(state: State) -> State:
    objective = state.get("objective", "")
    if not objective:
        state["plan"] = []
        return state

    max_retries = 3
    for attempt in range(max_retries):
        try:
            # run LLM
            chain = prompt | llm
            response = chain.invoke({"objective": objective})
            raw_output = response.content.strip()

            # Strip markdown code blocks
            if raw_output.startswith("```json"):
                raw_output = raw_output[7:]
            if raw_output.endswith("```"):
                raw_output = raw_output[:-3]
            raw_output = raw_output.strip()

            # Fix common JSON issues
            raw_output = re.sub(r',\s*]', ']', raw_output)  # Remove trailing commas before ]
            raw_output = re.sub(r',\s*}', '}', raw_output)  # Remove trailing commas before }

            plan = json.loads(raw_output)

            # Validate plan structure
            if not isinstance(plan, list):
                raise ValueError("Plan must be a list")

            for i, step in enumerate(plan):
                if not isinstance(step, dict):
                    raise ValueError(f"Step {i} must be a dictionary")
                required_fields = ["id", "type", "goal", "success_criteria"]
                for field in required_fields:
                    if field not in step:
                        raise ValueError(f"Step {i} missing required field: {field}")

            # Clean up any extra fields
            for step in plan:
                if "logic_step" in step:
                    del step["logic_step"]

            state["plan"] = plan
            return state

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            if attempt == max_retries - 1:
                # Final fallback
                state["plan"] = [{
                    "id": 1,
                    "type": "browser_step",
                    "goal": f"Execute objective: {objective}",
                    "success_criteria": "Test completes successfully"
                }]
                return state
            # Continue to next retry

    # Should not reach here, but just in case
    state["plan"] = []
    return state

# class PlanStep(TypedDict):
#     id: int
#     type: str          # "browser_step" | "logic_step"
#     goal: str
#     success_criteria: str

# def planner_node(state: dict) -> dict:
#     """
#     Stub planner: takes an objective string and outputs a static plan.
#     Later this will be replaced with an LLM-based planner.
#     """
#     objective = state.get("objective", "No objective provided")

#     # Fake plan for now, hardcoded
#     plan: List[PlanStep] = [
#         {
#             "id": 1,
#             "type": "browser_step",
#             "goal": "Open https://example.com",
#             "success_criteria": "Page title is 'Example Domain'",
#         },
#         {
#             "id": 2,
#             "type": "logic_step",
#             "goal": "Record test result into a log file",
#             "success_criteria": "Log file created with status",
#         },
#     ]

#     state["plan"] = plan
#     return state
