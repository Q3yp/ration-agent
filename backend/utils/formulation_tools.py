import json
import logging
from typing import Dict, List, Any, Optional, Annotated
from datetime import datetime
from pathlib import Path
import pandas as pd
from langchain_core.tools import tool, InjectedToolCallId
from langchain_core.messages import ToolMessage
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from formulation.optimizer import create_optimizer

logger = logging.getLogger(__name__)


def create_formulation_tools(session_id: str = None):
    """Create formulation tools that operate on LangGraph state.
    
    Args:
        session_id: Session ID for workspace path resolution (required for export_formulation)
    """
    
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
                return Command(
                    update={
                        "messages": [
                            ToolMessage("Error: Feed name must be a non-empty string", tool_call_id=tool_call_id)
                        ]
                    }
                )
            
            if not 0 < dry_matter_percent <= 100:
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
        Formulate optimal ration using flexible constraint system with tolerance support.
        Automatically calculates daily feed amounts when DMI is specified in constraints.
        
        Args:
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
            
            # Get feed database from state
            feed_database = state.get("feed_database", {})
            if not feed_database:
                return Command(
                    update={
                        "messages": [
                            ToolMessage("Error: No feed database found. Please add feeds first using add_feed tool.", tool_call_id=tool_call_id)
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
    
    
    @tool
    async def export_formulation(
        description: str,
        state: Annotated[dict, InjectedState],
        tool_call_id: Annotated[str, InjectedToolCallId],
        filename: Optional[str] = None
    ) -> Command:
        """
        Export current formulation to Excel with comprehensive 4-section structure.
        
        Creates Excel with sections:
        1. 饲料基础数据 (Feed Database) - 饲料营养成分和成本
        2. 优化约束 (Optimization Constraints) - 设定的营养约束条件  
        3. 优化结果 (Optimization Results) - 配方组成和约束验证
        4. 配方描述 (Description) - 用户提供的配方说明
        
        The tool automatically handles constraint validation with proper units:
        - 浓度约束: % 干物质基础
        - 日摄入约束: 绝对摄入量 (需要日采食量)
        - 比例约束: 无量纲比值
        
        Args:
            description: 配方描述，将显示在Excel第4部分
            filename: 可选文件名 (自动生成时间戳文件名)
            
        Returns:
            包含4个结构化部分的Excel文件
        """
        try:
            # Get all required data from state
            current_formulation = state.get("current_formulation", {})
            feed_database = state.get("feed_database", {})
            formulation_constraints = state.get("formulation_constraints", [])
            feed_constraints = state.get("feed_constraints", {})
            
            if not current_formulation or current_formulation.get("status") != "success":
                return Command(
                    update={
                        "messages": [
                            ToolMessage("未找到成功的配方。请先运行配方优化。", tool_call_id=tool_call_id)
                        ]
                    }
                )
            
            if not feed_database:
                return Command(
                    update={
                        "messages": [
                            ToolMessage("未找到饲料数据库。", tool_call_id=tool_call_id)
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
                
                # Sheet 1: 饲料数据库 (Feed Database)
                feed_data_list = []
                for feed_name, feed_info in feed_database.items():
                    base_data = {
                        '饲料名称': feed_name,
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
                
                # Sheet 2: 配方报告 (Formulation Report) - Combined sections
                report_data = []
                current_row = 0
                
                # Section 1: Description Header
                report_data.append(['配方报告', '', '', '', '', ''])
                report_data.append(['', '', '', '', '', ''])
                report_data.append(['配方描述:', description, '', '', '', ''])
                report_data.append(['导出日期:', datetime.now().strftime("%Y-%m-%d %H:%M:%S"), '', '', '', ''])
                report_data.append(['优化状态:', current_formulation.get('status', 'Unknown'), '', '', '', ''])
                report_data.append(['总成本:', f"{current_formulation.get('cost_per_kg_dm', 'N/A')} 元/公斤干物质", '', '', '', ''])
                report_data.append(['', '', '', '', '', ''])
                
                # Section 2: Optimization Constraints
                report_data.append(['优化约束条件', '', '', '', '', ''])
                report_data.append(['约束类型', '营养成分', '约束条件', '实际值', '单位', '满足情况'])
                
                constraint_results = validate_constraints()
                for result in constraint_results:
                    report_data.append([
                        result["约束类型"],
                        result["营养成分"], 
                        result["约束条件"],
                        result["实际值"],
                        result["单位"],
                        result["满足情况"]
                    ])
                
                report_data.append(['', '', '', '', '', ''])
                
                # Section 3: Formulation Results
                report_data.append(['配方组成', '', '', '', '', ''])
                report_data.append(['饲料名称', '干物质比例 (%)', '日饲喂量 (kg)', '', '', ''])
                
                for feed_name, feed_data in current_formulation["formulation"].items():
                    report_data.append([
                        feed_name,
                        feed_data["percentage_dm"],
                        feed_data["kg_per_day"],
                        '', '', ''
                    ])
                
                report_data.append(['', '', '', '', '', ''])
                
                # Section 4: Nutrient Analysis
                if "nutrient_analysis" in current_formulation:
                    report_data.append(['营养分析', '', '', '', '', ''])
                    report_data.append(['营养成分', '含量 (% DM)', '', '', '', ''])
                    
                    for nutrient, value in current_formulation["nutrient_analysis"].items():
                        report_data.append([nutrient, value, '', '', '', ''])
                
                # Create DataFrame and write to sheet
                report_df = pd.DataFrame(report_data)
                report_df.to_excel(writer, sheet_name='配方报告', index=False, header=False)
                
                # Apply formatting
                workbook = writer.book
                from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
                
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
                
                # Format 配方报告 sheet (custom report formatting)
                if '配方报告' in workbook.sheetnames:
                    ws_report = workbook['配方报告']
                    
                    # Set column widths
                    ws_report.column_dimensions['A'].width = 20
                    ws_report.column_dimensions['B'].width = 15
                    ws_report.column_dimensions['C'].width = 15
                    ws_report.column_dimensions['D'].width = 12
                    ws_report.column_dimensions['E'].width = 12
                    ws_report.column_dimensions['F'].width = 12
                    
                    # Set row heights for better readability
                    for row_num in range(1, ws_report.max_row + 1):
                        ws_report.row_dimensions[row_num].height = 20  # Increased from default ~15 to 20
                    
                    # Define styles
                    title_font = Font(bold=True, size=16, color="FFFFFF")
                    title_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
                    
                    section_font = Font(bold=True, size=12, color="FFFFFF")
                    section_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
                    
                    header_font = Font(bold=True, color="000000")
                    header_fill = PatternFill(start_color="D9E2F3", end_color="D9E2F3", fill_type="solid")
                    
                    label_font = Font(bold=True)
                    
                    # Apply formatting by scanning actual cell content instead of hardcoded positions
                    for row_num in range(1, ws_report.max_row + 1):
                        row_cells = [ws_report.cell(row=row_num, column=col) for col in range(1, 7)]
                        first_cell_value = str(row_cells[0].value or "")
                        
                        # Title row - first row with content
                        if row_num == 1 and first_cell_value == "配方报告":
                            row_cells[0].font = title_font
                            row_cells[0].fill = title_fill
                            ws_report.merge_cells(f'A{row_num}:F{row_num}')
                        
                        # Section headers
                        elif first_cell_value in ["优化约束条件", "配方组成", "营养分析"]:
                            row_cells[0].font = section_font
                            row_cells[0].fill = section_fill
                            ws_report.merge_cells(f'A{row_num}:F{row_num}')
                        
                        # Table headers - detect by content pattern
                        elif first_cell_value == "约束类型" and str(row_cells[1].value or "") == "营养成分":
                            for col in range(6):  # Constraints table has 6 columns
                                if row_cells[col].value:
                                    row_cells[col].font = header_font
                                    row_cells[col].fill = header_fill
                                    row_cells[col].alignment = Alignment(horizontal="center")
                        
                        elif first_cell_value == "饲料名称" and str(row_cells[1].value or "") == "干物质比例 (%)":
                            for col in range(3):  # Formulation table has 3 main columns
                                if row_cells[col].value:
                                    row_cells[col].font = header_font
                                    row_cells[col].fill = header_fill
                                    row_cells[col].alignment = Alignment(horizontal="center")
                        
                        elif first_cell_value == "营养成分" and str(row_cells[1].value or "") == "含量 (% DM)":
                            for col in range(2):  # Nutrient table has 2 columns
                                if row_cells[col].value:
                                    row_cells[col].font = header_font
                                    row_cells[col].fill = header_fill
                                    row_cells[col].alignment = Alignment(horizontal="center")
                        
                        # Label cells (description section)
                        elif first_cell_value.endswith(":") and row_num > 2:
                            row_cells[0].font = label_font
            
            # Format file info for backend parsing
            file_info = {
                "filepath": str(filepath),
                "filename": filename,
                "type": "excel"
            }
            
            return Command(
                update={
                    "messages": [
                        ToolMessage(f"✅ successfully exported {filename}. [FILE_EXPORT]{json.dumps(file_info)}[/FILE_EXPORT]", tool_call_id=tool_call_id)
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

    return [add_feed, formulate_ration, check_feeds, export_formulation]

