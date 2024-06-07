from Crypto.Hash import keccak

def keccak256(data: str):
    k = keccak.new(digest_bits=256)
    k.update(data.encode())
    return k.hexdigest()

def revert_message(data):
    error_messages = {
        keccak256("CommitmentTooNew"): "Commitment Too New",
        keccak256("CommitmentTooOld"): "Commitment Too Old",
        keccak256("NameNotAvailable"): "Name not available",
        keccak256("ResolverRequiredWhenDataSupplied"): "ResolverRequiredWhenDataSupplied",
        keccak256("UnexpiredCommitmentExists"): "UnexpiredCommitmentExists",
        keccak256("InsufficientValue"): "InsufficientValue",
        keccak256("Unauthorised"): "Unauthorised",
        keccak256("MaxCommitmentAgeTooLow"): "MaxCommitmentAgeTooLow",
        keccak256("MaxCommitmentAgeTooHigh"): "MaxCommitmentAgeTooHigh"
    }
    # hashed_data = keccak256(data)
    return error_messages.get(data, "No error")


# Contoh penggunaan
print(revert_message(
    "cb7690d7fedc48d0f2b5be0b0205021dc276e2cf59db6e5a1d266aaf4ae94bcdc1cd063a"))
# print(revert_message("CommitmentTooNew"))  # Output: Commitment Too New
# print(revert_message("InsufficientValue"))  # Output: InsufficientValue
# print(revert_message("UnknownError"))  # Output: No error
