import os
import subprocess
import uuid
import json
from pathlib import Path
from typing import Optional, List, Annotated
from datetime import datetime
from langchain_core.tools import tool, InjectedToolCallId
from langchain_core.messages import ToolMessage
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from langchain_community.agent_toolkits import FileManagementToolkit
from duckduckgo_search import DDGS
from .excel_tools import get_excel_tools
from .formulation_tools import create_formulation_tools

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


async def bash_command(command: str, session_id: str) -> str:
    """Execute a bash command in the session workspace."""
    try:
        # Import here to avoid circular imports
        from services.session_manager import session_manager
        
        # Get session context
        session = await session_manager.get_session(session_id)
        if not session:
            return f"Error: Session '{session_id}' not found"
        
        # Ensure workspace exists and get path
        session.ensure_workspace_exists()
        session_workspace = session.workspace_path
        
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


def create_bash_command_tool(session_id: str):
    """Create a bash command tool bound to a specific session"""
    @tool
    async def bash_command_for_session(command: str) -> str:
        """Execute a bash command in the session workspace."""
        return await bash_command(command, session_id)
    
    return bash_command_for_session


# Artifact tools
async def create_html_artifact(
    html_content: str, 
    title: str, 
    description: Optional[str] = None,
    session_id: str = None
) -> str:
    """
    Create an HTML artifact that can be displayed in the frontend.
    
    Args:
        html_content: The HTML content to save as an artifact
        title: A title for the artifact
        description: Optional description of what the artifact contains
        session_id: Session ID for file storage (injected by tool creation)
    
    Returns:
        String with artifact info for the agent to reference
    """
    try:
        # Import here to avoid circular imports
        from services.session_manager import session_manager
        
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


def create_artifact_tool(session_id: str):
    """Create an artifact tool bound to a specific session"""
    
    @tool
    async def create_artifact(
        html_content: str, 
        title: str, 
        description: Optional[str] = None
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
        return await create_html_artifact(html_content, title, description, session_id)
    
    return create_artifact




async def get_file_management_tools(session_id: str):
    """Get file management tools for a specific session."""
    # Import here to avoid circular imports
    from services.session_manager import session_manager
    
    # Get session context
    session = await session_manager.get_session(session_id)
    if not session:
        raise RuntimeError(f"Session '{session_id}' not found")
    
    # Ensure workspace exists
    session.ensure_workspace_exists()
    
    # Create FileManagementToolkit with session-specific root directory
    file_toolkit = FileManagementToolkit(
        root_dir=session.workspace_path,
        selected_tools=["write_file", "list_directory"]
    )
    
    return file_toolkit.get_tools()


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



async def get_nutritionist_tools(session_id: str, animal_type: str = "dairy_cow"):
    """Get nutritionist-specific tools"""
    # Add all formulation tools to nutritionist toolkit (includes add_feed, check_feeds, formulate_ration)
    formulation_tools = create_formulation_tools(session_id, animal_type)

    return formulation_tools

async def get_coder_tools(session_id: str, animal_type: str = "dairy_cow"):
    """Get all available tools for a session (code worker tools)."""
    # Create session-bound bash tool
    session_bash_tool = create_bash_command_tool(session_id)

    # Get file management tools for the session
    file_tools = await get_file_management_tools(session_id)

    # Create session-bound artifact tool
    artifact_tool = create_artifact_tool(session_id)

    # Get Excel tools for the session
    excel_tools = await get_excel_tools(session_id)

    # Get specific formulation tools for coder (add_feed, check_feeds, list_feed_bases only)
    all_formulation_tools = create_formulation_tools(session_id, animal_type)
    feed_tools = [tool for tool in all_formulation_tools if tool.name in ['add_feed', 'check_feeds', 'list_feed_bases']]

    return [session_bash_tool, artifact_tool] + file_tools + excel_tools + feed_tools


async def get_tools(session_id: str):
    """Get all available tools for a session (code worker tools)."""
    # Create session-bound bash tool
    session_bash_tool = create_bash_command_tool(session_id)

    # Get file management tools for the session
    file_tools = await get_file_management_tools(session_id)

    # Create session-bound artifact tool
    artifact_tool = create_artifact_tool(session_id)

    # Get Excel tools for the session
    excel_tools = await get_excel_tools(session_id)

    return [session_bash_tool, artifact_tool] + file_tools + excel_tools