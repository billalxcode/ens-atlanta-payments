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
from typing import Tuple

console = Console()
provider = Web3(HTTPProvider("http://localhost:8545"))


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
        self.owner = self.accounts[0]
        self.buyer1 = self.accounts[1]
        self.buyer2 = self.accounts[2]
        self.private_keys = {
            self.owner: "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
        }

        self.resolver = "0xa48a285BAb4061e9104EeA29f968b1B801423E32"
        self.default_gas = 2000000

        payment = self.load_artifacts()
        self.payment_contract: Contract = provider.eth.contract(
            address="0xaf981B8FB5429d1D64B16F98A2BDfc6cF667A08D", abi=payment["abi"]
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
        result = self.payment_contract.functions.makeCommitment(
            name, self.buyer1, duration, secret, self.resolver, [], False, 0
        ).transact(
            {
                "chainId": provider.eth.chain_id,
                "from": self.buyer1,
                "nonce": provider.eth.get_transaction_count(self.buyer1),
                "gas": self.default_gas,
            }
        )
        console.log(f"Commitment hash: {result.hex()}")
        return result.hex()

    def commit(self, name, duration, secret):
        commitment = self.makeCommitment(name, duration, secret)
        result = self.payment_contract.functions.commit(commitment).transact(
            {
                "chainId": provider.eth.chain_id,
                "from": self.buyer1,
                "nonce": provider.eth.get_transaction_count(self.buyer1),
                "gas": self.default_gas,
            }
        )
        console.log(f"Commit hash: {result.hex()}")
        return result.hex()

    def registerName(self, name, duration, secret):
        prices = self.get_prices(name, duration)
        register_value = prices['register']
        payment_value = prices['payment']
        payment_fee_value = prices['fee']
        console.log(f"Payment {provider.from_wei(payment_value, 'ether')}")
        console.log(f"Register {provider.from_wei(register_value, 'ether')}")
        console.log(f"Fee {provider.from_wei(payment_fee_value, 'ether')}")

        try:
            result = self.payment_contract.functions.registerName(
                name, self.buyer1, duration, secret, self.resolver, [], False, 0
            ).transact(
                {
                    "chainId": provider.eth.chain_id,
                    "from": self.buyer1,
                    "value": payment_value,
                    "nonce": provider.eth.get_transaction_count(self.buyer1),
                    "gas": self.default_gas,
                }
            )
            console.log(f"Register hash: {result.hex()}")
            return result.hex()
        except Exception as e:
            print(e)

    def contract_deposit(self):
        console.log("Check contract balance")
        balance = provider.eth.get_balance(self.payment_contract.address)
        if (provider.from_wei(balance, 'ether') < 10):
            value = provider.to_wei(10, "ether")
            console.log(
                f"Sending ether to contract from {self.owner} to {self.payment_contract.address} value {value}")
            result = self.payment_contract.functions.deposit().transact(
                {
                    "chainId": provider.eth.chain_id,
                    "from": self.buyer1,
                    "value": value,
                    "nonce": provider.eth.get_transaction_count(self.buyer1),
                    "gas": self.default_gas,
                }
            )
            console.log(f"Deposit hash {result.hex()}")
            balance = provider.eth.get_balance(self.payment_contract.address)
            console.log(
                f"Current balance: {provider.from_wei(balance, 'ether')}")

    def contract_owner(self):
        owner = self.payment_contract.functions.owner().call()
        console.log(f"Owner address: {owner}")

    def countdown(self):
        with console.status("Please wait 60s") as status:
            for t in range(60, 0, -1):
                status.update(f"Please wait {t}s")
                time.sleep(1)

    def main(self):
        name = "billal.test"
        duration = 60**2
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
