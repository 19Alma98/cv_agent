import os

import uvicorn


def main() -> None:
    host = os.environ.get("CV_AGENT_HOST", "127.0.0.1")
    port = int(os.environ.get("CV_AGENT_PORT", "8000"))
    uvicorn.run(
        "cv_agent.main:create_app",
        factory=True,
        host=host,
        port=port,
        reload=os.environ.get("CV_AGENT_RELOAD", "").lower() in ("1", "true", "yes"),
    )


if __name__ == "__main__":
    main()
