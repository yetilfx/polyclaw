import pytest
import os
from lib.llm_client import LLMClient, OPENROUTER_BASE_URL

def test_llm_client_initialization_with_base_url():
    """Test that LLMClient can be initialized with a custom base_url (should FAIL initially)."""
    custom_url = "https://custom.api/v1"
    client = LLMClient(
        model="test-model",
        api_key="test-key",
        base_url=custom_url
    )
    assert client.base_url == custom_url

def test_llm_client_default_base_url():
    """Test that LLMClient defaults to OPENROUTER_BASE_URL."""
    client = LLMClient(
        model="test-model",
        api_key="test-key"
    )
    assert client.base_url == OPENROUTER_BASE_URL
