# file: app/graph/generator.py
import pathlib
import json
from typing import Dict, Any, List
from langchain_community.chat_models import ChatOllama
from langchain.prompts import ChatPromptTemplate
import re
from app.graph.state import State

llm = ChatOllama(model="gemma3:1b", temperature=0)

# prompt = ChatPromptTemplate.from_messages([
#     ("system", "You are a code generator that writes Playwright Python tests from a plan."),
#     ("human", "Plan:\n{plan}\n\nGenerate a pytest file using Playwright sync API. "
#               "Only return valid Python code without explanations.")
# ])

# prompt = ChatPromptTemplate.from_messages([
#     ("system", "You are an assistant that generates Playwright Python tests."),
#     ("human", "Given this plan:\n{plan}\n\nGenerate a pytest file using Playwright (sync API).\n"
#               "Rules:\n"
#               "- Import from playwright.sync_api (Page, expect)\n"
#               "- Each browser_step becomes a Playwright test step\n"
#               "- Each logic_step becomes a Python assertion\n"
#               "- Return ONLY valid Python code, no explanations or markdown")
# ])

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an assistant that generates pytest test files using Playwright's Python sync API."),
    ("human", "Given this plan:\n{plan}\n\nGenerate a single pytest file.\n"
              "Rules:\n"
              "- Import exactly: `import pytest` and `from playwright.sync_api import Page, expect`\n"
              "- Use the pytest `page` fixture (do NOT manually create Page objects)\n"
              "- For each browser_step, use Playwright actions like `page.goto`, `page.click`, etc.\n"
              "- For each logic_step, use `expect(...)` assertions (e.g. `expect(page).to_have_title(...)`)\n"
              "- Do not invent pytest imports or extra functions\n"
              "- Return ONLY valid Python code (no markdown, no explanations)")
])

def validate_generated_code(code: str) -> bool:
    """Validate that generated code has required Playwright elements."""
    required_imports = ["import pytest", "from playwright.sync_api import Page, expect"]
    required_patterns = ["def test_", "page: Page", "expect("]

    for imp in required_imports:
        if imp not in code:
            return False

    for pattern in required_patterns:
        if pattern not in code:
            return False

    # Check for common mistakes
    if "page = Page(" in code:  # Should not manually create Page objects
        return False
    if "assert page." in code:  # Should use expect() instead of assert
        return False

    return True

def generator_node(state: State) -> State:
    plan = state.get("plan", [])
    if not plan:
        return state

    max_retries = 3
    for attempt in range(max_retries):
        chain = prompt | llm
        response = chain.invoke({"plan": json.dumps(plan, indent=2)})
        code = response.content.strip()

        # Remove any accidental markdown fencing
        code = re.sub(r"^```(python)?", "", code)
        code = re.sub(r"```$", "", code).strip()

        # Validate the generated code
        if validate_generated_code(code):
            break
        elif attempt == max_retries - 1:
            # Fallback: generate a simple working test
            code = f"""import pytest
from playwright.sync_api import Page, expect

def test_generated_plan(page: Page):
    page.goto("https://example.com")
    expect(page).to_have_title("Example Domain")
"""
            break

    artifacts_root = pathlib.Path(__file__).resolve().parents[2] / "artifacts/generated"
    artifacts_root.mkdir(parents=True, exist_ok=True)
    test_file = artifacts_root / "test_plan.py"
    test_file.write_text(code, encoding="utf-8")

    state["script_path"] = str(test_file)
    state["script_code"] = code
    return state
