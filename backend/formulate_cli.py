#!/usr/bin/env python3
"""
CLI tool for testing ration formulation directly.

Usage:
    # Default: 40kg milk, 17% CP target
    uv run python formulate_cli.py

    # Custom milk production
    uv run python formulate_cli.py --milk 35

    # Custom CP constraint
    uv run python formulate_cli.py --cp-min 16 --cp-max 18

    # Full custom run with NASEM evaluation
    uv run python formulate_cli.py --milk 40 --evaluate
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from formulation.optimizer import FormulationOptimizer
from services.nasem_service import get_nasem_service

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def load_feedbase() -> Dict[str, Any]:
    """Load NASEM feedbase from JSON file."""
    feedbase_path = Path(__file__).parent / "scripts" / "nasem_feedbase.json"
    with open(feedbase_path, "r") as f:
        data = json.load(f)
    
    # The JSON has structure: {"default_dairy_cow_nasem": {"animal_type": ..., "feeds": {...}}}
    # Normalize to {"feeds": {...}} format expected by optimizer
    if "default_dairy_cow_nasem" in data:
        return data["default_dairy_cow_nasem"]
    elif "feeds" in data:
        return data
    else:
        # Already in correct format or unknown structure
        return {"feeds": data}


def get_default_feeds() -> List[str]:
    """Return a practical list of dairy feeds for formulation."""
    return [
        # Forages
        "corn_silage_typical",
        "legume_hay_mature",
        "legume_hay_mid-maturity",
        "alfalfa_hay_mature",
        
        # Energy sources
        "corn_grain_dry_coarse_grind",
        "corn_grain_dry_fine_grind",
        "barley_grain_dry_ground",
        
        # Protein sources
        "soybean_meal_solvent_48cp",
        "ddgs_high_protein",
        "corn_gluten_meal",
        "canola_meal_solvent",
        
        # Bypass protein sources
        "blood_meal_ring-dried",
        "fish_meal_menhaden",
        
        # Minerals/Additives
        "calcium_phosphate_di",
        "limestone",
        "sodium_chloride_salt",
        "vittm_premix_generic",
    ]


def formulate(
    feedbase: Dict[str, Any],
    feeds: List[str],
    milk_prod: float = 40.0,
    body_weight: float = 650.0,
    dim: int = 90,
    parity: int = 2,
    cp_min: float = 16.0,
    cp_max: float = 18.0,
    ndf_min: float = 28.0,
    ndf_max: float = 38.0,
) -> Dict[str, Any]:
    """
    Run ration formulation with given constraints.
    
    Returns formulation result dict.
    """
    # Filter to feeds that exist in feedbase
    available_feeds = []
    feed_data = {}
    feeds_dict = feedbase.get("feeds", {})
    
    for feed in feeds:
        if feed in feeds_dict:
            available_feeds.append(feed)
            # Optimizer expects: {"feed_name": {"nutrients": {...}, "cost_per_kg": ..., "dm_percent": ...}}
            feed_data[feed] = feeds_dict[feed]
    
    if not available_feeds:
        return {"status": "error", "message": "No valid feeds found"}
    
    print(f"\n📋 Using {len(available_feeds)} feeds:")
    for f in available_feeds:
        print(f"   - {f}")
    
    # Create optimizer
    optimizer = FormulationOptimizer()
    optimizer.set_feeds(feed_data)
    optimizer.set_animal_params(
        body_weight=body_weight,
        dim=dim,
        parity=parity,
        milk_prod=milk_prod,
        bcs=3.0,
        milk_fat_pct=3.5,
        milk_protein_pct=3.2
    )
    
    # Build constraints
    constraints = [
        {"type": "concentration", "nutrient": "Fd_CP", "min": cp_min, "max": cp_max},
        {"type": "concentration", "nutrient": "Fd_NDF", "min": ndf_min, "max": ndf_max},
        {"type": "concentration", "nutrient": "Fd_ADF", "min": 17.0, "max": 28.0},
        {"type": "concentration", "nutrient": "Fd_St", "min": 20.0, "max": 35.0},
        {"type": "concentration", "nutrient": "Fd_Ca", "min": 0.6, "max": 1.2},
        {"type": "concentration", "nutrient": "Fd_P", "min": 0.35, "max": 0.55},
    ]
    
    # Feed constraints: ensure some forage
    feed_constraints = {
        "corn_silage_typical": {"min": 15, "max": 45},
        "legume_hay_mature": {"min": 5, "max": 30},
        "legume_hay_mid-maturity": {"min": 0, "max": 30},
        "alfalfa_hay_mature": {"min": 0, "max": 25},
        "corn_grain_dry_coarse_grind": {"min": 0, "max": 30},
        "corn_grain_dry_fine_grind": {"min": 0, "max": 25},
        "soybean_meal_solvent_48cp": {"min": 0, "max": 20},
        "ddgs_high_protein": {"min": 0, "max": 15},
        "corn_gluten_meal": {"min": 0, "max": 8},
        "canola_meal_solvent": {"min": 0, "max": 15},
        "blood_meal_ring-dried": {"min": 0, "max": 5},
        "fish_meal_menhaden": {"min": 0, "max": 5},
        "calcium_phosphate_di": {"min": 0, "max": 3},
        "limestone": {"min": 0, "max": 2},
        "sodium_chloride_salt": {"min": 0.2, "max": 0.8},
        "vittm_premix_generic": {"min": 0.2, "max": 1.0},
    }
    
    print(f"\n🎯 Constraints:")
    print(f"   CP: {cp_min}-{cp_max}% DM")
    print(f"   NDF: {ndf_min}-{ndf_max}% DM")
    print(f"   ADF: 17-28% DM")
    print(f"   Starch: 20-35% DM")
    
    # Optimize
    result = optimizer.optimize(
        nutritional_constraints=constraints,
        selected_feeds=available_feeds,
        feed_constraints=feed_constraints,
        optimization_goal="minimize_cost"
    )
    
    return result


def evaluate_with_nasem(
    feedbase: Dict[str, Any],
    formulation_result: Dict[str, Any],
    milk_prod: float = 40.0,
    body_weight: float = 650.0,
    dim: int = 90,
    parity: int = 2,
) -> Dict[str, Any]:
    """Evaluate formulation using NASEM dairy model.
    
    Args:
        feedbase: Feedbase dict with feeds
        formulation_result: Complete formulation result dict from optimizer  
        milk_prod, body_weight, dim, parity: Animal params
    """
    from services.nasem_service import NASEMService
    nasem_service = get_nasem_service()
    
    # Build diet using centralized helper (single source of truth)
    diet, predicted_dmi_kg = NASEMService.build_diet_from_formulation(formulation_result)
    
    # Build animal input with optimizer's predicted DMI
    animal_input = nasem_service.build_animal_input(
        body_weight_kg=body_weight,
        days_in_milk=dim,
        parity=parity,
        target_milk_kg=milk_prod,
        milk_fat_percent=3.5,
        milk_protein_percent=3.2,
        target_dmi_kg=predicted_dmi_kg  # Use optimizer's DMI
    )
    
    # Evaluate
    result = nasem_service.evaluate_diet(
        feedbase=feedbase,
        diet_composition=diet,
        animal_input=animal_input
    )
    
    return result


def print_formulation_result(result: Dict[str, Any]):
    """Pretty print formulation result."""
    if result.get("status") != "success":
        print(f"\n❌ Formulation failed: {result.get('message', 'Unknown error')}")
        return
    
    print("\n" + "=" * 60)
    print("✅ FORMULATION RESULT")
    print("=" * 60)
    
    formulation = result.get("formulation", {})
    total_kg = 0
    
    print(f"\n{'Feed':<35} {'% DM':>8} {'kg/day':>10}")
    print("-" * 55)
    for feed, data in sorted(formulation.items(), key=lambda x: -x[1].get("percentage_dm", 0)):
        pct = data.get("percentage_dm", 0)
        kg = data.get("kg_per_day", 0)
        total_kg += kg
        if pct > 0.01:  # Only show significant inclusions
            print(f"{feed:<35} {pct:>7.2f}% {kg:>9.2f}")
    
    print("-" * 55)
    print(f"{'TOTAL':<35} {'100.00%':>8} {total_kg:>9.2f}")
    
    # Nutrient analysis
    nutrients = result.get("nutrient_analysis", {})
    print(f"\n📊 Nutrient Analysis (% DM):")
    print("-" * 40)
    
    key_nutrients = [
        ("Fd_CP", "Crude Protein"),
        ("Fd_NDF", "NDF"),
        ("Fd_ADF", "ADF"),
        ("Fd_St", "Starch"),
        ("Fd_CFat", "Fat"),
        ("Fd_Ca", "Calcium"),
        ("Fd_P", "Phosphorus"),
        ("Fd_DE_Base", "DE (Mcal/kg)"),
    ]
    
    for key, name in key_nutrients:
        val = nutrients.get(key, 0)
        print(f"   {name:<20}: {val:>7.2f}")
    
    print(f"\n💰 Cost: ${result.get('cost_per_kg_dm', 0):.4f}/kg DM")
    print(f"📈 Predicted DMI: {result.get('predicted_dmi_kg', 0):.1f} kg/day")
    print(f"🔬 Predicted MP: {result.get('predicted_mp_g', 0):.0f} g/day")


def print_nasem_result(result: Dict[str, Any]):
    """Pretty print NASEM evaluation result."""
    if result.get("status") != "success":
        print(f"\n❌ NASEM evaluation failed: {result.get('error', 'Unknown error')}")
        return
    
    print("\n" + "=" * 60)
    print("🔬 NASEM EVALUATION")
    print("=" * 60)
    print(result.get("snapshot", "No output"))


def main():
    parser = argparse.ArgumentParser(description="CLI ration formulation tool")
    parser.add_argument("--milk", type=float, default=40.0, help="Target milk production (kg/day)")
    parser.add_argument("--bw", type=float, default=650.0, help="Body weight (kg)")
    parser.add_argument("--dim", type=int, default=90, help="Days in milk")
    parser.add_argument("--parity", type=int, default=2, help="Parity (lactation number)")
    parser.add_argument("--cp-min", type=float, default=16.0, help="Min CP (%)")
    parser.add_argument("--cp-max", type=float, default=18.0, help="Max CP (%)")
    parser.add_argument("--ndf-min", type=float, default=28.0, help="Min NDF (%)")
    parser.add_argument("--ndf-max", type=float, default=38.0, help="Max NDF (%)")
    parser.add_argument("--evaluate", action="store_true", help="Run NASEM evaluation")
    parser.add_argument("--feeds", type=str, help="Comma-separated list of feeds to use")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    print("=" * 60)
    print("🐄 RATION FORMULATION CLI")
    print("=" * 60)
    print(f"\n🎯 Target: {args.milk} kg/day milk production")
    print(f"   Body weight: {args.bw} kg")
    print(f"   Days in milk: {args.dim}")
    print(f"   Parity: {args.parity}")
    
    # Load feedbase
    print("\n📦 Loading NASEM feedbase...")
    feedbase = load_feedbase()
    print(f"   Loaded {len(feedbase.get('feeds', {}))} feeds")
    
    # Get feeds
    if args.feeds:
        feeds = [f.strip() for f in args.feeds.split(",")]
    else:
        feeds = get_default_feeds()
    
    # Run formulation
    print("\n⚙️  Running optimization...")
    result = formulate(
        feedbase=feedbase,
        feeds=feeds,
        milk_prod=args.milk,
        body_weight=args.bw,
        dim=args.dim,
        parity=args.parity,
        cp_min=args.cp_min,
        cp_max=args.cp_max,
        ndf_min=args.ndf_min,
        ndf_max=args.ndf_max,
    )
    
    print_formulation_result(result)
    
    # NASEM evaluation
    if args.evaluate and result.get("status") == "success":
        print("\n⚙️  Running NASEM evaluation...")
        nasem_result = evaluate_with_nasem(
            feedbase=feedbase,
            formulation_result=result,  # Pass full result for centralized diet extraction
            milk_prod=args.milk,
            body_weight=args.bw,
            dim=args.dim,
            parity=args.parity,
        )
        print_nasem_result(nasem_result)


if __name__ == "__main__":
    main()
