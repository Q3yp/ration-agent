from langchain_core.tools import tool
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_community.utilities import DuckDuckGoSearchAPIWrapper


def get_search_tools():
    """Get search-specific tools for the search worker"""
    
    @tool
    def web_search(query: str) -> str:
        """Search the web for information using DuckDuckGo"""
        try:
            search = DuckDuckGoSearchRun(api_wrapper=DuckDuckGoSearchAPIWrapper())
            results = search.run(query)
            return f"Search results for '{query}':\n{results}"
        except Exception as e:
            return f"Search failed: {str(e)}"
    
    @tool
    def research_topic(topic: str) -> str:
        """Conduct comprehensive research on a specific topic"""
        try:
            search = DuckDuckGoSearchRun(api_wrapper=DuckDuckGoSearchAPIWrapper())
            
            # Perform multiple searches for comprehensive coverage
            queries = [
                f"{topic} overview",
                f"{topic} best practices",
                f"{topic} latest trends 2024",
                f"{topic} examples"
            ]
            
            results = []
            for query in queries:
                try:
                    result = search.run(query)
                    results.append(f"=== {query} ===\n{result}\n")
                except:
                    continue
            
            return f"Comprehensive research on '{topic}':\n\n" + "\n".join(results)
        except Exception as e:
            return f"Research failed: {str(e)}"
    
    return [web_search, research_topic]