import asyncio
import json
import logging
import re
from typing import Dict, List, Any, Optional, Annotated
from datetime import datetime
from pathlib import Path
import pandas as pd
from langchain_core.tools import tool, InjectedToolCallId, InjectedToolArg
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


def create_formulation_tools(animal_type: str = "dairy_cow"):
    """Create formulation tools that operate on LangGraph state.

    Args:
        animal_type: Animal type for feedbase filtering (dairy_cow, beef_cow, cat, dog)
    """
    
    def _is_free_tier(config: Optional[RunnableConfig]) -> bool:
        """Determine whether current LangGraph run belongs to a free tier account."""
        try:
            tier = (config or {}).get("configurable", {}).get("account_tier")
            return (tier or "free") == "free"
        except AttributeError:
            return True

    def _free_tier_feedbase_message(action: str, tool_call_id: Optional[str]) -> Command:
        """Standardized response when free accounts attempt custom feedbase actions."""
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        f"Free tier accounts can only {action} system feedbases named default_*. Please upgrade to unlock custom feedbases.",
                        tool_call_id=tool_call_id,
                    )
                ]
            }
        )
    
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

            if _is_free_tier(config):
                return _free_tier_feedbase_message("create or edit", tool_call_id)

            # Block creating feedbases starting with "default"
            if feed_base_name.startswith("default"):
                return Command(
                    update={
                        "messages": [
                            ToolMessage("Error: Feedbase names cannot start with 'default'. This prefix is reserved for system feedbases.", tool_call_id=tool_call_id)
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
        Includes both user-created feedbases and system default feedbases.

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

            free_tier = _is_free_tier(config)
            store = get_store()

            if free_tier:
                system_feedbase_name = f"default_{animal_type}"
                system_namespace = ("system_feedbases", system_feedbase_name)
                system_feedbase = await store.aget(system_namespace, "data")

                if not system_feedbase:
                    return Command(
                        update={
                            "messages": [
                                ToolMessage(
                                    f"No system feedbase found for animal type '{animal_type}'. Please contact support.",
                                    tool_call_id=tool_call_id,
                                )
                            ]
                        }
                    )

                feed_count = len(system_feedbase.value.get("feeds", {}))
                message_lines = [
                    f"Available Feedbases for {animal_type} (1):",
                    "**System Feedbases:**",
                    f"- **{system_feedbase_name}** ({feed_count} feeds) [READ-ONLY]",
                    "",
                    "Upgrade your plan to create and manage custom feedbases."
                ]
                return Command(
                    update={
                        "messages": [
                            ToolMessage("\n".join(message_lines), tool_call_id=tool_call_id)
                        ]
                    }
                )

            # Search for user feedbases
            user_namespace = ("feedbases", user_id)
            user_feedbase_entries = await store.asearch(user_namespace)

            # Search for system default feedbase for this animal type
            system_feedbase_name = f"default_{animal_type}"
            system_namespace = ("system_feedbases", system_feedbase_name)
            system_feedbase = await store.aget(system_namespace, "data")

            # Filter user feedbases by animal_type
            filtered_feedbases = []
            for entry in user_feedbase_entries:
                feedbase_data = entry.value
                feedbase_animal_type = feedbase_data.get("animal_type", "dairy_cow")  # Default to dairy_cow for legacy data

                if feedbase_animal_type == animal_type:
                    filtered_feedbases.append(entry)

            # Build response
            feedbase_info = []
            total_count = len(filtered_feedbases)

            # Add system default feedbase if it exists and has feeds
            if system_feedbase and len(system_feedbase.value.get("feeds", {})) > 0:
                total_count += 1
                feedbase_info.append(f"Available Feedbases for {animal_type} ({total_count}):\n")
                feedbase_info.append("**System Feedbases:**")
                feed_count = len(system_feedbase.value.get("feeds", {}))
                feedbase_info.append(f"- **{system_feedbase_name}** ({feed_count} feeds) [READ-ONLY]")
                feedbase_info.append("")
            else:
                feedbase_info.append(f"Available Feedbases for {animal_type} ({total_count}):\n")

            # Add user feedbases
            if filtered_feedbases:
                if system_feedbase and len(system_feedbase.value.get("feeds", {})) > 0:
                    feedbase_info.append("**User Feedbases:**")
                for entry in filtered_feedbases:
                    # Namespace structure: ("feedbases", user_id, feedbase_name)
                    feedbase_name = entry.namespace[2]  # Get feedbase name from namespace
                    feedbase_data = entry.value
                    feed_count = len(feedbase_data.get("feeds", {}))
                    feedbase_info.append(f"- **{feedbase_name}** ({feed_count} feeds)")

            if total_count == 0:
                return Command(
                    update={
                        "messages": [
                            ToolMessage(f"No feedbases found for animal type '{animal_type}'.", tool_call_id=tool_call_id)
                        ]
                    }
                )

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
            
            if _is_free_tier(config) and not feed_base_name.startswith("default_"):
                return _free_tier_feedbase_message("use custom", tool_call_id)
                
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

            # Try user feedbase first
            namespace = ("feedbases", user_id, feed_base_name)
            feedbase_entry = await store.aget(namespace, "data")

            # If not found, try system feedbase
            if not feedbase_entry and feed_base_name.startswith("default_"):
                system_namespace = ("system_feedbases", feed_base_name)
                feedbase_entry = await store.aget(system_namespace, "data")

            if not feedbase_entry:
                return Command(
                    update={
                        "messages": [
                            ToolMessage(f"Error: Feedbase '{feed_base_name}' not found. Please create it first using add_feed tool or use the system 'default' feedbase.", tool_call_id=tool_call_id)
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
            
            optimization_result = await asyncio.to_thread(
                optimizer.optimize,
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
            
            if _is_free_tier(config) and not feed_base_name.startswith("default_"):
                return _free_tier_feedbase_message("inspect non-system", tool_call_id)
            
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

            # Try user feedbase first
            namespace = ("feedbases", user_id, feed_base_name)
            feedbase_entry = await store.aget(namespace, "data")

            # If not found, try system feedbase
            is_system_feedbase = False
            if not feedbase_entry and feed_base_name.startswith("default_"):
                system_namespace = ("system_feedbases", feed_base_name)
                feedbase_entry = await store.aget(system_namespace, "data")
                is_system_feedbase = True

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
            feedbase_type = "[SYSTEM DEFAULT]" if is_system_feedbase else "[USER]"
            feed_info.append(f"Feedbase '{feed_base_name}' {feedbase_type} (Animal Type: {feedbase_animal_type}, {len(feed_database)} feeds):\n")
            
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
        Export current formulation to Excel with 3-tab layout for better organization.

        Creates Excel with 3 sheets:
        1. 配方结果 (Formulation Results)
           - Top: Ingredient table (Name | Amount kg/day | Key Nutrients)
           - Middle: Final nutrition profile summary
           - Bottom: Nutrition profile chart (bar chart)

        2. 配方说明 (LLM Suggestions)
           - Formatted description text from the LLM
           - Formulation rationale and recommendations

        3. 约束条件 (Constraints Used)
           - Constraint validation table (pass/fail indicators)
           - Feed constraints table (min/max percentages)

        Args:
            description: Detailed formulation description and recommendations (supports multi-line text)
            filename: Optional custom filename (default: formulation_export_TIMESTAMP.xlsx)

        Returns:
            Excel file with 3-tab layout focusing on practical feeding information
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

                    # Try user feedbase first
                    namespace = ("feedbases", user_id, feedbase_name)
                    feedbase_entry = await store.aget(namespace, "data")

                    # If not found, try system feedbase
                    if not feedbase_entry and feedbase_name.startswith("default_"):
                        system_namespace = ("system_feedbases", feedbase_name)
                        feedbase_entry = await store.aget(system_namespace, "data")

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

            # Get session workspace path from config
            try:
                session_id = config["configurable"].get("thread_id")
                if session_id:
                    from services.session_manager import session_manager
                    workspace_path = await session_manager.get_session_workspace_path(session_id)
                else:
                    logger.warning("No session_id in config, using current directory")
                    workspace_path = Path(".")
            except Exception as e:
                logger.error(f"Failed to get session workspace: {e}")
                workspace_path = Path(".")

            # Generate filename if not provided
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"formulation_export_{timestamp}.xlsx"

            # Ensure .xlsx extension
            if not filename.endswith('.xlsx'):
                filename += '.xlsx'

            filepath = workspace_path / filename

            # Capture daily intake information if available
            daily_intake_kg = current_formulation.get("daily_dm_intake_kg")
            nutrient_analysis = current_formulation.get("nutrient_analysis", {})
            formulation_feeds = current_formulation.get("formulation", {})

            # Helper function to validate constraints and calculate achieved values
            def validate_constraints():
                constraint_results = []

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
            
            # Get constraint validation results
            constraint_results = validate_constraints()

            # Create Excel with 3 sheets
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:

                # ==================== TAB 1: 配方结果 (Formulation Results) ====================
                tab1_data = []

                # Header
                tab1_data.append(['配方结果'])
                tab1_data.append(['导出日期:', datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
                tab1_data.append(['优化状态:', current_formulation.get('status', 'Unknown')])
                tab1_data.append(['总成本:', f"{current_formulation.get('cost_per_kg_dm', 'N/A')} 元/公斤干物质"])
                if daily_intake_kg:
                    tab1_data.append(['日干物质采食量:', f"{daily_intake_kg} kg/day"])
                tab1_data.append([])

                # Section 1: Ingredient Table with Nutritional Facts
                tab1_data.append(['饲料配方明细'])
                tab1_data.append([])  # Empty row for spacing

                # Build header dynamically based on available nutrients
                ingredient_header = ['饲料名称', '日饲喂量 (kg/day)', '干物质比例 (%)']
                # Get all unique nutrients from used feeds
                all_nutrients = set()
                for feed_name in formulation_feeds.keys():
                    if feed_name in feed_database:
                        all_nutrients.update(feed_database[feed_name].get('nutrients', {}).keys())

                # Create two-row header
                # Row 1: Column names with merged "原料含量 (% DM)" header
                header_row1 = ['饲料名称', '日饲喂量 (kg/day)', '干物质比例 (%)']
                if len(all_nutrients) > 0:
                    header_row1.append('原料含量 (% DM)')
                    header_row1.extend([''] * (len(all_nutrients) - 1))
                tab1_data.append(header_row1)

                # Row 2: Individual nutrient names
                header_row2 = ['', '', ''] + [nutrient for nutrient in sorted(all_nutrients)]
                tab1_data.append(header_row2)

                # Add each feed with its details
                for feed_name, feed_data in formulation_feeds.items():
                    sanitized_name = sanitize_feed_name(feed_name)
                    row = [
                        sanitized_name,
                        feed_data.get("kg_per_day", "N/A"),
                        feed_data.get("percentage_dm", "N/A")
                    ]

                    # Add nutrient values for this feed
                    if feed_name in feed_database:
                        feed_nutrients = feed_database[feed_name].get('nutrients', {})
                        for nutrient in sorted(all_nutrients):
                            row.append(feed_nutrients.get(nutrient, ""))
                    else:
                        row.extend([""] * len(all_nutrients))

                    tab1_data.append(row)

                tab1_data.append([])

                # Section 2: Final Nutrition Profile
                tab1_data.append(['整体营养成分分析'])
                tab1_data.append(['营养成分', '含量 (% DM)'])

                for nutrient, value in nutrient_analysis.items():
                    tab1_data.append([nutrient, value])

                # Write Tab 1
                tab1_df = pd.DataFrame(tab1_data)
                tab1_df.to_excel(writer, sheet_name='配方结果', index=False, header=False)

                # ==================== TAB 2: 配方说明 (LLM Suggestions) ====================
                tab2_data = []

                tab2_data.append(['配方说明'])
                tab2_data.append([])

                # Add description text
                if isinstance(description, str) and description.strip():
                    # Split by newlines to preserve formatting
                    for line in description.split('\n'):
                        tab2_data.append([line])
                else:
                    tab2_data.append(['暂无配方说明'])

                # Write Tab 2
                tab2_df = pd.DataFrame(tab2_data)
                tab2_df.to_excel(writer, sheet_name='配方说明', index=False, header=False)

                # ==================== TAB 3: 约束条件 (Constraints Used) ====================
                tab3_data = []

                tab3_data.append(['约束条件'])
                tab3_data.append([])

                # Section 1: Nutritional Constraints Validation
                tab3_data.append(['营养约束验证'])
                tab3_data.append(['约束类型', '营养成分', '约束条件', '实际值', '单位', '满足情况'])

                for result in constraint_results:
                    tab3_data.append([
                        result["约束类型"],
                        result["营养成分"],
                        result["约束条件"],
                        result["实际值"],
                        result["单位"],
                        result["满足情况"]
                    ])

                tab3_data.append([])

                # Section 2: Feed Constraints
                tab3_data.append(['饲料用量约束'])
                if feed_constraints:
                    tab3_data.append(['饲料名称', '最小比例 (%)', '最大比例 (%)'])
                    for feed_name, constraints in feed_constraints.items():
                        sanitized_name = sanitize_feed_name(feed_name)
                        min_val = constraints.get('min', '')
                        max_val = constraints.get('max', '')
                        tab3_data.append([sanitized_name, min_val, max_val])
                else:
                    tab3_data.append(['无饲料用量约束'])

                # Write Tab 3
                tab3_df = pd.DataFrame(tab3_data)
                tab3_df.to_excel(writer, sheet_name='约束条件', index=False, header=False)
                
                # Apply formatting
                workbook = writer.book
                from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
                from openpyxl.chart import PieChart, Reference

                # Define common styles
                title_font = Font(bold=True, size=16, color="FFFFFF")
                title_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
                section_font = Font(bold=True, size=12, color="FFFFFF")
                section_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
                header_font = Font(bold=True, color="000000")
                header_fill = PatternFill(start_color="D9E2F3", end_color="D9E2F3", fill_type="solid")
                label_font = Font(bold=True)
                thin_side = Side(style="thin", color="B4C6E7")
                table_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)

                # ==================== FORMAT TAB 1: 配方结果 ====================
                if '配方结果' in workbook.sheetnames:
                    ws_tab1 = workbook['配方结果']

                    # Auto-adjust column widths
                    for column in ws_tab1.columns:
                        max_length = 0
                        column_letter = column[0].column_letter
                        for cell in column:
                            try:
                                if cell.value and len(str(cell.value)) > max_length:
                                    max_length = len(str(cell.value))
                            except:
                                pass
                        adjusted_width = min(max(max_length + 2, 12), 30)
                        ws_tab1.column_dimensions[column_letter].width = adjusted_width

                    # Apply formatting based on content
                    ingredient_header_row = None
                    nutrient_names_row = None

                    for row_num in range(1, ws_tab1.max_row + 1):
                        first_cell = ws_tab1.cell(row=row_num, column=1)
                        first_value = str(first_cell.value or "")
                        fourth_cell_value = str(ws_tab1.cell(row=row_num, column=4).value or "")

                        # Title row
                        if first_value == "配方结果":
                            first_cell.font = title_font
                            first_cell.fill = title_fill
                            ws_tab1.merge_cells(f'A{row_num}:C{row_num}')

                        # Section headers
                        elif first_value in ["饲料配方明细", "整体营养成分分析"]:
                            first_cell.font = section_font
                            first_cell.fill = section_fill
                            ws_tab1.merge_cells(f'A{row_num}:C{row_num}')

                        # Two-row ingredient table header
                        elif first_value == "饲料名称":
                            ingredient_header_row = row_num
                            # Format first row of header (with "原料含量 (% DM)")
                            for col in range(1, 4):  # First 3 columns
                                cell = ws_tab1.cell(row=row_num, column=col)
                                cell.font = header_font
                                cell.fill = header_fill
                                cell.alignment = Alignment(horizontal="center", wrap_text=True, vertical="center")

                            # Check next row for nutrient names
                            next_row_first = str(ws_tab1.cell(row=row_num + 1, column=1).value or "")
                            if next_row_first == "":  # Next row is nutrient names
                                nutrient_names_row = row_num + 1
                                # Merge "原料含量 (% DM)" across all nutrient columns
                                if ws_tab1.max_column > 3:
                                    ws_tab1.merge_cells(f'D{row_num}:{chr(64 + ws_tab1.max_column)}{row_num}')
                                    merged_cell = ws_tab1.cell(row=row_num, column=4)
                                    merged_cell.font = header_font
                                    merged_cell.fill = header_fill
                                    merged_cell.alignment = Alignment(horizontal="center", wrap_text=True, vertical="center")

                                # Format second row of header (nutrient names)
                                for col in range(4, ws_tab1.max_column + 1):
                                    cell = ws_tab1.cell(row=nutrient_names_row, column=col)
                                    if cell.value:
                                        cell.font = header_font
                                        cell.fill = header_fill
                                        cell.alignment = Alignment(horizontal="center", wrap_text=True, vertical="center")

                        # Regular nutrient analysis table header
                        elif first_value == "营养成分":
                            for col in range(1, ws_tab1.max_column + 1):
                                cell = ws_tab1.cell(row=row_num, column=col)
                                if cell.value:
                                    cell.font = header_font
                                    cell.fill = header_fill
                                    cell.alignment = Alignment(horizontal="center", wrap_text=True)

                        # Label rows (ending with :)
                        elif first_value.endswith(":"):
                            first_cell.font = label_font

                    # Add pie chart for nutrition profile (if nutrients exist)
                    if len(nutrient_analysis) > 0:
                        chart = PieChart()
                        chart.title = "营养成分组成图"

                        # Find the nutrition analysis section
                        nutrition_start_row = None
                        for row_num in range(1, ws_tab1.max_row + 1):
                            if str(ws_tab1.cell(row=row_num, column=1).value) == "整体营养成分分析":
                                nutrition_start_row = row_num + 2  # Skip header row
                                break

                        if nutrition_start_row:
                            data = Reference(ws_tab1, min_col=2, min_row=nutrition_start_row,
                                           max_row=nutrition_start_row + len(nutrient_analysis) - 1)
                            cats = Reference(ws_tab1, min_col=1, min_row=nutrition_start_row,
                                           max_row=nutrition_start_row + len(nutrient_analysis) - 1)
                            chart.add_data(data, titles_from_data=False)
                            chart.set_categories(cats)
                            chart.height = 12
                            chart.width = 15

                            # Place chart below the nutrition table
                            chart_position = f'D{nutrition_start_row}'
                            ws_tab1.add_chart(chart, chart_position)

                # ==================== FORMAT TAB 2: 配方说明 ====================
                if '配方说明' in workbook.sheetnames:
                    ws_tab2 = workbook['配方说明']

                    # Set column A to wide for description text
                    ws_tab2.column_dimensions['A'].width = 100

                    # Title formatting
                    title_cell = ws_tab2['A1']
                    title_cell.font = title_font
                    title_cell.fill = title_fill

                    # Wrap text for all cells
                    for row in ws_tab2.iter_rows(min_row=3):
                        for cell in row:
                            if cell.value:
                                cell.alignment = Alignment(wrap_text=True, vertical="top")

                # ==================== FORMAT TAB 3: 约束条件 ====================
                if '约束条件' in workbook.sheetnames:
                    ws_tab3 = workbook['约束条件']

                    # Auto-adjust column widths
                    for column in ws_tab3.columns:
                        max_length = 0
                        column_letter = column[0].column_letter
                        for cell in column:
                            try:
                                if cell.value and len(str(cell.value)) > max_length:
                                    max_length = len(str(cell.value))
                            except:
                                pass
                        adjusted_width = min(max(max_length + 2, 12), 35)
                        ws_tab3.column_dimensions[column_letter].width = adjusted_width

                    # Apply formatting based on content
                    for row_num in range(1, ws_tab3.max_row + 1):
                        first_cell = ws_tab3.cell(row=row_num, column=1)
                        first_value = str(first_cell.value or "")

                        # Title row
                        if first_value == "约束条件":
                            first_cell.font = title_font
                            first_cell.fill = title_fill
                            ws_tab3.merge_cells(f'A{row_num}:C{row_num}')

                        # Section headers
                        elif first_value in ["营养约束验证", "饲料用量约束"]:
                            first_cell.font = section_font
                            first_cell.fill = section_fill
                            ws_tab3.merge_cells(f'A{row_num}:C{row_num}')

                        # Table headers
                        elif first_value in ["约束类型", "饲料名称"]:
                            for col in range(1, ws_tab3.max_column + 1):
                                cell = ws_tab3.cell(row=row_num, column=col)
                                if cell.value:
                                    cell.font = header_font
                                    cell.fill = header_fill
                                    cell.alignment = Alignment(horizontal="center", wrap_text=True)

                        # Add green/red fill for pass/fail in 满足情况 column
                        if row_num > 1:
                            for col in range(1, ws_tab3.max_column + 1):
                                cell = ws_tab3.cell(row=row_num, column=col)
                                if cell.value:
                                    if "✓ 满足" in str(cell.value):
                                        cell.fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
                                        cell.font = Font(color="006100")
                                    elif "✗ 不满足" in str(cell.value):
                                        cell.fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
                                        cell.font = Font(color="9C0006")
            
            # Format file info for backend parsing
            file_info = {
                "filepath": str(filepath),
                "filename": filename,
                "type": "excel",
                "description": description
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
