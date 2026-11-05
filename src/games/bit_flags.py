"""Physical locations for MSB-first flags stored in 32-bit words."""


def msb_flag_location(base_address: int, index: int) -> tuple[int, int]:
    # Bounds and native index wrapping belong to callers: source proofs also
    # need physical locations beyond a bank's declared width to detect aliases.
    return base_address + index // 32 * 4, 0x80000000 >> (index % 32)
