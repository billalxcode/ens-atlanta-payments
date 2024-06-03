import { buildModule } from "@nomicfoundation/hardhat-ignition/modules"

const AtlantaPayments = buildModule("AtlantaPayments", (m) => {
    const contract = m.contract("AtlantaPayments", [
      "0x7BF3cF1176C4a037d3Ea2a5FF3d480359aC65Ecd",
    ])

    return { contract }
})

export default AtlantaPayments