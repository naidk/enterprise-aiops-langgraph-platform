"""
LLM Factory — centralized LLM provider management.

Provides a unified interface to instantiate ChatModels (Groq, Anthropic, OpenAI)
or a fallback MockLLM based on application settings.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage

from app.config import settings

logger = logging.getLogger(__name__)


class MockChatModel(BaseChatModel):
    """
    Minimal LangChain-compatible mock LLM for local testing and demos
    without API keys.
    """
    
    def _generate(self, messages: list[BaseMessage], stop: Optional[list[str]] = None, **kwargs: Any):
        # Default mock response for standard completion
        return AIMessage(content="Mock LLM response: Analysis complete. (TECHNICAL: ImportError detected in app/main.py)")

    def with_structured_output(self, schema: Any, **kwargs: Any) -> Any:
        """Mock implementation of structured output for LangChain."""
        class MockStructuredLLM:
            def __init__(self, schema):
                self.schema = schema
            def invoke(self, *args, **kwargs):
                # Return a dummy instance of the schema (e.g. RootCauseAnalysis)
                if hasattr(self.schema, "model_validate") or callable(self.schema):
                    try:
                        return self.schema(
                            predicted_root_cause="Mock RCA: Simulated diagnostic finding.",
                            affected_module="test-service",
                            severity="high",
                            confidence=0.9,
                            suggested_remediation="Rollback latest deployment.",
                            evidence_ids=["LOG-MOCK-001"]
                        )
                    except:
                        return "Mock JSON Response"
                return "Mock Response"
        return MockStructuredLLM(schema)

    @property
    def _llm_type(self) -> str:
        return "mock-chat-model"


def get_llm() -> BaseChatModel:
    """
    Instantiate the configured LLM provider.
    
    Returns:
        A LangChain-compatible BaseChatModel.
    """
    provider = settings.llm_provider.lower()
    model_name = settings.llm_model
    temp = settings.llm_temperature

    logger.info("LLMFactory: instantiating provider='%s', model='%s'", provider, model_name)

    if provider == "groq":
        if not settings.groq_api_key:
            logger.warning("GROQ_API_KEY not set. Falling back to MockLLM.")
            return MockChatModel()
        try:
            from langchain_groq import ChatGroq
            return ChatGroq(
                groq_api_key=settings.groq_api_key,
                model_name=model_name,
                temperature=temp,
            )
        except Exception as exc:
            logger.error("LLMFactory: Failed to initialise Groq (%s). Falling back to MockLLM.", exc)
            return MockChatModel()

    elif provider == "anthropic":
        if not settings.anthropic_api_key:
            logger.warning("ANTHROPIC_API_KEY not set. Falling back to MockLLM.")
            return MockChatModel()
        try:
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                anthropic_api_key=settings.anthropic_api_key,
                model_name=model_name,
                temperature=temp,
            )
        except Exception as exc:
            logger.error("LLMFactory: Failed to initialise Anthropic (%s). Falling back to MockLLM.", exc)
            return MockChatModel()

    elif provider == "openai":
        if not settings.openai_api_key:
            logger.warning("OPENAI_API_KEY not set. Falling back to MockLLM.")
            return MockChatModel()
        try:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                api_key=settings.openai_api_key,
                model_name=model_name,
                temperature=temp,
            )
        except Exception as exc:
            logger.error("LLMFactory: Failed to initialise OpenAI (%s). Falling back to MockLLM.", exc)
            return MockChatModel()

    # Default/Fallback
    logger.info("LLMFactory: provider='%s' not recognised. Using MockLLM.", provider)
    return MockChatModel()
