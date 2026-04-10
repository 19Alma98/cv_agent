from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse

from cv_agent.config import Settings


def get_client(settings: Settings) -> QdrantClient:
    kwargs: dict = {"url": settings.qdrant_url, "timeout": settings.qdrant_timeout}
    if settings.qdrant_api_key:
        kwargs["api_key"] = settings.qdrant_api_key
    return QdrantClient(**kwargs)


def qdrant_reachable(client: QdrantClient) -> tuple[bool, str | None]:
    """
    Return (True, None) if Qdrant responds, else (False, safe error hint).
    Does not raise for network errors.
    """
    try:
        client.get_collections()
    except UnexpectedResponse as e:
        return False, f"qdrant_http_{e.status_code}"
    except Exception:
        return False, "qdrant_unreachable"
    return True, None
