"""Opcode execution for SK-02 simulator."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .cpu import CPU

# Import opcode definitions from assembler
import sys
from pathlib import Path

# Add src to path to import opcodes
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from sk02_asm.opcodes import OPCODES, OperandType  # noqa: E402


def execute_instruction(cpu: "CPU") -> None:
    """Execute single instruction at current PC."""
    opcode_byte = cpu.fetch_byte()

    # Build reverse mapping for quick lookup
    opcode_map = {v.value: k for k, v in OPCODES.items()}

    if opcode_byte not in opcode_map:
        raise ValueError(f"Unknown opcode: ${opcode_byte:02X} at ${cpu.PC - 1:04X}")

    mnemonic = opcode_map[opcode_byte]
    execute_opcode(cpu, mnemonic, opcode_byte)


def execute_opcode(cpu: "CPU", mnemonic: str, opcode_byte: int) -> None:
    """Execute specific opcode by mnemonic."""
    # Data movement - register transfers
    if mnemonic == "A>B":
        cpu.B = cpu.A
    elif mnemonic == "A>C":
        cpu.C = cpu.A
    elif mnemonic == "A>D":
        cpu.D = cpu.A
    elif mnemonic == "A>E":
        cpu.E = cpu.A
    elif mnemonic == "A>F":
        cpu.F = cpu.A
    elif mnemonic == "A>G":
        cpu.G = cpu.A
    elif mnemonic == "A>H":
        cpu.H = cpu.A
    elif mnemonic == "B>A":
        cpu.A = cpu.B
    elif mnemonic == "B>C":
        cpu.C = cpu.B
    elif mnemonic == "B>D":
        cpu.D = cpu.B
    elif mnemonic == "B>E":
        cpu.E = cpu.B
    elif mnemonic == "B>F":
        cpu.F = cpu.B
    elif mnemonic == "B>G":
        cpu.G = cpu.B
    elif mnemonic == "B>H":
        cpu.H = cpu.B
    elif mnemonic == "C>A":
        cpu.A = cpu.C
    elif mnemonic == "C>B":
        cpu.B = cpu.C
    elif mnemonic == "C>D":
        cpu.D = cpu.C
    elif mnemonic == "C>E":
        cpu.E = cpu.C
    elif mnemonic == "C>F":
        cpu.F = cpu.C
    elif mnemonic == "C>G":
        cpu.G = cpu.C
    elif mnemonic == "C>H":
        cpu.H = cpu.C
    elif mnemonic == "D>A":
        cpu.A = cpu.D
    elif mnemonic == "D>B":
        cpu.B = cpu.D
    elif mnemonic == "D>C":
        cpu.C = cpu.D
    elif mnemonic == "D>E":
        cpu.E = cpu.D
    elif mnemonic == "D>F":
        cpu.F = cpu.D
    elif mnemonic == "D>G":
        cpu.G = cpu.D
    elif mnemonic == "D>H":
        cpu.H = cpu.D
    elif mnemonic == "E>A":
        cpu.A = cpu.E
    elif mnemonic == "E>B":
        cpu.B = cpu.E
    elif mnemonic == "E>C":
        cpu.C = cpu.E
    elif mnemonic == "E>D":
        cpu.D = cpu.E
    elif mnemonic == "E>F":
        cpu.F = cpu.E
    elif mnemonic == "E>G":
        cpu.G = cpu.E
    elif mnemonic == "E>H":
        cpu.H = cpu.E
    elif mnemonic == "F>A":
        cpu.A = cpu.F
    elif mnemonic == "F>B":
        cpu.B = cpu.F
    elif mnemonic == "F>C":
        cpu.C = cpu.F
    elif mnemonic == "F>D":
        cpu.D = cpu.F
    elif mnemonic == "F>E":
        cpu.E = cpu.F
    elif mnemonic == "F>G":
        cpu.G = cpu.F
    elif mnemonic == "F>H":
        cpu.H = cpu.F
    elif mnemonic == "G>A":
        cpu.A = cpu.G
    elif mnemonic == "G>B":
        cpu.B = cpu.G
    elif mnemonic == "G>C":
        cpu.C = cpu.G
    elif mnemonic == "G>D":
        cpu.D = cpu.G
    elif mnemonic == "G>E":
        cpu.E = cpu.G
    elif mnemonic == "G>F":
        cpu.F = cpu.G
    elif mnemonic == "G>H":
        cpu.H = cpu.G
    elif mnemonic == "H>A":
        cpu.A = cpu.H
    elif mnemonic == "H>B":
        cpu.B = cpu.H
    elif mnemonic == "H>C":
        cpu.C = cpu.H
    elif mnemonic == "H>D":
        cpu.D = cpu.H
    elif mnemonic == "H>E":
        cpu.E = cpu.H
    elif mnemonic == "H>F":
        cpu.F = cpu.H
    elif mnemonic == "H>G":
        cpu.G = cpu.H

    # 16-bit register pair transfers
    elif mnemonic == "AB>CD":
        cpu.CD = cpu.AB
    elif mnemonic == "AB>EF":
        cpu.EF = cpu.AB
    elif mnemonic == "AB>GH":
        cpu.GH = cpu.AB
    elif mnemonic == "CD>AB":
        cpu.AB = cpu.CD
    elif mnemonic == "CD>EF":
        cpu.EF = cpu.CD
    elif mnemonic == "CD>GH":
        cpu.GH = cpu.CD
    elif mnemonic == "EF>AB":
        cpu.AB = cpu.EF
    elif mnemonic == "EF>CD":
        cpu.CD = cpu.EF
    elif mnemonic == "EF>GH":
        cpu.GH = cpu.EF
    elif mnemonic == "GH>AB":
        cpu.AB = cpu.GH
    elif mnemonic == "GH>CD":
        cpu.CD = cpu.GH
    elif mnemonic == "GH>EF":
        cpu.EF = cpu.GH

    # Immediate loads
    elif mnemonic == "0>A":
        cpu.A = 0
    elif mnemonic == "0>B":
        cpu.B = 0
    elif mnemonic == "1>A":
        cpu.A = 1
    elif mnemonic == "1>B":
        cpu.B = 1
    elif mnemonic == "FF>A":
        cpu.A = 0xFF
    elif mnemonic == "FF>B":
        cpu.B = 0xFF
    elif mnemonic == "0>AB":
        cpu.AB = 0
    elif mnemonic == "1>AB":
        cpu.AB = 1
    elif mnemonic == "FFFF>AB":
        cpu.AB = 0xFFFF
    elif mnemonic == "SET_A":
        cpu.A = cpu.fetch_byte()
    elif mnemonic == "SET_B":
        cpu.B = cpu.fetch_byte()
    elif mnemonic == "SET_AB":
        cpu.AB = cpu.fetch_word()
    elif mnemonic == "SET_CD":
        cpu.CD = cpu.fetch_word()
    elif mnemonic == "SET_EF":
        cpu.EF = cpu.fetch_word()
    elif mnemonic == "SET_GH":
        cpu.GH = cpu.fetch_word()

    # Memory operations - absolute addressing
    elif mnemonic == "LOAD_A":
        addr = cpu.fetch_word()
        cpu.A = cpu.memory.read_byte(addr)
    elif mnemonic == "LOAD_B":
        addr = cpu.fetch_word()
        cpu.B = cpu.memory.read_byte(addr)
    elif mnemonic == "STORE_A":
        addr = cpu.fetch_word()
        cpu.memory.write_byte(addr, cpu.A)
    elif mnemonic == "STORE_B":
        addr = cpu.fetch_word()
        cpu.memory.write_byte(addr, cpu.B)

    # Memory operations - indexed by CD
    elif mnemonic == "LOAD_A_CD":
        cpu.A = cpu.memory.read_byte(cpu.CD)
    elif mnemonic == "LOAD_B_CD":
        cpu.B = cpu.memory.read_byte(cpu.CD)
    elif mnemonic == "STORE_A_CD":
        cpu.memory.write_byte(cpu.CD, cpu.A)
    elif mnemonic == "STORE_B_CD":
        cpu.memory.write_byte(cpu.CD, cpu.B)

    # Memory operations - indexed by EF
    elif mnemonic == "LOAD_A_EF":
        cpu.A = cpu.memory.read_byte(cpu.EF)
    elif mnemonic == "LOAD_B_EF":
        cpu.B = cpu.memory.read_byte(cpu.EF)
    elif mnemonic == "STORE_A_EF":
        cpu.memory.write_byte(cpu.EF, cpu.A)
    elif mnemonic == "STORE_B_EF":
        cpu.memory.write_byte(cpu.EF, cpu.B)

    # Memory operations - indexed by GH
    elif mnemonic == "LOAD_A_GH":
        cpu.A = cpu.memory.read_byte(cpu.GH)
    elif mnemonic == "LOAD_B_GH":
        cpu.B = cpu.memory.read_byte(cpu.GH)
    elif mnemonic == "STORE_A_GH":
        cpu.memory.write_byte(cpu.GH, cpu.A)
    elif mnemonic == "STORE_B_GH":
        cpu.memory.write_byte(cpu.GH, cpu.B)

    # 16-bit memory operations
    elif mnemonic == "LO_AB_CD":
        cpu.AB = cpu.memory.read_word(cpu.CD)
    elif mnemonic == "ST_AB_CD":
        cpu.memory.write_word(cpu.CD, cpu.AB)

    # Memory operations with auto-increment
    elif mnemonic == "LO_A_CD++":
        cpu.A = cpu.memory.read_byte(cpu.CD)
        cpu.CD = (cpu.CD + 1) & 0xFFFF
    elif mnemonic == "LO_B_CD++":
        cpu.B = cpu.memory.read_byte(cpu.CD)
        cpu.CD = (cpu.CD + 1) & 0xFFFF
    elif mnemonic == "ST_A_CD++":
        cpu.memory.write_byte(cpu.CD, cpu.A)
        cpu.CD = (cpu.CD + 1) & 0xFFFF
    elif mnemonic == "ST_B_CD++":
        cpu.memory.write_byte(cpu.CD, cpu.B)
        cpu.CD = (cpu.CD + 1) & 0xFFFF
    elif mnemonic == "LO_A_EF++":
        cpu.A = cpu.memory.read_byte(cpu.EF)
        cpu.EF = (cpu.EF + 1) & 0xFFFF
    elif mnemonic == "LO_B_EF++":
        cpu.B = cpu.memory.read_byte(cpu.EF)
        cpu.EF = (cpu.EF + 1) & 0xFFFF
    elif mnemonic == "ST_A_EF++":
        cpu.memory.write_byte(cpu.EF, cpu.A)
        cpu.EF = (cpu.EF + 1) & 0xFFFF
    elif mnemonic == "ST_B_EF++":
        cpu.memory.write_byte(cpu.EF, cpu.B)
        cpu.EF = (cpu.EF + 1) & 0xFFFF
    elif mnemonic == "LO_A_GH++":
        cpu.A = cpu.memory.read_byte(cpu.GH)
        cpu.GH = (cpu.GH + 1) & 0xFFFF
    elif mnemonic == "LO_B_GH++":
        cpu.B = cpu.memory.read_byte(cpu.GH)
        cpu.GH = (cpu.GH + 1) & 0xFFFF
    elif mnemonic == "ST_A_GH++":
        cpu.memory.write_byte(cpu.GH, cpu.A)
        cpu.GH = (cpu.GH + 1) & 0xFFFF
    elif mnemonic == "ST_B_GH++":
        cpu.memory.write_byte(cpu.GH, cpu.B)
        cpu.GH = (cpu.GH + 1) & 0xFFFF

    # Arithmetic - 8-bit
    elif mnemonic == "A++":
        cpu.A = (cpu.A + 1) & 0xFF
        cpu.update_zero_flag(cpu.A)
    elif mnemonic == "A--":
        cpu.A = (cpu.A - 1) & 0xFF
        cpu.update_zero_flag(cpu.A)
    elif mnemonic == "B++":
        cpu.B = (cpu.B + 1) & 0xFF
        cpu.update_zero_flag(cpu.B)
    elif mnemonic == "B--":
        cpu.B = (cpu.B - 1) & 0xFF
        cpu.update_zero_flag(cpu.B)
    elif mnemonic == "ADD":
        result = cpu.A + cpu.B
        cpu.overflow = result > 0xFF
        cpu.A = result & 0xFF
        cpu.update_zero_flag(cpu.A)
    elif mnemonic == "SUB":
        result = cpu.A - cpu.B
        cpu.overflow = result < 0
        cpu.A = result & 0xFF
        cpu.update_zero_flag(cpu.A)
    elif mnemonic == "ADD_c":
        result = cpu.A + cpu.C
        cpu.overflow = result > 0xFF
        cpu.A = result & 0xFF
        cpu.update_zero_flag(cpu.A)
    elif mnemonic == "SUB_c":
        result = cpu.A - cpu.C
        cpu.overflow = result < 0
        cpu.A = result & 0xFF
        cpu.update_zero_flag(cpu.A)

    # Arithmetic - 16-bit
    elif mnemonic == "AB++":
        cpu.AB = (cpu.AB + 1) & 0xFFFF
        cpu.update_zero_flag_16(cpu.AB)
    elif mnemonic == "AB--":
        cpu.AB = (cpu.AB - 1) & 0xFFFF
        cpu.update_zero_flag_16(cpu.AB)
    elif mnemonic == "CD++":
        cpu.CD = (cpu.CD + 1) & 0xFFFF
        cpu.update_zero_flag_16(cpu.CD)
    elif mnemonic == "CD--":
        cpu.CD = (cpu.CD - 1) & 0xFFFF
        cpu.update_zero_flag_16(cpu.CD)
    elif mnemonic == "EF++":
        cpu.EF = (cpu.EF + 1) & 0xFFFF
        cpu.update_zero_flag_16(cpu.EF)
    elif mnemonic == "EF--":
        cpu.EF = (cpu.EF - 1) & 0xFFFF
        cpu.update_zero_flag_16(cpu.EF)
    elif mnemonic == "GH++":
        cpu.GH = (cpu.GH + 1) & 0xFFFF
        cpu.update_zero_flag_16(cpu.GH)
    elif mnemonic == "GH--":
        cpu.GH = (cpu.GH - 1) & 0xFFFF
        cpu.update_zero_flag_16(cpu.GH)
    elif mnemonic == "AB+CD":
        result = cpu.AB + cpu.CD
        cpu.overflow = result > 0xFFFF
        cpu.AB = result & 0xFFFF
        cpu.update_zero_flag_16(cpu.AB)
    elif mnemonic == "AB-CD":
        result = cpu.AB - cpu.CD
        cpu.overflow = result < 0
        cpu.AB = result & 0xFFFF
        cpu.update_zero_flag_16(cpu.AB)

    # Logic operations
    elif mnemonic == "NOT":
        cpu.A = (~cpu.A) & 0xFF
        cpu.update_zero_flag(cpu.A)
    elif mnemonic == "AND":
        cpu.A = (cpu.A & cpu.B) & 0xFF
        cpu.update_zero_flag(cpu.A)
    elif mnemonic == "NAND":
        cpu.A = (~(cpu.A & cpu.B)) & 0xFF
        cpu.update_zero_flag(cpu.A)
    elif mnemonic == "OR":
        cpu.A = (cpu.A | cpu.B) & 0xFF
        cpu.update_zero_flag(cpu.A)
    elif mnemonic == "NOR":
        cpu.A = (~(cpu.A | cpu.B)) & 0xFF
        cpu.update_zero_flag(cpu.A)
    elif mnemonic == "XOR":
        cpu.A = (cpu.A ^ cpu.B) & 0xFF
        cpu.update_zero_flag(cpu.A)
    elif mnemonic == "NXOR":
        cpu.A = (~(cpu.A ^ cpu.B)) & 0xFF
        cpu.update_zero_flag(cpu.A)

    # Shifts - 8-bit logical
    elif mnemonic == "A>>":
        cpu.A = (cpu.A >> 1) & 0xFF
        cpu.update_zero_flag(cpu.A)
    elif mnemonic == "A<<":
        cpu.A = (cpu.A << 1) & 0xFF
        cpu.update_zero_flag(cpu.A)
    elif mnemonic == "B>>":
        cpu.B = (cpu.B >> 1) & 0xFF
        cpu.update_zero_flag(cpu.B)
    elif mnemonic == "B<<":
        cpu.B = (cpu.B << 1) & 0xFF
        cpu.update_zero_flag(cpu.B)

    # Shifts - 8-bit arithmetic (sign-extending)
    elif mnemonic == "S_A>>":
        sign = cpu.A & 0x80
        cpu.A = ((cpu.A >> 1) | sign) & 0xFF
        cpu.update_zero_flag(cpu.A)
    elif mnemonic == "S_B>>":
        sign = cpu.B & 0x80
        cpu.B = ((cpu.B >> 1) | sign) & 0xFF
        cpu.update_zero_flag(cpu.B)

    # Shifts - 16-bit
    elif mnemonic == "AB>>":
        cpu.AB = (cpu.AB >> 1) & 0xFFFF
        cpu.update_zero_flag_16(cpu.AB)
    elif mnemonic == "AB<<":
        cpu.AB = (cpu.AB << 1) & 0xFFFF
        cpu.update_zero_flag_16(cpu.AB)
    elif mnemonic == "S_AB>>":
        sign = cpu.AB & 0x8000
        cpu.AB = ((cpu.AB >> 1) | sign) & 0xFFFF
        cpu.update_zero_flag_16(cpu.AB)
    elif mnemonic == "CD>>":
        cpu.CD = (cpu.CD >> 1) & 0xFFFF
        cpu.update_zero_flag_16(cpu.CD)
    elif mnemonic == "CD<<":
        cpu.CD = (cpu.CD << 1) & 0xFFFF
        cpu.update_zero_flag_16(cpu.CD)
    elif mnemonic == "EF>>":
        cpu.EF = (cpu.EF >> 1) & 0xFFFF
        cpu.update_zero_flag_16(cpu.EF)
    elif mnemonic == "EF<<":
        cpu.EF = (cpu.EF << 1) & 0xFFFF
        cpu.update_zero_flag_16(cpu.EF)
    elif mnemonic == "GH>>":
        cpu.GH = (cpu.GH >> 1) & 0xFFFF
        cpu.update_zero_flag_16(cpu.GH)
    elif mnemonic == "GH<<":
        cpu.GH = (cpu.GH << 1) & 0xFFFF
        cpu.update_zero_flag_16(cpu.GH)

    # Comparison
    elif mnemonic == "CMP":
        result = cpu.A - cpu.B
        cpu.zero = (result & 0xFF) == 0
        cpu.overflow = result < 0
    elif mnemonic == "CMP_c":
        result = cpu.A - cpu.C
        cpu.zero = (result & 0xFF) == 0
        cpu.overflow = result < 0
    elif mnemonic == "CMP_16":
        result = cpu.AB - cpu.CD
        cpu.zero = (result & 0xFFFF) == 0
        cpu.overflow = result < 0
    elif mnemonic == "A_ZERO":
        cpu.zero = cpu.A == 0
    elif mnemonic == "AB_ZERO":
        cpu.zero = cpu.AB == 0

    # Stack operations
    elif mnemonic == "PUSH_A":
        cpu.push_data(cpu.A)
    elif mnemonic == "PUSH_B":
        cpu.push_data(cpu.B)
    elif mnemonic == "PUSH_C":
        cpu.push_data(cpu.C)
    elif mnemonic == "PUSH_D":
        cpu.push_data(cpu.D)
    elif mnemonic == "PUSH_E":
        cpu.push_data(cpu.E)
    elif mnemonic == "PUSH_F":
        cpu.push_data(cpu.F)
    elif mnemonic == "PUSH_G":
        cpu.push_data(cpu.G)
    elif mnemonic == "PUSH_H":
        cpu.push_data(cpu.H)
    elif mnemonic == "POP_A":
        cpu.A = cpu.pop_data()
    elif mnemonic == "POP_B":
        cpu.B = cpu.pop_data()
    elif mnemonic == "POP_C":
        cpu.C = cpu.pop_data()
    elif mnemonic == "POP_D":
        cpu.D = cpu.pop_data()
    elif mnemonic == "POP_E":
        cpu.E = cpu.pop_data()
    elif mnemonic == "POP_F":
        cpu.F = cpu.pop_data()
    elif mnemonic == "POP_G":
        cpu.G = cpu.pop_data()
    elif mnemonic == "POP_H":
        cpu.H = cpu.pop_data()

    # Control flow - unconditional
    elif mnemonic == "JMP":
        cpu.PC = cpu.fetch_word()
    elif mnemonic == "JMP_COMP":
        # Jump to address in AB
        cpu.PC = cpu.AB
    elif mnemonic == "GOSUB":
        addr = cpu.fetch_word()
        cpu.push_return(cpu.PC)
        cpu.PC = addr
    elif mnemonic == "GOSUB_COMP":
        # GOSUB to address in AB
        cpu.push_return(cpu.PC)
        cpu.PC = cpu.AB
    elif mnemonic == "RETURN":
        cpu.PC = cpu.pop_return()

    # Control flow - conditional
    elif mnemonic == "JMP_ZERO":
        addr = cpu.fetch_word()
        if cpu.zero:
            cpu.PC = addr
    elif mnemonic == "JMP_OVER":
        addr = cpu.fetch_word()
        if cpu.overflow:
            cpu.PC = addr
    elif mnemonic == "JMP_INTER":
        addr = cpu.fetch_word()
        if cpu.interrupt:
            cpu.PC = addr
    elif mnemonic == "JMP_A_POS":
        addr = cpu.fetch_word()
        if (cpu.A & 0x80) == 0:  # MSB not set = positive
            cpu.PC = addr
    elif mnemonic == "JMP_A_EVEN":
        addr = cpu.fetch_word()
        if (cpu.A & 0x01) == 0:  # LSB not set = even
            cpu.PC = addr
    elif mnemonic == "JMP_B_POS":
        addr = cpu.fetch_word()
        if (cpu.B & 0x80) == 0:
            cpu.PC = addr
    elif mnemonic == "JMP_B_EVEN":
        addr = cpu.fetch_word()
        if (cpu.B & 0x01) == 0:
            cpu.PC = addr

    # I/O operations
    elif mnemonic == "A>OUT_0":
        cpu.memory.out_0 = cpu.A
    elif mnemonic == "B>OUT_0":
        cpu.memory.out_0 = cpu.B
    elif mnemonic == "A>OUT_1":
        cpu.memory.out_1 = cpu.A
    elif mnemonic == "B>OUT_1":
        cpu.memory.out_1 = cpu.B
    elif mnemonic == "AB>OUT":
        # Output 16-bit value (split into two displays)
        cpu.memory.out_0 = cpu.A
        cpu.memory.out_1 = cpu.B
    elif mnemonic == "A>GPIO":
        cpu.memory.gpio = cpu.A
    elif mnemonic == "B>GPIO":
        cpu.memory.gpio = cpu.B
    elif mnemonic == "GPIO>A":
        cpu.A = cpu.memory.gpio
    elif mnemonic == "GPIO>B":
        cpu.B = cpu.memory.gpio
    elif mnemonic == "X>A":
        cpu.A = cpu.memory.x_input
    elif mnemonic == "X>B":
        cpu.B = cpu.memory.x_input
    elif mnemonic == "Y>A":
        cpu.A = cpu.memory.y_input
    elif mnemonic == "Y>B":
        cpu.B = cpu.memory.y_input

    # Interrupt handling
    elif mnemonic == "CLEAR_INTER":
        cpu.interrupt = False

    # System
    elif mnemonic == "NOP":
        pass  # No operation
    elif mnemonic == "HALT":
        cpu.halted = True

    # Unimplemented/hardware-specific opcodes
    elif mnemonic in [
        "TRG_HWI",
        "AB>IV",
        "IV>AB",
        "SET_IV",
        "HWI>A",
        "CLEAR_HWI",
        "RETURN_HWI",
        "HWI",
    ]:
        # Hardware interrupt opcodes - not implemented in simulator
        pass

    else:
        raise NotImplementedError(f"Opcode {mnemonic} not implemented")


def disassemble(cpu: "CPU", addr: int, count: int = 1) -> list[str]:
    """Disassemble instructions at given address."""
    lines = []
    opcode_map = {v.value: (k, v) for k, v in OPCODES.items()}

    current = addr
    for _ in range(count):
        if current >= 0x10000:
            break

        opcode_byte = cpu.memory.read_byte(current)
        if opcode_byte not in opcode_map:
            lines.append(f"${current:04X}: DB ${opcode_byte:02X}  ; Unknown opcode")
            current += 1
            continue

        mnemonic, opcode = opcode_map[opcode_byte]
        line = f"${current:04X}: {mnemonic:<12}"
        current += 1

        if opcode.operand == OperandType.IMM8:
            operand = cpu.memory.read_byte(current)
            line += f" ${operand:02X}"
            current += 1
        elif opcode.operand in (OperandType.IMM16, OperandType.ADDR16):
            low = cpu.memory.read_byte(current)
            high = cpu.memory.read_byte(current + 1)
            operand = low | (high << 8)
            line += f" ${operand:04X}"
            current += 2

        lines.append(line)

    return lines
