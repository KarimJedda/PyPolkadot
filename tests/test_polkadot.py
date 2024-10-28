import pytest
from decimal import Decimal
from substrateinterface import Keypair
from polkadot import Polkadot, Wallet
from polkadot.exceptions import PolkadotException

def test_polkadot_init():
    polka = Polkadot()
    assert polka.endpoint == "wss://polkadot-rpc-tn.dwellir.com"
    assert polka.timeout == 30
    assert polka.max_retries == 3
    assert not polka.testnet

    polka_testnet = Polkadot(testnet=True)
    assert polka_testnet.endpoint == "wss://westend-rpc.polkadot.io"
    assert polka_testnet.testnet

@pytest.fixture
def polkadot():
    return Polkadot()

@pytest.fixture
def polkadot_testnet():
    return Polkadot()

def test_connect(polkadot):
    polkadot.connect()
    assert polkadot.substrate is not None

def test_connect_testnet(polkadot_testnet):
    polkadot_testnet.connect()
    assert polkadot_testnet.substrate is not None
