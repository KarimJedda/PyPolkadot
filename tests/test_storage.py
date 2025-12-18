"""
Test storage queries on Polkadot via light client.

Usage:
    python -m pytest tests/test_storage.py -v -s

Note: These tests connect to Polkadot mainnet via smoldot light client.
Initial sync may take ~10-30 seconds.
"""

from pypolkadot import LightClient


def test_storage_total_issuance():
    """Test querying a plain storage value (no keys)."""
    print("\nConnecting to Polkadot...")
    client = LightClient()

    print("Querying Balances.TotalIssuance...")
    total = client.storage("Balances", "TotalIssuance")

    print(f"Total issuance: {total}")
    assert total is not None
    # Total issuance should be a large number (in Plancks)
    assert isinstance(total, (int, dict))


def test_storage_account_info():
    """Test querying a map storage value with key."""
    print("\nConnecting to Polkadot...")
    client = LightClient()

    # TODO: Fill in a valid Polkadot account address (SS58 or hex)
    # Example: Polkadot Treasury account
    account_id = "0x6d6f646c70792f74727372790000000000000000000000000000000000000000"  # py/trsry (Treasury)

    print(f"Querying System.Account for {account_id[:20]}...")
    account_info = client.storage("System", "Account", [account_id])

    print(f"Account info: {account_info}")
    # Account info should be a dict with nonce, consumers, providers, data fields
    assert account_info is not None
    assert isinstance(account_info, dict)


def test_storage_nonexistent_account():
    """Test querying a nonexistent account returns appropriate result."""
    print("\nConnecting to Polkadot...")
    client = LightClient()

    # Random account that likely has no balance
    fake_account = "0x0000000000000000000000000000000000000000000000000000000000000001"

    print(f"Querying System.Account for nonexistent account...")
    account_info = client.storage("System", "Account", [fake_account])

    print(f"Account info: {account_info}")
    # May return default values or None depending on storage type


def test_storage_current_block():
    """Test querying System.Number for current block number."""
    print("\nConnecting to Polkadot...")
    client = LightClient()

    print("Querying System.Number...")
    block_number = client.storage("System", "Number")

    print(f"Current block number: {block_number}")
    assert block_number is not None


if __name__ == "__main__":
    # Run a quick test
    print("=" * 60)
    print("pysubxt Storage Query Test")
    print("=" * 60)

    test_storage_total_issuance()
    print("\n" + "=" * 60)

    test_storage_account_info()
    print("\n" + "=" * 60)

    test_storage_current_block()
    print("\n" + "=" * 60)
    print("All tests passed!")
