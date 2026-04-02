# miner-cli

**MVP / work in progress.** This repository is an early-stage project whose goal is to provide **utility tooling for Bittensor miners**—practical command-line and automation helpers for common on-chain workflows (staking, unstaking, monitoring, and related operations).

**Current implementation:** only **unstake** is shipped today (remove subnet / alpha stake). Additional miner workflows will be added over time.

## Upcoming features

- **`fast_auto_reg.py`** — fast automated miner registration on a subnet.
- **`stake.py`** — stake with a limit price; wait until the subnet price moves up before submitting (aligned with the limit-price flow in `unstake.py`).
- More miner utilities will be added here over time.

Interactive command-line tool for [Bittensor](https://github.com/opentensor/bittensor) that removes subnet (alpha) stake from selected hotkeys. It batches `remove_stake_full_limit` calls, optionally waits per block until a price condition is met, and submits the batch via MEV-shielded (`mev_submit_encrypted`) extrinsics.

## Requirements

- Python 3.10+ (3.12 recommended)
- A Bittensor wallet configured locally (`btcli` / `~/.bittensor/wallets`)
- Network access to the chosen Bittensor endpoint

## Install

```bash
cd miner-cli
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Dependencies: `bittensor`, `python-dotenv`.

## Configuration

Optional environment variables (e.g. in a `.env` file in the project root; not committed):

| Variable | Description |
|----------|-------------|
| `DEFAULT_WALLET_NAME` | Wallet name used when you press Enter at the wallet prompt |
| `BT_NETWORK` | Bittensor network name (default: `finney`) |
| `MINER_CLI_MAX_BLOCK_WAITS` | If set to a positive integer, stop after that many block waits instead of looping forever when waiting on a limit price (default: `0` = no cap) |

## Usage

```bash
python unstake.py
```

The script will:

1. Connect and print chain name, endpoint, and runtime spec version.
2. Prompt for **wallet name** (empty uses `DEFAULT_WALLET_NAME` if set).
3. Prompt for **subnet netuid** (0–128).
4. Unlock the coldkey and list your alpha positions for that coldkey.
5. Prompt for **limit price** in TAO: empty means “market” (no limit); otherwise submission waits until the subnet price is **above** the limit (see below).
6. For each position on the chosen netuid, ask whether to **remove stake** (`y` / default `N`).
7. Build a single `Utility.force_batch` of `remove_stake_full_limit` calls. Each call only includes positions that still have more than **0.1** TAO-equivalent alpha remaining (hardcoded `MIN_REMAINING_ALPHA_TAO`).
8. Each new block: if there is no limit or current subnet price **>** limit, submit via `mev_submit_encrypted`; otherwise wait and retry.

**Keyboard interrupt** exits cleanly; other errors print a message and exit with status 1.

## Behavior notes

- **Limit price**: With a limit set, the tool waits block-by-block until `current_price > limit_price` before submitting. This is intended to avoid removing stake when the subnet price is at or below your threshold.
- **MEV shield**: Submissions use the library’s encrypted MEV path; success or failure is logged from the response.
- **Safety**: You explicitly confirm each hotkey to remove. The script does not remove 100% of alpha on a position; a small remainder is kept per the minimum threshold above.

## License

See the repository’s license if one is present; the project depends on Bittensor’s license terms for on-chain usage.
