// SPDX-License-Identifier: MIT
pragma solidity ^0.8;
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "./interface/IETHRegistrarController.sol";
import "./interface/IPriceOracle.sol";
import "./SafeMath.sol";
import "hardhat/console.sol";

error InsufficientValue();

contract AtlantaPayments is Ownable {
    using SafeERC20 for IERC20;
    using SafeMath for uint256;

    IETHRegistrarController registrarController;
    uint256 private baseRegisterFee;
    struct PricingWithFee {
        uint256 payment;
        uint256 register;
        uint256 fee;
    }

    event NameRegistered(
        string name,
        address indexed owner,
        uint256 cost,
        uint256 duration,
        uint256 timestamp
    );

    event NameRenewed(
        string name,
        uint256 cost,
        uint256 duration,
        uint256 timestamp
    );

    constructor(IETHRegistrarController _registrarAddress) Ownable(msg.sender) {
        registrarController = _registrarAddress;

        baseRegisterFee = 5;
    }

    receive() external payable {}

    function rentPrice(
        string memory name,
        uint256 duration
    ) external view returns (IPriceOracle.Price memory price) {
        price = registrarController.rentPrice(name, duration);
    }

    function available(string memory name) external returns (bool) {
        return registrarController.available(name);
    }

    function makeCommitment(
        string memory name,
        address owner,
        uint256 duration,
        bytes32 secret,
        address resolver,
        bytes[] calldata data,
        bool reverseRecord,
        uint16 ownerControlledFuses
    ) external view returns (bytes32) {
        return
            registrarController.makeCommitment(
                name,
                owner,
                duration,
                secret,
                resolver,
                data,
                reverseRecord,
                ownerControlledFuses
            );
    }

    function getPrices(
        string calldata _name,
        uint256 _duration
    ) public view returns (uint256 registerValue, uint256 paymentValue) {
        IPriceOracle.Price memory priceOracle = registrarController.rentPrice(
            _name,
            _duration
        );
        registerValue = calculatePrice(priceOracle, 110); // 110% of the rent price
        paymentValue = calculatePrice(priceOracle, 115); // 115% of the rent price
    }

    function commit(bytes32 commitment) public {
        registrarController.commit(commitment);
    }

    function calculatePrice(
        IPriceOracle.Price memory _price,
        uint256 percent
    ) internal pure returns (uint256 value) {
        uint256 totalPrice = _price.base.add(_price.premium);
        return totalPrice.mul(percent).div(100);
    }

    function registerName(
        string calldata _name,
        address _owner,
        uint256 _duration,
        bytes32 _secret,
        address _resolver,
        bytes[] calldata _data,
        bool _reverseRecord,
        uint16 _ownerControlledFuses
    ) public payable {
        (uint256 registerValue, uint256 paymentValue) = getPrices(
            _name,
            _duration
        );
        require(
            msg.value >= paymentValue,
            "The value must be greater than the payment value"
        );
        require(
            address(this).balance >= registerValue,
            "The balance must be greater than the register value"
        );

        registrarController.register{value: registerValue}(
            _name,
            _owner,
            _duration,
            _secret,
            _resolver,
            _data,
            _reverseRecord,
            _ownerControlledFuses
        );
        
        if (msg.value > paymentValue) {
            payable(msg.sender).transfer(msg.value - paymentValue);
        }
        emit NameRegistered(
            _name,
            _owner,
            paymentValue,
            _duration,
            block.timestamp
        );
    }

    function renew(string calldata _name, uint256 _duration) public payable {
        (uint256 registerValue, uint256 paymentValue) = getPrices(
            _name,
            _duration
        );
        require(
            msg.value >= paymentValue,
            "The value must be greater han the payment value"
        );
        require(
            address(this).balance >= registerValue,
            "The balance must be greater than the register value"
        );

        registrarController.renew{value: registerValue}(_name, _duration);

        if (msg.value > paymentValue) {
            payable(msg.sender).transfer(msg.value - paymentValue);
        }

        emit NameRenewed(_name, paymentValue, _duration, block.timestamp);
    }

    function deposit() public payable {}

    function withdraw(address payable _to) public onlyOwner {
        uint256 amount = address(this).balance;

        (bool success, ) = _to.call{value: amount}("");
        require(success, "Failed to send ether");
    }
}
