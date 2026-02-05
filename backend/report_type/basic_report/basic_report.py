from fastapi import WebSocket
from typing import Any

from arivara_researcher import Arivara_researcher


class BasicReport:
    def __init__(
        self,
        query: str,
        query_domains: list,
        report_type: str,
        report_source: str,
        source_urls,
        document_urls,
        tone: Any,
        config_path: str,
        websocket: WebSocket,
        headers=None,
        mcp_configs=None,
        mcp_strategy=None,
    ):
        self.query = query
        self.query_domains = query_domains
        self.report_type = report_type
        self.report_source = report_source
        self.source_urls = source_urls
        self.document_urls = document_urls
        self.tone = tone
        self.config_path = config_path
        self.websocket = websocket
        self.headers = headers or {}

        # Initialize researcher with optional MCP parameters
        arivara_researcher_params = {
            "query": self.query,
            "query_domains": self.query_domains,
            "report_type": self.report_type,
            "report_source": self.report_source,
            "source_urls": self.source_urls,
            "document_urls": self.document_urls,
            "tone": self.tone,
            "config_path": self.config_path,
            "websocket": self.websocket,
            "headers": self.headers,
        }
        
        # Add MCP parameters if provided
        if mcp_configs is not None:
            arivara_researcher_params["mcp_configs"] = mcp_configs
        if mcp_strategy is not None:
            arivara_researcher_params["mcp_strategy"] = mcp_strategy
            
        self.arivara_researcher = Arivara_researcher(**arivara_researcher_params)

    async def run(self):
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"=== BasicReport.run() STARTED for report_type={self.report_type} ===")
        logger.info(f"Websocket available: {self.websocket is not None}, type={type(self.websocket).__name__ if self.websocket else 'None'}")
        
        # Step 1: Conduct research (this is where HTTP logs come from)
        logger.info(f"Step 1: Starting conduct_research() for report_type={self.report_type}")
        await self.arivara_researcher.conduct_research()
        logger.info(f"Step 1: conduct_research() completed for report_type={self.report_type}")
        
        # Step 2: Write report (this is where report streaming should happen)
        logger.info(f"Step 2: Starting write_report() for report_type={self.report_type}")
        logger.info(f"Websocket before write_report: {self.arivara_researcher.websocket is not None}, type={type(self.arivara_researcher.websocket).__name__ if self.arivara_researcher.websocket else 'None'}")
        
        report = await self.arivara_researcher.write_report()
        
        logger.info(f"Step 2: write_report() completed for report_type={self.report_type}, report length={len(report) if report else 0}")
        
        # Append token usage summary to the report and print to console/logs
        try:
            token_usage = self.arivara_researcher.get_token_usage()
            if token_usage and token_usage.get('total_tokens', 0) > 0:
                from arivara_researcher.utils.token_summary import format_token_summary_markdown, print_token_summary
                model_name = self.arivara_researcher.cfg.smart_llm_model if hasattr(self.arivara_researcher.cfg, 'smart_llm_model') else None
                
                # Print to console/logs
                print_token_summary(token_usage, model_name, include_cost=True)
                
                # Append to report markdown
                token_summary = format_token_summary_markdown(token_usage, model_name, include_cost=True)
                report = report + "\n\n" + token_summary
                logger.info(f"Token usage summary appended to report: {token_usage.get('total_tokens', 0)} tokens")
            else:
                logger.warning(f"Token usage is empty or zero: {token_usage}")
        except Exception as e:
            logger.warning(f"Failed to append token usage summary: {e}", exc_info=True)
        
        logger.info(f"=== BasicReport.run() COMPLETED for report_type={self.report_type} ===")
        
        return report
