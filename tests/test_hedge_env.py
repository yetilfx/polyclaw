import pytest
import os
import sys
from unittest.mock import MagicMock, patch, AsyncMock
from scripts.hedge import cmd_scan, cmd_analyze

@pytest.mark.asyncio
async def test_cmd_scan_fails_missing_env(capsys):
    """Test that cmd_scan fails when ARK_* env vars are missing."""
    # Ensure env vars are NOT set
    env_patch = {
        "ARK_MODEL_ID": "",
        "ARK_API_KEY": "",
        "ARK_BASE_URL": ""
    }
    
    with patch.dict(os.environ, env_patch, clear=False):
        # Mock GammaClient to avoid network calls
        with patch("scripts.hedge.GammaClient") as mock_gamma:
            mock_gamma_inst = mock_gamma.return_value
            
            m1 = MagicMock()
            m1.closed = False
            m1.resolved = False
            m1.yes_price = 0.5
            m1.no_price = 0.5
            
            m2 = MagicMock()
            m2.closed = False
            m2.resolved = False
            m2.yes_price = 0.5
            m2.no_price = 0.5
            
            mock_gamma_inst.get_trending_markets = AsyncMock(return_value=[m1, m2])
            
            args = MagicMock()
            args.query = None
            args.limit = 20
            
            result = await cmd_scan(args)
            
            # This should fail with return code 1
            assert result == 1
            captured = capsys.readouterr()
            assert "Error: Missing environment variables" in captured.out

@pytest.mark.asyncio
async def test_cmd_scan_succeeds_with_env():
    """Test that cmd_scan continues with LLM initialization when env vars are present."""
    env_patch = {
        "ARK_MODEL_ID": "test-model",
        "ARK_API_KEY": "test-key",
        "ARK_BASE_URL": "https://test.api"
    }
    
    with patch.dict(os.environ, env_patch, clear=False):
        with patch("scripts.hedge.GammaClient") as mock_gamma:
            mock_gamma_inst = mock_gamma.return_value
            
            m1 = MagicMock()
            m1.closed = False
            m1.resolved = False
            m1.yes_price = 0.5
            m1.no_price = 0.5
            
            m2 = MagicMock()
            m2.closed = False
            m2.resolved = False
            m2.yes_price = 0.5
            m2.no_price = 0.5
            
            mock_gamma_inst.get_trending_markets = AsyncMock(return_value=[m1, m2])
            
            # Mock LLMClient to avoid actual initialization and calls
            with patch("scripts.hedge.LLMClient") as mock_llm:
                # Mock the close method which is awaited
                mock_llm.return_value.close = AsyncMock()
                
                args = MagicMock()
                args.query = None
                args.limit = 20
                args.json = False
                args.min_coverage = 0.85
                args.tier = 2
                
                # We expect it to reach the market analysis loop
                with patch("scripts.hedge.extract_implications_for_market") as mock_extract:
                    mock_extract.return_value = []
                    await cmd_scan(args)
                    
                    mock_llm.assert_called_once()
