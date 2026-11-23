# 山海手卷 API

浏览器先通过 `GET /api/v1/workbench` 取得 `auth_mode`，再通过已认证的 `GET /api/v1/workbench/session` 取得租户、用户、`model_configured` 和 `fiction_available`。前两项决定当前浏览器打开哪个书架。开发环境支持身份请求头，组织部署使用 OIDC。

## 请求一次续写

```bash
curl http://127.0.0.1:9090/api/v1/runs \
  -H 'Content-Type: application/json' \
  -H 'X-Duke-Tenant: demo' -H 'X-Duke-User: writer' \
  -d '{"agent_id":"fiction","thread_id":"chapter-seven-attempt-one","idempotency_key":"attempt-one","input":"从本章末句续写两段。沈砚在窗边拆开信，门外忽然响起铃声。"}'
```

小说写作台会先从本书选取有长度上限的当前正文、前章提要和节选，以及当前章可见的人物和线索，再组成输入。每次新提议使用独立线程；同一次请求重试复用原快照、线程和幂等键。「核对前文」使用同一路径，输入中指明核对任务。

`GET /api/v1/runs/{run_id}` 返回当前身份获准读取的结果。只有 `completed` 结果可供作者采纳。其他状态包括 `waiting_approval`、`denied` 和 `failed`。服务端不替作者修改浏览器原稿。

## 身份与运行状态

- `GET /api/v1/agents` 列出小说协作编辑。
- `GET /api/v1/contexts/fiction/{thread_id}` 查看授权线程上下文。
- `GET /api/v1/approvals` 与 `POST /api/v1/runs/{run_id}/approval` 供有权限的独立复核人处理受限运行。提交字段为 `approved` 和可选的 `comment`。
- `GET /api/v1/model/status` 和 `GET /api/v1/policy/status` 提供网关及策略状态。
- `GET /api/v1/health/live`、`GET /api/v1/health/ready` 和 `GET /metrics` 供部署方检查服务。

[身份配置](identity.md) · [上下文和运行记录的保留期限](storage.md)
