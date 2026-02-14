#!/usr/bin/env python3
"""Trade execution - split + CLOB sell."""

import sys
import json
import time
import uuid
import asyncio
import argparse
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional
from pathlib import Path

# Add parent to path for lib imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env file from skill root directory
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from web3 import Web3

from lib.wallet_manager import WalletManager
from lib.gamma_client import GammaClient, Market
from lib.clob_client import ClobClientWrapper
from lib.contracts import CONTRACTS, CTF_ABI, POLYGON_CHAIN_ID
from lib.position_storage import PositionStorage, PositionEntry


@dataclass
class TradeResult:
    """Result of a trade execution."""

    success: bool
    market_id: str
    position: str
    amount: float
    split_tx: Optional[str]
    clob_order_id: Optional[str]
    clob_filled: bool
    error: Optional[str] = None
    question: str = ""
    wanted_token_id: str = ""
    entry_price: float = 0.0


from lib.executor import ExecutionEngine

async def buy_position(
    market_id: str,
    position: str,
    amount: float,
    skip_clob_sell: bool = False,
) -> TradeResult:
    """Buy a position using the unified ExecutionEngine."""
    wallet = WalletManager()
    if not wallet.is_unlocked:
        return TradeResult(success=False, market_id=market_id, position=position, amount=amount, split_tx=None, clob_order_id=None, clob_filled=False, error="Wallet locked")
        
    engine = ExecutionEngine(wallet)
    try:
        res = await engine.split_and_sell(market_id, position, amount, skip_sell=skip_clob_sell)
        
        market = await engine.gamma.get_market(market_id)
        
        return TradeResult(
            success=res["success"],
            market_id=market_id,
            position=position,
            amount=amount,
            split_tx=res["split_tx"],
            clob_order_id=res["clob_order_id"],
            clob_filled=res["clob_order_id"] is not None,
            error=res["clob_error"],
            question=market.question,
            wanted_token_id=res["wanted_token"],
            entry_price=market.yes_price if position == "YES" else market.no_price
        )
    except Exception as e:
        return TradeResult(success=False, market_id=market_id, position=position, amount=amount, split_tx=None, clob_order_id=None, clob_filled=False, error=str(e))


async def cmd_buy(args):
    """Execute buy command."""
    wallet = WalletManager()

    if not wallet.is_unlocked:
        print("Error: No wallet configured")
        print("Set POLYCLAW_PRIVATE_KEY environment variable.")
        return 1

    try:
        executor = TradeExecutor(wallet)
        result = await executor.buy_position(
            args.market_id,
            args.position,
            args.amount,
            skip_clob_sell=args.skip_sell,
        )

        print("\n" + "=" * 50)
        if result.success:
            print("Trade executed successfully!")
            print(f"  Market: {result.question[:50]}...")
            print(f"  Position: {result.position}")
            print(f"  Amount: ${result.amount:.2f}")
            print(f"  Split TX: {result.split_tx}")
            if result.clob_filled:
                print(f"  CLOB Order: {result.clob_order_id} (FILLED)")
            elif result.clob_order_id:
                print(f"  CLOB Order: {result.clob_order_id} (pending)")
            elif args.skip_sell:
                print(f"  CLOB: Skipped (--skip-sell)")
                print(f"  Note: You have both YES and NO tokens")
            else:
                print(f"  CLOB: Failed - {result.error}")
                unwanted = "NO" if result.position == "YES" else "YES"
                print(f"  Note: You have {result.amount:.0f} {unwanted} tokens to sell manually")

            # Record position
            storage = PositionStorage()
            position_entry = PositionEntry(
                position_id=str(uuid.uuid4()),
                market_id=result.market_id,
                question=result.question,
                position=result.position,
                token_id=result.wanted_token_id,
                entry_time=datetime.now(timezone.utc).isoformat(),
                entry_amount=result.amount,
                entry_price=result.entry_price,
                split_tx=result.split_tx,
                clob_order_id=result.clob_order_id,
                clob_filled=result.clob_filled,
            )
            storage.add(position_entry)
            print(f"  Position ID: {position_entry.position_id[:12]}...")
        else:
            print(f"Trade failed: {result.error}")
            return 1

        # Output JSON if requested
        if args.json:
            print("\nJSON Result:")
            print(json.dumps(asdict(result), indent=2))

        return 0

    finally:
        wallet.lock()


def main():
    parser = argparse.ArgumentParser(description="Trade execution")
    parser.add_argument("--json", action="store_true", help="JSON output")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Buy
    buy_parser = subparsers.add_parser("buy", help="Buy a position")
    buy_parser.add_argument("market_id", help="Market ID")
    buy_parser.add_argument("position", choices=["YES", "NO", "yes", "no"], help="YES or NO")
    buy_parser.add_argument("amount", type=float, help="Amount in USD")
    buy_parser.add_argument(
        "--skip-sell", action="store_true",
        help="Skip selling unwanted side (keep both YES and NO)"
    )

    args = parser.parse_args()

    if args.command == "buy":
        return asyncio.run(cmd_buy(args))
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main() or 0)
