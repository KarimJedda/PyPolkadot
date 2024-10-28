# PyPolkadot

Abstractions for the Polkadot ecosystem. 

This package is a very opinionated wrapper around `py-substrate-interface`. It provides a simple synchronous interface for interacting with the Polkadot ecosystem. The `PyPolkadot` package can automatically detect when the metadata is outdated and refresh it behind the scenes. This ensures that developers don’t have to manually handle metadata updates.

Note: Light client functionality is not yet supported. 

## Installation

`pip install PyPolkadot`

## Usage

### Basic usage

```python

from polkadot import *

# Initialize Polkadot instance
polka = Polkadot()  # Defaults to the mainnet relay chain

# Optionally, specify a custom RPC endpoint or use a testnet
polka = Polkadot(endpoint="wss://polkadot-rpc-tn.dwellir.com")

# Get account balance
balance = polka.get_balance("12pDATAH2rCakrYjo6UoYFtmTEUpSyePTum8U5x9QdySZuqn")
print(f"Balance: {balance} DOT")

```


```python
# Create a Polkadot instance (testnet, defaults to Polkadot Westend)
polka = Polkadot(testnet=True)

# Create a new wallet
wallet1 = Wallet.create(polka)
address = wallet1.default_address

# Request tokens from the faucet (only on testnet)
faucet_tx = wallet1.faucet()

# Get balance
balance = wallet1.get_balance()

# Send tokens
receiver_address = "5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty"
tx_receipt = wallet1.send(1, receiver_address)
```