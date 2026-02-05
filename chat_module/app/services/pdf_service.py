from typing import List

import httpx
from pypdf import PdfReader
from io import BytesIO


class PDFService:
    """
    Service to fetch PDFs from URLs and extract text for use as LLM context.
    """

    async def fetch_and_extract_text(self, pdf_urls: List[str], max_chars: int = 8000) -> str:
        """
        Download PDFs from the given URLs and extract their text.

        The extracted text is concatenated and truncated to max_chars to keep prompts manageable.
        """
        if not pdf_urls:
            return ""

        combined_texts: List[str] = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            for url in pdf_urls:
                try:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    pdf_bytes = resp.content

                    reader = PdfReader(BytesIO(pdf_bytes))
                    pages_text: List[str] = []
                    for page in reader.pages:
                        try:
                            page_text = page.extract_text() or ""
                        except Exception:
                            page_text = ""
                        if page_text:
                            pages_text.append(page_text.strip())

                    if pages_text:
                        doc_text = "\n\n".join(pages_text)
                        combined_texts.append(f"PDF: {url}\n{doc_text}")
                except Exception as e:
                    # Skip PDFs that fail to download/parse, but continue with others
                    combined_texts.append(f"PDF: {url}\n[Failed to extract text: {e}]")

        full_text = "\n\n---\n\n".join(combined_texts)
        if len(full_text) > max_chars:
            return full_text[: max_chars] + "\n\n[Truncated PDF content]"
        return full_text

