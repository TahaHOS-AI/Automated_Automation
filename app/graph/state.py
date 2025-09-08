from typing import TypedDict, List, Dict, Any

class State(TypedDict, total=False):
    objective: str
    plan: List[Dict[str, Any]]
    script_path: str
    script_code: str
    result: Dict[str, Any]
