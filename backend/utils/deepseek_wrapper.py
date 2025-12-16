"""
DeepSeek Thinking Mode Compatibility Layer

This module provides compatibility fixes for DeepSeek's thinking mode with tool calls.

The issue: When using DeepSeek's thinking mode with tool calls, the API requires
`reasoning_content` from the assistant's response to be passed back in subsequent
requests within the same turn. LangChain's langchain-deepseek (v1.0.1) and 
langchain-openai don't handle this correctly.

See: https://github.com/langchain-ai/langchain/issues/34166
Reference: https://api-docs.deepseek.com/guides/thinking_mode#tool-calls

Solution: Monkey-patch the message conversion function in langchain-openai to
include `reasoning_content` when serializing AIMessages for DeepSeek API.

Usage:
    # Call this once at application startup (before creating models)
    from utils.deepseek_wrapper import apply_deepseek_thinking_patch
    apply_deepseek_thinking_patch()
"""

import os
import logging
from typing import Any

from langchain_core.messages import AIMessage

logger = logging.getLogger(__name__)

# Flag to track if patch has been applied
_PATCH_APPLIED = False

# Store reference to original function
_ORIGINAL_CONVERT_MESSAGE_TO_DICT = None


def apply_deepseek_thinking_patch() -> bool:
    """
    Apply monkey-patch to langchain-openai for DeepSeek thinking mode compatibility.
    
    This patches `_convert_message_to_dict` in langchain_openai.chat_models.base
    to include `reasoning_content` field when converting AIMessages.
    
    Returns:
        True if patch was applied (or already applied), False if patch failed.
    """
    global _PATCH_APPLIED, _ORIGINAL_CONVERT_MESSAGE_TO_DICT
    
    if _PATCH_APPLIED:
        logger.debug("DeepSeek thinking patch already applied")
        return True
    
    try:
        import langchain_openai.chat_models.base as openai_base
        
        # Store reference to original function
        _ORIGINAL_CONVERT_MESSAGE_TO_DICT = openai_base._convert_message_to_dict
        
        def _patched_convert_message_to_dict(
            message, 
            api="chat/completions"
        ) -> dict:
            """
            Patched version that includes reasoning_content for DeepSeek compatibility.
            """
            # Call original function
            result = _ORIGINAL_CONVERT_MESSAGE_TO_DICT(message, api=api)
            
            # Add reasoning_content for AIMessages if present
            if isinstance(message, AIMessage):
                additional_kwargs = getattr(message, 'additional_kwargs', {}) or {}
                reasoning_content = additional_kwargs.get('reasoning_content')
                
                if reasoning_content is not None:
                    result['reasoning_content'] = reasoning_content
                    logger.debug(f"Added reasoning_content to message dict (len={len(str(reasoning_content))})")
            
            return result
        
        # Apply the patch
        openai_base._convert_message_to_dict = _patched_convert_message_to_dict
        _PATCH_APPLIED = True
        
        logger.info("✓ DeepSeek thinking mode patch applied successfully")
        return True
        
    except Exception as e:
        logger.error(f"✗ Failed to apply DeepSeek thinking patch: {e}")
        return False


def clear_old_reasoning_content(messages: list) -> list:
    """
    Clear reasoning_content from messages in previous user turns.
    
    According to DeepSeek API docs, reasoning_content should be:
    - Preserved during tool-call loops within the same turn
    - Cleared/None when a new user turn begins (to save bandwidth)
    
    This function clears reasoning_content from AIMessages before the last HumanMessage.
    
    Args:
        messages: List of BaseMessage objects
        
    Returns:
        List with reasoning_content cleared from previous turns
    """
    if not messages:
        return messages
    
    # Find the last HumanMessage index
    last_human_idx = -1
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], (dict,)):
            if messages[i].get('role') == 'user' or messages[i].get('type') == 'human':
                last_human_idx = i
                break
        elif hasattr(messages[i], 'type') and messages[i].type == 'human':
            last_human_idx = i
            break
    
    if last_human_idx <= 0:
        # No HumanMessage found or it's the first message, return as-is
        return messages
    
    result = []
    for i, msg in enumerate(messages):
        if i < last_human_idx:
            # Clear reasoning_content from messages in previous turns
            if isinstance(msg, AIMessage):
                additional_kwargs = dict(getattr(msg, 'additional_kwargs', {}) or {})
                if 'reasoning_content' in additional_kwargs:
                    additional_kwargs['reasoning_content'] = None
                    # Create new message with cleared reasoning_content
                    msg = AIMessage(
                        content=msg.content,
                        additional_kwargs=additional_kwargs,
                        tool_calls=getattr(msg, 'tool_calls', []),
                        response_metadata=getattr(msg, 'response_metadata', {}),
                        id=msg.id,
                        name=getattr(msg, 'name', None),
                    )
            elif isinstance(msg, dict) and msg.get('role') == 'assistant':
                msg = dict(msg)
                if 'reasoning_content' in msg:
                    msg['reasoning_content'] = None
        result.append(msg)
    
    return result


def is_deepseek_direct() -> bool:
    """
    Check if we're using DeepSeek API directly (not via OpenRouter).
    
    Returns:
        True if OPENAI_ENDPOINT points to DeepSeek API
    """
    endpoint = os.getenv("OPENAI_ENDPOINT", "")
    return "api.deepseek.com" in endpoint


def should_apply_thinking_patch() -> bool:
    """
    Determine if the thinking patch should be applied based on configuration.
    
    Returns:
        True if using DeepSeek directly with a thinking-capable model
    """
    if not is_deepseek_direct():
        return False
    
    # Check if any model is a reasoner or thinking mode is enabled
    models = [
        os.getenv("NUTRITIONIST_MODEL", ""),
        os.getenv("RESEARCHER_MODEL", ""),
        os.getenv("CODER_MODEL", ""),
    ]
    
    for model in models:
        if model == "deepseek-reasoner":
            return True
    
    # Also apply if thinking mode is explicitly enabled for deepseek-chat
    if os.getenv("DEEPSEEK_THINKING_MODE", "false").lower() == "true":
        return True
    
    return False


def init_deepseek_compatibility():
    """
    Initialize DeepSeek compatibility patches if needed.
    
    Call this function at application startup to automatically apply
    necessary patches based on the current configuration.
    """
    if should_apply_thinking_patch():
        success = apply_deepseek_thinking_patch()
        if success:
            logger.info("DeepSeek thinking mode compatibility initialized")
        else:
            logger.warning("DeepSeek thinking mode compatibility failed to initialize")
    else:
        logger.debug("DeepSeek thinking patch not needed for current configuration")
