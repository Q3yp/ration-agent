#!/usr/bin/env python3
"""
Extract NASEM 2021 Feed Library and convert to ration-agent feedbase format.

The NASEM feed data is from the CNM-University-of-Guelph/NASEM-Model-Python project
which is MIT licensed.

This script extracts ALL NASEM nutrient columns to ensure full compatibility
with the NASEM model calculations.

Usage:
    python scripts/extract_nasem_feeds.py [--validate] [--output FILENAME]
"""

import csv
import json
import sys
from pathlib import Path
from typing import Any

# Metadata columns (not nutrients but needed for feed identification)
METADATA_COLUMNS = ["Fd_Libr", "UID", "Fd_Index", "Fd_Name", "Fd_Category", "Fd_Type", "Fd_Locked"]

# Common dairy feeds to extract by category
TARGET_FEEDS = {
    # Forages - Legumes
    "Alfalfa meal": "alfalfa_meal",
    "Alfalfa hay, mid-maturity": "alfalfa_hay",
    "Alfalfa haylage, mid-maturity": "alfalfa_haylage",
    "Alfalfa silage, mid-maturity": "alfalfa_silage",
    "Clover hay, mid-maturity": "clover_hay",
    
    # Forages - Grasses
    "Grass hay, mid-maturity": "grass_hay",
    "Grass silage, mid-maturity": "grass_silage",
    "Orchardgrass hay, mid-maturity": "orchardgrass_hay",
    "Timothy hay, mid-maturity": "timothy_hay",
    "Bermudagrass hay, mid-maturity": "bermudagrass_hay",
    
    # Grain Crop Forages
    "Corn silage, typical": "corn_silage",
    "Corn silage, BMR": "corn_silage_bmr",
    "Sorghum silage": "sorghum_silage",
    "Wheat silage": "wheat_silage",
    "Oat silage": "oat_silage",
    "Barley silage": "barley_silage",
    
    # Energy Sources - Grains
    "Corn grain, dry ground": "corn_grain",
    "Corn grain, high moisture": "corn_grain_hm",
    "Corn grain, steam flaked": "corn_grain_sf",
    "Barley grain, dry rolled": "barley_grain",
    "Wheat grain": "wheat_grain",
    "Oats grain": "oats_grain",
    "Sorghum grain": "sorghum_grain",
    
    # Plant Protein Sources
    "Soybean meal, solvent, 48% CP": "soybean_meal_48",
    "Soybean meal, expeller": "soybean_meal_expeller",
    "Canola meal, solvent": "canola_meal",
    "Cottonseed meal, solvent": "cottonseed_meal",
    "Sunflower meal, solvent": "sunflower_meal",
    "Peanut meal, solvent": "peanut_meal",
    "Linseed meal, solvent": "linseed_meal",
    
    # By-Products
    "Distillers grains, corn, dry": "corn_ddgs",
    "Distillers grains, corn, wet": "corn_wdgs",
    "Brewers grains, wet": "brewers_grains_wet",
    "Brewers grains, dry": "brewers_grains_dry",
    "Beet pulp, dry": "beet_pulp_dry",
    "Beet pulp, wet": "beet_pulp_wet",
    "Wheat middlings": "wheat_middlings",
    "Wheat bran": "wheat_bran",
    "Corn gluten feed, dry": "corn_gluten_feed",
    "Corn gluten meal": "corn_gluten_meal",
    "Citrus pulp, dry": "citrus_pulp",
    "Soybean hulls": "soybean_hulls",
    "Cottonseed, whole with lint": "cottonseed_whole",
    "Hominy feed": "hominy_feed",
    
    # Fat Supplements
    "Tallow": "tallow",
    "Calcium salts of palm fatty acids": "bypass_fat",
    
    # Minerals
    "Limestone (ite)": "limestone",
    "Dicalcium phosphate": "dicalcium_phosphate",
    "Sodium bicarbonate": "sodium_bicarbonate",
    "Magnesium oxide": "magnesium_oxide",
    "Salt": "salt",
    
    # Animal Proteins
    "Blood meal, ring dried": "blood_meal",
    "Fish meal, menhaden": "fish_meal",
    "Feather meal, hydrolyzed": "feather_meal",
    
    # Additives/Other
    "Urea": "urea",
    "Molasses, cane": "molasses",
}


def safe_float(value: str, default: float | None = None) -> float | None:
    """Convert string to float, returning default for empty/invalid values."""
    if not value or value.strip() == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


def extract_all_nasem_nutrients(row: dict) -> dict:
    """Extract ALL nutrient columns from a NASEM feed row.
    
    This preserves NASEM column names exactly for full model compatibility.
    """
    nutrients = {}
    for col, value in row.items():
        # Skip metadata columns
        if col in METADATA_COLUMNS:
            continue
        # Try to convert to float
        float_val = safe_float(value)
        if float_val is not None:
            nutrients[col] = round(float_val, 6)  # Keep precision
    return nutrients


def clean_feed_name(name: str) -> str:
    """Clean feed name to create a valid key."""
    key = name.lower()
    key = key.replace(",", "").replace("(", "").replace(")", "")
    key = key.replace("%", "pct").replace("/", "_")
    key = "_".join(key.split())
    return key


def convert_row(row: dict, original_name: str) -> dict:
    """Convert a NASEM row to ration-agent feed format with ALL nutrients."""
    dm = safe_float(row.get("Fd_DM", "90"), 90)
    category = row.get("Fd_Category", "")
    fd_type = row.get("Fd_Type", "")
    
    # Extract ALL NASEM nutrient columns
    nutrients = extract_all_nasem_nutrients(row)
    
    # Add NASEM metadata columns that the model requires
    fd_libr = row.get("Fd_Libr", "NRC 2020")
    uid = row.get("UID", "")
    fd_index = safe_float(row.get("Fd_Index", "0"), 0)
    fd_locked = safe_float(row.get("Fd_Locked", "0"), 0)
    
    return {
        "dm_percent": round(dm, 1),
        "cost_per_kg": 0.0,  # User must set prices
        "nutrients": nutrients,
        "nasem_name": original_name,
        "category": category,
        "type": fd_type,
        # NASEM model metadata
        "Fd_Libr": fd_libr,
        "UID": uid,
        "Fd_Index": int(fd_index),
        "Fd_Locked": int(fd_locked),
    }


def find_matching_feeds(rows: list[dict]) -> dict[str, dict]:
    """Find feeds matching our target list."""
    feeds = {}
    matched_names = set()
    
    for row in rows:
        name = row.get("Fd_Name", "")
        if not name:
            continue
            
        # Check for exact matches first
        if name in TARGET_FEEDS:
            key = TARGET_FEEDS[name]
            feeds[key] = convert_row(row, name)
            matched_names.add(name)
            continue
            
        # Check for partial matches
        for target_name, key in TARGET_FEEDS.items():
            if target_name.lower() in name.lower() and target_name not in matched_names:
                feeds[key] = convert_row(row, name)
                matched_names.add(target_name)
                
    return feeds


def extract_all_feeds(rows: list[dict]) -> dict[str, dict]:
    """Extract all feeds with full NASEM nutrient data."""
    feeds = {}
    
    for row in rows:
        name = row.get("Fd_Name", "")
        if not name:
            continue
            
        key = clean_feed_name(name)
        feeds[key] = convert_row(row, name)
        
    return feeds


def load_csv(filepath: Path) -> list[dict]:
    """Load NASEM feed library CSV."""
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Extract NASEM feeds to ration-agent format")
    parser.add_argument("--validate", action="store_true", help="Validate extraction")
    parser.add_argument("--output", default=None, help="Output file path")
    parser.add_argument("--all", action="store_true", help="Extract all feeds (not just targets)")
    args = parser.parse_args()
    
    # Find CSV file
    script_dir = Path(__file__).parent
    csv_path = script_dir / "NASEM_feed_library.csv"
    
    if not csv_path.exists():
        print(f"Error: NASEM_feed_library.csv not found at {csv_path}")
        print("Please download from: https://github.com/CNM-University-of-Guelph/NASEM-Model-Python")
        sys.exit(1)
    
    # Load data
    rows = load_csv(csv_path)
    print(f"Loaded {len(rows)} feeds from NASEM library")
    
    # Extract feeds
    if args.all:
        feeds = extract_all_feeds(rows)
    else:
        feeds = find_matching_feeds(rows)
    
    print(f"Extracted {len(feeds)} feeds")
    
    # Create feedbase structure
    feedbase = {
        "default_dairy_cow_nasem": {
            "animal_type": "dairy_cow",
            "source": "NASEM 2021 / CNM-University-of-Guelph (MIT License)",
            "feeds": feeds
        }
    }
    
    # Output
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = script_dir / "nasem_feedbase.json"
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(feedbase, f, indent=2)
    
    print(f"Saved to: {output_path}")
    
    # Validation
    if args.validate:
        print("\n--- Validation ---")
        for key, feed in list(feeds.items())[:5]:
            print(f"\n{key}:")
            print(f"  DM: {feed['dm_percent']}%")
            print(f"  Nutrients: {list(feed['nutrients'].keys())}")
            
    # Print summary by category
    if args.all:
        categories = {}
        for key, feed in feeds.items():
            cat = feed.get("category", "Unknown")
            categories[cat] = categories.get(cat, 0) + 1
        print("\nFeeds by category:")
        for cat, count in sorted(categories.items()):
            print(f"  {cat}: {count}")


if __name__ == "__main__":
    main()
