# app/graph/planner.py

import re
import json
from typing import List, Dict, Any
from langchain.prompts import ChatPromptTemplate
from app.graph.state import State
from app.llm_provider import ollama_llm

# Initialize LLM
llm = ollama_llm

# Prompt template for planning
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a planner that decomposes user objectives into executable browser automation steps. You must generate valid JSON with all required fields and focus ONLY on the specific objective provided."),
    ("human", "OBJECTIVE: {objective}\n\n"
              "Create a step-by-step plan to accomplish EXACTLY this objective using browser automation.\n\n"
              "MANDATORY: Return ONLY valid JSON in this exact format with ALL required fields:\n"
              "[{{\"id\": 1, \"type\": \"browser_step\", \"step\": \"[specific action from objective]\", \"success_criteria\": \"[how to verify success]\"}}, "
              "{{\"id\": 2, \"type\": \"logic_step\", \"step\": \"[another specific action]\", \"success_criteria\": \"[verification method]\"}}]\n\n"
              "CRITICAL REQUIREMENTS:\n"
              "- EVERY step MUST have ALL FOUR fields: id (number), type, step (description), success_criteria\n"
              "- type must be either \"browser_step\" or \"logic_step\"\n"
              "- step field contains SPECIFIC actions that directly accomplish the objective\n"
              "- success_criteria describes MEASURABLE verification of the step's success\n"
              "- DO NOT include generic steps like 'Open Chrome browser'\n"
              "- DO NOT use placeholder examples - use actions SPECIFIC to the objective\n"
              "- Extract actual website names, actions, and elements from the objective\n"
              "- Break down into 2-4 concrete steps that directly implement the objective\n"
              "- Return ONLY the JSON array - no markdown, no explanations, no extra text")
])

def clean_llm_response(raw_output: str) -> str:
    """Clean and prepare LLM response for JSON parsing."""
    # Strip markdown code blocks
    if raw_output.startswith("```json"):
        raw_output = raw_output[7:]
    if raw_output.endswith("```"):
        raw_output = raw_output[:-3]
    raw_output = raw_output.strip()

    # Fix common JSON issues
    raw_output = re.sub(r',\s*]', ']', raw_output)  # Remove trailing commas before ]
    raw_output = re.sub(r',\s*}', '}', raw_output)  # Remove trailing commas before }

    # Extract only the JSON part if there's extra content
    # Look for the first complete JSON array/object
    json_start = raw_output.find('[')
    if json_start != -1:
        # Find the matching closing bracket
        bracket_count = 0
        for i, char in enumerate(raw_output[json_start:], json_start):
            if char == '[':
                bracket_count += 1
            elif char == ']':
                bracket_count -= 1
                if bracket_count == 0:
                    return raw_output[json_start:i+1]

    return raw_output

def validate_plan(plan: List[Dict[str, Any]]) -> bool:
    """Validate that the plan has the correct structure."""
    if not isinstance(plan, list):
        raise ValueError("Plan must be a list")

    for i, step in enumerate(plan):
        if not isinstance(step, dict):
            raise ValueError(f"Step {i} must be a dictionary")

        required_fields = ["id", "type", "step", "success_criteria"]
        for field in required_fields:
            if field not in step:
                raise ValueError(f"Step {i} missing required field: {field}")

        if step["type"] not in ["browser_step", "logic_step"]:
            raise ValueError(f"Step {i} type must be 'browser_step' or 'logic_step'")

    return True

def create_fallback_plan(objective: str) -> List[Dict[str, Any]]:
    """Create a simple fallback plan when LLM fails."""
    return [{
        "id": 1,
        "type": "browser_step",
        "step": f"Execute objective: {objective}",
        "success_criteria": "Test completes successfully"
    }]

def generate_plan_with_llm(objective: str) -> List[Dict[str, Any]]:
    """Generate a plan using the LLM with retries."""
    max_retries = 3

    for attempt in range(max_retries):
        try:
            # Run LLM
            chain = prompt | llm
            response = chain.invoke({"objective": objective})
            raw_output = response.content.strip()

            # Clean response
            cleaned_output = clean_llm_response(raw_output)

            # Parse JSON
            plan = json.loads(cleaned_output)

            # Validate plan
            validate_plan(plan)

            return plan

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            print(f"(planner_node) -> Attempt {attempt + 1} failed. Error: {e}")
            print(f"(planner_node) -> Raw LLM output: {raw_output[:200]}...")
            if attempt == max_retries - 1:
                # Return fallback plan on final failure
                print(f"(planner_node) -> Failed to generate valid plan after {max_retries} attempts. Using fallback.")
                return create_fallback_plan(objective)
            # Continue to next retry

    # Should not reach here
    return []

def planner_node(state: State) -> State:
    """Main planner node that generates a JSON plan from the objective."""
    objective = state.get("objective", "")
    if not objective:
        state["plan"] = []
        return state

    # Generate plan using LLM
    plan = generate_plan_with_llm(objective)

    state["plan"] = plan
    return state
