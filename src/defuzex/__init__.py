"""Public DefuzeX Python SDK API.

Importing this module only binds types and functions; it does not read
credentials, inspect the environment, access the network, or create files.
"""

from ._version import __version__
from .api import configure, create_run
from .client import DEFAULT_BASE_URL, DefuzeClient
from .contracts import (
    CaptureComponent,
    CaptureStatus,
    Case,
    DefuzeXInput,
    FileChange,
    FileEvidence,
    HistoryItem,
    JudgeBatchResult,
    Submission,
    TestReport,
)
from .errors import (
    AuthenticationError,
    CaseIntegrityError,
    ConfigurationError,
    DockerRequiredError,
    EvidenceCaptureError,
    InputProtocolError,
    LimitExceededError,
    PermissionDeniedError,
    ProviderError,
    RepoStateMismatchError,
    RunAlreadyActiveError,
    SensitiveDataError,
    ServiceBusyError,
    ServiceError,
    ValidationError,
)
from .exceptions import (
    DefuzeAPIError,
    DefuzeAuthenticationError,
    DefuzeError,
    DefuzePermissionError,
    DefuzeRateLimitError,
    DefuzeTimeoutError,
)

__all__ = [
    "DEFAULT_BASE_URL",
    "AuthenticationError",
    "CaptureComponent",
    "CaptureStatus",
    "Case",
    "CaseIntegrityError",
    "ConfigurationError",
    "DefuzeAPIError",
    "DefuzeAuthenticationError",
    "DefuzeClient",
    "DefuzeError",
    "DefuzePermissionError",
    "DefuzeRateLimitError",
    "DefuzeTimeoutError",
    "DefuzeXInput",
    "DockerRequiredError",
    "EvidenceCaptureError",
    "FileChange",
    "FileEvidence",
    "HistoryItem",
    "InputProtocolError",
    "JudgeBatchResult",
    "LimitExceededError",
    "PermissionDeniedError",
    "ProviderError",
    "RepoStateMismatchError",
    "RunAlreadyActiveError",
    "SensitiveDataError",
    "ServiceBusyError",
    "ServiceError",
    "Submission",
    "TestReport",
    "ValidationError",
    "__version__",
    "configure",
    "create_run",
]
