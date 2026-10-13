"""Custom exception hierarchy for the application.

All application-specific exceptions inherit from ``AppException``, providing
consistent error handling, HTTP status codes, and structured error responses.
The global exception handler in middleware converts these into proper API responses.
"""

from __future__ import annotations

from typing import Any


class AppException(Exception):
    """Base exception for all application errors.

    Attributes:
        message: Human-readable error description.
        error_code: Machine-readable error code for client handling.
        status_code: HTTP status code to return.
        details: Additional error context and metadata.
    """

    def __init__(
        self,
        message: str = "An unexpected error occurred",
        error_code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """Serialize exception to a dictionary for API error responses."""
        return {
            "error": {
                "code": self.error_code,
                "message": self.message,
                "details": self.details,
            }
        }


# ── Authentication & Authorization ───────────────────────────────────────


class AuthenticationError(AppException):
    """Raised when authentication fails (invalid credentials, missing token)."""

    def __init__(
        self,
        message: str = "Authentication failed",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            error_code="AUTHENTICATION_ERROR",
            status_code=401,
            details=details,
        )


class AuthorizationError(AppException):
    """Raised when a user lacks the required permission for an operation."""

    def __init__(
        self,
        message: str = "Insufficient permissions",
        required_permission: str = "",
        details: dict[str, Any] | None = None,
    ) -> None:
        _details = details or {}
        if required_permission:
            _details["required_permission"] = required_permission
        super().__init__(
            message=message,
            error_code="AUTHORIZATION_ERROR",
            status_code=403,
            details=_details,
        )


class TokenExpiredError(AuthenticationError):
    """Raised when a JWT access or refresh token has expired."""

    def __init__(self) -> None:
        super().__init__(
            message="Token has expired",
            details={
                "hint": "Use the refresh token endpoint to obtain a new access token"
            },
        )


class InvalidTokenError(AuthenticationError):
    """Raised when a JWT token is malformed, tampered with, or otherwise invalid."""

    def __init__(self, message: str = "Invalid token") -> None:
        super().__init__(message=message)


# ── Resource Errors ──────────────────────────────────────────────────────


class NotFoundError(AppException):
    """Raised when a requested resource does not exist."""

    def __init__(
        self,
        resource: str = "Resource",
        resource_id: str | int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        _details = details or {}
        if resource_id is not None:
            _details["resource_id"] = str(resource_id)
        super().__init__(
            message=f"{resource} not found",
            error_code="NOT_FOUND",
            status_code=404,
            details=_details,
        )


class ConflictError(AppException):
    """Raised on resource conflicts such as duplicate entries."""

    def __init__(
        self,
        message: str = "Resource conflict",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            error_code="CONFLICT",
            status_code=409,
            details=details,
        )


# ── Validation Errors ───────────────────────────────────────────────────


class ValidationError(AppException):
    """Raised when input validation fails."""

    def __init__(
        self,
        message: str = "Validation error",
        field_errors: dict[str, str] | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        _details = details or {}
        if field_errors:
            _details["field_errors"] = field_errors
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=422,
            details=_details,
        )


# ── Rate Limiting ────────────────────────────────────────────────────────


class RateLimitError(AppException):
    """Raised when the client exceeds the allowed request rate."""

    def __init__(
        self,
        retry_after: int = 60,
        details: dict[str, Any] | None = None,
    ) -> None:
        _details = details or {}
        _details["retry_after_seconds"] = retry_after
        super().__init__(
            message="Rate limit exceeded",
            error_code="RATE_LIMIT_EXCEEDED",
            status_code=429,
            details=_details,
        )


# ── External Service Errors ─────────────────────────────────────────────


class ExternalServiceError(AppException):
    """Raised when an external service call fails."""

    def __init__(
        self,
        service: str,
        message: str = "External service error",
        details: dict[str, Any] | None = None,
    ) -> None:
        _details = details or {}
        _details["service"] = service
        super().__init__(
            message=message,
            error_code="EXTERNAL_SERVICE_ERROR",
            status_code=502,
            details=_details,
        )


class LLMProviderError(ExternalServiceError):
    """Raised when an LLM provider API call fails."""

    def __init__(
        self,
        provider: str,
        message: str = "LLM provider error",
        model: str = "",
        details: dict[str, Any] | None = None,
    ) -> None:
        _details = details or {}
        if model:
            _details["model"] = model
        super().__init__(
            service=f"llm:{provider}",
            message=message,
            details=_details,
        )


# ── AI Agent Errors ──────────────────────────────────────────────────────


class AgentExecutionError(AppException):
    """Raised when an AI agent fails during execution."""

    def __init__(
        self,
        agent: str,
        message: str = "Agent execution failed",
        step: str = "",
        details: dict[str, Any] | None = None,
    ) -> None:
        _details = details or {}
        _details["agent"] = agent
        if step:
            _details["step"] = step
        super().__init__(
            message=message,
            error_code="AGENT_EXECUTION_ERROR",
            status_code=500,
            details=_details,
        )


class ToolExecutionError(AppException):
    """Raised when a tool called by an agent fails."""

    def __init__(
        self,
        tool: str,
        message: str = "Tool execution failed",
        details: dict[str, Any] | None = None,
    ) -> None:
        _details = details or {}
        _details["tool"] = tool
        super().__init__(
            message=message,
            error_code="TOOL_EXECUTION_ERROR",
            status_code=500,
            details=_details,
        )


# ── Database Errors ──────────────────────────────────────────────────────


class DatabaseError(AppException):
    """Raised when a database operation fails unexpectedly."""

    def __init__(
        self,
        message: str = "Database error",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            error_code="DATABASE_ERROR",
            status_code=500,
            details=details,
        )


class SQLValidationError(AppException):
    """Raised when an AI-generated SQL query fails safety validation."""

    def __init__(
        self,
        message: str = "SQL validation failed",
        query: str = "",
        details: dict[str, Any] | None = None,
    ) -> None:
        _details = details or {}
        if query:
            _details["rejected_query_preview"] = query[:200]
        super().__init__(
            message=message,
            error_code="SQL_VALIDATION_ERROR",
            status_code=400,
            details=_details,
        )


# ── Document Errors ──────────────────────────────────────────────────────


class DocumentProcessingError(AppException):
    """Raised when document upload or text extraction fails."""

    def __init__(
        self,
        message: str = "Document processing failed",
        filename: str = "",
        details: dict[str, Any] | None = None,
    ) -> None:
        _details = details or {}
        if filename:
            _details["filename"] = filename
        super().__init__(
            message=message,
            error_code="DOCUMENT_PROCESSING_ERROR",
            status_code=500,
            details=_details,
        )


# ── Workflow Errors ──────────────────────────────────────────────────────


class WorkflowError(AppException):
    """Raised when a multi-step workflow execution fails."""

    def __init__(
        self,
        message: str = "Workflow execution failed",
        workflow_id: str = "",
        step: str = "",
        details: dict[str, Any] | None = None,
    ) -> None:
        _details = details or {}
        if workflow_id:
            _details["workflow_id"] = workflow_id
        if step:
            _details["step"] = step
        super().__init__(
            message=message,
            error_code="WORKFLOW_ERROR",
            status_code=500,
            details=_details,
        )


# ── Approval Errors ─────────────────────────────────────────────────────


class ApprovalRequiredError(AppException):
    """Raised when an operation requires human approval before execution.

    This is not an error per se — it signals the client that the operation
    has been queued for review. HTTP 202 Accepted is returned.
    """

    def __init__(
        self,
        operation: str,
        approval_id: str = "",
        details: dict[str, Any] | None = None,
    ) -> None:
        _details = details or {}
        _details["operation"] = operation
        if approval_id:
            _details["approval_id"] = approval_id
        super().__init__(
            message=f"Human approval required for: {operation}",
            error_code="APPROVAL_REQUIRED",
            status_code=202,
            details=_details,
        )


# ── Security Errors ─────────────────────────────────────────────────────


class PromptInjectionError(AppException):
    """Raised when a potential prompt injection attack is detected in user input."""

    def __init__(
        self,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message="Potentially malicious input detected",
            error_code="PROMPT_INJECTION_DETECTED",
            status_code=400,
            details=details,
        )


class TenantIsolationError(AppException):
    """Raised when a cross-tenant data access violation is detected."""

    def __init__(self) -> None:
        super().__init__(
            message="Tenant isolation violation",
            error_code="TENANT_ISOLATION_ERROR",
            status_code=403,
        )
