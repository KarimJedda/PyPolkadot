"""Test pysubxt light client functionality."""

from pypolkadot import LightClient, Block


def test_import():
    """Test that imports work."""
    assert LightClient is not None
    assert Block is not None


def test_connect_polkadot():
    """Test connecting to Polkadot mainnet and getting blocks.

    Note: This test requires network access and may take time for initial sync.
    """
    print("Connecting to Polkadot...")
    client = LightClient()
    print("Connected!")

    # Get latest finalized block
    print("Getting latest finalized block...")
    block = client.get_finalized_block()
    print(f"Latest block: {block}")
    assert block.number > 0
    assert block.hash.startswith("0x")

    # Subscribe to a few blocks
    print("Subscribing to finalized blocks...")
    count = 0
    for block in client.subscribe_finalized():
        print(f"  Block #{block.number}: {block.hash}")
        count += 1
        if count >= 3:
            break

    print(f"Received {count} blocks. Test passed!")


if __name__ == "__main__":
    test_import()
    print("Import test passed!")

    test_connect_polkadot()
