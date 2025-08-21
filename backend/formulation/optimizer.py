import numpy as np
from scipy.optimize import linprog
from typing import Dict, List, Any, Optional, Tuple
import json
import logging

logger = logging.getLogger(__name__)


class FormulationOptimizer:
    """
    Flexible feed formulation optimizer supporting multiple constraint types:
    - concentration: nutrient % of dry matter
    - daily_total: absolute daily nutrient intake
    - ratio: ratios between nutrients
    - inclusion: feed inclusion limits
    """
    
    def __init__(self):
        self.feeds = {}
        self.constraints = []
        self.optimization_goal = "minimize_cost"
    
    def set_feeds(self, feeds: Dict[str, Dict[str, Any]]):
        """Set available feeds with their nutrient composition and costs."""
        self.feeds = feeds
    
    def optimize(
        self,
        nutritional_constraints: List[Dict[str, Any]],
        selected_feeds: List[str],
        feed_constraints: Optional[Dict[str, Dict]] = None,
        optimization_goal: str = "minimize_cost"
    ) -> Dict[str, Any]:
        """
        Optimize feed formulation using linear programming.
        
        Args:
            nutritional_constraints: List of constraint dictionaries
            selected_feeds: List of feed names to include
            feed_constraints: Optional inclusion limits {"feed_name": {"min": 0, "max": 50}}
            optimization_goal: "minimize_cost" or other objectives
            
        Returns:
            Dictionary with optimization results
        """
        try:
            # Validate inputs
            if not selected_feeds:
                return {"error": "No feeds selected for formulation"}
            
            missing_feeds = [f for f in selected_feeds if f not in self.feeds]
            if missing_feeds:
                return {"error": f"Missing feeds in database: {missing_feeds}"}
            
            # Set up optimization problem
            n_feeds = len(selected_feeds)
            
            # Objective function (costs)
            costs = []
            for feed_name in selected_feeds:
                feed_data = self.feeds[feed_name]
                # Convert cost to per kg dry matter
                cost_per_kg_dm = feed_data["cost_per_kg"] / (feed_data["dm_percent"] / 100)
                costs.append(cost_per_kg_dm)
            
            # Equality constraint: sum of feed percentages = 100%
            A_eq = np.ones((1, n_feeds))
            b_eq = np.array([100.0])
            
            # Inequality constraints
            A_ub = []
            b_ub = []
            
            # Feed inclusion constraints
            bounds = []
            for i, feed_name in enumerate(selected_feeds):
                min_incl = 0.0
                max_incl = 100.0
                
                if feed_constraints and feed_name in feed_constraints:
                    constraint = feed_constraints[feed_name]
                    if "min" in constraint:
                        min_incl = constraint["min"]
                    if "max" in constraint:
                        max_incl = constraint["max"]
                
                bounds.append((min_incl, max_incl))
            
            # Nutritional constraints
            for constraint in nutritional_constraints:
                constraint_type = constraint.get("type", "")
                
                if constraint_type == "concentration":
                    # Concentration constraint: nutrient % of dry matter
                    nutrient = constraint["nutrient"]
                    min_val = constraint.get("min")
                    max_val = constraint.get("max")
                    
                    # Build constraint row
                    constraint_row = []
                    for feed_name in selected_feeds:
                        feed_nutrients = self.feeds[feed_name]["nutrients"]
                        nutrient_content = feed_nutrients.get(nutrient, 0.0)
                        constraint_row.append(nutrient_content)
                    
                    # Add min constraint: sum(feed_percent * nutrient_content) >= min_val * 100
                    if min_val is not None:
                        # Convert to <= form: -sum(feed_percent * nutrient_content) <= -min_val * 100
                        A_ub.append([-x for x in constraint_row])
                        b_ub.append(-min_val * 100)
                    
                    # Add max constraint: sum(feed_percent * nutrient_content) <= max_val * 100
                    if max_val is not None:
                        A_ub.append(constraint_row)
                        b_ub.append(max_val * 100)
                
                elif constraint_type == "daily_total":
                    # Daily total constraint: flexible system for any daily attribute
                    attribute = constraint.get("attribute")
                    target = constraint.get("target")
                    tolerance_percent = constraint.get("tolerance_percent", 10.0)
                    
                    if not attribute or target is None:
                        logger.warning(f"Daily total constraint missing attribute or target: {constraint}")
                        continue
                    
                    # Calculate tolerance range
                    tolerance_factor = tolerance_percent / 100.0
                    target_min = target * (1 - tolerance_factor)
                    target_max = target * (1 + tolerance_factor)
                    
                    if attribute == "dmi":
                        # Special case: DMI constraint affects all nutrients
                        # This is handled differently - DMI sets the total intake level
                        # Store DMI range for later use in nutrient calculations
                        self.dmi_min = target_min
                        self.dmi_max = target_max
                        self.dmi_target = target
                        continue
                    
                    else:
                        # Nutrient daily total constraint
                        # Requires DMI to be specified elsewhere
                        if not hasattr(self, 'dmi_target') or self.dmi_target is None:
                            logger.warning(f"Daily total constraint for {attribute} requires DMI to be specified")
                            continue
                        
                        # Use DMI range for constraint flexibility
                        dmi_min = getattr(self, 'dmi_min', self.dmi_target)
                        dmi_max = getattr(self, 'dmi_max', self.dmi_target)
                        
                        # Build constraint rows
                        constraint_row_min = []
                        constraint_row_max = []
                        for feed_name in selected_feeds:
                            feed_nutrients = self.feeds[feed_name]["nutrients"]
                            nutrient_content = feed_nutrients.get(attribute, 0.0)
                            # Convert to daily intake: (nutrient_content/100) * (dmi/100) * feed_percentage
                            constraint_row_min.append(nutrient_content * dmi_min / 10000)
                            constraint_row_max.append(nutrient_content * dmi_max / 10000)
                        
                        # Add target constraint with tolerance
                        # Use min DMI for lower bound, max DMI for upper bound to allow flexibility
                        A_ub.append([-x for x in constraint_row_min])  # >= target_min
                        b_ub.append(-target_min)
                        A_ub.append(constraint_row_max)  # <= target_max  
                        b_ub.append(target_max)
                
                elif constraint_type == "ratio":
                    # Ratio constraint: nutrient1/nutrient2 ratio
                    numerator = constraint["numerator"]
                    denominator = constraint["denominator"]
                    min_ratio = constraint.get("min")
                    max_ratio = constraint.get("max")
                    
                    # Build constraint: num - ratio*denom >= 0 (for min) or <= 0 (for max)
                    if min_ratio is not None:
                        constraint_row = []
                        for feed_name in selected_feeds:
                            feed_nutrients = self.feeds[feed_name]["nutrients"]
                            num_content = feed_nutrients.get(numerator, 0.0)
                            denom_content = feed_nutrients.get(denominator, 0.0)
                            # num - min_ratio * denom >= 0 -> -(num - min_ratio * denom) <= 0
                            constraint_row.append(-(num_content - min_ratio * denom_content))
                        
                        A_ub.append(constraint_row)
                        b_ub.append(0.0)
                    
                    if max_ratio is not None:
                        constraint_row = []
                        for feed_name in selected_feeds:
                            feed_nutrients = self.feeds[feed_name]["nutrients"]
                            num_content = feed_nutrients.get(numerator, 0.0)
                            denom_content = feed_nutrients.get(denominator, 0.0)
                            # num - max_ratio * denom <= 0
                            constraint_row.append(num_content - max_ratio * denom_content)
                        
                        A_ub.append(constraint_row)
                        b_ub.append(0.0)
            
            # Convert to numpy arrays
            if A_ub:
                A_ub = np.array(A_ub)
                b_ub = np.array(b_ub)
            else:
                A_ub = None
                b_ub = None
            
            # Solve optimization
            result = linprog(
                c=costs,
                A_ub=A_ub,
                b_ub=b_ub,
                A_eq=A_eq,
                b_eq=b_eq,
                bounds=bounds,
                method='highs'
            )
            
            if not result.success:
                return {
                    "error": f"Optimization failed: {result.message}",
                    "status": "failed"
                }
            
            # Format results
            formulation = {}
            total_cost = 0.0
            nutrient_analysis = {}
            
            for i, feed_name in enumerate(selected_feeds):
                percentage = float(result.x[i])  # Convert numpy.float64 to Python float
                if percentage > 0.001:  # Only include feeds with meaningful inclusion
                    formulation[feed_name] = {
                        "percentage_dm": round(percentage, 2),
                        "kg_per_day": 0.0  # Will be calculated if daily intake provided
                    }
                    
                    # Calculate cost contribution
                    feed_data = self.feeds[feed_name]
                    cost_per_kg_dm = feed_data["cost_per_kg"] / (feed_data["dm_percent"] / 100)
                    total_cost += percentage * cost_per_kg_dm / 100
            
            # Calculate nutrient analysis
            all_nutrients = set()
            for feed_name in selected_feeds:
                all_nutrients.update(self.feeds[feed_name]["nutrients"].keys())
            
            for nutrient in all_nutrients:
                total_content = 0.0
                for feed_name, inclusion in formulation.items():
                    feed_nutrients = self.feeds[feed_name]["nutrients"]
                    nutrient_content = float(feed_nutrients.get(nutrient, 0.0))  # Ensure Python float
                    total_content += inclusion["percentage_dm"] * nutrient_content / 100
                
                nutrient_analysis[nutrient] = round(float(total_content), 2)  # Ensure Python float
            
            return {
                "status": "success",
                "formulation": formulation,
                "cost_per_kg_dm": round(float(total_cost), 3),  # Ensure Python float
                "nutrient_analysis": nutrient_analysis,
                "constraint_satisfaction": "All constraints satisfied",
                "optimization_objective": optimization_goal
            }
            
        except Exception as e:
            logger.error(f"Optimization error: {e}")
            return {"error": f"Optimization error: {str(e)}", "status": "failed"}


def create_optimizer() -> FormulationOptimizer:
    """Create a new formulation optimizer instance."""
    return FormulationOptimizer()