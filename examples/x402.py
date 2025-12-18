"""
x402 Payment Verification Examples

Demonstrates two patterns for verifying payments via pypolkadot light client:
1. Proof-Based Verification (recommended for x402 HTTP flow)
2. Streaming Subscription (for monitoring/webhooks)

Usage:
    python examples/x402.py
"""

from pypolkadot import LightClient

# Example addresses (replace with real ones for testing)
# Treasury account on Asset Hub (has activity)
EXAMPLE_RECIPIENT = "0x6d6f646c70792f74727372790000000000000000000000000000000000000000"


def demo_proof_based_verification():
    """
    Pattern 1: Proof-Based Verification

    The buyer provides a block hash where the payment was included.
    Server verifies once - no streaming needed.

    This is the recommended pattern for x402 because:
    - No background listeners required
    - Server only works when requests come in
    - Scales better (verify on-demand)
    """
    print("=" * 60)
    print("Pattern 1: Proof-Based Verification")
    print("=" * 60)

    print("\nConnecting to Asset Hub via light client...")
    # testnet=False for mainnet (Asset Hub Polkadot)
    # testnet=True for testnet (Paseo Asset Hub)
    client = LightClient(testnet=False)

    # In real usage, buyer provides this in X-Payment header
    # For demo, we get the latest block
    block = client.get_finalized_block()
    print(f"Using block #{block.number}: {block.hash}")

    def verify_payment(block_hash: str, recipient: str, min_amount: int = 0) -> dict | None:
        """
        Verify a payment was included in a specific block.

        Returns the transfer event if found, None otherwise.
        """
        transfers = client.events(
            block_hash=block_hash,
            pallet="Balances",
            name="Transfer"
        )

        for t in transfers:
            to = t.fields.get("to")
            amount = t.fields.get("amount", 0)

            # Handle different field formats
            if isinstance(to, dict):
                to = to.get("Id") or to.get("value")

            if to == recipient and amount >= min_amount:
                return {
                    "from": t.fields.get("from"),
                    "to": to,
                    "amount": amount,
                    "event_index": t.index,
                }

        return None

    # Try to verify (may or may not find transfers in this block)
    print(f"\nLooking for transfers to {EXAMPLE_RECIPIENT[:20]}...")
    result = verify_payment(block.hash, EXAMPLE_RECIPIENT)

    if result:
        print("Payment verified!")
        print(f"  From: {result['from']}")
        print(f"  Amount: {result['amount']}")
    else:
        print("No matching transfer found in this block (this is normal)")
        print("In production, buyer would provide block hash where their tx was included")

    # Show all transfers in block for demo
    print(f"\nAll Balances.Transfer events in block {block.number}:")
    transfers = client.events(block_hash=block.hash, pallet="Balances", name="Transfer")
    if transfers:
        for t in transfers:
            from_addr = t.fields.get("from", "?")
            to_addr = t.fields.get("to", "?")
            if isinstance(from_addr, dict):
                from_addr = from_addr.get("Id", str(from_addr))
            if isinstance(to_addr, dict):
                to_addr = to_addr.get("Id", str(to_addr))
            print(f"  [{t.index}] {str(from_addr)[:20]}... -> {str(to_addr)[:20]}...")
    else:
        print("  (no transfers in this block)")

    return client  # Return for reuse


def demo_streaming_subscription(client: LightClient, max_blocks: int = 3):
    """
    Pattern 2: Streaming Subscription

    Server listens to all finalized blocks and watches for payments.

    Useful for:
    - Payment notifications/webhooks
    - Real-time dashboards
    - Backup reconciliation
    """
    print("\n" + "=" * 60)
    print("Pattern 2: Streaming Subscription")
    print("=" * 60)

    def watch_payments(recipient: str):
        """Watch for incoming payments to an address."""
        for block in client.subscribe_finalized():
            transfers = client.events(
                block_hash=block.hash,
                pallet="Balances",
                name="Transfer"
            )

            for t in transfers:
                to = t.fields.get("to")
                if isinstance(to, dict):
                    to = to.get("Id") or to.get("value")

                if to == recipient:
                    yield {
                        "block_number": block.number,
                        "block_hash": block.hash,
                        "from": t.fields.get("from"),
                        "amount": t.fields.get("amount"),
                    }

            # For demo, also yield block info even without transfers
            yield {"block_number": block.number, "transfers_to_recipient": 0}

    print(f"\nWatching for payments to {EXAMPLE_RECIPIENT[:20]}...")
    print(f"(Will monitor {max_blocks} blocks then stop)\n")

    blocks_seen = 0
    for event in watch_payments(EXAMPLE_RECIPIENT):
        if "amount" in event:
            # Actual payment received
            print(f"PAYMENT RECEIVED in block {event['block_number']}!")
            print(f"  From: {event['from']}")
            print(f"  Amount: {event['amount']}")
        else:
            # Just a block notification
            print(f"Block {event['block_number']} - no payments to watched address")
            blocks_seen += 1

        if blocks_seen >= max_blocks:
            print(f"\nStopping after {max_blocks} blocks (demo limit)")
            break


def demo_x402_flow():
    """
    Simulated x402 HTTP Flow

    Shows how the pieces fit together in a real x402 implementation.
    """
    print("\n" + "=" * 60)
    print("Simulated x402 HTTP Flow")
    print("=" * 60)

    print("""
    ┌─────────┐                    ┌─────────┐                    ┌─────────┐
    │  Buyer  │                    │ Server  │                    │  Chain  │
    └────┬────┘                    └────┬────┘                    └────┬────┘
         │                              │                              │
         │  1. GET /premium-content     │                              │
         │─────────────────────────────>│                              │
         │                              │                              │
         │  2. 402 Payment Required     │                              │
         │     {to: 0x..., amount: 100} │                              │
         │<─────────────────────────────│                              │
         │                              │                              │
         │  3. Sign & submit payment    │                              │
         │─────────────────────────────────────────────────────────────>
         │                              │                              │
         │  4. Wait for finalization    │                              │
         │     (get block hash)         │                              │
         │<─────────────────────────────────────────────────────────────
         │                              │                              │
         │  5. GET /premium-content     │                              │
         │     X-Payment: block=0xabc...│                              │
         │─────────────────────────────>│                              │
         │                              │  6. Verify payment           │
         │                              │     (light client query)     │
         │                              │─────────────────────────────>│
         │                              │                              │
         │                              │  7. Payment confirmed        │
         │                              │<─────────────────────────────│
         │                              │                              │
         │  8. 200 OK + content         │                              │
         │<─────────────────────────────│                              │
         │                              │                              │

    Key insight: Server only queries chain in step 6, when buyer provides proof.
    No constant listening required!
    """)


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("pypolkadot x402 Verification Examples")
    print("=" * 60)

    # Demo 1: Proof-based (recommended)
    client = demo_proof_based_verification()

    # Demo 2: Show the x402 flow diagram
    demo_x402_flow()

    # Demo 3: Streaming (optional, takes time)
    print("\nWould you like to demo streaming subscription? (watches ~3 blocks)")
    print("This takes about 36 seconds on Asset Hub (12s block time)")

    try:
        response = input("Run streaming demo? [y/N]: ").strip().lower()
        if response == "y":
            demo_streaming_subscription(client, max_blocks=3)
    except (EOFError, KeyboardInterrupt):
        print("\nSkipping streaming demo")

    print("\n" + "=" * 60)
    print("Done!")
