"""Handle research completion tasks: document storage, credit updates, status tracking."""

import os
import logging
import urllib.parse
from uuid import UUID
from typing import Optional, Dict, Any
from backend.services.research_history import ResearchHistoryService
from backend.services.document_storage import DocumentStorageService
from backend.services.credit_service import CreditService
from backend.utils import write_md_to_pdf, write_md_to_word

logger = logging.getLogger(__name__)


async def _handle_research_completion(
    websocket,
    research_id: str,
    user_id: str,
    report: str,
    sanitized_filename: str,
    report_type: str,
    token_usage: Optional[Dict[str, Any]] = None
) -> None:
    """
    Handle research completion: store documents, update credits, update status.
    
    Args:
        websocket: WebSocket connection
        research_id: Research UUID string
        user_id: User UUID string
        report: Generated report content
        sanitized_filename: Sanitized filename for documents
        report_type: Type of report generated
        token_usage: Optional token usage dictionary from researcher
    """
    try:
        research_id_uuid = UUID(research_id)
        user_id_uuid = UUID(user_id)
        
        logger.info(f"Handling research completion for research_id={research_id}, report_length={len(report) if report else 0}, token_usage_provided={token_usage is not None}")
        
        history_service = ResearchHistoryService()
        document_service = DocumentStorageService()
        credit_service = CreditService()
        
        # Generate document files
        documents = []
        try:
            # Check if report is empty
            if not report or not report.strip():
                logger.warning(f"Report is empty for research {research_id}, skipping document generation")
            else:
                docx_path = await write_md_to_word(report, sanitized_filename)
                pdf_path = await write_md_to_pdf(report, sanitized_filename)
                
                logger.info(f"Document generation - DOCX path: {docx_path}, PDF path: {pdf_path}")
                
                # Upload documents to Supabase Storage
                # Note: write_md_to_word and write_md_to_pdf return URL-encoded paths
                # We need to decode them before checking file existence
                
                if docx_path and docx_path.strip():
                    # Decode URL-encoded path
                    docx_decoded_path = urllib.parse.unquote(docx_path)
                    # Check if file exists (handle both relative and absolute paths)
                    docx_full_path = docx_decoded_path if os.path.isabs(docx_decoded_path) else os.path.join(os.getcwd(), docx_decoded_path.lstrip('/'))
                    if os.path.exists(docx_full_path):
                        try:
                            doc_docx = await document_service.upload_document(
                                research_id_uuid,
                                docx_full_path,
                                file_name=f"{sanitized_filename}.docx",
                                file_type="docx"
                            )
                            if doc_docx:
                                documents.append(doc_docx)
                                logger.info(f"Successfully uploaded DOCX document for research {research_id}")
                            else:
                                logger.warning(f"Document upload returned None for DOCX: {docx_full_path}")
                        except Exception as e:
                            logger.error(f"Error uploading DOCX document: {e}", exc_info=True)
                    else:
                        logger.warning(f"DOCX file does not exist at path: {docx_full_path} (original: {docx_path}, decoded: {docx_decoded_path})")
                
                if pdf_path and pdf_path.strip():
                    # Decode URL-encoded path
                    pdf_decoded_path = urllib.parse.unquote(pdf_path)
                    # Check if file exists (handle both relative and absolute paths)
                    pdf_full_path = pdf_decoded_path if os.path.isabs(pdf_decoded_path) else os.path.join(os.getcwd(), pdf_decoded_path.lstrip('/'))
                    if os.path.exists(pdf_full_path):
                        try:
                            doc_pdf = await document_service.upload_document(
                                research_id_uuid,
                                pdf_full_path,
                                file_name=f"{sanitized_filename}.pdf",
                                file_type="pdf"
                            )
                            if doc_pdf:
                                documents.append(doc_pdf)
                                logger.info(f"Successfully uploaded PDF document for research {research_id}")
                            else:
                                logger.warning(f"Document upload returned None for PDF: {pdf_full_path}")
                        except Exception as e:
                            logger.error(f"Error uploading PDF document: {e}", exc_info=True)
                    else:
                        logger.warning(f"PDF file does not exist at path: {pdf_full_path} (original: {pdf_path}, decoded: {pdf_decoded_path})")
        except Exception as e:
            logger.error(f"Error during document generation/upload: {e}", exc_info=True)
        
        logger.info(f"Total documents uploaded: {len(documents)} for research {research_id}")
        
        # ============================================================================
        # CREDIT LOGIC TEMPORARILY DISABLED
        # ============================================================================
        # Credit deduction and checking logic has been commented out per requirements.
        # The credit-related database models and fields remain intact.
        # To re-enable: uncomment the code below and restore credit checking in websocket_handler.py
        # ============================================================================
        
        # Get research entry for metadata
        research_entry = await history_service.get_research_by_id(research_id_uuid)
        report_type_from_db = research_entry.get("report_type", "research_report") if research_entry else "research_report"
        
        # Use token_usage from parameter if provided, otherwise try to get from database
        if not token_usage and research_entry:
            token_usage = research_entry.get("token_usage")
        
        # Log token usage for debugging
        if token_usage:
            logger.info(f"Token usage received: {token_usage} for research {research_id}")
        else:
            logger.warning(f"No token usage available for research {research_id} (not in parameter or database)")
        
        # COMMENTED OUT: Credit calculation and deduction logic
        # actual_credits = 0
        # if token_usage and isinstance(token_usage, dict) and token_usage.get('total_tokens', 0) > 0:
        #     # Use token-based calculation (1M tokens = 4500 credits)
        #     actual_credits = credit_service.calculate_credits_from_token_usage(token_usage)
        #     logger.info(f"Calculated credits from token usage: {actual_credits} credits for {token_usage.get('total_tokens', 0)} tokens")
        # else:
        #     # Fallback to report length-based calculation
        #     report_length = len(report)
        #     actual_credits = credit_service.calculate_research_cost(report_type_from_db, report_length)
        #     logger.info(f"Calculated credits from report length: {actual_credits} credits for {report_length} chars")
        # 
        # # Check if user still has enough credits (in case balance changed during research)
        # user_credits = await credit_service.get_credit_balance(user_id_uuid)
        # if user_credits < actual_credits:
        #     logger.warning(f"User {user_id} has insufficient credits ({user_credits}) for completed research ({actual_credits})")
        #     # Still complete the research, but log the issue
        #     actual_credits = user_credits  # Deduct what's available
        # 
        # # Deduct credits now that research is complete
        # if actual_credits > 0:
        #     success = await credit_service.deduct_credits(
        #         user_id_uuid,
        #         actual_credits,
        #         f"Research completed: {research_entry.get('query', 'N/A')[:50] if research_entry else 'N/A'}"
        #     )
        #     
        #     if not success:
        #         logger.error(f"Failed to deduct {actual_credits} credits for completed research {research_id}")
        #         # Still mark as completed, but log the error
        #         actual_credits = 0
        # else:
        #     logger.warning(f"No credits to deduct for research {research_id}")
        # 
        # # Send credit update
        # new_balance = await credit_service.get_credit_balance(user_id_uuid)
        # await websocket.send_json({
        #     "type": "credit_update",
        #     "credits": new_balance,
        #     "used": actual_credits,
        #     "description": "Research completed"
        # })
        
        actual_credits = 0  # Set to 0 since credits are disabled
        
        # Update research status to completed (store token_usage in database)
        # Note: actual_credits is set to 0 since credit logic is disabled
        result_summary = f"Report generated successfully. {len(documents)} document(s) created."
        await history_service.update_research_status(
            research_id_uuid,
            "completed",
            result_summary,
            actual_credits,  # 0 since credits are disabled
            token_usage  # Store token usage in database
        )
        
        # Prepare token usage for response (ensure all fields are present)
        token_usage_response = None
        logger.info(f"Preparing token usage for response. Input token_usage type: {type(token_usage)}, value: {token_usage}")
        
        if token_usage and isinstance(token_usage, dict):
            # Extract token usage values (handle both naming conventions)
            prompt_tokens = token_usage.get("prompt_tokens") or token_usage.get("total_prompt_tokens", 0)
            completion_tokens = token_usage.get("completion_tokens") or token_usage.get("total_completion_tokens", 0)
            total_tokens = token_usage.get("total_tokens", 0)
            call_count = token_usage.get("call_count", 0)
        
            # If total_tokens is 0 but we have prompt/completion, calculate it
            if total_tokens == 0 and (prompt_tokens > 0 or completion_tokens > 0):
                total_tokens = prompt_tokens + completion_tokens
            
            token_usage_response = {
                "total_prompt_tokens": prompt_tokens,
                "total_completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "call_count": call_count
            }
            logger.info(f"✅ Token usage prepared: {token_usage_response}")
        else:
            logger.warning(f"⚠️ Token usage is None or not a dict: {token_usage}")
        
        # ============================================================================
        # SINGLE CONSOLIDATED RESPONSE
        # ============================================================================
        # Send ONE final response at the end - no streaming or intermediate responses.
        # This response contains:
        # - research_id: The research task ID
        # - documents: Final report files (PDF/DOCX) generated from research
        # - token_usage: Complete token usage across ALL API calls during research
        # ============================================================================
        # NOTE: Current documents array contains final report files (PDF/DOCX).
        # To include scraped web content (title, url, content, relevance_score, source_query),
        # additional implementation is needed to track scraped documents during research.
        # See RESEARCH_RESPONSE_CHANGES.md for details.
        # ============================================================================
        completion_message = {
            "type": "research_complete",
            "research_id": research_id,
            "documents": [
                {
                    "id": doc["id"],
                    "name": doc["file_name"],
                    "url": doc["file_path"],
                    "type": doc["file_type"]
                }
                for doc in documents
            ]
        }
        
        # Add token usage to response if available (required field)
        if token_usage_response and token_usage_response.get("total_tokens", 0) > 0:
            completion_message["token_usage"] = token_usage_response
        else:
            # Include empty token_usage if not available
            completion_message["token_usage"] = {
                "total_prompt_tokens": 0,
                "total_completion_tokens": 0,
                "total_tokens": 0,
                "call_count": 0
            }
        
        await websocket.send_json(completion_message)
        
        logger.info(f"Research {research_id} completed successfully for user {user_id}")
        
    except Exception as e:
        logger.error(f"Error handling research completion: {e}", exc_info=True)
        # Try to update status to failed
        try:
            history_service = ResearchHistoryService()
            await history_service.update_research_status(
                UUID(research_id),
                "failed",
                f"Completion handling failed: {str(e)}"
            )
        except:
            pass

