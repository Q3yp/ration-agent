#!/usr/bin/env python3
"""
Direct test of the FormulationOptimizer to verify it works as expected.
Tests various constraint types and validates mathematical correctness.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from formulation.optimizer import FormulationOptimizer
import json


def test_basic_optimization():
    """Test basic cost minimization with concentration constraints"""
    print("=== Test 1: Basic Cost Minimization ===")
    
    optimizer = FormulationOptimizer()
    
    # Sample dairy feeds
    feeds = {
        "corn_silage": {
            "dm_percent": 35.0,
            "nutrients": {"CP": 8.0, "NEL": 1.50, "NDF": 45.0, "Ca": 0.25, "P": 0.20},
            "cost_per_kg": 0.15  # $0.15/kg as-fed
        },
        "alfalfa_hay": {
            "dm_percent": 90.0,
            "nutrients": {"CP": 18.5, "NEL": 1.30, "NDF": 40.0, "Ca": 1.40, "P": 0.25},
            "cost_per_kg": 0.35
        },
        "corn_grain": {
            "dm_percent": 87.0,
            "nutrients": {"CP": 9.0, "NEL": 2.00, "NDF": 10.0, "Ca": 0.03, "P": 0.30},
            "cost_per_kg": 0.25
        },
        "soybean_meal": {
            "dm_percent": 90.0,
            "nutrients": {"CP": 48.0, "NEL": 2.10, "NDF": 7.0, "Ca": 0.30, "P": 0.65},
            "cost_per_kg": 0.45
        }
    }
    
    optimizer.set_feeds(feeds)
    
    # Test constraints
    constraints = [
        {"type": "concentration", "nutrient": "CP", "min": 16.0, "max": 18.0},
        {"type": "concentration", "nutrient": "NEL", "min": 1.60, "max": 1.80},
        {"type": "concentration", "nutrient": "NDF", "min": 25.0, "max": 35.0}
    ]
    
    selected_feeds = ["corn_silage", "alfalfa_hay", "corn_grain", "soybean_meal"]
    
    result = optimizer.optimize(constraints, selected_feeds)
    
    print(f"Status: {result.get('status')}")
    if result.get('status') == 'success':
        print(f"Cost per kg DM: ${result['cost_per_kg_dm']:.3f}")
        print("Formulation:")
        for feed, data in result['formulation'].items():
            print(f"  {feed}: {data['percentage_dm']:.2f}%")
        
        print("\nNutrient Analysis:")
        for nutrient, value in result['nutrient_analysis'].items():
            print(f"  {nutrient}: {value:.2f}%")
        
        # Verify constraints
        analysis = result['nutrient_analysis']
        cp_ok = 16.0 <= analysis.get('CP', 0) <= 18.0
        nel_ok = 1.60 <= analysis.get('NEL', 0) <= 1.80
        ndf_ok = 25.0 <= analysis.get('NDF', 0) <= 35.0
        
        print(f"\nConstraint Verification:")
        print(f"  CP (16-18%): {analysis.get('CP', 0):.2f}% - {'✓' if cp_ok else '✗'}")
        print(f"  NEL (1.6-1.8): {analysis.get('NEL', 0):.2f} - {'✓' if nel_ok else '✗'}")
        print(f"  NDF (25-35%): {analysis.get('NDF', 0):.2f}% - {'✓' if ndf_ok else '✗'}")
        
        return cp_ok and nel_ok and ndf_ok
    else:
        print(f"Error: {result.get('error')}")
        return False


def test_daily_intake_constraints():
    """Test daily total constraints with DMI"""
    print("\n=== Test 2: Daily Intake Constraints ===")
    
    optimizer = FormulationOptimizer()
    
    # Same feeds as before
    feeds = {
        "corn_silage": {
            "dm_percent": 35.0,
            "nutrients": {"CP": 8.0, "NEL": 1.50},
            "cost_per_kg": 0.15
        },
        "soybean_meal": {
            "dm_percent": 90.0,
            "nutrients": {"CP": 48.0, "NEL": 2.10},
            "cost_per_kg": 0.45
        },
        "corn_grain": {
            "dm_percent": 87.0,
            "nutrients": {"CP": 9.0, "NEL": 2.00},
            "cost_per_kg": 0.25
        }
    }
    
    optimizer.set_feeds(feeds)
    
    # Daily intake constraints
    constraints = [
        {"type": "daily_total", "attribute": "dmi", "target": 22.0, "tolerance_percent": 5.0},
        {"type": "daily_total", "attribute": "NEL", "target": 36.0, "tolerance_percent": 8.0},
        {"type": "daily_total", "attribute": "CP", "target": 3.6, "tolerance_percent": 10.0}
    ]
    
    selected_feeds = ["corn_silage", "soybean_meal", "corn_grain"]
    
    result = optimizer.optimize(constraints, selected_feeds)
    
    print(f"Status: {result.get('status')}")
    if result.get('status') == 'success':
        print(f"Cost per kg DM: ${result['cost_per_kg_dm']:.3f}")
        print("Formulation:")
        for feed, data in result['formulation'].items():
            print(f"  {feed}: {data['percentage_dm']:.2f}%")
        
        print("\nNutrient Analysis:")
        analysis = result['nutrient_analysis']
        for nutrient, value in analysis.items():
            print(f"  {nutrient}: {value:.2f}%")
        
        # Verify daily intake calculations (manual check)
        dmi = 22.0  # Target DMI
        nel_daily = (analysis.get('NEL', 0) / 100) * dmi
        cp_daily = (analysis.get('CP', 0) / 100) * dmi
        
        print(f"\nDaily Intake Verification (DMI = {dmi} kg):")
        print(f"  NEL: {nel_daily:.2f} Mcal/day (target: 36.0 ± 8%)")
        print(f"  CP: {cp_daily:.2f} kg/day (target: 3.6 ± 10%)")
        
        nel_ok = 33.12 <= nel_daily <= 38.88  # 36 ± 8%
        cp_ok = 3.24 <= cp_daily <= 3.96      # 3.6 ± 10%
        
        print(f"  NEL constraint: {'✓' if nel_ok else '✗'}")
        print(f"  CP constraint: {'✓' if cp_ok else '✗'}")
        
        return nel_ok and cp_ok
    else:
        print(f"Error: {result.get('error')}")
        return False


def test_ratio_constraints():
    """Test ratio constraints"""
    print("\n=== Test 3: Ratio Constraints ===")
    
    optimizer = FormulationOptimizer()
    
    feeds = {
        "limestone": {
            "dm_percent": 95.0,
            "nutrients": {"Ca": 38.0, "P": 0.01},
            "cost_per_kg": 0.10
        },
        "dicalcium_phosphate": {
            "dm_percent": 95.0,
            "nutrients": {"Ca": 22.0, "P": 18.5},
            "cost_per_kg": 0.80
        },
        "corn_grain": {
            "dm_percent": 87.0,
            "nutrients": {"Ca": 0.03, "P": 0.30},
            "cost_per_kg": 0.25
        }
    }
    
    optimizer.set_feeds(feeds)
    
    # Test Ca:P ratio constraint
    constraints = [
        {"type": "ratio", "numerator": "Ca", "denominator": "P", "min": 1.5, "max": 2.5},
        {"type": "concentration", "nutrient": "Ca", "min": 0.60, "max": 0.90},
        {"type": "concentration", "nutrient": "P", "min": 0.35, "max": 0.45}
    ]
    
    selected_feeds = ["limestone", "dicalcium_phosphate", "corn_grain"]
    
    result = optimizer.optimize(constraints, selected_feeds)
    
    print(f"Status: {result.get('status')}")
    if result.get('status') == 'success':
        print(f"Cost per kg DM: ${result['cost_per_kg_dm']:.3f}")
        print("Formulation:")
        for feed, data in result['formulation'].items():
            print(f"  {feed}: {data['percentage_dm']:.2f}%")
        
        analysis = result['nutrient_analysis']
        ca_content = analysis.get('Ca', 0)
        p_content = analysis.get('P', 0)
        ca_p_ratio = ca_content / p_content if p_content > 0 else 0
        
        print(f"\nNutrient Analysis:")
        print(f"  Ca: {ca_content:.2f}%")
        print(f"  P: {p_content:.2f}%")
        print(f"  Ca:P ratio: {ca_p_ratio:.2f}")
        
        # Verify constraints
        ca_ok = 0.60 <= ca_content <= 0.90
        p_ok = 0.35 <= p_content <= 0.45
        ratio_ok = 1.5 <= ca_p_ratio <= 2.5
        
        print(f"\nConstraint Verification:")
        print(f"  Ca (0.6-0.9%): {ca_content:.2f}% - {'✓' if ca_ok else '✗'}")
        print(f"  P (0.35-0.45%): {p_content:.2f}% - {'✓' if p_ok else '✗'}")
        print(f"  Ca:P ratio (1.5-2.5): {ca_p_ratio:.2f} - {'✓' if ratio_ok else '✗'}")
        
        return ca_ok and p_ok and ratio_ok
    else:
        print(f"Error: {result.get('error')}")
        return False


def test_infeasible_constraints():
    """Test handling of infeasible constraints"""
    print("\n=== Test 4: Infeasible Constraints ===")
    
    optimizer = FormulationOptimizer()
    
    feeds = {
        "low_protein_feed": {
            "dm_percent": 90.0,
            "nutrients": {"CP": 5.0, "NEL": 1.20},
            "cost_per_kg": 0.10
        }
    }
    
    optimizer.set_feeds(feeds)
    
    # Impossible constraint - need 25% protein but only have 5% protein feed
    constraints = [
        {"type": "concentration", "nutrient": "CP", "min": 25.0}
    ]
    
    result = optimizer.optimize(constraints, ["low_protein_feed"])
    
    print(f"Status: {result.get('status')}")
    print(f"Expected: failed (infeasible constraints)")
    if result.get('status') == 'failed':
        print(f"Error message: {result.get('error')}")
        return True
    else:
        print("ERROR: Should have failed but didn't!")
        return False


def test_percentage_sum():
    """Test that feed percentages sum to 100%"""
    print("\n=== Test 5: Percentage Sum Verification ===")
    
    optimizer = FormulationOptimizer()
    
    feeds = {
        "feed_a": {"dm_percent": 90.0, "nutrients": {"CP": 10.0}, "cost_per_kg": 0.20},
        "feed_b": {"dm_percent": 85.0, "nutrients": {"CP": 20.0}, "cost_per_kg": 0.30},
        "feed_c": {"dm_percent": 95.0, "nutrients": {"CP": 30.0}, "cost_per_kg": 0.40}
    }
    
    optimizer.set_feeds(feeds)
    
    constraints = [
        {"type": "concentration", "nutrient": "CP", "min": 15.0, "max": 25.0}
    ]
    
    result = optimizer.optimize(constraints, ["feed_a", "feed_b", "feed_c"])
    
    if result.get('status') == 'success':
        total_percentage = sum(data['percentage_dm'] for data in result['formulation'].values())
        print(f"Total percentage: {total_percentage:.2f}%")
        sum_ok = abs(total_percentage - 100.0) < 0.01  # Allow tiny rounding error
        print(f"Sum to 100%: {'✓' if sum_ok else '✗'}")
        return sum_ok
    else:
        print(f"Optimization failed: {result.get('error')}")
        return False


if __name__ == "__main__":
    print("Testing FormulationOptimizer...")
    
    tests = [
        ("Basic Optimization", test_basic_optimization),
        ("Daily Intake Constraints", test_daily_intake_constraints),
        ("Ratio Constraints", test_ratio_constraints),
        ("Infeasible Constraints", test_infeasible_constraints),
        ("Percentage Sum", test_percentage_sum)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
            print(f"✓ {test_name}: {'PASS' if result else 'FAIL'}")
        except Exception as e:
            results.append((test_name, False))
            print(f"✗ {test_name}: ERROR - {e}")
        print("-" * 60)
    
    print("\n=== SUMMARY ===")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"  {test_name}: {status}")
    
    if passed == total:
        print("\n🎉 All tests passed! The optimizer appears to be working correctly.")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. The optimizer may have issues.")