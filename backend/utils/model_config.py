import os
from langchain_openai import ChatOpenAI


def get_model_config(model_name: str):
    """Get model configuration for different nodes
    
    Returns ChatDeepSeek if using DeepSeek models directly, otherwise ChatOpenAI.
    
    For DeepSeek thinking mode:
    - deepseek-reasoner: Always in thinking mode, no extra config needed
    - deepseek-chat + DEEPSEEK_THINKING_MODE=true: Enables thinking for V3.2
    """
    
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
    endpoint = os.getenv("OPENAI_ENDPOINT", "")
    model = config["model"]
    
    # Check if using DeepSeek API directly (not OpenRouter)
    is_deepseek_direct = "api.deepseek.com" in endpoint
    
    if is_deepseek_direct:
        # Use ChatDeepSeek for direct DeepSeek API access
        from langchain_deepseek import ChatDeepSeek
        
        # Check if this is the reasoner model (always thinking, no extra params needed)
        is_reasoner = model == "deepseek-reasoner"
        
        # For deepseek-chat, check if thinking mode should be enabled
        enable_thinking_for_chat = (
            not is_reasoner and 
            os.getenv("DEEPSEEK_THINKING_MODE", "false").lower() == "true"
        )
        
        # Build kwargs
        kwargs = {
            "model": model,
            "streaming": config["streaming"],
            "max_tokens": 8192,  # DeepSeek max is 8192
            "api_key": os.getenv("OPENROUTER_API_KEY"),  # Reusing for DeepSeek API key
        }
        
        # Reasoner ignores temperature, don't pass it
        if not is_reasoner:
            kwargs["temperature"] = config["temperature"]
            # Only pass thinking param for deepseek-chat when explicitly enabled
            if enable_thinking_for_chat:
                kwargs["thinking"] = {"type": "enabled"}
        
        return ChatDeepSeek(**kwargs)
    else:
        # Use ChatOpenAI for OpenRouter or other OpenAI-compatible endpoints
        return ChatOpenAI(
            model=model,
            temperature=config["temperature"],
            streaming=config["streaming"],
            max_tokens=4000,
            openai_api_base=endpoint,
            openai_api_key=os.getenv("OPENROUTER_API_KEY"),
            stream_usage=True  # Enable token usage tracking in response metadata
        )


def get_agent_config() -> dict:
    """Get agent configuration including recursion limits"""
    return {
        "recursion_limit": int(os.getenv("LANGGRAPH_RECURSION_LIMIT", "100"))
    }