# PyPolkadot

Abstractions for the Polkadot ecosystem. 

This package is a very opinionated wrapper around `py-substrate-interface`. It provides a simple synchronous interface for interacting with the Polkadot ecosystem. The `PyPolkadot` package can automatically detect when the metadata is outdated and refresh it behind the scenes. This ensures that developers don’t have to manually handle metadata updates.

Note: Light client functionality is not yet supported. 

## Installation

`pip install PyPolkadot`

## Usage

### Basic usage

```python

from polkadot_gateway import Polkadot

# Initialize Polkadot instance
polka = Polkadot()  # Defaults to the mainnet relay chain

# Optionally, specify a custom RPC endpoint or use a testnet
polka = Polkadot(endpoint="wss://polkadot-rpc-tn.dwellir.com")

# Get account balance
balance = polka.get_balance("12pDATAH2rCakrYjo6UoYFtmTEUpSyePTum8U5x9QdySZuqn")
print(f"Balance: {balance} DOT")

```