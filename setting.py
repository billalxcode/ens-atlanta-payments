import json
import os
import hashlib
import struct
import time
from rich.console import Console
from rich.table import Table
from web3 import HTTPProvider
from web3 import Web3
from web3.contract.contract import Contract
from web3 import exceptions
from web3.middleware.geth_poa import geth_poa_middleware
from typing import Tuple

console = Console()
provider = Web3(HTTPProvider("http://localhost:8545"))
# provider.middleware_onion.inject(geth_poa_middleware, layer=0)


class Setting:
    def __init__(self) -> None:
        self.accounts = provider.eth.accounts
        # self.owner = "0xC549EcF0d9D72eAc5d806Ca25545A82A6BBe8BD1"
        # self.buyer1 = "0x3D1FBeEeE8F4dCa226605d26f752130FeF9a5f0b"
        self.owner = self.accounts[0]
        self.buyer1 = self.accounts[1]
        # self.buyer2 = self.accounts[2]
        self.private_keys = {
            self.owner: "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80",
            self.buyer1: "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d"
        }

        self.resolver = "0xaD7191fBCda3b37BeF9427C26bE0A00DEC540487"
        self.default_gas = 2000000

        payment = self.load_artifacts()
        self.payment_contract: Contract = provider.eth.contract(
            address="0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512", abi=payment["abi"]
        )

    def load_artifacts(self):
        payment_artifact_file = open(
            "ignition/deployments/chain-31337/artifacts/AtlantaPayments#AtlantaPayments.json"
        ).read()
        payment_artifact_json = json.loads(payment_artifact_file)
        return payment_artifact_json

    def set_base_register_value(self):
        baseRegisterFee = self.payment_contract.functions.baseRegisterFee().call()
        console.log(f"Base register fee: {baseRegisterFee}")
        console.log(f"Setting up new base register fee")
        transaction = self.payment_contract.functions.setBaseRegisterFee(10).build_transaction({
            "chainId": provider.eth.chain_id,
            "nonce": provider.eth.get_transaction_count(self.owner),
            "gas": self.default_gas
        })
        console.log(f"Sign transaction")
        signedTransaction = provider.eth.account.sign_transaction(
            transaction, self.private_keys[self.owner]
        )
        console.log("Sending transaction")
        tx_hash = provider.eth.send_raw_transaction(
            signedTransaction.rawTransaction)
        provider.eth.wait_for_transaction_receipt(tx_hash)
        console.log(f"Transaction Hash: {tx_hash.hex()}")
        newBaseRegisterFee = self.payment_contract.functions.baseRegisterFee().call()
        console.log(f"New bsase register fee: {newBaseRegisterFee}")
        if newBaseRegisterFee == 10 or newBaseRegisterFee == "10":
            console.log("Ok")
        else:
            console.log("Fail")
    
    def set_registrar_controller(self):
        registarController = self.payment_contract.functions.registrarController().call()
        console.log(f"Registar Controller: {registarController}")

if __name__ == "__main__":
    setting = Setting()
    setting.set_base_register_value()
    setting.set_registrar_controller()