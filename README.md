# miner-cli

**MVP / work in progress.** This repository is an early-stage project whose goal is to provide **utility tooling for Bittensor miners**—practical command-line and automation helpers for common on-chain workflows (staking, unstaking, monitoring, and related operations).

**Current implementation:** only **unstake** is shipped today (remove subnet / alpha stake). Additional miner workflows will be added over time.

## Upcoming features

- **`fast_auto_reg.py`** — fast automated miner registration on a subnet.
- **`stake.py`** — stake with a limit price; wait until the subnet price moves up before submitting (aligned with the limit-price flow in `unstake.py`).
- More miner utilities will be added here over time.

Interactive command-line tool for [Bittensor](https://github.com/opentensor/bittensor) that removes subnet (alpha) stake from selected hotkeys. It batches `remove_stake_full_limit` calls inside `Utility.force_batch`, optionally waits per block until a price condition is met, and submits via MEV-shielded (`mev_submit_encrypted`) extrinsics.

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
| `MAX_RETRY_COUNT` | Maximum number of times a batch is **built** before the tool stops (default: `10`). Each successful `mev_submit_encrypted` clears the batch so the next build counts again. If this cap is reached, the script logs an abort and exits the loop. |

## Usage

```bash
python unstake.py
```

The script will:

1. Connect with `AsyncSubtensor` and print chain name, endpoint, and runtime spec version (`[connect]` log).
2. Prompt for **wallet name** (empty uses `DEFAULT_WALLET_NAME` if set); a name is required.
3. Prompt for **subnet netuid** (integer **0–128**).
4. Unlock the coldkey and log a shortened coldkey plus balance (`[wallet]`).
5. Load all alpha positions for that coldkey (`[stake]`), print the subnet’s **current price** in TAO (`[price]`), then prompt for **limit price** in TAO: empty means “market” (no limit); otherwise submission waits until the subnet price is **strictly above** the limit.
6. For **each** position in the list: print netuid, hotkey (short and full), and alpha; if `netuid` matches the one you chose, ask **Remove stake for this position?** (`y` / default `N`). Other netuids are skipped with a `[skip]` log.
7. Enter a loop: build a single `Utility.force_batch` of `remove_stake_full_limit` calls. Positions are re-checked on-chain; each call is only included if remaining alpha is **greater than** **0.1** TAO-equivalent (`MIN_REMAINING_ALPHA_TAO`). If nothing qualifies, the tool exits that loop with a message.
8. Each iteration: wait for the next block (`[wait]`), re-read the subnet price; if there is no limit or `current_price > limit_price`, submit the batch with `mev_submit_encrypted` (`[submit]`). On success or failure, log outcome and any `message` / `error` from the response, then clear the batch so it can be rebuilt next time. If the price is still at or below the limit, log `[price]` and wait for the next block **without** incrementing the build counter.
9. If the number of batch **builds** reaches `MAX_RETRY_COUNT`, log `[abort]` and stop.

Logs use bracketed tags such as `connect`, `wallet`, `stake`, `price`, `position`, `skip`, `batch`, `wait`, `submit`, and `abort`.

**Keyboard interrupt** prints the interrupt and exits with status **0**. Other errors print `Error: …` and exit with status **1**.

## Behavior notes

- **Limit price**: With a limit set, the tool waits block-by-block until `current_price > limit_price` before submitting. This is intended to avoid removing stake when the subnet price is at or below your threshold. That wait is **not** bounded by `MAX_RETRY_COUNT` (only batch rebuilds are counted).
- **MEV shield**: Submissions use the library’s encrypted MEV path; success or failure is logged from the response.
- **Safety**: You explicitly confirm each hotkey to remove. The script does not remove 100% of alpha on a position; a small remainder is kept per the minimum threshold above.
## License

See the repository’s license if one is present; the project depends on Bittensor’s license terms for on-chain usage.
