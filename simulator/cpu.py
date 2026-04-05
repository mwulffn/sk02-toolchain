"""CPU core for SK-02 simulator."""

from .memory import Memory


class CPU:
    """SK-02 CPU with registers, flags, and execution logic."""

    def __init__(self, memory: Memory):
        """Initialize CPU with memory reference."""
        self.memory = memory

        # 8-bit registers
        self.A = 0
        self.B = 0
        self.C = 0
        self.D = 0
        self.E = 0
        self.F = 0
        self.G = 0
        self.H = 0

        # Program counter
        self.PC = 0x8000  # Start at ROM

        # Flags
        self.zero = False
        self.overflow = False
        self.interrupt = False

        # Stacks (256 entries each, 8-bit pointers)
        self.return_stack = [0] * 256
        self.return_sp = 0
        self.data_stack = [0] * 256
        self.data_sp = 0

        # Execution state
        self.halted = False
        self.instruction_count = 0

    @property
    def AB(self) -> int:
        """Get AB register pair as 16-bit value."""
        return self.A | (self.B << 8)

    @AB.setter
    def AB(self, value: int) -> None:
        """Set AB register pair from 16-bit value."""
        value &= 0xFFFF
        self.A = value & 0xFF
        self.B = (value >> 8) & 0xFF

    @property
    def CD(self) -> int:
        """Get CD register pair as 16-bit value."""
        return self.C | (self.D << 8)

    @CD.setter
    def CD(self, value: int) -> None:
        """Set CD register pair from 16-bit value."""
        value &= 0xFFFF
        self.C = value & 0xFF
        self.D = (value >> 8) & 0xFF

    @property
    def EF(self) -> int:
        """Get EF register pair as 16-bit value."""
        return self.E | (self.F << 8)

    @EF.setter
    def EF(self, value: int) -> None:
        """Set EF register pair from 16-bit value."""
        value &= 0xFFFF
        self.E = value & 0xFF
        self.F = (value >> 8) & 0xFF

    @property
    def GH(self) -> int:
        """Get GH register pair as 16-bit value."""
        return self.G | (self.H << 8)

    @GH.setter
    def GH(self, value: int) -> None:
        """Set GH register pair from 16-bit value."""
        value &= 0xFFFF
        self.G = value & 0xFF
        self.H = (value >> 8) & 0xFF

    def reset(self) -> None:
        """Reset CPU to initial state."""
        self.A = self.B = self.C = self.D = 0
        self.E = self.F = self.G = self.H = 0
        self.PC = 0x8000
        self.zero = False
        self.overflow = False
        self.interrupt = False
        self.return_sp = 0
        self.data_sp = 0
        self.halted = False
        self.instruction_count = 0

    def fetch_byte(self) -> int:
        """Fetch next byte from PC and increment."""
        value = self.memory.read_byte(self.PC)
        self.PC = (self.PC + 1) & 0xFFFF
        return value

    def fetch_word(self) -> int:
        """Fetch next word (little-endian) from PC and increment."""
        low = self.fetch_byte()
        high = self.fetch_byte()
        return low | (high << 8)

    def push_return(self, value: int) -> None:
        """Push 16-bit value onto return stack."""
        value &= 0xFFFF
        self.return_stack[self.return_sp] = value & 0xFF
        self.return_sp = (self.return_sp + 1) & 0xFF
        self.return_stack[self.return_sp] = (value >> 8) & 0xFF
        self.return_sp = (self.return_sp + 1) & 0xFF

    def pop_return(self) -> int:
        """Pop 16-bit value from return stack."""
        self.return_sp = (self.return_sp - 1) & 0xFF
        high = self.return_stack[self.return_sp]
        self.return_sp = (self.return_sp - 1) & 0xFF
        low = self.return_stack[self.return_sp]
        return low | (high << 8)

    def push_data(self, value: int) -> None:
        """Push 8-bit value onto data stack."""
        self.data_stack[self.data_sp] = value & 0xFF
        self.data_sp = (self.data_sp + 1) & 0xFF

    def pop_data(self) -> int:
        """Pop 8-bit value from data stack."""
        self.data_sp = (self.data_sp - 1) & 0xFF
        return self.data_stack[self.data_sp]

    def update_zero_flag(self, value: int) -> None:
        """Update zero flag based on value."""
        self.zero = (value & 0xFF) == 0

    def update_zero_flag_16(self, value: int) -> None:
        """Update zero flag based on 16-bit value."""
        self.zero = (value & 0xFFFF) == 0

    def step(self) -> bool:
        """Execute one instruction. Returns True if execution should continue."""
        if self.halted:
            return False

        # Import here to avoid circular dependency
        from .opcodes import execute_instruction

        execute_instruction(self)
        self.instruction_count += 1
        return not self.halted

    def run(self, max_instructions: int = 1000000) -> None:
        """Run until HALT or max instructions reached."""
        for _ in range(max_instructions):
            if not self.step():
                break

    def get_register_display(self) -> str:
        """Get formatted register display string."""
        lines = []
        lines.append(
            f"PC: ${self.PC:04X}  RSP: {self.return_sp:02X}  "
            f"DSP: {self.data_sp:02X}  Flags: Z={int(self.zero)} "
            f"O={int(self.overflow)} I={int(self.interrupt)}"
        )
        lines.append(
            f"A=${self.A:02X} B=${self.B:02X} C=${self.C:02X} D=${self.D:02X} "
            f"E=${self.E:02X} F=${self.F:02X} G=${self.G:02X} H=${self.H:02X}"
        )
        lines.append(
            f"AB=${self.AB:04X} CD=${self.CD:04X} EF=${self.EF:04X} GH=${self.GH:04X}"
        )
        return "\n".join(lines)
