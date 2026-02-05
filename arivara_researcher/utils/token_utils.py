"""
Utility functions for extracting token usage from LLM responses.

This module provides helper functions to extract token usage information
from various response formats (LangChain AIMessage, OpenAI response, etc.).
"""

import logging
from typing import Any, Optional, Dict

logger = logging.getLogger(__name__)


def extract_token_usage_from_response(response: Any) -> Optional[Dict[str, int]]:
    """
    Extract token usage from various response types.
    
    This function handles:
    - LangChain AIMessage objects (with usage_metadata)
    - OpenAI response objects (with usage attribute)
    - Dictionary responses
    - Streaming response objects
    
    Args:
        response: Response object from LLM call
        
    Returns:
        Dictionary with token usage:
        {
            "prompt_tokens": int,
            "completion_tokens": int,
            "total_tokens": int
        }
        Returns None if usage cannot be extracted
    """
    if response is None:
        return None
    
    usage_dict = None
    
    # Try LangChain AIMessage format (usage_metadata)
    if hasattr(response, 'usage_metadata') and response.usage_metadata:
        usage_metadata = response.usage_metadata
        # LangChain uses input_tokens/output_tokens
        if isinstance(usage_metadata, dict):
            usage_dict = {
                "prompt_tokens": usage_metadata.get("input_tokens", 0),
                "completion_tokens": usage_metadata.get("output_tokens", 0),
                "total_tokens": usage_metadata.get("total_tokens", 0),
            }
        elif hasattr(usage_metadata, 'input_tokens'):
            usage_dict = {
                "prompt_tokens": getattr(usage_metadata, 'input_tokens', 0),
                "completion_tokens": getattr(usage_metadata, 'output_tokens', 0),
                "total_tokens": getattr(usage_metadata, 'total_tokens', 0),
            }
    
    # Try OpenAI format (usage attribute)
    if usage_dict is None and hasattr(response, 'usage'):
        usage = response.usage
        if usage is not None:
            if hasattr(usage, 'prompt_tokens'):
                usage_dict = {
                    "prompt_tokens": getattr(usage, 'prompt_tokens', 0),
                    "completion_tokens": getattr(usage, 'completion_tokens', 0),
                    "total_tokens": getattr(usage, 'total_tokens', 0),
                }
            elif isinstance(usage, dict):
                usage_dict = {
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                }
    
    # Try response_metadata (LangChain)
    if usage_dict is None and hasattr(response, 'response_metadata'):
        metadata = response.response_metadata
        if metadata and isinstance(metadata, dict):
            if 'token_usage' in metadata:
                token_usage = metadata['token_usage']
                if isinstance(token_usage, dict):
                    usage_dict = {
                        "prompt_tokens": token_usage.get("prompt_tokens", token_usage.get("input_tokens", 0)),
                        "completion_tokens": token_usage.get("completion_tokens", token_usage.get("output_tokens", 0)),
                        "total_tokens": token_usage.get("total_tokens", 0),
                    }
    
    # Try dictionary format
    if usage_dict is None and isinstance(response, dict):
        if 'usage' in response:
            usage = response['usage']
            if isinstance(usage, dict):
                usage_dict = {
                    "prompt_tokens": usage.get("prompt_tokens", usage.get("input_tokens", 0)),
                    "completion_tokens": usage.get("completion_tokens", usage.get("output_tokens", 0)),
                    "total_tokens": usage.get("total_tokens", 0),
                }
        elif 'token_usage' in response:
            token_usage = response['token_usage']
            if isinstance(token_usage, dict):
                usage_dict = {
                    "prompt_tokens": token_usage.get("prompt_tokens", token_usage.get("input_tokens", 0)),
                    "completion_tokens": token_usage.get("completion_tokens", token_usage.get("output_tokens", 0)),
                    "total_tokens": token_usage.get("total_tokens", 0),
                }
    
    # Validate usage_dict
    if usage_dict:
        # Ensure all values are non-negative integers
        usage_dict = {
            "prompt_tokens": max(0, int(usage_dict.get("prompt_tokens", 0))),
            "completion_tokens": max(0, int(usage_dict.get("completion_tokens", 0))),
            "total_tokens": max(0, int(usage_dict.get("total_tokens", 0))),
        }
        
        # Recalculate total if it doesn't match
        if usage_dict["total_tokens"] == 0:
            usage_dict["total_tokens"] = usage_dict["prompt_tokens"] + usage_dict["completion_tokens"]
        
        logger.debug(
            f"Extracted token usage: prompt={usage_dict['prompt_tokens']}, "
            f"completion={usage_dict['completion_tokens']}, "
            f"total={usage_dict['total_tokens']}"
        )
    
    return usage_dict


def extract_token_usage_from_streaming_response(
    response_obj: Any,
    accumulated_response: Optional[str] = None
) -> Optional[Dict[str, int]]:
    """
    Extract token usage from streaming response.
    
    For streaming responses, usage metadata might be in:
    - The final chunk
    - response_metadata after streaming completes
    - The response object itself
    
    Args:
        response_obj: Response object from streaming call (could be final chunk or response object)
        accumulated_response: Full accumulated response string (optional, for fallback estimation)
        
    Returns:
        Dictionary with token usage, or None if not available
    """
    # First try standard extraction
    usage_dict = extract_token_usage_from_response(response_obj)
    
    # If not found and we have accumulated_response, we could estimate
    # but we prefer actual usage data, so return None rather than estimate
    if usage_dict is None:
        logger.debug("Token usage not found in streaming response")
    
    return usage_dict


