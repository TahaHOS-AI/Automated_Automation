# file: app/graph/generator.py
import pathlib
import json
from typing import Dict, Any, List
# from langchain_ollama import ChatOllama
from langchain.prompts import ChatPromptTemplate
import re
from datetime import datetime
from app.graph.state import State

from app.llm_provider import gemini_llm, ollama_llm
import agentql

# Use Gemini if available, otherwise fall back to Ollama
if gemini_llm is not None:
    llm = gemini_llm
    print("(generator_node) -> Using Gemini for code generation")
else:
    llm = ollama_llm
    print("(generator_node) -> Using Ollama for code generation (Gemini unavailable)")

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an assistant that generates Python scripts using Playwright's sync_playwright context manager."),
    ("human", "Given this plan:\n{plan}\n\nGenerate a Python script using sync_playwright.\n"
              "Rules:\n"
              "- Start with: `from playwright.sync_api import sync_playwright`\n"
              "- Use: `with sync_playwright() as p:`\n"
              "- Launch browser with: `browser = p.chromium.launch(headless=False, slow_mo=1500)`\n"
              "- Create page with: `page = browser.new_page()`\n"
              "- For navigation: `page.goto('https://example.com', timeout=60000)`\n"
              "- For clicking: `page.query('button: Sign in').click()`\n"
              "- For typing: `page.query('input: Search').fill('text')`\n"
              "- For waiting/assertions: `page.wait_for_url('https://example.com')`\n"
              "- Take screenshots: `page.screenshot(path='./screenshot_step1.png')`\n"
              "- Use AgentQL natural language queries: `page.query('button: Submit form')`\n"
              "- AgentQL automatically finds elements by description\n"
              "- Add error handling: `try: ... except: print('Element not found')`\n"
              "- Add print statements to show progress\n"
              "- At the end, ask user to press Enter to close: `input('Press Enter to close browser...')`\n"
              "- Then close with: `browser.close()`\n"
              "- Return ONLY valid Python code (no markdown, no explanations)")
])

def validate_generated_code(code: str) -> bool:
    """Validate that generated code has required Playwright elements."""
    required_imports = ["from playwright.sync_api import sync_playwright"]
    required_patterns = ["with sync_playwright() as p:", "browser = p.chromium.launch", "page = browser.new_page()"]

    for imp in required_imports:
        if imp not in code:
            return False

    for pattern in required_patterns:
        if pattern not in code:
            return False

    # Check for common mistakes
    if "headless=True" in code:  # Should be headless=False for visibility
        return False

    return True

def generator_node(state: State) -> State:
    plan = state.get("plan", [])
    demonstrate = state.get("demonstrate", False)
    recorded_code = state.get("recorded_code", "")

    if not plan:
        return state

    # Generate unique execution folder
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    objective_slug = state.get("objective", "unknown")

    # Sanitize objective_slug for filesystem - remove/replace invalid characters
    import re
    objective_slug = re.sub(r'[<>:"/\\|?*]', '_', objective_slug)  # Replace invalid chars with _
    objective_slug = re.sub(r'[^\w\-_\.]', '_', objective_slug)    # Replace other non-word chars with _
    objective_slug = objective_slug.replace(" ", "_")[:30]        # Replace spaces and limit length

    execution_id = f"{objective_slug}_{timestamp}"

    # Create execution-specific folder
    artifacts_root = pathlib.Path(__file__).resolve().parents[2] / "artifacts"
    execution_folder = artifacts_root / "executions" / execution_id
    execution_folder.mkdir(parents=True, exist_ok=True)

    print(f"(generator_node) -> Created execution folder: {execution_id}")

    # Check if we should use codegen recording or LLM generation
    if demonstrate:
        print("(generator_node) -> Demonstrate mode: Using Playwright codegen for recording")
        code = handle_codegen_recording(plan, execution_folder)
    else:
        print("(generator_node) -> Generation mode: Using LLM to create Playwright script")
        result = generate_with_llm(plan, recorded_code, execution_folder)

        # Check if LLM generation failed and user needs to demonstrate
        if isinstance(result, dict) and result.get("generation_failed"):
            return result  # Return the state with failure flags

        # LLM generation succeeded
        code = result

    # Save the generated code with unique filename
    filename = f"automation_script.py"
    script_file = execution_folder / filename
    script_file.write_text(code, encoding="utf-8")

    state["script_path"] = str(script_file)
    state["execution_folder"] = str(execution_folder)
    print(f"(generator_node) -> Script saved to: {execution_folder}/{filename}")
    return state

def handle_codegen_recording(plan: List[Dict[str, Any]], execution_folder: pathlib.Path) -> str:
    """Handle browser recording using Playwright codegen."""
    print("(generator_node) -> Launching Playwright codegen for user demonstration...")
    print("📝 Instructions:")
    print("   1. A browser window will open")
    print("   2. Perform the actions you want to record")
    print("   3. Close the browser when done")
    print("   4. The recorded code will be saved")
    print()

    # Extract target URL from plan if available
    target_url = "https://example.com"  # Default
    for step in plan:
        step_desc = step.get("step", "").lower()
        if "navigate" in step_desc or "goto" in step_desc:
            # Try to extract URL from step description
            import re
            url_match = re.search(r'https?://[^\s\'"]+', step_desc)
            if url_match:
                target_url = url_match.group()
                break

    print(f"🎯 Starting recording on: {target_url}")
    print("🔄 Launching Playwright codegen...")

    try:
        # Launch Playwright codegen
        import subprocess
        cmd = [
            "playwright", "codegen",
            "--target", "python",
            "--output", "recorded_script.py",
            target_url
        ]

        print("💡 Perform your actions in the browser window that opens...")
        print("💡 Close the browser when you're done recording...")

        # Run codegen and wait for it to complete
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)  # 5 minute timeout

        if result.returncode == 0:
            print("✅ Recording completed successfully!")

            # Try to read the generated script
            recorded_file = pathlib.Path("recorded_script.py")
            if recorded_file.exists():
                recorded_code = recorded_file.read_text()
                recorded_file.unlink()  # Clean up the temp file

                # Convert the recorded pytest code to sync_playwright format
                converted_code = convert_recorded_code(recorded_code, plan)
                return converted_code
            else:
                print("⚠️  Recorded file not found, using template")
                return create_recording_template(plan)
        else:
            print(f"❌ Codegen failed: {result.stderr}")
            return create_recording_template(plan)

    except subprocess.TimeoutExpired:
        print("⏰ Recording timed out after 5 minutes")
        return create_recording_template(plan)
    except Exception as e:
        print(f"❌ Error during recording: {e}")
        return create_recording_template(plan)

def extract_imports_from_code(code: str) -> List[str]:
    """Extract all import statements from the recorded code."""
    imports = []

    # Find all import statements
    import_lines = re.findall(r'^(import\s+.+|from\s+.+import\s+.+)$', code, re.MULTILINE)

    for line in import_lines:
        line = line.strip()
        # Skip playwright-related imports as we'll handle them separately
        if 'playwright' not in line:
            imports.append(line)

    return imports

def convert_recorded_code(recorded_code: str, plan: List[Dict[str, Any]]) -> str:
    """Convert recorded pytest code to sync_playwright format."""
    print("(generator_node) -> Converting recorded code to sync_playwright format...")

    # Extract all imports from the recorded code
    extracted_imports = extract_imports_from_code(recorded_code)
    print(f"(generator_node) -> Found imports: {extracted_imports}")

    # Look for the run function pattern that Playwright codegen generates
    run_function_match = re.search(r'def run\(playwright: Playwright\) -> None:\n(.*?)(?=\n\n|\nwith sync_playwright|\Z)', recorded_code, re.DOTALL)

    if run_function_match:
        print("(generator_node) -> Found run function, extracting content...")
        run_content = run_function_match.group(1)

        # Remove the browser/context setup lines that we'll replace
        lines = run_content.split('\n')
        filtered_lines = []

        for line in lines:
            line = line.strip()
            # Skip the browser/context setup lines
            if any(skip_pattern in line for skip_pattern in [
                'browser = playwright.chromium.launch',
                'context = browser.new_context()',
                'page = context.new_page()',
                'context.close()',
                'browser.close()'
            ]):
                continue
            if line:  # Only add non-empty lines
                filtered_lines.append(line)

        # Join the filtered content
        actions_content = '\n    '.join(filtered_lines)

        # Build imports - start with playwright
        imports = ["from playwright.sync_api import sync_playwright"]

        # Add all extracted imports
        imports.extend(extracted_imports)

        # Join all imports
        imports_str = '\n'.join(imports)

        # Create the final script
        wrapper = f'''"""
Generated from user demonstration
Plan: {json.dumps(plan, indent=2)}
"""

{imports_str}

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=1500)
    page = browser.new_page()

    # Recorded actions
    {actions_content}

    print("\\n🎉 Automation completed successfully!")
    input("\\nPress Enter to close browser...")
    browser.close()
'''

        return wrapper

    else:
        print("(generator_node) -> Could not find run function, looking for other patterns...")

        # Try to find any function with page operations
        any_function_match = re.search(r'def \w+.*?:\n(.*?)(?=\n\n|\nwith sync_playwright|\Z)', recorded_code, re.DOTALL)
        if any_function_match:
            print("(generator_node) -> Found alternative function pattern...")
            function_content = any_function_match.group(1)

            # Clean up the content
            lines = function_content.split('\n')
            cleaned_lines = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#') and not any(skip in line for skip in [
                    'browser =', 'context =', 'page =', 'context.close()', 'browser.close()'
                ]):
                    cleaned_lines.append(line)

            actions_content = '\n    '.join(cleaned_lines)

            wrapper = f'''"""
Generated from user demonstration
Plan: {json.dumps(plan, indent=2)}
"""

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=1500)
    page = browser.new_page()

    # Recorded actions
    {actions_content}

    print("\\n🎉 Automation completed successfully!")
    input("\\nPress Enter to close browser...")
    browser.close()
'''

            return wrapper

        else:
            print("(generator_node) -> No function found, using template...")
            return create_recording_template(plan)

def create_recording_template(plan: List[Dict[str, Any]]) -> str:
    """Create a template when recording fails."""
    return f'''"""
Playwright script template for user demonstration.
Plan: {json.dumps(plan, indent=2)}

To complete this script:
1. Run: playwright codegen --target python https://target-website.com
2. Perform your actions in the browser
3. Copy the generated code and replace the TODO section below
"""

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=1500)
    page = browser.new_page()

    print("Starting automation...")

    # TODO: Replace this section with your recorded code
    page.goto("https://example.com")
    print("Navigated to example.com")

    # Add your recorded actions here
    # Example:
    # page.locator('input[name="q"]').fill("search term")
    # page.locator('input[name="q"]').press("Enter")

    print("Automation completed")

    input("Press Enter to close browser...")
    browser.close()
'''

def generate_with_llm(plan: List[Dict[str, Any]], recorded_code: str = "", execution_folder: pathlib.Path = None) -> str | dict:
    """Generate Playwright code using LLM."""
    max_retries = 3

    for attempt in range(max_retries):
        # Use the proper ChatPromptTemplate
        chain = prompt | llm

        # Prepare the input data
        input_data = {"plan": json.dumps(plan, indent=2)}
        if recorded_code:
            # If we have recorded code, include it in the prompt
            enhanced_plan = f"{json.dumps(plan, indent=2)}\n\nRecorded code to enhance:\n{recorded_code}"
            input_data = {"plan": enhanced_plan}

        response = chain.invoke(input_data)
        code = response.content.strip()

        # Remove any accidental markdown fencing
        code = re.sub(r"^```(python)?", "", code)
        code = re.sub(r"```$", "", code).strip()

        # Remove any validator prompt text that might be appended
        # Look for common patterns that indicate extra text
        extra_patterns = [
            r"\nCheck for errors.*",
            r"\nIf there are problems.*",
            r"\nIf it's valid.*",
            r"\nReturn ONLY.*"
        ]
        for pattern in extra_patterns:
            code = re.sub(pattern, "", code, flags=re.DOTALL)

        # Validate the generated code
        if validate_generated_code(code):
            return code  # Success!
        elif attempt == max_retries - 1:
            # LLM generation failed - return failure indicator
            print(f'(generator_node) -> LLM code generation failed after {max_retries} attempts.')
            print(f'(generator_node) -> Last response: {response.content[:200]}...')
            print('(generator_node) -> Would you like to switch to demonstrate mode (codegen)?')

            # Return failure indicator instead of modifying state
            return {
                "generation_failed": True,
                "needs_demonstration": True,
                "error_message": f"Failed to generate valid code after {max_retries} attempts"
            }

    # Should not reach here
    return ""
