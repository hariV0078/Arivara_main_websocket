from typing import Dict, Optional
import json
import logging

from ..utils.llm import construct_subtopics
from ..actions import (
    stream_output,
    generate_report,
    generate_draft_section_titles,
    write_report_introduction,
    write_conclusion
)

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generates reports based on research data."""

    def __init__(self, researcher):
        self.researcher = researcher
        self.research_params = {
            "query": self.researcher.query,
            "agent_role_prompt": self.researcher.cfg.agent_role or self.researcher.role,
            "report_type": self.researcher.report_type,
            "report_source": self.researcher.report_source,
            "tone": self.researcher.tone,
            "websocket": self.researcher.websocket,
            "cfg": self.researcher.cfg,
            "headers": self.researcher.headers,
        }

    async def write_report(self, existing_headers: list = [], relevant_written_contents: list = [], ext_context=None, custom_prompt="") -> str:
        """
        Write a report based on existing headers and relevant contents.

        Args:
            existing_headers (list): List of existing headers.
            relevant_written_contents (list): List of relevant written contents.
            ext_context (Optional): External context, if any.
            custom_prompt (str): Custom prompt for the report.

        Returns:
            str: The generated report.
        """
        # send the selected images prior to writing report
        research_images = self.researcher.get_research_images()
        if research_images:
            await stream_output(
                "images",
                "selected_images",
                json.dumps(research_images),
                self.researcher.websocket,
                True,
                research_images
            )

        context = ext_context or self.researcher.context
        
        # For deep research, allow much more context before truncating
        # Deep research needs extensive context to generate comprehensive 20+ page reports
        # API limit is 128k tokens total, so we can use 50k for context + 16k for output = 66k total
        if self.researcher.report_type == "deep" or self.researcher.report_type == "DeepResearch":
            max_tokens_threshold = 50000  # Allow 50k tokens for deep research context
        else:
            max_tokens_threshold = 20000  # Regular reports use 20k
        
        char_threshold = max_tokens_threshold * 4  # ~4 chars per token
        
        # Truncate context if it's a string and too large (to avoid token limit errors)
        if isinstance(context, str) and len(context) > char_threshold:
            from ..actions.report_generation import truncate_context_for_tokens, estimate_tokens
            original_tokens = estimate_tokens(context)
            if original_tokens > max_tokens_threshold:
                logger.warning(f"Context is very large ({original_tokens} tokens), truncating before report generation (threshold: {max_tokens_threshold})...")
                context = truncate_context_for_tokens(context, max_tokens=max_tokens_threshold)
                if self.researcher.websocket:
                    try:
                        await self.researcher.websocket.send_json({
                            "type": "logs",
                            "content": "context_truncated",
                            "output": f"⚠️ Research context is very large ({original_tokens} tokens). Truncating to {max_tokens_threshold} tokens to allow comprehensive report generation."
                        })
                    except:
                        pass
            else:
                logger.info(f"Context size: {original_tokens} tokens (within {max_tokens_threshold} limit for {self.researcher.report_type})")
        
        # Send a clear message that report generation is starting
        if self.researcher.websocket:
            try:
                logger.info(f"=== REPORT GENERATION STARTING for report_type={self.researcher.report_type} ===")
                await self.researcher.websocket.send_json({
                    "type": "logs",
                    "content": "report_generation_start",
                    "output": f"📝 Starting report generation for '{self.researcher.query[:50]}'... This may take a moment."
                })
                logger.info(f"✓ Report generation start message sent to websocket")
            except Exception as e:
                logger.error(f"✗ Failed to send report generation start message: {e}", exc_info=True)
        
        if self.researcher.verbose:
            await stream_output(
                "logs",
                "writing_report",
                f"✍️ Writing report for '{self.researcher.query}'...",
                self.researcher.websocket,
            )

        report_params = self.research_params.copy()
        report_params["context"] = context
        report_params["custom_prompt"] = custom_prompt
        
        # Always use the current websocket from researcher (not the stored one)
        # This ensures we have the latest websocket reference
        current_websocket = self.researcher.websocket
        report_params["websocket"] = current_websocket

        if self.researcher.report_type == "subtopic_report":
            report_params.update({
                "main_topic": self.researcher.parent_query,
                "existing_headers": existing_headers,
                "relevant_written_contents": relevant_written_contents,
                "cost_callback": self.researcher.add_costs,
            })
        else:
            report_params["cost_callback"] = self.researcher.add_costs

        # Add researcher to kwargs for token tracking
        kwargs_with_researcher = self.researcher.kwargs.copy()
        kwargs_with_researcher["researcher"] = self.researcher

        # Log websocket status for debugging
        if current_websocket is None:
            logger.error(f"✗ ReportGenerator.write_report: websocket is None for report_type={self.researcher.report_type}, query={self.researcher.query[:50]} - report will NOT be streamed!")
        else:
            has_send_json = hasattr(current_websocket, 'send_json')
            inner_ws = getattr(current_websocket, 'websocket', None)
            logger.info(f"✓ ReportGenerator.write_report: websocket available (type={type(current_websocket).__name__}, has send_json={has_send_json}, inner_websocket={inner_ws is not None}) for report_type={self.researcher.report_type}, query={self.researcher.query[:50]}")

        report = await generate_report(**report_params, **kwargs_with_researcher)

        if self.researcher.verbose:
            await stream_output(
                "logs",
                "report_written",
                f"📝 Report written for '{self.researcher.query}'",
                self.researcher.websocket,
            )

        return report

    async def write_report_conclusion(self, report_content: str) -> str:
        """
        Write the conclusion for the report.

        Args:
            report_content (str): The content of the report.

        Returns:
            str: The generated conclusion.
        """
        if self.researcher.verbose:
            await stream_output(
                "logs",
                "writing_conclusion",
                f"✍️ Writing conclusion for '{self.researcher.query}'...",
                self.researcher.websocket,
            )

        # Ensure researcher is in kwargs for token tracking
        kwargs_with_researcher = self.researcher.kwargs.copy()
        kwargs_with_researcher["researcher"] = self.researcher

        conclusion = await write_conclusion(
            query=self.researcher.query,
            context=report_content,
            config=self.researcher.cfg,
            agent_role_prompt=self.researcher.cfg.agent_role or self.researcher.role,
            cost_callback=self.researcher.add_costs,
            websocket=self.researcher.websocket,
            prompt_family=self.researcher.prompt_family,
            **kwargs_with_researcher
        )

        if self.researcher.verbose:
            await stream_output(
                "logs",
                "conclusion_written",
                f"📝 Conclusion written for '{self.researcher.query}'",
                self.researcher.websocket,
            )

        return conclusion

    async def write_introduction(self):
        """Write the introduction section of the report."""
        if self.researcher.verbose:
            await stream_output(
                "logs",
                "writing_introduction",
                f"✍️ Writing introduction for '{self.researcher.query}'...",
                self.researcher.websocket,
            )

        # Ensure researcher is in kwargs for token tracking
        kwargs_with_researcher = self.researcher.kwargs.copy()
        kwargs_with_researcher["researcher"] = self.researcher

        introduction = await write_report_introduction(
            query=self.researcher.query,
            context=self.researcher.context,
            agent_role_prompt=self.researcher.cfg.agent_role or self.researcher.role,
            config=self.researcher.cfg,
            websocket=self.researcher.websocket,
            cost_callback=self.researcher.add_costs,
            prompt_family=self.researcher.prompt_family,
            **kwargs_with_researcher
        )

        if self.researcher.verbose:
            await stream_output(
                "logs",
                "introduction_written",
                f"📝 Introduction written for '{self.researcher.query}'",
                self.researcher.websocket,
            )

        return introduction

    async def get_subtopics(self):
        """Retrieve subtopics for the research."""
        if self.researcher.verbose:
            await stream_output(
                "logs",
                "generating_subtopics",
                f"🌳 Generating subtopics for '{self.researcher.query}'...",
                self.researcher.websocket,
            )

        # Ensure researcher is in kwargs for token tracking
        kwargs_with_researcher = self.researcher.kwargs.copy()
        kwargs_with_researcher["researcher"] = self.researcher

        subtopics = await construct_subtopics(
            task=self.researcher.query,
            data=self.researcher.context,
            config=self.researcher.cfg,
            subtopics=self.researcher.subtopics,
            prompt_family=self.researcher.prompt_family,
            **kwargs_with_researcher
        )

        if self.researcher.verbose:
            await stream_output(
                "logs",
                "subtopics_generated",
                f"📊 Subtopics generated for '{self.researcher.query}'",
                self.researcher.websocket,
            )

        return subtopics

    async def get_draft_section_titles(self, current_subtopic: str):
        """Generate draft section titles for the report."""
        if self.researcher.verbose:
            await stream_output(
                "logs",
                "generating_draft_sections",
                f"📑 Generating draft section titles for '{self.researcher.query}'...",
                self.researcher.websocket,
            )

        # Ensure researcher is in kwargs for token tracking
        kwargs_with_researcher = self.researcher.kwargs.copy()
        kwargs_with_researcher["researcher"] = self.researcher

        draft_section_titles = await generate_draft_section_titles(
            query=self.researcher.query,
            current_subtopic=current_subtopic,
            context=self.researcher.context,
            role=self.researcher.cfg.agent_role or self.researcher.role,
            websocket=self.researcher.websocket,
            config=self.researcher.cfg,
            cost_callback=self.researcher.add_costs,
            prompt_family=self.researcher.prompt_family,
            **kwargs_with_researcher
        )

        if self.researcher.verbose:
            await stream_output(
                "logs",
                "draft_sections_generated",
                f"🗂️ Draft section titles generated for '{self.researcher.query}'",
                self.researcher.websocket,
            )

        return draft_section_titles
