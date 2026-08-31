from __future__ import annotations

import argparse
import json
from datetime import timedelta

from duke_harness.config import get_settings
from duke_harness.context.repository import repository_from_url
from duke_harness.domain import utc_now


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Duke Agent Fabric maintenance commands.")
    subcommands = parser.add_subparsers(dest="command", required=True)
    prune = subcommands.add_parser("prune-context", help="Apply the configured context retention period.")
    prune.add_argument("--apply", action="store_true", help="Delete matching rows. Default is a dry run.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = get_settings()
    repository = repository_from_url(
        settings.database_url,
        settings.data_dir,
        redis_url=settings.redis_connection_url,
        short_term_ttl_seconds=settings.short_term_ttl_seconds,
    )
    try:
        if args.command == "prune-context":
            short_term_cutoff = utc_now() - timedelta(days=settings.short_term_retention_days)
            long_term_cutoff = utc_now() - timedelta(days=settings.long_term_retention_days)
            expired_pending = repository.expire_pending_runs(
                short_term_cutoff,
                dry_run=not args.apply,
            )
            counts = repository.prune_retention(
                short_term_cutoff,
                long_term_cutoff,
                dry_run=not args.apply,
            )
            counts["expired_pending"] = expired_pending
            print(
                json.dumps(
                    {
                        "dry_run": not args.apply,
                        "short_term_cutoff": short_term_cutoff.isoformat(),
                        "long_term_cutoff": long_term_cutoff.isoformat(),
                        "matched": counts,
                    },
                    ensure_ascii=False,
                )
            )
    finally:
        close = getattr(repository, "close", None)
        if close:
            close()


if __name__ == "__main__":
    main()
