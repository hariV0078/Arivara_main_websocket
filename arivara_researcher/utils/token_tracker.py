"""
Centralized Token Usage Tracker for OpenAI API calls.

This module provides a thread-safe TokenUsageTracker class that records token usage
for every OpenAI API call and aggregates the total usage for a full report.
"""

import threading
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TokenUsage:
    """Data class for token usage information."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def to_dict(self) -> Dict[str, int]:
        """Convert to dictionary format."""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }

    def __add__(self, other: 'TokenUsage') -> 'TokenUsage':
        """Add two TokenUsage objects together."""
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )


# Alias for backward compatibility and user preference
TokenMeter = None  # Will be set below

class TokenUsageTracker:
    """
    Thread-safe token usage tracker that records token usage for every OpenAI API call.
    
    This tracker accumulates token usage across all API calls made during a report generation,
    supporting both sequential and async/concurrent execution patterns.
    
    Also known as TokenMeter (alias provided for user preference).
    
    Example:
        >>> tracker = TokenUsageTracker()
        >>> tracker.add(prompt_tokens=100, completion_tokens=200)
        >>> usage = tracker.summary()
        >>> print(f"Total tokens: {usage['total_tokens']}")
    """
    
    def __init__(self):
        """Initialize the token usage tracker."""
        self._lock = threading.Lock()
        self._prompt_tokens = 0
        self._completion_tokens = 0
        self._total_tokens = 0
        self._call_count = 0  # Track number of API calls
        
    def add(
        self,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: Optional[int] = None,
        usage: Optional[Dict[str, Any]] = None,
        usage_obj: Optional[Any] = None
    ) -> None:
        """
        Add token usage from an API call.
        
        Args:
            prompt_tokens: Number of prompt tokens (optional if usage/usage_obj provided)
            completion_tokens: Number of completion tokens (optional if usage/usage_obj provided)
            total_tokens: Total tokens (optional, will be calculated if not provided)
            usage: Dictionary with token usage information (e.g., {"prompt_tokens": 100, "completion_tokens": 200})
            usage_obj: Object with token usage attributes (e.g., response.usage from OpenAI)
            
        Examples:
            >>> tracker.add(prompt_tokens=100, completion_tokens=200)
            >>> tracker.add(usage={"prompt_tokens": 100, "completion_tokens": 200})
            >>> tracker.add(usage_obj=response.usage)
        """
        with self._lock:
            # Extract from usage_obj if provided (e.g., OpenAI response.usage)
            if usage_obj is not None:
                if hasattr(usage_obj, 'prompt_tokens'):
                    prompt_tokens = getattr(usage_obj, 'prompt_tokens', 0)
                if hasattr(usage_obj, 'completion_tokens'):
                    completion_tokens = getattr(usage_obj, 'completion_tokens', 0)
                if hasattr(usage_obj, 'total_tokens'):
                    total_tokens = getattr(usage_obj, 'total_tokens', None)
                # Also try dict-like access (for compatibility)
                elif hasattr(usage_obj, 'get'):
                    prompt_tokens = usage_obj.get('prompt_tokens', prompt_tokens)
                    completion_tokens = usage_obj.get('completion_tokens', completion_tokens)
                    total_tokens = usage_obj.get('total_tokens', total_tokens)
            
            # Extract from usage dict if provided
            elif usage is not None:
                prompt_tokens = usage.get('prompt_tokens', prompt_tokens)
                completion_tokens = usage.get('completion_tokens', completion_tokens)
                total_tokens = usage.get('total_tokens', total_tokens)
            
            # Ensure non-negative values
            prompt_tokens = max(0, int(prompt_tokens or 0))
            completion_tokens = max(0, int(completion_tokens or 0))
            
            # Calculate total if not provided
            if total_tokens is None:
                total_tokens = prompt_tokens + completion_tokens
            else:
                total_tokens = max(0, int(total_tokens))
            
            # Accumulate usage
            self._prompt_tokens += prompt_tokens
            self._completion_tokens += completion_tokens
            self._total_tokens += total_tokens
            self._call_count += 1
            
            logger.debug(
                f"TokenUsageTracker: Added usage - prompt: {prompt_tokens}, "
                f"completion: {completion_tokens}, total: {total_tokens} "
                f"(cumulative: {self._total_tokens})"
            )
    
    def reset(self) -> None:
        """Reset all counters for a new report run."""
        with self._lock:
            self._prompt_tokens = 0
            self._completion_tokens = 0
            self._total_tokens = 0
            self._call_count = 0
            logger.debug("TokenUsageTracker: Reset all counters")
    
    def summary(self) -> Dict[str, Any]:
        """
        Get summary of token usage.
        
        Returns:
            Dictionary with token usage totals:
            {
                "prompt_tokens": int,
                "completion_tokens": int,
                "total_tokens": int,
                "call_count": int
            }
        """
        with self._lock:
            return {
                "prompt_tokens": self._prompt_tokens,
                "completion_tokens": self._completion_tokens,
                "total_tokens": self._total_tokens,
                "call_count": self._call_count,
                # For backwards compatibility with existing code
                "total_prompt_tokens": self._prompt_tokens,
                "total_completion_tokens": self._completion_tokens,
            }
    
    @property
    def prompt_tokens(self) -> int:
        """Get total prompt tokens (read-only)."""
        with self._lock:
            return self._prompt_tokens
    
    @property
    def completion_tokens(self) -> int:
        """Get total completion tokens (read-only)."""
        with self._lock:
            return self._completion_tokens
    
    @property
    def total_tokens(self) -> int:
        """Get total tokens (read-only)."""
        with self._lock:
            return self._total_tokens
    
    @property
    def call_count(self) -> int:
        """Get number of API calls tracked (read-only)."""
        with self._lock:
            return self._call_count
    
    def __repr__(self) -> str:
        """String representation of the tracker."""
        return (
            f"TokenUsageTracker(prompt={self._prompt_tokens}, "
            f"completion={self._completion_tokens}, "
            f"total={self._total_tokens}, calls={self._call_count})"
        )


# Create alias for user preference (TokenMeter)
TokenMeter = TokenUsageTracker


