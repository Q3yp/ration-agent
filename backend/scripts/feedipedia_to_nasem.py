"""Layer 2: Feedipedia → NASEM mapping + feedbase builder.

Maps Feedipedia nutrient names/units to NASEM Fd_* columns, finds the best
NASEM template for each Feedipedia feed, and produces new NASEM-compatible
feed entries.

Usage:
    uv run python scripts/feedipedia_to_nasem.py                  # build feedbase
    uv run python scripts/feedipedia_to_nasem.py --stats           # show mapping stats
    uv run python scripts/feedipedia_to_nasem.py --dry-run         # preview without writing

Requires: data/feedipedia.db (from scrape_feedipedia.py)

Data is licensed CC-BY-4.0 by INRA, CIRAD, AFZ, and FAO.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sqlite3
import sys
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts.nasem_nutrient_graph import (
        ROOT_NUTRIENTS,
        OVERRIDABLE_FROM_EXTERNAL,
        adjust_template,
    )
else:
    from .nasem_nutrient_graph import (
        ROOT_NUTRIENTS,
        OVERRIDABLE_FROM_EXTERNAL,
        adjust_template,
    )

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

FEEDIPEDIA_DB = Path(__file__).resolve().parent.parent / "data" / "feedipedia.db"
NASEM_FEEDBASE_PATH = Path(__file__).resolve().parent / "nasem_feedbase.json"
OUTPUT_PATH = Path(__file__).resolve().parent / "nasem_feedbase.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Layer 2: Feedipedia nutrient name/unit → NASEM column + conversion
# ---------------------------------------------------------------------------

# Unit conversion functions
def _identity(x: float) -> float:
    return x

def _mj_to_mcal(x: float) -> float:
    """MJ/kg DM → Mcal/kg DM"""
    return x * 0.239006

def _gkg_to_pct(x: float) -> float:
    """g/kg DM → % DM"""
    return x / 10.0

def _mgkg_direct(x: float) -> float:
    """mg/kg DM → mg/kg DM (ppm) — identity"""
    return x


# Each entry: (Feedipedia nutrient_name, Feedipedia unit) → (NASEM column, converter)
# We use (name, unit) as key because some nutrients appear with different units
FEEDIPEDIA_TO_NASEM: Dict[Tuple[str, str], Tuple[str, callable]] = {
    # --- Main analysis ---
    ("Dry matter", "% as fed"):           ("Fd_DM",    _identity),
    ("Crude protein", "% DM"):            ("Fd_CP",    _identity),
    ("NDF", "% DM"):                      ("Fd_NDF",   _identity),
    ("Neutral detergent fibre", "% DM"):  ("Fd_NDF",   _identity),   # alias
    ("ADF", "% DM"):                      ("Fd_ADF",   _identity),
    ("Acid detergent fibre", "% DM"):     ("Fd_ADF",   _identity),   # alias
    ("Lignin", "% DM"):                   ("Fd_Lg",    _identity),
    ("Ether extract", "% DM"):            ("Fd_CFat",  _identity),
    ("Ash", "% DM"):                      ("Fd_Ash",   _identity),
    ("Starch (polarimetry)", "% DM"):     ("Fd_St",    _identity),
    ("Starch (enzymatic)", "% DM"):       ("Fd_St",    _identity),   # fallback
    ("Total sugars", "% DM"):             ("Fd_WSC",   _identity),
    ("Gross energy", "MJ/kg DM"):         ("Fd_GE",    _mj_to_mcal),  # not a NASEM col but useful

    # --- Ruminant nutritive values ---
    ("DE ruminants", "MJ/kg DM"):         ("Fd_DE_Base", _mj_to_mcal),
    ("ME ruminants", "MJ/kg DM"):         ("Fd_ME",      _mj_to_mcal),  # store for reference

    # --- Macro minerals (g/kg DM → % DM) ---
    ("Calcium", "g/kg DM"):               ("Fd_Ca",    _gkg_to_pct),
    ("Phosphorus", "g/kg DM"):            ("Fd_P",     _gkg_to_pct),
    ("Potassium", "g/kg DM"):             ("Fd_K",     _gkg_to_pct),
    ("Sodium", "g/kg DM"):                ("Fd_Na",    _gkg_to_pct),
    ("Magnesium", "g/kg DM"):             ("Fd_Mg",    _gkg_to_pct),
    ("Chlorine", "g/kg DM"):              ("Fd_Cl",    _gkg_to_pct),
    ("Sulfur", "g/kg DM"):                ("Fd_S",     _gkg_to_pct),

    # --- Trace minerals (mg/kg DM → mg/kg DM / ppm) ---
    ("Iron", "mg/kg DM"):                 ("Fd_Fe",    _mgkg_direct),
    ("Manganese", "mg/kg DM"):            ("Fd_Mn",    _mgkg_direct),
    ("Zinc", "mg/kg DM"):                 ("Fd_Zn",    _mgkg_direct),
    ("Copper", "mg/kg DM"):               ("Fd_Cu",    _mgkg_direct),
    ("Selenium", "mg/kg DM"):             ("Fd_Se",    _mgkg_direct),

    # --- Amino acids (% protein → % CP) ---
    ("Arginine", "% protein"):            ("Fd_Arg_CP", _identity),
    ("Histidine", "% protein"):           ("Fd_His_CP", _identity),
    ("Isoleucine", "% protein"):          ("Fd_Ile_CP", _identity),
    ("Leucine", "% protein"):             ("Fd_Leu_CP", _identity),
    ("Lysine", "% protein"):              ("Fd_Lys_CP", _identity),
    ("Methionine", "% protein"):          ("Fd_Met_CP", _identity),
    ("Phenylalanine", "% protein"):       ("Fd_Phe_CP", _identity),
    ("Threonine", "% protein"):           ("Fd_Thr_CP", _identity),
    ("Tryptophan", "% protein"):          ("Fd_Trp_CP", _identity),
    ("Valine", "% protein"):              ("Fd_Val_CP", _identity),

    # --- Fatty acid profile (% fatty acids → % FA) ---
    ("Palmitic acid C16:0", "% fatty acids"):     ("Fd_C160_FA",  _identity),
    ("Palmitoleic acid C16:1", "% fatty acids"):  ("Fd_C161_FA",  _identity),
    ("Stearic acid C18:0", "% fatty acids"):      ("Fd_C180_FA",  _identity),
    ("Oleic acid C18:1", "% fatty acids"):        ("Fd_C181c_FA", _identity),
    ("Linoleic acid C18:2", "% fatty acids"):     ("Fd_C182_FA",  _identity),
    ("Linolenic acid C18:3", "% fatty acids"):    ("Fd_C183_FA",  _identity),
    ("Myristic acid C14:0", "% fatty acids"):     ("Fd_C140_FA",  _identity),

    # --- Ruminant degradability kinetics → NASEM CP fractions ---
    # a(N) = soluble fraction ≈ Fd_CPARU (rapidly degradable)
    # b(N) = potentially degradable ≈ Fd_CPBRU
    # Then Fd_CPCRU ≈ 100 - a - b
    ("a (N)", "%"):                       ("Fd_CPARU",  _identity),
    ("b (N)", "%"):                       ("Fd_CPBRU",  _identity),

    # Nitrogen degradability (effective, k=6%) → approximate RUP
    # RUP ≈ 100 - N_degradability
    ("Nitrogen degradability (effective, k=6%)", "%"): ("_N_degrad_k6", _identity),

    # OM digestibility
    ("OM digestibility, ruminants", "%"):  ("_OM_digest", _identity),
    ("OM digestibility, Ruminant", "%"):   ("_OM_digest", _identity),  # variant casing
}


def map_feedipedia_nutrients(
    raw_nutrients: List[Dict[str, Any]],
) -> Dict[str, float]:
    """Convert a list of Feedipedia nutrient rows to NASEM Fd_* column values.

    Args:
        raw_nutrients: List of dicts from SQLite with keys:
            nutrient_name, unit, avg, section

    Returns:
        Dict of NASEM column name → converted value.
        Only includes mappable nutrients with non-null avg values.
    """
    nasem_vals: Dict[str, float] = {}

    for row in raw_nutrients:
        name = row["nutrient_name"]
        unit = row["unit"]
        avg = row["avg"]

        if avg is None:
            continue

        key = (name, unit)
        mapping = FEEDIPEDIA_TO_NASEM.get(key)
        if mapping is None:
            continue

        nasem_col, converter = mapping
        try:
            nasem_vals[nasem_col] = converter(avg)
        except (ValueError, TypeError):
            continue

    # --- Post-processing: derive additional values ---

    # Derive Fd_CPCRU from a(N) and b(N): C fraction = 100 - A - B
    a_frac = nasem_vals.get("Fd_CPARU")
    b_frac = nasem_vals.get("Fd_CPBRU")
    if a_frac is not None and b_frac is not None:
        c_frac = max(0, 100.0 - a_frac - b_frac)
        nasem_vals["Fd_CPCRU"] = c_frac

    # Derive Fd_RUP_base from nitrogen degradability
    n_degrad = nasem_vals.pop("_N_degrad_k6", None)
    if n_degrad is not None:
        nasem_vals["Fd_RUP_base"] = 100.0 - n_degrad

    # Remove internal-only keys
    nasem_vals.pop("_OM_digest", None)
    nasem_vals.pop("Fd_GE", None)
    nasem_vals.pop("Fd_ME", None)

    return nasem_vals


# ---------------------------------------------------------------------------
# Template matching: find best NASEM feed for each Feedipedia feed
# ---------------------------------------------------------------------------

# Category mapping: Feedipedia categories → NASEM feed types/categories
CATEGORY_HINTS = {
    "cereal grains":        ["Energy Source", "Grain"],
    "cereal by-products":   ["Energy Source", "By-Product"],
    "oil plants":           ["Oil Seed", "Energy Source"],
    "oilseed meals":        ["Plant Protein", "Oil Seed"],
    "plant protein":        ["Plant Protein"],
    "legume seeds":         ["Plant Protein", "Legume"],
    "roots and tubers":     ["Energy Source"],
    "sugar processing":     ["Energy Source", "By-Product"],
    "fruit by-products":    ["By-Product"],
    "brewery by-products":  ["By-Product", "Energy Source"],
    "distillery by-products": ["By-Product", "Energy Source"],
    "citrus pulp":          ["By-Product"],
    "grass":                ["Forage"],
    "forage":               ["Forage"],
    "legume forage":        ["Forage", "Legume"],
    "hay":                  ["Forage"],
    "silage":               ["Forage", "Silage"],
    "straw":                ["Forage", "Roughage"],
    "animal by-products":   ["Animal Protein"],
    "fish meal":            ["Animal Protein"],
    "dairy products":       ["Animal Protein"],
    "minerals":             ["Mineral"],
    "fats and oils":        ["Fat/Oil"],
}


def _normalize_name(name: str) -> str:
    """Normalize a feed name for comparison."""
    name = name.lower()
    # Remove parenthetical species names
    name = re.sub(r"\([^)]*\)", "", name)
    # Remove common suffixes
    for suffix in [", fresh", ", dried", ", dehydrated", ", ground",
                   ", whole", ", raw", ", mature"]:
        name = name.replace(suffix, "")
    return name.strip()


def _text_similarity(a: str, b: str) -> float:
    """Compute text similarity between two normalized names."""
    return SequenceMatcher(None, _normalize_name(a), _normalize_name(b)).ratio()


def _nutrient_distance(
    fp_vals: Dict[str, float],
    nasem_nutrients: Dict[str, float],
) -> float:
    """Compute a normalized distance between Feedipedia and NASEM nutrient profiles.
    Lower = more similar. Uses key nutrients: CP, NDF, ADF, EE, Ash."""
    keys = ["Fd_CP", "Fd_NDF", "Fd_ADF", "Fd_CFat", "Fd_Ash"]
    diffs = []
    for key in keys:
        fp_val = fp_vals.get(key)
        nasem_val = nasem_nutrients.get(key)
        if fp_val is not None and nasem_val is not None and nasem_val != 0:
            diff = abs(fp_val - nasem_val) / max(nasem_val, 1.0)
            diffs.append(diff)
    return sum(diffs) / max(len(diffs), 1)


def _category_overlap(fp_categories: List[str], nasem_feed: Dict) -> float:
    """Score how well Feedipedia categories match a NASEM feed's category/type."""
    nasem_cat = (nasem_feed.get("category", "") or "").lower()
    nasem_type = (nasem_feed.get("type", "") or "").lower()

    score = 0.0
    for fp_cat in fp_categories:
        fp_cat_lower = fp_cat.lower()
        # Direct category match
        if fp_cat_lower in nasem_cat or nasem_cat in fp_cat_lower:
            score += 2.0
        if fp_cat_lower in nasem_type or nasem_type in fp_cat_lower:
            score += 1.5
        # Check hint mapping
        for hint_key, hint_vals in CATEGORY_HINTS.items():
            if hint_key in fp_cat_lower:
                for hint in hint_vals:
                    if hint.lower() in nasem_cat or hint.lower() in nasem_type:
                        score += 1.0
    return score


def find_best_template(
    fp_name: str,
    fp_categories: List[str],
    fp_nasem_vals: Dict[str, float],
    nasem_feeds: Dict[str, Dict],
) -> Tuple[str, float]:
    """Find the best-matching NASEM feed template for a Feedipedia feed.

    Scoring: 40% text similarity, 30% nutrient distance, 30% category overlap.

    Args:
        fp_name: Feedipedia feed name
        fp_categories: Feedipedia category list
        fp_nasem_vals: Mapped NASEM values from Feedipedia
        nasem_feeds: Full dict of existing NASEM feeds

    Returns:
        (best_feed_name, score)
    """
    best_name = ""
    best_score = -1.0

    for nasem_name, nasem_feed in nasem_feeds.items():
        # Skip vitamin/mineral premixes — they have all-zero nutrients and
        # would vacuously match any low-data feed
        nasem_cat = (nasem_feed.get("category", "") or "").lower()
        nasem_type_str = (nasem_feed.get("type", "") or "").lower()
        if any(skip in nasem_cat for skip in ("vitamin", "mineral", "premix")):
            continue
        if any(skip in nasem_name for skip in ("premix", "vit_a_", "vit_d_", "vit_e_")):
            continue

        # Skip templates with no real nutrient data (all key nutrients zero/missing)
        nasem_nutrients = nasem_feed.get("nutrients", {})
        key_vals = [nasem_nutrients.get(k, 0) for k in ("Fd_CP", "Fd_NDF", "Fd_ADF", "Fd_CFat", "Fd_Ash")]
        if sum(abs(v) for v in key_vals) < 0.1:
            continue

        nasem_display = nasem_feed.get("nasem_name", nasem_name)

        # Text similarity (weight: 0.4)
        text_sim = max(
            _text_similarity(fp_name, nasem_name),
            _text_similarity(fp_name, nasem_display),
        )

        # Nutrient distance (weight: 0.3, inverted to score)
        ndist = _nutrient_distance(fp_nasem_vals, nasem_nutrients)
        nutrient_score = max(0, 1.0 - ndist)

        # Category overlap (weight: 0.3, normalized to 0-1)
        cat_score = min(_category_overlap(fp_categories, nasem_feed) / 3.0, 1.0)

        # Combined score
        score = 0.4 * text_sim + 0.3 * nutrient_score + 0.3 * cat_score

        if score > best_score:
            best_score = score
            best_name = nasem_name

    return best_name, best_score


# ---------------------------------------------------------------------------
# Feedbase builder: read Feedipedia DB → produce NASEM feed entries
# ---------------------------------------------------------------------------


def _sanitize_feed_key(name: str) -> str:
    """Convert a Feedipedia name to a valid feed key."""
    key = name.lower()
    key = re.sub(r"\([^)]*\)", "", key)   # remove parenthetical
    key = re.sub(r"[^a-z0-9]+", "_", key) # non-alphanum to underscore
    key = key.strip("_")
    # Prefix with fp_ to avoid collisions with existing NASEM feeds
    return f"fp_{key}"


def build_feedbase(
    db_path: Path = FEEDIPEDIA_DB,
    nasem_path: Path = NASEM_FEEDBASE_PATH,
    min_nutrients: int = 5,
    dry_run: bool = False,
    output_path: Path = OUTPUT_PATH,
) -> Dict[str, Any]:
    """Build an enriched NASEM feedbase by adding Feedipedia feeds.

    Args:
        db_path: Path to feedipedia.db
        nasem_path: Path to existing nasem_feedbase.json
        min_nutrients: Minimum mapped nutrients required to include a feed
        dry_run: If True, don't write output file

    Returns:
        Stats dict with counts
    """
    # Load existing NASEM feedbase
    with nasem_path.open("r") as f:
        nasem_data = json.load(f)

    nasem_feeds = nasem_data["default_dairy_cow_nasem"]["feeds"]
    template_feeds = dict(nasem_feeds)
    original_count = len(template_feeds)
    logger.info("Loaded %d existing NASEM feeds", original_count)

    # Open Feedipedia DB
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Get all successfully crawled feeds
    feeds = conn.execute(
        "SELECT node_id, name, scientific_name, family, categories "
        "FROM feeds WHERE status = 'done' ORDER BY name"
    ).fetchall()
    logger.info("Found %d crawled Feedipedia feeds", len(feeds))

    stats = {
        "feedipedia_total": len(feeds),
        "added": 0,
        "skipped_low_data": 0,
        "skipped_no_subfeed": 0,
        "template_matches": defaultdict(int),
    }

    for feed in feeds:
        node_id = feed["node_id"]
        fp_name = feed["name"]
        fp_categories = json.loads(feed["categories"] or "[]")

        # Get sub-feeds and their nutrients
        sub_feeds = conn.execute(
            "SELECT sub_node_id, name FROM sub_feeds WHERE parent_node_id = ?",
            (node_id,)
        ).fetchall()

        if not sub_feeds:
            stats["skipped_no_subfeed"] += 1
            continue

        for sf in sub_feeds:
            sf_id = sf["sub_node_id"]
            sf_name = sf["name"]

            # Get nutrients for this sub-feed
            nutrient_rows = conn.execute(
                "SELECT nutrient_name, unit, avg, section FROM nutrients "
                "WHERE sub_node_id = ?",
                (sf_id,)
            ).fetchall()

            if not nutrient_rows:
                continue

            raw_nutrients = [dict(r) for r in nutrient_rows]

            # Layer 2: Map to NASEM columns
            nasem_vals = map_feedipedia_nutrients(raw_nutrients)

            # Filter: need minimum useful data
            mapped_root_count = sum(1 for k in nasem_vals if k in ROOT_NUTRIENTS)
            if mapped_root_count < min_nutrients:
                stats["skipped_low_data"] += 1
                continue

            # Find best NASEM template
            template_name, match_score = find_best_template(
                sf_name, fp_categories, nasem_vals, template_feeds
            )

            if not template_name:
                stats["skipped_low_data"] += 1
                continue

            stats["template_matches"][template_name] += 1
            template_feed = template_feeds[template_name]
            template_nutrients = dict(template_feed.get("nutrients", {}))

            # Layer 1: Apply overrides with consistency adjustment
            adjusted_nutrients = adjust_template(template_nutrients, nasem_vals)

            # Build the new feed entry
            feed_key = _sanitize_feed_key(sf_name)

            # Skip if key already exists (don't overwrite NASEM originals)
            if feed_key in nasem_feeds:
                # Append node_id to make unique
                feed_key = f"{feed_key}_{sf_id}"

            # Determine category from Feedipedia categories
            category = template_feed.get("category", "Unknown")
            if fp_categories:
                # Use first Feedipedia category, falling back to template
                category = fp_categories[0]

            # Determine feed type (Forage vs Concentrate) from Fd_Conc
            feed_type = "Concentrate" if adjusted_nutrients.get("Fd_Conc", 0) >= 50 else "Forage"

            new_feed = {
                "dm_percent": adjusted_nutrients.get("Fd_DM", template_feed.get("dm_percent", 90.0)),
                "cost_per_kg": template_feed.get("cost_per_kg", 0.0),
                "nutrients": adjusted_nutrients,
                "nasem_name": sf_name,
                "category": category,
                "type": feed_type,
                "Fd_Libr": "Feedipedia",
                "UID": f"feedipedia_{sf_id}",
                "_template": template_name,
                "_template_score": round(match_score, 3),
                "_feedipedia_node_id": node_id,
                "_feedipedia_sub_node_id": sf_id,
                "_source": "Feedipedia (CC-BY-4.0, INRA/CIRAD/AFZ/FAO)",
                "_mapped_nutrients": sorted(nasem_vals.keys()),
            }

            nasem_feeds[feed_key] = new_feed
            stats["added"] += 1

    conn.close()

    # Output
    final_count = len(nasem_feeds)
    logger.info(
        "Feedbase enrichment complete: %d original + %d new = %d total feeds",
        original_count, stats["added"], final_count,
    )

    if not dry_run:
        with output_path.open("w") as f:
            json.dump(nasem_data, f, indent=2, ensure_ascii=False)
        logger.info("Written to %s (%.1f MB)", output_path, output_path.stat().st_size / 1024 / 1024)
    else:
        logger.info("[DRY RUN] Would write to %s", output_path)

    return {
        "original_feeds": original_count,
        "feedipedia_total": stats["feedipedia_total"],
        "added": stats["added"],
        "skipped_low_data": stats["skipped_low_data"],
        "skipped_no_subfeed": stats["skipped_no_subfeed"],
        "final_total": final_count,
        "top_templates": sorted(
            stats["template_matches"].items(), key=lambda x: -x[1]
        )[:20],
    }


def print_stats(stats: Dict) -> None:
    """Pretty-print build statistics."""
    print(f"\n{'=' * 60}")
    print(f"  Feedipedia → NASEM Feedbase Build Results")
    print(f"{'=' * 60}")
    print(f"  Original NASEM feeds:     {stats['original_feeds']:>6}")
    print(f"  Feedipedia feeds crawled:  {stats['feedipedia_total']:>6}")
    print(f"  New feeds added:           {stats['added']:>6}")
    print(f"  Skipped (low data):        {stats['skipped_low_data']:>6}")
    print(f"  Skipped (no sub-feed):     {stats['skipped_no_subfeed']:>6}")
    print(f"  Final feedbase total:      {stats['final_total']:>6}")
    print(f"{'=' * 60}")

    if stats.get("top_templates"):
        print(f"\n  Most-used NASEM templates:")
        for template, count in stats["top_templates"]:
            print(f"    {count:>4}× {template}")
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build enriched NASEM feedbase from Feedipedia data."
    )
    parser.add_argument(
        "--db", type=Path, default=FEEDIPEDIA_DB,
        help=f"Feedipedia SQLite database (default: {FEEDIPEDIA_DB})"
    )
    parser.add_argument(
        "--nasem", type=Path, default=NASEM_FEEDBASE_PATH,
        help=f"Existing NASEM feedbase JSON (default: {NASEM_FEEDBASE_PATH})"
    )
    parser.add_argument(
        "--output", type=Path, default=OUTPUT_PATH,
        help=f"Output path (default: {OUTPUT_PATH})"
    )
    parser.add_argument(
        "--min-nutrients", type=int, default=5,
        help="Minimum mapped root nutrients to include a feed (default: 5)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview without writing output"
    )
    parser.add_argument(
        "--stats", action="store_true",
        help="Just dump mapping coverage stats from the DB"
    )
    args = parser.parse_args()

    if args.stats:
        # Quick stats from DB
        conn = sqlite3.connect(str(args.db))
        total_nutrients = conn.execute("SELECT COUNT(*) FROM nutrients").fetchone()[0]
        unique_names = conn.execute(
            "SELECT DISTINCT nutrient_name, unit FROM nutrients"
        ).fetchall()

        mapped = 0
        unmapped = []
        for name, unit in unique_names:
            if (name, unit) in FEEDIPEDIA_TO_NASEM:
                mapped += 1
            else:
                unmapped.append(f"  {name} ({unit})")

        print(f"\nMapping coverage:")
        print(f"  Total nutrient types: {len(unique_names)}")
        print(f"  Mapped to NASEM:      {mapped}")
        print(f"  Unmapped:             {len(unmapped)}")
        if unmapped:
            print(f"\n  Unmapped nutrients:")
            for u in sorted(unmapped):
                print(f"    {u}")
        conn.close()
        return

    stats = build_feedbase(
        db_path=args.db,
        nasem_path=args.nasem,
        min_nutrients=args.min_nutrients,
        dry_run=args.dry_run,
        output_path=args.output,
    )
    print_stats(stats)


if __name__ == "__main__":
    main()
