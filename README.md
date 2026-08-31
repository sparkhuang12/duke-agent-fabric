<div align="center">

# Duke Agent Fabric

**把模型调用变成可隔离、可恢复、可审计、可审批的智能体执行系统。**

LangChain · LangGraph · Open Policy Agent · Model Context Protocol · FastAPI

</div>

---

Duke Agent Fabric 是一个面向企业与政务场景的主权多智能体运行平台。它不是另一个聊天页面，也不把一段 ReAct prompt 包装成“生产系统”。它负责模型之外真正困难的部分：身份边界、上下文生命周期、策略决策、工具权限、人工审批、故障恢复和审计证据。

项目从六个办公智能体原型演进而来，目前提供可运行的 Harness 核心、兼容旧工作台的 API，以及一套可以替换模型网关、存储和部署环境的工程边界。

> [!IMPORTANT]
> 这是 production-oriented framework，不是开箱即用的合规证明。真实上线仍需由部署方提供 IdP、TLS、秘密管理、备份、网络策略、数据分级制度和经过验收的业务评测集。

## Why Duke

大多数 Agent Demo 在模型返回答案时就结束了。真实系统还要回答：

- 这次运行代表哪个租户和用户？
- `meeting` agent 能否读取 `policy` agent 的历史？
- 工具调用之前由谁做授权？OPA 不可用时放行还是拒绝？
- 服务重启后，待审批任务从哪里继续？
- 模型超时、限流或返回错误时，重试、切换还是熔断？
- 放进 prompt 的 skill 从哪里来，是否被篡改，是否夹带可执行脚本？
- 出现事故时，能否重建一次运行的策略、工具和审批轨迹？

Duke 把这些问题放在 Harness 层解决，而不是寄希望于模型“自觉遵守”。

## Highlights

- **Durable graph runtime** — 使用 LangGraph 管理状态机、工具循环、checkpoint 和人工审批中断。
- **OpenAI-compatible model boundary** — 使用 LangChain 接入模型 API；支持重试、备用模型和独立熔断器。
- **Policy at every boundary** — OPA 在输入、上下文读取、工具调用和输出阶段做结构化决策。
- **Context isolation by construction** — `tenant / user / agent / thread` 四维地址生成独立命名空间，相同 thread ID 也不会跨 agent 读写。
- **Four-tier context model** — 请求上下文、运行工作状态、会话历史与长期记忆分开存储和保留。
- **Local MCP server** — 提供知识检索、受控文件读取、文本比对和敏感信息扫描四个本地工具。
- **Audited skills** — skill 只以文本形式加载，必须固定上游 commit 与 SHA-256；脚本默认不进入执行面。
- **Human-in-the-loop** — 高风险 agent 在输出后进入 durable interrupt，审批结果可在进程重启后恢复。
- **Failure containment** — 模型超时、指数重试、fallback、熔断、图步数/工具数/总时长预算和结构化错误分类。
- **Cross-replica run lease** — Redis 非阻塞租约保证同一待审批运行只被一个实例恢复，并在实例失联后自动过期。
- **Observable by default** — JSON 日志、内容最小化审计事件、Prometheus metrics、liveness/readiness。
- **Fail-fast production config** — 生产环境缺少 MySQL、Redis、OIDC、内网模型白名单或 fail-closed OPA 时拒绝启动。

## Architecture

```text
                         ┌──────────────────────────┐
                         │  Identity-aware proxy    │
                         └────────────┬─────────────┘
                                      │ trusted identity
                                      ▼
┌──────────┐   input policy   ┌───────────────────┐
│   OPA    │◄─────────────────│   FastAPI ingress │
└────┬─────┘                  └─────────┬─────────┘
     │                                  │
     │                                  ▼
     │                         ┌───────────────────┐
     │                         │ Context assembler │
     │                         │ tenant/user/agent │
     │                         │      /thread      │
     │                         └─────────┬─────────┘
     │                                  ▼
     │       tool policy      ┌───────────────────┐       ┌──────────────┐
     ├────────────────────────│ LangGraph runtime │──────►│ Model API    │
     │                        └──────┬─────┬──────┘       └──────────────┘
     │                               │     │
     │                               │     └─────────────► MCP / tools
     │       output policy           ▼
     └───────────────────────► approval interrupt
                                      │
                                      ▼
                       Redis 7-day state + MySQL 1-year memory/audit
```

完整说明见 [Architecture](docs/architecture.md)、[Storage](docs/storage.md)、[Identity](docs/identity.md) 和 [Model gateway](docs/model-gateway.md)。

## Context isolation

每个上下文都必须携带：

```text
tenant_id + user_id + agent_id + thread_id
```

四元组经过 SHA-256 生成内部 namespace。数据访问始终以 namespace 为条件；LangGraph 运行再使用 `namespace + run_id` 生成独立 checkpoint ID。因此：

- 同一用户、同一 thread，不同 agent：隔离；
- 同一 agent、同一 thread，不同用户：隔离；
- 同一用户与 agent，不同 tenant：隔离；
- 需要共享的知识必须成为显式 resource，并重新经过 OPA，而不是读取别人的 memory。

Checkpoint 只负责恢复图状态，不承担长期记忆。Redis 保存短期消息、rolling summary 和 LangGraph checkpoint，写入后七天自动过期；短期运行在 MySQL 中的输入、输出及用户 metadata 也会在七天后被清空，只留下最小审计骨架。只有显式选择 `long_term` 且审批完成的运行内容和记忆才保留一年；拒绝或失败的长期请求仍按七天内容保留期处理。

## Execution lifecycle

```text
authorize input
  → hydrate bounded context
  → invoke primary/fallback model
  → authorize and execute tool calls
  → authorize final output
  → classify data and pause for human approval when required
  → idempotent persistence
  → audit + metrics
```

六个内置 agent 位于 [config/agents.json](config/agents.json)：公文生成、政策问答、文件检索、会议纪要、文件比对和智能审校。Agent 只声明自己允许使用的工具和 skills，不拥有全局工具权限。

## Quick start

### 1. Install

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

### 2. Run OPA

如果本机已安装 OPA：

```bash
opa run --server --addr 127.0.0.1:8181 policies
```

开发环境也可以暂时使用内置的最小策略 fallback；生产环境会强制关闭它。

### 3. Configure a model gateway

```bash
export DUKE_MODEL_API_BASE=https://your-gateway.example.com/v1
export DUKE_MODEL_API_KEY=replace-me
export DUKE_MODEL_NAME=your-model
export DUKE_MODEL_FALLBACKS=your-fallback-model
```

这里要求的是 OpenAI-compatible API。仓库不绑定任何模型供应商，也不会把密钥写进配置文件。

### 4. Start

```bash
.venv/bin/duke-agent-fabric --host 127.0.0.1 --port 9090
```

打开 `http://127.0.0.1:9090` 可继续使用原有工作台；OpenAPI 文档位于 `http://127.0.0.1:9090/docs`。

从旧预发布版本升级时，`duke-harness` CLI 仍作为兼容别名保留；新部署应统一使用 `duke-agent-fabric`。内部 Python import namespace 暂时保持 `duke_harness`，避免破坏插件和集成代码。

## Run an agent

```bash
curl --request POST http://127.0.0.1:9090/api/v1/runs \
  --header 'Content-Type: application/json' \
  --header 'X-Duke-Tenant: demo' \
  --header 'X-Duke-User: alice' \
  --header 'X-Duke-Roles: user' \
  --data '{
    "agent_id": "meeting",
    "thread_id": "weekly-sync-2026-08-31",
    "input": "请根据会议记录整理纪要……",
    "idempotency_key": "example-1",
    "security_level": "internal",
    "memory_scope": "short_term"
  }'
```

需要人工复核的 agent 返回 `waiting_approval`。审批人与发起人必须不同；`confidential`/`secret` 必须由同租户 `security_approver` 审批，普通强制复核由 `approver` 或 `security_approver` 处理。审批队列位于 `GET /api/v1/approvals`。

```bash
curl --request POST http://127.0.0.1:9090/api/v1/runs/RUN_ID/approval \
  --header 'Content-Type: application/json' \
  --header 'X-Duke-Tenant: demo' \
  --header 'X-Duke-User: reviewer' \
  --header 'X-Duke-Roles: approver' \
  --data '{"approved": true, "comment": "已核对来源"}'
```

## OPA policy

[policies/harness.rego](policies/harness.rego) 默认拒绝请求，只在身份拥有上下文、工具位于 agent allowlist 且密级满足时放行。保密内容和长期记忆写入会产生人工审批 obligation；生产模式固定为 fail-closed。

```bash
opa fmt --fail policies
opa test policies
```

生产环境建议通过签名 bundle 分发策略，并启用 OPA decision logs；不要通过应用发布流程临时覆盖线上策略。

## Local MCP tools

本地 stdio server 配置位于 [.mcp.json](.mcp.json)：

| Tool | Purpose | Safety boundary |
| --- | --- | --- |
| `search_knowledge` | 检索本地知识 | 按进程绑定 principal 和 clearance 过滤 |
| `get_document` | 读取一个文件 | 拒绝超过调用者密级的文档 |
| `compare_texts` | 生成 bounded unified diff | 输入和输出长度限制 |
| `scan_sensitive_text` | 扫描手机号、身份证号、邮箱 | 只返回类型和数量，不回显匹配值 |

启动：

```bash
.venv/bin/duke-office-mcp
```

stdio MCP 进程的身份通过环境注入，模型参数不能提升 clearance。远程 MCP 必须另行实现 OAuth、租户绑定和网络策略。

## Skills supply chain

项目从 GitHub 官方 `awesome-copilot` 仓库筛选并裁剪了三个 MIT skills：

| Skill | Used by | Governance |
| --- | --- | --- |
| `meeting-minutes` | meeting | commit pinned + checksum |
| `documentation-writer` | document | commit pinned + checksum |
| `ai-prompt-engineering-safety-review` | review | commit pinned + checksum |

清单位于 [skills/manifest.json](skills/manifest.json)，第三方声明位于 [THIRD_PARTY_LICENSES.md](skills/THIRD_PARTY_LICENSES.md)。运行时只接受 manifest 中的常规 `SKILL.md` 文件，拒绝路径逃逸、符号链接、超大文件和 checksum 不一致。

> [!WARNING]
> 安装量不是安全证明。任何外部 skill 在进入仓库前都应完成许可证、来源、脚本、网络访问、秘密访问和 prompt injection 审查。

## Failure handling

| Failure | Default behavior |
| --- | --- |
| Model timeout / transient provider error | bounded retry → fallback model → circuit breaker |
| Model API missing | structured `model_not_configured`, no fake answer |
| OPA unavailable in production | deny / fail closed |
| Tool outside agent allowlist | deny that call and return policy evidence |
| Tool execution error | bounded error result; graph may continue safely |
| Graph or tool budget exhausted | terminate as denied/failed |
| Approval pending during restart | resume from seven-day Redis checkpoint |
| Approval requested after seven days | fail as `approval_expired`; never recreate a draft |
| Repeated create request | return the run selected by idempotency key |
| Concurrent approval / resume | one replica holds the Redis lease; others receive retryable `run_busy` |
| Tool / unknown runtime exception | return only a sanitized error type; persist structured audit metadata |

## Production deployment

根目录 Compose 适配受保护单机，提供 API、MySQL 8.4、Redis 8 和 OPA；Keycloak 与模型网关作为内网基础设施独立部署：

```bash
cp .env.example .env
# Fill MySQL/Redis secrets, Keycloak OIDC settings and the internal model gateway.
docker compose up --build -d
```

The production profile deliberately refuses to start unless:

- MySQL replaces SQLite and Redis provides short-term context/checkpoints;
- OPA is fail-closed and embedded fallback is disabled;
- an allow-listed, self-hosted OpenAI-compatible model API is configured;
- Keycloak-compatible OIDC issuer, audience and allow-listed JWKS endpoint are configured;
- the unauthenticated legacy API is disabled.

Read the [production checklist](docs/production-checklist.md) before exposing the service.

## API surface

| Endpoint | Description |
| --- | --- |
| `GET /api/v1/health/live` | process liveness |
| `GET /api/v1/health/ready` | database, OPA, model and registry readiness |
| `GET /api/v1/agents` | agent catalog |
| `POST /api/v1/runs` | create or replay-idempotent run |
| `GET /api/v1/runs/{run_id}` | inspect owned run |
| `POST /api/v1/runs/{run_id}/approval` | resume HITL interrupt |
| `GET /api/v1/approvals` | list only runs the current reviewer may approve |
| `GET /api/v1/contexts/{agent}/{thread}` | inspect one authorized context namespace |
| `GET /api/v1/tools` | tool schemas |
| `GET /api/v1/skills` | skill provenance and checksums |
| `GET /api/v1/model/status` | model/circuit status without secrets |
| `GET /api/v1/policy/status` | OPA readiness and failure mode |
| `GET /metrics` | Prometheus exposition |

## Development

```bash
make test
make lint
make policy-test
```

Context retention is a dry run by default. Schedule the applied command only after the owner approves the retention policy:

```bash
.venv/bin/duke-maintenance prune-context
.venv/bin/duke-maintenance prune-context --apply
```

当前验证覆盖上下文跨租户/用户/agent 隔离、Redis TTL、OIDC claims、上下文预算、OPA fail-closed、密级审批、工具 allowlist、skill checksum、MCP 核心函数、模型缺失、工具循环、HITL 恢复、幂等请求、API 身份和旧接口兼容。

## Deployment profiles

| Profile | Files | Intended use |
| --- | --- | --- |
| Protected single host | `compose.yaml`, `deploy/single-host/` | pilot / small internal installation |
| Private-cloud VM | `deploy/vm/` | systemd + Nginx with private managed dependencies |
| Kubernetes | `deploy/kubernetes/` | 3–12 replicas, PDB/HPA and default-deny network policy |

所有模式都要求数据面、Keycloak、OPA 和模型网关位于批准的境内/内网边界。应用禁用环境代理继承，生产配置拒绝未列入 `DUKE_MODEL_ALLOWED_HOSTS` 的模型主机，并拒绝开启外部 LangSmith tracing。推荐直接使用自托管 vLLM，或只配置自托管上游的 LiteLLM。

## Project layout

```text
src/duke_harness/
  agents/          agent registry and declarations
  api/             FastAPI ingress, identity and compatibility routes
  context/         Redis short-term + MySQL long-term isolated stores
  identity/        cached offline OIDC/JWKS validation
  harness/         LangGraph state machine, checkpoints and runner
  models/          OpenAI-compatible routing, fallback and circuits
  policy/          OPA client and failure behavior
  skills/          checksum-verified text-only skill loader
  tools/           policy-mediated local tools
  mcp/             FastMCP stdio adapter
  observability/   metrics and structured logging
policies/           Rego policies and tests
skills/             vendored skills, provenance and licenses
config/agents.json  six built-in agent specifications
compose.yaml        production-oriented local stack
deploy/             single-host, VM, Kubernetes and Keycloak assets
  mysql/            versioned schema bootstrap for privileged migration
```

## Design references

- [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangGraph subgraphs and isolation modes](https://docs.langchain.com/oss/python/langgraph/use-subgraphs)
- [OPA integration](https://www.openpolicyagent.org/docs/integration)
- [OPA decision logs](https://www.openpolicyagent.org/docs/management-decision-logs)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Skills registry security guidance](https://www.skills.sh/docs)
- [LangGraph Redis checkpointer](https://pypi.org/project/langgraph-checkpoint-redis/)
- [Keycloak protocol mappers](https://www.keycloak.org/admin-api/protocol-mappers)
- [LiteLLM production deployment](https://docs.litellm.ai/docs/proxy/deploy)

## Status

The framework core and three deployment profiles are implemented and tested. Before calling a concrete installation “production ready”, operators still need workload sizing, release-blocking agent evaluations, backup/restore drills, penetration testing and an approved internal model inventory.

## Contributing

Issues and pull requests are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md) before submitting changes. The project is released under Apache-2.0; vendored Skill licenses and pinned sources are tracked separately.
