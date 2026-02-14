#!/usr/bin/env python3
import asyncio
import os
import sys
import argparse
from pathlib import Path

# Add parent to path for lib imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.gamma_client import GammaClient
from lib.arbitrage import calculate_split_arbitrage, calculate_negrisk_arbitrage
from lib.wallet_manager import WalletManager
from lib.executor import ExecutionEngine

async def scan():
    gamma = GammaClient()
    parser = argparse.ArgumentParser(description="Scan for arbitrage opportunities")
    subparsers = parser.add_subparsers(dest="command")
    
    execute_parser = subparsers.add_parser("execute", help="Execute an arbitrage plan")
    execute_parser.add_argument("--query", "-q", help="Plan ID to execute (e.g. ETH_1.9k)")
    execute_parser.add_argument("--amount", type=float, default=10.0, help="Total USD to spend across all legs")

    scan_parser = subparsers.add_parser("scan", help="Scan for opportunities")
    scan_parser.add_argument("--query", "-q", help="Asset to scan (BTC, ETH, XRP)")
    scan_parser.add_argument("--threshold", type=float, default=0.01, help="Min profit threshold")
    
    args = parser.parse_args()

    if args.command == "execute":
        if not args.query:
            print("Error: Specify plan ID via --query (e.g. ETH_1.9k)")
            return

        wallet = WalletManager()
        if not wallet.is_unlocked:
             print("Error: Wallet locked")
             return

        engine = ExecutionEngine(wallet)
        # Fetch targets for identified plans
        target_splits = []
        if args.query.upper() == "ETH_1.9K":
             target_splits = [
                {"agg": "1345784", "comp": ["1345816", "1345786"], "id": "1.9k"},
             ]
        
        for split in target_splits:
            agg = await gamma.get_market(split["agg"])
            comps = [await gamma.get_market(cid) for cid in split["comp"]]
            portfolio = calculate_split_arbitrage(agg, comps)
            
            # Fetch fresh prices to verify one last time
            all_token_ids = [leg.token_id for leg in portfolio.legs]
            prices = await gamma.get_prices(all_token_ids, side="BUY")
            current_cost = sum([prices.get(tid, 1.0) for tid in all_token_ids])
            
            if (1.0 - current_cost) < 0:
                print(f"ABORT: Spread disappeared! Current cost: {current_cost:.4f}")
                return

            print(f"STARTING EXECUTION: {portfolio.description}")
            steps = portfolio.get_execution_steps(args.amount)
            
            for step in steps:
                print(f"Step: {step.description} (${step.amount:.2f})")
                res = await engine.split_and_sell(step.market_id, step.position, step.amount)
                if res["success"]:
                    print(f"  TX: {res['split_tx']}")
                    if res["clob_order_id"]:
                         print(f"  Sell Filled: {res['clob_order_id']}")
                    else:
                         print(f"  Sell Error/Manual required: {res['clob_error']}")
                else:
                    print(f"  FAILED step: {step.description}")
                    return

    elif args.command == "scan":
        gamma = GammaClient()
    print(f"--- ANTIGRAVITY SURGICAL SCAN: {args.query or 'Global'} ---")

    # 1. Hierarchical Split Scan (Specialized for ETH/BTC)
    if args.query and args.query.upper() in ["ETH", "BTC"]:
        print(f"\n[PHASE 1] Checking Hierarchical Splits for {args.query.upper()}...")
        # Define known splits or search for them
        # For MVP, we use the verified IDs for Feb 13
        target_splits = []
        if args.query.upper() == "ETH":
            target_splits = [
                {"agg": "1345781", "comp": ["1345815", "1345784"], "id": "1.8k"},
                {"agg": "1345784", "comp": ["1345816", "1345786"], "id": "1.9k"},
                {"agg": "1345786", "comp": ["1345818", "1345789"], "id": "2.0k"},
            ]
        elif args.query.upper() == "BTC":
            target_splits = [
                {"agg": "1345814", "comp": ["1345780", "1345817"], "id": "64k"},
                {"agg": "1345817", "comp": ["1345783", "1345819"], "id": "66k"},
                {"agg": "1345819", "comp": ["1345785", "1345822"], "id": "68k"},
            ]

        for split in target_splits:
            agg = await gamma.get_market(split["agg"])
            comps = [await gamma.get_market(cid) for cid in split["comp"]]
            
            portfolio = calculate_split_arbitrage(agg, comps)
            
            # Fetch fresh prices
            all_token_ids = [leg.token_id for leg in portfolio.legs]
            prices = await gamma.get_prices(all_token_ids, side="BUY")
            
            # Update portfolio with fresh prices
            current_cost = 0.0
            for leg in portfolio.legs:
                leg.price = prices.get(leg.token_id, 1.0)
                current_cost += leg.price
            
            portfolio.total_cost = current_cost
            portfolio.profit_margin = 1.0 - current_cost
            
            if portfolio.profit_margin >= args.threshold:
                print(f"  [ALERT] {split['id']} Split | Profit: {portfolio.profit_margin*100:.2f}%")
                print(f"  Plan: {portfolio.description}")
                for step in portfolio.get_execution_steps(100.0): # Mock $100
                    print(f"    - Buy {step.position} on {step.market_id} (${step.amount:.2f})")
            else:
                print(f"  {split['id']} Scan | Profit: {portfolio.profit_margin*100:.2f}%")

    # 2. NegRisk Scan (Event-based)
    print("\n[PHASE 2] Checking NegRisk Groupings...")
    # This would ideally use Gamma's event API to find Mutually Exclusive groups
    # For now, we report the high-confidence XRP bracket we verified
    if not args.query or args.query.upper() == "XRP":
        xrp_ids = ["1345858", "1345860", "1345862", "1345865", "1345867", "1345869", "1345871", "1345873", "1345875", "1345877", "1345880"]
        total_yes = 0
        token_ids = []
        markets = []
        for mid in xrp_ids:
            m = await gamma.get_market(mid)
            markets.append(m)
            token_ids.append(m.yes_token_id)
        
        prices = await gamma.get_prices(token_ids, side="BUY")
        total_yes = sum([prices.get(tid, 1.0) for tid in token_ids])
        
        profit = (1.0 - total_yes) * 100
        if profit >= args.threshold * 100:
             print(f"  [ALERT] XRP Pricing Bracket | Profit: {profit:.2f}% | Yes Sum: {total_yes:.4f}")
        else:
             print(f"  XRP Scan | Profit: {profit:.2f}%")

if __name__ == "__main__":
    asyncio.run(scan())
