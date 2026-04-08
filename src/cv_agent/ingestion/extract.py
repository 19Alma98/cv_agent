from pathlib import Path

from cv_agent.ingestion.pdf_extract import extract_text_from_pdf


def extract_cv_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return extract_text_from_pdf(path)
    if suffix in (".txt", ".md"):
        return path.read_text(encoding="utf-8", errors="replace")
    raise ValueError(f"Unsupported CV file type: {path.suffix} ({path})")
