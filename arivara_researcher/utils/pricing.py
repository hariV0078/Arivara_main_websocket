"""
Pricing configuration for OpenAI and other LLM models.

This module provides pricing information per 1k tokens for various models,
used for calculating costs from token usage.
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Pricing per 1k tokens (input/output)
# Format: {model_name: {"prompt": price_per_1k, "completion": price_per_1k}}
# Prices are in USD
PRICING_CONFIG: Dict[str, Dict[str, float]] = {
    # GPT-4 models
    "gpt-4": {"prompt": 0.03, "completion": 0.06},
    "gpt-4-32k": {"prompt": 0.06, "completion": 0.12},
    "gpt-4-turbo": {"prompt": 0.01, "completion": 0.03},
    "gpt-4-turbo-preview": {"prompt": 0.01, "completion": 0.03},
    "gpt-4o": {"prompt": 0.0025, "completion": 0.01},
    "gpt-4o-mini": {"prompt": 0.00015, "completion": 0.0006},
    
    # GPT-3.5 models
    "gpt-3.5-turbo": {"prompt": 0.0015, "completion": 0.002},
    "gpt-3.5-turbo-16k": {"prompt": 0.003, "completion": 0.004},
    
    # O1/O3/O4 models (OpenAI reasoning models)
    "o1-preview": {"prompt": 0.015, "completion": 0.06},
    "o1-mini": {"prompt": 0.003, "completion": 0.012},
    "o3-mini": {"prompt": 0.0005, "completion": 0.002},
    "o4": {"prompt": 0.0025, "completion": 0.01},
    "o4-mini": {"prompt": 0.0005, "completion": 0.002},
    
    # Default fallback (average of common models)
    "default": {"prompt": 0.002, "completion": 0.005},
}

# Model name normalization map (to handle variations like "openai:gpt-4o")
MODEL_NORMALIZATION: Dict[str, str] = {
    # OpenAI provider prefix
    "openai:gpt-4": "gpt-4",
    "openai:gpt-4-32k": "gpt-4-32k",
    "openai:gpt-4-turbo": "gpt-4-turbo",
    "openai:gpt-4-turbo-preview": "gpt-4-turbo-preview",
    "openai:gpt-4o": "gpt-4o",
    "openai:gpt-4o-mini": "gpt-4o-mini",
    "openai:gpt-3.5-turbo": "gpt-3.5-turbo",
    "openai:gpt-3.5-turbo-16k": "gpt-3.5-turbo-16k",
    "openai:o1-preview": "o1-preview",
    "openai:o1-mini": "o1-mini",
    "openai:o3-mini": "o3-mini",
    "openai:o4": "o4",
    "openai:o4-mini": "o4-mini",
}


def normalize_model_name(model_name: str) -> str:
    """
    Normalize model name to match pricing config.
    
    Args:
        model_name: Model name (e.g., "openai:gpt-4o" or "gpt-4o-mini")
        
    Returns:
        Normalized model name (e.g., "gpt-4o")
    """
    if not model_name:
        return "default"
    
    model_name = str(model_name).strip().lower()
    
    # Check normalization map first
    if model_name in MODEL_NORMALIZATION:
        return MODEL_NORMALIZATION[model_name]
    
    # Remove common prefixes
    prefixes = ["openai:", "anthropic:", "google:", "cohere:", "huggingface:"]
    for prefix in prefixes:
        if model_name.startswith(prefix):
            model_name = model_name[len(prefix):]
            break
    
    # Extract base model name (handle versions like "gpt-4o-2024-08-06")
    # Split by "-" and take first meaningful parts
    parts = model_name.split("-")
    if len(parts) >= 2:
        # Try common patterns: "gpt-4o", "gpt-3.5-turbo", etc.
        if parts[0] == "gpt" and len(parts) >= 2:
            if parts[1].startswith("4"):
                # GPT-4 variants
                if len(parts) >= 3 and parts[2] in ["turbo", "32k", "o"]:
                    base = f"{parts[0]}-{parts[1]}-{parts[2]}"
                    if len(parts) >= 4 and parts[3] in ["mini", "preview"]:
                        base = f"{base}-{parts[3]}"
                    if base in PRICING_CONFIG:
                        return base
                elif parts[1] == "4":
                    if len(parts) >= 3 and parts[2] in ["turbo", "32k", "o"]:
                        base = f"{parts[0]}-{parts[1]}-{parts[2]}"
                        if base in PRICING_CONFIG:
                            return base
                base = f"{parts[0]}-{parts[1]}"
                if base in PRICING_CONFIG:
                    return base
            elif parts[1].startswith("3"):
                # GPT-3.5 variants
                if len(parts) >= 3:
                    base = f"{parts[0]}-{parts[1]}-{parts[2]}"
                    if base in PRICING_CONFIG:
                        return base
        elif parts[0] in ["o1", "o3", "o4"]:
            # O-series models
            if len(parts) >= 2:
                base = f"{parts[0]}-{parts[1]}"
                if base in PRICING_CONFIG:
                    return base
            base = parts[0]
            if base in PRICING_CONFIG:
                return base
    
    # Check if exact match exists
    if model_name in PRICING_CONFIG:
        return model_name
    
    # Return normalized name for logging, but use default pricing
    return model_name


def get_pricing(model_name: str) -> Dict[str, float]:
    """
    Get pricing information for a model.
    
    Args:
        model_name: Model name (e.g., "gpt-4o" or "openai:gpt-4o-mini")
        
    Returns:
        Dictionary with "prompt" and "completion" prices per 1k tokens
    """
    normalized = normalize_model_name(model_name)
    
    if normalized in PRICING_CONFIG:
        return PRICING_CONFIG[normalized]
    
    # Fallback to default pricing
    logger.warning(
        f"Unknown model '{model_name}' (normalized: '{normalized}'). "
        f"Using default pricing. Please add pricing to PRICING_CONFIG."
    )
    return PRICING_CONFIG["default"]


def calculate_cost(
    prompt_tokens: int,
    completion_tokens: int,
    model_name: str
) -> float:
    """
    Calculate cost in USD based on token usage and model.
    
    Args:
        prompt_tokens: Number of prompt tokens
        completion_tokens: Number of completion tokens
        model_name: Model name (e.g., "gpt-4o")
        
    Returns:
        Cost in USD (float)
    """
    pricing = get_pricing(model_name)
    
    prompt_cost = (prompt_tokens / 1000.0) * pricing["prompt"]
    completion_cost = (completion_tokens / 1000.0) * pricing["completion"]
    
    total_cost = prompt_cost + completion_cost
    
    return total_cost


def calculate_cost_from_usage(
    token_usage: Dict[str, int],
    model_name: str
) -> float:
    """
    Calculate cost from token usage dictionary.
    
    Args:
        token_usage: Dictionary with token usage information
            Expected keys: "prompt_tokens" or "total_prompt_tokens",
                          "completion_tokens" or "total_completion_tokens"
        model_name: Model name (e.g., "gpt-4o")
        
    Returns:
        Cost in USD (float)
    """
    prompt_tokens = token_usage.get("prompt_tokens") or token_usage.get("total_prompt_tokens", 0)
    completion_tokens = token_usage.get("completion_tokens") or token_usage.get("total_completion_tokens", 0)
    
    return calculate_cost(prompt_tokens, completion_tokens, model_name)


