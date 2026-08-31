"""Backward-compatible entry point for the FastAPI-based Duke Agent Fabric."""

from __future__ import annotations

import os
from pathlib import Path


def _map_legacy_environment() -> None:
    legacy_data_dir = os.environ.get("DUKE_AGENT_DATA_DIR")
    if legacy_data_dir and "DUKE_DATABASE_URL" not in os.environ:
        target = (Path(legacy_data_dir).resolve() / "harness.db").as_posix()
        os.environ["DUKE_DATABASE_URL"] = f"sqlite:///{target}"
        os.environ.setdefault("DUKE_DATA_DIR", str(Path(legacy_data_dir).resolve()))


def main() -> None:
    _map_legacy_environment()
    from duke_harness.cli import main as cli_main

    cli_main()


if __name__ == "__main__":
    main()
