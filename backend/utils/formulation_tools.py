import json
import logging
from typing import Dict, List, Any, Optional, Annotated
from langchain_core.tools import tool, InjectedToolCallId
from langchain_core.messages import ToolMessage
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from formulation.optimizer import create_optimizer

logger = logging.getLogger(__name__)


def create_formulation_tools():
    """Create formulation tools that operate on LangGraph state."""
    
    @tool
    def add_feed(
        name: str,
        dry_matter_percent: float,
        nutrients: Dict[str, float],
        cost_per_kg: float,
        state: Annotated[dict, InjectedState],
        tool_call_id: Annotated[str, InjectedToolCallId]
    ) -> Command:
        """
        Add or update feed ingredient in the feed database.
        
        Args:
            name: Feed name (will replace if exists)
            dry_matter_percent: Dry matter percentage (0-100)
            nutrients: Nutrient composition on dry matter basis (e.g., {"CP": 18.5, "NEL": 1.65})
            cost_per_kg: Cost per kg as-fed
            
        Returns:
            State update with confirmation message
        """
        try:
            # Validate inputs
            if not isinstance(name, str) or not name.strip():
                return {}
            
            if not 0 < dry_matter_percent <= 100:
                return {}
            
            if not isinstance(nutrients, dict) or not nutrients:
                return {}
            
            if cost_per_kg < 0:
                return {}
            
            # Validate nutrient values
            for nutrient, value in nutrients.items():
                if not isinstance(value, (int, float)) or value < 0:
                    return {}
            
            # Format feed data
            feed_data = {
                "dm_percent": dry_matter_percent,
                "nutrients": nutrients,
                "cost_per_kg": cost_per_kg
            }
            
            # Update state directly
            current_feed_db = state.get("feed_database", {})
            updated_feed_db = {**current_feed_db, name: feed_data}
            
            # Return Command with state update and tool message
            return Command(update={
                    "feed_database": updated_feed_db,
                    "messages": [
                        ToolMessage(f"Successfully added feed '{name}' to database", tool_call_id=tool_call_id)
                    ]
                }
            )
            
        except Exception as e:
            logger.error(f"Add feed error: {e}")
            return Command(
                update={
                    "messages": [
                        ToolMessage(f"Error adding feed: {str(e)}", tool_call_id=tool_call_id)
                    ]
                }
            )
    
    @tool
    def formulate_ration(
        nutritional_constraints: List[Dict[str, Any]],
        selected_feeds: List[str],
        state: Annotated[dict, InjectedState],
        tool_call_id: Annotated[str, InjectedToolCallId],
        feed_constraints: Optional[Dict[str, Dict]] = None,
        optimization_goal: str = "minimize_cost"
    ) -> Command:
        """
        Formulate optimal ration using flexible constraint system.
        
        Args:
            nutritional_constraints: List of constraint dictionaries:
                - {"type": "concentration", "nutrient": "CP", "min": 16.0, "max": 18.0}
                - {"type": "daily_total", "nutrient": "NEL", "target": 32.0, "daily_intake_kg": 18.0}
                - {"type": "ratio", "numerator": "Ca", "denominator": "P", "min": 1.2, "max": 2.0}
            selected_feeds: List of feed names to include in optimization
            feed_constraints: Optional inclusion limits {"feed_name": {"min": 0, "max": 50}}
            optimization_goal: "minimize_cost" or other objectives
            
        Returns:
            State update with formulation results
        """
        try:
            # Validate inputs
            if not isinstance(nutritional_constraints, list):
                return {}
            
            if not isinstance(selected_feeds, list) or not selected_feeds:
                return {}
            
            # Validate constraint format
            for i, constraint in enumerate(nutritional_constraints):
                if not isinstance(constraint, dict):
                    return {}
                
                constraint_type = constraint.get("type", "")
                if constraint_type not in ["concentration", "daily_total", "ratio"]:
                    return {}
                
                if "nutrient" not in constraint and constraint_type != "ratio":
                    return {}
            
            # Get feed database from state
            feed_database = state.get("feed_database", {})
            if not feed_database:
                return {}
            
            # Check if selected feeds exist
            missing_feeds = [f for f in selected_feeds if f not in feed_database]
            if missing_feeds:
                return {}
            
            # Run optimization
            optimizer = create_optimizer()
            optimizer.set_feeds(feed_database)
            
            optimization_result = optimizer.optimize(
                nutritional_constraints=nutritional_constraints,
                selected_feeds=selected_feeds,
                feed_constraints=feed_constraints or {},
                optimization_goal=optimization_goal
            )
            
            # Return Command with state update and tool message containing the results
            return Command(
                update={
                    "current_formulation": optimization_result,
                    "messages": [
                        ToolMessage(json.dumps(optimization_result, indent=2), tool_call_id=tool_call_id)
                    ]
                }
            )
            
        except Exception as e:
            logger.error(f"Formulation error: {e}")
            return Command(
                update={
                    "messages": [
                        ToolMessage(f"Error formulating ration: {str(e)}", tool_call_id=tool_call_id)
                    ]
                }
            )
    
    @tool
    def check_feeds(
        state: Annotated[dict, InjectedState],
        tool_call_id: Annotated[str, InjectedToolCallId]
    ) -> Command:
        """
        Check and list all feeds in the current feed database.
        
        Returns:
            Formatted string with complete feed database information
        """
        try:
            # Get feed database from state
            feed_database = state.get("feed_database", {})
            
            if not feed_database:
                return Command(
                    update={
                        "messages": [
                            ToolMessage("No feeds currently in the database.", tool_call_id=tool_call_id)
                        ]
                    }
                )
            
            # Format feed information for all feeds
            feed_info = []
            feed_info.append(f"Complete Feed Database ({len(feed_database)} feeds):\n")
            
            for feed_name, feed_data in feed_database.items():
                feed_info.append(f"**{feed_name}**")
                feed_info.append(f"  - Dry Matter: {feed_data.get('dm_percent', 'N/A')}%")
                feed_info.append(f"  - Cost: ${feed_data.get('cost_per_kg', 'N/A')}/kg")
                
                nutrients = feed_data.get('nutrients', {})
                if nutrients:
                    feed_info.append("  - Nutrients (DM basis):")
                    for nutrient, value in nutrients.items():
                        feed_info.append(f"    - {nutrient}: {value}")
                feed_info.append("")
            
            return Command(
                update={
                    "messages": [
                        ToolMessage("\n".join(feed_info), tool_call_id=tool_call_id)
                    ]
                }
            )
            
        except Exception as e:
            logger.error(f"Check feeds error: {e}")
            return Command(
                update={
                    "messages": [
                        ToolMessage(f"Error retrieving feed information: {str(e)}", tool_call_id=tool_call_id)
                    ]
                }
            )
    
    return [add_feed, formulate_ration, check_feeds]


# For backward compatibility and easy import
def get_formulation_tools():
    """Get all formulation tools."""
    return create_formulation_tools()

def get_add_feed_tool():
    """Get just the add_feed tool for coder."""
    tools = create_formulation_tools()
    # Return only the add_feed tool
    return [tool for tool in tools if tool.name == "add_feed"]