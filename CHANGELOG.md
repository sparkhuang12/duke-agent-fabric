# Changelog

This project follows semantic versioning after `1.0.0`. Dates use UTC.

## [Unreleased]

- 山海手卷专注小说章回、人物与伏笔。移除六个办公角色、旧版接口、办公页面和 MCP 工具；已有小说书架继续使用原身份和存储格式。

- Added a Chinese-language writing desk with editable manuscript briefs, isolated revision threads, role guidance and reviewer feedback.
- Prioritized the latest approved draft and its instruction when assembling bounded context, with explicit excerpts for oversized manuscripts.

- Renamed the public project and distribution from Duke Agent Harness to Duke Agent Fabric.
- Added `duke-agent-fabric` as the primary CLI while retaining `duke-harness` as a compatibility alias.

## [0.3.0] - 2026-08-31

### Added

- MySQL one-year long-term memory/run/audit repository.
- Redis seven-day conversation and LangGraph checkpoint storage.
- Keycloak-compatible OIDC JWT validation and authoritative claim mapping.
- Dynamic confidential/secret approval policy and reviewer queue.
- Four-eyes reviewer separation and seven-day short-term run-payload scrubbing.
- Redis cross-replica run leases for approval resume.
- Protected single-host, private-cloud VM and Kubernetes deployment profiles.
- Model gateway host allow-list and external tracing production guard.

## [0.2.0] - 2026-08-31

- Initial policy-governed LangGraph harness, isolated context, OPA enforcement, local MCP tools, audited Skills and legacy UI compatibility.
