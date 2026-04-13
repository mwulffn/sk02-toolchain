"""Tests for the SK-02 assembler."""

import builtins
from pathlib import Path

import pytest

from sk02_asm.assembler import Assembler
from sk02_asm.errors import (
    AddressOutOfRangeError,
    AsmSyntaxError,
    AssemblyError,
    DuplicateSymbolError,
    InvalidOperandError,
    UndefinedSymbolError,
)
from sk02_asm.lexer import Lexer, TokenType
from sk02_asm.opcodes import OPCODES, OperandType
from sk02_asm.output import BinaryWriter, IntelHexWriter
from sk02_asm.preprocessor import Preprocessor, PreprocessorError
from sk02_asm.symbols import SymbolTable

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def asm(source: str, start_address: int = 0x8000, **kwargs) -> list[int]:
    """Assemble source and return bytes as a list. Raises on error."""
    assembler = Assembler(source, start_address, **kwargs)
    output, errors = assembler.assemble()
    assert errors == [], f"Assembly errors: {errors}"
    if not output.data:
        return []
    return [
        output.data.get(addr, 0)
        for addr in range(output.min_address, output.max_address + 1)
    ]


def asm_errors(source: str, **kwargs) -> list:
    """Assemble source and return error list."""
    assembler = Assembler(source, **kwargs)
    _, errors = assembler.assemble()
    return errors


# ===========================================================================
# Opcode encoding tests
# ===========================================================================


class TestImpliedOpcodes:
    """Test all implied (no-operand) opcodes assemble to their correct byte."""

    def test_all_implied_opcodes(self):
        """Every NONE-operand opcode should assemble to exactly its value byte."""
        for name, opcode in OPCODES.items():
            if opcode.operand != OperandType.NONE:
                continue
            result = asm(f"    .ORG $8000\n    {name}")
            assert result == [opcode.value], (
                f"{name}: expected [{opcode.value}], got {result}"
            )

    def test_nop(self):
        result = asm("    .ORG $8000\n    NOP")
        assert result == [0]

    def test_halt(self):
        result = asm("    .ORG $8000\n    HALT")
        assert result == [127]

    def test_digit_prefix_opcodes(self):
        """Opcodes starting with digits must be assembled correctly (lexer bug regression)."""
        cases = {
            "0>A": 1,
            "0>B": 2,
            "1>A": 3,
            "1>B": 4,
            "FF>A": 5,
            "FF>B": 6,
            "0>AB": 191,
            "1>AB": 192,
            "FFFF>AB": 193,
        }
        for mnemonic, expected_byte in cases.items():
            result = asm(f"    .ORG $8000\n    {mnemonic}")
            assert result == [expected_byte], (
                f"{mnemonic}: expected [{expected_byte}], got {result}"
            )

    def test_register_transfers_8bit(self):
        """Spot-check 8-bit register transfers."""
        assert asm("    .ORG $8000\n    A>B") == [42]
        assert asm("    .ORG $8000\n    B>A") == [51]
        assert asm("    .ORG $8000\n    C>A") == [60]
        assert asm("    .ORG $8000\n    H>G") == [101]

    def test_register_transfers_16bit(self):
        """Spot-check 16-bit register pair transfers."""
        assert asm("    .ORG $8000\n    AB>CD") == [177]
        assert asm("    .ORG $8000\n    AB>EF") == [178]
        assert asm("    .ORG $8000\n    CD>AB") == [180]
        assert asm("    .ORG $8000\n    GH>EF") == [188]

    def test_arithmetic(self):
        assert asm("    .ORG $8000\n    A++") == [11]
        assert asm("    .ORG $8000\n    A--") == [12]
        assert asm("    .ORG $8000\n    ADD") == [19]
        assert asm("    .ORG $8000\n    SUB") == [20]
        assert asm("    .ORG $8000\n    AB+CD") == [150]
        assert asm("    .ORG $8000\n    AB-CD") == [151]

    def test_logic(self):
        assert asm("    .ORG $8000\n    NOT") == [21]
        assert asm("    .ORG $8000\n    AND") == [22]
        assert asm("    .ORG $8000\n    OR") == [195]
        assert asm("    .ORG $8000\n    XOR") == [197]

    def test_stack_ops(self):
        assert asm("    .ORG $8000\n    PUSH_A") == [24]
        assert asm("    .ORG $8000\n    POP_A") == [26]
        assert asm("    .ORG $8000\n    PUSH_H") == [120]
        assert asm("    .ORG $8000\n    POP_H") == [121]

    def test_io_opcodes(self):
        assert asm("    .ORG $8000\n    A>OUT_0") == [49]
        assert asm("    .ORG $8000\n    A>OUT_1") == [50]
        assert asm("    .ORG $8000\n    AB>OUT") == [149]
        assert asm("    .ORG $8000\n    X>A") == [106]
        assert asm("    .ORG $8000\n    Y>B") == [109]

    def test_shift_ops(self):
        assert asm("    .ORG $8000\n    A>>") == [13]
        assert asm("    .ORG $8000\n    A<<") == [14]
        assert asm("    .ORG $8000\n    AB>>") == [147]
        assert asm("    .ORG $8000\n    AB<<") == [148]
        assert asm("    .ORG $8000\n    S_A>>") == [168]

    def test_comparison_ops(self):
        assert asm("    .ORG $8000\n    CMP") == [23]
        assert asm("    .ORG $8000\n    CMP_c") == [130]
        assert asm("    .ORG $8000\n    CMP_16") == [152]
        assert asm("    .ORG $8000\n    A_ZERO") == [189]
        assert asm("    .ORG $8000\n    AB_ZERO") == [190]


class TestImmediateOpcodes:
    """Test opcodes with 8-bit immediate operands."""

    def test_set_a_decimal(self):
        result = asm("    .ORG $8000\n    SET_A #42")
        assert result == [17, 42]

    def test_set_b_hex(self):
        result = asm("    .ORG $8000\n    SET_B #$FF")
        assert result == [18, 255]

    def test_set_a_binary(self):
        result = asm("    .ORG $8000\n    SET_A #%10101010")
        assert result == [17, 170]

    def test_set_a_zero(self):
        result = asm("    .ORG $8000\n    SET_A #0")
        assert result == [17, 0]

    def test_set_a_max(self):
        result = asm("    .ORG $8000\n    SET_A #255")
        assert result == [17, 255]

    def test_imm8_out_of_range(self):
        errors = asm_errors("    .ORG $8000\n    SET_A #256")
        assert len(errors) > 0


class TestAddressOpcodes:
    """Test opcodes with 16-bit address/immediate operands."""

    def test_set_ab(self):
        # SET_AB = opcode 167, 16-bit little-endian
        result = asm("    .ORG $8000\n    SET_AB #$1234")
        assert result == [167, 0x34, 0x12]

    def test_set_cd(self):
        result = asm("    .ORG $8000\n    SET_CD #$ABCD")
        assert result == [199, 0xCD, 0xAB]

    def test_jmp_address(self):
        # JMP = opcode 34, 16-bit address little-endian
        result = asm("    .ORG $8000\n    JMP $9000")
        assert result == [34, 0x00, 0x90]

    def test_gosub_address(self):
        result = asm("    .ORG $8000\n    GOSUB $8100")
        assert result == [32, 0x00, 0x81]

    def test_load_a_address(self):
        result = asm("    .ORG $8000\n    LOAD_A $0100")
        assert result == [7, 0x00, 0x01]

    def test_store_a_address(self):
        result = asm("    .ORG $8000\n    STORE_A $2000")
        assert result == [9, 0x00, 0x20]

    def test_conditional_jumps(self):
        result = asm("    .ORG $8000\n    JMP_ZERO $8010")
        assert result == [39, 0x10, 0x80]
        result = asm("    .ORG $8000\n    JMP_OVER $8020")
        assert result == [40, 0x20, 0x80]


# ===========================================================================
# Label tests
# ===========================================================================


class TestLabels:
    """Test label definition and resolution."""

    def test_forward_reference(self):
        source = """\
    .ORG $8000
    JMP TARGET
    NOP
TARGET:
    HALT"""
        result = asm(source)
        # JMP(3 bytes) + NOP(1 byte) = TARGET at $8004
        assert result == [34, 0x04, 0x80, 0, 127]

    def test_backward_reference(self):
        source = """\
    .ORG $8000
LOOP:
    NOP
    JMP LOOP"""
        result = asm(source)
        # NOP at $8000, JMP LOOP at $8001 -> address $8000
        assert result == [0, 34, 0x00, 0x80]

    def test_multiple_labels(self):
        source = """\
    .ORG $8000
START:
    NOP
MIDDLE:
    NOP
END:
    HALT"""
        result = asm(source)
        assert result == [0, 0, 127]

    def test_label_on_same_line_as_instruction(self):
        source = """\
    .ORG $8000
START: NOP
    JMP START"""
        result = asm(source)
        assert result == [0, 34, 0x00, 0x80]

    def test_local_labels(self):
        source = """\
    .ORG $8000
FUNC1:
    NOP
.loop:
    JMP .loop
FUNC2:
    NOP
.loop:
    JMP .loop"""
        result = asm(source)
        # FUNC1 at $8000: NOP(1) .loop at $8001: JMP .loop(3) -> $8001
        # FUNC2 at $8004: NOP(1) .loop at $8005: JMP .loop(3) -> $8005
        assert result == [
            0,
            34,
            0x01,
            0x80,  # FUNC1: NOP, JMP $8001
            0,
            34,
            0x05,
            0x80,  # FUNC2: NOP, JMP $8005
        ]

    def test_undefined_label_error(self):
        errors = asm_errors("    .ORG $8000\n    JMP NOWHERE")
        assert len(errors) > 0

    def test_duplicate_label_error(self):
        source = """\
    .ORG $8000
DUP:
    NOP
DUP:
    HALT"""
        errors = asm_errors(source)
        assert len(errors) > 0

    def test_label_with_conditional_jump(self):
        source = """\
    .ORG $8000
    SET_A #10
    SET_B #10
    CMP
    JMP_ZERO EQUAL
    HALT
EQUAL:
    A>OUT_0
    HALT"""
        result = asm(source)
        # SET_A(2) + SET_B(2) + CMP(1) + JMP_ZERO(3) + HALT(1) = 9 -> EQUAL at $8009
        assert result[5] == 39  # JMP_ZERO opcode
        assert result[6] == 0x09  # low byte of $8009
        assert result[7] == 0x80  # high byte


# ===========================================================================
# Directive tests
# ===========================================================================


class TestDirectives:
    """Test assembler directives."""

    def test_org(self):
        source = """\
    .ORG $9000
    HALT"""
        assembler = Assembler(source)
        output, errors = assembler.assemble()
        assert errors == []
        assert 0x9000 in output.data
        assert output.data[0x9000] == 127

    def test_byte_directive(self):
        source = """\
    .ORG $8000
    .BYTE $FF, $00, $42"""
        result = asm(source)
        assert result == [0xFF, 0x00, 0x42]

    def test_word_directive(self):
        source = """\
    .ORG $8000
    .WORD $1234"""
        result = asm(source)
        assert result == [0x34, 0x12]  # little-endian

    def test_word_with_label(self):
        source = """\
    .ORG $8000
TARGET:
    HALT
    .WORD TARGET"""
        result = asm(source)
        # HALT at $8000, then .WORD TARGET = $8000 little-endian
        assert result == [127, 0x00, 0x80]

    def test_ascii_directive(self):
        source = """\
    .ORG $8000
    .ASCII "Hello" """
        result = asm(source)
        assert result == [72, 101, 108, 108, 111]  # "Hello"

    def test_asciiz_directive(self):
        source = """\
    .ORG $8000
    .ASCIIZ "Hi" """
        result = asm(source)
        assert result == [72, 105, 0]  # "Hi\0"

    def test_equ_directive(self):
        source = """\
    .ORG $8000
    .EQU MYVAL, $42
    SET_A #MYVAL"""
        result = asm(source)
        assert result == [17, 0x42]

    def test_equ_with_address(self):
        source = """\
    .ORG $8000
    .EQU PORT, $A000
    STORE_A PORT"""
        result = asm(source)
        assert result == [9, 0x00, 0xA0]

    def test_multiple_org(self):
        source = """\
    .ORG $8000
    NOP
    .ORG $9000
    HALT"""
        assembler = Assembler(source)
        output, errors = assembler.assemble()
        assert errors == []
        assert output.data[0x8000] == 0
        assert output.data[0x9000] == 127


# ===========================================================================
# Number format tests
# ===========================================================================


class TestNumberFormats:
    """Test hex, decimal, binary, and char literal parsing."""

    def test_hex_prefix_dollar(self):
        result = asm("    .ORG $8000\n    SET_A #$2A")
        assert result == [17, 42]

    def test_decimal(self):
        result = asm("    .ORG $8000\n    SET_A #100")
        assert result == [17, 100]

    def test_binary_prefix_percent(self):
        result = asm("    .ORG $8000\n    SET_A #%11111111")
        assert result == [17, 255]

    def test_char_literal(self):
        result = asm("    .ORG $8000\n    SET_A #'A'")
        assert result == [17, 65]


# ===========================================================================
# Lexer tests
# ===========================================================================


class TestLexer:
    """Test the lexer/tokenizer."""

    def test_digit_starting_mnemonic(self):
        """Regression: lexer must accept mnemonics starting with digits."""
        lexer = Lexer("    0>A")
        mnemonics = [t for t in lexer.get_tokens() if t.type == TokenType.MNEMONIC]
        assert len(mnemonics) == 1
        assert mnemonics[0].value == "0>A"

    def test_ff_mnemonic(self):
        lexer = Lexer("    FF>A")
        mnemonics = [t for t in lexer.get_tokens() if t.type == TokenType.MNEMONIC]
        assert len(mnemonics) == 1
        assert mnemonics[0].value == "FF>A"

    def test_ffff_mnemonic(self):
        lexer = Lexer("    FFFF>AB")
        mnemonics = [t for t in lexer.get_tokens() if t.type == TokenType.MNEMONIC]
        assert len(mnemonics) == 1
        assert mnemonics[0].value == "FFFF>AB"

    def test_label_and_mnemonic(self):
        lexer = Lexer("START: NOP")
        tokens = lexer.get_tokens()
        labels = [t for t in tokens if t.type == TokenType.LABEL]
        mnemonics = [t for t in tokens if t.type == TokenType.MNEMONIC]
        assert len(labels) == 1
        assert labels[0].value == "START"
        assert len(mnemonics) == 1
        assert mnemonics[0].value == "NOP"

    def test_comment_stripped(self):
        lexer = Lexer("    NOP ; this is a comment")
        mnemonics = [t for t in lexer.get_tokens() if t.type == TokenType.MNEMONIC]
        assert len(mnemonics) == 1

    def test_directive_token(self):
        lexer = Lexer("    .ORG $8000")
        directives = [t for t in lexer.get_tokens() if t.type == TokenType.DIRECTIVE]
        assert len(directives) == 1
        assert directives[0].value == ".ORG"

    def test_immediate_value(self):
        lexer = Lexer("    SET_A #$FF")
        tokens = lexer.get_tokens()
        imm = [t for t in tokens if t.type == TokenType.IMMEDIATE]
        nums = [t for t in tokens if t.type == TokenType.NUMBER]
        assert len(imm) == 1
        assert len(nums) == 1
        assert nums[0].value == "255"

    def test_string_literal(self):
        lexer = Lexer('    .ASCII "Hello"')
        strings = [t for t in lexer.get_tokens() if t.type == TokenType.STRING]
        assert len(strings) == 1
        assert strings[0].value == "Hello"

    def test_local_label(self):
        lexer = Lexer(".loop: NOP")
        labels = [t for t in lexer.get_tokens() if t.type == TokenType.LABEL]
        assert len(labels) == 1
        assert labels[0].value == ".loop"

    def test_case_insensitive_mnemonic(self):
        """Mnemonics should be uppercased."""
        lexer = Lexer("    nop")
        mnemonics = [t for t in lexer.get_tokens() if t.type == TokenType.MNEMONIC]
        assert len(mnemonics) == 1
        assert mnemonics[0].value == "NOP"

    def test_operand_column_is_in_original_line_coords(self):
        """Operand token columns must be relative to the original line, not a
        sliced remainder.  Previously, all operand columns were reset to 0
        after the label/mnemonic was stripped."""
        # "start:    SET_A #42"
        # Label 'start' is at col 0; mnemonic 'SET_A' is at col 10; operand '#42' at col 16.
        lexer = Lexer("start:    SET_A #42")
        tokens = {t.type: t for t in lexer.get_tokens()}
        assert tokens[TokenType.LABEL].column == 0
        assert tokens[TokenType.MNEMONIC].column == 10
        # The NUMBER token for 42 follows the '#' — it should be past col 16.
        num_tok = next(t for t in lexer.get_tokens() if t.type == TokenType.NUMBER)
        assert num_tok.column > 10, (
            f"Operand column {num_tok.column} should be > 10 (mnemonic column); "
            "column tracking was previously broken after label stripping"
        )


# ===========================================================================
# Symbol table tests
# ===========================================================================


class TestSymbolTable:
    def test_define_and_lookup(self):
        st = SymbolTable()
        st.define("FOO", 0x1234)
        assert st.lookup("FOO") == 0x1234

    def test_duplicate_error(self):
        st = SymbolTable()
        st.define("FOO", 0x1234)
        with pytest.raises(DuplicateSymbolError):
            st.define("FOO", 0x5678)

    def test_undefined_error(self):
        st = SymbolTable()
        with pytest.raises(UndefinedSymbolError):
            st.lookup("MISSING")

    def test_local_label_scoping(self):
        st = SymbolTable()
        st.define("FUNC1", 0x8000)
        st.define(".loop", 0x8001)
        st.define("FUNC2", 0x8010)
        st.define(".loop", 0x8011)
        # Lookup in FUNC2 scope
        assert st.lookup(".loop") == 0x8011
        # Switch scope back
        st.set_global_scope("FUNC1")
        assert st.lookup(".loop") == 0x8001

    def test_contains(self):
        st = SymbolTable()
        st.define("FOO", 42)
        assert st.contains("FOO")
        assert not st.contains("BAR")


# ===========================================================================
# Preprocessor tests
# ===========================================================================


class TestPreprocessor:
    """Test macro and include preprocessing."""

    def test_simple_macro(self):
        source = """\
.MACRO DOUBLE_NOP
    NOP
    NOP
.ENDM
    .ORG $8000
    DOUBLE_NOP
    HALT"""
        result = asm(source)
        assert result == [0, 0, 127]

    def test_macro_unique_counter(self):
        """\\@ should be replaced with unique numbers per expansion."""
        source = """\
.MACRO TEST_MACRO
__label_\\@:
    NOP
    JMP __label_\\@
.ENDM
    .ORG $8000
    TEST_MACRO
    TEST_MACRO"""
        result = asm(source)
        # First expansion: __label_0 at $8000, JMP $8000
        # Second expansion: __label_1 at $8004, JMP $8004
        assert result == [
            0,
            34,
            0x00,
            0x80,  # NOP, JMP $8000
            0,
            34,
            0x04,
            0x80,  # NOP, JMP $8004
        ]

    def test_nested_macro(self):
        """A macro that invokes another macro."""
        source = """\
.MACRO INNER
    NOP
.ENDM
.MACRO OUTER
    INNER
    HALT
.ENDM
    .ORG $8000
    OUTER"""
        result = asm(source)
        assert result == [0, 127]

    def test_macro_with_labels_and_counter(self):
        """Macro with internal labels using \\@ for uniqueness."""
        source = """\
.MACRO DELAY
__delay_\\@:
    A--
    JMP_ZERO __done_\\@
    JMP __delay_\\@
__done_\\@:
.ENDM
    .ORG $8000
    SET_A #5
    DELAY
    HALT"""
        result = asm(source)
        # SET_A #5 = [17, 5] at $8000-$8001
        # __delay_0 at $8002: A-- = [12]
        # JMP_ZERO __done_0 at $8003: [39, low, high] -> $800A (after JMP)
        # JMP __delay_0 at $8006: [34, 0x02, 0x80]
        # __done_0 at $8009: (empty, just a label)
        # Wait — __done_0 is at $8009, so JMP_ZERO target is $8009
        assert result[0:2] == [17, 5]  # SET_A #5
        assert result[2] == 12  # A--
        assert result[3] == 39  # JMP_ZERO
        assert result[6] == 34  # JMP
        assert result[-1] == 127  # HALT

    def test_unterminated_macro_error(self):
        source = """\
.MACRO BROKEN
    NOP"""
        pp = Preprocessor()
        with pytest.raises(PreprocessorError, match="Unterminated"):
            pp.process(source)

    def test_duplicate_macro_error(self):
        source = """\
.MACRO FOO
    NOP
.ENDM
.MACRO FOO
    HALT
.ENDM"""
        pp = Preprocessor()
        with pytest.raises(PreprocessorError, match="Duplicate"):
            pp.process(source)

    def test_macro_expansion_depth_limit(self):
        """Recursive macros should be caught."""
        source = """\
.MACRO RECURSE
    RECURSE
.ENDM
    RECURSE"""
        pp = Preprocessor()
        with pytest.raises(PreprocessorError, match="depth"):
            pp.process(source)

    def test_include_file(self, tmp_path):
        """Test .INCLUDE directive."""
        lib_file = tmp_path / "lib.asm"
        lib_file.write_text("    NOP\n")

        source = '    .INCLUDE "lib.asm"\n    .ORG $8000\n    HALT'
        assembler = Assembler(source, include_paths=[tmp_path])
        output, errors = assembler.assemble()
        assert errors == [], f"Errors: {errors}"

    def test_include_not_found(self):
        source = '    .INCLUDE "nonexistent.asm"'
        errors = asm_errors(source)
        assert len(errors) > 0

    def test_include_no_duplicates(self, tmp_path):
        """Including the same file twice should only include it once."""
        lib_file = tmp_path / "lib.asm"
        lib_file.write_text("""\
.MACRO MY_NOP
    NOP
.ENDM
""")
        source = """\
    .INCLUDE "lib.asm"
    .INCLUDE "lib.asm"
    .ORG $8000
    MY_NOP
    HALT"""
        assembler = Assembler(source, include_paths=[tmp_path])
        output, errors = assembler.assemble()
        assert errors == []

    def test_include_with_macros(self, tmp_path):
        """Macros from included files should be usable."""
        lib_file = tmp_path / "macros.asm"
        lib_file.write_text("""\
.MACRO SET_AB
    SET_A #$12
    SET_B #$34
.ENDM
""")
        source = """\
    .INCLUDE "macros.asm"
    .ORG $8000
    SET_AB
    HALT"""
        result_asm = Assembler(source, include_paths=[tmp_path])
        output, errors = result_asm.assemble()
        assert errors == []
        data = [
            output.data.get(addr, 0)
            for addr in range(output.min_address, output.max_address + 1)
        ]
        assert data == [17, 0x12, 18, 0x34, 127]


# ===========================================================================
# Integration tests — complete programs
# ===========================================================================


class TestIntegration:
    """End-to-end assembly of complete programs."""

    def test_count_to_10(self):
        """Classic loop: count A from 0 to 10."""
        source = """\
    .ORG $8000
    SET_A #0
LOOP:
    A++
    SET_B #10
    CMP
    JMP_ZERO DONE
    JMP LOOP
DONE:
    A>OUT_0
    HALT"""
        result = asm(source)
        # Verify structure: SET_A(2), A++(1), SET_B(2), CMP(1), JMP_ZERO(3), JMP(3), A>OUT_0(1), HALT(1)
        assert len(result) == 14
        assert result[0] == 17  # SET_A
        assert result[1] == 0  # #0
        assert result[-1] == 127  # HALT
        assert result[-2] == 49  # A>OUT_0

    def test_multiply_6x7(self):
        """Assemble the multiplication example (6*7=42) with stdlib macros."""
        lib_path = Path(__file__).parent.parent / "lib"
        if not (lib_path / "stdlib.asm").exists():
            pytest.skip("stdlib.asm not found")

        source = """\
    .INCLUDE "stdlib.asm"
    .ORG $8000
START:
    SET_AB #6
    SET_CD #7
    AB_MULT_CD
    AB>OUT
    HALT"""
        assembler = Assembler(
            source,
            include_paths=[lib_path],
        )
        output, errors = assembler.assemble()
        assert errors == [], f"Assembly errors: {errors}"
        assert output.data  # Should have produced some bytes

    def test_data_section_with_code(self):
        """Mix code and data directives."""
        source = """\
    .ORG $8000
    LOAD_A DATA
    A>OUT_0
    HALT
DATA:
    .BYTE $42"""
        result = asm(source)
        # LOAD_A(3) + A>OUT_0(1) + HALT(1) + BYTE(1) = 6
        assert len(result) == 6
        assert result[0] == 7  # LOAD_A opcode
        # LOAD_A address should point to DATA at $8005
        assert result[1] == 0x05
        assert result[2] == 0x80
        assert result[-1] == 0x42

    def test_jump_table(self):
        """A table of addresses using .WORD."""
        source = """\
    .ORG $8000
HANDLER_A:
    HALT
HANDLER_B:
    NOP
    HALT
TABLE:
    .WORD HANDLER_A, HANDLER_B"""
        result = asm(source)
        # HANDLER_A at $8000: HALT(1)
        # HANDLER_B at $8001: NOP(1) + HALT(1)
        # TABLE at $8003: WORD $8000, WORD $8001
        assert len(result) == 7
        # Check .WORD values (little-endian)
        assert result[3] == 0x00  # low(HANDLER_A)
        assert result[4] == 0x80  # high(HANDLER_A)
        assert result[5] == 0x01  # low(HANDLER_B)
        assert result[6] == 0x80  # high(HANDLER_B)

    def test_all_conditional_jumps_with_labels(self):
        """Every conditional jump opcode resolves labels correctly."""
        jumps = [
            ("JMP_ZERO", 39),
            ("JMP_OVER", 40),
            ("JMP_INTER", 41),
            ("JMP_A_POS", 35),
            ("JMP_A_EVEN", 36),
            ("JMP_B_POS", 37),
            ("JMP_B_EVEN", 38),
        ]
        for mnemonic, opcode_byte in jumps:
            source = f"""\
    .ORG $8000
    {mnemonic} TARGET
TARGET:
    HALT"""
            result = asm(source)
            assert result[0] == opcode_byte, f"{mnemonic} opcode wrong"
            # Target is at $8003 (after 3-byte jump instruction)
            assert result[1] == 0x03, f"{mnemonic} target low byte wrong"
            assert result[2] == 0x80, f"{mnemonic} target high byte wrong"
            assert result[3] == 127, f"{mnemonic} HALT missing"


# ===========================================================================
# Error handling tests
# ===========================================================================


class TestErrors:
    def test_unknown_opcode(self):
        errors = asm_errors("    .ORG $8000\n    BOGUS")
        assert len(errors) > 0

    def test_missing_operand_for_set_a(self):
        errors = asm_errors("    .ORG $8000\n    SET_A")
        assert len(errors) > 0

    def test_extra_operand_for_nop(self):
        errors = asm_errors("    .ORG $8000\n    NOP #5")
        assert len(errors) > 0

    def test_address_out_of_range(self):
        errors = asm_errors("    .ORG $8000\n    JMP $10000")
        assert len(errors) > 0

    def test_empty_source(self):
        result = asm("")
        assert result == []

    def test_comment_only(self):
        result = asm("; just a comment")
        assert result == []

    def test_asm_syntax_error_is_assembly_error_not_builtin(self):
        """AsmSyntaxError must not be caught by bare 'except SyntaxError' (builtin)."""
        from sk02_asm.errors import AssemblyError

        err = AsmSyntaxError("bad syntax", line_num=1)
        assert isinstance(err, AssemblyError)
        # Must NOT be the Python builtin SyntaxError
        assert not isinstance(err, builtins.SyntaxError)

    def test_bad_org_directive_raises_asm_syntax_error(self):
        """A bad .ORG raises AsmSyntaxError (not Python builtin SyntaxError)."""
        errors = asm_errors("    .ORG")
        assert len(errors) > 0
        assert isinstance(errors[0], AssemblyError)


# ---------------------------------------------------------------------------
# Output writer tests
# ---------------------------------------------------------------------------


class TestOutputWriters:
    """BinaryWriter and IntelHexWriter share validation logic via base class."""

    def test_binary_writer_write_and_read(self):
        w = BinaryWriter()
        w.write_byte(0x8000, 0xAB)
        assert w.data[0x8000] == 0xAB
        assert w.min_address == 0x8000
        assert w.max_address == 0x8000

    def test_binary_writer_tracks_extents(self):
        w = BinaryWriter()
        w.write_byte(0x8005, 0x01)
        w.write_byte(0x8000, 0x02)
        assert w.min_address == 0x8000
        assert w.max_address == 0x8005

    def test_binary_writer_address_out_of_range(self):
        w = BinaryWriter()
        with pytest.raises(AddressOutOfRangeError):
            w.write_byte(0x10000, 0x00)

    def test_binary_writer_value_out_of_range(self):
        w = BinaryWriter()
        with pytest.raises(InvalidOperandError):
            w.write_byte(0x8000, 0x100)

    def test_intel_hex_writer_write_and_read(self):
        w = IntelHexWriter()
        w.write_byte(0x8000, 0xCD)
        assert w.data[0x8000] == 0xCD

    def test_intel_hex_writer_address_out_of_range(self):
        w = IntelHexWriter()
        with pytest.raises(AddressOutOfRangeError):
            w.write_byte(0x10000, 0x00)

    def test_intel_hex_writer_value_out_of_range(self):
        w = IntelHexWriter()
        with pytest.raises(InvalidOperandError):
            w.write_byte(0x8000, 256)

    def test_write_bytes_delegates_to_write_byte(self):
        w = BinaryWriter()
        w.write_bytes(0x8000, [0x01, 0x02, 0x03])
        assert w.data[0x8000] == 0x01
        assert w.data[0x8001] == 0x02
        assert w.data[0x8002] == 0x03
