"""Application-wide constants and enumerations.

All enums and constant values used across the application are defined here
to ensure consistency and prevent magic strings throughout the codebase.
"""

from __future__ import annotations

try:
    from enum import StrEnum, unique
except ImportError:
    from enum import Enum, unique

    class StrEnum(str, Enum):  # type: ignore[no-redef]
        """Fallback StrEnum for Python < 3.11."""
        def __str__(self) -> str:
            return str(self.value)


# ── Application Environments ─────────────────────────────────────────────


@unique
class Environment(StrEnum):
    """Application runtime environments."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


# ── RBAC ─────────────────────────────────────────────────────────────────


@unique
class RoleName(StrEnum):
    """User role names for role-based access control."""

    ADMIN = "admin"
    MANAGER = "manager"
    EMPLOYEE = "employee"


@unique
class Permission(StrEnum):
    """Granular permissions for RBAC.

    Each permission follows the pattern 'resource:action' for clarity
    and consistency across the authorization layer.
    """

    # Tenant management
    TENANT_MANAGE = "tenant:manage"

    # User management
    USER_CREATE = "user:create"
    USER_READ = "user:read"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"
    USER_LIST_ALL = "user:list_all"

    # Chat
    CHAT_CREATE = "chat:create"
    CHAT_READ_OWN = "chat:read_own"
    CHAT_READ_ALL = "chat:read_all"
    CHAT_DELETE_OWN = "chat:delete_own"
    CHAT_DELETE_ALL = "chat:delete_all"

    # Documents
    DOCUMENT_UPLOAD = "document:upload"
    DOCUMENT_READ = "document:read"
    DOCUMENT_DELETE_OWN = "document:delete_own"
    DOCUMENT_DELETE_ALL = "document:delete_all"

    # Approvals
    APPROVAL_REVIEW = "approval:review"

    # Analytics & Cost
    ANALYTICS_VIEW = "analytics:view"
    COST_VIEW = "cost:view"

    # Database
    DATABASE_EXPLORE = "database:explore"
    DATABASE_QUERY = "database:query"

    # Settings
    SETTINGS_MANAGE = "settings:manage"

    # MCP
    MCP_MANAGE = "mcp:manage"

    # Memory
    MEMORY_READ_OWN = "memory:read_own"
    MEMORY_READ_ALL = "memory:read_all"
    MEMORY_DELETE = "memory:delete"

    # Workflows
    WORKFLOW_CREATE = "workflow:create"
    WORKFLOW_READ = "workflow:read"
    WORKFLOW_EXECUTE = "workflow:execute"
    WORKFLOW_DELETE = "workflow:delete"

    # Evaluation
    EVALUATION_RUN = "evaluation:run"
    EVALUATION_VIEW = "evaluation:view"


# Role → Permission mapping.
# Admin gets all permissions; Manager and Employee get subsets.
ROLE_PERMISSIONS: dict[RoleName, set[Permission]] = {
    RoleName.ADMIN: set(Permission),
    RoleName.MANAGER: {
        Permission.USER_READ,
        Permission.USER_LIST_ALL,
        Permission.CHAT_CREATE,
        Permission.CHAT_READ_OWN,
        Permission.CHAT_READ_ALL,
        Permission.CHAT_DELETE_OWN,
        Permission.DOCUMENT_UPLOAD,
        Permission.DOCUMENT_READ,
        Permission.DOCUMENT_DELETE_OWN,
        Permission.DOCUMENT_DELETE_ALL,
        Permission.APPROVAL_REVIEW,
        Permission.ANALYTICS_VIEW,
        Permission.COST_VIEW,
        Permission.DATABASE_EXPLORE,
        Permission.DATABASE_QUERY,
        Permission.MEMORY_READ_OWN,
        Permission.MEMORY_READ_ALL,
        Permission.WORKFLOW_CREATE,
        Permission.WORKFLOW_READ,
        Permission.WORKFLOW_EXECUTE,
        Permission.EVALUATION_VIEW,
    },
    RoleName.EMPLOYEE: {
        Permission.CHAT_CREATE,
        Permission.CHAT_READ_OWN,
        Permission.CHAT_DELETE_OWN,
        Permission.DOCUMENT_UPLOAD,
        Permission.DOCUMENT_READ,
        Permission.DOCUMENT_DELETE_OWN,
        Permission.MEMORY_READ_OWN,
        Permission.WORKFLOW_READ,
        Permission.WORKFLOW_EXECUTE,
    },
}


# ── LLM ──────────────────────────────────────────────────────────────────


@unique
class LLMProvider(StrEnum):
    """Supported LLM providers."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    AZURE = "azure"
    OLLAMA = "ollama"


# ── Agents ───────────────────────────────────────────────────────────────


@unique
class AgentType(StrEnum):
    """AI agent types in the supervisor orchestration system."""

    SUPERVISOR = "supervisor"
    PLANNER = "planner"
    SQL = "sql"
    RAG = "rag"
    MEMORY = "memory"
    TOOL = "tool"
    REPORT = "report"


# ── Workflows ────────────────────────────────────────────────────────────


@unique
class WorkflowStatus(StrEnum):
    """Workflow execution status."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@unique
class ApprovalStatus(StrEnum):
    """Human approval request status."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


# ── Documents ────────────────────────────────────────────────────────────


@unique
class DocumentType(StrEnum):
    """Supported document types for upload and processing."""

    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    XLSX = "xlsx"
    CSV = "csv"


# ── Background Tasks ────────────────────────────────────────────────────


@unique
class TaskStatus(StrEnum):
    """Background task (Celery) status."""

    PENDING = "pending"
    STARTED = "started"
    SUCCESS = "success"
    FAILURE = "failure"
    RETRY = "retry"
    REVOKED = "revoked"


# ── WebSocket Events ────────────────────────────────────────────────────


@unique
class WebSocketEvent(StrEnum):
    """WebSocket event types for real-time communication."""

    # Chat events
    CHAT_MESSAGE = "chat.message"
    CHAT_THINKING = "chat.thinking"
    CHAT_STREAM = "chat.stream"

    # Workflow events
    WORKFLOW_STEP_STARTED = "workflow.step_started"
    WORKFLOW_STEP_COMPLETED = "workflow.step_completed"
    WORKFLOW_COMPLETED = "workflow.completed"
    WORKFLOW_FAILED = "workflow.failed"

    # Approval events
    APPROVAL_REQUESTED = "approval.requested"
    APPROVAL_RESOLVED = "approval.resolved"

    # Document events
    DOCUMENT_PROCESSING = "document.processing"
    DOCUMENT_COMPLETED = "document.completed"

    # Notifications
    NOTIFICATION_INFO = "notification.info"
    NOTIFICATION_ERROR = "notification.error"


# ── Memory ───────────────────────────────────────────────────────────────


@unique
class MemoryType(StrEnum):
    """Long-term memory entry types."""

    FACT = "fact"
    PREFERENCE = "preference"
    CONVERSATION_SUMMARY = "conversation_summary"
    IMPORTANT_CONTEXT = "important_context"
    USER_INSTRUCTION = "user_instruction"


# ═════════════════════════════════════════════════════════════════════════
# Constant Values
# ═════════════════════════════════════════════════════════════════════════

# LLM pricing per 1M tokens (USD) — updated for current models
LLM_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    "claude-3-haiku": {"input": 0.25, "output": 1.25},
    "gemini-2.0-flash": {"input": 0.075, "output": 0.30},
    "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
}

# Maximum context window sizes per model
MODEL_CONTEXT_WINDOWS: dict[str, int] = {
    "gpt-4o": 128_000,
    "gpt-4o-mini": 128_000,
    "gpt-4-turbo": 128_000,
    "claude-sonnet-4-20250514": 200_000,
    "claude-3-haiku": 200_000,
    "gemini-2.0-flash": 1_000_000,
    "gemini-1.5-pro": 2_000_000,
}

# Document processing defaults
DEFAULT_CHUNK_SIZE: int = 1000
DEFAULT_CHUNK_OVERLAP: int = 200
MAX_CHUNKS_PER_RETRIEVAL: int = 10

# Rate limiting defaults
DEFAULT_RATE_LIMIT_REQUESTS: int = 100
DEFAULT_RATE_LIMIT_WINDOW: int = 60  # seconds

# SQL safety configuration
SQL_QUERY_TIMEOUT_SECONDS: int = 30
SQL_MAX_RESULT_ROWS: int = 1000
SQL_ALLOWED_STATEMENTS: frozenset[str] = frozenset({"SELECT", "WITH"})
SQL_APPROVAL_REQUIRED_STATEMENTS: frozenset[str] = frozenset(
    {"INSERT", "UPDATE", "DELETE"}
)
SQL_BLOCKED_STATEMENTS: frozenset[str] = frozenset(
    {"DROP", "ALTER", "TRUNCATE", "CREATE", "GRANT", "REVOKE", "EXEC", "EXECUTE"}
)

# Background task retry policy
TASK_MAX_RETRIES: int = 3
TASK_RETRY_BACKOFF: int = 60  # seconds (exponential base)
TASK_DLQ_ROUTING_KEY: str = "dlq"

# Celery queue names
CELERY_QUEUE_DEFAULT: str = "default"
CELERY_QUEUE_DOCUMENTS: str = "documents"
CELERY_QUEUE_EMBEDDINGS: str = "embeddings"
CELERY_QUEUE_REPORTS: str = "reports"
CELERY_QUEUE_EMAILS: str = "emails"
