# file: app/graph/validator.py

import pathlib
from langchain_ollama import ChatOllama
from langchain.prompts import ChatPromptTemplate
import re
from app.graph.state import State

llm = ChatOllama(model="gemma2:2b", temperature=0)

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a senior QA engineer. Review Playwright pytest scripts."),
    ("human", "Here is the generated script:\n\n{script}\n\n"
              "Check for errors, bad imports, wrong Playwright usage, or invalid pytest code.\n"
              "If there are problems, FIX them and return the corrected script.\n"
              "If it's valid, return it unchanged.\n"
              "Return ONLY Python code, no explanations or markdown.")
])

# def validator_node(state: State) -> State:
#     script = state.get("script_code", "")
#     if not script:
#         return state

#     chain = prompt | llm
#     response = chain.invoke({"script": script})
#     reviewed_code = response.content.strip()

#     # Strip accidental markdown
#     reviewed_code = re.sub(r"^```(python)?", "", reviewed_code)
#     reviewed_code = re.sub(r"```$", "", reviewed_code).strip()

#     state["script_code"] = reviewed_code
#     return state
def validate_playwright_code(code: str) -> list:
    """Validate Playwright code and return list of issues found."""
    issues = []

    # Check required imports
    if "import pytest" not in code:
        issues.append("Missing pytest import")
    if "from playwright.sync_api import Page, expect" not in code:
        issues.append("Missing Playwright imports")

    # Check for common mistakes
    if "page = Page(" in code:
        issues.append("Manual Page object creation - should use page fixture")
    if "assert page." in code:
        issues.append("Using assert instead of expect() for page assertions")
    if "page.title" in code and "expect(" not in code:
        issues.append("Direct page.title access without expect()")

    # Check test function signature
    if "def test_" in code and "page: Page" not in code:
        issues.append("Test function missing page: Page parameter")

    return issues

def validator_node(state: State) -> State:
    script = state.get("script_code", "")
    script_path = state.get("script_path")

    if not script or not script_path:
        return state

    # First, do basic validation
    issues = validate_playwright_code(script)

    if issues:
        # If there are issues, enhance the prompt with specific guidance
        enhanced_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a senior QA engineer specializing in Playwright. Fix the following issues in this test script:"),
            ("human", f"Issues found:\n" + "\n".join(f"- {issue}" for issue in issues) +
                      f"\n\nScript to fix:\n{script}\n\nReturn ONLY the corrected Python code.")
        ])
        chain = enhanced_prompt | llm
        response = chain.invoke({})
    else:
        # Use original prompt for general review
        chain = prompt | llm
        response = chain.invoke({"script": script})

    reviewed_code = response.content.strip()

    # Remove accidental markdown fences
    reviewed_code = re.sub(r"^```(python)?", "", reviewed_code, flags=re.MULTILINE)
    reviewed_code = re.sub(r"```$", "", reviewed_code, flags=re.MULTILINE).strip()

    # Final validation
    final_issues = validate_playwright_code(reviewed_code)
    if final_issues:
        # If still issues after LLM review, apply manual fixes
        reviewed_code = apply_manual_fixes(reviewed_code, final_issues)

    # Overwrite the script file with the reviewed version
    path = pathlib.Path(script_path)
    path.write_text(reviewed_code, encoding="utf-8")

    # Update state
    state["script_code"] = reviewed_code
    return state

def apply_manual_fixes(code: str, issues: list) -> str:
    """Apply manual fixes for common issues."""
    lines = code.split('\n')
    fixed_lines = []

    for line in lines:
        # Fix missing imports
        if "import pytest" not in code and "def test_" in line:
            fixed_lines.insert(0, "import pytest")
            fixed_lines.insert(1, "from playwright.sync_api import Page, expect")
            fixed_lines.insert(2, "")

        # Fix manual Page creation
        if "page = Page(" in line:
            continue  # Remove this line

        # Fix assert to expect
        if "assert page." in line:
            line = line.replace("assert page.", "expect(page).to_have_")
            if "title" in line:
                line = line.replace("to_have_title(", "to_have_title(")

        fixed_lines.append(line)

    return '\n'.join(fixed_lines)
