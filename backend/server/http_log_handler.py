"""Custom logging handler to capture httpx HTTP requests and send via WebSocket."""

import logging
import re
import asyncio
from typing import Optional, Dict, Any
from fastapi import WebSocket
from queue import Queue, Empty


class WebSocketHTTPLogHandler(logging.Handler):
    """Custom logging handler that sends httpx HTTP request logs to WebSocket."""
    
    def __init__(self, websocket: Optional[WebSocket] = None):
        """
        Initialize the handler.
        
        Args:
            websocket: WebSocket connection to send logs to
        """
        super().__init__()
        self.websocket = websocket
        self.setLevel(logging.INFO)
        self.log_queue: Queue = Queue()
        self._sender_task: Optional[asyncio.Task] = None
        
        # Pattern to match httpx HTTP request logs
        # Format: "HTTP Request: POST https://api.openai.com/v1/embeddings "HTTP/1.1 200 OK""
        self.request_pattern = re.compile(
            r'HTTP Request:\s+(\w+)\s+(https?://[^\s]+)\s+"HTTP/1\.1\s+(\d+)\s+([^"]+)"'
        )
        
        # Start sender task if websocket is provided
        if websocket:
            self._start_sender()
    
    def set_websocket(self, websocket: WebSocket):
        """Update the WebSocket connection and start sender if needed."""
        self.websocket = websocket
        if websocket and not self._sender_task:
            self._start_sender()
    
    def _start_sender(self):
        """Start the async sender task."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                self._sender_task = asyncio.create_task(self._sender_loop())
        except RuntimeError:
            # No event loop, will start when one is available
            pass
    
    async def _sender_loop(self):
        """Continuously send queued logs to WebSocket."""
        while self.websocket:
            try:
                # Get log from queue (non-blocking)
                try:
                    log_data = self.log_queue.get_nowait()
                    if self.websocket:
                        await self.websocket.send_json(log_data)
                except Empty:
                    # No logs to send, wait a bit
                    await asyncio.sleep(0.1)
                except Exception as e:
                    # WebSocket might be closed, stop sender
                    break
            except Exception:
                break
    
    def emit(self, record: logging.LogRecord):
        """
        Emit a log record to WebSocket if it's an httpx HTTP request.
        This is synchronous and queues the message for async sending.
        
        Args:
            record: Log record to process
        """
        if not self.websocket:
            return
        
        # Only process httpx logger messages
        if record.name != 'httpx':
            return
        
        # Only process INFO level messages (HTTP requests are logged at INFO)
        if record.levelno < logging.INFO:
            return
        
        message = record.getMessage()
        
        # Check if this is an HTTP request log
        match = self.request_pattern.search(message)
        if match:
            method, url, status_code, status_text = match.groups()
            
            # Extract API provider from URL
            api_provider = self._extract_api_provider(url)
            
            # Format the log message for frontend
            log_data = {
                "type": "logs",
                "content": "http_request",
                "output": f"🌐 {method} {url} → {status_code} {status_text}",
                "metadata": {
                    "method": method,
                    "url": url,
                    "status_code": int(status_code),
                    "status_text": status_text,
                    "api_provider": api_provider,
                    "timestamp": record.created
                }
            }
            
            # Queue the log for async sending
            try:
                self.log_queue.put_nowait(log_data)
                # Start sender if not already running
                if not self._sender_task or self._sender_task.done():
                    self._start_sender()
            except Exception as e:
                # Queue full or other error, ignore
                pass
    
    def _extract_api_provider(self, url: str) -> str:
        """Extract API provider name from URL."""
        if 'openai.com' in url:
            return 'OpenAI'
        elif 'anthropic.com' in url or 'claude' in url:
            return 'Anthropic'
        elif 'googleapis.com' in url or 'google.com' in url:
            return 'Google'
        elif 'x.ai' in url:
            return 'xAI'
        elif 'deepseek.com' in url:
            return 'DeepSeek'
        elif 'tavily.com' in url:
            return 'Tavily'
        elif 'serpapi.com' in url:
            return 'SerpAPI'
        elif 'serper.dev' in url:
            return 'Serper'
        elif 'searchapi.io' in url:
            return 'SearchAPI'
        elif 'bing.com' in url:
            return 'Bing'
        else:
            return 'Unknown'


# Global handler instance (will be set per WebSocket connection)
_http_log_handler: Optional[WebSocketHTTPLogHandler] = None


def setup_httpx_logging(websocket: Optional[WebSocket] = None) -> WebSocketHTTPLogHandler:
    """
    Setup httpx logging to send HTTP requests to WebSocket.
    
    Args:
        websocket: WebSocket connection to send logs to
        
    Returns:
        The configured log handler
    """
    global _http_log_handler
    
    # Get httpx logger
    httpx_logger = logging.getLogger('httpx')
    
    # Remove existing handler if it exists
    if _http_log_handler:
        httpx_logger.removeHandler(_http_log_handler)
    
    # Create new handler
    _http_log_handler = WebSocketHTTPLogHandler(websocket)
    httpx_logger.addHandler(_http_log_handler)
    httpx_logger.setLevel(logging.INFO)
    httpx_logger.propagate = False  # Prevent duplicate logs
    
    return _http_log_handler


def update_httpx_log_websocket(websocket: WebSocket):
    """
    Update the WebSocket connection for httpx logging.
    
    Args:
        websocket: New WebSocket connection
    """
    global _http_log_handler
    if _http_log_handler:
        _http_log_handler.set_websocket(websocket)

