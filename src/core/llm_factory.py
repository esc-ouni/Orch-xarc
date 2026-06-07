"""
LLM factory — returns the correct LangChain chat model based on model name.

Supports:
  • OpenAI models  (gpt-*)     → ChatOpenAI
  • Google models  (gemini-*)  → ChatGoogleGenerativeAI

Usage::

    from src.core.llm_factory import create_llm
    llm = create_llm()          # uses settings defaults
    llm = create_llm(tools=...) # auto-binds tools
"""

from __future__ import annotations

from typing import Any, Sequence

import structlog
from langchain_core.language_models import BaseChatModel

from src.core.config import settings

logger = structlog.get_logger(__name__)


def create_llm(
    *,
    tools: Sequence[Any] | None = None,
) -> BaseChatModel:
    """
    Create a LangChain chat model from application settings.

    Automatically selects the provider based on ``settings.llm_model``:
      - ``gemini-*``  → ``ChatGoogleGenerativeAI``
      - everything else → ``ChatOpenAI``

    Args:
        tools: Optional list of tools to bind to the model.

    Returns:
        A ready-to-use chat model, optionally with tools bound.
    """
    model_name = settings.llm_model
    temperature = settings.llm_temperature

    if model_name.startswith("gemini"):
        from langchain_google_genai import ChatGoogleGenerativeAI

        api_key = settings.google_api_key or None
        if not api_key:
            raise ValueError(
                "ORCH_GOOGLE_API_KEY must be set when using a Gemini model. "
                f"Current model: {model_name}"
            )

        llm = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=temperature,
            google_api_key=api_key,
        )
        logger.info("llm.created", provider="google", model=model_name)

    else:
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model=model_name,
            temperature=temperature,
            api_key=settings.openai_api_key or None,
        )
        logger.info("llm.created", provider="openai", model=model_name)

    if tools:
        llm = llm.bind_tools(tools)

    return llm
