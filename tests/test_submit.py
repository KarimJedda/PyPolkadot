"""
Test extrinsic submission API.

Note: Actually submitting requires a valid signed extrinsic.
These tests verify the API is exposed and handles errors correctly.

Usage:
    python tests/test_submit.py
    # or with pytest:
    python -m pytest tests/test_submit.py -v -s
"""

from pypolkadot import LightClient

try:
    import pytest
    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False


def test_submit_method_exists():
    """Verify the submit method is available."""
    print("\nConnecting to Polkadot...")
    client = LightClient()

    # Check method exists
    assert hasattr(client, "submit")
    assert callable(client.submit)
    print("submit() method is available")


def test_submit_invalid_hex():
    """Test that invalid hex is rejected."""
    print("\nConnecting to Polkadot...")
    client = LightClient()

    # Try to submit invalid hex
    try:
        client.submit("not-valid-hex")
        assert False, "Should have raised an error"
    except RuntimeError as e:
        assert "Invalid hex" in str(e)
        print(f"Invalid hex correctly rejected: {e}")


def test_submit_invalid_extrinsic():
    """Test that invalid extrinsic bytes are rejected by the chain."""
    print("\nConnecting to Polkadot...")
    client = LightClient()

    # Valid hex but not a valid extrinsic (just random bytes)
    fake_extrinsic = "0x" + "00" * 32

    # This should fail when the chain tries to decode it
    try:
        client.submit(fake_extrinsic)
        assert False, "Should have raised an error"
    except RuntimeError as e:
        print(f"Invalid extrinsic correctly rejected: {e}")


def test_submit_usage_example():
    """
    Document the intended usage pattern.

    In real usage, you would:
    1. Build the extrinsic payload
    2. Sign it with an external library (py-sr25519-bindings, substrateinterface)
    3. Submit via pysubxt light client
    """
    print("\n" + "=" * 60)
    print("Submit Extrinsic Usage Pattern")
    print("=" * 60)

    example_code = '''
    # 1. Build extrinsic (using substrateinterface or similar)
    from substrateinterface import SubstrateInterface, Keypair

    # Connect to get metadata (or use cached)
    substrate = SubstrateInterface(url="wss://rpc.polkadot.io")

    # Create and sign extrinsic
    keypair = Keypair.create_from_uri("//Alice")
    call = substrate.compose_call(
        call_module="Balances",
        call_function="transfer_keep_alive",
        call_params={"dest": "5G...", "value": 1000000000}
    )
    extrinsic = substrate.create_signed_extrinsic(call=call, keypair=keypair)

    # 2. Get the encoded bytes
    signed_hex = extrinsic.data.hex()

    # 3. Submit via pysubxt light client (trustless!)
    from pypolkadot import LightClient
    client = LightClient()
    tx_hash = client.submit(signed_hex)
    print(f"Submitted: {tx_hash}")

    # 4. Verify inclusion
    # Wait a bit for finalization, then check events
    import time
    time.sleep(12)  # ~2 blocks
    events = client.events(pallet="System", name="ExtrinsicSuccess")
    '''

    print(example_code)
    print("=" * 60)


if __name__ == "__main__":
    test_submit_method_exists()
    test_submit_usage_example()
    print("\nNote: Full submission test requires a valid signed extrinsic")
    print("The API is ready - signing happens externally!")
