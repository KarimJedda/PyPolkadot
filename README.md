# pypolkadot

Experimental Python light client for Polkadot/Substrate via [smoldot](https://github.com/smol-dot/smoldot).

Connect to Polkadot blockchains **trustlessly** - no full node, no RPC provider needed.

This is a feasibility demonstrator to integrate the functionality in https://github.com/JAMdotTech/py-polkadot-sdk. 

## Installation

```bash
pip install pypolkadot
```

## Quick Start

```python
from pypolkadot import LightClient

# Connect to Polkadot mainnet (embedded light client)
client = LightClient()

# Query storage
total = client.storage("Balances", "TotalIssuance")
print(f"Total issuance: {total}")

# Get events
for event in client.events(pallet="System"):
    print(f"{event.pallet}.{event.name}")

# Subscribe to blocks
for block in client.subscribe_finalized():
    print(f"Block #{block.number}: {block.hash}")
```

## Features

- Verifies proofs cryptographically, no RPC trust required
- Light client runs in-process, no external dependencies
- Query any storage/events without codegen
- Simple Python API, no async/await required

## API

| Method | Description |
|--------|-------------|
| `LightClient()` | Connect to Polkadot mainnet |
| `LightClient(testnet=True)` | Connect to Polkadot mainnet |
| `LightClient.from_chain_spec(json)` | Connect with custom chain spec |
| `client.storage(pallet, entry, keys)` | Query storage |
| `client.events(block_hash, pallet, name)` | Get/filter events |
| `client.submit(signed_hex)` | Submit pre-signed extrinsic |
| `client.subscribe_finalized()` | Stream finalized blocks |

## Development

```bash
# Setup
uv venv && source .venv/bin/activate
pip install maturin

# Build
maturin develop

# Test
python tests/test_storage.py
```

## License

GPL-3.0 as intended.
