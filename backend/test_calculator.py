#!/usr/bin/env python3
"""
Test script for the calculator tool
"""

import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

from utils.tools import calculate

def test_calculator():
    """Test various calculator expressions"""

    test_cases = [
        # Basic arithmetic
        ("2 + 2", "Result: 4"),
        ("10 - 3", "Result: 7"),
        ("5 * 6", "Result: 30"),
        ("15 / 3", "Result: 5"),
        ("2 ** 3", "Result: 8"),
        ("17 % 5", "Result: 2"),
        ("17 // 5", "Result: 3"),

        # Order of operations
        ("2 + 2 * 3", "Result: 8"),
        ("(2 + 2) * 3", "Result: 12"),

        # Mathematical functions
        ("sqrt(16)", "Result: 4"),
        ("abs(-5)", "Result: 5"),
        ("round(3.7)", "Result: 4"),
        ("min([1, 2, 3])", "Result: 1"),
        ("max([1, 2, 3])", "Result: 3"),
        ("sum([1, 2, 3, 4, 5])", "Result: 15"),

        # Constants
        ("pi", "Result: 3.141593"),
        ("e", "Result: 2.718282"),

        # Multi-line with variables
        ("x = 5\ny = 10\nx * y", "Result: 50"),
        ("dm = 25\ntotal = 100\nresult = (dm / 100) * total\nresult", "Result: 25"),

        # Percentage calculations (useful for nutrition)
        ("(45 / 100) * 250", "Result: 112.5"),

        # Error cases
        ("1 / 0", "Error: Division by zero"),
        ("invalid_function(5)", "Error: Function 'invalid_function' not allowed"),
        ("import os", "Syntax Error"),
    ]

    print("Testing Calculator Tool")
    print("=" * 60)

    passed = 0
    failed = 0

    for expression, expected_contains in test_cases:
        result = calculate.invoke({"expression": expression})

        # Check if expected string is in result
        if expected_contains in result:
            print(f"✓ PASS: {expression}")
            print(f"  Result: {result}")
            passed += 1
        else:
            print(f"✗ FAIL: {expression}")
            print(f"  Expected to contain: {expected_contains}")
            print(f"  Got: {result}")
            failed += 1
        print()

    print("=" * 60)
    print(f"Test Results: {passed} passed, {failed} failed")

    return failed == 0


if __name__ == "__main__":
    success = test_calculator()
    sys.exit(0 if success else 1)
