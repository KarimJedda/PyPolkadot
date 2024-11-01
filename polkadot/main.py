from decimal import Decimal
from substrateinterface import SubstrateInterface, Keypair
from .exceptions import PolkadotException
import os 
import json
import time
import logging
import sys

TESTNET_RPCS = [
    "wss://westend-rpc.dwellir.com",
    "wss://westend-rpc-tn.dwellir.com",
    "wss://westend-rpc.polkadot.io",
]

MAINNET_RPCS = [
    "wss://rpc.polkadot.io",
    "wss://polkadot-rpc.dwellir.com",
    "wss://polkadot.api.onfinality.io/public-ws"
]

class Polkadot:
    def __init__(self, endpoint=None, timeout=30, max_retries=3, testnet=False):
        self.testnet = testnet
        self.endpoint = endpoint
        self.timeout = timeout
        self.max_retries = max_retries
        self.substrate = None

    def connect(self):
        if self.endpoint:
            self._try_connect([self.endpoint])
        else:
            rpcs = TESTNET_RPCS if self.testnet else MAINNET_RPCS
            self._try_connect(rpcs)

    def _try_connect(self, endpoints):
        for rpc in endpoints:
            for attempt in range(self.max_retries):
                try:
                    if self.testnet:
                        self.substrate = SubstrateInterface(url=rpc, ss58_format=42)
                    else:
                        self.substrate = SubstrateInterface(url=rpc, ss58_format=0, type_registry_preset="polkadot")
                    logging.info(f"Successfully connected to {rpc}")
                    return
                except Exception as e:
                    logging.warning(f"Failed to connect to {rpc}: {str(e)}")
                    if attempt == self.max_retries - 1:
                        logging.warning(f"Max retries reached for {rpc}")
                    time.sleep(1)
        
        logging.error("Unable to connect to any of the provided RPC endpoints")
        sys.exit(1)

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

    def send_tokens(self, sender_wallet, amount, receiver, asset_id=None):
        self.ensure_connected()
        
        try:
            if asset_id is None:
                call = self.substrate.compose_call(
                    call_module='Balances',
                    call_function='transfer_keep_alive',
                    call_params={
                        'dest': receiver,
                        'value': int(amount * 10**10)
                    }
                )
            else:
                call = self.substrate.compose_call(
                    call_module='Assets',
                    call_function='transfer',
                    call_params={
                        'id': asset_id,
                        'target': receiver,
                        'amount': int(amount * 10**10)
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
    def __init__(self, polkadot, keypair, store_keys=True):
        self.polkadot = polkadot
        self.keypair = keypair
        self.default_address = keypair.ss58_address
        self.store_keys = store_keys
        
        if self.store_keys:
            self._save_keys()

    def _save_keys(self):
        keys_file = 'keys.json'
        if not os.path.exists(keys_file):
            with open(keys_file, 'w') as f:
                json.dump({
                    'private_key': '0x' + self.keypair.private_key.hex(),
                    'public_key': '0x' +  self.keypair.public_key.hex()
                }, f)
            logging.info(f"Keys saved to {keys_file}")
        else:
            logging.info(f"{keys_file} already exists, not overwriting")

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
    def create(cls, polkadot, mnemonic=None, store_keys=True):
        keys_file = 'keys.json'
        
        if os.path.exists(keys_file) and store_keys:
            logging.info(f"Loading keys from {keys_file}")
            with open(keys_file, 'r') as f:
                keys = json.load(f)
            keypair = Keypair(private_key=keys['private_key'], ss58_format=42)
        else:
            if mnemonic:
                keypair = Keypair.create_from_mnemonic(mnemonic)
            else:
                keypair = Keypair.create_from_uri(Keypair.generate_mnemonic())
            logging.info("New keypair created")

        return cls(polkadot, keypair, store_keys)