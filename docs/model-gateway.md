# Model gateway and data residency

The production default is not a public model API. Duke accepts an OpenAI-compatible endpoint only when its exact hostname appears in `DUKE_MODEL_ALLOWED_HOSTS`; the HTTP client ignores ambient proxy variables and does not follow redirects.

## Approved patterns

1. **Direct self-hosted vLLM** — preferred for one approved model pool. It has the smallest operational and data-flow surface and exposes an OpenAI-compatible server.
2. **Self-hosted LiteLLM** — appropriate when one internal gateway must route across several on-premises vLLM/SGLang pools, enforce keys/rate limits, collect local cost metrics or perform provider fallback.

LiteLLM is allowed only when every upstream is inside the same approved residency boundary. Disable external callbacks, traffic mirroring and hosted telemetry; store its own keys and logs in the internal secret/database services. Pin the container version and verify image signatures. Its production guide recommends multiple replicas and Redis for shared routing state.

## Rejected by default

- public SaaS model gateways and public model APIs;
- a self-hosted gateway that forwards to an unapproved external provider;
- DNS wildcards, redirect-based routing or endpoints not covered by network egress policy;
- fallback models in another legal/data-processing boundary;
- external LangSmith tracing or prompt logging.

The application allow-list is defense in depth, not a firewall. Kubernetes NetworkPolicy or host/cloud firewall rules must make all other egress impossible. Validate the primary and fallback model for tool-call compatibility, maximum context, timeout behavior, Chinese quality, prompt-injection resistance and peak capacity before adding its hostname.

References: [vLLM OpenAI-compatible server](https://docs.vllm.ai/en/latest/serving/openai_compatible_server/), [LiteLLM production deployment](https://docs.litellm.ai/docs/proxy/deploy), [LiteLLM fallback routing](https://docs.litellm.ai/docs/proxy/reliability).
