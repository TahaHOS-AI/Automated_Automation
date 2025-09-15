# app/graph/plan_validator.py

import json
from typing import List, Dict, Any
from langchain.prompts import ChatPromptTemplate
from app.graph.state import State
from app.llm_provider import ollama_llm

# Initialize LLM
llm = ollama_llm

# Prompt for plan validation and reflection
plan_review_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a senior QA engineer reviewing automation test plans. Your job is to validate that the plan correctly implements the given objective."),
    ("human", "OBJECTIVE: {objective}\n\n"
              "GENERATED PLAN:\n{plan}\n\n"
              "REVIEW REQUIREMENTS:\n"
              "- Does the plan directly accomplish the objective?\n"
              "- Are all steps relevant to the objective?\n"
              "- Do the steps follow a logical sequence?\n"
              "- Are there any missing critical steps?\n"
              "- Are the success criteria measurable?\n\n"
              "If the plan is GOOD, respond with: VALID\n"
              "If the plan needs IMPROVEMENT, respond with: INVALID\n\n"
              "Then provide specific feedback on what's wrong and how to fix it.\n\n"
              "Format: VALID/INVALID\n[Your detailed feedback]")
])

def validate_plan_with_llm(objective: str, plan: List[Dict[str, Any]]) -> tuple[bool, str]:
    """Validate the plan using LLM and return (is_valid, feedback)."""
    max_retries = 2

    for attempt in range(max_retries):
        try:
            chain = plan_review_prompt | llm
            response = chain.invoke({
                "objective": objective,
                "plan": json.dumps(plan, indent=2)
            })

            result = response.content.strip()

            # Parse the response
            if result.upper().startswith("VALID"):
                return True, "Plan validation passed"
            elif result.upper().startswith("INVALID"):
                # Extract feedback after INVALID
                feedback = result[6:].strip() if len(result) > 6 else "Plan needs improvement"
                return False, feedback
            else:
                # Unexpected format, try again
                if attempt == max_retries - 1:
                    return False, f"Unexpected validation response format: {result[:100]}..."

        except Exception as e:
            if attempt == max_retries - 1:
                return False, f"Plan validation failed: {str(e)}"

    return False, "Plan validation failed after retries"

def plan_validator_node(state: State) -> State:
    """Validate and potentially improve the generated plan."""
    objective = state.get("objective", "")
    plan = state.get("plan", [])

    if not objective or not plan:
        return state

    print("(plan_validator_node) -> Reviewing generated plan...")

    # Validate the plan
    is_valid, feedback = validate_plan_with_llm(objective, plan)

    if is_valid:
        print("(plan_validator_node) -> Plan validation passed ✓")
        print(f"(plan_validator_node) -> Feedback: {feedback}")
        return state
    else:
        print("(plan_validator_node) -> Plan validation failed ✗")
        print(f"(plan_validator_node) -> Issues: {feedback}")

        # For now, we'll proceed with the plan but mark it as potentially problematic
        # In a full implementation, we could regenerate the plan or ask for user input
        state["plan_validation_feedback"] = feedback
        state["plan_potentially_invalid"] = True

        print("(plan_validator_node) -> Proceeding with current plan despite issues")
        return state
