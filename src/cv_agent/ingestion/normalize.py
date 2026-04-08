import re
import unicodedata


def normalize_text(text: str) -> str:
    """
    Unicode NFC, trim, collapse excessive blank lines, normalize line endings to ``\\n``.
    """
    if not text:
        return ""
    t = unicodedata.normalize("NFC", text)
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    t = t.strip()
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t
