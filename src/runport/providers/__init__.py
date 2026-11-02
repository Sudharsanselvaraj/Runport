"""Provider abstraction package for external API and local serving backends."""

from runport.providers.base import (
    BaseProvider,
    ConfidentialityViolationError,
    LiveNotAuthorizedError,
    ProviderError,
    ProviderRequest,
    ProviderResponse,
    RateLimitError,
    UsageUnavailableError,
    require_complete_usage,
    require_recordable_cost,
    scrub_secrets,
)
from runport.providers.openrouter import OpenRouterAdapter

__all__ = [
    "BaseProvider",
    "OpenRouterAdapter",
    "ProviderRequest",
    "ProviderResponse",
    "ProviderError",
    "ConfidentialityViolationError",
    "RateLimitError",
    "LiveNotAuthorizedError",
    "UsageUnavailableError",
    "require_complete_usage",
    "require_recordable_cost",
    "scrub_secrets",
]
