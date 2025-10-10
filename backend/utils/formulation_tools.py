import json
import logging
import re
from typing import Dict, List, Any, Optional, Annotated
from datetime import datetime
from pathlib import Path
import pandas as pd
from langchain_core.tools import tool, InjectedToolCallId
from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from langgraph.config import get_store

from formulation.optimizer import create_optimizer

logger = logging.getLogger(__name__)


def sanitize_feed_name(name: str) -> str:
    """
    Sanitize feed names for Excel export by removing control characters and null bytes.
    
    Args:
        name: Original feed name
        
    Returns:
        Sanitized feed name safe for Excel
    """
    if not isinstance(name, str):
        return str(name)
    
    # Remove control characters (0x00-0x1F and 0x7F-0x9F)
    sanitized = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', name)
    
    # Remove any remaining null bytes
    sanitized = sanitized.replace('\x00', '')
    
    # Strip whitespace
    sanitized = sanitized.strip()
    
    # If name becomes empty after sanitization, provide a default
    if not sanitized:
        sanitized = "饲料"
    
    return sanitized


def create_formulation_tools(session_id: str = None, animal_type: str = "dairy_cow"):
    """Create formulation tools that operate on LangGraph state.

    Args:
        session_id: Session ID for workspace path resolution (required for export_formulation)
        animal_type: Animal type for feedbase filtering (dairy_cow, beef_cow, cat, dog)
    """
    
    @tool
    async def add_feed(
        feed_base_name: str,
        name: str,
        dm_percent: Optional[float] = None,
        dry_matter_percent: Optional[float] = None,
        nutrients: Dict[str, float] = None,
        cost_per_kg: float = 0.0,
        state: Annotated[dict, InjectedState] = None,
        tool_call_id: Annotated[str, InjectedToolCallId] = None,
        config: RunnableConfig = None
    ) -> Command:
        """
        Add or update feed ingredient in a specific feedbase.
        
        Args:
            feed_base_name: Name of the feedbase to add the feed to
            name: Feed name (will replace if exists)
            dm_percent: Dry matter percentage (0-100)
            nutrients: Nutrient composition on dry matter basis (e.g., {"CP": 18.5, "NEL": 1.65})
            cost_per_kg: Cost per kg as-fed
            
        Returns:
            Confirmation message
        """
        try:
            # Validate inputs
            if not isinstance(feed_base_name, str) or not feed_base_name.strip():
                return Command(
                    update={
                        "messages": [
                            ToolMessage("Error: Feedbase name must be a non-empty string", tool_call_id=tool_call_id)
                        ]
                    }
                )
                
            if not isinstance(name, str) or not name.strip():
                return Command(
                    update={
                        "messages": [
                            ToolMessage("Error: Feed name must be a non-empty string", tool_call_id=tool_call_id)
                        ]
                    }
                )
            
            # Accept legacy param name
            if dm_percent is None and dry_matter_percent is not None:
                dm_percent = dry_matter_percent
            if dm_percent is None:
                return Command(
                    update={
                        "messages": [
                            ToolMessage("Error: dm_percent (dry matter %) is required", tool_call_id=tool_call_id)
                        ]
                    }
                )
            if not 0 < dm_percent <= 100:
                return Command(
                    update={
                        "messages": [
                            ToolMessage("Error: Dry matter percentage must be between 0 and 100", tool_call_id=tool_call_id)
                        ]
                    }
                )
            
            if not isinstance(nutrients, dict) or not nutrients:
                return Command(
                    update={
                        "messages": [
                            ToolMessage("Error: Nutrients must be a non-empty dictionary", tool_call_id=tool_call_id)
                        ]
                    }
                )
            
            if cost_per_kg < 0:
                return Command(
                    update={
                        "messages": [
                            ToolMessage("Error: Cost per kg must be non-negative", tool_call_id=tool_call_id)
                        ]
                    }
                )
            
            # Validate nutrient values
            for nutrient, value in nutrients.items():
                if not isinstance(value, (int, float)) or value < 0:
                    return Command(
                        update={
                            "messages": [
                                ToolMessage(f"Error: Nutrient '{nutrient}' must have a non-negative numeric value", tool_call_id=tool_call_id)
                            ]
                        }
                    )
            
            # Get user_id from config and access store
            user_id = config["configurable"].get("user_id")
            if not user_id:
                return Command(
                    update={
                        "messages": [
                            ToolMessage("Error: User ID not found in configuration", tool_call_id=tool_call_id)
                        ]
                    }
                )
            
            store = get_store()
            namespace = ("feedbases", user_id, feed_base_name)
            
            # Get existing feedbase or create new one
            existing_feedbase = await store.aget(namespace, "data")
            if existing_feedbase:
                feedbase_data = existing_feedbase.value
            else:
                # Create new feedbase with animal_type metadata
                feedbase_data = {
                    "animal_type": animal_type,
                    "feeds": {}
                }
            
            # Format feed data
            feed_data = {
                "dm_percent": dm_percent,
                "nutrients": nutrients,
                "cost_per_kg": cost_per_kg
            }
            
            # Add feed to feedbase
            sanitized_name = sanitize_feed_name(name)
            feedbase_data["feeds"][sanitized_name] = feed_data
            
            # Store updated feedbase
            await store.aput(namespace, "data", feedbase_data)
            
            # Return success message
            return Command(
                update={
                    "messages": [
                        ToolMessage(f"Successfully added feed '{sanitized_name}' to feedbase '{feed_base_name}'", tool_call_id=tool_call_id)
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
    async def list_feed_bases(
        state: Annotated[dict, InjectedState],
        tool_call_id: Annotated[str, InjectedToolCallId],
        config: RunnableConfig
    ) -> Command:
        """
        List all available feedbases for the user filtered by animal type.

        Returns:
            List of available feedbase names matching the current animal type
        """
        try:
            # Get user_id from config and access store
            user_id = config["configurable"].get("user_id")
            if not user_id:
                return Command(
                    update={
                        "messages": [
                            ToolMessage("Error: User ID not found in configuration", tool_call_id=tool_call_id)
                        ]
                    }
                )

            store = get_store()
            namespace = ("feedbases", user_id)

            # Search for all feedbases for this user
            feedbase_entries = await store.asearch(namespace)

            if not feedbase_entries:
                return Command(
                    update={
                        "messages": [
                            ToolMessage("No feedbases found for this user.", tool_call_id=tool_call_id)
                        ]
                    }
                )

            # Filter feedbases by animal_type
            filtered_feedbases = []
            for entry in feedbase_entries:
                feedbase_data = entry.value
                feedbase_animal_type = feedbase_data.get("animal_type", "dairy_cow")  # Default to dairy_cow for legacy data

                if feedbase_animal_type == animal_type:
                    filtered_feedbases.append(entry)

            if not filtered_feedbases:
                return Command(
                    update={
                        "messages": [
                            ToolMessage(f"No feedbases found for animal type '{animal_type}'.", tool_call_id=tool_call_id)
                        ]
                    }
                )

            # Extract feedbase names from namespace
            feedbase_info = []
            feedbase_info.append(f"Available Feedbases for {animal_type} ({len(filtered_feedbases)}):\n")

            for entry in filtered_feedbases:
                # Namespace structure: ("feedbases", user_id, feedbase_name)
                feedbase_name = entry.namespace[2]  # Get feedbase name from namespace
                feedbase_data = entry.value
                feed_count = len(feedbase_data.get("feeds", {}))
                feedbase_info.append(f"- **{feedbase_name}** ({feed_count} feeds)")

            return Command(
                update={
                    "messages": [
                        ToolMessage("\n".join(feedbase_info), tool_call_id=tool_call_id)
                    ]
                }
            )
            
        except Exception as e:
            logger.error(f"List feedbases error: {e}")
            return Command(
                update={
                    "messages": [
                        ToolMessage(f"Error listing feedbases: {str(e)}", tool_call_id=tool_call_id)
                    ]
                }
            )
    
    @tool
    async def formulate_ration(
        feed_base_name: str,
        nutritional_constraints: List[Dict[str, Any]],
        selected_feeds: List[str],
        state: Annotated[dict, InjectedState],
        tool_call_id: Annotated[str, InjectedToolCallId],
        config: RunnableConfig,
        feed_constraints: Optional[Dict[str, Dict]] = None,
        optimization_goal: str = "minimize_cost"
    ) -> Command:
        """
        Formulate optimal ration using flexible constraint system with tolerance support.
        Automatically calculates daily feed amounts when DMI is specified in constraints.
        
        Args:
            feed_base_name: Name of the feedbase to use for formulation
            nutritional_constraints: List of constraint dictionaries:
                - {"type": "concentration", "nutrient": "CP", "min": 16.0, "max": 18.0}
                - {"type": "daily_total", "attribute": "dmi", "target": 18.0, "tolerance_percent": 10.0}
                - {"type": "daily_total", "attribute": "NEL", "target": 32.0, "tolerance_percent": 5.0}
                - {"type": "daily_total", "attribute": "CP", "target": 2.8, "tolerance_percent": 8.0}
                - {"type": "ratio", "numerator": "Ca", "denominator": "P", "min": 1.2, "max": 2.0}
            selected_feeds: List of feed names to include in optimization
            feed_constraints: Optional inclusion limits {"feed_name": {"min": 0, "max": 50}}
            optimization_goal: "minimize_cost" or other objectives
            
        Daily Total Constraints:
            - Use "daily_total" type for any daily target (DMI, nutrients, etc.)
            - "attribute": can be "dmi" or any nutrient name (e.g., "NEL", "CP", "Ca")
            - "target": the target daily amount
            - "tolerance_percent": optional tolerance (default 10%) - creates flexible range around target
            - DMI constraint should be specified first, as nutrient daily totals depend on it
            
        Returns:
            State update with formulation results including daily amounts when DMI is provided
        """
        try:
            # Validate inputs
            if not isinstance(feed_base_name, str) or not feed_base_name.strip():
                return Command(
                    update={
                        "messages": [
                            ToolMessage("Error: Feedbase name must be a non-empty string", tool_call_id=tool_call_id)
                        ]
                    }
                )
                
            if not isinstance(nutritional_constraints, list):
                return Command(
                    update={
                        "messages": [
                            ToolMessage("Error: nutritional_constraints must be a list", tool_call_id=tool_call_id)
                        ]
                    }
                )
            
            if not isinstance(selected_feeds, list) or not selected_feeds:
                return Command(
                    update={
                        "messages": [
                            ToolMessage("Error: selected_feeds must be a non-empty list", tool_call_id=tool_call_id)
                        ]
                    }
                )
            
            # Validate constraint format
            for i, constraint in enumerate(nutritional_constraints):
                if not isinstance(constraint, dict):
                    return Command(
                        update={
                            "messages": [
                                ToolMessage(f"Error: Constraint {i} must be a dictionary", tool_call_id=tool_call_id)
                            ]
                        }
                    )
                
                constraint_type = constraint.get("type", "")
                if constraint_type not in ["concentration", "daily_total", "ratio"]:
                    return Command(
                        update={
                            "messages": [
                                ToolMessage(f"Error: Invalid constraint type '{constraint_type}' in constraint {i}. Must be 'concentration', 'daily_total', or 'ratio'", tool_call_id=tool_call_id)
                            ]
                        }
                    )
                
                # Validate specific constraint requirements
                if constraint_type == "concentration" and "nutrient" not in constraint:
                    return Command(
                        update={
                            "messages": [
                                ToolMessage(f"Error: Concentration constraint {i} missing 'nutrient' field", tool_call_id=tool_call_id)
                            ]
                        }
                    )
                elif constraint_type == "daily_total":
                    if "attribute" not in constraint:
                        return Command(
                            update={
                                "messages": [
                                    ToolMessage(f"Error: Daily total constraint {i} missing 'attribute' field", tool_call_id=tool_call_id)
                                ]
                            }
                        )
                    if "target" not in constraint:
                        return Command(
                            update={
                                "messages": [
                                    ToolMessage(f"Error: Daily total constraint {i} missing 'target' field", tool_call_id=tool_call_id)
                                ]
                            }
                        )
            
            # Get user_id from config and access store
            user_id = config["configurable"].get("user_id")
            if not user_id:
                return Command(
                    update={
                        "messages": [
                            ToolMessage("Error: User ID not found in configuration", tool_call_id=tool_call_id)
                        ]
                    }
                )
            
            store = get_store()
            namespace = ("feedbases", user_id, feed_base_name)
            
            # Get feedbase from store
            feedbase_entry = await store.aget(namespace, "data")
            if not feedbase_entry:
                return Command(
                    update={
                        "messages": [
                            ToolMessage(f"Error: Feedbase '{feed_base_name}' not found. Please create it first using add_feed tool.", tool_call_id=tool_call_id)
                        ]
                    }
                )
            
            feedbase_data = feedbase_entry.value
            feed_database = feedbase_data.get("feeds", {})
            if not feed_database:
                return Command(
                    update={
                        "messages": [
                            ToolMessage(f"Error: Feedbase '{feed_base_name}' is empty. Please add feeds first using add_feed tool.", tool_call_id=tool_call_id)
                        ]
                    }
                )
            
            # Check if selected feeds exist
            missing_feeds = [f for f in selected_feeds if f not in feed_database]
            if missing_feeds:
                return Command(
                    update={
                        "messages": [
                            ToolMessage(f"Error: The following feeds are not in the database: {', '.join(missing_feeds)}. Available feeds: {', '.join(feed_database.keys())}", tool_call_id=tool_call_id)
                        ]
                    }
                )
            
            # Extract daily intake if provided in constraints
            daily_intake_kg = None
            for constraint in nutritional_constraints:
                if constraint.get("type") == "daily_total" and constraint.get("attribute") == "dmi":
                    daily_intake_kg = constraint.get("target")
                    break
            
            # Run optimization
            optimizer = create_optimizer()
            optimizer.set_feeds(feed_database)
            
            optimization_result = optimizer.optimize(
                nutritional_constraints=nutritional_constraints,
                selected_feeds=selected_feeds,
                feed_constraints=feed_constraints or {},
                optimization_goal=optimization_goal
            )
            
            # If optimization succeeded and daily intake is provided, calculate daily amounts
            if optimization_result.get("status") == "success" and daily_intake_kg is not None:
                # Calculate daily amounts for each feed
                updated_formulation = {}
                for feed_name, feed_data in optimization_result["formulation"].items():
                    percentage_dm = feed_data["percentage_dm"]
                    
                    # Get feed dry matter percentage
                    feed_dm_percent = feed_database[feed_name]["dm_percent"]
                    
                    # Calculate daily amount as-fed
                    # Formula: (feed_percentage_dm / 100) * daily_dm_intake_kg / (feed_dm_percent / 100)
                    kg_per_day = (percentage_dm / 100) * daily_intake_kg / (feed_dm_percent / 100)
                    
                    updated_formulation[feed_name] = {
                        "percentage_dm": percentage_dm,
                        "kg_per_day": round(kg_per_day, 2)
                    }
                
                # Update the formulation result
                optimization_result["formulation"] = updated_formulation
                optimization_result["daily_dm_intake_kg"] = daily_intake_kg
            
            # Only store constraints in state if optimization succeeded
            state_update = {
                "current_formulation": optimization_result,
                "current_feedbase_name": feed_base_name,  # Store feedbase reference for export
                "current_user_id": user_id,  # Store user ID for export
                "messages": [
                    ToolMessage(json.dumps(optimization_result, indent=2), tool_call_id=tool_call_id)
                ]
            }
            
            if optimization_result.get("status") == "success":
                state_update["formulation_constraints"] = nutritional_constraints
                state_update["feed_constraints"] = feed_constraints or {}
            
            return Command(update=state_update)
            
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
    async def check_feeds(
        feed_base_name: str,
        state: Annotated[dict, InjectedState],
        tool_call_id: Annotated[str, InjectedToolCallId],
        config: RunnableConfig
    ) -> Command:
        """
        Check and list all feeds in a specific feedbase.
        
        Args:
            feed_base_name: Name of the feedbase to check
            
        Returns:
            Formatted string with complete feedbase information
        """
        try:
            # Validate feedbase name
            if not isinstance(feed_base_name, str) or not feed_base_name.strip():
                return Command(
                    update={
                        "messages": [
                            ToolMessage("Error: Feedbase name must be a non-empty string", tool_call_id=tool_call_id)
                        ]
                    }
                )
            
            # Get user_id from config and access store
            user_id = config["configurable"].get("user_id")
            if not user_id:
                return Command(
                    update={
                        "messages": [
                            ToolMessage("Error: User ID not found in configuration", tool_call_id=tool_call_id)
                        ]
                    }
                )
            
            store = get_store()
            namespace = ("feedbases", user_id, feed_base_name)
            
            # Get feedbase from store
            feedbase_entry = await store.aget(namespace, "data")
            if not feedbase_entry:
                return Command(
                    update={
                        "messages": [
                            ToolMessage(f"Feedbase '{feed_base_name}' not found.", tool_call_id=tool_call_id)
                        ]
                    }
                )
            
            feedbase_data = feedbase_entry.value
            feed_database = feedbase_data.get("feeds", {})
            feedbase_animal_type = feedbase_data.get("animal_type", "dairy_cow")

            if not feed_database:
                return Command(
                    update={
                        "messages": [
                            ToolMessage(f"Feedbase '{feed_base_name}' is empty.", tool_call_id=tool_call_id)
                        ]
                    }
                )

            # Format feed information for all feeds
            feed_info = []
            feed_info.append(f"Feedbase '{feed_base_name}' (Animal Type: {feedbase_animal_type}, {len(feed_database)} feeds):\n")
            
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
    
    
    @tool
    async def export_formulation(
        description: str,
        state: Annotated[dict, InjectedState],
        tool_call_id: Annotated[str, InjectedToolCallId],
        config: RunnableConfig,
        filename: Optional[str] = None
    ) -> Command:
        """
        Export current formulation to Excel with optimized layout for readability.

        Creates Excel with 2 sheets:
        1. 配方结果 (Formulation Results) - Professionally formatted results
           Layout structure:
           - TOP: Export metadata (date, status, cost)
           - LEFT (Columns A-D): Constraint validation table with color-coded pass/fail
           - RIGHT (Columns E-H): Large merged cell for detailed description with text wrapping
           - BOTTOM: Formulation composition and nutrient analysis tables

        2. 饲料数据库 (Feed Database) - Complete feed ingredient reference

        The description parameter should contain comprehensive information:
        - Animal information and production targets
        - Formulation objectives and rationale
        - Key nutritional highlights
        - Economic analysis
        - Feeding recommendations
        - Special considerations

        The large description cell (minimum 15 rows) supports multi-paragraph text with
        automatic line wrapping for excellent readability.

        Args:
            description: Detailed formulation description and recommendations (supports multi-line text)
            filename: Optional custom filename (default: formulation_export_TIMESTAMP.xlsx)

        Returns:
            Excel file with professional formatting and comprehensive formulation details
        """
        try:
            # Get all required data from state
            current_formulation = state.get("current_formulation", {})
            formulation_constraints = state.get("formulation_constraints", [])
            feed_constraints = state.get("feed_constraints", {})
            
            # Get feedbase references from state
            feedbase_name = state.get("current_feedbase_name", "")
            user_id = state.get("current_user_id", "")
            
            if not current_formulation or current_formulation.get("status") != "success":
                return Command(
                    update={
                        "messages": [
                            ToolMessage("未找到成功的配方。请先运行配方优化。", tool_call_id=tool_call_id)
                        ]
                    }
                )
            
            # Get feed database from store using state references
            feed_database = {}
            if feedbase_name and user_id:
                try:
                    store = get_store()
                    namespace = ("feedbases", user_id, feedbase_name)
                    feedbase_entry = await store.aget(namespace, "data")
                    if feedbase_entry:
                        feedbase_data = feedbase_entry.value
                        feed_database = feedbase_data.get("feeds", {})
                except Exception as e:
                    logger.error(f"Failed to get feedbase data from store: {e}")
            
            if not feed_database:
                return Command(
                    update={
                        "messages": [
                            ToolMessage("未找到饲料数据库。导出可能不包含完整的饲料信息。", tool_call_id=tool_call_id)
                        ]
                    }
                )
            
            # Get session workspace path
            if session_id:
                try:
                    from services.session_manager import session_manager
                    workspace_path = await session_manager.get_session_workspace_path(session_id)
                except Exception as e:
                    logger.error(f"Failed to get session workspace: {e}")
                    workspace_path = Path(".")
            else:
                logger.warning("No session_id provided to export_formulation, using current directory")
                workspace_path = Path(".")
            
            # Generate filename if not provided
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"formulation_export_{timestamp}.xlsx"
            
            # Ensure .xlsx extension
            if not filename.endswith('.xlsx'):
                filename += '.xlsx'
            
            filepath = workspace_path / filename
            
            # Helper function to validate constraints and calculate achieved values
            def validate_constraints():
                constraint_results = []
                nutrient_analysis = current_formulation.get("nutrient_analysis", {})
                
                for constraint in formulation_constraints:
                    constraint_type = constraint.get("type", "")
                    result = {
                        "约束类型": "",
                        "营养成分": "",
                        "约束条件": "",
                        "实际值": "",
                        "单位": "",
                        "满足情况": ""
                    }
                    
                    if constraint_type == "concentration":
                        nutrient = constraint["nutrient"]
                        min_val = constraint.get("min")
                        max_val = constraint.get("max")
                        achieved = nutrient_analysis.get(nutrient, 0.0)
                        
                        result["约束类型"] = "浓度约束"
                        result["营养成分"] = nutrient
                        result["实际值"] = achieved
                        result["单位"] = "% DM"
                        
                        if min_val is not None and max_val is not None:
                            result["约束条件"] = f"{min_val} - {max_val}"
                            satisfied = min_val <= achieved <= max_val
                        elif min_val is not None:
                            result["约束条件"] = f"≥ {min_val}"
                            satisfied = achieved >= min_val
                        elif max_val is not None:
                            result["约束条件"] = f"≤ {max_val}"
                            satisfied = achieved <= max_val
                        else:
                            satisfied = True
                            
                        result["满足情况"] = "✓ 满足" if satisfied else "✗ 不满足"
                    
                    elif constraint_type == "daily_total":
                        attribute = constraint.get("attribute")
                        target = constraint.get("target")
                        tolerance_percent = constraint.get("tolerance_percent", 10.0)
                        
                        if attribute == "dmi":
                            result["约束类型"] = "干物质采食量约束"
                            result["营养成分"] = "DMI"
                            result["单位"] = "kg/day"
                            result["约束条件"] = f"目标: {target} ± {tolerance_percent}%"
                            result["实际值"] = f"{target} (范围内)"
                            result["满足情况"] = "✓ 满足"
                        else:
                            # Nutrient daily total constraint
                            result["约束类型"] = "日摄入约束"
                            result["营养成分"] = attribute
                            result["单位"] = "日摄入量"
                            
                            if daily_intake_kg:
                                nutrient_percent = nutrient_analysis.get(attribute, 0.0)
                                achieved = (nutrient_percent / 100) * daily_intake_kg
                                result["实际值"] = round(achieved, 2)
                                
                                tolerance_factor = tolerance_percent / 100.0
                                target_min = target * (1 - tolerance_factor)
                                target_max = target * (1 + tolerance_factor)
                                result["约束条件"] = f"目标: {target} ± {tolerance_percent}% ({target_min:.2f} - {target_max:.2f})"
                                satisfied = target_min <= achieved <= target_max
                            else:
                                result["实际值"] = "需要日采食量"
                                result["约束条件"] = "无法计算"
                                satisfied = False
                                
                            result["满足情况"] = "✓ 满足" if satisfied else "✗ 不满足"
                    
                    elif constraint_type == "ratio":
                        numerator = constraint["numerator"]
                        denominator = constraint["denominator"]
                        min_ratio = constraint.get("min")
                        max_ratio = constraint.get("max")
                        
                        result["约束类型"] = "比例约束"
                        result["营养成分"] = f"{numerator}:{denominator}"
                        result["单位"] = "比值"
                        
                        num_content = nutrient_analysis.get(numerator, 0.0)
                        denom_content = nutrient_analysis.get(denominator, 0.0)
                        
                        if denom_content > 0:
                            achieved = num_content / denom_content
                            result["实际值"] = round(achieved, 2)
                            
                            conditions = []
                            if min_ratio is not None:
                                conditions.append(f"≥ {min_ratio}")
                            if max_ratio is not None:
                                conditions.append(f"≤ {max_ratio}")
                            result["约束条件"] = " & ".join(conditions)
                            
                            satisfied = True
                            if min_ratio is not None and achieved < min_ratio:
                                satisfied = False
                            if max_ratio is not None and achieved > max_ratio:
                                satisfied = False
                        else:
                            result["实际值"] = "分母为零"
                            result["约束条件"] = "无法计算"
                            satisfied = False
                        
                        result["满足情况"] = "✓ 满足" if satisfied else "✗ 不满足"
                    
                    constraint_results.append(result)
                
                return constraint_results
            
            # Create Excel with 2 sheets
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:

                # Sheet 1: 配方结果 (Formulation Results) - Redesigned layout
                # Left side (A-C): Constraint validation
                # Right side (E-H): Large merged description area
                main_data = []

                # Get constraint results first to determine description area size
                constraint_results = validate_constraints()

                # Header row
                main_data.append(['约束验证', '', '', '', '配方描述与说明', '', '', ''])
                main_data.append(['', '', '', '', '', '', '', ''])

                # Basic information row
                main_data.append([
                    '导出日期:', datetime.now().strftime("%Y-%m-%d %H:%M:%S"), '', '', '', '', '', ''
                ])
                main_data.append([
                    '优化状态:', current_formulation.get('status', 'Unknown'), '', '', '', '', '', ''
                ])
                main_data.append([
                    '总成本:', f"{current_formulation.get('cost_per_kg_dm', 'N/A')} 元/公斤干物质", '', '', '', '', '', ''
                ])
                main_data.append(['', '', '', '', '', '', '', ''])

                # Constraint validation table header
                main_data.append(['约束类型', '营养成分', '约束条件', '满足情况', '', '', '', ''])

                # Description will span from row 7 (index 6) to row (7 + max(constraint rows, 10))
                # Store description row indices for later merging
                description_start_row = 7  # Row number (1-indexed)

                # Add constraint rows (minimum 10 rows to give description space)
                min_description_rows = 15  # Give description plenty of vertical space
                constraint_row_count = max(len(constraint_results), min_description_rows)

                for i in range(constraint_row_count):
                    row = ['', '', '', '', '', '', '', '']

                    # Left side: Constraint validation
                    if i < len(constraint_results):
                        result = constraint_results[i]
                        row[0] = result["约束类型"]
                        row[1] = result["营养成分"]
                        row[2] = result["约束条件"]
                        row[3] = result["满足情况"]

                    # Description goes in column E (index 4) - will be merged later
                    if i == 0:
                        row[4] = description  # Put description in first row only

                    main_data.append(row)

                description_end_row = description_start_row + constraint_row_count - 1

                main_data.append(['', '', '', '', '', '', '', ''])

                # Formulation composition section
                main_data.append(['配方组成', '', '', '', '', '', '', ''])
                main_data.append(['饲料名称', '干物质比例 (%)', '日饲喂量 (kg)', '', '', '', '', ''])

                formulation_feeds = list(current_formulation["formulation"].items())
                for feed_name, feed_data in formulation_feeds:
                    sanitized_name = sanitize_feed_name(feed_name)
                    main_data.append([
                        sanitized_name,
                        feed_data["percentage_dm"],
                        feed_data["kg_per_day"],
                        '', '', '', '', ''
                    ])

                main_data.append(['', '', '', '', '', '', '', ''])

                # Nutrient Analysis Section
                if "nutrient_analysis" in current_formulation:
                    main_data.append(['营养分析', '', '', '', '', '', '', ''])
                    main_data.append(['营养成分', '含量 (% DM)', '', '', '', '', '', ''])

                    for nutrient, value in current_formulation["nutrient_analysis"].items():
                        main_data.append([nutrient, value, '', '', '', '', '', ''])
                
                # Create DataFrame and write to sheet
                main_df = pd.DataFrame(main_data)
                main_df.to_excel(writer, sheet_name='配方结果', index=False, header=False)
                
                # Sheet 2: 饲料数据库 (Feed Database) - Reference data
                feed_data_list = []
                for feed_name, feed_info in feed_database.items():
                    sanitized_name = sanitize_feed_name(feed_name)
                    base_data = {
                        '饲料名称': sanitized_name,
                        '干物质含量 (%)': feed_info.get('dm_percent', ''),
                        '价格 (元/公斤)': feed_info.get('cost_per_kg', '')
                    }
                    
                    # Add all nutrient columns
                    nutrients = feed_info.get('nutrients', {})
                    for nutrient, value in nutrients.items():
                        base_data[nutrient] = value
                    
                    feed_data_list.append(base_data)
                
                feed_df = pd.DataFrame(feed_data_list)
                feed_df.to_excel(writer, sheet_name='饲料数据库', index=False)
                
                # Apply formatting
                workbook = writer.book
                from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
                
                # Format 配方结果 sheet (redesigned layout with description on right)
                if '配方结果' in workbook.sheetnames:
                    ws_main = workbook['配方结果']

                    # Set column widths for better readability
                    ws_main.column_dimensions['A'].width = 18  # 约束类型
                    ws_main.column_dimensions['B'].width = 15  # 营养成分
                    ws_main.column_dimensions['C'].width = 22  # 约束条件
                    ws_main.column_dimensions['D'].width = 12  # 满足情况 / separator
                    ws_main.column_dimensions['E'].width = 80  # Large description area (merged E-H)
                    ws_main.column_dimensions['F'].width = 2   # Hidden (merged into E)
                    ws_main.column_dimensions['G'].width = 2   # Hidden (merged into E)
                    ws_main.column_dimensions['H'].width = 2   # Hidden (merged into E)

                    # Set row heights - make description rows taller
                    for row_num in range(1, ws_main.max_row + 1):
                        # Taller rows for description area
                        if description_start_row <= row_num <= description_end_row:
                            ws_main.row_dimensions[row_num].height = 18
                        else:
                            ws_main.row_dimensions[row_num].height = 20

                    # Define styles
                    title_font = Font(bold=True, size=16, color="FFFFFF")
                    title_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")

                    section_font = Font(bold=True, size=12, color="FFFFFF")
                    section_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")

                    header_font = Font(bold=True, color="000000")
                    header_fill = PatternFill(start_color="D9E2F3", end_color="D9E2F3", fill_type="solid")

                    label_font = Font(bold=True)
                    desc_fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
                    desc_font = Font(size=11)

                    # Merge large description cell (E to H, spanning multiple rows)
                    ws_main.merge_cells(f'E{description_start_row}:H{description_end_row}')

                    # Format the merged description cell
                    desc_cell = ws_main[f'E{description_start_row}']
                    desc_cell.fill = desc_fill
                    desc_cell.font = desc_font
                    desc_cell.alignment = Alignment(
                        wrap_text=True,
                        vertical="top",
                        horizontal="left"
                    )

                    # Apply formatting by scanning actual cell content
                    for row_num in range(1, ws_main.max_row + 1):
                        row_cells = [ws_main.cell(row=row_num, column=col) for col in range(1, 9)]
                        first_cell_value = str(row_cells[0].value or "")
                        fifth_cell_value = str(row_cells[4].value or "")

                        # Title row headers
                        if row_num == 1:
                            if first_cell_value == "约束验证":
                                row_cells[0].font = title_font
                                row_cells[0].fill = title_fill
                                ws_main.merge_cells(f'A{row_num}:D{row_num}')
                            if fifth_cell_value == "配方描述与说明":
                                row_cells[4].font = title_font
                                row_cells[4].fill = title_fill
                                ws_main.merge_cells(f'E{row_num}:H{row_num}')

                        # Section headers
                        elif first_cell_value in ["配方组成", "营养分析"]:
                            row_cells[0].font = section_font
                            row_cells[0].fill = section_fill
                            ws_main.merge_cells(f'A{row_num}:C{row_num}')

                        # Table headers
                        elif first_cell_value == "约束类型":
                            # Constraint validation table header
                            for col in range(4):
                                if row_cells[col].value:
                                    row_cells[col].font = header_font
                                    row_cells[col].fill = header_fill
                                    row_cells[col].alignment = Alignment(horizontal="center")

                        elif first_cell_value == "饲料名称":
                            # Formulation table header
                            for col in range(3):
                                if row_cells[col].value:
                                    row_cells[col].font = header_font
                                    row_cells[col].fill = header_fill
                                    row_cells[col].alignment = Alignment(horizontal="center")

                        elif first_cell_value == "营养成分" and str(row_cells[1].value or "") == "含量 (% DM)":
                            # Nutrient analysis table header
                            for col in range(2):
                                if row_cells[col].value:
                                    row_cells[col].font = header_font
                                    row_cells[col].fill = header_fill
                                    row_cells[col].alignment = Alignment(horizontal="center")

                        # Label cells
                        elif first_cell_value.endswith(":"):
                            row_cells[0].font = label_font
                
                # Format 饲料数据库 sheet (standard table formatting)
                if '饲料数据库' in workbook.sheetnames:
                    ws_feed = workbook['饲料数据库']
                    
                    # Auto-adjust column widths
                    for column in ws_feed.columns:
                        max_length = 0
                        column_letter = column[0].column_letter
                        for cell in column:
                            try:
                                if len(str(cell.value)) > max_length:
                                    max_length = len(str(cell.value))
                            except:
                                pass
                        adjusted_width = min(max_length + 2, 25)
                        ws_feed.column_dimensions[column_letter].width = adjusted_width
                    
                    # Header formatting
                    header_font = Font(bold=True, color="FFFFFF")
                    header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
                    
                    for cell in ws_feed[1]:
                        cell.font = header_font
                        cell.fill = header_fill
                        cell.alignment = Alignment(horizontal="center")
            
            # Format file info for backend parsing
            file_info = {
                "filepath": str(filepath),
                "filename": filename,
                "type": "excel"
            }
            
            return Command(
                update={
                    "messages": [
                        ToolMessage(f"✅ successfully exported {filename}. [FILE_EXPORT]{json.dumps(file_info, ensure_ascii=False)}[/FILE_EXPORT]", tool_call_id=tool_call_id)
                    ]
                }
            )
            
        except Exception as e:
            logger.error(f"Export formulation error: {e}")
            return Command(
                update={
                    "messages": [
                        ToolMessage(f"Error exporting formulation: {str(e)}", tool_call_id=tool_call_id)
                    ]
                }
            )

    return [add_feed, formulate_ration, check_feeds, list_feed_bases, export_formulation]

