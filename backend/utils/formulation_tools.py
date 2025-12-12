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
from utils.language import normalize_locale, get_export_texts
from utils.formulation_exporter import create_export_formulation_tool, sanitize_feed_name
from services.embedding_service import get_embedding_service

logger = logging.getLogger(__name__)


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
        cost_per_kg: float = 0.0,
        nutrients: Optional[Dict[str, float]] = None,
        state: Annotated[dict, InjectedState] = None,
        tool_call_id: Annotated[str, InjectedToolCallId] = None,
        config: RunnableConfig = None
    ) -> Command:
        """
        Add or update feed ingredient in a custom feedbase.

        For dairy cows: Feed must exist in default_dairy_cow feedbase. All NASEM nutrients
        are copied from the source, with optional cost and nutrient overrides.

        For other animals: Same reference-based behavior from respective default feedbase.

        Args:
            feed_base_name: Name of user's custom feedbase (will create if not exists)
            name: Feed name (must exist in default_{animal_type} feedbase)
            cost_per_kg: Cost per kg as-fed (optional, defaults to 0)
            nutrients: Optional nutrient overrides - replaces specific nutrient values
                       e.g., {"Fd_CP": 50.0} to override crude protein

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
            
            if cost_per_kg < 0:
                return Command(
                    update={"messages": [ToolMessage("Error: Cost per kg must be non-negative", tool_call_id=tool_call_id)]}
                )
            
            # Validate nutrient override values if provided
            if nutrients:
                if not isinstance(nutrients, dict):
                    return Command(
                        update={"messages": [ToolMessage("Error: Nutrients must be a dictionary", tool_call_id=tool_call_id)]}
                    )
                for nutrient, value in nutrients.items():
                    if not isinstance(value, (int, float)) or value < 0:
                        return Command(
                            update={"messages": [ToolMessage(f"Error: Nutrient '{nutrient}' must have a non-negative numeric value", tool_call_id=tool_call_id)]}
                        )
            
            # Get user_id from config and access store
            user_id = config["configurable"].get("user_id")
            if not user_id:
                return Command(
                    update={"messages": [ToolMessage("Error: User ID not found in configuration", tool_call_id=tool_call_id)]}
                )
            
            store = get_store()
            
            # Look up the source feed from the default system feedbase
            default_feedbase_name = f"default_{animal_type}"
            system_namespace = ("system_feedbases", default_feedbase_name)
            system_feedbase = await store.aget(system_namespace, "data")
            
            if not system_feedbase:
                return Command(
                    update={"messages": [ToolMessage(f"Error: System feedbase '{default_feedbase_name}' not found.", tool_call_id=tool_call_id)]}
                )
            
            system_feeds = system_feedbase.value.get("feeds", {})
            sanitized_name = sanitize_feed_name(name)
            
            # Check if the feed exists in the default feedbase
            if sanitized_name not in system_feeds:
                # Try to find a close match for better error message
                available_feeds = list(system_feeds.keys())[:10]
                return Command(
                    update={"messages": [ToolMessage(
                        f"Error: Feed '{sanitized_name}' not found in '{default_feedbase_name}'. "
                        f"Use check_feeds to find available feeds. Examples: {', '.join(available_feeds[:5])}...",
                        tool_call_id=tool_call_id
                    )]}
                )
            
            # Copy the full feed data from the source
            import copy
            source_feed = system_feeds[sanitized_name]
            feed_data = copy.deepcopy(source_feed)
            
            # Apply cost override
            feed_data["cost_per_kg"] = cost_per_kg
            
            # Apply nutrient overrides if provided
            if nutrients:
                if "nutrients" not in feed_data:
                    feed_data["nutrients"] = {}
                for nutrient_key, nutrient_value in nutrients.items():
                    feed_data["nutrients"][nutrient_key] = nutrient_value
            
            # Get or create user's custom feedbase
            namespace = ("feedbases", user_id, feed_base_name)
            existing_feedbase = await store.aget(namespace, "data")
            if existing_feedbase:
                feedbase_data = existing_feedbase.value
            else:
                # Create new feedbase with animal_type metadata
                feedbase_data = {
                    "animal_type": animal_type,
                    "feeds": {}
                }
            
            # Determine if this is an add or update
            is_update = sanitized_name in feedbase_data.get("feeds", {})
            
            # Add/update feed in feedbase
            feedbase_data["feeds"][sanitized_name] = feed_data
            
            # Store updated feedbase
            await store.aput(namespace, "data", feedbase_data)
            
            # Build success message
            action = "Updated" if is_update else "Added"
            override_info = ""
            if nutrients:
                override_info = f" with {len(nutrients)} nutrient override(s)"
            
            return Command(
                update={"messages": [ToolMessage(
                    f"{action} feed '{sanitized_name}' in feedbase '{feed_base_name}' "
                    f"(source: {default_feedbase_name}, cost: ${cost_per_kg}/kg{override_info})",
                    tool_call_id=tool_call_id
                )]}
            )
            
        except Exception as e:
            logger.error(f"Add feed error: {e}")
            return Command(
                update={"messages": [ToolMessage(f"Error adding feed: {str(e)}", tool_call_id=tool_call_id)]}
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
                    update={"messages": [ToolMessage("Error: User ID not found in configuration", tool_call_id=tool_call_id)]}
                )

            free_tier = _is_free_tier(config)
            store = get_store()

            if free_tier:
                system_feedbase_name = f"default_{animal_type}"
                system_namespace = ("system_feedbases", system_feedbase_name)
                system_feedbase = await store.aget(system_namespace, "data")

                if not system_feedbase:
                    return Command(
                        update={"messages": [ToolMessage(f"No system feedbase found for animal type '{animal_type}'. Please contact support.", tool_call_id=tool_call_id)]}
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
                    update={"messages": [ToolMessage("\n".join(message_lines), tool_call_id=tool_call_id)]}
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
                    update={"messages": [ToolMessage(f"No feedbases found for animal type '{animal_type}'.", tool_call_id=tool_call_id)]}
                )

            return Command(
                update={"messages": [ToolMessage("\n".join(feedbase_info), tool_call_id=tool_call_id)]}
            )

        except Exception as e:
            logger.error(f"List feedbases error: {e}")
            return Command(
                update={"messages": [ToolMessage(f"Error listing feedbases: {str(e)}", tool_call_id=tool_call_id)]}
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
                    update={"messages": [ToolMessage("Error: Feedbase name must be a non-empty string", tool_call_id=tool_call_id)]}
                )
            
            if _is_free_tier(config) and not feed_base_name.startswith("default_"):
                return _free_tier_feedbase_message("use custom", tool_call_id)
                
            if not isinstance(nutritional_constraints, list):
                return Command(
                    update={"messages": [ToolMessage("Error: nutritional_constraints must be a list", tool_call_id=tool_call_id)]}
                )
            
            if not isinstance(selected_feeds, list) or not selected_feeds:
                return Command(
                    update={"messages": [ToolMessage("Error: selected_feeds must be a non-empty list", tool_call_id=tool_call_id)]}
                )
            
            # Validate constraint format
            for i, constraint in enumerate(nutritional_constraints):
                if not isinstance(constraint, dict):
                    return Command(
                        update={"messages": [ToolMessage(f"Error: Constraint {i} must be a dictionary", tool_call_id=tool_call_id)]}
                    )
                
                constraint_type = constraint.get("type", "")
                if constraint_type not in ["concentration", "daily_total", "ratio"]:
                    return Command(
                        update={"messages": [ToolMessage(f"Error: Invalid constraint type '{constraint_type}' in constraint {i}. Must be 'concentration', 'daily_total', or 'ratio'", tool_call_id=tool_call_id)]}
                    )
                
                # Validate specific constraint requirements
                if constraint_type == "concentration" and "nutrient" not in constraint:
                    return Command(
                        update={"messages": [ToolMessage(f"Error: Concentration constraint {i} missing 'nutrient' field", tool_call_id=tool_call_id)]}
                    )
                elif constraint_type == "daily_total":
                    if "attribute" not in constraint:
                        return Command(
                            update={"messages": [ToolMessage(f"Error: Daily total constraint {i} missing 'attribute' field", tool_call_id=tool_call_id)]}
                        )
                    if "target" not in constraint:
                        return Command(
                            update={"messages": [ToolMessage(f"Error: Daily total constraint {i} missing 'target' field", tool_call_id=tool_call_id)]}
                        )
            
            # Get user_id from config and access store
            user_id = config["configurable"].get("user_id")
            if not user_id:
                return Command(
                    update={"messages": [ToolMessage("Error: User ID not found in configuration", tool_call_id=tool_call_id)]}
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
                    update={"messages": [ToolMessage(f"Error: Feedbase '{feed_base_name}' not found. Please create it first using add_feed tool or use the system 'default' feedbase.", tool_call_id=tool_call_id)]}
                )

            feedbase_data = feedbase_entry.value
            feed_database = feedbase_data.get("feeds", {})
            if not feed_database:
                return Command(
                    update={"messages": [ToolMessage(f"Error: Feedbase '{feed_base_name}' is empty. Please add feeds first using add_feed tool.", tool_call_id=tool_call_id)]}
                )
            
            # Check if selected feeds exist
            missing_feeds = [f for f in selected_feeds if f not in feed_database]
            if missing_feeds:
                return Command(
                    update={"messages": [ToolMessage(f"Error: The following feeds are not in the database: {', '.join(missing_feeds)}. Available feeds: {', '.join(feed_database.keys())}", tool_call_id=tool_call_id)]}
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
                update={"messages": [ToolMessage(f"Error formulating ration: {str(e)}", tool_call_id=tool_call_id)]}
            )
    
    @tool
    async def check_feeds(
        feed_base_name: str,
        state: Annotated[dict, InjectedState],
        tool_call_id: Annotated[str, InjectedToolCallId],
        config: RunnableConfig,
        query: str = ""
    ) -> Command:
        """
        Query feeds in a feedbase using semantic search or special syntax.
        
        Query Syntax Options:
        
        1. Empty query ("") - Returns category summary for large feedbases, or full list for small ones
        
        2. Special queries:
           - "nutrients" → Returns list of all available nutrient column names
        
        3. Free-text query (SEMANTIC SEARCH):
           Any text query uses AI embeddings to find semantically similar feeds.
           Examples: "corn silage", "high protein feed", "玉米青贮"
           
           Supports modifiers:
           - LIMIT n: Max results (default 10, max 20)
           - RETURN full: Include all nutrients
        
        4. List syntax:
           "[feed1, feed2, feed3]" → Returns full details for specific feeds
           
        5. Category filter:
           "WHERE category IN [Energy Source, Plant Protein]" → Filter by category
        
        Examples:
            check_feeds("default_dairy_cow", "")  
            # → Category summary
            
            check_feeds("default_dairy_cow", "corn silage")  
            # → Semantic search for corn silage feeds
            
            check_feeds("default_dairy_cow", "high protein legume LIMIT 5")
            # → Top 5 semantically similar feeds
            
            check_feeds("default_dairy_cow", "[corn_silage_typical, soybean_meal_48]")
            # → Full details for specific feeds
        
        Args:
            feed_base_name: Name of the feedbase to query
            query: Query string (empty for summary, free-text for semantic search, or special syntax)
            
        Returns:
            Query results (names by default, full nutrients with RETURN full or list syntax)
        """
        from services.session_manager import check_token_limit
        
        HUGE_FEEDBASE_THRESHOLD = 50
        MAX_LIMIT = 20
        MAX_TOKENS = 50000  # Safe limit for tool responses
        
        def parse_query(query_str: str) -> dict:
            """Parse SQL-like query into components."""
            result = {
                "pattern": None,
                "categories": [],
                "order_by": None,
                "order_dir": "ASC",
                "limit": MAX_LIMIT,
                "return_full": False  # Default to names only
            }
            
            if not query_str:
                return result
            
            q = query_str.strip()
            
            # Extract RETURN full clause
            return_match = re.search(r'\bRETURN\s+full\b', q, re.IGNORECASE)
            if return_match:
                result["return_full"] = True
                q = q[:return_match.start()] + q[return_match.end():]
            
            # Extract LIMIT clause
            limit_match = re.search(r'\bLIMIT\s+(\d+)\b', q, re.IGNORECASE)
            if limit_match:
                result["limit"] = min(int(limit_match.group(1)), MAX_LIMIT)
                q = q[:limit_match.start()] + q[limit_match.end():]
            
            # Extract ORDER BY clause
            order_match = re.search(r'\bORDER\s+BY\s+(\w+)\s*(ASC|DESC)?\b', q, re.IGNORECASE)
            if order_match:
                result["order_by"] = order_match.group(1)
                result["order_dir"] = (order_match.group(2) or "ASC").upper()
                q = q[:order_match.start()] + q[order_match.end():]
            
            # Extract WHERE category IN [...] clause
            where_match = re.search(r'\bWHERE\s+category\s+IN\s*\[([^\]]+)\]', q, re.IGNORECASE)
            if where_match:
                cats = where_match.group(1)
                result["categories"] = [c.strip() for c in cats.split(",") if c.strip()]
                q = q[:where_match.start()] + q[where_match.end():]
            
            # Remaining text is the pattern
            pattern = q.strip()
            if pattern:
                result["pattern"] = pattern
            
            return result
        
        def format_feed_names(feeds: list) -> str:
            """Format feed names as comma-separated list."""
            return ", ".join(feeds)
        
        def format_feed_full(feed_name: str, feed_data: dict) -> str:
            """Format feed with all nutrients (full mode), skipping 0/null values."""
            lines = [f"**{feed_name}**"]
            lines.append(f"  DM: {feed_data.get('dm_percent', 'N/A')}%")
            lines.append(f"  Cost: ${feed_data.get('cost_per_kg', 0)}/kg")
            
            if feed_data.get('category'):
                lines.append(f"  Category: {feed_data['category']}")
            if feed_data.get('type'):
                lines.append(f"  Type: {feed_data['type']}")
            
            nutrients = feed_data.get('nutrients', {})
            if nutrients:
                lines.append("  Nutrients (DM basis):")
                for nutrient, value in nutrients.items():
                    # Skip 0/null values
                    if value not in (0, 0.0, None, ""):
                        lines.append(f"    {nutrient}: {value}")
            return "\n".join(lines)
        
        try:
            # Validate feedbase name
            if not isinstance(feed_base_name, str) or not feed_base_name.strip():
                return Command(
                    update={"messages": [ToolMessage("Error: Feedbase name must be a non-empty string", tool_call_id=tool_call_id)]}
                )
            
            if _is_free_tier(config) and not feed_base_name.startswith("default_"):
                return _free_tier_feedbase_message("inspect non-system", tool_call_id)
            
            # Get user_id from config and access store
            user_id = config["configurable"].get("user_id")
            if not user_id:
                return Command(
                    update={"messages": [ToolMessage("Error: User ID not found in configuration", tool_call_id=tool_call_id)]}
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
                    update={"messages": [ToolMessage(f"Feedbase '{feed_base_name}' not found.", tool_call_id=tool_call_id)]}
                )

            feedbase_data = feedbase_entry.value
            feed_database = feedbase_data.get("feeds", {})
            feedbase_animal_type = feedbase_data.get("animal_type", "dairy_cow")

            if not feed_database:
                return Command(
                    update={"messages": [ToolMessage(f"Feedbase '{feed_base_name}' is empty.", tool_call_id=tool_call_id)]}
                )
            
            num_feeds = len(feed_database)
            is_huge = num_feeds > HUGE_FEEDBASE_THRESHOLD
            feedbase_type = "[SYSTEM]" if is_system_feedbase else "[USER]"
            header = f"Feedbase '{feed_base_name}' {feedbase_type} ({feedbase_animal_type}, {num_feeds} feeds)"
            
            query = query.strip() if query else ""
            
            # Handle special query: "nutrients"
            if query.lower() == "nutrients":
                # Collect all unique nutrient names from all feeds
                all_nutrients = set()
                for feed_data in feed_database.values():
                    nutrients = feed_data.get("nutrients", {})
                    all_nutrients.update(nutrients.keys())
                
                sorted_nutrients = sorted(all_nutrients)
                result = f"{header}\n\nAvailable nutrient columns ({len(sorted_nutrients)}):\n{', '.join(sorted_nutrients)}"
                return Command(
                    update={"messages": [ToolMessage(result, tool_call_id=tool_call_id)]}
                )
            
            # Handle list syntax: "[feed1, feed2, feed3]"
            list_match = re.match(r'^\s*\[([^\]]+)\]\s*$', query)
            if list_match:
                feed_names = [f.strip() for f in list_match.group(1).split(",") if f.strip()]
                output_lines = [header, ""]
                found_feeds = []
                missing_feeds = []
                
                for name in feed_names:
                    if name in feed_database:
                        found_feeds.append(name)
                    else:
                        missing_feeds.append(name)
                
                if missing_feeds:
                    output_lines.append(f"⚠️ Not found: {', '.join(missing_feeds)}\n")
                
                for name in found_feeds:
                    output_lines.append(format_feed_full(name, feed_database[name]))
                    output_lines.append("")
                
                result = "\n".join(output_lines)
                
                # Token check
                is_within_limit, token_count, error_msg = check_token_limit(result, MAX_TOKENS)
                if not is_within_limit:
                    return Command(
                        update={"messages": [ToolMessage(f"Error: {error_msg}\nTry requesting fewer feeds.", tool_call_id=tool_call_id)]}
                    )
                
                result = f"[FULL] {result}"
                return Command(
                    update={"messages": [ToolMessage(result, tool_call_id=tool_call_id)]}
                )
            
            # Handle empty query - return summary for huge feedbases
            if not query:
                if is_huge:
                    # Return category summary
                    categories = {}
                    for feed_name, feed_data in feed_database.items():
                        cat = feed_data.get("category", "Unknown")
                        categories[cat] = categories.get(cat, 0) + 1
                    
                    output_lines = [header, "", "Categories:"]
                    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
                        output_lines.append(f"  - {cat}: {count} feeds")
                    
                    output_lines.append("")
                    output_lines.append("ℹ️ This is a large feedbase. Use query syntax:")
                    output_lines.append(f'  check_feeds("{feed_base_name}", "nutrients")  # List nutrient columns')
                    output_lines.append(f'  check_feeds("{feed_base_name}", "corn.* LIMIT 10")  # Search by name')
                    output_lines.append(f'  check_feeds("{feed_base_name}", "WHERE category IN [Plant Protein]")')
                    output_lines.append(f'  check_feeds("{feed_base_name}", "[feed1, feed2]")  # Full details for specific feeds')
                    
                    result = "\n".join(output_lines)
                    return Command(
                        update={"messages": [ToolMessage(result, tool_call_id=tool_call_id)]}
                    )
                else:
                    # Small feedbase - return all feed names
                    feed_names = list(feed_database.keys())
                    output_lines = [header, "", format_feed_names(feed_names)]
                    result = "\n".join(output_lines)
                    
                    return Command(
                        update={"messages": [ToolMessage(result, tool_call_id=tool_call_id)]}
                    )
            
            # Parse SQL-like query
            parsed = parse_query(query)
            
            # Use semantic search if there's a pattern and embeddings are available
            use_semantic = parsed["pattern"]
            
            # Try semantic search if available and applicable
            if use_semantic:
                embedding_service = get_embedding_service()
                if embedding_service.has_embeddings():
                    try:
                        # Use semantic search - get more results if we need to re-sort
                        search_limit = parsed["limit"] * 3 if parsed["order_by"] else parsed["limit"]
                        search_results = await embedding_service.search(
                            query=parsed["pattern"],
                            feedbase_name=feed_base_name,
                            limit=min(search_limit, 100)  # Cap at 100 for reranking pool
                        )
                        
                        # Filter by categories
                        filtered_feeds = []
                        for feed_name, similarity in search_results:
                            if feed_name in feed_database:
                                feed_data = feed_database[feed_name]
                                # Apply category filter
                                if parsed["categories"]:
                                    feed_cat = feed_data.get("category", "")
                                    if not any(cat.lower() == feed_cat.lower() for cat in parsed["categories"]):
                                        continue
                                # Store similarity score in feed_data for display
                                feed_data_with_score = dict(feed_data)
                                feed_data_with_score["_similarity"] = round(similarity, 3)
                                filtered_feeds.append((feed_name, feed_data_with_score))
                        
                        # Re-sort by nutrient if ORDER BY specified (reranker)
                        if parsed["order_by"]:
                            def get_sort_key(item):
                                _, feed_data = item
                                nutrients = feed_data.get("nutrients", {})
                                val = nutrients.get(parsed["order_by"], 0)
                                return val if val is not None else 0
                            
                            reverse = parsed["order_dir"] == "DESC"
                            filtered_feeds.sort(key=get_sort_key, reverse=reverse)
                        
                        # Apply limit after reranking
                        filtered_feeds = filtered_feeds[:parsed["limit"]]
                        
                        # Format output with similarity scores
                        order_info = f" → reranked by {parsed['order_by']} {parsed['order_dir']}" if parsed["order_by"] else ""
                        output_lines = [header, f"\n🔍 Semantic search: \"{parsed['pattern']}\"{order_info}", f"Results: {len(filtered_feeds)} feeds\n"]
                        
                        if parsed["return_full"]:
                            for feed_name, feed_data in filtered_feeds:
                                output_lines.append(format_feed_full(feed_name, feed_data))
                                output_lines.append(f"  Similarity: {feed_data.get('_similarity', 'N/A')}")
                                output_lines.append("")
                        else:
                            # Names with similarity scores
                            for feed_name, feed_data in filtered_feeds:
                                output_lines.append(f"  {feed_name} ({feed_data.get('_similarity', 'N/A')})")
                        
                        result = "\n".join(output_lines)
                        
                        # Token check
                        is_within_limit, token_count, error_msg = check_token_limit(result, MAX_TOKENS)
                        if not is_within_limit:
                            return Command(
                                update={"messages": [ToolMessage(
                                    f"Error: {error_msg}\nTry: LIMIT {parsed['limit'] // 2}",
                                    tool_call_id=tool_call_id
                                )]}
                            )
                        
                        return Command(
                            update={"messages": [ToolMessage(result, tool_call_id=tool_call_id)]}
                        )
                        
                    except Exception as e:
                        logger.warning(f"Semantic search failed, falling back to regex: {e}")
                        # Fall through to regex matching
            
            # Fallback: regex/substring matching
            filtered_feeds = []
            for feed_name, feed_data in feed_database.items():
                # Apply pattern filter
                if parsed["pattern"]:
                    try:
                        if not re.search(parsed["pattern"], feed_name, re.IGNORECASE):
                            # Also check nasem_name if available
                            nasem_name = feed_data.get("nasem_name", "")
                            if not re.search(parsed["pattern"], nasem_name, re.IGNORECASE):
                                continue
                    except re.error:
                        # If invalid regex, treat as substring match
                        if parsed["pattern"].lower() not in feed_name.lower():
                            nasem_name = feed_data.get("nasem_name", "").lower()
                            if parsed["pattern"].lower() not in nasem_name:
                                continue
                
                # Apply category filter
                if parsed["categories"]:
                    feed_cat = feed_data.get("category", "")
                    if not any(cat.lower() == feed_cat.lower() for cat in parsed["categories"]):
                        continue
                
                filtered_feeds.append((feed_name, feed_data))
            
            # Sort if requested
            if parsed["order_by"]:
                def get_sort_key(item):
                    _, feed_data = item
                    nutrients = feed_data.get("nutrients", {})
                    val = nutrients.get(parsed["order_by"], 0)
                    return val if val is not None else 0
                
                reverse = parsed["order_dir"] == "DESC"
                filtered_feeds.sort(key=get_sort_key, reverse=reverse)
            
            # Apply limit
            filtered_feeds = filtered_feeds[:parsed["limit"]]
            
            # Format output based on return type
            output_lines = [header, f"\nQuery: {query}", f"Results: {len(filtered_feeds)} feeds\n"]
            
            if parsed["return_full"]:
                # Full nutrient data
                for feed_name, feed_data in filtered_feeds:
                    output_lines.append(format_feed_full(feed_name, feed_data))
                    output_lines.append("")
                result = "\n".join(output_lines)
            else:
                # Names only (default)
                feed_names = [name for name, _ in filtered_feeds]
                output_lines.append(format_feed_names(feed_names))
                result = "\n".join(output_lines)
            
            # Token check for all responses
            is_within_limit, token_count, error_msg = check_token_limit(result, MAX_TOKENS)
            if not is_within_limit:
                return Command(
                    update={"messages": [ToolMessage(
                        f"Error: {error_msg}\n"
                        f"Try: LIMIT {parsed['limit'] // 2}",
                        tool_call_id=tool_call_id
                    )]}
                )
            
            return Command(
                update={"messages": [ToolMessage(result, tool_call_id=tool_call_id)]}
            )
            
        except Exception as e:
            logger.error(f"Check feeds error: {e}")
            return Command(
                update={"messages": [ToolMessage(f"Error retrieving feed information: {str(e)}", tool_call_id=tool_call_id)]}
            )

    # Create export tool from separate module
    export_formulation = create_export_formulation_tool(animal_type)

    return [add_feed, formulate_ration, check_feeds, list_feed_bases, export_formulation]