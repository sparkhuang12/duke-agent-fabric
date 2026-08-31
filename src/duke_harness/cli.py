from __future__ import annotations

import argparse

import uvicorn

from duke_harness.config import get_settings


def parse_args() -> argparse.Namespace:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Run the Duke Agent Fabric API.")
    parser.add_argument("--host", default=settings.host)
    parser.add_argument("--port", default=settings.port, type=int)
    parser.add_argument("--reload", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    uvicorn.run(
        "duke_harness.api.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        proxy_headers=True,
        forwarded_allow_ips="127.0.0.1",
        server_header=False,
    )


if __name__ == "__main__":
    main()
