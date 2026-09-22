from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


BODY_LEN = 0x3C
SIGNATURE_LEN = 0x80
VIN_OFFSET = 0x1A
VIN_LEN = 7
APPID_OFFSET = 0x02
DEFAULT_APPID = 0x017C
ALL_APPIDS = (
    0x01A4,
    0x01AB,
    0x01AC,
    0x01AF,
    0x01C1,
    0x01DE,
    0x01E2,
    0x01E3,
    0x01E4,
    0x01E8,
    0x01EC,
    0x01EE,
    0x01EF,
    0x01F0,
    0x01F1,
    0x01F2,
    0x007B,
    0x017C,
    0x0095,
    0x0180,
    0x0188,
)

APPID_LABELS = {
    0x017C: "017C - Default",
    0x01A4: "01A4",
    0x01AB: "01AB",
    0x01AC: "01AC",
    0x01AF: "01AF",
    0x01C1: "01C1",
    0x01DE: "01DE",
    0x01E2: "01E2",
    0x01E3: "01E3",
    0x01E4: "01E4",
    0x01E8: "01E8",
    0x01EC: "01EC",
    0x01EE: "01EE",
    0x01EF: "01EF",
    0x01F0: "01F0",
    0x01F1: "01F1",
    0x01F2: "01F2",
    0x007B: "007B",
    0x0095: "0095",
    0x0180: "0180",
    0x0188: "0188",
}

E = 3

N_RAW_LE = bytes.fromhex(
    """
    03 F8 69 D6 55 B1 80 74 21 3D A6 2C AD C6 17 EC
    BB 84 C1 71 EC B8 13 97 3E 1F 34 D8 4B 9B 18 8E
    1F F2 59 AF 0F 80 EC 3B BD 43 DF B1 90 E2 6F AC
    38 97 59 3C E1 57 10 67 54 A4 29 1B D0 3B C9 7D
    11 A6 9D D7 38 97 CE 1D D3 54 5E A6 2A 2A F5 1A
    AB DA DD 75 0A AB 69 57 CE 41 B0 E5 07 69 F3 F3
    9C 84 36 3F 57 4C EA 92 78 C2 35 64 5B 07 72 80
    79 10 53 6D 5C F9 8C F7 1F 3B EF 8C D4 90 70 F5
    """
)
N = int.from_bytes(N_RAW_LE, "little")

TEMPLATE_BODY = bytes.fromhex(
    """
    01 01 01 7C 00 01 20 20 37 37 33 34 38 37 01 20
    30 30 30 30 30 30 30 1D 61 01 39 4A 32 39 34 33
    36 01 00 00 00 00 00 00 00 00 00 04 02 32 30
    32 36 30 31 30 31 31 30 30 30 5A 00
    """
)

KNOWN_SUFFIX_ONLY_SIGNATURE = bytes.fromhex(
    """
    16 DC 66 62 4B 4D 8C 57 94 0C 5F 9D 13 70 5F 08
    BE A5 C5 19 88 AA D3 3C 3C CF 6C CF D0 07 0C A1
    33 26 D3 1A D0 C2 6A 0E 44 0D C1
    """
)

BUILTIN_TEMPLATE = (
    TEMPLATE_BODY
    + b"\x00"
    + b"\x00" * (SIGNATURE_LEN - len(KNOWN_SUFFIX_ONLY_SIGNATURE))
    + KNOWN_SUFFIX_ONLY_SIGNATURE
)

MD5_DIGEST_INFO_PREFIX = bytes.fromhex(
    "30 20 30 0C 06 08 2A 86 48 86 F7 0D 02 05 05 00 04 10"
)


@dataclass(frozen=True)
class FscResult:
    data: bytes
    digest: bytes
    quotient: int
    rsa_result: bytes
    strict_valid: bool


def validate_vin(vin_text: str) -> bytes:
    vin = vin_text.strip().upper()
    if len(vin) != VIN_LEN:
        raise ValueError(f"VIN must be exactly {VIN_LEN} letters or digits.")
    if not vin.isalnum():
        raise ValueError("VIN must contain only letters and digits.")
    try:
        return vin.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValueError("VIN must contain ASCII letters and digits only.") from exc


def parse_appid(value: str) -> int:
    text = value.strip()
    if text.lower().startswith("0x"):
        text = text[2:]
    try:
        appid = int(text, 16)
    except ValueError as exc:
        raise ValueError("App ID must be hexadecimal, for example 017C.") from exc
    if not 0 <= appid <= 0xFFFF:
        raise ValueError("App ID must fit in 16 bits.")
    return appid


def floor_cuberoot(value: int) -> int:
    if value < 0:
        raise ValueError("cube root input must be non-negative")
    lo, hi = 0, 1 << ((value.bit_length() + 2) // 3)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if mid * mid * mid <= value:
            lo = mid
        else:
            hi = mid - 1
    return lo


def ceil_cuberoot(value: int) -> int:
    root = floor_cuberoot(value)
    return root if root * root * root == value else root + 1


def odd_cube_root_mod_2_128(value: int) -> int:
    modulus = 1 << 128
    value %= modulus
    if not value & 1:
        raise ValueError("value must be odd")
    inverse_of_three = pow(3, -1, 1 << 126)
    root = pow(value, inverse_of_three, modulus)
    if pow(root, 3, modulus) != value:
        raise AssertionError("internal modular cube-root failure")
    return root


def forge_suffix_only_signature(digest: bytes) -> tuple[bytes, int, bytes]:
    if len(digest) != 16:
        raise ValueError("MD5 digest must be 16 bytes")

    modulus_128 = 1 << 128
    digest_int = int.from_bytes(digest, "big")

    for quotient in range(256):
        target_low = (digest_int + quotient * N) % modulus_128
        if not target_low & 1:
            continue

        residue = odd_cube_root_mod_2_128(target_low)
        lower = ceil_cuberoot(quotient * N)
        upper = floor_cuberoot((quotient + 1) * N - 1)

        if residue > upper:
            continue
        lift = (upper - residue) // modulus_128
        candidate = residue + lift * modulus_128
        if candidate < lower or candidate >= N:
            continue

        recovered_int = pow(candidate, E, N)
        recovered = recovered_int.to_bytes(SIGNATURE_LEN, "big")
        if recovered[-16:] != digest:
            continue

        return candidate.to_bytes(SIGNATURE_LEN, "big"), quotient, recovered

    raise RuntimeError("could not construct a suffix-only signature")


def strict_pkcs1_v1_5_block(digest: bytes) -> bytes:
    digest_info = MD5_DIGEST_INFO_PREFIX + digest
    padding_len = SIGNATURE_LEN - len(digest_info) - 3
    if padding_len < 8:
        raise ValueError("RSA modulus is too short for DigestInfo")
    return b"\x00\x01" + b"\xff" * padding_len + b"\x00" + digest_info


def load_template(path: Path | None = None) -> bytearray:
    data = BUILTIN_TEMPLATE if path is None else path.read_bytes()
    expected = BODY_LEN + SIGNATURE_LEN
    if len(data) < expected:
        raise ValueError(f"template is {len(data)} bytes; need at least {expected} bytes")
    return bytearray(data[:BODY_LEN] + data[-SIGNATURE_LEN:])


def build_fsc(template: bytearray, vin: bytes, appid: int) -> FscResult:
    output = bytearray(template)
    output[APPID_OFFSET : APPID_OFFSET + 2] = appid.to_bytes(2, "big")
    output[VIN_OFFSET : VIN_OFFSET + VIN_LEN] = vin

    digest = hashlib.md5(output[:BODY_LEN]).digest()
    signature, quotient, recovered = forge_suffix_only_signature(digest)
    output[-SIGNATURE_LEN:] = signature

    stored_signature = int.from_bytes(output[-SIGNATURE_LEN:], "big")
    checked = pow(stored_signature, E, N).to_bytes(SIGNATURE_LEN, "big")
    weak_valid = checked[-16:] == hashlib.md5(output[:BODY_LEN]).digest()
    strict_valid = checked == strict_pkcs1_v1_5_block(digest)
    if not weak_valid or checked != recovered:
        raise AssertionError("generated FSC failed the vulnerable-verifier self-check")

    return FscResult(bytes(output), digest, quotient, checked, strict_valid)


def spaced_hex(data: bytes) -> str:
    return data.hex(" ").upper()


def hex_dump(data: bytes, width: int = 16) -> str:
    lines = []
    for offset in range(0, len(data), width):
        chunk = data[offset : offset + width]
        hex_part = " ".join(f"{byte:02X}" for byte in chunk)
        ascii_part = "".join(chr(byte) if 32 <= byte < 127 else "." for byte in chunk)
        lines.append(f"{offset:04X}  {hex_part:<{width * 3 - 1}}  {ascii_part}")
    return "\n".join(lines)
