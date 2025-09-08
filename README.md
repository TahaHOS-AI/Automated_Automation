# Automated Automation 🚀

An experimental framework for **self-planning, self-generating, and self-validating** automated tests using:

- 🧠 **LLMs** for planning & test generation
- 🎭 **Playwright + Pytest** for running browser tests
- 🔁 **Validator (reflection agent)** for fixing generated code
- 📊 **Allure** for reporting & dashboards

---

## 📂 Project Structure

```
app/
  graph/
    compile.py    # Main workflow runner (planner → generator → validator → runner)
    planner.py    # Decomposes objectives into executable steps
    generator.py  # Generates Playwright tests from plan
    validator.py  # Validates & fixes generated test scripts
    state.py      # Shared state definition
artifacts/        # Auto-generated tests, reports, and traces
tests/            # Manual or baseline test cases
```

---

## 🛠 Setup

### 1. Clone & install
```bash
git clone <your-repo-url>
cd <repo-name>
python -m venv automation_venv
source automation_venv/bin/activate   # or .\automation_venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### 2. Install Playwright browsers
```bash
playwright install
```

### 3. Install Allure (for reports)
- [Download Allure CLI](https://allurereport.org/docs/gettingstarted-installation/)  
- Or use [Scoop](https://scoop.sh/) on Windows:
  ```bash
  scoop install allure
  ```

---

## ▶️ Usage

Run the main workflow:

```bash
python -m app.graph.compile
```

This will:
1. Take your **objective** (e.g. *“Open example.com and verify the title”*).
2. Generate a test plan using an LLM (Ollama).
3. Generate Playwright tests from the plan.
4. Validate/fix the test with a reflection agent.
5. Execute the test using Pytest.
6. Save reports, traces, and artifacts.

---

## 📊 Viewing Reports

After running tests, generate an Allure report:

```bash
allure serve artifacts/allure-results
```
