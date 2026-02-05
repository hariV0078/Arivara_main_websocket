"""Document storage service for research documents."""

from typing import Optional, List, Dict, Any
from uuid import UUID
from pathlib import Path
import os
import logging
from supabase import Client
from ..auth.supabase_client import get_service_client
from ..models.research import ResearchDocument, ResearchDocumentCreate

logger = logging.getLogger(__name__)


class DocumentStorageService:
    """Service for managing research documents."""
    
    def __init__(self, client: Optional[Client] = None, storage_bucket: str = "research-documents"):
        """
        Initialize DocumentStorageService.
        
        Args:
            client: Optional Supabase client (uses service client by default)
            storage_bucket: Supabase storage bucket name
        """
        self.client = client or get_service_client()
        self.storage_bucket = storage_bucket
    
    async def upload_document(
        self,
        research_id: UUID,
        file_path: str,
        file_name: Optional[str] = None,
        file_type: str = "pdf"
    ) -> Optional[Dict[str, Any]]:
        """
        Upload document to Supabase Storage and create database entry.
        
        Args:
            research_id: Research UUID
            file_path: Local file path
            file_name: Optional custom file name
            file_type: File type (pdf, docx, markdown)
            
        Returns:
            Document dictionary if successful, None otherwise
        """
        try:
            # Read file
            if not os.path.exists(file_path):
                logger.error(f"File not found: {file_path}")
                return None
            
            with open(file_path, "rb") as f:
                file_data = f.read()
            
            # Generate file name if not provided
            if not file_name:
                file_name = os.path.basename(file_path)
            
            # Sanitize file name
            file_name = self._sanitize_filename(file_name)
            
            # Storage path: research-documents/{research_id}/{file_name}
            storage_path = f"{research_id}/{file_name}"
            
            # Upload to Supabase Storage
            self.client.storage.from_(self.storage_bucket).upload(
                path=storage_path,
                file=file_data,
                file_options={"content-type": self._get_content_type(file_type)}
            )
            
            # Get file size
            file_size = len(file_data)
            
            # Get public URL
            file_url = self.client.storage.from_(self.storage_bucket).get_public_url(storage_path)
            
            # Create database entry
            document = ResearchDocumentCreate(
                research_id=research_id,
                file_name=file_name,
                file_path=file_url,  # Store public URL
                file_type=file_type,
                file_size=file_size
            )
            
            result = self.client.table("research_documents").insert(document.dict()).execute()
            
            if result.data and len(result.data) > 0:
                logger.info(f"Uploaded document {file_name} for research {research_id}")
                return result.data[0]
            return None
            
        except Exception as e:
            logger.error(f"Error uploading document: {e}")
            return None
    
    async def get_document_url(
        self,
        research_id: UUID,
        file_name: str
    ) -> Optional[str]:
        """
        Get document URL by research ID and file name.
        
        Args:
            research_id: Research UUID
            file_name: File name
            
        Returns:
            Document URL or None
        """
        try:
            result = (
                self.client.table("research_documents")
                .select("file_path")
                .eq("research_id", str(research_id))
                .eq("file_name", file_name)
                .execute()
            )
            
            if result.data and len(result.data) > 0:
                return result.data[0].get("file_path")
            return None
            
        except Exception as e:
            logger.error(f"Error getting document URL: {e}")
            return None
    
    async def list_research_documents(
        self,
        research_id: UUID
    ) -> List[Dict[str, Any]]:
        """
        List all documents for a research entry.
        
        Args:
            research_id: Research UUID
            
        Returns:
            List of document dictionaries
        """
        try:
            result = (
                self.client.table("research_documents")
                .select("*")
                .eq("research_id", str(research_id))
                .order("created_at", desc=True)
                .execute()
            )
            
            return result.data or []
            
        except Exception as e:
            logger.error(f"Error listing documents: {e}")
            return []
    
    async def delete_document(
        self,
        document_id: UUID
    ) -> bool:
        """
        Delete document from storage and database.
        
        Args:
            document_id: Document UUID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get document info
            result = (
                self.client.table("research_documents")
                .select("*")
                .eq("id", str(document_id))
                .execute()
            )
            
            if not result.data or len(result.data) == 0:
                return False
            
            document = result.data[0]
            storage_path = f"{document['research_id']}/{document['file_name']}"
            
            # Delete from storage
            self.client.storage.from_(self.storage_bucket).remove([storage_path])
            
            # Delete from database
            self.client.table("research_documents").delete().eq("id", str(document_id)).execute()
            
            logger.info(f"Deleted document {document_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting document: {e}")
            return False
    
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for storage."""
        # Remove path components
        filename = os.path.basename(filename)
        # Remove special characters
        filename = "".join(c for c in filename if c.isalnum() or c in "._-")
        return filename
    
    def _get_content_type(self, file_type: str) -> str:
        """Get content type for file type."""
        content_types = {
            "pdf": "application/pdf",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "markdown": "text/markdown",
        }
        return content_types.get(file_type, "application/octet-stream")

