"""Versioned outcomes shared by the template's Python tool adapters."""

STATUSES = frozenset({
    "succeeded", "unchanged", "no_record", "incomplete", "denied",
    "unavailable", "invalid_input", "failed", "unverified",
})
SUCCESS_STATUSES = frozenset({"succeeded", "unchanged"})


class ToolResult(dict):
    def __bool__(self):
        raise TypeError("Inspect result['status']; a tool result is not a success boolean")


class ToolError(Exception):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status = status
        self.code = code


def outcome(operation, status, *, data=None, evidence=None, error=None):
    if status not in STATUSES:
        raise ValueError(f"Unknown tool status: {status}")
    if status in SUCCESS_STATUSES and (error is not None or not evidence):
        raise ValueError("Success requires evidence and no error")
    return ToolResult(
        schema_version=1, operation=operation, status=status,
        data={} if data is None else data,
        evidence=[] if evidence is None else evidence,
        error=error,
    )


def error_details(exc):
    # Only use curated messages. Provider stderr can contain credentials or data.
    return {"code": exc.code, "message": str(exc), "retryable": False}
