"""Generate system companion animal feedbases using USDA FoodData Central data.

This script fetches nutrient data for a curated list of home-feeding ingredients
and produces DM-basis feed definitions aligned with FEDIAF reporting needs.

Usage:
    uv run python scripts/build_companion_feedbases.py --write
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from copy import deepcopy
from pathlib import Path
from typing import Dict, List, Optional

import sys

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from utils.usda_client import USDAClient
from utils.system_feedbases import SYSTEM_FEEDBASES_PATH, reload_system_feedbases


@dataclass(frozen=True)
class FeedSpec:
    name: str
    fdc_id: int
    cost_per_kg: float
    category: str
    label_en: str
    label_zh: str


CAT_FEEDS: List[FeedSpec] = [
    FeedSpec("chicken_thigh_raw", 173627, 4.0, "muscle_meat", "Chicken thigh (raw, boneless, skinless)", "鸡大腿肉（生）"),
    FeedSpec("turkey_breast_raw", 171098, 6.5, "muscle_meat", "Turkey breast (raw, boneless)", "火鸡胸肉（生）"),
    FeedSpec("duck_breast_raw", 0, 7.5, "muscle_meat", "Duck breast (raw, boneless)", "鸭胸肉（生）"),
    FeedSpec("rabbit_ground_raw", 0, 9.0, "muscle_meat", "Rabbit (whole ground, raw)", "兔肉（整只绞碎，生）"),
    FeedSpec("atlantic_salmon_raw", 173686, 12.0, "oily_fish", "Atlantic salmon fillet (raw)", "大西洋三文鱼（生）"),
    FeedSpec("atlantic_mackerel_raw", 175119, 9.0, "oily_fish", "Atlantic mackerel (raw)", "大西洋鲭鱼（生）"),
    FeedSpec("chicken_liver_raw", 171060, 3.5, "organ", "Chicken liver (raw)", "鸡肝（生）"),
    FeedSpec("beef_liver_raw", 169451, 4.0, "organ", "Beef liver (raw)", "牛肝（生）"),
    FeedSpec("pork_heart_raw", 168267, 3.2, "organ", "Pork heart (raw)", "猪心（生）"),
    FeedSpec("lamb_heart_raw", 0, 4.8, "organ", "Lamb heart (raw)", "羊心（生）"),
    FeedSpec("chicken_gizzard_raw", 0, 3.2, "organ", "Chicken gizzard (raw)", "鸡胗（生）"),
    FeedSpec("sardine_canned_with_bone", 175139, 10.0, "oily_fish", "Sardines in oil with bone (drained)", "沙丁鱼（油浸带骨）"),
    FeedSpec("mussels_steamed", 0, 6.2, "seafood", "Blue mussels (steamed)", "蓝贻贝（蒸）"),
    FeedSpec("whole_egg_raw", 171287, 2.5, "egg", "Whole egg (raw)", "整蛋（生）"),
    FeedSpec("pumpkin_cooked", 168449, 1.8, "fiber", "Pumpkin, cooked & drained", "南瓜（熟）"),
    FeedSpec("butternut_squash_cooked", 0, 1.5, "fiber", "Butternut squash (cooked & mashed)", "冬南瓜（熟泥）"),
    FeedSpec("kelp_raw", 168457, 18.0, "supplement", "Kelp / seaweed (raw)", "海带（生）"),
    FeedSpec("goat_milk_raw", 0, 2.9, "fermented_dairy", "Goat milk (raw)", "山羊奶（生）"),
]


DOG_FEEDS: List[FeedSpec] = [
    FeedSpec("chicken_thigh_raw", 173627, 4.0, "muscle_meat", "Chicken thigh (raw, boneless, skinless)", "鸡大腿肉（生）"),
    FeedSpec("turkey_breast_raw", 171098, 6.5, "muscle_meat", "Turkey breast (raw, boneless)", "火鸡胸肉（生）"),
    FeedSpec("duck_breast_raw", 0, 7.5, "muscle_meat", "Duck breast (raw, boneless)", "鸭胸肉（生）"),
    FeedSpec("rabbit_ground_raw", 0, 9.0, "muscle_meat", "Rabbit (whole ground, raw)", "兔肉（整只绞碎，生）"),
    FeedSpec("ground_beef_90lean_raw", 174030, 7.5, "muscle_meat", "Ground beef 90% lean (raw)", "牛肉碎（90%瘦，生）"),
    FeedSpec("atlantic_salmon_raw", 173686, 12.0, "oily_fish", "Atlantic salmon fillet (raw)", "大西洋三文鱼（生）"),
    FeedSpec("sardine_canned_with_bone", 175139, 10.0, "oily_fish", "Sardines in oil with bone (drained)", "沙丁鱼（油浸带骨）"),
    FeedSpec("chicken_liver_raw", 171060, 3.5, "organ", "Chicken liver (raw)", "鸡肝（生）"),
    FeedSpec("beef_liver_raw", 169451, 4.0, "organ", "Beef liver (raw)", "牛肝（生）"),
    FeedSpec("pork_heart_raw", 168267, 3.2, "organ", "Pork heart (raw)", "猪心（生）"),
    FeedSpec("lamb_heart_raw", 0, 4.8, "organ", "Lamb heart (raw)", "羊心（生）"),
    FeedSpec("chicken_gizzard_raw", 0, 3.2, "organ", "Chicken gizzard (raw)", "鸡胗（生）"),
    FeedSpec("green_tripe_raw", 0, 2.6, "organ", "Beef green tripe (raw)", "牛百叶（生）"),
    FeedSpec("sweet_potato_baked", 169307, 2.0, "carbohydrate", "Sweet potato baked (no salt)", "红薯（烤，无盐）"),
    FeedSpec("brown_rice_cooked", 2710789, 1.6, "carbohydrate", "Brown rice cooked", "糙米饭（熟）"),
    FeedSpec("pumpkin_cooked", 168449, 1.8, "fiber", "Pumpkin, cooked & drained", "南瓜（熟）"),
    FeedSpec("butternut_squash_cooked", 0, 1.5, "fiber", "Butternut squash (cooked & mashed)", "冬南瓜（熟泥）"),
    FeedSpec("carrot_cooked", 170394, 1.4, "fiber", "Carrot, cooked & drained", "胡萝卜（熟）"),
    FeedSpec("peas_cooked", 0, 1.2, "carbohydrate", "Green peas (cooked)", "青豌豆（熟）"),
    FeedSpec("green_beans_cooked", 0, 1.0, "greens", "Green beans (steamed)", "四季豆（蒸）"),
    FeedSpec("spinach_cooked", 168463, 3.0, "greens", "Spinach, cooked & drained", "菠菜（熟）"),
    FeedSpec("oatmeal_cooked", 173905, 1.7, "carbohydrate", "Rolled oats, cooked with water", "燕麦粥（清水）"),
    FeedSpec("mussels_steamed", 0, 6.2, "seafood", "Blue mussels (steamed)", "蓝贻贝（蒸）"),
    FeedSpec("ground_flaxseed", 2262075, 7.0, "seed", "Ground flaxseed", "亚麻籽粉"),
    FeedSpec("chia_seed_ground", 0, 8.5, "seed", "Chia seed (ground)", "奇亚籽粉"),
    FeedSpec("blueberries_raw", 171711, 4.5, "fruit", "Blueberries (fresh)", "蓝莓（鲜）"),
    FeedSpec("apple_raw", 0, 3.2, "fruit", "Apple (fresh, diced)", "苹果（鲜切）"),
    FeedSpec("yogurt_plain_whole", 2259793, 2.8, "fermented_dairy", "Plain whole-milk yogurt", "全脂酸奶（原味）"),
    FeedSpec("goat_milk_raw", 0, 2.9, "fermented_dairy", "Goat milk (raw)", "山羊奶（生）"),
    FeedSpec("cottage_cheese_lowfat", 0, 3.1, "fermented_dairy", "Cottage cheese (low-fat)", "低脂干酪"),
    FeedSpec("kelp_raw", 168457, 18.0, "supplement", "Kelp / seaweed (raw)", "海带（生）"),
]

OVERRIDE_PATH = Path(__file__).with_name("manual_feed_overrides.json")
# Manual nutrient overrides allow us to keep curated pet feeds in sync even when
# USDA API access is unavailable. When the JSON file is missing we simply fall
# back to live fetching for every ingredient.
if OVERRIDE_PATH.exists():
    FEED_OVERRIDES: Dict[str, Dict[str, dict]] = json.loads(OVERRIDE_PATH.read_text())
else:
    FEED_OVERRIDES = {}

PERCENT_KEYS = {
    "Protein": "CP",
    "Total lipid (fat)": "EE",
    "Ash": "Ash",
    "Fiber, total dietary": "CF",
    "Calcium, Ca": "Ca",
    "Phosphorus, P": "P",
}

PPM_KEYS = {
    "Magnesium, Mg": "Mg",
    "Potassium, K": "K",
    "Sodium, Na": "Na",
    "Iron, Fe": "Fe",
    "Zinc, Zn": "Zn",
    "Copper, Cu": "Cu",
    "Manganese, Mn": "Mn",
    "Selenium, Se": "Se",
    "Iodine, I": "I",
}

VITAMIN_MG = {
    "Vitamin C, total ascorbic acid": "VitC",
    "Choline, total": "Choline",
    "Thiamin": "VitB1",
    "Riboflavin": "VitB2",
    "Niacin": "VitB3",
    "Pantothenic acid": "VitB5",
    "Vitamin B-6": "VitB6",
    "Vitamin E (alpha-tocopherol)": "VitE",
}

VITAMIN_MCG = {
    "Vitamin B-12": "VitB12",
    "Folate, total": "Folate",
}

VITAMIN_IU = {
    "Vitamin A, IU": "VitA_IU",
    "Vitamin D (D2 + D3), International Units": "VitD_IU",
}


def _amount_to_grams(amount: Optional[float], unit: Optional[str]) -> Optional[float]:
    if amount is None or unit is None:
        return None
    unit = unit.lower()
    if unit == "g":
        return amount
    if unit == "mg":
        return amount / 1000.0
    if unit in {"µg", "ug"}:
        return amount / 1_000_000.0
    return None


def _mg_per_kg_dm(amount: Optional[float], unit: Optional[str], dm_fraction: float) -> Optional[float]:
    grams = _amount_to_grams(amount, unit)
    if grams is None or dm_fraction <= 0:
        return None
    return grams * 10000.0 / dm_fraction


def _percent_dm(amount: Optional[float], unit: Optional[str], dm_fraction: float) -> Optional[float]:
    grams = _amount_to_grams(amount, unit)
    if grams is None or dm_fraction <= 0:
        return None
    return (grams / dm_fraction)


def _collect_nutrients(food: dict, spec: FeedSpec) -> Dict[str, float]:
    nutrient_index: Dict[str, tuple] = {}
    for entry in food.get("foodNutrients", []):
        nutrient = entry.get("nutrient") or {}
        name = nutrient.get("name")
        unit = nutrient.get("unitName")
        amount = entry.get("amount")
        if not name or amount is None:
            continue

        if name == "Energy":
            if unit == "kcal":
                nutrient_index["Energy_kcal"] = (amount, unit)
            elif unit == "kJ":
                nutrient_index["Energy_kJ"] = (amount, unit)
            # Do not break; still allow generic key

        nutrient_index.setdefault(name, (amount, unit))

    water = nutrient_index.get("Water", (None, None))[0]
    if water is None:
        raise ValueError(f"Missing water value for FDC {spec.fdc_id}")

    dm_percent = round(100 - water, 3)
    dm_fraction = dm_percent / 100.0

    nutrients: Dict[str, float] = {}

    percent_values = {}
    for src, key in PERCENT_KEYS.items():
        amount, unit = nutrient_index.get(src, (None, None))
        value = _percent_dm(amount, unit, dm_fraction)
        if value is not None:
            nutrients[key] = round(value, 4)
            percent_values[key] = value

    cp = percent_values.get("CP", 0.0)
    ee = percent_values.get("EE", 0.0)
    ash = percent_values.get("Ash", 0.0)
    cf = percent_values.get("CF", 0.0)
    nfe = max(0.0, 100.0 - (cp + ee + ash + cf))
    nutrients["NFE"] = round(nfe, 4)

    for src, key in PPM_KEYS.items():
        amount, unit = nutrient_index.get(src, (None, None))
        mgkg = _mg_per_kg_dm(amount, unit, dm_fraction)
        if mgkg is not None:
            nutrients[f"{key}_mg_per_kg"] = round(mgkg, 2)

    for src, key in VITAMIN_MG.items():
        amount, unit = nutrient_index.get(src, (None, None))
        mgkg = _mg_per_kg_dm(amount, unit, dm_fraction)
        if mgkg is not None:
            nutrients[f"{key}_mg_per_kg"] = round(mgkg, 2)

    for src, key in VITAMIN_MCG.items():
        amount, unit = nutrient_index.get(src, (None, None))
        mgkg = _mg_per_kg_dm(amount, unit, dm_fraction)
        if mgkg is not None:
            nutrients[f"{key}_mg_per_kg"] = round(mgkg, 2)

    for src, key in VITAMIN_IU.items():
        amount, unit = nutrient_index.get(src, (None, None))
        if amount is None:
            continue
        iu_per_kg_dm = (amount * 10.0) / dm_fraction if dm_fraction > 0 else None
        if iu_per_kg_dm is not None:
            nutrients[f"{key}_per_kg_DM"] = round(iu_per_kg_dm, 1)

    energy_kcal = nutrient_index.get("Energy_kcal", nutrient_index.get("Energy", (None, None)))[0]
    if energy_kcal is not None and dm_fraction > 0:
        me_kcal = (energy_kcal * 10.0) / dm_fraction
        nutrients["ME_kcal_per_kg_DM"] = round(me_kcal, 2)
        nutrients["ME_MJ_per_kg_DM"] = round(me_kcal * 0.004184, 3)

    return dm_percent, nutrients


def build_feedbase(client: USDAClient, specs: List[FeedSpec], animal_type: str) -> Dict[str, dict]:
    feeds = {}
    labels: Dict[str, Dict[str, str]] = {}
    for spec in specs:
        override = FEED_OVERRIDES.get(spec.name)
        if override:
            dm_percent = override["dm_percent"]
            nutrients = deepcopy(override["nutrients"])
        else:
            food = client.get_food(spec.fdc_id)
            dm_percent, nutrients = _collect_nutrients(food, spec)
        feeds[spec.name] = {
            "dm_percent": dm_percent,
            "cost_per_kg": spec.cost_per_kg,
            "nutrients": nutrients,
        }
        labels[spec.name] = {
            "en": spec.label_en,
            "zh": spec.label_zh,
        }
    return {
        "animal_type": animal_type,
        "feeds": feeds,
        "feed_labels": labels,
    }


def main(write: bool, pretty: bool):
    client = USDAClient()
    data = {
        "default_cat": build_feedbase(client, CAT_FEEDS, "cat"),
        "default_dog": build_feedbase(client, DOG_FEEDS, "dog"),
    }

    indent = 2 if pretty else None
    output_path = SYSTEM_FEEDBASES_PATH

    if write:
        if output_path.exists():
            try:
                existing = json.loads(output_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                existing = {}
        else:
            existing = {}

        if not isinstance(existing, dict):
            existing = {}

        existing.update(data)
        ordered = {name: existing[name] for name in sorted(existing.keys())}
        text = json.dumps(ordered, indent=indent, ensure_ascii=False)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text + ("\n" if not text.endswith("\n") else ""), encoding="utf-8")
        reload_system_feedbases()
        print(f"Wrote companion feedbases to {output_path}")
    else:
        text = json.dumps(data, indent=indent, ensure_ascii=False)
        print(text)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build cat/dog feedbases from USDA data")
    parser.add_argument("--write", action="store_true", help="Write output JSON to migrations/data directory")
    parser.add_argument("--no-pretty", action="store_true", help="Disable pretty JSON formatting")
    args = parser.parse_args()
    main(write=args.write, pretty=not args.no_pretty)
