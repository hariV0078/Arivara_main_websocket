"""
Helper functions for token tracking integration.
"""

from typing import Optional, Any


def get_token_tracker_from_kwargs(researcher=None, **kwargs) -> Optional[Any]:
    """
    Extract token_tracker from kwargs or researcher instance.
    
    This helper function checks:
    1. If token_tracker is directly in kwargs
    2. If researcher parameter is provided and has token_tracker attribute
    3. If researcher is in kwargs and has token_tracker attribute
    
    Args:
        researcher: Optional researcher instance (can be passed as parameter)
        **kwargs: Keyword arguments that may contain token_tracker or researcher
        
    Returns:
        TokenUsageTracker instance if found, None otherwise
    """
    # Check for direct token_tracker
    if 'token_tracker' in kwargs:
        return kwargs['token_tracker']
    
    # Check for researcher parameter first
    if researcher and hasattr(researcher, 'token_tracker'):
        return researcher.token_tracker
    
    # Check for researcher instance in kwargs
    if 'researcher' in kwargs:
        researcher_from_kwargs = kwargs['researcher']
        if researcher_from_kwargs and hasattr(researcher_from_kwargs, 'token_tracker'):
            return researcher_from_kwargs.token_tracker
    
    return None

