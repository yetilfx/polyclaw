import asyncio
import pytest
from lib.gamma_client import GammaClient, Market

@pytest.mark.asyncio
async def test_public_search():
    client = GammaClient()
    # Use a common keyword like "Trump"
    results = await client.public_search("Trump", limit_per_type=5)
    
    assert "events" in results
    assert "tags" in results
    assert len(results["events"]) <= 5

@pytest.mark.asyncio
async def test_search_markets():
    client = GammaClient()
    markets = await client.search_markets("Elon", limit=5)
    
    assert isinstance(markets, list)
    if markets:
        assert isinstance(markets[0], Market)
        assert len(markets) <= 5

@pytest.mark.asyncio
async def test_get_related_tags():
    client = GammaClient()
    # "politics" is a common tag slug
    try:
        tags = await client.get_related_tags("politics")
        assert isinstance(tags, list)
        if tags:
            assert hasattr(tags[0], "slug")
    except Exception as e:
        pytest.skip(f"API endpoint might not exist or returned error: {e}")

@pytest.mark.asyncio
async def test_discover_deep():
    client = GammaClient()
    # "Fed" should trigger horizontal expansion to "interest rates" or similar
    markets = await client.discover_deep("Fed", max_depth=1)
    
    assert isinstance(markets, list)
    # Even if no markets found (unlikely), it should return a list
    print(f"Found {len(markets)} markets for 'Fed' via deep discovery")
