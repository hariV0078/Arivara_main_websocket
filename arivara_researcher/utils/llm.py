# libraries
from __future__ import annotations

import logging
from typing import Any

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate

from arivara_researcher.llm_provider.generic.base import NO_SUPPORT_TEMPERATURE_MODELS, SUPPORT_REASONING_EFFORT_MODELS, ReasoningEfforts

from ..prompts import PromptFamily
from .costs import estimate_llm_cost
from .validators import Subtopics
import os


def get_llm(llm_provider, **kwargs):
    from arivara_researcher.llm_provider import GenericLLMProvider
    return GenericLLMProvider.from_provider(llm_provider, **kwargs)


async def create_chat_completion(
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float | None = 0.4,
        max_tokens: int | None = 4000,
        llm_provider: str | None = None,
        stream: bool = False,
        websocket: Any | None = None,
        llm_kwargs: dict[str, Any] | None = None,
        cost_callback: callable = None,
        reasoning_effort: str | None = ReasoningEfforts.Medium.value,
        token_tracker: Any = None,
        **kwargs
) -> str:
    """Create a chat completion using the OpenAI API
    
    Args:
        messages (list[dict[str, str]]): The messages to send to the chat completion.
        model (str, optional): The model to use. Defaults to None.
        temperature (float, optional): The temperature to use. Defaults to 0.4.
        max_tokens (int, optional): The max tokens to use. Defaults to 4000.
        llm_provider (str, optional): The LLM Provider to use.
        stream (bool): Whether to stream the response. Defaults to False.
        webocket (WebSocket): The websocket used in the currect request,
        llm_kwargs (dict[str, Any], optional): Additional LLM keyword arguments. Defaults to None.
        cost_callback: Callback function for updating cost.
        reasoning_effort (str, optional): Reasoning effort for OpenAI's reasoning models. Defaults to 'low'.
        token_tracker: Optional TokenUsageTracker instance to track token usage.
        **kwargs: Additional keyword arguments.
    Returns:
        str: The response from the chat completion.
    """
    # validate input
    if model is None:
        raise ValueError("Model cannot be None")
    # Allow up to 32k tokens for deep research (GPT-4 supports up to 16k, but some models support more)
    # The check was > 32001 which allows up to 32k, but error message said 16k - updating to be consistent
    if max_tokens is not None and max_tokens > 32000:
        raise ValueError(
            f"Max tokens cannot be more than 32,000, but got {max_tokens}")

    # Get the provider from supported providers
    provider_kwargs = {'model': model}

    if llm_kwargs:
        provider_kwargs.update(llm_kwargs)

    if model in SUPPORT_REASONING_EFFORT_MODELS:
        provider_kwargs['reasoning_effort'] = reasoning_effort

    if model not in NO_SUPPORT_TEMPERATURE_MODELS:
        provider_kwargs['temperature'] = temperature
        provider_kwargs['max_tokens'] = max_tokens
    else:
        provider_kwargs['temperature'] = None
        provider_kwargs['max_tokens'] = None

    if llm_provider == "openai":
        base_url = os.environ.get("OPENAI_BASE_URL", None)
        if base_url:
            provider_kwargs['openai_api_base'] = base_url

    provider = get_llm(llm_provider, **provider_kwargs)
    response = ""
    
    # Log websocket status for debugging
    if stream and websocket is None:
        logging.warning("create_chat_completion: stream=True but websocket=None - report will not be streamed")
    elif stream and websocket is not None:
        logging.info(f"create_chat_completion: stream=True, websocket type={type(websocket).__name__}")
    
    # create response
    for _ in range(10):  # maximum of 10 attempts
        response = await provider.get_chat_response(
            messages, stream, websocket, token_tracker=token_tracker, model_name=model, **kwargs
        )

        if cost_callback:
            llm_costs = estimate_llm_cost(str(messages), response)
            cost_callback(llm_costs)

        return response

    logging.error(f"Failed to get response from {llm_provider} API")
    raise RuntimeError(f"Failed to get response from {llm_provider} API")


async def construct_subtopics(
    task: str,
    data: str,
    config,
    subtopics: list = [],
    prompt_family: type[PromptFamily] | PromptFamily = PromptFamily,
    **kwargs
) -> list:
    """
    Construct subtopics based on the given task and data.

    Args:
        task (str): The main task or topic.
        data (str): Additional data for context.
        config: Configuration settings.
        subtopics (list, optional): Existing subtopics. Defaults to [].
        prompt_family (PromptFamily): Family of prompts
        **kwargs: Additional keyword arguments (may include 'researcher' with token_tracker).

    Returns:
        list: A list of constructed subtopics.
    """
    try:
        # Extract token_tracker from kwargs if available
        token_tracker = None
        if 'researcher' in kwargs:
            researcher = kwargs.get('researcher')
            if hasattr(researcher, 'token_tracker'):
                token_tracker = researcher.token_tracker
        
        parser = PydanticOutputParser(pydantic_object=Subtopics)

        prompt = PromptTemplate(
            template=prompt_family.generate_subtopics_prompt(),
            input_variables=["task", "data", "subtopics", "max_subtopics"],
            partial_variables={
                "format_instructions": parser.get_format_instructions()},
        )

        provider_kwargs = {'model': config.smart_llm_model}

        if config.llm_kwargs:
            provider_kwargs.update(config.llm_kwargs)

        if config.smart_llm_model in SUPPORT_REASONING_EFFORT_MODELS:
            provider_kwargs['reasoning_effort'] = ReasoningEfforts.High.value
        else:
            provider_kwargs['temperature'] = config.temperature
            provider_kwargs['max_tokens'] = config.smart_token_limit

        provider = get_llm(config.smart_llm_provider, **provider_kwargs)

        model = provider.llm

        chain = prompt | model | parser

        # Filter out non-LangChain kwargs before invoking
        chain_kwargs = {k: v for k, v in kwargs.items() if k not in ['researcher', 'token_tracker', 'model_name']}

        output = await chain.ainvoke({
            "task": task,
            "data": data,
            "subtopics": subtopics,
            "max_subtopics": config.max_subtopics
        }, **chain_kwargs)
        
        # Track token usage from chain output
        if token_tracker is not None:
            try:
                from ..utils.token_utils import extract_token_usage_from_response
                usage_dict = extract_token_usage_from_response(output)
                if usage_dict:
                    token_tracker.add(
                        prompt_tokens=usage_dict.get("prompt_tokens", 0),
                        completion_tokens=usage_dict.get("completion_tokens", 0),
                        total_tokens=usage_dict.get("total_tokens", 0)
                    )
            except Exception as e:
                logging.getLogger(__name__).debug(f"Could not track token usage from construct_subtopics: {e}")

        return output

    except Exception as e:
        print("Exception in parsing subtopics : ", e)
        logging.getLogger(__name__).error("Exception in parsing subtopics : \n {e}")
        return subtopics
