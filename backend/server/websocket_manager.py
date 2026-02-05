import asyncio
import datetime
from typing import Dict, List

from fastapi import WebSocket

from backend.report_type import BasicReport, DetailedReport
from backend.chat import ChatAgentWithMemory

from arivara_researcher.utils.enum import ReportType, Tone
from multi_agents.main import run_research_task
from arivara_researcher.actions import stream_output  # Import stream_output
from backend.server.server_utils import CustomLogsHandler


class WebSocketManager:
    """Manage websockets"""

    def __init__(self):
        """Initialize the WebSocketManager class."""
        self.active_connections: List[WebSocket] = []
        self.sender_tasks: Dict[WebSocket, asyncio.Task] = {}
        self.message_queues: Dict[WebSocket, asyncio.Queue] = {}
        # Store chat agents per WebSocket connection to prevent data mixing between users
        self.chat_agents: Dict[WebSocket, ChatAgentWithMemory] = {}

    async def start_sender(self, websocket: WebSocket):
        """Start the sender task."""
        queue = self.message_queues.get(websocket)
        if not queue:
            return

        while True:
            try:
                message = await queue.get()
                if message is None:  # Shutdown signal
                    break
                    
                if websocket in self.active_connections:
                    if message == "ping":
                        await websocket.send_text("pong")
                    else:
                        await websocket.send_text(message)
                else:
                    break
            except Exception as e:
                print(f"Error in sender task: {e}")
                break

    async def connect(self, websocket: WebSocket):
        """Connect a websocket."""
        try:
            await websocket.accept()
            self.active_connections.append(websocket)
            self.message_queues[websocket] = asyncio.Queue()
            self.sender_tasks[websocket] = asyncio.create_task(
                self.start_sender(websocket))
        except Exception as e:
            print(f"Error connecting websocket: {e}")
            if websocket in self.active_connections:
                await self.disconnect(websocket)

    async def disconnect(self, websocket: WebSocket):
        """Disconnect a websocket."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            if websocket in self.sender_tasks:
                self.sender_tasks[websocket].cancel()
                await self.message_queues[websocket].put(None)
                del self.sender_tasks[websocket]
            if websocket in self.message_queues:
                del self.message_queues[websocket]
            # Clean up chat agent for this connection
            if websocket in self.chat_agents:
                del self.chat_agents[websocket]
            try:
                await websocket.close()
            except:
                pass  # Connection might already be closed

    async def start_streaming(self, task, report_type, report_source, source_urls, document_urls, tone, websocket, headers=None, query_domains=[], mcp_enabled=False, mcp_strategy="fast", mcp_configs=[]):
        """Start streaming the output."""
        # Normalize tone value: strip whitespace and capitalize first letter
        if tone:
            tone = str(tone).strip()
            if tone:  # Check if tone is not empty after stripping
                # Map common variations
                tone_mapping = {
                    "professional": "Formal",
                    "academic": "Formal",
                    "casual": "Casual",
                    "simple": "Simple",
                }
                # Convert to title case if not already (e.g., "objective" -> "Objective")
                if tone.lower() in tone_mapping:
                    tone = tone_mapping[tone.lower()]
                elif len(tone) > 0 and not tone[0].isupper():
                    tone = tone.capitalize()
            else:
                tone = None
        
        # Default to Objective if tone is not provided or invalid
        try:
            tone = Tone[tone] if tone else Tone.Objective
        except KeyError:
            # If tone is not found, try to find a close match or default to Objective
            original_tone = tone
            await websocket.send_json({
                "type": "logs",
                "content": "error",
                "output": f"Invalid tone '{original_tone}'. Using default 'Objective' tone."
            })
            tone = Tone.Objective
        # add customized JSON config file path here
        config_path = "default"
        
        # Pass MCP parameters to run_agent
        result = await run_agent(
            task, report_type, report_source, source_urls, document_urls, tone, websocket, 
            headers=headers, query_domains=query_domains, config_path=config_path,
            mcp_enabled=mcp_enabled, mcp_strategy=mcp_strategy, mcp_configs=mcp_configs
        )
        
        # Extract report and token_usage from result
        if isinstance(result, tuple):
            report, token_usage = result
        else:
            report = result
            token_usage = None
        
        # Create new Chat Agent per WebSocket connection whenever a new report is written
        # This ensures each user gets their own chat agent with their own report
        self.chat_agents[websocket] = ChatAgentWithMemory(report, config_path, headers)
        return report, token_usage

    async def chat(self, message, websocket):
        """Chat with the agent based message diff"""
        # Get chat agent for this specific WebSocket connection
        chat_agent = self.chat_agents.get(websocket)
        if chat_agent:
            await chat_agent.chat(message, websocket)
        else:
            await websocket.send_json({"type": "chat", "content": "Knowledge empty, please run the research first to obtain knowledge"})

async def run_agent(task, report_type, report_source, source_urls, document_urls, tone: Tone, websocket, stream_output=stream_output, headers=None, query_domains=[], config_path="", return_researcher=False, mcp_enabled=False, mcp_strategy="fast", mcp_configs=[]):
    """Run the agent."""    
    # Create logs handler for this research task
    logs_handler = CustomLogsHandler(websocket, task)

    # Set up MCP configuration if enabled
    if mcp_enabled and mcp_configs:
        import os
        current_retriever = os.getenv("RETRIEVER", "tavily")
        if "mcp" not in current_retriever:
            # Add MCP to existing retrievers
            os.environ["RETRIEVER"] = f"{current_retriever},mcp"
        
        # Set MCP strategy
        os.environ["MCP_STRATEGY"] = mcp_strategy
        
        print(f"🔧 MCP enabled with strategy '{mcp_strategy}' and {len(mcp_configs)} server(s)")
        await logs_handler.send_json({
            "type": "logs",
            "content": "mcp_init",
            "output": f"🔧 MCP enabled with strategy '{mcp_strategy}' and {len(mcp_configs)} server(s)"
        })

    # Initialize researcher based on report type
    researcher = None
    token_usage = None
    
    if report_type == "multi_agents":
        report = await run_research_task(
            query=task, 
            websocket=logs_handler,  # Use logs_handler instead of raw websocket
            stream_output=stream_output, 
            tone=tone, 
            headers=headers
        )
        report = report.get("report", "")
        # multi_agents doesn't have a researcher object, so token_usage stays None

    elif report_type == ReportType.DetailedReport.value:
        researcher = DetailedReport(
            query=task,
            query_domains=query_domains,
            report_type=report_type,
            report_source=report_source,
            source_urls=source_urls,
            document_urls=document_urls,
            tone=tone,
            config_path=config_path,
            websocket=logs_handler,  # Use logs_handler instead of raw websocket
            headers=headers,
            mcp_configs=mcp_configs if mcp_enabled else None,
            mcp_strategy=mcp_strategy if mcp_enabled else None,
        )
        report = await researcher.run()
        
    else:
        researcher = BasicReport(
            query=task,
            query_domains=query_domains,
            report_type=report_type,
            report_source=report_source,
            source_urls=source_urls,
            document_urls=document_urls,
            tone=tone,
            config_path=config_path,
            websocket=logs_handler,  # Use logs_handler instead of raw websocket
            headers=headers,
            mcp_configs=mcp_configs if mcp_enabled else None,
            mcp_strategy=mcp_strategy if mcp_enabled else None,
        )
        report = await researcher.run()

    # Get token usage from researcher if available
    token_usage = None
    if researcher is not None:
        try:
            import logging
            logger = logging.getLogger(__name__)
            
            # Debug: Check if researcher has arivara_researcher attribute
            if not hasattr(researcher, 'arivara_researcher'):
                logger.error(f"Researcher object does not have 'arivara_researcher' attribute. Type: {type(researcher)}")
            else:
                # Debug: Check if arivara_researcher has get_token_usage method
                if not hasattr(researcher.arivara_researcher, 'get_token_usage'):
                    logger.error(f"arivara_researcher does not have 'get_token_usage' method")
                else:
                    token_usage = researcher.arivara_researcher.get_token_usage()
                    if token_usage:
                        logger.info(f"✅ Retrieved token usage from researcher: prompt={token_usage.get('prompt_tokens', 0)}, completion={token_usage.get('completion_tokens', 0)}, total={token_usage.get('total_tokens', 0)}, calls={token_usage.get('call_count', 0)}")
                    else:
                        logger.warning(f"⚠️ Token usage is None/empty from researcher")
                        
                        # Debug: Check if token_tracker exists
                        if hasattr(researcher.arivara_researcher, 'token_tracker'):
                            tracker = researcher.arivara_researcher.token_tracker
                            if tracker:
                                tracker_summary = tracker.summary()
                                logger.info(f"Debug: token_tracker.summary() = {tracker_summary}")
                            else:
                                logger.error(f"token_tracker is None")
                        else:
                            logger.error(f"arivara_researcher does not have 'token_tracker' attribute")
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"❌ Failed to get token usage from researcher: {e}", exc_info=True)
    
    if return_researcher and researcher is not None:
        return report, researcher.arivara_researcher, token_usage
    else:
        return report, token_usage
