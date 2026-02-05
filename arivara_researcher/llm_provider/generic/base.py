import aiofiles
import asyncio
import importlib
import json
import logging
import subprocess
import sys
import traceback
from typing import Any
from colorama import Fore, Style, init
import os
from enum import Enum

logger = logging.getLogger(__name__)

_SUPPORTED_PROVIDERS = {
    "openai",
    "anthropic",
    "azure_openai",
    "cohere",
    "google_vertexai",
    "google_genai",
    "fireworks",
    "ollama",
    "together",
    "mistralai",
    "huggingface",
    "groq",
    "bedrock",
    "dashscope",
    "xai",
    "deepseek",
    "litellm",
    "gigachat",
    "openrouter",
    "vllm_openai",
    "aimlapi",
}

NO_SUPPORT_TEMPERATURE_MODELS = [
    "deepseek/deepseek-reasoner",
    "o1-mini",
    "o1-mini-2024-09-12",
    "o1",
    "o1-2024-12-17",
    "o3-mini",
    "o3-mini-2025-01-31",
    "o1-preview",
    "o3",
    "o3-2025-04-16",
    "o4-mini",
    "o4-mini-2025-04-16",
]

SUPPORT_REASONING_EFFORT_MODELS = [
    "o3-mini",
    "o3-mini-2025-01-31",
    "o3",
    "o3-2025-04-16",
    "o4-mini",
    "o4-mini-2025-04-16",
]

class ReasoningEfforts(Enum):
    High = "high"
    Medium = "medium"
    Low = "low"


class ChatLogger:
    """Helper utility to log all chat requests and their corresponding responses
    plus the stack trace leading to the call.
    """

    def __init__(self, fname: str):
        self.fname = fname
        self._lock = asyncio.Lock()

    async def log_request(self, messages, response):
        async with self._lock:
            async with aiofiles.open(self.fname, mode="a", encoding="utf-8") as handle:
                await handle.write(json.dumps({
                    "messages": messages,
                    "response": response,
                    "stacktrace": traceback.format_exc()
                }) + "\n")

class GenericLLMProvider:

    def __init__(self, llm, chat_log: str | None = None,  verbose: bool = True):
        self.llm = llm
        self.chat_logger = ChatLogger(chat_log) if chat_log else None
        self.verbose = verbose
    @classmethod
    def from_provider(cls, provider: str, chat_log: str | None = None, verbose: bool=True, **kwargs: Any):
        if provider == "openai":
            _check_pkg("langchain_openai")
            from langchain_openai import ChatOpenAI

            # Ensure OPENAI_BASE_URL is used if provided in environment
            # This matches the behavior in arivara_researcher/utils/llm.py
            if "openai_api_base" not in kwargs:
                base_url = os.environ.get("OPENAI_BASE_URL", None)
                if base_url:
                    kwargs['openai_api_base'] = base_url
            
            llm = ChatOpenAI(**kwargs)
        elif provider == "anthropic":
            _check_pkg("langchain_anthropic")
            from langchain_anthropic import ChatAnthropic

            llm = ChatAnthropic(**kwargs)
        elif provider == "azure_openai":
            _check_pkg("langchain_openai")
            from langchain_openai import AzureChatOpenAI

            if "model" in kwargs:
                model_name = kwargs.get("model", None)
                kwargs = {"azure_deployment": model_name, **kwargs}

            llm = AzureChatOpenAI(**kwargs)
        elif provider == "cohere":
            _check_pkg("langchain_cohere")
            from langchain_cohere import ChatCohere

            llm = ChatCohere(**kwargs)
        elif provider == "google_vertexai":
            _check_pkg("langchain_google_vertexai")
            from langchain_google_vertexai import ChatVertexAI

            llm = ChatVertexAI(**kwargs)
        elif provider == "google_genai":
            _check_pkg("langchain_google_genai")
            from langchain_google_genai import ChatGoogleGenerativeAI

            llm = ChatGoogleGenerativeAI(**kwargs)
        elif provider == "fireworks":
            _check_pkg("langchain_fireworks")
            from langchain_fireworks import ChatFireworks

            llm = ChatFireworks(**kwargs)
        elif provider == "ollama":
            _check_pkg("langchain_community")
            _check_pkg("langchain_ollama")
            from langchain_ollama import ChatOllama

            llm = ChatOllama(base_url=os.environ["OLLAMA_BASE_URL"], **kwargs)
        elif provider == "together":
            _check_pkg("langchain_together")
            from langchain_together import ChatTogether

            llm = ChatTogether(**kwargs)
        elif provider == "mistralai":
            _check_pkg("langchain_mistralai")
            from langchain_mistralai import ChatMistralAI

            llm = ChatMistralAI(**kwargs)
        elif provider == "huggingface":
            _check_pkg("langchain_huggingface")
            from langchain_huggingface import ChatHuggingFace

            if "model" in kwargs or "model_name" in kwargs:
                model_id = kwargs.pop("model", None) or kwargs.pop("model_name", None)
                kwargs = {"model_id": model_id, **kwargs}
            llm = ChatHuggingFace(**kwargs)
        elif provider == "groq":
            _check_pkg("langchain_groq")
            from langchain_groq import ChatGroq

            llm = ChatGroq(**kwargs)
        elif provider == "bedrock":
            _check_pkg("langchain_aws")
            from langchain_aws import ChatBedrock

            if "model" in kwargs or "model_name" in kwargs:
                model_id = kwargs.pop("model", None) or kwargs.pop("model_name", None)
                kwargs = {"model_id": model_id, "model_kwargs": kwargs}
            llm = ChatBedrock(**kwargs)
        elif provider == "dashscope":
            _check_pkg("langchain_openai")
            from langchain_openai import ChatOpenAI

            llm = ChatOpenAI(openai_api_base='https://dashscope.aliyuncs.com/compatible-mode/v1',
                     openai_api_key=os.environ["DASHSCOPE_API_KEY"],
                     **kwargs
                )
        elif provider == "xai":
            _check_pkg("langchain_xai")
            from langchain_xai import ChatXAI

            llm = ChatXAI(**kwargs)
        elif provider == "deepseek":
            _check_pkg("langchain_openai")
            from langchain_openai import ChatOpenAI

            llm = ChatOpenAI(openai_api_base='https://api.deepseek.com',
                     openai_api_key=os.environ["DEEPSEEK_API_KEY"],
                     **kwargs
                )
        elif provider == "litellm":
            _check_pkg("langchain_community")
            from langchain_community.chat_models.litellm import ChatLiteLLM

            llm = ChatLiteLLM(**kwargs)
        elif provider == "gigachat":
            _check_pkg("langchain_gigachat")
            from langchain_gigachat.chat_models import GigaChat

            kwargs.pop("model", None) # Use env GIGACHAT_MODEL=GigaChat-Max
            llm = GigaChat(**kwargs)
        elif provider == "openrouter":
            _check_pkg("langchain_openai")
            from langchain_openai import ChatOpenAI
            from langchain_core.rate_limiters import InMemoryRateLimiter

            rps = float(os.environ["OPENROUTER_LIMIT_RPS"]) if "OPENROUTER_LIMIT_RPS" in os.environ else 1.0

            rate_limiter = InMemoryRateLimiter(
                requests_per_second=rps,
                check_every_n_seconds=0.1,
                max_bucket_size=10,
            )

            llm = ChatOpenAI(openai_api_base='https://openrouter.ai/api/v1',
                     openai_api_key=os.environ["OPENROUTER_API_KEY"],
                     rate_limiter=rate_limiter,
                     **kwargs
                )
        elif provider == "vllm_openai":
            _check_pkg("langchain_openai")
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(
                openai_api_key=os.environ["VLLM_OPENAI_API_KEY"],
                openai_api_base=os.environ["VLLM_OPENAI_API_BASE"],
                **kwargs
            )
        elif provider == "aimlapi":
            _check_pkg("langchain_openai")
            from langchain_openai import ChatOpenAI

            llm = ChatOpenAI(openai_api_base='https://api.aimlapi.com/v1',
                             openai_api_key=os.environ["AIMLAPI_API_KEY"],
                             **kwargs
                             )
        else:
            supported = ", ".join(_SUPPORTED_PROVIDERS)
            raise ValueError(
                f"Unsupported {provider}.\n\nSupported model providers are: {supported}"
            )
        return cls(llm, chat_log, verbose=verbose)


    async def get_chat_response(self, messages, stream, websocket=None, token_tracker=None, model_name=None, **kwargs):
        """
        Get chat response from LLM.
        
        Args:
            messages: Messages to send to the LLM
            stream: Whether to stream the response
            websocket: WebSocket connection for streaming
            token_tracker: Optional TokenUsageTracker instance to track token usage
            model_name: Optional model name for token tracking
            **kwargs: Additional arguments (will filter out 'researcher' and 'token_tracker' before passing to LLM)
        """
        # Filter out arguments that shouldn't be passed to the LLM
        llm_kwargs = {k: v for k, v in kwargs.items() if k not in ['researcher', 'token_tracker', 'model_name']}
        
        # Log websocket status
        if stream:
            if websocket is None:
                logger.warning("get_chat_response: stream=True but websocket=None - report will not be streamed")
            else:
                logger.info(f"get_chat_response: stream=True, websocket type={type(websocket).__name__}, has send_json={hasattr(websocket, 'send_json')}")
        
        if not stream:
            # Getting output from the model chain using ainvoke for asynchronous invoking
            output = await self.llm.ainvoke(messages, **llm_kwargs)

            # DEBUG: Log response structure and usage (user-requested debug output)
            print(f"DEBUG: API Response type: {type(output)}")
            print(f"DEBUG: Has usage_metadata: {hasattr(output, 'usage_metadata')}")
            print(f"DEBUG: Has response_metadata: {hasattr(output, 'response_metadata')}")
            if hasattr(output, 'usage_metadata'):
                print(f"DEBUG: Response usage_metadata: {output.usage_metadata}")
            if hasattr(output, 'response_metadata'):
                print(f"DEBUG: Response response_metadata: {output.response_metadata}")
            logger.debug(f"API Response type: {type(output)}, has usage_metadata: {hasattr(output, 'usage_metadata')}, has response_metadata: {hasattr(output, 'response_metadata')}")
            
            # Track token usage from response
            if token_tracker is not None:
                try:
                    # Try direct usage_metadata first (LangChain format)
                    if hasattr(output, 'usage_metadata') and output.usage_metadata:
                        usage_metadata = output.usage_metadata
                        if isinstance(usage_metadata, dict):
                            prompt_tokens = usage_metadata.get('input_tokens', 0)
                            completion_tokens = usage_metadata.get('output_tokens', 0)
                            total_tokens = usage_metadata.get('total_tokens', 0)
                        else:
                            prompt_tokens = getattr(usage_metadata, 'input_tokens', 0)
                            completion_tokens = getattr(usage_metadata, 'output_tokens', 0)
                            total_tokens = getattr(usage_metadata, 'total_tokens', 0)
                        
                        if prompt_tokens > 0 or completion_tokens > 0:
                            logger.info(f"Tracking usage from usage_metadata: prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}")
                            token_tracker.add(
                                prompt_tokens=prompt_tokens,
                                completion_tokens=completion_tokens,
                                total_tokens=total_tokens if total_tokens > 0 else (prompt_tokens + completion_tokens)
                            )
                        else:
                            logger.warning(f"Usage metadata exists but tokens are zero: {usage_metadata}")
                    
                    # Fallback to extraction utility
                    else:
                        from ..utils.token_utils import extract_token_usage_from_response
                        usage_dict = extract_token_usage_from_response(output)
                        if usage_dict and (usage_dict.get("prompt_tokens", 0) > 0 or usage_dict.get("completion_tokens", 0) > 0):
                            logger.info(f"Tracking usage from extract utility: {usage_dict}")
                            token_tracker.add(
                                prompt_tokens=usage_dict.get("prompt_tokens", 0),
                                completion_tokens=usage_dict.get("completion_tokens", 0),
                                total_tokens=usage_dict.get("total_tokens", 0)
                            )
                        else:
                            logger.warning(f"Could not extract usage from response. usage_dict: {usage_dict}, output type: {type(output)}")
                            # DEBUG: Print response attributes (user-requested debug output)
                            print(f"DEBUG: Response attributes: {[attr for attr in dir(output) if not attr.startswith('_')]}")
                            if hasattr(output, 'response_metadata'):
                                print(f"DEBUG: response_metadata: {output.response_metadata}")
                            print(f"DEBUG: Subquery usage extraction failed - usage_dict: {usage_dict}")
                except Exception as e:
                    logger.error(f"Failed to track token usage from non-streaming response: {e}", exc_info=True)
                    print(f"ERROR tracking tokens: {e}")
            else:
                logger.warning("token_tracker is None - token usage will not be tracked")

            res = output.content

        else:
            res = await self.stream_response(messages, websocket, token_tracker=token_tracker, model_name=model_name, **llm_kwargs)

        if self.chat_logger:
            await self.chat_logger.log_request(messages, res)

        return res

    async def stream_response(self, messages, websocket=None, token_tracker=None, model_name=None, **kwargs):
        """
        Stream OpenAI response efficiently, sending on newlines or when buffer fills.
        Optimized to balance real-time streaming with network efficiency.
        
        Args:
            messages: Messages to send
            websocket: WebSocket connection for streaming
            token_tracker: Optional TokenUsageTracker instance to track token usage
            model_name: Optional model name for token tracking
            **kwargs: Additional arguments
        """
        paragraph = ""  # Buffer for accumulating content
        response = ""  # Full accumulated response for return
        last_chunk = None  # Keep track of last chunk for token usage extraction
        
        # Log websocket status for debugging
        if websocket is None:
            logger.error("stream_response called with websocket=None - report will NOT be streamed to client!")
        else:
            logger.info(f"stream_response: websocket type={type(websocket).__name__}, has send_json={hasattr(websocket, 'send_json')}")

        # Streaming the response using the chain astream method from langchain
        chunk_count = 0
        first_chunk_sent = False
        max_retries = 3
        base_delay = 2.0  # Start with 2 seconds
        
        for attempt in range(max_retries + 1):
            # Reset variables for each retry attempt
            attempt_response = ""
            attempt_chunk_count = 0
            attempt_first_chunk_sent = False
            attempt_paragraph = ""
            attempt_last_chunk = None
            
            try:
                if attempt > 0:
                    # Reset main response for retry (use only the successful attempt's response)
                    response = ""
                    # Calculate exponential backoff delay
                    delay = base_delay * (2 ** (attempt - 1))  # 2s, 4s, 8s
                    logger.info(f"Rate limit retry attempt {attempt}/{max_retries} after {delay:.1f}s delay...")
                    if websocket:
                        try:
                            await self._send_output(
                                f"\n\n⏳ Retrying after rate limit error (attempt {attempt}/{max_retries}, waiting {delay:.0f}s)...\n\n",
                                websocket
                            )
                        except:
                            pass
                    import asyncio
                    await asyncio.sleep(delay)
                
                logger.info(f"Starting to stream response chunks... (attempt {attempt + 1}/{max_retries + 1}, websocket={websocket is not None})")
                # Filter out arguments that shouldn't be passed to the LLM
                llm_kwargs = {k: v for k, v in kwargs.items() if k not in ['researcher', 'token_tracker', 'model_name']}
                async for chunk in self.llm.astream(messages, **llm_kwargs):
                    attempt_chunk_count += 1
                    attempt_last_chunk = chunk  # Keep track of last chunk
                    content = chunk.content
                    
                    if content is not None and len(content) > 0:
                        attempt_response += content
                        response += content  # Accumulate in main response (reset on retry, so only current attempt)
                        attempt_paragraph += content
                        
                        # Send immediately on first chunk for instant feedback
                        # Then send on newlines or when buffer gets large (100 chars)
                        should_send = (
                            not attempt_first_chunk_sent or  # Always send first chunk immediately
                            "\n" in attempt_paragraph or  # Send on newline
                            len(attempt_paragraph) >= 100  # Send when buffer fills
                        )
                        
                        if should_send:
                            await self._send_output(attempt_paragraph, websocket)
                            attempt_first_chunk_sent = True
                            attempt_paragraph = ""  # Clear buffer after sending
                            
                    elif content is None:
                        logger.debug(f"Received None content in chunk #{attempt_chunk_count}")
                    else:
                        logger.debug(f"Received empty content in chunk #{attempt_chunk_count}")
                
                # Send any final remaining content from this attempt
                if attempt_paragraph:
                    await self._send_output(attempt_paragraph, websocket)
                
                # Track token usage from last chunk if available
                if token_tracker is not None and attempt_last_chunk is not None:
                    try:
                        from ..utils.token_utils import extract_token_usage_from_response
                        usage_dict = extract_token_usage_from_response(attempt_last_chunk)
                        if usage_dict:
                            token_tracker.add(
                                prompt_tokens=usage_dict.get("prompt_tokens", 0),
                                completion_tokens=usage_dict.get("completion_tokens", 0),
                                total_tokens=usage_dict.get("total_tokens", 0)
                            )
                    except Exception as e:
                        logger.debug(f"Could not extract token usage from streaming chunk: {e}")
                        # For streaming, token usage might not be available until end
                        # This is acceptable - we'll try to get it from response_metadata if available
                
                last_chunk = attempt_last_chunk
                # Successfully completed streaming
                chunk_count = attempt_chunk_count
                logger.info(f"Successfully completed streaming on attempt {attempt + 1} with {chunk_count} chunks, {len(response)} chars")
                break
                    
            except Exception as e:
                error_str = str(e)
                # Check if it's a rate limit error (429)
                is_rate_limit = (
                    "429" in error_str or 
                    "rate_limit" in error_str.lower() or 
                    "too many requests" in error_str.lower() or
                    "tokens per min" in error_str.lower() or
                    "rate limit" in error_str.lower()
                )
                
                if is_rate_limit and attempt < max_retries:
                    logger.warning(f"✗ Rate limit error in stream_response (attempt {attempt + 1}/{max_retries + 1}): {e}")
                    # Continue to retry with exponential backoff
                    continue
                elif is_rate_limit:
                    # Final attempt failed - return whatever we've accumulated so far
                    logger.error(f"✗ Rate limit error in stream_response after {max_retries + 1} attempts: {e}")
                    # Send any remaining buffered content from this attempt
                    if attempt_paragraph:
                        await self._send_output(attempt_paragraph, websocket)
                    # Send user-friendly error message to websocket
                    if websocket:
                        try:
                            await self._send_output(
                                "\n\n⚠️ **Rate Limit Error**: The API rate limit was exceeded after multiple retries. "
                                "The report generation may be incomplete. Please try again in a few moments.\n\n",
                                websocket
                            )
                        except:
                            pass
                    # Return accumulated response (from last attempt, which was reset, so only partial content)
                    logger.warning(f"Returning partial response ({len(response)} chars) due to rate limit after {max_retries + 1} attempts")
                    return response
                else:
                    # Not a rate limit error
                    logger.error(f"✗ Error in stream_response: {e}", exc_info=True)
                    # Send any remaining content even if there's an error
                    if attempt_paragraph:
                        logger.info(f"Sending remaining content after error: {len(attempt_paragraph)} chars")
                        await self._send_output(attempt_paragraph, websocket)
                    raise
        
        logger.info(f"stream_response completed. Total chunks: {chunk_count}, Total response length: {len(response)}")

        return response

    async def _send_output(self, content, websocket=None):
        """
        Send output to websocket in real-time. Ensures the output is always sent to the client as:
        {
            "type": "report",
            "output": "..."
        }
        Sends immediately without buffering - even single characters are sent.
        """
        # Ensure content is always a string and not None
        if content is None:
            content = ""
        
        # Ensure string type
        content = str(content)
        
        # Don't skip any content - send even single characters for real-time streaming
        # Only skip if completely empty (no characters at all)
        if len(content) == 0:
            logger.debug(f"_send_output: Skipping completely empty content")
            return
            
        if websocket is not None:
            try:
                # Check if websocket has send_json method (WebSocket or CustomLogsHandler)
                if hasattr(websocket, 'send_json'):
                    # Always wrap the response in the correct format
                    report_message = {
                        "type": "report",
                        "output": content
                    }
                    # Send immediately - no buffering
                    await websocket.send_json(report_message)
                    
                    # Log for debugging (only log first 30 chars to avoid spam)
                    if len(content) <= 30:
                        logger.debug(f"✓ Sent report chunk ({len(content)} chars): '{content}'")
                    else:
                        preview = content[:30].replace('\n', '\\n')
                        logger.debug(f"✓ Sent report chunk ({len(content)} chars): '{preview}...'")
                else:
                    # Fallback: try to use it as a WebSocket directly
                    logger.error(f"✗ WebSocket object {type(websocket)} does not have send_json method - report will NOT be streamed!")
                    if self.verbose:
                        print(f"{Fore.GREEN}{content}{Style.RESET_ALL}")
            except Exception as e:
                logger.error(f"✗ EXCEPTION in _send_output: {type(e).__name__}: {e}", exc_info=True)
                # Still print if verbose mode
                if self.verbose:
                    print(f"{Fore.GREEN}{content}{Style.RESET_ALL}")
        else:
            logger.error(f"✗ _send_output: websocket is None - report chunk NOT sent! Content: '{content[:100]}...' ({len(content)} chars)")
            if self.verbose:
                print(f"{Fore.GREEN}{content}{Style.RESET_ALL}")


def _check_pkg(pkg: str) -> None:
    if not importlib.util.find_spec(pkg):
        pkg_kebab = pkg.replace("_", "-")
        # Import colorama and initialize it
        init(autoreset=True)

        try:
            print(f"{Fore.YELLOW}Installing {pkg_kebab}...{Style.RESET_ALL}")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-U", pkg_kebab])
            print(f"{Fore.GREEN}Successfully installed {pkg_kebab}{Style.RESET_ALL}")

            # Try importing again after install
            importlib.import_module(pkg)

        except subprocess.CalledProcessError:
            raise ImportError(
                Fore.RED + f"Failed to install {pkg_kebab}. Please install manually with "
                f"`pip install -U {pkg_kebab}`"
            )
