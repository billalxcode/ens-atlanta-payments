import { HardhatUserConfig } from "hardhat/config"
import "@nomicfoundation/hardhat-toolbox"

const config: HardhatUserConfig = {
  solidity: {
    settings: {
      viaIR: true,
      optimizer: {
        enabled: true,
        runs: 200,
      },
    },
    compilers: [
      {
        version: "0.8.24",
      },
      {
        version: "0.4.11",
      },
    ],
  },

  defaultNetwork: "local",
  networks: {
    sepolia: {
      url: "https://sepolia.infura.io/v3/c47fcf77394e40e78eac21970ed5feeb",
      accounts: [
        "0x8f5c4eacb3ee8bf077b047a96f0f268cb5217a884e32d5242bbe234eefad4202",
      ],
    },
    local: {
      url: "http://localhost:8545",
    },
  },
  etherscan: {
    apiKey: "F6F6K7349I5GZ91KHJCUJH32GM5QFVXZI9",
  },
}

export default config
