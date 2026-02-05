import asyncio
from typing import List, Dict, Set, Optional, Any
from fastapi import WebSocket

from arivara_researcher import Arivara_researcher


class DetailedReport:
    def __init__(
        self,
        query: str,
        report_type: str,
        report_source: str,
        source_urls: List[str] = [],
        document_urls: List[str] = [],
        query_domains: List[str] = [],
        config_path: str = None,
        tone: Any = "",
        websocket: WebSocket = None,
        subtopics: List[Dict] = [],
        headers: Optional[Dict] = None,
        complement_source_urls: bool = False,
        mcp_configs=None,
        mcp_strategy=None,
    ):
        self.query = query
        self.report_type = report_type
        self.report_source = report_source
        self.source_urls = source_urls
        self.document_urls = document_urls
        self.query_domains = query_domains
        self.config_path = config_path
        self.tone = tone
        self.websocket = websocket
        self.subtopics = subtopics
        self.headers = headers or {}
        self.complement_source_urls = complement_source_urls
        
        # Initialize researcher with optional MCP parameters
        arivara_researcher_params = {
            "query": self.query,
            "query_domains": self.query_domains,
            "report_type": "research_report",
            "report_source": self.report_source,
            "source_urls": self.source_urls,
            "document_urls": self.document_urls,
            "config_path": self.config_path,
            "tone": self.tone,
            "websocket": self.websocket,
            "headers": self.headers,
            "complement_source_urls": self.complement_source_urls,
        }
        
        # Add MCP parameters if provided
        if mcp_configs is not None:
            arivara_researcher_params["mcp_configs"] = mcp_configs
        if mcp_strategy is not None:
            arivara_researcher_params["mcp_strategy"] = mcp_strategy
            
        self.arivara_researcher = Arivara_researcher(**arivara_researcher_params)
        self.existing_headers: List[Dict] = []
        self.global_context: List[str] = []
        self.global_written_sections: List[str] = []
        self.global_urls: Set[str] = set(
            self.source_urls) if self.source_urls else set()

    async def run(self) -> str:
        import logging
        logger = logging.getLogger(__name__)
        
        await self._initial_research()
        subtopics = await self._get_all_subtopics()
        report_introduction = await self.arivara_researcher.write_introduction()
        _, report_body = await self._generate_subtopic_reports(subtopics)
        self.arivara_researcher.visited_urls.update(self.global_urls)
        report = await self._construct_detailed_report(report_introduction, report_body)
        
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
        
        return report

    async def _initial_research(self) -> None:
        await self.arivara_researcher.conduct_research()
        self.global_context = self.arivara_researcher.context
        self.global_urls = self.arivara_researcher.visited_urls

    async def _get_all_subtopics(self) -> List[Dict]:
        subtopics_data = await self.arivara_researcher.get_subtopics()

        all_subtopics = []
        if subtopics_data and subtopics_data.subtopics:
            for subtopic in subtopics_data.subtopics:
                all_subtopics.append({"task": subtopic.task})
        else:
            print(f"Unexpected subtopics data format: {subtopics_data}")

        return all_subtopics

    async def _generate_subtopic_reports(self, subtopics: List[Dict]) -> tuple:
        subtopic_reports = []
        subtopics_report_body = ""

        for subtopic in subtopics:
            result = await self._get_subtopic_report(subtopic)
            if result["report"]:
                subtopic_reports.append(result)
                subtopics_report_body += f"\n\n\n{result['report']}"

        return subtopic_reports, subtopics_report_body

    async def _get_subtopic_report(self, subtopic: Dict) -> Dict[str, str]:
        current_subtopic_task = subtopic.get("task")
        subtopic_assistant = Arivara_researcher(
            query=current_subtopic_task,
            query_domains=self.query_domains,
            report_type="subtopic_report",
            report_source=self.report_source,
            websocket=self.websocket,
            headers=self.headers,
            parent_query=self.query,
            subtopics=self.subtopics,
            visited_urls=self.global_urls,
            agent=self.arivara_researcher.agent,
            role=self.arivara_researcher.role,
            tone=self.tone,
            complement_source_urls=self.complement_source_urls,
            source_urls=self.source_urls
        )

        subtopic_assistant.context = list(set(self.global_context))
        await subtopic_assistant.conduct_research()

        draft_section_titles = await subtopic_assistant.get_draft_section_titles(current_subtopic_task)

        if not isinstance(draft_section_titles, str):
            draft_section_titles = str(draft_section_titles)

        parse_draft_section_titles = self.arivara_researcher.extract_headers(draft_section_titles)
        parse_draft_section_titles_text = [header.get(
            "text", "") for header in parse_draft_section_titles]

        relevant_contents = await subtopic_assistant.get_similar_written_contents_by_draft_section_titles(
            current_subtopic_task, parse_draft_section_titles_text, self.global_written_sections
        )

        subtopic_report = await subtopic_assistant.write_report(self.existing_headers, relevant_contents)

        self.global_written_sections.extend(self.arivara_researcher.extract_sections(subtopic_report))
        self.global_context = list(set(subtopic_assistant.context))
        self.global_urls.update(subtopic_assistant.visited_urls)

        self.existing_headers.append({
            "subtopic task": current_subtopic_task,
            "headers": self.arivara_researcher.extract_headers(subtopic_report),
        })

        return {"topic": subtopic, "report": subtopic_report}

    async def _construct_detailed_report(self, introduction: str, report_body: str) -> str:
        toc = self.arivara_researcher.table_of_contents(report_body)
        conclusion = await self.arivara_researcher.write_report_conclusion(report_body)
        conclusion_with_references = self.arivara_researcher.add_references(
            conclusion, self.arivara_researcher.visited_urls)
        report = f"{introduction}\n\n{toc}\n\n{report_body}\n\n{conclusion_with_references}"
        
        # Append token usage summary to the report
        try:
            import logging
            logger = logging.getLogger(__name__)
            token_usage = self.arivara_researcher.get_token_usage()
            if token_usage and token_usage.get('total_tokens', 0) > 0:
                from arivara_researcher.utils.token_summary import format_token_summary_markdown
                model_name = self.arivara_researcher.cfg.smart_llm_model if hasattr(self.arivara_researcher.cfg, 'smart_llm_model') else None
                token_summary = format_token_summary_markdown(token_usage, model_name, include_cost=True)
                report = report + "\n\n" + token_summary
                logger.info(f"Token usage summary appended to report: {token_usage.get('total_tokens', 0)} tokens")
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to append token usage summary: {e}", exc_info=True)
        
        return report
