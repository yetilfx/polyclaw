"""Unified execution engine for PolyClaw - Split + Sell logic."""
import time
import asyncio
from typing import Optional, Tuple
from web3 import Web3
from lib.contracts import CONTRACTS, CTF_ABI, POLYGON_CHAIN_ID
from lib.wallet_manager import WalletManager
from lib.clob_client import ClobClientWrapper
from lib.gamma_client import GammaClient

class ExecutionEngine:
    """Consolidated engine for on-chain split and CLOB sell operations."""
    
    def __init__(self, wallet: WalletManager):
        self.wallet = wallet
        self.gamma = GammaClient()
        self.w3 = Web3(Web3.HTTPProvider(self.wallet.rpc_url, request_kwargs={"timeout": 60, "proxies": {}}))
        
    async def split_and_sell(
        self, 
        market_id: str, 
        position: str, 
        amount_usd: float,
        skip_sell: bool = False
    ) -> dict:
        """
        Executes the 'Split + Sell' pattern:
        1. Split USDC.e into YES + NO tokens.
        2. Sell the unwanted side via CLOB.
        """
        position = position.upper()
        market = await self.gamma.get_market(market_id)
        
        # 0. Pre-Check Liquidity
        unwanted_token = market.no_token_id if position == "YES" else market.yes_token_id
        unwanted_price = market.no_price if position == "YES" else market.yes_price
        
        if not skip_sell:
            print(f"Checking liquidity for {unwanted_token[:8]} to sell ${amount_usd} at ~{unwanted_price:.2f}...")
            clob = ClobClientWrapper(self.wallet.get_unlocked_key(), self.wallet.address)
            # Accept slippage down to 5 cents for the check (we really just want ANY liquidity depth)
            has_liquidity = clob.check_liquidity(unwanted_token, "sell", amount_usd, 0.05)
            
            if not has_liquidity:
                return {
                    "success": False,
                    "error": f"Insufficient liquidity to sell ${amount_usd}. Aborting Split."
                }
        
        # 1. Split
        print(f"Executing Split for {market.question[:50]}... (${amount_usd})")
        tx_hash = self._split_position(market.condition_id, amount_usd)
        
        # 2. Sell Unwanted
        clob_order_id = None
        clob_error = None
        
        if not skip_sell:
            print(f"Selling unwanted {unwanted_token[:8]}... at ~{unwanted_price:.2f}")
            # clob client already initialized above
            clob_order_id, filled, clob_error = clob.sell_robust(unwanted_token, amount_usd, unwanted_price)
            
        return {
            "success": True,
            "split_tx": tx_hash,
            "clob_order_id": clob_order_id,
            "clob_error": clob_error,
            "wanted_token": market.yes_token_id if position == "YES" else market.no_token_id
        }

    def _split_position(self, condition_id: str, amount_usd: float) -> str:
        """Internal helper for on-chain split."""
        address = Web3.to_checksum_address(self.wallet.address)
        account = self.w3.eth.account.from_key(self.wallet.get_unlocked_key())
        
        ctf = self.w3.eth.contract(
            address=Web3.to_checksum_address(CONTRACTS["CTF"]),
            abi=CTF_ABI,
        )
        
        amount_wei = int(amount_usd * 1e6)
        condition_bytes = bytes.fromhex(condition_id[2:] if condition_id.startswith("0x") else condition_id)
        
        tx = ctf.functions.splitPosition(
            Web3.to_checksum_address(CONTRACTS["USDC_E"]),
            bytes(32),
            condition_bytes,
            [1, 2],
            amount_wei,
        ).build_transaction({
            "from": address,
            "nonce": self.w3.eth.get_transaction_count(address),
            "gas": 300000,
            "gasPrice": self.w3.eth.gas_price,
            "chainId": POLYGON_CHAIN_ID,
        })
        
        signed = account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        
        if receipt["status"] != 1:
            raise ValueError(f"Split failed: {tx_hash.hex()}")
            
        return tx_hash.hex()

    def merge_positions(self, condition_id: str, amount_usd: float) -> str:
        """Merge YES and NO tokens back into USDC.e."""
        address = Web3.to_checksum_address(self.wallet.address)
        account = self.w3.eth.account.from_key(self.wallet.get_unlocked_key())
        
        ctf = self.w3.eth.contract(
            address=Web3.to_checksum_address(CONTRACTS["CTF"]),
            abi=CTF_ABI,
        )
        
        amount_wei = int(amount_usd * 1e6)
        condition_bytes = bytes.fromhex(condition_id[2:] if condition_id.startswith("0x") else condition_id)
        
        tx = ctf.functions.mergePositions(
            Web3.to_checksum_address(CONTRACTS["USDC_E"]),
            bytes(32),
            condition_bytes,
            [1, 2],
            amount_wei,
        ).build_transaction({
            "from": address,
            "nonce": self.w3.eth.get_transaction_count(address),
            "gas": 300000,
            "gasPrice": self.w3.eth.gas_price,
            "chainId": POLYGON_CHAIN_ID,
        })
        
        signed = account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        
        if receipt["status"] != 1:
            raise ValueError(f"Merge failed: {tx_hash.hex()}")
            
        return tx_hash.hex()

    def redeem_positions(self, condition_id: str) -> str:
        """Redeem settled positions for collateral."""
        address = Web3.to_checksum_address(self.wallet.address)
        account = self.w3.eth.account.from_key(self.wallet.get_unlocked_key())
        
        # We need the redeemPositions ABI
        REDEMPTION_ABI = [
            {
                "inputs": [
                    {"name": "collateralToken", "type": "address"},
                    {"name": "parentCollectionId", "type": "bytes32"},
                    {"name": "conditionId", "type": "bytes32"},
                    {"name": "indexSets", "type": "uint256[]"},
                ],
                "name": "redeemPositions",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function",
            }
        ]
        
        ctf = self.w3.eth.contract(
            address=Web3.to_checksum_address(CONTRACTS["CTF"]),
            abi=CTF_ABI + REDEMPTION_ABI,
        )
        
        condition_bytes = bytes.fromhex(condition_id[2:] if condition_id.startswith("0x") else condition_id)
        
        tx = ctf.functions.redeemPositions(
            Web3.to_checksum_address(CONTRACTS["USDC_E"]),
            bytes(32),
            condition_bytes,
            [1, 2], # YES and NO
        ).build_transaction({
            "from": address,
            "nonce": self.w3.eth.get_transaction_count(address),
            "gas": 300000,
            "gasPrice": self.w3.eth.gas_price,
            "chainId": POLYGON_CHAIN_ID,
        })
        
        signed = account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        
        if receipt["status"] != 1:
            raise ValueError(f"Redeem failed: {tx_hash.hex()}")
            
        return tx_hash.hex()
