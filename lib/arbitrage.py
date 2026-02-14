"""Core arbitrage logic for PolyClaw."""
from dataclasses import dataclass
from typing import List, Dict

@dataclass
class ArbitrageLeg:
    token_id: str
    side: str  # "YES" or "NO"
    price: float
    market_id: str
    question: str

@dataclass
class ExecutionStep:
    market_id: str
    position: str
    amount: float
    description: str

@dataclass
class ArbitragePortfolio:
    type: str  # "SPLIT" or "NEGRISK"
    legs: List[ArbitrageLeg]
    total_cost: float
    profit_margin: float
    description: str
    
    def get_execution_steps(self, total_capital: float) -> List[ExecutionStep]:
        """Generate 'Split + Sell' steps for this portfolio."""
        steps = []
        for leg in self.legs:
            # For each leg, we need to split $Amount and sell the OTHER side
            # Leg price is the 'market price' we used for calculation
            steps.append(ExecutionStep(
                market_id=leg.market_id,
                position=leg.side,
                amount=total_capital * (leg.price / self.total_cost),
                description=f"Enter {leg.side} on {leg.market_id} via Split"
            ))
        return steps

def calculate_split_arbitrage(agg_market, component_markets) -> ArbitragePortfolio:
    """
    Calculate spread for hierarchical split:
    Agg NO + Component1 YES + Component2 YES ...
    Total cost < 1.0 implies arbitrage.
    """
    legs = []
    # Buy Aggregate NO
    legs.append(ArbitrageLeg(
        token_id=agg_market.no_token_id,
        side="NO",
        price=agg_market.no_price,
        market_id=agg_market.id,
        question=agg_market.question
    ))
    
    total_cost = agg_market.no_price
    
    # Buy all components YES
    for m in component_markets:
        legs.append(ArbitrageLeg(
            token_id=m.yes_token_id,
            side="YES",
            price=m.yes_price,
            market_id=m.id,
            question=m.question
        ))
        total_cost += m.yes_price
        
    profit = 1.0 - total_cost
    
    return ArbitragePortfolio(
        type="SPLIT",
        legs=legs,
        total_cost=total_cost,
        profit_margin=profit,
        description=f"Hierarchical Split on {agg_market.question}"
    )

def calculate_negrisk_arbitrage(markets) -> ArbitragePortfolio:
    """
    Calculate spread for NegRisk (Mutually Exclusive Outcomes):
    Sum(YES prices) < 1.0 implies arbitrage.
    """
    legs = []
    total_cost = 0.0
    
    for m in markets:
        legs.append(ArbitrageLeg(
            token_id=m.yes_token_id,
            side="YES",
            price=m.yes_price,
            market_id=m.id,
            question=m.question
        ))
        total_cost += m.yes_price
        
    profit = 1.0 - total_cost
    
    return ArbitragePortfolio(
        type="NEGRISK",
        legs=legs,
        total_cost=total_cost,
        profit_margin=profit,
        description=f"Negative Risk on Event group ({len(markets)} outcomes)"
    )
