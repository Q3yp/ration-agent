"""Command line helper for querying USDA FoodData Central."""

from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from utils.usda_client import USDAClient, format_nutrients


def _print_json(data):
    print(json.dumps(data, indent=2, ensure_ascii=False))


def cmd_search(args: argparse.Namespace) -> int:
    client = USDAClient()
    response = client.search_foods(
        args.query,
        data_type=args.data_type,
        page_size=args.limit,
        page_number=args.page,
        require_all_words=not args.fuzzy,
    )

    if args.json:
        _print_json(response)
        return 0

    foods = response.get("foods", [])
    if not foods:
        print("No foods found.")
        return 0

    for food in foods:
        nutrients = format_nutrients(food.get("foodNutrients", []), args.nutrients)
        nutrient_summary = ", ".join(f"{n['name']}: {n['amount']} {n['unit']}" for n in nutrients)
        print(f"FDC {food.get('fdcId')}: {food.get('description')} [{food.get('dataType')}]")
        if nutrient_summary:
            print(f"  Nutrients: {nutrient_summary}")
        print()

    return 0


def cmd_details(args: argparse.Namespace) -> int:
    client = USDAClient()
    data = client.get_food(args.fdc_id)

    if args.json:
        _print_json(data)
        return 0

    nutrients = format_nutrients(data.get("foodNutrients", []), args.nutrients)
    print(f"FDC ID: {data.get('fdcId')}")
    print(f"Description: {data.get('description')}")
    print(f"Data Type: {data.get('dataType')}")
    print(f"Category: {data.get('foodCategory')}")
    print("Nutrients:")
    if nutrients:
        for nutrient in nutrients:
            print(f"  - {nutrient['name']}: {nutrient['amount']} {nutrient['unit']}")
    else:
        print("  (none)")

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="USDA FoodData helper")
    sub = parser.add_subparsers(dest="command", required=True)

    search = sub.add_parser("search", help="Search for foods")
    search.add_argument("query", help="Search phrase")
    search.add_argument("--limit", type=int, default=10, help="Max number of results (default 10)")
    search.add_argument("--page", type=int, default=1, help="Page number (default 1)")
    search.add_argument(
        "--data-type",
        action="append",
        dest="data_type",
        help="Optional USDA data type filters (can be provided multiple times)",
    )
    search.add_argument(
        "--nutrient",
        action="append",
        dest="nutrients",
        help="Only show these nutrient names in summaries",
    )
    search.add_argument("--fuzzy", action="store_true", help="Allow partial word matches")
    search.add_argument("--json", action="store_true", help="Print raw JSON response")
    search.set_defaults(func=cmd_search)

    details = sub.add_parser("details", help="Fetch food details for an FDC ID")
    details.add_argument("fdc_id", type=int, help="FDC identifier")
    details.add_argument(
        "--nutrient",
        action="append",
        dest="nutrients",
        help="Only show these nutrient names",
    )
    details.add_argument("--json", action="store_true", help="Print raw JSON response")
    details.set_defaults(func=cmd_details)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

