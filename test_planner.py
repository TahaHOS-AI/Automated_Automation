#!/usr/bin/env python3
"""
Test script for the planner node
Run this to test the planner independently
"""

import json
from app.graph.planner import planner_node
from app.graph.state import State

def test_planner():
    """Test the planner with a sample objective."""

    # Test case 1: Simple objective
    print("=== Test 1: Simple Login Objective ===")
    state1: State = {
        "objective": "Login to LinkedIn and verify dashboard loads"
    }

    result1 = planner_node(state1)
    print("Generated Plan:")
    print(json.dumps(result1["plan"], indent=2))
    print()

    # Test case 2: More complex objective
    print("=== Test 2: Complex E-commerce Objective ===")
    state2: State = {
        "objective": "Navigate to Amazon, search for 'laptop', filter by price under $1000, add first result to cart, and verify cart total"
    }

    result2 = planner_node(state2)
    print("Generated Plan:")
    print(json.dumps(result2["plan"], indent=2))
    print()

    # Test case 3: Empty objective
    print("=== Test 3: Empty Objective ===")
    state3: State = {
        "objective": ""
    }

    result3 = planner_node(state3)
    print("Generated Plan:")
    print(json.dumps(result3["plan"], indent=2))

if __name__ == "__main__":
    test_planner()
