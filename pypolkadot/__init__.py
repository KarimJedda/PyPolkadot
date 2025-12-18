"""
pypolkadot - Python light client for Polkadot/Substrate via smoldot.

Connect to Asset Hub trustlessly, without running a full node or relying on RPC providers.

Example:
    >>> from pypolkadot import LightClient
    >>> client = LightClient()              # Asset Hub Polkadot (mainnet)
    >>> client = LightClient(testnet=True)  # Paseo Asset Hub (testnet)
    >>> for block in client.subscribe_finalized():
    ...     print(f"Block #{block.number}: {block.hash}")
"""

from pypolkadot._pypolkadot import Block, BlockSubscription, Event, LightClient

__all__ = ["LightClient", "BlockSubscription", "Block", "Event"]
__version__ = "0.1.0"
