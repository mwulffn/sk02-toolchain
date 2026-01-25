"""Output writers for binary and Intel HEX formats."""

from pathlib import Path


class BinaryWriter:
    """Write raw binary output."""

    def __init__(self, start_address: int = 0x8000):
        self.start_address = start_address
        self.data: dict[int, int] = {}
        self.min_address = 0xFFFF
        self.max_address = 0

    def write_byte(self, address: int, value: int):
        """Write a single byte at the given address."""
        if address < 0 or address > 0xFFFF:
            raise ValueError(f"Address out of range: ${address:04X}")
        if value < 0 or value > 0xFF:
            raise ValueError(f"Byte value out of range: ${value:02X}")

        self.data[address] = value
        self.min_address = min(self.min_address, address)
        self.max_address = max(self.max_address, address)

    def write_bytes(self, address: int, values: list[int]):
        """Write multiple bytes starting at the given address."""
        for i, value in enumerate(values):
            self.write_byte(address + i, value)

    def save(self, filename: str | Path):
        """Save to binary file."""
        if not self.data:
            # Empty output
            with open(filename, "wb") as f:
                pass
            return

        # Create contiguous binary from min to max address
        output = bytearray()
        for addr in range(self.min_address, self.max_address + 1):
            output.append(self.data.get(addr, 0))

        with open(filename, "wb") as f:
            f.write(output)

    def get_listing(self) -> str:
        """Generate assembly listing."""
        if not self.data:
            return ""

        lines = []
        addr = self.min_address
        while addr <= self.max_address:
            # Format: address: bytes (up to 16 per line)
            line_bytes = []
            line_addr = addr
            for _ in range(16):
                if addr > self.max_address:
                    break
                line_bytes.append(self.data.get(addr, 0))
                addr += 1

            hex_bytes = " ".join(f"{b:02X}" for b in line_bytes)
            lines.append(f"{line_addr:04X}: {hex_bytes}")

        return "\n".join(lines)


class IntelHexWriter:
    """Write Intel HEX format output."""

    def __init__(self):
        self.data: dict[int, int] = {}

    def write_byte(self, address: int, value: int):
        """Write a single byte at the given address."""
        if address < 0 or address > 0xFFFF:
            raise ValueError(f"Address out of range: ${address:04X}")
        if value < 0 or value > 0xFF:
            raise ValueError(f"Byte value out of range: ${value:02X}")

        self.data[address] = value

    def write_bytes(self, address: int, values: list[int]):
        """Write multiple bytes starting at the given address."""
        for i, value in enumerate(values):
            self.write_byte(address + i, value)

    def _checksum(self, data: list[int]) -> int:
        """Calculate Intel HEX checksum."""
        return (-sum(data)) & 0xFF

    def save(self, filename: str | Path):
        """Save to Intel HEX file."""
        lines = []

        if not self.data:
            # Empty file - just EOF record
            lines.append(":00000001FF")
        else:
            # Sort addresses
            addresses = sorted(self.data.keys())

            # Group into 16-byte records
            i = 0
            while i < len(addresses):
                record_addr = addresses[i]
                record_data = []

                # Collect up to 16 contiguous bytes
                while i < len(addresses) and len(record_data) < 16:
                    addr = addresses[i]
                    # Check for contiguous addresses
                    if record_data and addr != record_addr + len(record_data):
                        break
                    record_data.append(self.data[addr])
                    i += 1

                # Create data record
                byte_count = len(record_data)
                addr_high = (record_addr >> 8) & 0xFF
                addr_low = record_addr & 0xFF
                record_type = 0x00  # Data record

                record = [byte_count, addr_high, addr_low, record_type] + record_data
                checksum = self._checksum(record)
                record.append(checksum)

                line = ":" + "".join(f"{b:02X}" for b in record)
                lines.append(line)

            # EOF record
            lines.append(":00000001FF")

        with open(filename, "w") as f:
            f.write("\n".join(lines) + "\n")
