import asyncio
from typing import List, Dict, Any
from ..config.config import Config
from ..utils.llm import create_chat_completion
from ..utils.logger import get_formatted_logger
from ..prompts import PromptFamily, get_prompt_by_report_type
from ..utils.enum import Tone, ReportType

logger = get_formatted_logger()


def estimate_tokens(text: str) -> int:
    """
    Rough estimation of tokens (1 token ≈ 4 characters for English text).
    This is a conservative estimate to avoid token limit errors.
    """
    if not text:
        return 0
    # Rough estimate: 1 token ≈ 4 characters
    return len(text) // 4


def truncate_context_for_tokens(context: str, max_tokens: int = 20000) -> str:
    """
    Truncate context to stay within token limit.
    Keeps the beginning and end of context to preserve important information.
    
    Args:
        context: The context string to truncate
        max_tokens: Maximum tokens allowed (default 20000 to leave room for output)
    
    Returns:
        Truncated context string
    """
    if not context:
        return context
    
    estimated_tokens = estimate_tokens(context)
    
    if estimated_tokens <= max_tokens:
        return context
    
    # Truncate: keep first 40% and last 40% to preserve important info
    # This ensures we keep both introduction and conclusion
    target_chars = max_tokens * 4  # Convert tokens back to chars
    first_part = int(target_chars * 0.4)
    last_part = int(target_chars * 0.4)
    
    if len(context) <= target_chars:
        return context
    
    truncated = context[:first_part] + "\n\n[... Context truncated due to size limit ...]\n\n" + context[-last_part:]
    
    logger.warning(f"Context truncated: {estimated_tokens} tokens -> ~{estimate_tokens(truncated)} tokens (original length: {len(context)}, truncated: {len(truncated)})")
    
    return truncated


async def write_report_introduction(
    query: str,
    context: str,
    agent_role_prompt: str,
    config: Config,
    websocket=None,
    cost_callback: callable = None,
    prompt_family: type[PromptFamily] | PromptFamily = PromptFamily,
    **kwargs
) -> str:
    """
    Generate an introduction for the report.

    Args:
        query (str): The research query.
        context (str): Context for the report.
        role (str): The role of the agent.
        config (Config): Configuration object.
        websocket: WebSocket connection for streaming output.
        cost_callback (callable, optional): Callback for calculating LLM costs.
        prompt_family: Family of prompts

    Returns:
        str: The generated introduction.
    """
    try:
        introduction = await create_chat_completion(
            model=config.smart_llm_model,
            messages=[
                {"role": "system", "content": f"{agent_role_prompt}"},
                {"role": "user", "content": prompt_family.generate_report_introduction(
                    question=query,
                    research_summary=context,
                    language=config.language
                )},
            ],
            temperature=0.25,
            llm_provider=config.smart_llm_provider,
            stream=True,
            websocket=websocket,
            max_tokens=config.smart_token_limit,
            llm_kwargs=config.llm_kwargs,
            cost_callback=cost_callback,
            **kwargs
        )
        return introduction
    except Exception as e:
        logger.error(f"Error in generating report introduction: {e}")
    return ""


async def write_conclusion(
    query: str,
    context: str,
    agent_role_prompt: str,
    config: Config,
    websocket=None,
    cost_callback: callable = None,
    prompt_family: type[PromptFamily] | PromptFamily = PromptFamily,
    **kwargs
) -> str:
    """
    Write a conclusion for the report.

    Args:
        query (str): The research query.
        context (str): Context for the report.
        role (str): The role of the agent.
        config (Config): Configuration object.
        websocket: WebSocket connection for streaming output.
        cost_callback (callable, optional): Callback for calculating LLM costs.
        prompt_family: Family of prompts

    Returns:
        str: The generated conclusion.
    """
    try:
        conclusion = await create_chat_completion(
            model=config.smart_llm_model,
            messages=[
                {"role": "system", "content": f"{agent_role_prompt}"},
                {
                    "role": "user",
                    "content": prompt_family.generate_report_conclusion(query=query,
                                                                        report_content=context,
                                                                        language=config.language),
                },
            ],
            temperature=0.25,
            llm_provider=config.smart_llm_provider,
            stream=True,
            websocket=websocket,
            max_tokens=config.smart_token_limit,
            llm_kwargs=config.llm_kwargs,
            cost_callback=cost_callback,
            **kwargs
        )
        return conclusion
    except Exception as e:
        logger.error(f"Error in writing conclusion: {e}")
    return ""


async def summarize_url(
    url: str,
    content: str,
    role: str,
    config: Config,
    websocket=None,
    cost_callback: callable = None,
    **kwargs
) -> str:
    """
    Summarize the content of a URL.

    Args:
        url (str): The URL to summarize.
        content (str): The content of the URL.
        role (str): The role of the agent.
        config (Config): Configuration object.
        websocket: WebSocket connection for streaming output.
        cost_callback (callable, optional): Callback for calculating LLM costs.

    Returns:
        str: The summarized content.
    """
    try:
        summary = await create_chat_completion(
            model=config.smart_llm_model,
            messages=[
                {"role": "system", "content": f"{role}"},
                {"role": "user", "content": f"Summarize the following content from {url}:\n\n{content}"},
            ],
            temperature=0.25,
            llm_provider=config.smart_llm_provider,
            stream=True,
            websocket=websocket,
            max_tokens=config.smart_token_limit,
            llm_kwargs=config.llm_kwargs,
            cost_callback=cost_callback,
            **kwargs
        )
        return summary
    except Exception as e:
        logger.error(f"Error in summarizing URL: {e}")
    return ""


async def generate_draft_section_titles(
    query: str,
    current_subtopic: str,
    context: str,
    role: str,
    config: Config,
    websocket=None,
    cost_callback: callable = None,
    prompt_family: type[PromptFamily] | PromptFamily = PromptFamily,
    **kwargs
) -> List[str]:
    """
    Generate draft section titles for the report.

    Args:
        query (str): The research query.
        context (str): Context for the report.
        role (str): The role of the agent.
        config (Config): Configuration object.
        websocket: WebSocket connection for streaming output.
        cost_callback (callable, optional): Callback for calculating LLM costs.
        prompt_family: Family of prompts

    Returns:
        List[str]: A list of generated section titles.
    """
    try:
        section_titles = await create_chat_completion(
            model=config.smart_llm_model,
            messages=[
                {"role": "system", "content": f"{role}"},
                {"role": "user", "content": prompt_family.generate_draft_titles_prompt(
                    current_subtopic, query, context)},
            ],
            temperature=0.25,
            llm_provider=config.smart_llm_provider,
            stream=True,
            websocket=None,
            max_tokens=config.smart_token_limit,
            llm_kwargs=config.llm_kwargs,
            cost_callback=cost_callback,
            **kwargs
        )
        return section_titles.split("\n")
    except Exception as e:
        logger.error(f"Error in generating draft section titles: {e}")
    return []


async def generate_report(
    query: str,
    context,
    agent_role_prompt: str,
    report_type: str,
    tone: Tone,
    report_source: str,
    websocket,
    cfg,
    main_topic: str = "",
    existing_headers: list = [],
    relevant_written_contents: list = [],
    cost_callback: callable = None,
    custom_prompt: str = "", # This can be any prompt the user chooses with the context
    headers=None,
    prompt_family: type[PromptFamily] | PromptFamily = PromptFamily,
    **kwargs
):
    """
    generates the final report
    Args:
        query:
        context:
        agent_role_prompt:
        report_type:
        websocket:
        tone:
        cfg:
        main_topic:
        existing_headers:
        relevant_written_contents:
        cost_callback:
        prompt_family: Family of prompts

    Returns:
        report:

    """
    import logging
    report_logger = logging.getLogger(__name__)
    
    # Truncate context if it's too large to avoid token limit errors
    # For deep research, allow much more context to generate comprehensive 20+ page reports
    if isinstance(context, str):
        original_context_length = len(context)
        estimated_context_tokens = estimate_tokens(context)
        
        # For deep research, use moderate context limit to avoid rate limits
        # Reduce context size to prevent hitting rate limits while still maintaining quality
        if report_type == "deep" or report_type == ReportType.DeepResearch.value:
            max_context_tokens = 35000  # Reduced from 50k to 35k to avoid rate limits (50k + 16k output = 66k was too close to limits)
            if estimated_context_tokens > max_context_tokens:
                report_logger.warning(f"Deep research context very large ({estimated_context_tokens} tokens), truncating to {max_context_tokens} to avoid rate limits...")
                context = truncate_context_for_tokens(context, max_tokens=max_context_tokens)
                if websocket:
                    try:
                        await websocket.send_json({
                            "type": "logs",
                            "content": "context_truncated",
                            "output": f"⚠️ Deep research context was very large ({estimated_context_tokens} tokens). Truncated to {max_context_tokens} tokens to prevent rate limits while ensuring comprehensive report generation."
                        })
                    except:
                        pass
            else:
                report_logger.info(f"Deep research context size: {estimated_context_tokens} tokens (within {max_context_tokens} limit)")
        else:
            # For regular reports, use lower limit
            max_context_tokens = 20000
            if estimated_context_tokens > max_context_tokens:
                report_logger.warning(f"Context too large ({estimated_context_tokens} tokens), truncating to avoid rate limit...")
                context = truncate_context_for_tokens(context, max_tokens=max_context_tokens)
                if websocket:
                    try:
                        await websocket.send_json({
                            "type": "logs",
                            "content": "context_truncated",
                            "output": f"⚠️ Context was very large ({estimated_context_tokens} tokens). Truncated to fit within API limits."
                        })
                    except:
                        pass
    
    generate_prompt = get_prompt_by_report_type(report_type, prompt_family)
    report = ""

    # Use higher word count for deep research to ensure comprehensive reports (16-20 pages)
    total_words = cfg.total_words
    if report_type == "deep" or report_type == ReportType.DeepResearch.value:
        # Deep research should have comprehensive reports (target: 16-20 pages)
        # 16-20 pages ≈ 8,000-10,000 words (assuming 500 words per page with formatting)
        # Set to 18,000 words to ensure we reach 16-20 pages (accounting for formatting, headers, etc.)
        total_words = 18000  # 18,000 words for 16-20 page comprehensive reports
        report_logger.info(f"Using enhanced word count for deep research: {total_words} words - targeting 16-20 pages (500 words per page)")

    if report_type == "subtopic_report":
        content = f"{generate_prompt(query, existing_headers, relevant_written_contents, main_topic, context, report_format=cfg.report_format, tone=tone, total_words=total_words, language=cfg.language)}"
    elif custom_prompt:
        content = f"{custom_prompt}\n\nContext: {context}"
    else:
        content = f"{generate_prompt(query, context, report_source, report_format=cfg.report_format, tone=tone, total_words=total_words, language=cfg.language)}"
    
    # Estimate total tokens for the request and adjust max_tokens if needed
    estimated_input_tokens = estimate_tokens(content) + estimate_tokens(agent_role_prompt)
    
    # For deep research, use maximum output tokens to allow for comprehensive reports (targeting 16-20 pages)
    if report_type == "deep" or report_type == ReportType.DeepResearch.value:
        # GPT-4o max output limit is 16,384 tokens (approximately 6,500 words)
        # While this is less than the 18,000 word target, we use the maximum to get the most comprehensive report possible
        # The prompt will emphasize using the full token budget and being as detailed as possible
        max_output_tokens = 16384  # Use 16k tokens (GPT-4o max output) - approximately 6,500 words / 13+ pages
        report_logger.info(f"Deep research: Using max_output_tokens={max_output_tokens} (GPT-4o max output limit) to maximize report comprehensiveness (target: 16-20 pages, will use full token budget)")
    else:
        max_output_tokens = cfg.smart_token_limit
        # Adjust max_tokens based on input size to avoid hitting rate limits
        if estimated_input_tokens > 20000:
            max_output_tokens = min(cfg.smart_token_limit, 8000)
            report_logger.warning(f"Large input detected ({estimated_input_tokens} tokens), reducing max_output_tokens to {max_output_tokens}")
        elif estimated_input_tokens > 15000:
            max_output_tokens = min(cfg.smart_token_limit, 10000)
            report_logger.info(f"Moderate input size ({estimated_input_tokens} tokens), reducing max_output_tokens to {max_output_tokens}")
    
    # Extract token_tracker from kwargs or cost_callback's researcher if available
    from ..utils.token_helpers import get_token_tracker_from_kwargs
    token_tracker = get_token_tracker_from_kwargs(**kwargs)
    
    try:
        report = await create_chat_completion(
            model=cfg.smart_llm_model,
            messages=[
                {"role": "system", "content": f"{agent_role_prompt}"},
                {"role": "user", "content": content},
            ],
            temperature=0.35,
            llm_provider=cfg.smart_llm_provider,
            stream=True,
            websocket=websocket,
            max_tokens=max_output_tokens,
            llm_kwargs=cfg.llm_kwargs,
            cost_callback=cost_callback,
            token_tracker=token_tracker,
            **kwargs
        )
    except Exception as e1:
        error_str = str(e1)
        # Check if it's a rate limit error
        is_rate_limit = (
            "rate_limit" in error_str.lower() or 
            "429" in error_str or 
            "tokens per min" in error_str.lower() or 
            "too large" in error_str.lower() or
            "too many requests" in error_str.lower()
        )
        
        if is_rate_limit:
            report_logger.error(f"Rate limit error in generate_report (first attempt): {e1}")
            # Send user-friendly error message
            if websocket:
                try:
                    await websocket.send_json({
                        "type": "error",
                        "code": "RATE_LIMIT_ERROR",
                        "message": "API rate limit exceeded. The report generation may be incomplete. Please try again in a moment.",
                        "details": str(e1)
                    })
                except:
                    pass
            # Try alternative format, but if that also fails, return empty string
            try:
                report = await create_chat_completion(
                    model=cfg.smart_llm_model,
                    messages=[
                        {"role": "user", "content": f"{agent_role_prompt}\n\n{content}"},
                    ],
                    temperature=0.35,
                    llm_provider=cfg.smart_llm_provider,
                    stream=True,
                    websocket=websocket,
                    max_tokens=max_output_tokens,
                    llm_kwargs=cfg.llm_kwargs,
                    cost_callback=cost_callback,
                    token_tracker=token_tracker,
                    **kwargs
                )
            except Exception as e2:
                report_logger.error(f"Rate limit error in generate_report (second attempt): {e2}")
                if websocket:
                    try:
                        await websocket.send_json({
                            "type": "error",
                            "code": "RATE_LIMIT_ERROR",
                            "message": "Unable to generate report due to API rate limits. Please try again in a moment or use a more specific query.",
                            "details": str(e2)
                        })
                    except:
                        pass
                # Return empty string if both attempts fail
                report = ""
        else:
            # Not a rate limit error, try alternative format
            try:
                report = await create_chat_completion(
                    model=cfg.smart_llm_model,
                    messages=[
                        {"role": "user", "content": f"{agent_role_prompt}\n\n{content}"},
                    ],
                    temperature=0.35,
                    llm_provider=cfg.smart_llm_provider,
                    stream=True,
                    websocket=websocket,
                    max_tokens=max_output_tokens,
                    llm_kwargs=cfg.llm_kwargs,
                    cost_callback=cost_callback,
                    **kwargs
                )
            except Exception as e2:
                report_logger.error(f"Error in generate_report (both attempts failed): {e2}", exc_info=True)
                report = ""

    return report
