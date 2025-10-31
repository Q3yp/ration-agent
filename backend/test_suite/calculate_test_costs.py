#!/usr/bin/env python3
"""
Calculate total tokens and costs for test cases using Claude Haiku 4.5 model.
Only counts test cases that have Excel output files (complete tests).
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Tuple

# Claude Haiku 4.5 pricing (per 1M tokens)
# Source: https://www.anthropic.com/api#pricing
HAIKU_4_5_INPUT_PRICE = 1.00  # $1.00 per 1M input tokens
HAIKU_4_5_OUTPUT_PRICE = 5.00  # $5.00 per 1M output tokens


def has_excel_output(test_case_dir: Path) -> bool:
    """Check if test case has Excel output file (indicating completion)."""
    excel_files = list(test_case_dir.glob("*.xlsx"))
    # Exclude the default feedbase file
    excel_files = [f for f in excel_files if "default" not in f.name.lower()]
    return len(excel_files) > 0


def extract_tokens_from_messages(messages_file: Path) -> Tuple[int, int, int]:
    """Extract input, output, and total tokens from messages.json file."""
    with open(messages_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    total_input = 0
    total_output = 0

    # Iterate through all messages
    for message in data.get("messages", []):
        # Only count AI messages with usage_metadata
        if message.get("type") == "ai" and "usage_metadata" in message:
            usage = message["usage_metadata"]
            total_input += usage.get("input_tokens", 0)
            total_output += usage.get("output_tokens", 0)

    total_tokens = total_input + total_output
    return total_input, total_output, total_tokens


def calculate_cost(input_tokens: int, output_tokens: int) -> float:
    """Calculate cost in USD for given token counts."""
    input_cost = (input_tokens / 1_000_000) * HAIKU_4_5_INPUT_PRICE
    output_cost = (output_tokens / 1_000_000) * HAIKU_4_5_OUTPUT_PRICE
    return input_cost + output_cost


def analyze_test_cases(base_dir: Path) -> Dict:
    """Analyze all test cases and calculate token usage and costs."""
    results = {
        "complete_tests": [],
        "incomplete_tests": [],
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "total_tokens": 0,
        "total_cost": 0.0,
        "complete_count": 0,
        "incomplete_count": 0,
    }

    # Find all messages.json files
    for messages_file in base_dir.rglob("messages.json"):
        test_case_dir = messages_file.parent
        scenario_name = test_case_dir.name
        category = test_case_dir.parent.name  # success/failed
        animal_type = test_case_dir.parent.parent.name  # beef_cattle, etc.

        # Check if test has Excel output
        has_output = has_excel_output(test_case_dir)

        # Extract token counts
        input_tokens, output_tokens, total_tokens = extract_tokens_from_messages(messages_file)
        cost = calculate_cost(input_tokens, output_tokens)

        test_info = {
            "scenario": scenario_name,
            "category": category,
            "animal_type": animal_type,
            "path": str(test_case_dir.relative_to(base_dir)),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "cost": cost,
        }

        if has_output:
            results["complete_tests"].append(test_info)
            results["total_input_tokens"] += input_tokens
            results["total_output_tokens"] += output_tokens
            results["total_tokens"] += total_tokens
            results["total_cost"] += cost
            results["complete_count"] += 1
        else:
            results["incomplete_tests"].append(test_info)
            results["incomplete_count"] += 1

    # Calculate average cost per complete test
    if results["complete_count"] > 0:
        results["average_cost_per_test"] = results["total_cost"] / results["complete_count"]
        results["average_tokens_per_test"] = results["total_tokens"] / results["complete_count"]
    else:
        results["average_cost_per_test"] = 0.0
        results["average_tokens_per_test"] = 0

    return results


def print_results(results: Dict):
    """Print analysis results in a formatted way."""
    print("=" * 80)
    print("TEST CASE COST ANALYSIS - Claude Haiku 4.5")
    print("=" * 80)
    print()

    print("PRICING:")
    print(f"  Input tokens:  ${HAIKU_4_5_INPUT_PRICE:.2f} per 1M tokens")
    print(f"  Output tokens: ${HAIKU_4_5_OUTPUT_PRICE:.2f} per 1M tokens")
    print()

    print("COMPLETE TESTS (with Excel output):")
    print(f"  Count: {results['complete_count']}")
    print(f"  Total input tokens:  {results['total_input_tokens']:,}")
    print(f"  Total output tokens: {results['total_output_tokens']:,}")
    print(f"  Total tokens:        {results['total_tokens']:,}")
    print(f"  Total cost:          ${results['total_cost']:.4f}")
    print()

    print("AVERAGES PER COMPLETE TEST:")
    print(f"  Average tokens: {results['average_tokens_per_test']:,.0f}")
    print(f"  Average cost:   ${results['average_cost_per_test']:.4f}")
    print()

    print("INCOMPLETE TESTS (no Excel output):")
    print(f"  Count: {results['incomplete_count']}")
    print()

    # Sort complete tests by cost (descending)
    sorted_tests = sorted(results['complete_tests'], key=lambda x: x['cost'], reverse=True)

    print("TOP 10 MOST EXPENSIVE COMPLETE TESTS:")
    print(f"{'Rank':<6} {'Scenario':<40} {'Tokens':>12} {'Cost':>10}")
    print("-" * 80)
    for i, test in enumerate(sorted_tests[:10], 1):
        print(f"{i:<6} {test['scenario']:<40} {test['total_tokens']:>12,} ${test['cost']:>9.4f}")
    print()

    print("INCOMPLETE TESTS (excluded from totals):")
    if results['incomplete_tests']:
        for test in results['incomplete_tests']:
            print(f"  - {test['path']}")
    else:
        print("  (none)")
    print()

    print("=" * 80)


def main():
    # Get base directory
    base_dir = Path(__file__).parent / "test_cases"

    if not base_dir.exists():
        print(f"Error: test_cases directory not found at {base_dir}")
        return

    print(f"Analyzing test cases in: {base_dir}")
    print()

    results = analyze_test_cases(base_dir)
    print_results(results)

    # Save detailed results to JSON
    output_file = Path(__file__).parent / "test_cost_analysis.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"Detailed results saved to: {output_file}")


if __name__ == "__main__":
    main()
