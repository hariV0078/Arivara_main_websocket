import aiofiles
import urllib.parse
import mistune
import requests
import tempfile
import os

async def write_to_file(filename: str, text: str) -> None:
    """Asynchronously write text to a file in UTF-8 encoding.

    Args:
        filename (str): The filename to write to.
        text (str): The text to write.
    """
    # Ensure text is a string
    if not isinstance(text, str):
        text = str(text)

    # Convert text to UTF-8, replacing any problematic characters
    text_utf8 = text.encode('utf-8', errors='replace').decode('utf-8')

    async with aiofiles.open(filename, "w", encoding='utf-8') as file:
        await file.write(text_utf8)

async def write_text_to_md(text: str, filename: str = "") -> str:
    """Writes text to a Markdown file and returns the file path.

    Args:
        text (str): Text to write to the Markdown file.

    Returns:
        str: The file path of the generated Markdown file.
    """
    file_path = f"outputs/{filename[:60]}.md"
    await write_to_file(file_path, text)
    return urllib.parse.quote(file_path)

async def write_md_to_pdf(text: str, filename: str = "") -> str:
    """Converts Markdown text to a PDF file and returns the file path.

    The function first attempts to use ConvertAPI. If that fails (e.g., empty
    payload, network issues, or API errors), it falls back to a local PDF
    generator powered by ``fpdf``.

    Args:
        text (str): Markdown text to convert.

    Returns:
        str: The encoded file path of the generated PDF, or an empty string on failure.
    """
    file_path = f"outputs/{filename[:60]}.pdf"

    # Skip conversion when there is no content.
    if not text.strip():
        print("PDF generation skipped: report content is empty.")
        return ""

    # --- Attempt ConvertAPI first -------------------------------------------------
    try:
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.md', delete=False, encoding='utf-8') as md_file:
            md_file.write(text)
            md_file_path = md_file.name

        api_key = "bn7K3wvxTumu2Wrp1WcEt3IMf4rB864K"
        url = "https://v2.convertapi.com/convert/md/to/pdf"

        headers = {"Authorization": f"Bearer {api_key}"}
        files = {
            "File": (os.path.basename(md_file_path), open(md_file_path, 'rb'), 'text/markdown')
        }
        data = {"StoreFile": "true"}

        response = requests.post(url, headers=headers, files=files, data=data, timeout=30)

        try:
            os.unlink(md_file_path)
        except PermissionError:
            pass

        if response.status_code == 200:
            try:
                response_data = response.json()
                if response_data.get('Files'):
                    pdf_url = response_data['Files'][0]['Url']
                    pdf_response = requests.get(pdf_url, timeout=30)
                    if pdf_response.status_code == 200:
                        with open(file_path, 'wb') as pdf_file:
                            pdf_file.write(pdf_response.content)
                        print(f"Report written to {file_path}")
                        return urllib.parse.quote(file_path)
                    print(f"Failed to download PDF from URL: {pdf_response.status_code}")
                else:
                    print("No PDF file found in ConvertAPI response")
            except Exception as parse_err:
                print(f"Error parsing ConvertAPI response: {parse_err}")
        else:
            print(f"ConvertAPI error: {response.status_code} - {response.text}")

    except Exception as api_err:
        print(f"Error in ConvertAPI PDF conversion: {api_err}")

    # --- Fallback: local PDF generation using fpdf --------------------------------
    return _generate_pdf_fallback(text, file_path)


def _generate_pdf_fallback(text: str, file_path: str) -> str:
    """Generate a simple PDF locally using fpdf as a fallback."""
    try:
        from fpdf import FPDF
    except ImportError:
        print("FPDF fallback not available. Install 'fpdf2' to enable local PDF generation.")
        return ""

    try:
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        pdf.set_font("Arial", size=12)

        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                pdf.ln(5)
                continue

            if stripped.startswith("#"):
                level = len(stripped) - len(stripped.lstrip('#'))
                heading_text = stripped[level:].strip()
                font_size = max(18 - (level - 1) * 2, 12)
                pdf.set_font("Arial", "B", font_size)
                pdf.multi_cell(0, 10, heading_text)
                pdf.ln(2)
                pdf.set_font("Arial", size=12)
            else:
                pdf.multi_cell(0, 8, line)

        pdf.output(file_path)
        print(f"Report written to {file_path} (fallback)")
        return urllib.parse.quote(file_path)

    except Exception as fallback_err:
        print(f"Fallback PDF generation failed: {fallback_err}")
        return ""

async def write_md_to_word(text: str, filename: str = "") -> str:
    """Converts Markdown text to a DOCX file and returns the file path.

    Args:
        text (str): Markdown text to convert.

    Returns:
        str: The encoded file path of the generated DOCX.
    """
    file_path = f"outputs/{filename[:60]}.docx"

    try:
        from docx import Document
        from htmldocx import HtmlToDocx
        # Convert report markdown to HTML
        html = mistune.html(text)
        # Create a document object
        doc = Document()
        # Convert the html generated from the report to document format
        HtmlToDocx().add_html_to_document(html, doc)

        # Saving the docx document to file_path
        doc.save(file_path)

        print(f"Report written to {file_path}")

        encoded_file_path = urllib.parse.quote(file_path)
        return encoded_file_path

    except Exception as e:
        print(f"Error in converting Markdown to DOCX: {e}")
        return ""
