#!/usr/bin/env python3
import asyncio
import os
import sys
import httpx
import time
from pathlib import Path

# Add parent to path for lib imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.gamma_client import GammaClient
from py_clob_client.client import ClobClient

DATA_API = "https://data-api.polymarket.com"

async def run_audit():
    PRIVATE_KEY = os.getenv("POLYCLAW_PRIVATE_KEY")
    if not PRIVATE_KEY:
        print("Error: POLYCLAW_PRIVATE_KEY not set.")
        return

    client = ClobClient("https://clob.polymarket.com", key=PRIVATE_KEY, chain_id=137)
    
    try:
        creds = client.derive_api_key()
        client.set_api_creds(creds)
    except:
        pass

    address = client.get_address()
    print(f"--- POLYMARKET AUDIT: {address} ---")
    
    # 1. Balance
    print("\n[BALANCE]")
    try:
        bal = client.get_balance_allowance()
        balance = bal.get("balance", "0") if isinstance(bal, dict) else getattr(bal, "balance", "0")
        allowance = bal.get("allowance", "0") if isinstance(bal, dict) else getattr(bal, "allowance", "0")
        print(f"  USDC: {balance:<10} | Allowance: {allowance}")
    except Exception as e:
        print(f"  Error: {e}")

    # 2. Positions
    print("\n[POSITIONS]")
    async with httpx.AsyncClient() as http:
        try:
            resp = await http.get(f"{DATA_API}/positions", params={"user": address})
            if resp.status_code == 200:
                pos_list = resp.json()
                if not pos_list:
                    print("  No active positions.")
                else:
                    print(f"  {'Outcome':<8} | {'Size':<8} | {'Avg Px':<8} | {'Cur Px':<8} | {'Question'}")
                    print(f"  " + "-" * 100)
                    for p in pos_list:
                        sz = float(p.get("size", 0))
                        if sz > 0.1:
                            print(f"  {p.get('outcome'):<8} | {sz:<8.1f} | {p.get('avgPrice'):<8.3f} | {p.get('curPrice'):<8.3f} | {p.get('title')[:60]}")
            else:
                print(f"  Data API Error: {resp.status_code}")
        except Exception as e:
            print(f"  Data API Exception: {e}")

    # 3. Recent Trades
    print("\n[RECENT TRADES]")
    try:
        trades = client.get_trades()
        if not trades:
            print("  No recent trades found.")
        else:
            print(f"  {'Time':<20} | {'Side':<5} | {'Size':<8} | {'Price':<8}")
            print(f"  " + "-" * 50)
            for t in trades[:5]:
                t_ts = t.get("timestamp") if isinstance(t, dict) else getattr(t, "timestamp", 0)
                side = t.get("side") if isinstance(t, dict) else getattr(t, "side", "?")
                size = t.get("size") if isinstance(t, dict) else getattr(t, "size", "?")
                price = t.get("price") if isinstance(t, dict) else getattr(t, "price", "?")
                t_str = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(float(t_ts))) if t_ts else "Unknown"
                print(f"  {t_str:<20} | {side:<5} | {size:<8} | {price:<8}")
    except Exception as e:
        print(f"  Error: {e}")

if __name__ == "__main__":
    asyncio.run(run_audit())
