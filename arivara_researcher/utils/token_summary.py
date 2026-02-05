"""
Token usage summary formatting and output utilities.
"""

import logging
from typing import Dict, Any, Optional
from .pricing import calculate_cost_from_usage
from .token_tracker import TokenUsageTracker

logger = logging.getLogger(__name__)


def format_token_summary(
    token_usage: Dict[str, Any],
    model_name: Optional[str] = None,
    include_cost: bool = True
) -> str:
    """
    Format token usage summary as a formatted string.
    
    Args:
        token_usage: Dictionary with token usage information
        model_name: Optional model name for cost calculation
        include_cost: Whether to include cost calculation
        
    Returns:
        Formatted string with token usage summary
    """
    prompt_tokens = token_usage.get("prompt_tokens") or token_usage.get("total_prompt_tokens", 0)
    completion_tokens = token_usage.get("completion_tokens") or token_usage.get("total_completion_tokens", 0)
    total_tokens = token_usage.get("total_tokens", prompt_tokens + completion_tokens)
    call_count = token_usage.get("call_count", 0)
    
    # Format with commas
    prompt_tokens_str = f"{prompt_tokens:,}"
    completion_tokens_str = f"{completion_tokens:,}"
    total_tokens_str = f"{total_tokens:,}"
    
    lines = [
        "─" * 50,
        "📊 Token Usage Summary (Report Run)",
        "─" * 50,
        f"Prompt Tokens:      {prompt_tokens_str:>15}",
        f"Completion Tokens:  {completion_tokens_str:>15}",
        f"Total Tokens:        {total_tokens_str:>15}",
        f"API Calls:           {call_count:>15,}",
    ]
    
    if include_cost and model_name:
        try:
            cost = calculate_cost_from_usage(token_usage, model_name)
            lines.append(f"Estimated Cost:     ${cost:>14.4f}")
        except Exception as e:
            logger.debug(f"Could not calculate cost: {e}")
            lines.append("Estimated Cost:     (unavailable)")
    
    lines.append("─" * 50)
    
    return "\n".join(lines)


def format_token_summary_markdown(
    token_usage: Dict[str, Any],
    model_name: Optional[str] = None,
    include_cost: bool = True
) -> str:
    """
    Format token usage summary as markdown.
    
    Args:
        token_usage: Dictionary with token usage information
        model_name: Optional model name for cost calculation
        include_cost: Whether to include cost calculation
        
    Returns:
        Formatted markdown string with token usage summary
    """
    prompt_tokens = token_usage.get("prompt_tokens") or token_usage.get("total_prompt_tokens", 0)
    completion_tokens = token_usage.get("completion_tokens") or token_usage.get("total_completion_tokens", 0)
    total_tokens = token_usage.get("total_tokens", prompt_tokens + completion_tokens)
    call_count = token_usage.get("call_count", 0)
    
    lines = [
        "## 📊 Token Usage Report",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Prompt Tokens | {prompt_tokens:,} |",
        f"| Completion Tokens | {completion_tokens:,} |",
        f"| Total Tokens | {total_tokens:,} |",
        f"| API Calls | {call_count:,} |",
    ]
    
    if include_cost and model_name:
        try:
            cost = calculate_cost_from_usage(token_usage, model_name)
            lines.append(f"| Estimated Cost | ${cost:.4f} |")
        except Exception as e:
            logger.debug(f"Could not calculate cost: {e}")
            lines.append("| Estimated Cost | (unavailable) |")
    
    lines.append("")
    
    return "\n".join(lines)


def print_token_summary(
    token_usage: Dict[str, Any],
    model_name: Optional[str] = None,
    include_cost: bool = True
) -> None:
    """
    Print token usage summary to console/logs.
    
    This function formats and prints the token usage summary in a clean format,
    integrating with the existing logging system.
    
    Args:
        token_usage: Dictionary with token usage information
        model_name: Optional model name for cost calculation
        include_cost: Whether to include cost calculation
    """
    summary = format_token_summary(token_usage, model_name, include_cost)
    logger.info(f"\n{summary}\n")
    # Also print to console for visibility
    print(f"\n{summary}\n")


