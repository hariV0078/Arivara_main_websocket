from typing import List, Dict, Any, Optional, Set
import asyncio
import logging
import time
from datetime import datetime, timedelta

from arivara_researcher.llm_provider.generic.base import ReasoningEfforts
from ..utils.llm import create_chat_completion
from ..utils.enum import ReportType, ReportSource, Tone
from ..actions.query_processing import get_search_results

logger = logging.getLogger(__name__)

# Maximum words allowed in context (50k words for deep research to ensure comprehensive reports)
# This is higher than regular research to allow for the extensive context from deep research
MAX_CONTEXT_WORDS = 50000

def count_words(text: str) -> int:
    """Count words in a text string"""
    return len(text.split())

def trim_context_to_word_limit(context_list: List[str], max_words: int = MAX_CONTEXT_WORDS) -> List[str]:
    """Trim context list to stay within word limit while preserving most recent/relevant items"""
    total_words = 0
    trimmed_context = []

    # Process in reverse to keep most recent items
    for item in reversed(context_list):
        words = count_words(item)
        if total_words + words <= max_words:
            trimmed_context.insert(0, item)  # Insert at start to maintain original order
            total_words += words
        else:
            break

    return trimmed_context

class ResearchProgress:
    def __init__(self, total_depth: int, total_breadth: int):
        self.current_depth = 1  # Start from 1 and increment up to total_depth
        self.total_depth = total_depth
        self.current_breadth = 0  # Start from 0 and count up to total_breadth as queries complete
        self.total_breadth = total_breadth
        self.current_query: Optional[str] = None
        self.total_queries = 0
        self.completed_queries = 0


class DeepResearchSkill:
    def __init__(self, researcher):
        self.researcher = researcher
        self.breadth = getattr(researcher.cfg, 'deep_research_breadth', 4)
        self.depth = getattr(researcher.cfg, 'deep_research_depth', 2)
        self.concurrency_limit = getattr(researcher.cfg, 'deep_research_concurrency', 2)
        self.websocket = researcher.websocket
        self.tone = researcher.tone
        self.config_path = researcher.cfg.config_path if hasattr(researcher.cfg, 'config_path') else None
        self.headers = researcher.headers or {}
        self.visited_urls = researcher.visited_urls
        self.learnings = []
        self.research_sources = []  # Track all research sources
        self.context = []  # Track all context

    async def generate_search_queries(self, query: str, num_queries: int = 3) -> List[Dict[str, str]]:
        """Generate SERP queries for research"""
        messages = [
            {"role": "system", "content": "You are an expert researcher generating search queries."},
            {"role": "user",
             "content": f"Given the following prompt, generate {num_queries} unique search queries to research the topic thoroughly. For each query, provide a research goal. Format as 'Query: <query>' followed by 'Goal: <goal>' for each pair: {query}"}
        ]

        # Use the parent researcher's token_tracker
        token_tracker = self.researcher.token_tracker if hasattr(self.researcher, 'token_tracker') else None
        
        response = await create_chat_completion(
            messages=messages,
            llm_provider=self.researcher.cfg.strategic_llm_provider,
            model=self.researcher.cfg.strategic_llm_model,
            reasoning_effort=self.researcher.cfg.reasoning_effort,
            temperature=0.4,
            token_tracker=token_tracker
        )
        
        # DEBUG: Log usage (user-requested debug output)
        if token_tracker:
            usage_summary = token_tracker.summary()
            print(f"DEBUG: Deep Research generate_search_queries usage: {usage_summary}")

        lines = response.split('\n')
        queries = []
        current_query = {}

        for line in lines:
            line = line.strip()
            if line.startswith('Query:'):
                if current_query:
                    queries.append(current_query)
                current_query = {'query': line.replace('Query:', '').strip()}
            elif line.startswith('Goal:') and current_query:
                current_query['researchGoal'] = line.replace('Goal:', '').strip()

        if current_query:
            queries.append(current_query)

        return queries[:num_queries]

    async def generate_research_plan(self, query: str, num_questions: int = 3) -> List[str]:
        """Generate follow-up questions to clarify research direction"""
        # Get initial search results to inform query generation
        # Pass the researcher so MCP retriever receives cfg and mcp_configs
        search_results = await get_search_results(
            query,
            self.researcher.retrievers[0],
            researcher=self.researcher
        )
        logger.info(f"Initial web knowledge obtained: {len(search_results)} results")

        # Get current time for context
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        messages = [
            {"role": "system", "content": "You are an expert researcher. Your task is to analyze the original query and search results, then generate targeted questions that explore different aspects and time periods of the topic."},
            {"role": "user",
             "content": f"""Original query: {query}

Current time: {current_time}

Search results:
{search_results}

Based on these results, the original query, and the current time, generate {num_questions} unique questions. Each question should explore a different aspect or time period of the topic, considering recent developments up to {current_time}.

Format each question on a new line starting with 'Question: '"""}
        ]

        # Use the parent researcher's token_tracker
        token_tracker = self.researcher.token_tracker if hasattr(self.researcher, 'token_tracker') else None
        
        response = await create_chat_completion(
            messages=messages,
            llm_provider=self.researcher.cfg.strategic_llm_provider,
            model=self.researcher.cfg.strategic_llm_model,
            reasoning_effort=ReasoningEfforts.High.value,
            temperature=0.4,
            token_tracker=token_tracker
        )
        
        # DEBUG: Log usage (user-requested debug output)
        if token_tracker:
            usage_summary = token_tracker.summary()
            print(f"DEBUG: Deep Research generate_research_plan usage: {usage_summary}")

        questions = [q.replace('Question:', '').strip()
                     for q in response.split('\n')
                     if q.strip().startswith('Question:')]
        return questions[:num_questions]

    async def process_research_results(self, query: str, context: str, num_learnings: int = 3) -> Dict[str, List[str]]:
        """Process research results to extract learnings and follow-up questions"""
        messages = [
            {"role": "system", "content": "You are an expert researcher analyzing search results."},
            {"role": "user",
             "content": f"Given the following research results for the query '{query}', extract key learnings and suggest follow-up questions. For each learning, include a citation to the source URL if available. Format each learning as 'Learning [source_url]: <insight>' and each question as 'Question: <question>':\n\n{context}"}
        ]

        # Use the parent researcher's token_tracker
        token_tracker = self.researcher.token_tracker if hasattr(self.researcher, 'token_tracker') else None
        
        response = await create_chat_completion(
            messages=messages,
            llm_provider=self.researcher.cfg.strategic_llm_provider,
            model=self.researcher.cfg.strategic_llm_model,
            temperature=0.4,
            reasoning_effort=ReasoningEfforts.High.value,
            max_tokens=1000,
            token_tracker=token_tracker
        )
        
        # DEBUG: Log usage (user-requested debug output)
        if token_tracker:
            usage_summary = token_tracker.summary()
            print(f"DEBUG: Deep Research process_research_results usage: {usage_summary}")

        lines = response.split('\n')
        learnings = []
        questions = []
        citations = {}

        for line in lines:
            line = line.strip()
            if line.startswith('Learning'):
                import re
                url_match = re.search(r'\[(.*?)\]:', line)
                if url_match:
                    url = url_match.group(1)
                    learning = line.split(':', 1)[1].strip()
                    learnings.append(learning)
                    citations[learning] = url
                else:
                    # Try to find URL in the line itself
                    url_match = re.search(
                        r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', line)
                    if url_match:
                        url = url_match.group(0)
                        learning = line.replace(url, '').replace('Learning:', '').strip()
                        learnings.append(learning)
                        citations[learning] = url
                    else:
                        learnings.append(line.replace('Learning:', '').strip())
            elif line.startswith('Question:'):
                questions.append(line.replace('Question:', '').strip())

        return {
            'learnings': learnings[:num_learnings],
            'followUpQuestions': questions[:num_learnings],
            'citations': citations
        }

    async def deep_research(
            self,
            query: str,
            breadth: int,
            depth: int,
            learnings: List[str] = None,
            citations: Dict[str, str] = None,
            visited_urls: Set[str] = None,
            on_progress=None
    ) -> Dict[str, Any]:
        """Conduct deep iterative research"""
        print(f"\n📊 DEEP RESEARCH: depth={depth}, breadth={breadth}, query={query[:100]}...", flush=True)
        if learnings is None:
            learnings = []
        if citations is None:
            citations = {}
        if visited_urls is None:
            visited_urls = set()

        progress = ResearchProgress(depth, breadth)

        if on_progress:
            on_progress(progress)

        # Generate search queries
        print(f"🔎 Generating {breadth} search queries...", flush=True)
        serp_queries = await self.generate_search_queries(query, num_queries=breadth)
        print(f"✅ Generated {len(serp_queries)} queries: {[q['query'] for q in serp_queries]}", flush=True)
        progress.total_queries = len(serp_queries)

        all_learnings = learnings.copy()
        all_citations = citations.copy()
        all_visited_urls = visited_urls.copy()
        all_context = []
        all_sources = []

        # Process queries with concurrency limit
        semaphore = asyncio.Semaphore(self.concurrency_limit)

        async def process_query(serp_query: Dict[str, str]) -> Optional[Dict[str, Any]]:
            async with semaphore:
                try:
                    progress.current_query = serp_query['query']
                    if on_progress:
                        on_progress(progress)

                    from .. import Arivara_researcher
                    researcher = Arivara_researcher(
                        query=serp_query['query'],
                        report_type=ReportType.ResearchReport.value,
                        report_source=ReportSource.Web.value,
                        tone=self.tone,
                        websocket=self.websocket,
                        config_path=self.config_path,
                        headers=self.headers,
                        visited_urls=self.visited_urls,
                        # Propagate MCP configuration to nested researchers
                        mcp_configs=self.researcher.mcp_configs,
                        mcp_strategy=self.researcher.mcp_strategy
                    )
                    
                    # CRITICAL: Use the parent researcher's token_tracker instead of creating a new one
                    # This ensures all subquery calls contribute to the same TokenMeter instance
                    if hasattr(self.researcher, 'token_tracker') and self.researcher.token_tracker:
                        researcher.token_tracker = self.researcher.token_tracker
                        logger.debug(f"Using parent researcher's token_tracker for nested researcher (query: {serp_query['query'][:50]})")
                    else:
                        logger.warning(f"Parent researcher does not have token_tracker - nested researcher will use its own tracker")

                    # Conduct research
                    context = await researcher.conduct_research()

                    # Get results and visited URLs
                    visited = researcher.visited_urls
                    sources = researcher.research_sources

                    # Process results to extract learnings and citations
                    results = await self.process_research_results(
                        query=serp_query['query'],
                        context=context
                    )

                    # Update progress
                    progress.completed_queries += 1
                    progress.current_breadth += 1
                    if on_progress:
                        on_progress(progress)

                    return {
                        'learnings': results['learnings'],
                        'visited_urls': list(visited),
                        'followUpQuestions': results['followUpQuestions'],
                        'researchGoal': serp_query['researchGoal'],
                        'citations': results['citations'],
                        'context': context if context else "",
                        'sources': sources if sources else []
                    }

                except Exception as e:
                    import traceback
                    error_details = traceback.format_exc()
                    logger.error(f"Error processing query '{serp_query['query']}': {str(e)}")
                    print(f"\n❌ DEEP RESEARCH ERROR: {str(e)}\n{error_details}", flush=True)
                    return None

        # Process queries concurrently with limit
        tasks = [process_query(query) for query in serp_queries]
        results = await asyncio.gather(*tasks)
        results = [r for r in results if r is not None]

        # Update breadth progress based on successful queries
        progress.current_breadth = len(results)
        if on_progress:
            on_progress(progress)

        # Collect all results from current depth level
        for result in results:
            all_learnings.extend(result['learnings'])
            all_visited_urls.update(result['visited_urls'])
            all_citations.update(result['citations'])
            if result['context']:
                all_context.append(result['context'])
            if result['sources']:
                all_sources.extend(result['sources'])

        # Continue to next depth level only once (not for each result)
        # This prevents exponential growth and infinite loops
        if depth > 1 and len(results) > 0:
            new_breadth = max(2, breadth // 2)
            new_depth = depth - 1
            progress.current_depth += 1
            
            logger.info(f"Continuing to depth {new_depth} with breadth {new_breadth} (current depth: {depth})")
            
            # Combine all follow-up questions and research goals from current level
            all_follow_up_questions = []
            all_research_goals = []
            for result in results:
                if result.get('followUpQuestions'):
                    all_follow_up_questions.extend(result['followUpQuestions'])
                if result.get('researchGoal'):
                    all_research_goals.append(result['researchGoal'])
            
            # Create combined query for next depth level from all current results
            # Limit to avoid excessive queries
            combined_follow_ups = ' '.join(all_follow_up_questions[:5])  # Max 5 follow-up questions
            combined_goals = '; '.join(all_research_goals[:3])  # Max 3 research goals
            
            next_query = f"""
            Previous research goals: {combined_goals}
            Key follow-up questions: {combined_follow_ups}
            Continue research based on these findings.
            """

            # Recursive research - only called once per depth level
            deeper_results = await self.deep_research(
                query=next_query,
                breadth=new_breadth,
                depth=new_depth,
                learnings=all_learnings,
                citations=all_citations,
                visited_urls=all_visited_urls,
                on_progress=on_progress
            )

            # Merge deeper results
            all_learnings.extend(deeper_results['learnings'])
            all_visited_urls.update(deeper_results['visited_urls'])
            all_citations.update(deeper_results['citations'])
            if deeper_results.get('context'):
                all_context.extend(deeper_results['context'])
            if deeper_results.get('sources'):
                all_sources.extend(deeper_results['sources'])

        # Update class tracking
        self.context.extend(all_context)
        self.research_sources.extend(all_sources)

        # Don't trim here - return full context and trim only once at the end in run()
        # This ensures we preserve all research context until final report generation
        logger.info(f"Collected {len(all_context)} context items, {len(all_learnings)} learnings, {len(all_sources)} sources")

        return {
            'learnings': list(set(all_learnings)),
            'visited_urls': list(all_visited_urls),
            'citations': all_citations,
            'context': all_context,  # Return full context, not trimmed
            'sources': all_sources
        }

    async def run(self, on_progress=None) -> str:
        """Run the deep research process and generate final report"""
        print(f"\n🔍 DEEP RESEARCH: Starting with breadth={self.breadth}, depth={self.depth}, concurrency={self.concurrency_limit}", flush=True)
        start_time = time.time()

        # Log initial costs
        initial_costs = self.researcher.get_costs()

        follow_up_questions = await self.generate_research_plan(self.researcher.query)
        answers = ["Automatically proceeding with research"] * len(follow_up_questions)

        qa_pairs = [f"Q: {q}\nA: {a}" for q, a in zip(follow_up_questions, answers)]
        combined_query = f"""
        Initial Query: {self.researcher.query}\nFollow - up Questions and Answers:\n
        """ + "\n".join(qa_pairs)

        results = await self.deep_research(
            query=combined_query,
            breadth=self.breadth,
            depth=self.depth,
            on_progress=on_progress
        )

        # Get costs after deep research
        research_costs = self.researcher.get_costs() - initial_costs

        # Log research costs if we have a log handler
        if self.researcher.log_handler:
            await self.researcher._log_event("research", step="deep_research_costs", details={
                "research_costs": research_costs,
                "total_costs": self.researcher.get_costs()
            })

        # Prepare context with citations
        context_with_citations = []
        
        # Add learnings with citations first (these are key insights)
        for learning in results['learnings']:
            citation = results['citations'].get(learning, '')
            if citation:
                context_with_citations.append(f"{learning} [Source: {citation}]")
            else:
                context_with_citations.append(learning)

        # Add all research context (full context from all research iterations)
        if results.get('context'):
            # results['context'] is a list of context strings
            if isinstance(results['context'], list):
                context_with_citations.extend(results['context'])
            else:
                # If it's a string, split by newlines or add as single item
                context_with_citations.append(results['context'])

        # Log context size before trimming
        total_words_before = sum(count_words(item) for item in context_with_citations)
        logger.info(f"Total context before trimming: {len(context_with_citations)} items, ~{total_words_before} words")

        # Trim final context to word limit (only trim once, at the end)
        # Use a higher limit for deep research to ensure comprehensive reports
        final_context = trim_context_to_word_limit(context_with_citations, max_words=MAX_CONTEXT_WORDS)
        
        total_words_after = sum(count_words(item) for item in final_context)
        logger.info(f"Total context after trimming: {len(final_context)} items, ~{total_words_after} words")
        
        # Set enhanced context and visited URLs
        self.researcher.context = "\n".join(final_context)
        self.researcher.visited_urls = results['visited_urls']

        # Set research sources
        if results.get('sources'):
            self.researcher.research_sources = results['sources']

        # Log total execution time
        end_time = time.time()
        execution_time = timedelta(seconds=end_time - start_time)
        logger.info(f"Total research execution time: {execution_time}")
        logger.info(f"Total research costs: ${research_costs:.2f}")

        # Return the context - don't generate report here as it will be done by the main agent
        return self.researcher.context
