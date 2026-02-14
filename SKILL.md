---
description: PolyClaw - The Surgical Polymarket Arbitrage Engine
---

# PolyClaw: Advanced Polymarket Arbitrage & Hedging

**PolyClaw** is a high-performance, modular toolkit designed for surgical arbitrage and hedging on Polymarket (Polygon). It bypasses the limitations of the standard web UI by interacting directly with the Gamma API (Events/Markets) and the CLOB API (Order Execution).

## 🚀 Core Capabilities

### 1. Unified CLI (`scripts/polyclaw.py`)
The central entry point for all operations. Do not run individual scripts unless debugging.

```bash
# General Usage
uv run python scripts/polyclaw.py [COMMAND] [ARGS]
```

#### Commands:
- **`audit`**: Comprehensive portfolio health check.
    - Displays USDC.e/POL balances (and allowance).
    - Lists active positions with current market value.
    - Shows recent fill history.
- **`arb scan`**: Scans for arbitrage opportunities.
    - **Split Arb**: Checks Aggregate vs. Component markets (e.g., "Will ETH > $2000?" vs "$2100", "$2200"...).
    - **NegRisk Arb**: Checks Mutually Exclusive events for "Sum of Prices < 1.0" or "Sum of Prices > 1.0" (Cost basis arb).
- **`hedge scan`**: AI-driven discovery of hedging opportunities based on portfolio correlation.

### 2. Surgical Execution Engine (`lib/executor.py`)
A robust, safety-first execution module handling the complex "Split & Sell" lifecycle.

- **Atomic-like Operations**:
    1.  **Liquidity Check**: Verifies CLOB depth before committing capital.
    2.  **Mint**: Interacts with the specific CTF or NegRiskAdapter contract to merge/split positions.
    3.  **Sell**: Executes robust sell orders (FOK -> IOC -> Limit) to ensure exit.
- **Safety**: Aborts if spread tightens or liquidity vanishes during pre-flight.

## 📂 Architecture

### `lib/` (The Brain)
- **`gamma_client.py`**: Fetches market metadata, prices, and event structures.
- **`clob_client.py`**: Handles order placement, cancellation, and order book retrieval. Implements proxy rotation and retry logic.
- **`contracts.py`**: ABI definitions and address management for CTF Exchange and NegRisk Adapter (Crucial for correct minting).
- **`executor.py`**: Orchestrates the "Mint -> Trade" workflow.
- **`wallet_manager.py`**: Manages private keys and Polygon RPC connections.

### `scripts/` (The Hands)
- **`polyclaw.py`**: The CLI commander.
- **`audit.py`**: Standalone audit tool (invoked by CLI).
- **`scan_arbitrage.py`**: The scanner (invoked by CLI).
- **`hedge.py`**: Hedging logic.

## 🛠️ Setup & Configuration

1.  **Environment Variables**:
    Required in `.env`:
    - `PRIVATE_KEY`: Your Polygon EOA key (starts with `0x`).
    - `POLYGON_RPC_URL`: A reliable RPC endpoint (e.g., Alchemy/Infura).
    - `CLOB_API_KEY` / `CLOB_API_SECRET` / `CLOB_PASSPHRASE`: Polymarket API credentials.

2.  **Dependencies**:
    Managed via `uv` (or `pip`). Ensure `web3`, `py-clob-client`, `requests` are installed.

## ⚠️ Critical Operational Notes

1.  **NegRisk Transparency**:
    - **Exchange** (`0xC5d563..`) is for TRADING.
    - **Adapter** (`0xd91E80..`) is for MINTING/MERGING.
    - *Never send merge transactions to the Exchange.*

2.  **Liquidity Reality**:
    - "Volume" does not equal "Liquidity". A market can have $10M volume but 0 bids.
    - **Always verify the Order Book** before execution.

3.  **Position IDs**:
    - `0` = NO (Long Token)
    - `1` = YES (Long Token)
    - NegRisk IDs are derived from `questionId` + index byte.

---
*Maintained by the Antigravity Team (Linus Persona).*
