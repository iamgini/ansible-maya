# Copyright 2026 Ansible AI Gateway Contributors
# Licensed under the Apache License, Version 2.0

"""Core business logic for Ansible Sage."""

from ansible_ai_gateway.core.ansible_context import AnsibleContextProcessor, AnsibleFileType
from ansible_ai_gateway.core.exceptions import (
    AnsibleLintError,
    ConfigurationError,
    EventClassificationError,
    LLMProviderError,
    PlaybookGenerationError,
    ValidationError,
)
from ansible_ai_gateway.core.providers import (
    BaseLLMProvider,
    ClaudeProvider,
    GenerationRequest,
    GenerationResponse,
    ModelTier,
    get_provider,
)
from ansible_ai_gateway.core.prompt_templates import get_event_prompt, get_system_prompt

__all__ = [
    # Context processing
    "AnsibleContextProcessor",
    "AnsibleFileType",
    # Providers
    "BaseLLMProvider",
    "ClaudeProvider",
    "GenerationRequest",
    "GenerationResponse",
    "ModelTier",
    "get_provider",
    # Prompts
    "get_system_prompt",
    "get_event_prompt",
    # Exceptions
    "ConfigurationError",
    "LLMProviderError",
    "PlaybookGenerationError",
    "ValidationError",
    "AnsibleLintError",
    "EventClassificationError",
]
