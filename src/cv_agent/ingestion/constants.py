# PDF text is extracted with LangChain PyPDFLoader (pypdf). Microsoft Agent Framework
# does not ship a PDF text parser
PARSER_BACKEND = "langchain_pypdf"
PARSER_VERSION = "1.0"

DEFAULT_CHUNK_SIZE_CHARS = 2400
DEFAULT_CHUNK_OVERLAP_CHARS = 360  # ~15% of 2400
