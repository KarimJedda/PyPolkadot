from decimal import Decimal
from substrateinterface import SubstrateInterface, Keypair
from .exceptions import PolkadotException
import time


class Polkadot:
    def __init__(self, endpoint="wss://polkadot-rpc-tn.dwellir.com", timeout=30, max_retries=3, testnet=False):
        self.testnet = testnet
        self.endpoint = "wss://westend-rpc.polkadot.io" if testnet else endpoint
        self.timeout = timeout
        self.max_retries = max_retries
        self.substrate = None

    def connect(self):
        for attempt in range(self.max_retries):
            try:
                if self.testnet:
                    self.substrate = SubstrateInterface(url=self.endpoint, ss58_format=0)
                else:
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

    def create_wallet(self, mnemonic=None):
        self.ensure_connected()
        try:
            if mnemonic:
                keypair = Keypair.create_from_mnemonic(mnemonic)
            else:
                keypair = Keypair.create_from_uri(Keypair.generate_mnemonic())
            return Wallet(self, keypair)
        except Exception as e:
            raise PolkadotException(f"Failed to create wallet: {str(e)}")

    def send_tokens(self, sender_wallet, amount, receiver):
        self.ensure_connected()
        try:
            call = self.substrate.compose_call(
                call_module='Balances',
                call_function='transfer',
                call_params={
                    'dest': receiver,
                    'value': int(amount * 10**10)  # Convert DOT to planck
                }
            )
            extrinsic = self.substrate.create_signed_extrinsic(call=call, keypair=sender_wallet.keypair)
            receipt = self.substrate.submit_extrinsic(extrinsic, wait_for_inclusion=True)
            return receipt
        except Exception as e:
            raise PolkadotException(f"Failed to send tokens: {str(e)}")

    def subscribe_events(self):
        self.ensure_connected()
        try:
            for event in self.substrate.subscribe_events():
                yield event
        except Exception as e:
            raise PolkadotException(f"Failed to subscribe to events: {str(e)}")
        

class Wallet:
    def __init__(self, polkadot, keypair):
        self.polkadot = polkadot
        self.keypair = keypair
        self.default_address = keypair.ss58_address

    def get_balance(self):
        return self.polkadot.get_balance(self.default_address)

    def send(self, amount, receiver):
        return self.polkadot.send_tokens(self, amount, receiver)

    def faucet(self):
        if not self.polkadot.testnet:
            raise PolkadotException("Faucet is only available on testnet")
        try:
            raise NotImplementedError("Faucet functionality is not implemented yet")
            response = requests.post(
                "https://faucet.westend.network/",
                json={"address": self.default_address, "amount": 1}
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise PolkadotException(f"Failed to request from faucet: {str(e)}")

    @classmethod
    def create(cls, polkadot, mnemonic=None):
        return polkadot.create_wallet(mnemonic)