"""Polymarket Gamma API client for market browsing."""

import json
from dataclasses import dataclass
from typing import Optional

import httpx


GAMMA_API_BASE = "https://gamma-api.polymarket.com"


@dataclass
class Market:
    """Polymarket market data."""

    id: str
    question: str
    slug: str
    condition_id: str
    yes_token_id: str
    no_token_id: Optional[str]
    yes_price: float
    no_price: float
    volume: float
    volume_24h: float
    liquidity: float
    end_date: str
    active: bool
    closed: bool
    resolved: bool
    outcome: Optional[str]


@dataclass
class MarketGroup:
    """Polymarket event/group containing multiple markets."""

    id: str
    title: str
    slug: str
    description: str
    markets: list[Market]
    tags: list[str] = None


@dataclass
class Tag:
    """Polymarket tag data."""

    id: str
    label: str
    slug: str


class GammaClient:
    """HTTP client for Polymarket Gamma API."""

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    async def get_trending_markets(self, limit: int = 20) -> list[Market]:
        """Get trending markets by volume."""
        async with httpx.AsyncClient(timeout=self.timeout) as http:
            resp = await http.get(
                f"{GAMMA_API_BASE}/markets",
                params={
                    "closed": "false",
                    "limit": limit,
                    "order": "volume24hr",
                    "ascending": "false",
                },
            )
            resp.raise_for_status()
            return [self._parse_market(m) for m in resp.json()]

    async def public_search(
        self, query: str, limit_per_type: int = 10
    ) -> dict:
        """Full-text search across events, tags, and profiles.

        Returns a dict with 'events', 'tags', and 'profiles' keys.
        """
        async with httpx.AsyncClient(timeout=self.timeout) as http:
            resp = await http.get(
                f"{GAMMA_API_BASE}/public-search",
                params={
                    "q": query,
                    "limit_per_type": limit_per_type,
                    "search_tags": "true",
                    "search_profiles": "true",
                },
            )
            resp.raise_for_status()
            return resp.json()

    async def search_markets(self, query: str, limit: int = 20) -> list[Market]:
        """Search markets by keyword using system search.

        Replaces the old legacy local filtering logic.
        """
        search_data = await self.public_search(query, limit_per_type=limit)
        markets = []

        # Extract markets from events returned by search
        for event_data in search_data.get("events", []):
            event_markets = event_data.get("markets", [])
            for m in event_markets:
                markets.append(self._parse_market(m))
                if len(markets) >= limit:
                    return markets

        return markets

    async def get_tag_markets(self, tag_slug: str, limit: int = 50) -> list[Market]:
        """Get markets associated with a specific tag."""
        async with httpx.AsyncClient(timeout=self.timeout) as http:
            resp = await http.get(
                f"{GAMMA_API_BASE}/markets",
                params={
                    "tag_slug": tag_slug,
                    "closed": "false",
                    "limit": limit,
                    "active": "true",
                },
            )
            resp.raise_for_status()
            return [self._parse_market(m) for m in resp.json()]

    async def get_related_tags(self, tag_slug: str) -> list[Tag]:
        """Get tags related to a specific tag slug."""
        async with httpx.AsyncClient(timeout=self.timeout) as http:
            resp = await http.get(f"{GAMMA_API_BASE}/tags/slug/{tag_slug}/related-tags/tags")
            resp.raise_for_status()
            return [
                Tag(id=str(t.get("id", "")), label=t.get("label", ""), slug=t.get("slug", ""))
                for t in resp.json()
            ]

    async def discover_deep(self, query: str, max_depth: int = 1) -> list[Market]:
        """
        Recursive deep mining logic:
        1. Search for keywords (Initial Interest Map)
        2. Expand via Tags (Horizontal Mining)
        3. Drill down into Events (Vertical Mining)
        """
        # 1. Search for initial "seed"
        search_data = await self.public_search(query, limit_per_type=10)
        found_markets = []
        processed_event_ids = set()
        processed_tag_slugs = set()

        # 2. Extract markets and tags from found events
        for event_data in search_data.get("events", []):
            event_id = event_data.get("id")
            if event_id in processed_event_ids:
                continue
            processed_event_ids.add(event_id)

            # Vertical: Get all markets in this event
            event_markets = event_data.get("markets", [])
            for m in event_markets:
                found_markets.append(self._parse_market(m))

            # Horizontal: Track tags for further expansion
            tags = event_data.get("tags", [])
            for t in tags:
                tag_slug = t.get("slug")
                if tag_slug:
                    processed_tag_slugs.add(tag_slug)

        # 3. Horizontal Expansion (Depth 1)
        if max_depth >= 1:
            for tag_slug in list(processed_tag_slugs):
                # Get related tags
                try:
                    related_tags = await self.get_related_tags(tag_slug)
                    for rt in related_tags:
                        if rt.slug not in processed_tag_slugs:
                            # Fetch markets from related tags
                            tag_markets = await self.get_tag_markets(rt.slug, limit=10)
                            found_markets.extend(tag_markets)
                            processed_tag_slugs.add(rt.slug)
                except Exception:
                    continue

        # Deduplicate by condition_id
        unique_markets = {}
        for m in found_markets:
            if m.condition_id not in unique_markets:
                unique_markets[m.condition_id] = m

        return list(unique_markets.values())

    async def get_market(self, market_id: str) -> Market:
        """Get market by ID."""
        async with httpx.AsyncClient(timeout=self.timeout) as http:
            resp = await http.get(f"{GAMMA_API_BASE}/markets/{market_id}")
            resp.raise_for_status()
            return self._parse_market(resp.json())

    async def get_market_by_slug(self, slug: str) -> Market:
        """Get market by slug."""
        async with httpx.AsyncClient(timeout=self.timeout) as http:
            resp = await http.get(
                f"{GAMMA_API_BASE}/markets",
                params={"slug": slug},
            )
            resp.raise_for_status()
            markets = resp.json()
            if not markets:
                raise ValueError(f"Market not found: {slug}")
            return self._parse_market(markets[0])

    async def get_events(self, limit: int = 20) -> list[MarketGroup]:
        """Get events/groups with their markets."""
        async with httpx.AsyncClient(timeout=self.timeout) as http:
            resp = await http.get(
                f"{GAMMA_API_BASE}/events",
                params={
                    "closed": "false",
                    "limit": limit,
                    "order": "volume24hr",
                    "ascending": "false",
                },
            )
            resp.raise_for_status()
            return [self._parse_event(e) for e in resp.json()]

    async def get_prices(self, token_ids: list[str]) -> dict[str, float]:
        """Get current prices for token IDs."""
        if not token_ids:
            return {}

        headers = {"Accept": "application/json"}
        async with httpx.AsyncClient(timeout=self.timeout, headers=headers) as http:
            resp = await http.get(
                "https://clob.polymarket.com/prices",
                params={"token_ids": ",".join(token_ids)},
            )
            resp.raise_for_status()
            return resp.json()

    def _parse_market(self, data: dict) -> Market:
        """Parse market JSON into Market dataclass."""
        clob_tokens = json.loads(data.get("clobTokenIds", "[]"))
        prices = json.loads(data.get("outcomePrices", "[0.5, 0.5]"))

        return Market(
            id=data.get("id", ""),
            question=data.get("question", ""),
            slug=data.get("slug", ""),
            condition_id=data.get("conditionId", ""),
            yes_token_id=clob_tokens[0] if clob_tokens else "",
            no_token_id=clob_tokens[1] if len(clob_tokens) > 1 else None,
            yes_price=float(prices[0]) if prices else 0.5,
            no_price=float(prices[1]) if len(prices) > 1 else 0.5,
            volume=float(data.get("volume", 0) or 0),
            volume_24h=float(data.get("volume24hr", 0) or 0),
            liquidity=float(data.get("liquidity", 0) or 0),
            end_date=data.get("endDate", ""),
            active=data.get("active", True),
            closed=data.get("closed", False),
            resolved=data.get("resolved", False),
            outcome=data.get("outcome"),
        )

    def _parse_event(self, data: dict) -> MarketGroup:
        """Parse event JSON into MarketGroup dataclass."""
        markets_data = data.get("markets", [])
        return MarketGroup(
            id=data.get("id", ""),
            title=data.get("title", ""),
            slug=data.get("slug", ""),
            description=data.get("description", ""),
            markets=[self._parse_market(m) for m in markets_data],
        )
