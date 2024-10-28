from decimal import Decimal
from substrateinterface import SubstrateInterface
from .exceptions import PolkadotException
import time


class Polkadot:
    def __init__(self, endpoint="wss://rpc.polkadot.io", timeout=30, max_retries=3):
        self.endpoint = endpoint
        self.timeout = timeout
        self.max_retries = max_retries
        self.substrate = None

    def connect(self):
        for attempt in range(self.max_retries):
            try:
                self.substrate = SubstrateInterface(url=self.endpoint, ss58_format=0, type_registry_preset="polkadot")
                return
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise PolkadotException(f"Failed to connect after {self.max_retries} attempts: {str(e)}")
                time.sleep(1)

    def ensure_connected(self):
        if self.substrate is None:
            self.connect()

    def close(self):
        if self.substrate:
            self.substrate.close()
            self.substrate = None

    def get_balance(self, address):
        self.ensure_connected()
        try:
            result = self.substrate.query("System", "Account", [address])
            balance = result["data"]["free"].value
            return Decimal(balance) / Decimal(10**10)  # Convert planck to DOT
        except Exception as e:
            raise PolkadotException(f"Failed to get balance: {str(e)}")

    def subscribe_events(self):
        self.ensure_connected()
        try:
            for event in self.substrate.subscribe_events():
                yield event
        except Exception as e:
            raise PolkadotException(f"Failed to subscribe to events: {str(e)}")