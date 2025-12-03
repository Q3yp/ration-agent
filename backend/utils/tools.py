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
from langchain_community.agent_toolkits import FileManagementToolkit
from duckduckgo_search import DDGS
from .excel_tools import get_excel_tools
from .formulation_tools import create_formulation_tools
from .usda_tools import get_usda_tools

try:
    import bleach
    BLEACH_AVAILABLE = True
except ImportError:
    BLEACH_AVAILABLE = False

try:
    from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, BrowserConfig
    CRAWL4AI_AVAILABLE = True
except ImportError:
    CRAWL4AI_AVAILABLE = False
    AsyncWebCrawler = None
    CrawlerRunConfig = None
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
    Create an HTML artifact that can be displayed in the frontend.

    Use this tool when you want to create interactive HTML content, charts,
    visualizations, or any other HTML-based content that the user can interact with.

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
        artifact_data = {
            'title': title,
            'description': description or '',
            'html_content': full_html
        }

        # Use compact JSON serialization without newlines to avoid parsing issues
        artifact_json = json.dumps(artifact_data, ensure_ascii=False, separators=(',', ':'))

        return f"✅ HTML artifact created successfully!\n- Title: {title}\n- Description: {description or 'No description'}\n\n[ARTIFACT_DATA]\n{artifact_json}\n[/ARTIFACT_DATA]\n\nThe artifact is now available for display in the frontend."

    except Exception as e:
        logger.error(f"Failed to create HTML artifact: {e}")
        return f"❌ Error creating HTML artifact: {str(e)}"


@tool
def calculate(expression: str) -> str:
    """
    Safely evaluate mathematical expressions and perform calculations.

    This tool can handle:
    - Basic arithmetic operations: +, -, *, /, ** (power), % (modulo), // (floor division)
    - Mathematical functions: sqrt, sin, cos, tan, asin, acos, atan, log, log10, exp, abs, round, ceil, floor
    - Constants: pi, e
    - Statistical functions: sum, min, max
    - Multi-line calculations with variable assignments

    Examples:
    - Simple calculation: "2 + 2 * 3"
    - With functions: "sqrt(16) + log(100)"
    - Multi-line with variables: "x = 5\\ny = 10\\nresult = x * y\\nresult"
    - Percentage calculations: "(45 / 100) * 250"
    - Statistical: "sum([1, 2, 3, 4, 5])"

    Returns:
    - The calculated result as a string, or an error message if evaluation fails

    Note: This tool uses safe evaluation via AST parsing and does not execute arbitrary code.
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

        # Handle multi-line expressions with assignments
        lines = expression.strip().split('\n')
        variables = {}
        result = None

        for line in lines:
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
                    return f"Error: Invalid variable name '{var_name}'"

                # Parse and evaluate the expression
                tree = ast.parse(expr, mode='eval')
                calculator = SafeCalculator(variables)
                result = calculator.visit(tree)
                variables[var_name] = result
            else:
                # Regular expression
                tree = ast.parse(line, mode='eval')
                calculator = SafeCalculator(variables)
                result = calculator.visit(tree)

        # Format the result
        if result is None:
            return "Error: No result to return"

        # Handle different result types
        if isinstance(result, (int, float)):
            # Format numbers nicely
            if isinstance(result, float):
                # Round to reasonable precision
                if abs(result) < 1e-10:
                    formatted_result = "0"
                elif abs(result) > 1e10 or abs(result) < 1e-4:
                    formatted_result = f"{result:.6e}"
                else:
                    formatted_result = f"{result:.6f}".rstrip('0').rstrip('.')
            else:
                formatted_result = str(result)

            return f"Result: {formatted_result}"
        elif isinstance(result, (list, tuple)):
            return f"Result: {result}"
        else:
            return f"Result: {result}"

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


# Search tools
@tool
def duckduckgo_search(query: str, max_results: int = 10) -> str:
    """Search the web using DuckDuckGo with enhanced results"""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            
            formatted_results = []
            for i, result in enumerate(results, 1):
                formatted_results.append(
                    f"{i}. **{result.get('title', 'No title')}**\n"
                    f"   URL: {result.get('href', 'No URL')}\n"
                    f"   {result.get('body', 'No description')}\n"
                )
            
            return f"DuckDuckGo search results for '{query}':\n\n" + "\n".join(formatted_results)
    except Exception as e:
        logger.error(f"DuckDuckGo search failed: {e}")
        return f"DuckDuckGo search failed: {str(e)}"

@tool
def duckduckgo_news_search(query: str, max_results: int = 5) -> str:
    """Search for recent news using DuckDuckGo"""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.news(query, max_results=max_results))
            
            formatted_results = []
            for i, result in enumerate(results, 1):
                formatted_results.append(
                    f"{i}. **{result.get('title', 'No title')}**\n"
                    f"   Source: {result.get('source', 'Unknown')}\n"
                    f"   Date: {result.get('date', 'Unknown date')}\n"
                    f"   URL: {result.get('url', 'No URL')}\n"
                    f"   {result.get('body', 'No description')}\n"
                )
            
            return f"DuckDuckGo news search results for '{query}':\n\n" + "\n".join(formatted_results)
    except Exception as e:
        logger.error(f"DuckDuckGo news search failed: {e}")
        return f"DuckDuckGo news search failed: {str(e)}"

@tool
async def crawl_website(url: str, extract_content: bool = True) -> str:
    """Crawl and extract content from a specific website using Crawl4AI"""
    if not CRAWL4AI_AVAILABLE:
        return "Crawl4AI is not available. Please install it with: pip install crawl4ai"
    
    try:
        async with AsyncWebCrawler() as crawler:
            config = CrawlerRunConfig(
                cache_mode="bypass",
                verbose=False
            )
            result = await crawler.arun(url=url, config=config)
            
            if not result.success:
                return f"Failed to crawl {url}: {result.error_message or 'Unknown error'}"
            
            if extract_content and result.markdown:
                # Return cleaned markdown content (truncated if too long)
                content = result.markdown[:4000] if len(result.markdown) > 4000 else result.markdown
                return f"Successfully crawled {url}:\n\n{content}"
            else:
                # Return basic info
                return f"Successfully crawled {url}:\n- Status: {result.status_code}\n- Content length: {len(result.html)} characters\n- Title: {getattr(result, 'title', 'N/A')}"
    
    except Exception as e:
        logger.error(f"Website crawling failed: {e}")
        return f"Website crawling failed: {str(e)}"

@tool
async def crawl_multiple_urls(urls: List[str]) -> str:
    """Crawl multiple URLs and aggregate the results"""
    if not CRAWL4AI_AVAILABLE:
        return "Crawl4AI is not available. Please install it with: pip install crawl4ai"
    
    try:
        results = []
        
        async with AsyncWebCrawler() as crawler:
            config = CrawlerRunConfig(
                cache_mode="bypass",
                verbose=False
            )
            
            for url in urls[:5]:  # Limit to 5 URLs to prevent timeout
                try:
                    result = await crawler.arun(url=url, config=config)
                    
                    if result.success and result.markdown:
                        content = result.markdown[:1500] if len(result.markdown) > 1500 else result.markdown
                        results.append(f"**{url}:**\n{content}\n")
                    else:
                        results.append(f"**{url}:** Failed to crawl\n")
                        
                except Exception as e:
                    results.append(f"**{url}:** Error - {str(e)}\n")
        
        return f"Crawled {len(urls)} URLs:\n\n" + "\n".join(results)
        
    except Exception as e:
        logger.error(f"Multiple URL crawling failed: {e}")
        return f"Multiple URL crawling failed: {str(e)}"

@tool
def research_topic_comprehensive(topic: str) -> str:
    """Conduct comprehensive research on a topic using multiple search strategies"""
    try:
        results = []
        
        # 1. General web search
        with DDGS() as ddgs:
            web_results = list(ddgs.text(f"{topic} overview guide", max_results=5))
            if web_results:
                results.append("**General Web Search Results:**")
                for result in web_results:
                    results.append(f"- {result.get('title', 'No title')}: {result.get('body', 'No description')}")
                results.append("")
        
        # 2. News search
        with DDGS() as ddgs:
            news_results = list(ddgs.news(f"{topic} latest news", max_results=3))
            if news_results:
                results.append("**Recent News:**")
                for result in news_results:
                    results.append(f"- {result.get('title', 'No title')} ({result.get('date', 'Unknown date')})")
                results.append("")
        
        # 3. Specific searches for different aspects
        aspects = ["best practices", "examples", "trends 2024", "guide"]
        for aspect in aspects:
            with DDGS() as ddgs:
                aspect_results = list(ddgs.text(f"{topic} {aspect}", max_results=2))
                if aspect_results:
                    results.append(f"**{aspect.title()} Search:**")
                    for result in aspect_results:
                        results.append(f"- {result.get('title', 'No title')}: {result.get('body', 'No description')[:200]}...")
                    results.append("")
        
        return f"Comprehensive research on '{topic}':\n\n" + "\n".join(results)
    except Exception as e:
        logger.error(f"Comprehensive research failed: {e}")
        return f"Comprehensive research failed: {str(e)}"

@tool
async def search_and_crawl(query: str, max_search_results: int = 3) -> str:
    """Search for URLs then crawl the top results for detailed content"""
    if not CRAWL4AI_AVAILABLE:
        return "Crawl4AI is not available. Please install it with: pip install crawl4ai"
    
    try:
        # First, search for relevant URLs
        with DDGS() as ddgs:
            search_results = list(ddgs.text(query, max_results=max_search_results))
        
        if not search_results:
            return f"No search results found for '{query}'"
        
        # Extract URLs
        urls = [result.get('href') for result in search_results if result.get('href')]
        
        if not urls:
            return f"No valid URLs found in search results for '{query}'"
        
        # Search summary
        results = [f"Search and crawl results for '{query}':\n"]
        results.append("=== SEARCH RESULTS ===\n")
        
        for i, result in enumerate(search_results, 1):
            title = result.get('title', 'No Title')
            url = result.get('href', 'No URL')
            body = result.get('body', 'No description')
            results.append(f"{i}. **{title}**\n   URL: {url}\n   Description: {body}\n")
        
        results.append("\n=== DETAILED CONTENT ===\n")
        
        # Crawl the URLs
        async with AsyncWebCrawler() as crawler:
            config = CrawlerRunConfig(
                cache_mode="bypass",
                verbose=False
            )
            
            for i, url in enumerate(urls, 1):
                try:
                    crawl_result = await crawler.arun(url=url, config=config)
                    if crawl_result.success and crawl_result.markdown:
                        content = crawl_result.markdown[:1500] if len(crawl_result.markdown) > 1500 else crawl_result.markdown
                        results.append(f"\n--- Content from {search_results[i-1].get('title', 'No title')} ---\n{content}\n")
                    else:
                        results.append(f"\n--- Failed to crawl {search_results[i-1].get('title', 'No title')} ---\n")
                except Exception as e:
                    results.append(f"\n--- Error crawling {search_results[i-1].get('title', 'No title')}: {str(e)} ---\n")
        
        return "\n".join(results)
        
    except Exception as e:
        logger.error(f"Search and crawl failed: {e}")
        return f"Search and crawl failed: {str(e)}"


def get_search_tools():
    """Get search-specific tools for the search worker"""
    search_tools = [
        duckduckgo_search,
        crawl_website
    ]

    return search_tools



async def get_nutritionist_tools(animal_type: str = "dairy_cow"):
    """Get nutritionist-specific tools"""
    # Add all formulation tools to nutritionist toolkit (includes add_feed, check_feeds, formulate_ration)
    formulation_tools = create_formulation_tools(animal_type)
    return formulation_tools + get_usda_tools() + [calculate]

async def get_coder_tools(animal_type: str = "dairy_cow"):
    """Get all available tools for a session (code worker tools)."""
    # Get file management tools
    file_tools = get_file_management_tools()

    # Get Excel tools
    excel_tools = get_excel_tools()

    # Get specific formulation tools for coder (add_feed, check_feeds, list_feed_bases only)
    all_formulation_tools = create_formulation_tools(animal_type)
    feed_tools = [tool for tool in all_formulation_tools if tool.name in ['add_feed', 'check_feeds', 'list_feed_bases']]

    usda_tools = get_usda_tools()

    return [bash_command, create_artifact] + file_tools + excel_tools + feed_tools + usda_tools
