import os
from langchain_openrouter import ChatOpenRouter


def get_model_config(model_name: str):
    """Get model configuration for different nodes
    
    Returns ChatOpenRouter configured for the appropriate model.
    
    ChatOpenRouter reads OPENROUTER_API_KEY from env automatically.
    For thinking/reasoning models, set THINKING_LEVEL=low|medium|high to enable reasoning output.
    """
    
    # Model and temperature mapping
    model_configs = {
        "nutritionist": {
            "model": os.getenv("NUTRITIONIST_MODEL", os.getenv("OPENROUTER_MODEL")),
            "temperature": float(os.getenv("NUTRITIONIST_TEMPERATURE", "0")),
            "streaming": True
        },
        "title_generation": {
            "model": os.getenv("TITLE_GENERATION_MODEL", os.getenv("OPENROUTER_MODEL")),
            "temperature": float(os.getenv("TITLE_GENERATION_TEMPERATURE", "0.3")),
            "streaming": False
        }
    }

    if model_name not in model_configs:
        raise ValueError(f"Unknown model name: {model_name}. Available: {list(model_configs.keys())}")
    
    config = model_configs[model_name]
    
    # Check thinking level (low | medium | high); anything else disables reasoning
    thinking_level = os.getenv("THINKING_LEVEL", "").lower()
    
    kwargs = {
        "model": config["model"],
        "temperature": config["temperature"],
        "streaming": config["streaming"],
        "max_tokens": 8192,
    }
    
    # Use native reasoning parameter for thinking models
    if thinking_level in ("low", "medium", "high"):
        kwargs["reasoning"] = {"effort": thinking_level}
    
    return ChatOpenRouter(**kwargs)


def get_agent_config() -> dict:
    """Get agent configuration including recursion limits"""
    return {
        "recursion_limit": int(os.getenv("LANGGRAPH_RECURSION_LIMIT", "100"))
    }