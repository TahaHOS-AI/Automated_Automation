# app/graph/validator.py

import pathlib
from langchain.prompts import ChatPromptTemplate
import re
from typing import List
from app.graph.state import State
from app.llm_provider import ollama_llm

# Initialize LLM
llm = ollama_llm

# Prompt for general code review
review_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a senior QA engineer. Review Playwright pytest scripts."),
    ("human", "Here is the generated script:\n\n{script}\n\n"
              "Check for errors, bad imports, wrong Playwright usage, or invalid pytest code.\n"
              "If there are problems, FIX them and return the corrected script.\n"
              "If it's valid, return it unchanged.\n"
              "Return ONLY Python code, no explanations or markdown.")
])

def clean_code_response(raw_output: str) -> str:
    """Clean LLM response for code validation."""
    # Remove markdown code blocks
    raw_output = re.sub(r"^```(python)?", "", raw_output, flags=re.MULTILINE)
    raw_output = re.sub(r"```$", "", raw_output, flags=re.MULTILINE).strip()
    return raw_output

def validate_playwright_code(code: str) -> List[str]:
    """Validate Playwright code and return list of issues found."""
    issues = []

    # Check required imports
    if "import pytest" not in code:
        issues.append("Missing pytest import")
    if "from playwright.sync_api import Page, expect" not in code:
        issues.append("Missing Playwright imports")
    if "import agentql" not in code:
        issues.append("Missing AgentQL import")

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

def apply_manual_fixes(code: str, issues: List[str]) -> str:
    """Apply manual fixes for common issues."""
    lines = code.split('\n')
    fixed_lines = []
    imports_added = False

    for line in lines:
        # Add missing imports at the beginning
        if not imports_added and "def test_" in line:
            if "import pytest" not in code:
                fixed_lines.append("import pytest")
            if "from playwright.sync_api import Page, expect" not in code:
                fixed_lines.append("from playwright.sync_api import Page, expect")
            if "import agentql" not in code:
                fixed_lines.append("import agentql")
            fixed_lines.append("")
            imports_added = True

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

def review_code_with_llm(script: str, issues: List[str] = None) -> str:
    """Review and fix code using LLM with retries."""
    max_retries = 3

    for attempt in range(max_retries):
        try:
            if issues:
                # Use enhanced prompt for fixing specific issues
                enhanced_prompt = ChatPromptTemplate.from_messages([
                    ("system", "You are a senior QA engineer specializing in Playwright. Fix the following issues in this test script:"),
                    ("human", f"Issues found:\n" + "\n".join(f"- {issue}" for issue in issues) +
                              f"\n\nScript to fix:\n{script}\n\nReturn ONLY the corrected Python code.")
                ])
                chain = enhanced_prompt | llm
                response = chain.invoke({})
            else:
                # Use general review prompt
                chain = review_prompt | llm
                response = chain.invoke({"script": script})

            reviewed_code = clean_code_response(response.content)

            # Validate the reviewed code
            final_issues = validate_playwright_code(reviewed_code)
            if not final_issues:
                return reviewed_code  # Success!

        except Exception as e:
            print(f"(validator_node) -> LLM review attempt {attempt + 1} failed: {e}")

    # All retries failed
    print(f"(validator_node) -> LLM code review failed after {max_retries} attempts.")
    print("(validator_node) -> Would you like to proceed with manual fixes or skip validation?")

    return None  # Indicate failure

def validator_node(state: State) -> State:
    """Validate and fix generated Playwright code."""
    script = state.get("script_code", "")
    script_path = state.get("script_path")

    if not script or not script_path:
        return state

    print("(validator_node) -> Validating generated Playwright code...")

    # First, do basic validation
    issues = validate_playwright_code(script)
    print(f"(validator_node) -> Found {len(issues)} validation issues")

    if issues:
        print("(validator_node) -> Issues found, attempting LLM repair...")
        reviewed_code = review_code_with_llm(script, issues)

        if reviewed_code is None:
            # LLM repair failed, ask user what to do
            print("(validator_node) -> LLM repair failed. Applying manual fixes...")
            reviewed_code = apply_manual_fixes(script, issues)

            # Check if manual fixes resolved all issues
            remaining_issues = validate_playwright_code(reviewed_code)
            if remaining_issues:
                print(f"(validator_node) -> Manual fixes applied, but {len(remaining_issues)} issues remain")
                print("(validator_node) -> Proceeding with partially fixed code")
    else:
        print("(validator_node) -> Code validation passed, doing final review...")
        reviewed_code = review_code_with_llm(script)

        if reviewed_code is None:
            # LLM review failed but code was originally valid
            print("(validator_node) -> LLM review failed, keeping original code")
            reviewed_code = script

    # Save the reviewed code
    path = pathlib.Path(script_path)
    path.write_text(reviewed_code, encoding="utf-8")

    # Update state
    state["script_code"] = reviewed_code
    print("(validator_node) -> Code validation and review complete")
    return state
