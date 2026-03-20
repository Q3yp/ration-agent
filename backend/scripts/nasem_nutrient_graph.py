"""Layer 1: NASEM Internal Nutrient Dependency Graph.

Defines the relationships between NASEM Fd_* nutrient columns so that when
a "root" nutrient is overridden from an external source (e.g., Feedipedia),
dependent columns can be adjusted to maintain internal consistency.

The graph organises nutrients into:
  - ROOT columns: independently measured, can be directly overridden
  - RATIO columns: expressed as % of a parent (e.g. Fd_Lys_CP = lysine as % CP)
  - PROPORTIONAL columns: scale linearly with a parent (e.g. Fd_FA ∝ Fd_CFat)
  - COEFFICIENT columns: feed-type properties, inherited from template
  - DERIVED columns: can be recalculated from other values

When overriding a root, dependents are handled by type:
  - RATIO deps: keep the ratio value (already consistent)
  - PROPORTIONAL deps: scale by (new_root / old_root) ratio
  - COEFFICIENT deps: keep from template (no change)
  - DERIVED deps: recalculate

Data: Feedipedia CC-BY-4.0 by INRA, CIRAD, AFZ, and FAO.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


class DepType(Enum):
    """How a dependent column relates to its parent."""

    RATIO = auto()          # Expressed as % of parent; value stays on override
    PROPORTIONAL = auto()   # Absolute value that scales linearly with parent
    COEFFICIENT = auto()    # Feed-type property; always inherited from template
    DERIVED = auto()        # Re-calculated from a formula


@dataclass
class Dependency:
    """One edge in the dependency graph: child depends on parent."""

    child: str              # NASEM column name (e.g. "Fd_Lys_CP")
    parent: str             # NASEM column that child depends on (e.g. "Fd_CP")
    dep_type: DepType
    # For PROPORTIONAL: reference column used for scaling ratio
    # For DERIVED: callable  (parent_vals: dict) -> float
    scale_ref: Optional[str] = None
    derive_fn: Optional[Callable[[Dict[str, float]], Optional[float]]] = None


# ---------------------------------------------------------------------------
# Root nutrients — can be directly overridden from external data
# ---------------------------------------------------------------------------

ROOT_NUTRIENTS: Set[str] = {
    # Main analysis
    "Fd_DM",
    "Fd_CP",
    "Fd_NDF",
    "Fd_ADF",
    "Fd_Lg",       # Lignin
    "Fd_CFat",     # Crude fat / Ether extract
    "Fd_Ash",
    "Fd_St",       # Starch
    "Fd_WSC",      # Water-soluble carbohydrates / Total sugars
    "Fd_DE_Base",  # Digestible energy base (Mcal/kg)
    # Macro minerals (% DM)
    "Fd_Ca", "Fd_P", "Fd_Mg", "Fd_K", "Fd_Na", "Fd_Cl", "Fd_S",
    # Trace minerals (mg/kg or ppm)
    "Fd_Fe", "Fd_Mn", "Fd_Zn", "Fd_Cu", "Fd_Co", "Fd_Se", "Fd_I",
    "Fd_Cr", "Fd_Mo",
}


# ---------------------------------------------------------------------------
# Dependency edges
# ---------------------------------------------------------------------------

def _build_dependencies() -> List[Dependency]:
    """Build the full list of nutrient dependency edges."""
    deps: List[Dependency] = []

    # --- CP dependents (amino acids as % of CP) ---
    aa_columns = [
        "Fd_Arg_CP", "Fd_His_CP", "Fd_Ile_CP", "Fd_Leu_CP",
        "Fd_Lys_CP", "Fd_Met_CP", "Fd_Phe_CP", "Fd_Thr_CP",
        "Fd_Trp_CP", "Fd_Val_CP",
    ]
    for aa in aa_columns:
        deps.append(Dependency(child=aa, parent="Fd_CP", dep_type=DepType.RATIO))

    # CP fractions (A, B, C as % of CP — must sum to ~100)
    for frac in ["Fd_CPARU", "Fd_CPBRU", "Fd_CPCRU"]:
        deps.append(Dependency(child=frac, parent="Fd_CP", dep_type=DepType.COEFFICIENT))

    # CP solubility fraction
    deps.append(Dependency(child="Fd_CPs_CP", parent="Fd_CP", dep_type=DepType.COEFFICIENT))

    # Non-protein nitrogen as % CP
    deps.append(Dependency(child="Fd_NPN_CP", parent="Fd_CP", dep_type=DepType.COEFFICIENT))

    # Rumen undegradable protein — feed-type specific
    deps.append(Dependency(child="Fd_RUP_base", parent="Fd_CP", dep_type=DepType.COEFFICIENT))
    deps.append(Dependency(child="Fd_KdRUP", parent="Fd_CP", dep_type=DepType.COEFFICIENT))
    deps.append(Dependency(child="Fd_dcRUP", parent="Fd_CP", dep_type=DepType.COEFFICIENT))

    # --- NDF dependents ---
    deps.append(Dependency(child="Fd_DNDF48_NDF", parent="Fd_NDF", dep_type=DepType.COEFFICIENT))
    deps.append(Dependency(child="Fd_DNDF48_input", parent="Fd_NDF", dep_type=DepType.COEFFICIENT))
    deps.append(Dependency(child="Fd_NDFIP", parent="Fd_NDF", dep_type=DepType.COEFFICIENT))

    # --- ADF dependents ---
    deps.append(Dependency(child="Fd_ADFIP", parent="Fd_ADF", dep_type=DepType.COEFFICIENT))

    # --- Fat/EE dependents ---
    # Fd_FA (total fatty acids) scales proportionally with Fd_CFat
    deps.append(Dependency(
        child="Fd_FA", parent="Fd_CFat",
        dep_type=DepType.PROPORTIONAL, scale_ref="Fd_CFat",
    ))
    # Individual FA profile — ratios of total FA (stay as-is)
    fa_profile_cols = [
        "Fd_C120_FA", "Fd_C140_FA", "Fd_C160_FA", "Fd_C161_FA",
        "Fd_C180_FA", "Fd_C181t_FA", "Fd_C181c_FA", "Fd_C182_FA",
        "Fd_C183_FA", "Fd_OtherFA_FA",
    ]
    for fa in fa_profile_cols:
        deps.append(Dependency(child=fa, parent="Fd_FA", dep_type=DepType.RATIO))

    # Fat digestibility — feed-type coefficient
    deps.append(Dependency(child="Fd_dcFA", parent="Fd_CFat", dep_type=DepType.COEFFICIENT))

    # --- Starch dependents ---
    deps.append(Dependency(child="Fd_dcSt", parent="Fd_St", dep_type=DepType.COEFFICIENT))

    # --- Mineral absorption coefficients ---
    mineral_ac_pairs = [
        ("Fd_acCa_input", "Fd_Ca"),
        ("Fd_acPtot_input", "Fd_P"),
        ("Fd_acMg_input", "Fd_Mg"),
        ("Fd_acK_input", "Fd_K"),
        ("Fd_acNa_input", "Fd_Na"),
        ("Fd_acCl_input", "Fd_Cl"),
        ("Fd_acFe_input", "Fd_Fe"),
        ("Fd_acMn_input", "Fd_Mn"),
        ("Fd_acZn_input", "Fd_Zn"),
        ("Fd_acCu_input", "Fd_Cu"),
    ]
    for ac_col, mineral_col in mineral_ac_pairs:
        deps.append(Dependency(child=ac_col, parent=mineral_col, dep_type=DepType.COEFFICIENT))

    # Phosphorus fractions — coefficients
    deps.append(Dependency(child="Fd_Pinorg_P", parent="Fd_P", dep_type=DepType.COEFFICIENT))
    deps.append(Dependency(child="Fd_Porg_P", parent="Fd_P", dep_type=DepType.COEFFICIENT))

    # --- Derived: Fd_Conc (concentrate flag) from fiber content ---
    def _derive_conc(vals: Dict[str, float]) -> Optional[float]:
        ndf = vals.get("Fd_NDF")
        adf = vals.get("Fd_ADF")
        if ndf is not None and adf is not None:
            # Rule of thumb: concentrates have NDF < 35% and ADF < 20%
            # Keep existing logic from NASEM convention
            return 0.0 if ndf > 35 else 100.0
        return None

    deps.append(Dependency(
        child="Fd_Conc", parent="Fd_NDF",
        dep_type=DepType.DERIVED, derive_fn=_derive_conc,
    ))

    # Vitamins — pure template values, no dependency on roots
    # They're not in any dependency chain, so they naturally inherit from template

    return deps


# Singleton instance
DEPENDENCIES: List[Dependency] = _build_dependencies()

# Lookup: child -> Dependency
_CHILD_LOOKUP: Dict[str, Dependency] = {d.child: d for d in DEPENDENCIES}

# All dependent columns (not directly overridable from external data)
DEPENDENT_COLUMNS: Set[str] = {d.child for d in DEPENDENCIES}

# All columns that can be overridden (directly from Feedipedia)
# = ROOT + RATIO deps that also appear in Feedipedia mapping
OVERRIDABLE_FROM_EXTERNAL: Set[str] = ROOT_NUTRIENTS | {
    d.child for d in DEPENDENCIES if d.dep_type == DepType.RATIO
}


# ---------------------------------------------------------------------------
# Consistency adjustment engine
# ---------------------------------------------------------------------------


def adjust_template(
    template_nutrients: Dict[str, float],
    overrides: Dict[str, float],
) -> Dict[str, float]:
    """Apply external overrides to a cloned NASEM template, maintaining consistency.

    Args:
        template_nutrients: Full dict of Fd_* values cloned from best-matching NASEM feed.
        overrides: Dict of Fd_* column -> new value from Feedipedia (after Layer 2 mapping).

    Returns:
        New dict with overrides applied and dependents adjusted.
    """
    result = dict(template_nutrients)

    # 1. Apply all direct overrides (root + ratio columns from external data)
    for col, val in overrides.items():
        if val is not None:
            result[col] = val

    # 2. Walk the dependency graph and adjust dependents
    for dep in DEPENDENCIES:
        if dep.child in overrides:
            # This dependent was directly overridden from external data — skip adjustment
            continue

        parent_old = template_nutrients.get(dep.parent)
        parent_new = result.get(dep.parent)

        if dep.dep_type == DepType.RATIO:
            # Ratio stays from template (already expressed as % of parent)
            # No adjustment needed
            pass

        elif dep.dep_type == DepType.PROPORTIONAL:
            # Scale proportionally
            if parent_old and parent_old != 0 and parent_new is not None:
                ratio = parent_new / parent_old
                old_val = template_nutrients.get(dep.child, 0)
                result[dep.child] = old_val * ratio

        elif dep.dep_type == DepType.COEFFICIENT:
            # Keep from template — no change
            pass

        elif dep.dep_type == DepType.DERIVED:
            if dep.derive_fn is not None:
                derived = dep.derive_fn(result)
                if derived is not None:
                    result[dep.child] = derived

    # 3. Validation: basic sanity checks
    _validate_nutrients(result)

    return result


def _validate_nutrients(nutrients: Dict[str, float]) -> None:
    """In-place fix obvious inconsistencies."""
    ndf = nutrients.get("Fd_NDF", 0)
    adf = nutrients.get("Fd_ADF", 0)
    lg = nutrients.get("Fd_Lg", 0)

    # ADF cannot exceed NDF
    if adf > ndf and ndf > 0:
        nutrients["Fd_ADF"] = ndf * 0.95

    # Lignin cannot exceed ADF
    if lg > adf and adf > 0:
        nutrients["Fd_Lg"] = adf * 0.5

    # CP fractions should sum to ~100
    a = nutrients.get("Fd_CPARU", 0)
    b = nutrients.get("Fd_CPBRU", 0)
    c = nutrients.get("Fd_CPCRU", 0)
    total = a + b + c
    if total > 0 and abs(total - 100) > 5:
        # Normalize
        nutrients["Fd_CPARU"] = a * 100 / total
        nutrients["Fd_CPBRU"] = b * 100 / total
        nutrients["Fd_CPCRU"] = c * 100 / total

    # DM must be between 1 and 100
    dm = nutrients.get("Fd_DM", 0)
    if dm < 1:
        nutrients["Fd_DM"] = 1.0
    elif dm > 100:
        nutrients["Fd_DM"] = 100.0


def get_dependency_info(column: str) -> Optional[Dependency]:
    """Lookup dependency info for a given NASEM column."""
    return _CHILD_LOOKUP.get(column)


def list_dependents(parent: str) -> List[Dependency]:
    """List all columns that depend on the given parent column."""
    return [d for d in DEPENDENCIES if d.parent == parent]
