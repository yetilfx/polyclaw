"""Coverage calculation for hedge portfolios.

Calculate coverage metrics and tier classification for covering portfolios.

Coverage formula:
    Coverage = P(target wins) + P(target loses) x P(cover fires | target loses)

Example:
    Buy: "Region NOT captured" @ $0.80 (target)
    Buy: "City captured"       @ $0.15 (cover)
    Total cost: $0.95

    Coverage = 0.80 + 0.20 x 0.98 = 99.6%
    Expected profit = $0.996 - $0.95 = +$0.046

Tier classification:
    - TIER 1 (HIGH):     >=95% coverage - near-arbitrage
    - TIER 2 (GOOD):     90-95% - strong hedges
    - TIER 3 (MODERATE): 85-90% - decent but noticeable risk
    - TIER 4 (LOW):      <85% - speculative
"""

# =============================================================================
# CONFIGURATION
# =============================================================================

# Minimum coverage to include (filters out Tier 4 / Low quality)
MIN_COVERAGE = 0.85

# Probability for necessary relationships
NECESSARY_PROBABILITY = 0.98

# Coverage tier thresholds (coverage_threshold, tier_number, label, description)
TIER_THRESHOLDS = [
    (0.95, 1, "HIGH", "near-arbitrage"),
    (0.90, 2, "GOOD", "strong hedge"),
    (0.85, 3, "MODERATE", "decent hedge"),
    (0.00, 4, "LOW", "speculative"),
]


# =============================================================================
# METRICS CALCULATION
# =============================================================================


def calculate_coverage_metrics(
    target_price: float,
    cover_probability: float,
    total_cost: float,
) -> dict:
    """
    Calculate coverage and expected value for a portfolio.

    Args:
        target_price: Price of target position (= P(target pays out))
        cover_probability: P(cover fires | target doesn't pay out)
        total_cost: Total cost of both positions

    Returns:
        Dict with coverage, loss_probability, expected_profit
    """
    p_target = target_price
    p_not_target = 1 - target_price

    # Coverage = P(get paid) = P(target wins) + P(target loses) x P(cover fires)
    coverage = p_target + p_not_target * cover_probability

    # Loss probability = P(both fail)
    loss_probability = p_not_target * (1 - cover_probability)

    # Expected payout is just coverage (each payout is $1)
    expected_profit = coverage - total_cost

    return {
        "coverage": round(coverage, 4),
        "loss_probability": round(loss_probability, 4),
        "expected_profit": round(expected_profit, 4),
    }


def classify_tier(coverage: float, total_cost: float) -> tuple[int, str]:
    """
    Classify portfolio into tier based on coverage and cost.

    Returns:
        Tuple of (tier_number, tier_label)
    """
    # Any cost >= 1.0 is speculative/junk (Tier 4)
    if total_cost >= 1.0:
        return 4, "LOW"

    for threshold, tier, label, _ in TIER_THRESHOLDS:
        if coverage >= threshold:
            return tier, label
    return 4, "LOW"


def get_tier_description(tier: int) -> str:
    """Get description for a tier number."""
    for _, t, label, desc in TIER_THRESHOLDS:
        if t == tier:
            return desc
    return "speculative"


# =============================================================================
# PORTFOLIO BUILDING
# =============================================================================


def build_portfolio(
    target_market: dict,
    cover_market: dict,
    target_position: str,
    cover_position: str,
    cover_probability: float,
    relationship: str,
) -> dict | None:
    """
    Build a single portfolio from target and cover markets.

    Args:
        target_market: Target market dict with prices
        cover_market: Cover market dict with prices
        target_position: "YES" or "NO" for target
        cover_position: "YES" or "NO" for cover
        cover_probability: P(cover fires | target doesn't)
        relationship: Explanation of the logical relationship

    Returns:
        Portfolio dict or None if invalid
    """
    # Get prices based on positions
    if target_position == "YES":
        target_price = target_market.get("yes_price", 0)
    else:
        target_price = target_market.get("no_price", 0)

    if cover_position == "YES":
        cover_price = cover_market.get("yes_price", 0)
    else:
        cover_price = cover_market.get("no_price", 0)

    total_cost = target_price + cover_price

    # Skip invalid costs
    if total_cost <= 0 or total_cost > 2.0:
        return None

    # PRICE SANITY CHECK (The "Good Taste" Filter)
    # If A => B is true, then P(B) must be >= P(A) in an efficient market.
    # If the "cover" is significantly cheaper than the thing it guarantees,
    # the LLM is likely hallucinating the logical necessity.
    SANITY_MARGIN = 0.05
    if cover_probability >= 0.95:  # Only for "Necessary" relationships
        # Case Implied_By: OTHER => TARGET (so TargetPrice should be >= OtherPrice)
        if target_position == "YES" and cover_position == "NO": # other YES => target YES
             # This means cover_market.yes_price => target_market.yes_price
             # which is equivalent to 1-cover_price => target_market.yes_price
             pass # Logic varies by orientation, simpler to check payout relation

    # Simplify: A hedge H for target T is valid only if P(payout) makes sense.
    # If total_cost is very low but P(win) is claimed 98%, be suspicious.
    # In Case 3: Target(NO@0.07) + Hedge(YES@0.07) = Cost 0.14, Coverage claimed 98%.
    # But if Target fails, it means Fed Stayed. Fed Stayed => Cut 25 (Hedge) is 0%.
    # So P(win) is actually 7%, not 98%.
    
    # Let's enforce that for a "Necessary" hedge, the cover price must 
    # at least reflect the risk it's covering.
    if cover_probability >= 0.95:
        p_risk = 1.0 - target_price
        # If the risk is 93% (p_risk=0.93) but the cover price is only 0.07,
        # it's only a hedge if P(cover|risk) is high. 
        # Market says P(cover) is 0.07. P(risk) is 0.93. 
        # So P(cover|risk) = P(cover and risk) / P(risk) <= 0.07 / 0.93 = 7.5%.
        # LLM says 98%. LLM is wrong.
        
        max_possible_cond_prob = cover_price / (1.0 - target_price) if target_price < 1.0 else 1.0
        if max_possible_cond_prob < 0.5: # If market says it's <50% chance even in best case
            return None # Discard hallucination

    # Calculate metrics
    metrics = calculate_coverage_metrics(target_price, cover_probability, total_cost)

    # Skip low coverage portfolios
    if metrics["coverage"] < MIN_COVERAGE:
        return None

    # Classify tier
    tier, tier_label = classify_tier(metrics["coverage"], total_cost)

    return {
        # Target info
        "target_id": target_market.get("id", ""),
        "target_question": target_market.get("question", ""),
        "target_slug": target_market.get("slug", ""),
        "target_position": target_position,
        "target_price": round(target_price, 4),
        # Cover info
        "cover_id": cover_market.get("id", ""),
        "cover_question": cover_market.get("question", ""),
        "cover_slug": cover_market.get("slug", ""),
        "cover_position": cover_position,
        "cover_price": round(cover_price, 4),
        "cover_probability": cover_probability,
        # Relationship
        "relationship": relationship,
        # Metrics
        "total_cost": round(total_cost, 4),
        "profit": round(1.0 - total_cost, 4),
        "profit_pct": round((1.0 - total_cost) / total_cost * 100, 2) if total_cost > 0 else 0,
        **metrics,
        # Tier
        "tier": tier,
        "tier_label": tier_label,
    }


def filter_portfolios_by_tier(
    portfolios: list[dict],
    max_tier: int = 2,
) -> list[dict]:
    """
    Filter portfolios by maximum tier.

    Args:
        portfolios: List of portfolios
        max_tier: Maximum tier to include (1 = best only)

    Returns:
        Filtered list
    """
    return [p for p in portfolios if p["tier"] <= max_tier]


def filter_portfolios_by_coverage(
    portfolios: list[dict],
    min_coverage: float = MIN_COVERAGE,
) -> list[dict]:
    """
    Filter portfolios by minimum coverage.

    Args:
        portfolios: List of portfolios
        min_coverage: Minimum coverage threshold

    Returns:
        Filtered list
    """
    return [p for p in portfolios if p["coverage"] >= min_coverage]


def sort_portfolios(portfolios: list[dict]) -> list[dict]:
    """Sort portfolios by tier (ascending) then coverage (descending)."""
    return sorted(portfolios, key=lambda p: (p["tier"], -p["coverage"]))
