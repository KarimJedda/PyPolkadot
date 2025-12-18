"""
Test events queries on Polkadot via light client.

Usage:
    python -m pytest tests/test_events.py -v -s

Note: These tests connect to Polkadot mainnet via smoldot light client.
Initial sync may take ~10-30 seconds.
"""

from pypolkadot import LightClient, Event


def test_events_latest_block():
    """Test getting all events for the latest block."""
    print("\nConnecting to Polkadot...")
    client = LightClient()

    print("Fetching events for latest block...")
    events = client.events()

    print(f"Found {len(events)} events:")
    for event in events[:10]:  # Show first 10
        print(f"  [{event.index}] {event.pallet}.{event.name}")

    assert len(events) > 0
    assert all(isinstance(e, Event) for e in events)


def test_events_filter_by_pallet():
    """Test filtering events by pallet name."""
    print("\nConnecting to Polkadot...")
    client = LightClient()

    print("Fetching System events...")
    system_events = client.events(pallet="System")

    print(f"Found {len(system_events)} System events:")
    for event in system_events:
        print(f"  [{event.index}] {event.pallet}.{event.name}")
        assert event.pallet == "System"


def test_events_filter_by_pallet_and_name():
    """Test filtering events by pallet and event name."""
    print("\nConnecting to Polkadot...")
    client = LightClient()

    print("Fetching System.ExtrinsicSuccess events...")
    success_events = client.events(pallet="System", name="ExtrinsicSuccess")

    print(f"Found {len(success_events)} ExtrinsicSuccess events:")
    for event in success_events[:5]:
        print(f"  [{event.index}] {event.pallet}.{event.name}: {event.fields}")
        assert event.pallet == "System"
        assert event.name == "ExtrinsicSuccess"


def test_events_for_specific_block():
    """Test getting events for a specific block hash."""
    print("\nConnecting to Polkadot...")
    client = LightClient()

    # First get the latest block hash
    block = client.get_finalized_block()
    print(f"Got block #{block.number}: {block.hash}")

    # Now get events for that specific block
    events = client.events(block_hash=block.hash)

    print(f"Found {len(events)} events in block {block.number}:")
    for event in events[:10]:
        print(f"  [{event.index}] {event.pallet}.{event.name}")

    assert len(events) > 0


def test_events_fields_structure():
    """Test that event fields are properly decoded."""
    print("\nConnecting to Polkadot...")
    client = LightClient()

    print("Fetching events...")
    events = client.events()

    # Find an ExtrinsicSuccess event which should have dispatch_info
    for event in events:
        if event.name == "ExtrinsicSuccess":
            print(f"\nExtrinsicSuccess event fields: {event.fields}")
            assert isinstance(event.fields, (dict, list))
            break


def test_balances_transfer_events():
    """Test looking for Balances.Transfer events (may or may not exist in current block)."""
    print("\nConnecting to Polkadot...")
    client = LightClient()

    print("Looking for Balances.Transfer events...")
    transfers = client.events(pallet="Balances", name="Transfer")

    if transfers:
        print(f"Found {len(transfers)} transfer(s):")
        for t in transfers:
            print(f"  Transfer: {t.fields}")
            # For smol402, you'd check: t.fields['to'] == expected_recipient
    else:
        print("No transfers in this block (this is normal)")


if __name__ == "__main__":
    print("=" * 60)
    print("pysubxt Events Test")
    print("=" * 60)

    test_events_latest_block()
    print("\n" + "=" * 60)

    test_events_filter_by_pallet()
    print("\n" + "=" * 60)

    test_events_filter_by_pallet_and_name()
    print("\n" + "=" * 60)

    test_events_for_specific_block()
    print("\n" + "=" * 60)

    test_balances_transfer_events()
    print("\n" + "=" * 60)

    print("All tests passed!")
