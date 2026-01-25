"""Memory subsystem for SK-02 simulator."""


class Memory:
    """64KB memory subsystem with RAM, ROM, and I/O mapping."""

    def __init__(self):
        """Initialize memory with 64KB address space."""
        self.data = bytearray(65536)  # 64KB address space

        # I/O registers
        self.gpio = 0
        self.out_0 = 0
        self.out_1 = 0
        self.x_input = 0
        self.y_input = 0

    def read_byte(self, addr: int) -> int:
        """Read a byte from memory."""
        addr &= 0xFFFF  # Wrap to 16-bit
        return self.data[addr]

    def write_byte(self, addr: int, value: int) -> None:
        """Write a byte to memory."""
        addr &= 0xFFFF  # Wrap to 16-bit
        value &= 0xFF  # Ensure 8-bit value

        # ROM area ($8000-$FFFF) is read-only after loading
        # Allow writes during initialization for loading binaries
        self.data[addr] = value

    def read_word(self, addr: int) -> int:
        """Read a 16-bit word (little-endian) from memory."""
        low = self.read_byte(addr)
        high = self.read_byte(addr + 1)
        return low | (high << 8)

    def write_word(self, addr: int, value: int) -> None:
        """Write a 16-bit word (little-endian) to memory."""
        value &= 0xFFFF  # Ensure 16-bit value
        self.write_byte(addr, value & 0xFF)
        self.write_byte(addr + 1, (value >> 8) & 0xFF)

    def load_binary(self, data: bytes, origin: int = 0x8000) -> None:
        """Load binary data into memory at specified origin."""
        for i, byte in enumerate(data):
            addr = (origin + i) & 0xFFFF
            self.data[addr] = byte

    def dump(self, addr: int, length: int = 16) -> str:
        """Return a hex dump of memory region."""
        lines = []
        for offset in range(0, length, 16):
            current_addr = (addr + offset) & 0xFFFF
            hex_bytes = []
            ascii_chars = []

            for i in range(16):
                if offset + i < length:
                    byte = self.read_byte(current_addr + i)
                    hex_bytes.append(f"{byte:02X}")
                    # Show printable ASCII or '.' for non-printable
                    ascii_chars.append(chr(byte) if 32 <= byte < 127 else ".")
                else:
                    hex_bytes.append("  ")
                    ascii_chars.append(" ")

            # Format: ADDR: XX XX XX XX ... | aaaa...
            hex_part = " ".join(hex_bytes)
            ascii_part = "".join(ascii_chars)
            lines.append(f"{current_addr:04X}: {hex_part} | {ascii_part}")

        return "\n".join(lines)
