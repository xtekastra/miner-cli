from __future__ import annotations

import asyncio
import os
import sys

import bittensor as bt
from bittensor.core.async_subtensor import AsyncSubtensor
from bittensor.core.chain_data.stake_info import StakeInfo
from bittensor.utils.balance import Balance
from dotenv import load_dotenv

load_dotenv()

DEFAULT_WALLET_NAME = os.getenv("DEFAULT_WALLET_NAME")
BT_NETWORK = os.getenv("BT_NETWORK", "finney")
MIN_REMAINING_ALPHA_TAO = 0.1


def _max_retry_limit_from_env() -> int | None:
    raw = os.getenv("MAX_RETRY_COUNT", "10")
    try:
        n = int(raw.strip(), 10)
    except ValueError:
        print("Warning: MAX_RETRY_COUNT must be an integer; using default 10.", file=sys.stderr)
        return 10
    if n <= 0:
        return None
    return n


MAX_RETRY_LIMIT = _max_retry_limit_from_env()


def _log(tag: str, message: str) -> None:
    print(f"[{tag}] {message}")


def _ss58_short(addr: str, head: int = 8, tail: int = 6) -> str:
    if len(addr) <= head + tail + 1:
        return addr
    return f"{addr[:head]}…{addr[-tail:]}"


async def build_call(subtensor: AsyncSubtensor, ck_addr: str, remove_stake_list: list[tuple[str, int]], limit_price: float | None = None):
    calls = []
    for hotkey_ss58, netuid in remove_stake_list:
        remaining_alpha = await subtensor.get_stake(coldkey_ss58=ck_addr, hotkey_ss58=hotkey_ss58, netuid=netuid)
        min_remaining = Balance.from_tao(MIN_REMAINING_ALPHA_TAO, netuid=netuid)
        if remaining_alpha > min_remaining:
            remove_call = await subtensor.compose_call(
                call_module="SubtensorModule",
                call_function="remove_stake_full_limit",
                call_params={
                    "hotkey": hotkey_ss58,
                    "netuid": netuid,
                    "limit_price": limit_price,
                },
            )
            calls.append(remove_call)
    if not calls:
        return None, 0
    force_batch_call = await subtensor.compose_call(
        call_module="Utility",
        call_function="force_batch",
        call_params={"calls": calls},
    )
    return force_batch_call, len(calls)


async def main() -> None:
    async with AsyncSubtensor(network=BT_NETWORK, websocket_shutdown_timer=None) as subtensor:
        chain = await subtensor.substrate.rpc_request("system_chain", [])
        runtime_version = await subtensor.substrate.rpc_request("state_getRuntimeVersion", [])
        _log("connect", f"{chain['result']}  endpoint={subtensor.chain_endpoint}  spec_version={runtime_version['result']['specVersion']}")

        default_hint = DEFAULT_WALLET_NAME or "(none)"
        wallet_name = input(f"Wallet name [Enter = default {default_hint}]: ").strip() or DEFAULT_WALLET_NAME
        if not wallet_name:
            raise ValueError("Wallet name is required")
        try:
            netuid = int(input("Subnet netuid: ").strip())
        except ValueError:
            raise ValueError("Netuid must be an integer") from None
        if netuid < 0 or netuid > 128:
            raise ValueError("Netuid must be between 0 and 128")

        wallet = bt.Wallet(name=wallet_name)
        wallet.unlock_coldkey()
        ck_addr = wallet.coldkey.ss58_address
        _log("wallet", f"{wallet_name}  coldkey={_ss58_short(ck_addr)}({await subtensor.get_balance(ck_addr)})")

        _log("stake", f"Loading alpha positions for netuid {netuid}…")
        stake_info: list[StakeInfo] = await subtensor.get_stake_info_for_coldkey(ck_addr)

        current_price = (await subtensor.get_subnet_price(netuid)).tao
        _log("price", f"subnet {netuid}  current={current_price} TAO")

        limit_raw = input("Limit price [Enter = market / no limit]: ").strip()
        if not limit_raw:
            limit_price = None
        else:
            try:
                limit_price = float(limit_raw)
            except ValueError:
                raise ValueError("Limit price must be a number") from None

        remove_stake_list: list[tuple[str, int]] = []
        for si in stake_info:
            print()
            _log("position", f"netuid {si.netuid}  hotkey {_ss58_short(si.hotkey_ss58)}")
            print(f"         hotkey {si.hotkey_ss58}")
            print(f"         alpha  {si.stake}")
            if si.netuid == netuid:
                yes_or_no = input("Remove stake for this position? [y/N]: ").strip().lower()
                if yes_or_no == "y":
                    remove_stake_list.append((si.hotkey_ss58, si.netuid))
                else:
                    _log("skip", f"netuid {si.netuid}  hotkey {_ss58_short(si.hotkey_ss58)}")
                    continue
            else:
                _log("skip", f"netuid {si.netuid}  hotkey {_ss58_short(si.hotkey_ss58)}")
                continue

        call = None
        batch_n = 0
        retry_count = 0

        while True:
            if MAX_RETRY_LIMIT is not None and retry_count >= MAX_RETRY_LIMIT:
                _log("abort", f"Stopped after {MAX_RETRY_LIMIT} retries.")
                break
            if not call:
                call, batch_n = await build_call(subtensor=subtensor, ck_addr=ck_addr, remove_stake_list=remove_stake_list, limit_price=limit_price)
                if not call:
                    _log("batch", "Nothing to submit (no removable stake above threshold).")
                    break
                _log("batch", f"Ready: {batch_n} remove call(s) in one force_batch.")
                retry_count += 1

            limit_str = "market" if limit_price is None else str(limit_price)
            _log("wait", f"Next block…  subnet={netuid}  limit={limit_str}")
            await subtensor.wait_for_block()

            current_price = (await subtensor.get_subnet_price(netuid)).tao
            if limit_price is None or current_price > limit_price:
                _log("submit", f"Submitting batch of {batch_n} remove(s)…")
                resp = await subtensor.mev_submit_encrypted(wallet=wallet, call=call)
                if resp.success:
                    _log("submit", f"Success — batch of {batch_n} remove(s) completed.")
                else:
                    _log("submit", f"Failed — batch of {batch_n} remove(s) not accepted.")
                    if resp.message:
                        _log("submit", f"Message: {resp.message}")
                    if resp.error is not None:
                        _log("submit", f"Error: {resp.error!r}")
                call = None
            else:
                _log("price", f"Below limit - subnet={netuid}  current={current_price} TAO  limit={limit_price} TAO")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt as e:
        print(f"KeyboardInterrupt: {e}")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
