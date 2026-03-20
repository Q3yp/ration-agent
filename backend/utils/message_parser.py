"""
Simplified unified message parser.
Handles both streaming events and stored messages with identical logic.
Produces 6 message types: user, agent, tool_call, tool_result, role_transition, artifact
"""
import logging
import re
import json
from typing import List, Dict, Any, Optional, Tuple
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, ToolMessage, SystemMessage
from models import (
    ParsedMessage,
    create_user_message,
    create_user_input_message,
    create_agent_message,
    create_thinking_message,
    create_tool_call_message,
    create_tool_result_message,
    create_role_transition_message,
    create_artifact_message,
    create_file_export_message,
    create_analysis_start_message,
    create_analysis_update_message,
    create_analysis_complete_message,
    create_formulation_start_message,
    create_formulation_update_message,
    create_formulation_complete_message,
    create_calculation_message
)
from utils.language import normalize_locale, t

logger = logging.getLogger(__name__)

class UnifiedMessageParser:
    """
    Single parser for both streaming and history contexts.
    Smart tool handling: combines delegation tools into role transitions,
    detects artifacts, handles normal tool calls/results separately.
    """
    
    def __init__(self, session_id: str, preferred_language: Optional[str] = None):
        self.session_id = session_id
        self.delegation_tools = {
            # LangGraph Swarm tools with custom prefix
            "transfer_to_researcher", "transfer_to_coder", "transfer_to_nutritionist",
        }
        self.pending_delegations = {}  # tool_id -> (tool_name, tool_args, timestamp)
        self.pending_calculations = {}  # tool_id -> (expression, timestamp)
        self.pending_ask_user = {}  # tool_id -> {"description": str, "questions": list}
        self.agent_message_counter = 0
        self.current_agent_message_id = None

        # Tool analysis tracking
        self.excel_tools = {"excel_metadata", "excel_query", "read_excel"}
        self.file_tools = {"write_file", "list_directory", "read_file"}
        self.bash_tools = {"bash_command"}
        self.formulation_tools = {"add_feed", "formulate_ration", "check_feeds", "export_formulation", "list_feed_bases", "predict_dairy_requirements", "evaluate_diet_with_nasem", "set_animal_params"}
        self.active_analysis = None  # {"message_id": str, "operations": [], "start_time": float}
        self.active_formulation = None  # {"message_id": str, "operations": [], "start_time": float, "results": {}}
        self.analysis_operation_counter = 0

        # Token usage tracking
        self.accumulated_token_usage = None  # Will store the latest usage_metadata from chunks
        self.preferred_language = normalize_locale(preferred_language) if preferred_language else "zh-CN"

    def set_preferred_language(self, preferred_language: Optional[str]) -> None:
        """Update the language used for generated copy."""
        if preferred_language:
            self.preferred_language = normalize_locale(preferred_language)
    
    def reset_state(self):
        """Reset parser state - call this before parsing history to avoid state carryover"""
        self.pending_delegations = {}
        self.pending_calculations = {}
        self.agent_message_counter = 0
        self.current_agent_message_id = None
        self.active_analysis = None
        self.active_formulation = None
        self.analysis_operation_counter = 0
        self.accumulated_token_usage = None

    def get_and_reset_token_usage(self):
        """Get accumulated token usage and reset it. Returns dict with input_tokens, output_tokens."""
        if not self.accumulated_token_usage:
            return None

        usage = self.accumulated_token_usage
        self.accumulated_token_usage = None  # Reset for next message

        # Extract token counts from usage_metadata
        return {
            "input_tokens": getattr(usage, 'input_tokens', 0),
            "output_tokens": getattr(usage, 'output_tokens', 0),
            "total_tokens": getattr(usage, 'total_tokens', 0)
        }
    
    
    def _extract_file_export_data(self, content: str) -> Optional[Dict[str, str]]:
        """Extract file export data from tool result content"""
        # Simple string extraction instead of regex
        start_tag = '[FILE_EXPORT]'
        end_tag = '[/FILE_EXPORT]'

        start_idx = content.find(start_tag)
        if start_idx == -1:
            return None

        end_idx = content.find(end_tag)
        if end_idx == -1:
            return None

        # Extract JSON content between tags
        json_start = start_idx + len(start_tag)
        file_json = content[json_start:end_idx].strip()

        if not file_json:
            return None

        try:
            file_data = json.loads(file_json)

            if file_data.get('filepath') and file_data.get('filename'):
                return {
                    'filepath': file_data['filepath'],
                    'filename': file_data['filename'],
                    'file_type': file_data.get('type', 'unknown'),
                    'description': file_data.get('description')
                }

        except (json.JSONDecodeError, AttributeError):
            pass

        return None

    def _extract_calculation_result(self, content: str) -> Optional[str]:
        """Extract calculation result from calculator tool output"""
        # Handle multi-line output with steps (new format)
        if "\nResult: " in content:
            # Extract just the final result line for display
            lines = content.split('\n')
            for line in reversed(lines):
                if line.startswith("Result: "):
                    return line[8:].strip()

        # Handle simple single-line format (legacy)
        if content.startswith("Result: "):
            return content[8:].strip()

        return None

    def _extract_all_results(self, content: str) -> List[str]:
        """Extract all results (variables + intermediate + final) from calculator tool output"""
        all_results = []
        lines = content.split('\n')

        # Extract from "Calculation Steps:" section (variable assignments with results)
        in_steps_section = False
        for line in lines:
            if line.strip() == "Calculation Steps:":
                in_steps_section = True
                continue
            elif line.strip() in ["", "Variables:", "Intermediate Results:", "Result:"] or line.startswith("Result: "):
                in_steps_section = False

            if in_steps_section and "=" in line:
                # Format: "  var_name = value"
                parts = line.split("=", 1)
                if len(parts) == 2:
                    all_results.append(parts[1].strip())

        # Extract from "Intermediate Results:" section
        in_intermediate_section = False
        for line in lines:
            if line.strip() == "Intermediate Results:":
                in_intermediate_section = True
                continue
            elif line.strip() == "":
                # Empty line ends the intermediate section
                in_intermediate_section = False
                continue
            elif line.startswith("Result: "):
                # Don't process "Result:" line as intermediate result
                in_intermediate_section = False
                break

            if in_intermediate_section and line.strip().startswith("["):
                # Format: "  [1] 150"
                parts = line.split("] ", 1)
                if len(parts) == 2:
                    all_results.append(parts[1].strip())

        # Extract final result
        for line in reversed(lines):
            if line.startswith("Result: "):
                all_results.append(line[8:].strip())
                break

        return all_results
    
    
    def _get_delegation_role(self, tool_name: str) -> Optional[str]:
        """Map delegation tool names to roles"""
        mapping = {
            "transfer_to_researcher": "researcher",
            "transfer_to_coder": "coder", 
            "transfer_to_nutritionist": "nutritionist",
        }
        return mapping.get(tool_name)
    
    def _is_analysis_tool(self, tool_name: str) -> str:
        """Check if tool is part of analysis and return tool type"""
        if tool_name in self.excel_tools:
            return "excel"
        elif tool_name in self.file_tools:
            return "file"
        elif tool_name in self.bash_tools:
            return "bash"
        return ""
    
    def _is_formulation_tool(self, tool_name: str) -> bool:
        """Check if tool is part of formulation"""
        return tool_name in self.formulation_tools
    
    def _should_start_analysis(self, tool_name: str) -> bool:
        """Check if we should start a new analysis block"""
        return self._is_analysis_tool(tool_name) and self.active_analysis is None
    
    def _should_end_analysis(self, tool_name: str) -> bool:
        """Check if we should end the current analysis block"""
        if self.active_analysis is None:
            return False
        
        # End only if it's NOT an analysis tool (allows all analysis tools to contribute to same block)
        return not self._is_analysis_tool(tool_name)

    def _get_analysis_label(self) -> str:
        """Localized label for analysis sections."""
        return t("tool.data_analysis", self.preferred_language)

    def _get_formulation_label(self) -> str:
        """Localized label for formulation sections."""
        return t("tool.formulation", self.preferred_language)
    
    def _get_operation_description(self, tool_name: str, tool_args: Dict[str, Any]) -> str:
        """Get human-readable description for tool operation with detailed context"""
        locale = self.preferred_language

        def zh_cn(text: str) -> str:
            return text

        def en_us(text: str) -> str:
            return text

        # Excel tools
        if tool_name == "excel_metadata":
            filepaths = tool_args.get("filepaths", [])
            if len(filepaths) == 1:
                filename = filepaths[0].split('/')[-1]
                return (
                    f"分析 {filename} 文件结构"
                    if locale != "en-US"
                    else f"Inspect structure of {filename}"
                )
            count = len(filepaths)
            return f"分析 {count} 个文件结构" if locale != "en-US" else f"Inspect structure of {count} files"
                
        elif tool_name == "excel_query":
            filepath = tool_args.get("filepath", "文件")
            sheet = tool_args.get("sheet", "工作表")
            query_string = tool_args.get("query_string", "")
            filename = filepath.split('/')[-1]
            
            # Extract meaningful info from query if possible
            query_preview = ""
            if "head(" in query_string:
                query_preview = " (预览数据)" if locale != "en-US" else " (preview rows)"
            elif "describe(" in query_string:
                query_preview = " (统计信息)" if locale != "en-US" else " (summary stats)"
            elif "groupby" in query_string:
                query_preview = " (数据分组)" if locale != "en-US" else " (grouping data)"
            elif "filter" in query_string or "[" in query_string:
                query_preview = " (数据筛选)" if locale != "en-US" else " (filtering data)"
            elif "count" in query_string or "len(" in query_string:
                query_preview = " (记录计数)" if locale != "en-US" else " (counting records)"
            
            if locale == "en-US":
                return f"Query {filename}:{sheet}{query_preview}"
            return f"查询 {filename}:{sheet}{query_preview}"
            
        elif tool_name == "read_excel":
            filepath = tool_args.get("filepath", "文件")
            coordinates = tool_args.get("coordinates", "单元格")
            filename = filepath.split('/')[-1]
            
            # Make coordinates more readable
            coord_desc = coordinates
            if ":" in coordinates:
                coord_desc = f"范围 {coordinates}" if locale != "en-US" else f"range {coordinates}"
            elif coordinates.isdigit():
                coord_desc = f"第 {coordinates} 行" if locale != "en-US" else f"row {coordinates}"
            
            if locale == "en-US":
                return f"Read {coord_desc} from {filename}"
            return f"读取 {filename} 中的{coord_desc}"
            
        # File tools
        elif tool_name == "write_file":
            file_path = tool_args.get("file_path", "文件")
            filename = file_path.split('/')[-1] if "/" in file_path else file_path
            return (
                f"写入文件 {filename}"
                if locale != "en-US"
                else f"Write file {filename}"
            )
            
        elif tool_name == "list_directory":
            dir_path = tool_args.get("dir_path", "目录")
            if dir_path == "." or dir_path == "":
                return "列出当前目录内容" if locale != "en-US" else "List current directory"
            else:
                dirname = dir_path.split('/')[-1] if "/" in dir_path else dir_path
                return (
                    f"列出目录 {dirname} 内容"
                    if locale != "en-US"
                    else f"List contents of {dirname}"
                )
                
        elif tool_name == "read_file":
            file_path = tool_args.get("file_path", "文件")
            filename = file_path.split('/')[-1] if "/" in file_path else file_path
            return (
                f"读取文件 {filename}"
                if locale != "en-US"
                else f"Read file {filename}"
            )
            
        # Bash tools
        elif tool_name == "bash_command":
            command = tool_args.get("command", "命令")
            # Extract first part of command for description
            cmd_parts = command.strip().split()
            if cmd_parts:
                main_cmd = cmd_parts[0]
                if main_cmd in ["ls", "ll"]:
                    return "列出文件" if locale != "en-US" else "List files"
                elif main_cmd == "cd":
                    return "切换目录" if locale != "en-US" else "Change directory"
                elif main_cmd in ["mkdir"]:
                    return "创建目录" if locale != "en-US" else "Create directory"
                elif main_cmd in ["rm", "rmdir"]:
                    return "删除文件" if locale != "en-US" else "Remove files"
                elif main_cmd in ["cp", "mv"]:
                    return "移动/复制文件" if locale != "en-US" else "Move or copy files"
                elif main_cmd in ["grep", "find"]:
                    return "搜索文件内容" if locale != "en-US" else "Search file contents"
                elif main_cmd in ["cat", "head", "tail"]:
                    return "查看文件内容" if locale != "en-US" else "View file contents"
                else:
                    return (
                        f"执行 {main_cmd} 命令"
                        if locale != "en-US"
                        else f"Run command {main_cmd}"
                    )
            return "执行命令" if locale != "en-US" else "Run shell command"
        
        else:
            return f"执行 {tool_name}" if locale != "en-US" else f"Execute {tool_name}"
    
    def _get_formulation_operation_description(self, tool_name: str, tool_args: Dict[str, Any]) -> tuple[str, dict]:
        """Get description and structured data for formulation operation"""
        locale = self.preferred_language
        if tool_name == "add_feed":
            name = tool_args.get("name", "饲料")
            feed_base_name = tool_args.get("feed_base_name", "")
            cost = tool_args.get("cost_per_kg", 0)
            nutrients = tool_args.get("nutrients", {})

            operation_data = {
                "feed_name": name,
                "feed_base_name": feed_base_name,
                "cost_per_kg": f"{cost:.2f}",
                "nutrients": nutrients
            }
            # Note: DM% is not shown because it comes from the source feed in system feedbase,
            # not from user input. The add_feed tool copies nutrients from the source feed.
            description = (
                f"添加饲料 {name} 到饲料库 [{feed_base_name}] ({cost:.2f}/kg)"
                if locale != "en-US"
                else f"Add feed {name} to feedbase [{feed_base_name}] ({cost:.2f}/kg)"
            )
            return description, operation_data
            
        elif tool_name == "formulate_ration":
            target_animals = tool_args.get("target_animals", "奶牛")
            requirements = tool_args.get("requirements", {})
            constraints = tool_args.get("constraints", {})
            
            operation_data = {
                "target_animals": target_animals,
                "requirements": requirements,
                "constraints": constraints
            }
            description = "进行配方优化" if locale != "en-US" else "Run ration optimization"
            return description, operation_data
            
        elif tool_name == "check_feeds":
            operation_data = {"action": "检查可用饲料"}
            description = "检查可用饲料库" if locale != "en-US" else "Check available feeds"
            return description, operation_data
            
        elif tool_name == "export_formulation":
            format_type = tool_args.get("format", "Excel")
            operation_data = {"export_format": format_type}
            description = (
                f"导出配方为 {format_type} 格式"
                if locale != "en-US"
                else f"Export formulation as {format_type}"
            )
            return description, operation_data
            
        elif tool_name == "list_feed_bases":
            operation_data = {"action": "列出饲料基础库"}
            description = "获取饲料基础库列表" if locale != "en-US" else "List feedbases"
            return description, operation_data
            
        elif tool_name == "predict_dairy_requirements":
            body_weight = tool_args.get("body_weight_kg")
            feedbase_name = tool_args.get("feedbase_name", "")
            operation_data = {
                "body_weight_kg": body_weight,
                "feedbase_name": feedbase_name
            }
            # Agent typically uses stored animal_params from set_animal_params
            if body_weight is None:
                description = (
                    "计算营养需求 (使用已存储参数)"
                    if locale != "en-US"
                    else "Calculate nutrition requirements (using stored params)"
                )
            else:
                description = (
                    f"计算营养需求 (体重{body_weight}kg)"
                    if locale != "en-US"
                    else f"Calculate nutrition requirements (BW {body_weight}kg)"
                )
            return description, operation_data
            
        elif tool_name == "evaluate_diet_with_nasem":
            # Agent uses stored animal_params from set_animal_params
            operation_data = {}
            description = (
                "使用NASEM模型评估日粮 (使用已存储参数)"
                if locale != "en-US"
                else "Evaluate diet with NASEM (using stored params)"
            )
            return description, operation_data
        
        elif tool_name == "set_animal_params":
            body_weight = tool_args.get("body_weight", 0)
            milk_prod = tool_args.get("milk_prod", 0)
            dim = tool_args.get("dim", 90)
            parity = tool_args.get("parity", 2)
            bcs = tool_args.get("bcs", 3.0)
            milk_fat_pct = tool_args.get("milk_fat_pct", 3.5)
            milk_protein_pct = tool_args.get("milk_protein_pct", 3.2)
            days_pregnant = tool_args.get("days_pregnant", 0)
            breed = tool_args.get("breed", "Holstein")
            milk_price = tool_args.get("milk_price_per_kg")
            
            operation_data = {
                "body_weight": f"{body_weight}kg",
                "milk_prod": f"{milk_prod}kg/d",
                "dim": dim,
                "parity": parity,
                "bcs": bcs,
                "milk_fat_pct": f"{milk_fat_pct}%",
                "milk_protein_pct": f"{milk_protein_pct}%",
                "days_pregnant": days_pregnant,
                "breed": breed,
            }
            if milk_price is not None:
                operation_data["milk_price"] = f"{milk_price}/kg"
            description = (
                f"设置动物参数 (体重{body_weight}kg, 产奶{milk_prod}kg, DIM{dim}, 胎次{parity})"
                if locale != "en-US"
                else f"Set animal params (BW {body_weight}kg, milk {milk_prod}kg, DIM{dim}, parity {parity})"
            )
            return description, operation_data
            
        else:
            description = (
                f"执行配方工具 {tool_name}"
                if locale != "en-US"
                else f"Run formulation tool {tool_name}"
            )
            return description, {}
    
    def _create_analysis_summary(self) -> str:
        """Create final summary of analysis"""
        label = self._get_analysis_label()
        if not self.active_analysis:
            return f"{label}: Completed" if self.preferred_language == "en-US" else f"{label}: 已完成"
        
        operations = self.active_analysis["operations"]
        operation_count = len(operations)
        
        if self.preferred_language == "en-US":
            return f"{label}: {operation_count} operations completed"
        return f"{label}: {operation_count}项操作 已完成"
    
    def _create_formulation_summary(self) -> str:
        """Create final summary of formulation"""
        label = self._get_formulation_label()
        if not self.active_formulation:
            return f"{label}: Completed" if self.preferred_language == "en-US" else f"{label}: 已完成"
        
        operations = self.active_formulation["operations"]
        operation_count = len(operations)
        
        if self.preferred_language == "en-US":
            return f"{label}: {operation_count} operations completed"
        return f"{label}: {operation_count}项操作 已完成"
    
    def parse_messages(self, messages: List[BaseMessage]) -> List[ParsedMessage]:
        """Parse list of messages (for history context)"""
        # Reset parser state to avoid carryover from previous parsing
        self.reset_state()
        
        # Convert dict messages to BaseMessage objects if needed
        converted_messages = []
        for msg in messages:
            if isinstance(msg, dict):
                msg_type = msg.get("type", "").lower()
                content = msg.get("content", "")
                additional_kwargs = msg.get("additional_kwargs", {})
                
                if msg_type == "human":
                    converted_messages.append(HumanMessage(content=content, additional_kwargs=additional_kwargs))
                elif msg_type == "ai":
                    ai_msg = AIMessage(content=content, additional_kwargs=additional_kwargs)
                    if "tool_calls" in msg:
                        ai_msg.tool_calls = msg["tool_calls"]
                    converted_messages.append(ai_msg)
                elif msg_type == "tool":
                    converted_messages.append(ToolMessage(
                        content=content, 
                        tool_call_id=msg.get("tool_call_id", ""), 
                        additional_kwargs=additional_kwargs
                    ))
                elif msg_type == "system":
                    converted_messages.append(SystemMessage(content=content, additional_kwargs=additional_kwargs))
            else:
                converted_messages.append(msg)
        
        # Process messages sequentially, tracking tool calls and ending groups appropriately
        result = []
        
        # Log message types for debugging
        message_types = [type(msg).__name__ for msg in converted_messages]
        logger.info(f"Processing {len(converted_messages)} messages: {message_types}")
        
        for msg in converted_messages:
            timestamp = getattr(msg, 'timestamp', msg.additional_kwargs.get('timestamp', 0))
            if timestamp == 0:
                timestamp = msg.additional_kwargs.get('created_at', 0)
            
            # Handle AIMessage - both with and without tool calls
            if isinstance(msg, AIMessage):
                # First handle tool calls if present
                has_tool_calls = hasattr(msg, 'tool_calls') and msg.tool_calls
                
                if has_tool_calls:
                    # Check each tool call to see if we need to end current groups or start new ones
                    for tool_call in msg.tool_calls:
                        tool_name = tool_call.get("name", "")
                        tool_args = tool_call.get("args", {})
                        tool_id = tool_call.get("id", f"tool_{int(timestamp * 1000000)}")
                        
                        # Check if we should end current analysis (non-analysis tool starting)
                        if self._should_end_analysis(tool_name):
                            summary = self._create_analysis_summary()
                            result.append(create_analysis_complete_message(
                                summary=summary,
                                message_id=self.active_analysis["message_id"],
                                timestamp=timestamp,
                                operations_count=len(self.active_analysis["operations"]),
                                operations=self.active_analysis["operations"],
                                preferred_language=self.preferred_language,
                            ))
                            self.active_analysis = None
                        
                        # Check if we should end current formulation (non-formulation tool starting)
                        # export_formulation is the final step, so it should end the formulation
                        if tool_name == "export_formulation" and self.active_formulation:
                            # End formulation when export starts
                            summary = self._create_formulation_summary()
                            result.append(create_formulation_complete_message(
                                summary=summary,
                                message_id=self.active_formulation["message_id"],
                                timestamp=timestamp,
                                operations_count=len(self.active_formulation["operations"]),
                                operations=self.active_formulation["operations"],
                                formulation_results=self.active_formulation.get("results", {}),
                                preferred_language=self.preferred_language,
                            ))
                            self.active_formulation = None
                        elif self._is_formulation_tool(tool_name):
                            # Continue formulation for other formulation tools
                            pass
                        elif self.active_formulation:
                            # End formulation when switching to non-formulation tool
                            summary = self._create_formulation_summary()
                            result.append(create_formulation_complete_message(
                                summary=summary,
                                message_id=self.active_formulation["message_id"],
                                timestamp=timestamp,
                                operations_count=len(self.active_formulation["operations"]),
                                operations=self.active_formulation["operations"],
                                formulation_results=self.active_formulation.get("results", {}),
                                preferred_language=self.preferred_language,
                            ))
                            self.active_formulation = None
                        
                        # Check if we should start new analysis
                        if self._should_start_analysis(tool_name):
                            analysis_message_id = f"{self.session_id}_history_analysis_{int(timestamp * 1000000)}"
                            self.active_analysis = {
                                "message_id": analysis_message_id,
                                "operations": [],
                                "start_time": timestamp
                            }
                        
                        # Check if we should start new formulation
                        if self._is_formulation_tool(tool_name) and not self.active_formulation:
                            formulation_message_id = f"{self.session_id}_history_formulation_{int(timestamp * 1000000)}"
                            self.active_formulation = {
                                "message_id": formulation_message_id,
                                "operations": [],
                                "start_time": timestamp,
                                "results": {}
                            }
                        
                        # Handle analysis tools - add operations but don't emit individual tool calls
                        current_tool_type = self._is_analysis_tool(tool_name)
                        if current_tool_type:
                            if self.active_analysis:
                                operation = self._get_operation_description(tool_name, tool_args)
                                self.active_analysis["operations"].append(operation)
                            # Don't add individual tool_call messages for analysis tools
                            continue
                        
                        # Handle formulation tools - add operations but don't emit individual tool calls
                        if self._is_formulation_tool(tool_name):
                            if self.active_formulation:
                                operation, operation_data = self._get_formulation_operation_description(tool_name, tool_args)
                                self.active_formulation["operations"].append(operation)
                            # Don't add individual tool_call messages for formulation tools
                            continue
                        
                        # Handle delegation tools (store for later combination)
                        if tool_name in self.delegation_tools:
                            self.pending_delegations[tool_id] = (tool_name, tool_args, timestamp)
                            continue
                        elif tool_name == "ask_user":
                            # Store description and questions for later - will be used when processing tool result
                            self.pending_ask_user[tool_id] = {
                                "description": tool_args.get('description'),
                                "questions": tool_args.get('questions', [])
                            }
                            continue
                        elif tool_name == "calculate":
                            # Store calculator expression for later combination with result
                            expression = tool_args.get('expression', '')
                            self.pending_calculations[tool_id] = (expression, timestamp)
                            continue
                        elif tool_name == "create_artifact":
                            # Create artifact message directly
                            result.append(create_artifact_message(
                                title=tool_args.get('title', ''),
                                description=tool_args.get('description', ''),
                                html_content=tool_args.get('html_content', ''),
                                message_id=f"{tool_id}_artifact",
                                timestamp=timestamp
                            ))
                            continue
                        else:
                            # Regular tool call
                            result.append(create_tool_call_message(
                                tool_name=tool_name,
                                tool_args=tool_args,
                                tool_id=tool_id,
                                timestamp=timestamp,
                                preferred_language=self.preferred_language,
                            ))
                else:
                    # AIMessage without tool calls - end any active groups
                    if self.active_analysis:
                        summary = self._create_analysis_summary()
                        result.append(create_analysis_complete_message(
                            summary=summary,
                            message_id=self.active_analysis["message_id"],
                            timestamp=timestamp,
                            operations_count=len(self.active_analysis["operations"]),
                            operations=self.active_analysis["operations"],
                            preferred_language=self.preferred_language,
                        ))
                        self.active_analysis = None
                    
                    if self.active_formulation:
                        summary = self._create_formulation_summary()
                        result.append(create_formulation_complete_message(
                            summary=summary,
                            message_id=self.active_formulation["message_id"],
                            timestamp=timestamp,
                            operations_count=len(self.active_formulation["operations"]),
                            operations=self.active_formulation["operations"],
                            formulation_results=self.active_formulation.get("results", {}),
                            preferred_language=self.preferred_language,
                        ))
                        self.active_formulation = None
                
                # Process AI message content if present (for both cases)
                if msg.content.strip():
                    result.append(create_agent_message(
                        content=msg.content,
                        message_id=f"msg_{hash(str(msg.content))}_{int(timestamp * 1000000)}",
                        timestamp=timestamp,
                        is_streaming=False
                    ))
                    
            elif isinstance(msg, ToolMessage):
                tool_name = getattr(msg, 'name', msg.additional_kwargs.get('tool_name', 'unknown'))
                tool_id = getattr(msg, 'tool_call_id', f"tool_{int(timestamp * 1000000)}")
                
                # First, extract any special data and create events BEFORE skipping
                result_for_this_tool = []
                
                # Check for file export data and create file export event
                file_export_data = self._extract_file_export_data(msg.content)
                if file_export_data:
                    result_for_this_tool.append(create_file_export_message(
                        filename=file_export_data['filename'],
                        file_type=file_export_data['file_type'],
                        filepath=file_export_data['filepath'],
                        message_id=f"{tool_id}_export",
                        timestamp=timestamp,
                        preferred_language=self.preferred_language,
                        description=file_export_data.get('description'),
                    ))
                

                
                # Check for calculator tool results BEFORE skipping
                if tool_id in self.pending_calculations:
                    expression, call_timestamp = self.pending_calculations.pop(tool_id)
                    all_results = self._extract_all_results(msg.content)

                    if all_results:
                        # Create calculation message with all results
                        result.append(create_calculation_message(
                            expression=expression,
                            result=all_results[-1],  # Keep for backward compatibility
                            message_id=f"{tool_id}_calc",
                            timestamp=timestamp,
                            preferred_language=self.preferred_language,
                            all_results=all_results,
                        ))
                    continue

                # Skip tool results for grouped tools completely, but add any extracted events
                if (self._is_analysis_tool(tool_name) and self.active_analysis) or \
                   (self._is_formulation_tool(tool_name) and self.active_formulation) or \
                   tool_name in ["create_artifact"]:
                    result.extend(result_for_this_tool)  # Add any file export/artifact events
                    continue  # Skip processing this ToolMessage entirely

                # Check for delegation tool results and handle role transitions
                if tool_id in self.pending_delegations:
                    tool_name, tool_args, call_timestamp = self.pending_delegations.pop(tool_id)
                    to_role = self._get_delegation_role(tool_name)

                    result.append(create_role_transition_message(
                        to_role=to_role,
                        message_id=f"{tool_id}_transition",
                        timestamp=timestamp,
                        preferred_language=self.preferred_language,
                    ))
                    continue

                # Check for ask_user tool result - render as user message with questions context
                if tool_name == "ask_user":
                    ask_user_data = self.pending_ask_user.pop(tool_id, {"description": None, "questions": []})
                    result.append(create_user_input_message(
                        content=msg.content,
                        questions=ask_user_data.get("questions", []),
                        message_id=f"{tool_id}_user_input",
                        timestamp=timestamp,
                        description=ask_user_data.get("description")
                    ))
                    continue

                # Regular tool result - add any extracted events first, then the tool result
                result.extend(result_for_this_tool)
                result.append(create_tool_result_message(
                    content=msg.content,
                    tool_name=tool_name,
                    tool_id=tool_id,
                    timestamp=timestamp
                ))
                
            elif isinstance(msg, HumanMessage):
                # End any active groups when user sends a new message
                if self.active_analysis:
                    summary = self._create_analysis_summary()
                    result.append(create_analysis_complete_message(
                        summary=summary,
                        message_id=self.active_analysis["message_id"],
                        timestamp=timestamp,
                        operations_count=len(self.active_analysis["operations"]),
                        operations=self.active_analysis["operations"],
                        preferred_language=self.preferred_language,
                    ))
                    self.active_analysis = None
                
                if self.active_formulation:
                    summary = self._create_formulation_summary()
                    result.append(create_formulation_complete_message(
                        summary=summary,
                        message_id=self.active_formulation["message_id"],
                        timestamp=timestamp,
                        operations_count=len(self.active_formulation["operations"]),
                        operations=self.active_formulation["operations"],
                        formulation_results=self.active_formulation.get("results", {}),
                        preferred_language=self.preferred_language,
                    ))
                    self.active_formulation = None
                
                # Add user message
                result.append(create_user_message(
                    content=msg.content,
                    message_id=f"msg_{hash(str(msg.content))}_{int(timestamp * 1000000)}",
                    timestamp=timestamp
                ))
            
            # Skip SystemMessage and other types
        
        # Complete any remaining groups at the end
        if self.active_analysis:
            summary = self._create_analysis_summary()
            result.append(create_analysis_complete_message(
                summary=summary,
                message_id=self.active_analysis["message_id"],
                timestamp=timestamp,
                operations_count=len(self.active_analysis["operations"]),
                operations=self.active_analysis["operations"],
                preferred_language=self.preferred_language,
            ))
            self.active_analysis = None
        
        if self.active_formulation:
            summary = self._create_formulation_summary()
            result.append(create_formulation_complete_message(
                summary=summary,
                message_id=self.active_formulation["message_id"],
                timestamp=timestamp,
                operations_count=len(self.active_formulation["operations"]),
                operations=self.active_formulation["operations"],
                formulation_results=self.active_formulation.get("results", {}),
                preferred_language=self.preferred_language,
            ))
            self.active_formulation = None
        
        return result
    
    def parse_streaming_event(self, event: Dict[str, Any]) -> List[ParsedMessage]:
        """Parse streaming LangGraph event"""
        event_type = event.get("event", "")
        timestamp = event.get("timestamp", 0)
        
        if event_type == "on_chat_model_start":
            # New AI response starting - increment counter
            self.agent_message_counter += 1
            self.current_agent_message_id = f"{self.session_id}_agent_{self.agent_message_counter}"
            return []  # Don't send anything yet, wait for chunks
        
        elif event_type == "on_chat_model_stream":
            # Agent content chunk - use current message ID
            chunk = event["data"]["chunk"]
            chunk_content = chunk.content
            results = []
            
            # Handle thinking/reasoning mode: stream reasoning_content as separate thinking message
            # reasoning_content is available in additional_kwargs for models that support it (Qwen, DeepSeek, etc.)
            reasoning_content = None
            if hasattr(chunk, 'additional_kwargs'):
                reasoning_content = chunk.additional_kwargs.get('reasoning_content')
            
            # Stream reasoning content (thinking) as a separate message type
            if reasoning_content and self.current_agent_message_id:
                # Use a separate message ID for reasoning content
                reasoning_message_id = f"{self.current_agent_message_id}_thinking"
                results.append(create_thinking_message(
                    content=reasoning_content,
                    message_id=reasoning_message_id,
                    timestamp=timestamp,
                    is_streaming=True
                ))
            
            # Stream regular content (final answer)
            if chunk_content and self.current_agent_message_id:
                results.append(create_agent_message(
                    content=chunk_content,
                    message_id=self.current_agent_message_id,
                    timestamp=timestamp,
                    is_streaming=True
                ))

            return results
        
        # elif event_type == "on_chat_model_end":
        #     # AI response finished - reset current message ID
        #     self.current_agent_message_id = None
        #     return []  # Don't complete analysis here - it's too frequent
        
        elif event_type == "on_chain_end":
            # Check if this is the main LangGraph chain ending
            name = event.get("name", "")
            result = []
            
            if name == "LangGraph":
                # Complete any active analysis
                if self.active_analysis:
                    summary = self._create_analysis_summary()
                    result.append(create_analysis_complete_message(
                        summary=summary,
                        message_id=self.active_analysis["message_id"],
                        timestamp=timestamp,
                        operations_count=len(self.active_analysis["operations"]),
                        operations=self.active_analysis["operations"],
                        preferred_language=self.preferred_language,
                    ))
                    self.active_analysis = None
                
                # Complete any active formulation
                if self.active_formulation:
                    summary = self._create_formulation_summary()
                    result.append(create_formulation_complete_message(
                        summary=summary,
                        message_id=self.active_formulation["message_id"],
                        timestamp=timestamp,
                        operations_count=len(self.active_formulation["operations"]),
                        operations=self.active_formulation["operations"],
                        formulation_results=self.active_formulation.get("results", {}),
                        preferred_language=self.preferred_language,
                    ))
                    self.active_formulation = None
                    
            return result
        
        elif event_type == "on_tool_start":
            # Tool call started
            tool_name = event.get("name", "")
            # Get args from LangGraph streaming events
            tool_args = event["data"].get("input", {})
            tool_id = event.get("run_id", f"tool_{int(timestamp * 1000000)}")
            
            result = []
            
            # Check if we should end current analysis (non-analysis tool starting)
            if self._should_end_analysis(tool_name):
                summary = self._create_analysis_summary()
                result.append(create_analysis_complete_message(
                    summary=summary,
                    message_id=self.active_analysis["message_id"],
                    timestamp=timestamp,
                    operations_count=len(self.active_analysis["operations"]),
                    operations=self.active_analysis["operations"],
                    preferred_language=self.preferred_language,
                ))
                self.active_analysis = None
                
            # Check if we should end current formulation (non-formulation tool starting)
            # export_formulation is the final step, so it should end the formulation
            if tool_name == "export_formulation" and self.active_formulation:
                # End formulation when export starts
                summary = self._create_formulation_summary()
                result.append(create_formulation_complete_message(
                    summary=summary,
                    message_id=self.active_formulation["message_id"],
                    timestamp=timestamp,
                    operations_count=len(self.active_formulation["operations"]),
                    operations=self.active_formulation["operations"],
                    formulation_results=self.active_formulation.get("results", {}),
                    preferred_language=self.preferred_language,
                ))
                self.active_formulation = None
            elif self._is_formulation_tool(tool_name):
                # Continue formulation for other formulation tools
                pass
            elif self.active_formulation:
                # End formulation when switching to non-formulation tool
                summary = self._create_formulation_summary()
                result.append(create_formulation_complete_message(
                    summary=summary,
                    message_id=self.active_formulation["message_id"],
                    timestamp=timestamp,
                    operations_count=len(self.active_formulation["operations"]),
                    operations=self.active_formulation["operations"],
                    formulation_results=self.active_formulation.get("results", {}),
                    preferred_language=self.preferred_language,
                ))
                self.active_formulation = None
                
            # Check if we should start new analysis
            if self._should_start_analysis(tool_name):
                analysis_message_id = f"{self.session_id}_analysis_{int(timestamp * 1000000)}"
                self.active_analysis = {
                    "message_id": analysis_message_id,
                    "operations": [],
                    "start_time": timestamp
                }
                
                result.append(create_analysis_start_message(
                    analysis_type=self._get_analysis_label(),
                    message_id=analysis_message_id,
                    timestamp=timestamp,
                    preferred_language=self.preferred_language,
                ))
            
            # Check if we should start new formulation
            if self._is_formulation_tool(tool_name) and not self.active_formulation:
                formulation_message_id = f"{self.session_id}_formulation_{int(timestamp * 1000000)}"
                self.active_formulation = {
                    "message_id": formulation_message_id,
                    "operations": [],
                    "start_time": timestamp,
                    "results": {}
                }
                
                result.append(create_formulation_start_message(
                    formulation_type=self._get_formulation_label(),
                    message_id=formulation_message_id,
                    timestamp=timestamp,
                    preferred_language=self.preferred_language,
                ))
            
            # Handle analysis tools with live updates
            current_tool_type = self._is_analysis_tool(tool_name)
            if current_tool_type:
                if self.active_analysis:
                    operation = self._get_operation_description(tool_name, tool_args)
                    self.active_analysis["operations"].append(operation)
                    result.append(create_analysis_update_message(
                        operation=operation,
                        message_id=self.active_analysis["message_id"],
                        timestamp=timestamp
                    ))
                # Don't send individual tool_call messages for analysis tools
                return result
            
            # Handle formulation tools with live updates
            if self._is_formulation_tool(tool_name):
                if self.active_formulation:
                    operation, operation_data = self._get_formulation_operation_description(tool_name, tool_args)
                    self.active_formulation["operations"].append(operation)
                    result.append(create_formulation_update_message(
                        operation=operation,
                        message_id=self.active_formulation["message_id"],
                        timestamp=timestamp,
                        operation_data=operation_data
                    ))
                # Don't send individual tool_call messages for formulation tools
                return result
            
            # Handle other tool types
            if tool_name in self.delegation_tools:
                # Store delegation for later combination
                self.pending_delegations[tool_id] = (tool_name, tool_args, timestamp)
                return result  # Return any analysis events but don't add tool call
            elif tool_name == "ask_user":
                # Store description and questions for later - will be used when processing tool result
                self.pending_ask_user[tool_id] = {
                    "description": tool_args.get('description'),
                    "questions": tool_args.get('questions', [])
                }
                return result
            elif tool_name == "calculate":
                # Store calculator expression for later combination with result
                expression = tool_args.get('expression', '')
                self.pending_calculations[tool_id] = (expression, timestamp)
                return result  # Don't send tool call event
            elif tool_name == "create_artifact":
                # Create artifact message directly from tool args
                result.append(create_artifact_message(
                    title=tool_args.get('title', ''),
                    description=tool_args.get('description', ''),
                    html_content=tool_args.get('html_content', ''),
                    message_id=f"{tool_id}_artifact",
                    timestamp=timestamp
                ))
                return result
            elif tool_name == "export_formulation" or self._is_formulation_tool(tool_name):
                # Don't send formulation tool calls to frontend
                return result
            else:
                # Regular tool call
                result.append(create_tool_call_message(
                    tool_name=tool_name,
                    tool_args=tool_args,
                    tool_id=tool_id,
                    timestamp=timestamp,
                    preferred_language=self.preferred_language,
                ))
                return result
        
        elif event_type == "on_tool_end":
            # Tool call completed
            tool_name = event.get("name", "")
            tool_id = event.get("run_id", f"tool_{int(timestamp * 1000000)}")

            # Extract content from output (handle both ToolMessage objects and strings)
            output = event["data"].get("output", "")
            if hasattr(output, 'content'):
                result_content = str(output.content)
            else:
                result_content = str(output)
            
            
            # Check if this is a delegation tool result
            if tool_id in self.pending_delegations:
                tool_name, tool_args, call_timestamp = self.pending_delegations.pop(tool_id)
                to_role = self._get_delegation_role(tool_name)

                # Create single role transition bubble
                return [create_role_transition_message(
                    to_role=to_role,
                    message_id=f"{tool_id}_transition",
                    timestamp=timestamp,
                    preferred_language=self.preferred_language,
                )]

            # Check if this is ask_user tool result - render as user message with questions context
            if tool_name == "ask_user":
                ask_user_data = self.pending_ask_user.pop(tool_id, {"description": None, "questions": []})
                return [create_user_input_message(
                    content=result_content,
                    questions=ask_user_data.get("questions", []),
                    message_id=f"{tool_id}_user_input",
                    timestamp=timestamp,
                    description=ask_user_data.get("description")
                )]

            # Check if this is a calculator tool result
            if tool_id in self.pending_calculations:
                expression, call_timestamp = self.pending_calculations.pop(tool_id)
                all_results = self._extract_all_results(result_content)

                if all_results:
                    # Create calculation message with all results
                    return [create_calculation_message(
                        expression=expression,
                        result=all_results[-1],  # Keep for backward compatibility
                        message_id=f"{tool_id}_calc",
                        timestamp=timestamp,
                        preferred_language=self.preferred_language,
                        all_results=all_results,
                    )]

            # First, extract any special data and create events
            result = []
            
            # Check for file export data and create file export event
            file_export_data = self._extract_file_export_data(result_content)
            if file_export_data:
                result.append(create_file_export_message(
                    filename=file_export_data['filename'],
                    file_type=file_export_data['file_type'],
                    filepath=file_export_data['filepath'],
                    message_id=f"{tool_id}_export",
                    timestamp=timestamp,
                    preferred_language=self.preferred_language,
                    description=file_export_data.get('description'),
                ))
            

            
            # Then decide whether to include the raw tool result message
            current_tool_type = self._is_analysis_tool(tool_name)
            is_formulation_tool = self._is_formulation_tool(tool_name)
            if tool_name in ["create_artifact", "export_formulation", "calculate"] or current_tool_type or is_formulation_tool:
                # Don't include raw tool result for these tools (handled by analysis/formulation/calculation updates)
                return result
            else:
                # Include the tool result message for other tools
                result.append(create_tool_result_message(
                    content=result_content,
                    tool_name=tool_name,
                    tool_id=tool_id,
                    timestamp=timestamp
                ))
                return result
        
        # Unknown or unhandled event type  
        return []
    
    

# No global parser - create per session
