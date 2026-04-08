from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader


def extract_text_from_pdf(path: Path) -> str:
    """
    Extract plain text from a PDF file. Pages are concatenated with newlines.

    Raises on missing file or loader failures; callers should handle empty strings.
    """
    loader = PyPDFLoader(str(path))
    docs = loader.load()
    parts = [d.page_content for d in docs if d.page_content and d.page_content.strip()]
    return "\n\n".join(parts).strip()
