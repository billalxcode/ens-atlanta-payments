import { buildModule } from "@nomicfoundation/hardhat-ignition/modules"

const AtlantaToken = buildModule("AtlantaToken", (m) => {
    const contract = m.contract("AtlantaToken")
    return { contract }
})

export default AtlantaToken