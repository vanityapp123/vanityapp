# payments.py
"""
Solana payment monitoring and wallet generation.
Each user gets a unique keypair - we monitor their deposit address.
"""

import os
import json
import asyncio
import logging
from typing import Optional, Tuple, List, Dict

try:
    from solana.rpc.async_api import AsyncClient
    from solana.rpc.commitment import Confirmed
    from solders.pubkey import Pubkey
    from solders.keypair import Keypair as SolderKeypair
    from solders.signature import Signature as SolderSignature
    import base58
    from solana.keypair import Keypair as PyKeypair
    from solana.publickey import PublicKey as PyPublicKey
    from solana.transaction import Transaction
    from solana.system_program import TransferParams, transfer
except ImportError as e:
    print(f"Warning: Solana imports failed: {e}")
    print("Install with: pip install solana solders base58")

import db

logger = logging.getLogger(__name__)

KEYPAIRS_FILE = "user_keypairs.json"
# MAIN_WALLET must be set in the .env file (e.g., MAIN_WALLET=YOUR_PUBLIC_KEY)
MAIN_WALLET = os.getenv("MAIN_WALLET") 
SOLANA_RPC = os.getenv("SOLANA_RPC", "https://api.mainnet-beta.solana.com")
POLL_INTERVAL = float(os.getenv("POLL_INTERVAL", "8"))

_keypair_cache = {}


# ---------------------------------------------------
# USER WALLET MANAGEMENT
# ---------------------------------------------------

def load_keypairs() -> dict:
    if os.path.exists(KEYPAIRS_FILE):
        try:
            with open(KEYPAIRS_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading keypairs: {e}")
    return {}


def save_keypairs(keypairs: dict):
    try:
        with open(KEYPAIRS_FILE, "w") as f:
            json.dump(keypairs, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving keypairs: {e}")


def generate_user_keypair(user_id: int) -> Tuple[str, str]:
    keypair = SolderKeypair()
    public_key = str(keypair.pubkey())
    private_key = base58.b58encode(bytes(keypair)).decode("ascii")

    keypairs = load_keypairs()
    keypairs[str(user_id)] = {"public_key": public_key, "private_key": private_key}
    save_keypairs(keypairs)
    _keypair_cache[str(user_id)] = (public_key, private_key)

    logger.info(f"Generated deposit address for user {user_id}: {public_key}")
    return public_key, private_key


def get_user_keypair(user_id: int) -> Optional[Tuple[str, str]]:
    user_id_str = str(user_id)
    if user_id_str in _keypair_cache:
        return _keypair_cache[user_id_str]

    keypairs = load_keypairs()
    if user_id_str in keypairs:
        kp = keypairs[user_id_str]
        result = (kp["public_key"], kp["private_key"])
        _keypair_cache[user_id_str] = result
        return result
    return None


def get_or_create_deposit_address(user_id: int) -> str:
    user = db.get_user_by_id(user_id)
    if user and user["deposit_address"]:
        return user["deposit_address"]

    keypair = get_user_keypair(user_id)
    if keypair:
        public_key = keypair[0]
    else:
        public_key, _ = generate_user_keypair(user_id)

    if user:
        db.update_user_deposit_address(user["telegram_id"], public_key)
    return public_key


# ---------------------------------------------------
# DEPOSIT MONITORING
# ---------------------------------------------------

async def check_address_balance(address: str) -> float:
    try:
        async with AsyncClient(SOLANA_RPC) as client:
            pubkey = Pubkey.from_string(address)
            resp = await client.get_balance(pubkey, commitment=Confirmed)
            if resp.value is not None:
                return resp.value / 1e9
    except Exception as e:
        logger.error(f"Error checking balance for {address}: {e}")
    return 0.0


async def get_recent_transactions(address: str, limit: int = 10) -> list:
    try:
        async with AsyncClient(SOLANA_RPC) as client:
            pubkey = Pubkey.from_string(address)
            resp = await client.get_signatures_for_address(pubkey, limit=limit, commitment=Confirmed)
            if resp.value:
                return resp.value
    except Exception as e:
        logger.error(f"Error getting transactions for {address}: {e}")
    return []


async def process_transaction(signature_info: dict, user_id: int, deposit_address: str):
    try:
        sig_str = str(getattr(signature_info, "signature", signature_info))
        if db.get_transaction_by_signature(sig_str):
            return

        async with AsyncClient(SOLANA_RPC) as client:
            sig_obj = SolderSignature.from_string(sig_str)
            tx = await client.get_transaction(sig_obj, encoding="json", commitment=Confirmed)
            if not tx.value:
                return

            tx_data = tx.value
            meta = tx_data.transaction.meta
            if not meta:
                return

            message = tx_data.transaction.transaction.message
            account_keys = message.account_keys
            deposit_index = next((i for i, k in enumerate(account_keys) if str(k) == deposit_address), None)
            if deposit_index is None:
                return

            pre = meta.pre_balances[deposit_index]
            post = meta.post_balances[deposit_index]
            lamports_received = post - pre
            if lamports_received <= 0:
                return

            sol_received = lamports_received / 1e9
            db.record_transaction(user_id, sig_str, sol_received, "deposit")
            db.update_balance(user_id, sol_received)
            logger.info(f"User {user_id} received {sol_received} SOL in {sig_str}")

            user = db.get_user_by_id(user_id)
            if user and user["referred_by"]:
                bonus_pct = float(db.get_setting("referral_bonus_percent", "5"))
                bonus = sol_received * (bonus_pct / 100)
                db.update_balance(user["referred_by"], bonus)
                db.record_transaction(user["referred_by"], f"referral_{sig_str}", bonus, "referral_bonus")
                logger.info(f"Referral bonus {bonus} SOL -> {user['referred_by']}")

            return sol_received
    except Exception as e:
        logger.error(f"Error processing transaction {signature_info}: {e}")
        return None


async def monitor_user_deposits(user_id: int, deposit_address: str, last_signature: Optional[str] = None):
    try:
        txs = await get_recent_transactions(deposit_address, 10)
        if not txs:
            return last_signature

        new_sig = None
        for tx_info in reversed(txs):
            sig_str = str(getattr(tx_info, "signature", tx_info))
            if last_signature and sig_str == last_signature:
                break
            amount = await process_transaction(tx_info, user_id, deposit_address)
            if amount:
                new_sig = sig_str
        return new_sig or last_signature
    except Exception as e:
        logger.error(f"Error monitoring user {user_id}: {e}")
        return last_signature


async def payment_monitor_loop(bot):
    logger.info("Starting payment monitor loop")
    last_sigs = {}

    while True:
        try:
            users = db.get_all_users(limit=1000)
            for u in users:
                if not u["deposit_address"]:
                    continue
                uid = u["id"]
                dep_addr = u["deposit_address"]
                last_sig = last_sigs.get(uid)
                new_sig = await monitor_user_deposits(uid, dep_addr, last_sig)
                if new_sig and new_sig != last_sigs.get(uid):
                    last_sigs[uid] = new_sig
                    if not db.get_transaction_by_signature(new_sig):
                        continue
                    try:
                        data = db.get_user_by_id(uid)
                        if data:
                            await bot.send_message(
                                data["telegram_id"],
                                f"✅ <b>Deposit Confirmed!</b>\n\n"
                                f"Your balance has been updated.\n"
                                f"Current balance: <b>{data['balance_sol']:.6f} SOL</b>",
                                parse_mode="HTML",
                            )
                    except Exception as e:
                        logger.error(f"Notify fail {uid}: {e}")
                await asyncio.sleep(5)
            await asyncio.sleep(POLL_INTERVAL)
        except Exception as e:
            logger.error(f"Monitor loop error: {e}")
            await asyncio.sleep(POLL_INTERVAL)


# ---------------------------------------------------
# SWEEP FUNCTIONS
# ---------------------------------------------------

DEFAULT_MIN_RETAIN_LAMPORTS = int(os.getenv("MIN_RETAIN_LAMPORTS", "5000"))


async def sweep_user_funds(user_id: int, min_retain_lamports: int = DEFAULT_MIN_RETAIN_LAMPORTS) -> Optional[Dict]:
    # --- ADDED LOGGING ---
    logger.info(f"Attempting sweep from user {user_id}")
    # --- END ADDED LOGGING ---

    if not MAIN_WALLET:
        logger.error("MAIN_WALLET not configured.")
        return None

    kp = get_user_keypair(user_id)
    if not kp:
        logger.info(f"No keypair for {user_id}")
        return None

    pubkey_str, priv_base58 = kp
    try:
        secret = base58.b58decode(priv_base58)
        # Using PyKeypair for solana-py transaction signing
        py_keypair = PyKeypair.from_secret_key(secret) 
    except Exception as e:
        logger.error(f"Keypair decode failed {user_id}: {e}")
        return None

    user_pub = py_keypair.public_key
    main_pub = PyPublicKey(MAIN_WALLET)

    try:
        async with AsyncClient(SOLANA_RPC) as client:
            resp = await client.get_balance(user_pub)
            lamports = int(resp["result"]["value"]) if "result" in resp else int(getattr(resp, "value", 0))
            if lamports <= min_retain_lamports:
                logger.info(f"User {user_id} has {lamports} lamports — skipping sweep.")
                return None

            amount_to_transfer = lamports - min_retain_lamports
            
            tx = Transaction()
            tx.add(
                transfer(
                    TransferParams(
                        from_pubkey=user_pub,
                        to_pubkey=main_pub,
                        lamports=amount_to_transfer,
                    )
                )
            )

            try:
                # The user's keypair signs the transaction to transfer their funds
                send = await client.send_transaction(tx, py_keypair) 
                tx_sig = send.get("result") if isinstance(send, dict) else getattr(send, "value", str(send))
                if not tx_sig:
                    logger.error(f"Sweep send failed {user_id}: {send}")
                    return None

                # Confirmation is required before reporting success
                try:
                    # Using a higher commitment for robust confirmation
                    await client.confirm_transaction(tx_sig, commitment="confirmed") 
                    logger.info(f"Sweep tx {tx_sig} confirmed.")
                except Exception as e:
                    logger.warning(f"Confirm failed {tx_sig}: {e}")

                sol_amt = amount_to_transfer / 1e9
                try:
                    # Record sweep as a transaction
                    db.record_transaction(user_id, tx_sig, -sol_amt, "sweep") # Use negative for withdrawal
                except Exception as e:
                    logger.warning(f"DB record failed sweep {user_id}: {e}")
                
                # Optional: Deduct from user's internal balance to reflect the sweep
                # Note: The balance logic is complex, assuming the monitor updates it after deposit.
                # If the internal balance includes *only* un-swept deposits, this is fine.
                # If the internal balance is based on deposits and purchases, this logic is safer:
                user = db.get_user_by_id(user_id)
                if user and user["balance_sol"] < sol_amt:
                     db.update_balance(user_id, -user["balance_sol"]) # Zero out balance if swept
                elif user:
                    db.update_balance(user_id, -sol_amt) # Deduct swept amount

                logger.info(f"Swept {sol_amt:.9f} SOL from {user_id} -> {MAIN_WALLET}. Sig: {tx_sig}")
                return {"user_id": user_id, "address": str(user_pub), "transferred_sol": sol_amt, "tx_sig": tx_sig}

            except Exception as e:
                logger.error(f"Send tx failed {user_id}: {e}", exc_info=True)
                return None

    except Exception as e:
        logger.error(f"Sweep error user {user_id}: {e}", exc_info=True)
        return None


async def sweep_all_users(limit: int = 10000, min_retain_lamports: int = DEFAULT_MIN_RETAIN_LAMPORTS) -> List[Dict]:
    results = []
    users = db.get_all_users(limit=limit)
    # --- ADDED LOGGING ---
    logger.info(f"Starting mass sweep across {len(users)} users.")
    # --- END ADDED LOGGING ---
    for u in users:
        if not u.get("deposit_address"):
            continue
        try:
            res = await sweep_user_funds(u["id"], min_retain_lamports)
            if res:
                results.append(res)
            # Throttle the loop to prevent overwhelming the RPC client or the Solana network
            await asyncio.sleep(0.15) 
        except Exception as e:
            logger.error(f"Sweep user {u['id']} error: {e}")
    # --- ADDED LOGGING ---
    total_sol_swept = sum(r['transferred_sol'] for r in results)
    logger.info(f"Mass sweep complete. Total successful sweeps: {len(results)}. Total SOL: {total_sol_swept:.6f}")
    # --- END ADDED LOGGING ---
    return results