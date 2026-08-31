# Contributing to Duke Agent Fabric

Thank you for improving Duke. Changes to an agent harness can affect tenant isolation, tool authority and retained data, so security evidence is part of the implementation—not a follow-up task.

## Development setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev,production]'
make verify
```

Use Python 3.10 or newer. Keep new runtime dependencies narrowly scoped and include their license and supply-chain rationale in the pull request.

## Pull requests

- Open a focused issue or pull request with the problem, threat boundary and expected behavior.
- Add tests for tenant/user/agent/thread isolation, retries, denial paths and retention behavior when relevant.
- Never weaken production fail-closed checks to make local development easier.
- Do not add model calls, telemetry, remote MCP servers or network-capable Skills without an explicit data-flow review.
- Keep external Skills commit-pinned, checksum-verified, text-only and license-reviewed.
- Update README/docs and `memory/architecture.md` when public behavior or a durable design decision changes.

Run `ruff`, `mypy`, `pytest`, OPA formatting/tests and Compose validation before submitting. Commits should be understandable and may be squashed by the maintainer.

## Security changes

Security fixes should follow [SECURITY.md](SECURITY.md). Do not demonstrate a live exploit against systems you do not own or place secrets, personal data, model prompts or private documents in an issue.
