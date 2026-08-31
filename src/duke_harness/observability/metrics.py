from __future__ import annotations

from prometheus_client import Counter, Histogram

RUNS = Counter("duke_harness_runs_total", "Harness runs", ["agent_id", "status"])
RUN_DURATION = Histogram(
    "duke_harness_run_duration_seconds",
    "End-to-end harness run duration",
    ["agent_id"],
    buckets=(0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120),
)
POLICY_DECISIONS = Counter(
    "duke_harness_policy_decisions_total",
    "OPA and fallback decisions",
    ["source", "allow"],
)
TOOL_CALLS = Counter("duke_harness_tool_calls_total", "Tool calls", ["agent_id"])
