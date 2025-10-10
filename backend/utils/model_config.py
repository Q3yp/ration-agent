import os
from langchain_openai import ChatOpenAI


def get_model_config(model_name: str) -> ChatOpenAI:
    """Get model configuration for different nodes"""
    
    # Model and temperature mapping
    model_configs = {
        "nutritionist": {
            "model": os.getenv("NUTRITIONIST_MODEL", os.getenv("OPENROUTER_MODEL")),
            "temperature": float(os.getenv("NUTRITIONIST_TEMPERATURE", "0")),
            "streaming": True
        },
        "researcher": {
            "model": os.getenv("RESEARCHER_MODEL", os.getenv("OPENROUTER_MODEL")),
            "temperature": float(os.getenv("RESEARCHER_TEMPERATURE", "0")),
            "streaming": True
        },
        "coder": {
            "model": os.getenv("CODER_MODEL", os.getenv("OPENROUTER_MODEL")),
            "temperature": float(os.getenv("CODER_TEMPERATURE", "0")),
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
    
    return ChatOpenAI(
        model=config["model"],
        temperature=config["temperature"],
        streaming=config["streaming"],
        #openai_api_base="https://openrouter.ai/api/v1",
        max_tokens=4000,
        openai_api_base=os.getenv("OPENAI_ENDPOINT"),
        openai_api_key=os.getenv("OPENROUTER_API_KEY"),
        stream_usage=True  # Enable token usage tracking in response metadata
    )


def get_agent_config() -> dict:
    """Get agent configuration including recursion limits"""
    return {
        "recursion_limit": int(os.getenv("LANGGRAPH_RECURSION_LIMIT", "100"))
    }