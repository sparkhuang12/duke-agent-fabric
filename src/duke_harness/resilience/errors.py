from __future__ import annotations


class HarnessError(RuntimeError):
    code = "harness_error"
    retryable = False
    stage = "runtime"


class ModelNotConfiguredError(HarnessError):
    code = "model_not_configured"
    stage = "model"


class ModelUnavailableError(HarnessError):
    code = "model_unavailable"
    retryable = True
    stage = "model"


class ModelProtocolError(HarnessError):
    code = "model_protocol_error"
    retryable = False
    stage = "model"


class RunDeadlineExceededError(HarnessError):
    code = "run_deadline_exceeded"
    retryable = True
    stage = "runtime"


class ToolExecutionError(HarnessError):
    code = "tool_execution_error"
    retryable = False
    stage = "tool"


class RunNotFoundError(HarnessError):
    code = "run_not_found"
    stage = "api"


class RunBusyError(HarnessError):
    code = "run_busy"
    retryable = True
    stage = "execution"


class ContextAccessDeniedError(HarnessError):
    code = "context_access_denied"
    stage = "policy"
