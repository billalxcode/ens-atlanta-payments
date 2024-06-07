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

class CampaignReferenceTooLargeError(Exception):
    def __init__(self, campaign):
        self.campaign = campaign
        self.message = f"Campaign reference {campaign} is too large"
        super().__init__(self.message)


def pad(data, size):
    return data.ljust(size, b"\0")


def to_bytes(data):
    if isinstance(data, int):
        return struct.pack(">I", data)
    elif isinstance(data, str):
        return data.encode()
    elif isinstance(data, bytes):
        return data
    else:
        raise ValueError("Unsupported data type for to_bytes")


def to_hex(data):
    return data.hex()


def namehash(name):
    # Assuming namehash is a simplified version for this conversion
    return hashlib.sha256(name.encode()).digest()


def random_secret(platform_domain=None, campaign=None):
    bytes_array = bytearray(os.urandom(32))

    if platform_domain:
        hash_bytes = namehash(platform_domain)
        for i in range(4):
            bytes_array[i] = hash_bytes[i]

    if campaign is not None:
        if campaign > 0xFFFFFFFF:
            raise CampaignReferenceTooLargeError(campaign)
        campaign_bytes = pad(to_bytes(campaign), 4)
        for i in range(4):
            bytes_array[i + 4] = campaign_bytes[i]

    return "0x" + to_hex(bytes_array)


def calculate_price(price, percent: int) -> int:
    total_price = price['base'] + price['premium']
    return total_price * percent // 100


def decode_error_message(error_data):
    # Decoding error data
    if error_data[:10] == '0x08c379a0':  # Standard Error(string) signature
        error_message = provider.codec.decode_abi(
            ['string'], bytes.fromhex(error_data[10:]))
        return error_message[0]
    elif error_data[:10] == '0x4e487b71':  # Panic(uint256) signature
        error_code = provider.codec.decode_abi(
            ['uint256'], bytes.fromhex(error_data[10:]))
        return f"Panic error with code {error_code[0]}"
    else:
        return "Unknown error"
    
def get_prices(price_oracle) -> Tuple[int, int, int]:
    register_value = calculate_price(
        price_oracle, 110)  # 110% of the rent price
    payment_value = calculate_price(
        price_oracle, 115)  # 115% of the rent price
    payment_fee_value = payment_value - register_value
    return register_value, payment_value, payment_fee_value


class Payments:
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
            address="0x2135b360D32B17fAEE573BDE47C75e5e34bdC875", abi=payment["abi"]
        )

    def load_artifacts(self):
        payment_artifact_file = open(
            "ignition/deployments/chain-31337/artifacts/AtlantaPayments#AtlantaPayments.json"
        ).read()
        payment_artifact_json = json.loads(payment_artifact_file)
        return payment_artifact_json

    def print_acccounts(self):
        tables = Table(title="Payment Accounts")
        tables.add_column("#", justify="center")
        tables.add_column("Address")
        tables.add_column("Balance")

        for i, acc in enumerate(self.accounts):
            balance = provider.eth.get_balance(acc)
            tables.add_row(
                str(i + 1), str(acc), str(provider.from_wei(balance, "ether"))
            )
        console.print(tables)

    def show_payment_contract_balance(self):
        balance = provider.eth.get_balance(self.payment_contract.address)
        console.log("Contract Balance: " +
                    str(provider.from_wei(balance, "ether")))

    def rent_price(self, name, duration):
        (basePrice, premiumPrice) = self.payment_contract.functions.rentPrice(
            name, duration
        ).call()
        console.log(
            f"Price: base {provider.from_wei(basePrice, 'ether')} | premium {provider.from_wei(premiumPrice, 'ether')}"
        )
        return {'base': basePrice, 'premium': premiumPrice}

    def get_prices(self, name, duration):
        (register, payment )= self.payment_contract.functions.getPrices(
            name, duration).call()

        return {'register': register, 'payment': payment, 'fee': payment - register}

    def makeCommitment(self, name, duration, secret):
        commitment = self.payment_contract.functions.makeCommitment(
            name, self.buyer1, duration, secret, self.resolver, [], False, 0
        ).call()
        console.log(f"Commitment hash: {commitment.hex()}")
        return "0x" + commitment.hex()

    def commit(self, name, duration, secret):
        commitment = self.makeCommitment(name, duration, secret)
        transaction = self.payment_contract.functions.commit(commitment).build_transaction(
            {
                "chainId": provider.eth.chain_id,
                "nonce": provider.eth.get_transaction_count(self.buyer1),
                "gas": self.default_gas,
            }
        )
        signedTransaction = provider.eth.account.sign_transaction(
            transaction, self.private_keys[self.buyer1])
        tx_hash = provider.eth.send_raw_transaction(
            signedTransaction.rawTransaction)
        provider.eth.wait_for_transaction_receipt(tx_hash)
        console.log(f"Commit hash: {tx_hash.hex()}")
        return tx_hash.hex()

    def registerName(self, name, duration, secret):
        prices = self.get_prices(name, duration)
        register_value = prices['register']
        payment_value = prices['payment']
        payment_fee_value = prices['fee']
        console.log(f"Payment {provider.from_wei(payment_value, 'ether')}")
        console.log(f"Register {provider.from_wei(register_value, 'ether')}")
        console.log(f"Fee {provider.from_wei(payment_fee_value, 'ether')}")

        try:
            transaction = self.payment_contract.functions.registerName(
                name, self.buyer1, duration, secret, self.resolver, [], False, 0
            ).build_transaction(
                {
                    "chainId": provider.eth.chain_id,
                    "value": payment_value,
                    "nonce": provider.eth.get_transaction_count(self.buyer1),
                    "gas": self.default_gas,
                }
            )
            signedTransaction = provider.eth.account.sign_transaction(
                transaction, self.private_keys[self.buyer1])
            tx_hash = provider.eth.send_raw_transaction(
                signedTransaction.rawTransaction)
            provider.eth.wait_for_transaction_receipt(tx_hash)
            console.log(f"Register hash: {tx_hash.hex()}")
            return tx_hash.hex()
        except Exception as e:
            print(e)

    def contract_deposit(self):
        console.log("Check contract balance")
        balance = provider.eth.get_balance(self.payment_contract.address)
        if (provider.from_wei(balance, 'ether') < 10):
            balance = provider.eth.get_balance(self.owner)
            console.log(f"Owner balance {provider.from_wei(balance, 'ether')}" )
            value = provider.to_wei(10, "ether")
            console.log(
                f"Sending ether to contract from {self.owner} to {self.payment_contract.address} value {value}")
            transaction = self.payment_contract.functions.deposit().build_transaction(
                {
                    "chainId": provider.eth.chain_id,
                    "value": value,
                    "nonce": provider.eth.get_transaction_count(self.owner),
                    "gas": self.default_gas,
                }
            )
            signedTransaction = provider.eth.account.sign_transaction(transaction, self.private_keys[self.owner])
            tx_hash = provider.eth.send_raw_transaction(signedTransaction.rawTransaction)
            provider.eth.wait_for_transaction_receipt(tx_hash)
            console.log(f"Deposit hash {tx_hash.hex()}")
            
            balance = provider.eth.get_balance(self.payment_contract.address)
            console.log(
                f"Current balance: {provider.from_wei(balance, 'ether')}")

    def withdraw(self):
        console.log("Withdraw balance")
        transaction = self.payment_contract.functions.withdraw().build_transaction({
            "chainId": provider.eth.chain_id,
            "nonce": provider.eth.get_transaction_count(self.owner),
            "gas": self.default_gas
        })
    def contract_owner(self):
        owner = self.payment_contract.functions.owner().call()
        console.log(f"Owner address: {owner}")

    def countdown(self):
        with console.status("Please wait 60s") as status:
            for t in range(80, 0, -1):
                status.update(f"Please wait {t}s")
                time.sleep(1)


    def available(self, name):
        result = self.payment_contract.functions.available(name).call()
        console.log(f"Available? {result}")

    def main(self):
        name = "testatlanta"
        duration = 2628000
        self.available(name)
        self.print_acccounts()
        self.show_payment_contract_balance()
        self.contract_deposit()
        self.contract_owner()
        prices = self.get_prices(name, duration)

        console.log(f"Register value: {prices['register']}")
        console.log(f"Payment value: {prices['payment']}")
        console.log(f"Fee value: {prices['fee']}")

        secret = random_secret()
        console.log(f"Secret: {secret}")
        console.log(f"Buyer: {self.buyer1}")
        console.log(f"Duration: {duration}s")

        self.commit(name, duration, secret)
        self.countdown()
        self.registerName(name, duration, secret)


if __name__ == "__main__":
    payment = Payments()
    payment.main()
