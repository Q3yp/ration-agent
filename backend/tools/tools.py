import os
import subprocess
import uuid
import json
import shlex
import ast
import operator
import math
from pathlib import Path
from typing import Optional, List, Annotated
from datetime import datetime
from langchain_core.tools import tool, InjectedToolCallId, InjectedToolArg
from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from .excel_tools import get_excel_tools
from .formulation_tools import create_formulation_tools

try:
    import bleach
    BLEACH_AVAILABLE = True
except ImportError:
    BLEACH_AVAILABLE = False
import logging

logger = logging.getLogger(__name__)

ALLOWED_SHELL_COMMANDS = {"ls", "cat", "head", "tail", "pwd", "echo", "uv"}
DISALLOWED_SHELL_TOKENS = [";", "&&", "||", "|", ">", "<", "`", "$("]


def validate_shell_command(command: str) -> Optional[str]:
    """
    Ensure shell command is limited to a safe allow-list and does not contain chaining operators.
    Returns an error message when invalid, otherwise None.
    """
    stripped = command.strip()
    if not stripped:
        return "Command cannot be empty"

    if any(token in stripped for token in DISALLOWED_SHELL_TOKENS):
        return "Command contains disallowed shell operators"

    try:
        tokens = shlex.split(stripped)
    except ValueError:
        return "Unable to parse command"

    if not tokens:
        return "Command cannot be empty"

    executable = tokens[0]
    if executable not in ALLOWED_SHELL_COMMANDS:
        return f"Command '{executable}' is not permitted"

    return None


def sanitize_html_content(html_content: str) -> str:
    """
    Sanitize HTML content to prevent XSS attacks while preserving safe elements.
    
    Args:
        html_content: Raw HTML content to sanitize
        
    Returns:
        Sanitized HTML content
    """
    if not BLEACH_AVAILABLE:
        logger.warning("Bleach not available - HTML content will not be sanitized")
        return html_content
    
    # Define allowed tags and attributes for HTML artifacts
    allowed_tags = [
        # Structure
        'html', 'head', 'body', 'title', 'meta',
        # Content
        'div', 'span', 'p', 'br', 'hr',
        # Headers
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        # Lists
        'ul', 'ol', 'li',
        # Tables
        'table', 'thead', 'tbody', 'tr', 'th', 'td',
        # Forms (for interactive content)
        'form', 'input', 'button', 'select', 'option', 'textarea', 'label',
        # Media
        'img', 'svg', 'canvas',
        # Text formatting
        'strong', 'b', 'em', 'i', 'u', 'code', 'pre',
        # Links (with restrictions)
        'a',
        # Style
        'style'
    ]
    
    allowed_attributes = {
        '*': ['class', 'id', 'style', 'data-*'],
        'a': ['href', 'target', 'rel'],
        'img': ['src', 'alt', 'width', 'height'],
        'input': ['type', 'name', 'value', 'placeholder', 'min', 'max', 'step'],
        'button': ['type', 'onclick'],
        'select': ['name', 'multiple'],
        'option': ['value', 'selected'],
        'textarea': ['name', 'rows', 'cols', 'placeholder'],
        'form': ['method', 'action'],
        'meta': ['charset', 'name', 'content', 'viewport'],
        'canvas': ['width', 'height'],
        'svg': ['width', 'height', 'viewBox', 'xmlns'],
        'table': ['border', 'cellpadding', 'cellspacing'],
        'th': ['colspan', 'rowspan'],
        'td': ['colspan', 'rowspan']
    }
    
    # Define allowed CSS properties
    allowed_css_properties = [
        'color', 'background-color', 'font-size', 'font-family', 'font-weight',
        'text-align', 'margin', 'padding', 'border', 'width', 'height',
        'display', 'position', 'top', 'left', 'right', 'bottom',
        'flex', 'grid', 'justify-content', 'align-items', 'gap',
        'border-radius', 'box-shadow', 'opacity', 'transform',
        'transition', 'animation'
    ]
    
    def css_sanitizer(style):
        """Custom CSS sanitizer"""
        if not style:
            return ''
        
        # Simple CSS property filtering
        safe_styles = []
        for declaration in style.split(';'):
            if ':' in declaration:
                prop, value = declaration.split(':', 1)
                prop = prop.strip().lower()
                if prop in allowed_css_properties:
                    # Basic value sanitization - remove javascript: and other dangerous protocols
                    value = value.strip()
                    if not any(dangerous in value.lower() for dangerous in ['javascript:', 'data:', 'vbscript:', 'expression(']):
                        safe_styles.append(f"{prop}: {value}")
        
        return '; '.join(safe_styles)
    
    try:
        # Sanitize the HTML
        sanitized = bleach.clean(
            html_content,
            tags=allowed_tags,
            attributes=allowed_attributes,
            css_sanitizer=css_sanitizer,
            strip=True,  # Remove disallowed tags completely
            strip_comments=True  # Remove HTML comments
        )
        
        logger.info("HTML content sanitized successfully")
        return sanitized
        
    except Exception as e:
        logger.error(f"HTML sanitization failed: {e}")
        # Fallback to basic escaping if sanitization fails
        import html
        return html.escape(html_content)


@tool
async def bash_command(
    command: str,
    config: Annotated[RunnableConfig, InjectedToolArg]
) -> str:
    """Execute a bash command in the session workspace. Only allowlisted utilities are permitted: ls, cat, head, tail, pwd, echo, uv."""
    try:
        # Import here to avoid circular imports
        from services.session_manager import session_manager

        # Extract session_id from config
        session_id = config["configurable"]["thread_id"]

        # Get session context
        session = await session_manager.get_session(session_id)
        if not session:
            return f"Error: Session '{session_id}' not found"

        # Ensure workspace exists and get path
        session.ensure_workspace_exists()
        session_workspace = session.workspace_path

        validation_error = validate_shell_command(command)
        if validation_error:
            return f"Error: {validation_error}"

        result = subprocess.run(
            command,
            shell=True,
            executable='/bin/bash',  # Force use of bash instead of sh
            cwd=session_workspace,
            capture_output=True,
            text=True,
            timeout=30  # 30 second timeout
        )

        output = ""
        if result.stdout:
            output += f"STDOUT:\n{result.stdout}"
        if result.stderr:
            output += f"\nSTDERR:\n{result.stderr}"
        if not output:
            output = "Command executed successfully with no output."

        output += f"\nReturn code: {result.returncode}"
        return output

    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 30 seconds"
    except Exception as e:
        return f"Error executing command: {str(e)}"


@tool
async def create_artifact(
    html_content: str,
    title: str,
    description: Optional[str] = None,
    config: Annotated[RunnableConfig, InjectedToolArg] = None
) -> str:
    """
    Create an HTML artifact displayed in the frontend.

    Creates interactive HTML content, charts, visualizations, or other 
    HTML-based content that the user can view and interact with.

    Args:
        html_content: The HTML content to save as an artifact (can include CSS and JavaScript)
        title: A descriptive title for the artifact
        description: Optional description of what the artifact contains

    Returns:
        Confirmation message with artifact details
    """
    try:
        # Import here to avoid circular imports
        from services.session_manager import session_manager

        # Extract session_id from config
        session_id = config["configurable"]["thread_id"]

        # Get session context
        session = await session_manager.get_session(session_id)
        if not session:
            return f"Error: Session '{session_id}' not found"

        # Ensure workspace exists
        session.ensure_workspace_exists()

        # Use HTML content directly without sanitization
        # Wrap content in a complete HTML document if it's not already
        if not html_content.strip().lower().startswith('<!doctype') and not html_content.strip().lower().startswith('<html'):
            full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 20px;
            line-height: 1.6;
        }}
        .artifact-container {{
            max-width: 100%;
            margin: 0 auto;
        }}
    </style>
</head>
<body>
    <div class="artifact-container">
        {html_content}
    </div>
</body>
</html>"""
        else:
            # If it's already a complete HTML document, use as-is
            full_html = html_content

        logger.info(f"Created HTML artifact for session {session_id}: {title}")

        # Return structured data that includes the HTML content for frontend display
        # No file saving needed - content is embedded in tool result and persisted via LangGraph checkpointing
        # NOTE: Artifacts are now created directly from tool call args by the message parser.
        # This return string is just for agent confirmation.

        return f"✅ HTML artifact created successfully!\n- Title: {title}\n- Description: {description or 'No description'}\n\nThe artifact is now available for display in the frontend."

    except Exception as e:
        logger.error(f"Failed to create HTML artifact: {e}")
        return f"❌ Error creating HTML artifact: {str(e)}"


@tool
def calculate(expression: str) -> str:
    """
    Evaluate mathematical expressions safely.

    Supported operations: +, -, *, /, ** (power), % (modulo), // (floor division)
    Functions: sqrt, sin, cos, tan, log, log10, exp, abs, round, ceil, floor, sum, min, max
    Constants: pi, e

    Expression formats:
    - Single: "2 + 2 * 3", "sqrt(16) + log(100)"
    - Multi-line (use \\n): "100 + 50\\n100 - 50\\n100 * 2"
    - Variables (use \\n): "x = 5\\ny = 10\\nx * y"

    Comments are not allowed. Variables persist across lines.
    """
    try:
        # Define allowed operations for safe evaluation
        allowed_operators = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.FloorDiv: operator.floordiv,
            ast.Mod: operator.mod,
            ast.Pow: operator.pow,
            ast.USub: operator.neg,
            ast.UAdd: operator.pos,
        }

        # Define allowed functions
        allowed_functions = {
            'sqrt': math.sqrt,
            'sin': math.sin,
            'cos': math.cos,
            'tan': math.tan,
            'asin': math.asin,
            'acos': math.acos,
            'atan': math.atan,
            'log': math.log,
            'log10': math.log10,
            'exp': math.exp,
            'abs': abs,
            'round': round,
            'ceil': math.ceil,
            'floor': math.floor,
            'sum': sum,
            'min': min,
            'max': max,
            'len': len,
        }

        # Define allowed constants
        allowed_names = {
            'pi': math.pi,
            'e': math.e,
        }

        class SafeCalculator(ast.NodeVisitor):
            """AST visitor for safe mathematical expression evaluation"""

            def __init__(self, variables=None):
                self.variables = variables or {}

            def visit_Expression(self, node):
                return self.visit(node.body)

            def visit_Constant(self, node):
                return node.value

            def visit_Num(self, node):  # For Python < 3.8 compatibility
                return node.n

            def visit_BinOp(self, node):
                left = self.visit(node.left)
                right = self.visit(node.right)
                op_type = type(node.op)
                if op_type not in allowed_operators:
                    raise ValueError(f"Operator {op_type.__name__} not allowed")
                return allowed_operators[op_type](left, right)

            def visit_UnaryOp(self, node):
                operand = self.visit(node.operand)
                op_type = type(node.op)
                if op_type not in allowed_operators:
                    raise ValueError(f"Unary operator {op_type.__name__} not allowed")
                return allowed_operators[op_type](operand)

            def visit_Call(self, node):
                if not isinstance(node.func, ast.Name):
                    raise ValueError("Only simple function calls are allowed")

                func_name = node.func.id
                if func_name not in allowed_functions:
                    raise ValueError(f"Function '{func_name}' not allowed")

                args = [self.visit(arg) for arg in node.args]
                return allowed_functions[func_name](*args)

            def visit_Name(self, node):
                name = node.id
                # Check variables first, then allowed constants
                if name in self.variables:
                    return self.variables[name]
                elif name in allowed_names:
                    return allowed_names[name]
                else:
                    raise ValueError(f"Name '{name}' is not defined")

            def visit_List(self, node):
                return [self.visit(item) for item in node.elts]

            def visit_Tuple(self, node):
                return tuple(self.visit(item) for item in node.elts)

            def generic_visit(self, node):
                raise ValueError(f"Node type {type(node).__name__} not allowed")

        # Helper function to format numbers
        def format_number(value):
            """Format a number for display"""
            if isinstance(value, float):
                if abs(value) < 1e-10:
                    return "0"
                elif abs(value) > 1e10 or abs(value) < 1e-4:
                    return f"{value:.6e}"
                else:
                    return f"{value:.6f}".rstrip('0').rstrip('.')
            else:
                return str(value)

        # Handle multi-line expressions with assignments
        lines = expression.strip().split('\n')
        variables = {}
        result = None
        steps = []  # Track intermediate steps
        results = []  # Track all expression results (non-assignments)

        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue

            # Check if this is an assignment
            if '=' in line and not any(op in line.split('=')[0] for op in ['==', '!=', '<=', '>=']):
                parts = line.split('=', 1)
                var_name = parts[0].strip()
                expr = parts[1].strip()

                # Validate variable name
                if not var_name.isidentifier():
                    return f"Error: Invalid variable name '{var_name}' on line {line_num}"

                # Parse and evaluate the expression
                tree = ast.parse(expr, mode='eval')
                calculator = SafeCalculator(variables)
                result = calculator.visit(tree)
                variables[var_name] = result

                # Track step
                formatted_value = format_number(result) if isinstance(result, (int, float)) else str(result)
                steps.append(f"{var_name} = {formatted_value}")
            else:
                # Regular expression (not an assignment)
                tree = ast.parse(line, mode='eval')
                calculator = SafeCalculator(variables)
                result = calculator.visit(tree)
                results.append(result)

        # Format the output
        output_lines = []

        # Show intermediate variable assignments if there are any
        if steps:
            output_lines.append("Calculation Steps:")
            for step in steps:
                output_lines.append(f"  {step}")
            output_lines.append("")

        # Show all variable values if there are variables
        if variables:
            output_lines.append("Variables:")
            for var_name, var_value in variables.items():
                formatted_value = format_number(var_value) if isinstance(var_value, (int, float)) else str(var_value)
                output_lines.append(f"  {var_name} = {formatted_value}")
            output_lines.append("")

        # Show intermediate expression results if there are multiple
        if len(results) > 1:
            output_lines.append("Intermediate Results:")
            for i, res in enumerate(results[:-1], 1):  # All except last
                formatted = format_number(res) if isinstance(res, (int, float)) else str(res)
                output_lines.append(f"  [{i}] {formatted}")
            output_lines.append("")

        # Determine final result
        # Priority: last non-assignment result > last variable value > last assignment
        if results:
            # Use the last expression result
            final_result = results[-1]
        elif result is not None:
            # Use the last computed value
            final_result = result
        else:
            return "Error: No result to return"

        # Format final result
        if isinstance(final_result, (int, float)):
            formatted_result = format_number(final_result)
            output_lines.append(f"Result: {formatted_result}")
        elif isinstance(final_result, (list, tuple)):
            output_lines.append(f"Result: {final_result}")
        else:
            output_lines.append(f"Result: {final_result}")

        return "\n".join(output_lines)

    except SyntaxError as e:
        return f"Syntax Error: Invalid expression - {str(e)}"
    except ValueError as e:
        return f"Error: {str(e)}"
    except ZeroDivisionError:
        return "Error: Division by zero"
    except Exception as e:
        logger.error(f"Calculator error: {e}")
        return f"Calculation Error: {str(e)}"


def get_file_management_tools():
    """Get file management tools (session context extracted from config at runtime)."""
    # Note: FileManagementToolkit tools don't support InjectedToolArg yet
    # They will operate in the agent's working directory, which is set by bash_command
    # For now, we'll return empty list and rely on bash for file operations
    # TODO: Implement custom write_file and list_directory tools with InjectedToolArg
    return []


# --- Consolidated tool registry ---

async def get_tools(animal_type: str = "dairy_cow", include_file_tools: bool = False):
    """Get the full tool list for a single agent.

    Args:
        animal_type: Animal type (dairy_cow, beef_cow, cat, dog)
        include_file_tools: If True, include Excel, bash, artifact tools

    Returns:
        List of LangChain tools
    """
    from tools.ask_user_tool import ask_user

    # Core formulation tools (always included)
    formulation_tools = create_formulation_tools(animal_type)

    # Base tools for all animal types
    tools = formulation_tools + [calculate, ask_user]

    # Add NASEM tools for dairy cows only
    if animal_type == "dairy_cow":
        try:
            from tools.nasem_tools import get_nasem_tools
            nasem_tools = get_nasem_tools()
            tools.extend(nasem_tools)
            logger.info(f"Added {len(nasem_tools)} NASEM tools for dairy_cow")
        except ImportError as e:
            logger.warning(f"Could not load NASEM tools: {e}")

    # File/Excel/code tools (only when user has uploaded files)
    if include_file_tools:
        excel_tools = get_excel_tools()
        tools.extend([bash_command, create_artifact] + excel_tools)
        logger.info(f"Added file tools (bash, artifact, {len(excel_tools)} excel tools)")

    logger.info(f"get_tools({animal_type}, file_tools={include_file_tools}): {len(tools)} tools total")
    return tools

