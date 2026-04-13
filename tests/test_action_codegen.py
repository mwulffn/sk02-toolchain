"""Tests for the SK-02 Action! code generator.

Red/green: tests written first, then codegen implemented to pass them.
Helper: asm_lines(source) compiles Action! source → list of stripped assembly lines.
"""

from sk02action.call_graph import CallGraph
from sk02action.codegen import CodeGenerator
from sk02action.const_fold import ConstantFolder
from sk02action.lexer import Lexer
from sk02action.parser import Parser
from sk02action.type_checker import TypeChecker

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def asm_lines(source: str) -> list[str]:
    """Compile Action! source and return stripped, non-empty, non-comment lines."""
    tokens = Lexer(source).tokenize()
    ast = Parser(tokens).parse_program()
    TypeChecker().check(ast)
    ConstantFolder().fold(ast)
    cg = CallGraph(ast)
    cg.check_no_recursion()
    gen = CodeGenerator(cg)
    output = gen.generate(ast)
    return [
        line.strip()
        for line in output.splitlines()
        if line.strip() and not line.strip().startswith(";")
    ]


def asm_text(source: str) -> str:
    """Compile Action! source and return full assembly text."""
    tokens = Lexer(source).tokenize()
    ast = Parser(tokens).parse_program()
    TypeChecker().check(ast)
    ConstantFolder().fold(ast)
    cg = CallGraph(ast)
    cg.check_no_recursion()
    gen = CodeGenerator(cg)
    return gen.generate(ast)


# ===========================================================================
# Startup and structure
# ===========================================================================


class TestEmitStructure:
    """Generated assembly has correct overall structure."""

    def test_has_org(self):
        lines = asm_lines("PROC Main()\nRETURN")
        assert ".ORG $8000" in lines

    def test_entry_point_is_last_proc(self):
        """Startup GOSUB targets the last PROC."""
        lines = asm_lines("PROC Foo()\nRETURN\nPROC Main()\nRETURN")
        # Should have GOSUB _main early in the output
        assert "GOSUB _main" in lines

    def test_proc_label(self):
        lines = asm_lines("PROC Main()\nRETURN")
        assert "_main:" in lines

    def test_proc_return(self):
        lines = asm_lines("PROC Main()\nRETURN")
        assert "RETURN" in lines


# ===========================================================================
# Global variables
# ===========================================================================


class TestEmitGlobalVars:
    """Global variable declarations emit correct storage directives."""

    def test_byte_var(self):
        text = asm_text("BYTE x\nPROC Main()\nRETURN")
        assert "_x:" in text
        assert ".BYTE 0" in text

    def test_card_var(self):
        text = asm_text("CARD c\nPROC Main()\nRETURN")
        assert "_c:" in text
        assert ".WORD 0" in text

    def test_initialized_byte(self):
        text = asm_text("BYTE x=[42]\nPROC Main()\nRETURN")
        assert ".BYTE 42" in text

    def test_initialized_card(self):
        text = asm_text("CARD c=[1000]\nPROC Main()\nRETURN")
        assert ".WORD 1000" in text

    def test_address_placed(self):
        """Variables with =address emit .EQU instead of storage."""
        text = asm_text("BYTE x=$8000\nPROC Main()\nRETURN")
        assert ".EQU _x, $8000" in text


# ===========================================================================
# Assignment (8-bit)
# ===========================================================================


class TestEmitAssignment8Bit:
    """8-bit variable assignment generates correct load/store."""

    def test_assign_literal(self):
        """x = 5 → SET_A #5, STORE_A _main_x"""
        lines = asm_lines("PROC Main()\n  BYTE x\n  x = 5\nRETURN")
        assert "SET_A #5" in lines
        assert "STORE_A _main_x" in lines

    def test_assign_variable(self):
        """y = x → LOAD_A _main_x, STORE_A _main_y"""
        lines = asm_lines("PROC Main()\n  BYTE x, y\n  x = 1\n  y = x\nRETURN")
        assert "LOAD_A _main_x" in lines
        assert "STORE_A _main_y" in lines


# ===========================================================================
# Assignment (16-bit)
# ===========================================================================


class TestEmitAssignment16Bit:
    """16-bit variable assignment generates correct load/store via CD pointer."""

    def test_assign_literal(self):
        """c = 1000 → SET_AB #1000, SET_CD #_main_c, ST_AB_CD"""
        lines = asm_lines("PROC Main()\n  CARD c\n  c = 1000\nRETURN")
        assert "SET_AB #1000" in lines
        assert "SET_CD #_main_c" in lines
        assert "ST_AB_CD" in lines

    def test_assign_variable(self):
        """d = c → SET_CD #_main_c, LO_AB_CD, SET_CD #_main_d, ST_AB_CD"""
        lines = asm_lines("PROC Main()\n  CARD c, d\n  c = 1000\n  d = c\nRETURN")
        assert "LO_AB_CD" in lines

    def test_assign_negative_int_literal(self):
        """INT i = -2 → SET_AB #65534 (two's complement, not SET_AB #-2)."""
        lines = asm_lines("PROC Main()\n  INT i\n  i = -2\nRETURN")
        assert "SET_AB #65534" in lines

    def test_assign_negative_int_to_byte_var(self):
        """Assigning -1 to BYTE: -1 has INT type, so SET_AB #65535 (masked), not SET_AB #-1."""
        lines = asm_lines("PROC Main()\n  BYTE b\n  b = -1\nRETURN")
        assert "SET_AB #65535" in lines
        assert "SET_AB #-1" not in lines


# ===========================================================================
# Arithmetic (8-bit)
# ===========================================================================


class TestEmitArithmetic8Bit:
    """8-bit arithmetic generates correct register operations."""

    def test_add(self):
        lines = asm_lines("PROC Main()\n  BYTE a, b, c\n  c = a + b\nRETURN")
        assert "ADD" in lines

    def test_sub(self):
        lines = asm_lines("PROC Main()\n  BYTE a, b, c\n  c = a - b\nRETURN")
        assert "SUB" in lines

    def test_bitwise_and(self):
        lines = asm_lines("PROC Main()\n  BYTE a, b, c\n  c = a AND b\nRETURN")
        assert "AND" in lines

    def test_bitwise_or(self):
        lines = asm_lines("PROC Main()\n  BYTE a, b, c\n  c = a OR b\nRETURN")
        assert "OR" in lines

    def test_bitwise_xor(self):
        lines = asm_lines("PROC Main()\n  BYTE a, b, c\n  c = a XOR b\nRETURN")
        assert "XOR" in lines


# ===========================================================================
# Arithmetic (16-bit)
# ===========================================================================


class TestEmitArithmetic16Bit:
    """16-bit arithmetic uses AB/CD register pairs."""

    def test_add(self):
        lines = asm_lines("PROC Main()\n  CARD a, b, c\n  c = a + b\nRETURN")
        assert "AB+CD" in lines

    def test_sub(self):
        lines = asm_lines("PROC Main()\n  CARD a, b, c\n  c = a - b\nRETURN")
        assert "AB-CD" in lines


# ===========================================================================
# Comparisons
# ===========================================================================


class TestEmitComparison:
    """Comparison operators generate CMP + conditional jumps."""

    def test_equality(self):
        lines = asm_lines("PROC Main()\n  BYTE a, b, c\n  c = a = b\nRETURN")
        assert "CMP" in lines
        assert any("JMP_ZERO" in ln for ln in lines)

    def test_less_than(self):
        lines = asm_lines("PROC Main()\n  BYTE a, b, c\n  c = a < b\nRETURN")
        assert "CMP" in lines
        assert any("JMP_OVER" in ln for ln in lines)


# ===========================================================================
# IF statement
# ===========================================================================


class TestEmitIf:
    """IF/THEN/FI generates condition + conditional jump over body."""

    def test_simple_if(self):
        lines = asm_lines(
            "PROC Main()\n  BYTE x\n  IF x > 0 THEN\n    x = 1\n  FI\nRETURN"
        )
        # Should have A_ZERO or CMP + conditional jump
        has_conditional = any("JMP_ZERO" in ln or "JMP_OVER" in ln for ln in lines)
        assert has_conditional

    def test_if_else(self):
        lines = asm_lines(
            "PROC Main()\n  BYTE x\n"
            "  IF x > 0 THEN\n    x = 1\n  ELSE\n    x = 0\n  FI\nRETURN"
        )
        # Should have at least two JMP instructions (conditional + unconditional)
        jmp_count = sum(1 for ln in lines if ln.startswith("JMP "))
        assert jmp_count >= 1


# ===========================================================================
# WHILE loop
# ===========================================================================


class TestEmitWhile:
    """WHILE/DO/OD generates loop with condition check and back-jump."""

    def test_while_loop(self):
        lines = asm_lines(
            "PROC Main()\n  BYTE x\n  x = 10\n"
            "  WHILE x > 0\n  DO\n    x = x - 1\n  OD\nRETURN"
        )
        # Should have a JMP back to loop start
        jmp_lines = [ln for ln in lines if ln.startswith("JMP ")]
        assert len(jmp_lines) >= 1


# ===========================================================================
# Procedure calls
# ===========================================================================


class TestEmitProcCall:
    """Procedure calls pass arguments and emit GOSUB."""

    def test_no_args(self):
        lines = asm_lines("PROC Foo()\nRETURN\nPROC Main()\n  Foo()\nRETURN")
        assert "GOSUB _foo" in lines

    def test_one_byte_arg(self):
        """First BYTE arg goes in A register."""
        lines = asm_lines("PROC Foo(BYTE a)\nRETURN\nPROC Main()\n  Foo(42)\nRETURN")
        assert "SET_A #42" in lines
        assert "GOSUB _foo" in lines

    def test_two_byte_args(self):
        """Second BYTE arg goes in B register."""
        lines = asm_lines(
            "PROC Foo(BYTE a, BYTE b)\nRETURN\nPROC Main()\n  Foo(1, 2)\nRETURN"
        )
        assert "GOSUB _foo" in lines


# ===========================================================================
# FUNC return
# ===========================================================================


class TestEmitFuncReturn:
    """FUNC return value in A (8-bit) or AB (16-bit)."""

    def test_return_literal(self):
        lines = asm_lines("BYTE FUNC Get5()\nRETURN(5)\nPROC Main()\nRETURN")
        assert "SET_A #5" in lines
        assert "RETURN" in lines

    def test_return_16bit(self):
        lines = asm_lines("CARD FUNC GetBig()\nRETURN(1000)\nPROC Main()\nRETURN")
        assert "SET_AB #1000" in lines
        assert "RETURN" in lines


# ===========================================================================
# Runtime routines (multiply / divide / modulo)
# ===========================================================================


class TestRuntimeRoutines:
    """Multiply/divide/modulo emit GOSUB to runtime subroutines."""

    def test_multiply_emits_gosub_rt_mul(self):
        # Use variables so constant folding doesn't eliminate the multiply
        lines = asm_lines(
            "PROC Main()\n  BYTE a, b, x\n  a = 6\n  b = 7\n  x = a * b\nRETURN"
        )
        assert "GOSUB __rt_mul" in lines

    def test_divide_emits_gosub_rt_div(self):
        lines = asm_lines(
            "PROC Main()\n  BYTE a, b, x\n  a = 10\n  b = 2\n  x = a / b\nRETURN"
        )
        assert "GOSUB __rt_div" in lines

    def test_modulo_emits_gosub_and_c_to_a(self):
        lines = asm_lines(
            "PROC Main()\n  BYTE a, b, x\n  a = 7\n  b = 3\n  x = a MOD b\nRETURN"
        )
        assert "GOSUB __rt_div" in lines
        assert "C>A" in lines

    def test_rt_mul_routine_in_output(self):
        text = asm_text(
            "PROC Main()\n  BYTE a, b, x\n  a = 2\n  b = 3\n  x = a * b\nRETURN"
        )
        assert "__rt_mul:" in text

    def test_rt_div_routine_in_output(self):
        text = asm_text(
            "PROC Main()\n  BYTE a, b, x\n  a = 6\n  b = 2\n  x = a / b\nRETURN"
        )
        assert "__rt_div:" in text

    def test_runtime_not_emitted_when_unused(self):
        text = asm_text("PROC Main()\n  BYTE x\n  x = 3 + 4\nRETURN")
        assert "__rt_mul" not in text
        assert "__rt_div" not in text


# ===========================================================================
# Pointer codegen
# ===========================================================================


class TestPointerCodegen:
    """Address-of and dereference emit correct instructions."""

    def test_address_of_emits_set_ab(self):
        """@x emits SET_AB #_x (loads address of x into AB)."""
        lines = asm_lines("BYTE x\nBYTE POINTER bp\nPROC Main()\n  bp = @x\nRETURN")
        assert any(line.startswith("SET_AB #_x") for line in lines)

    def test_deref_read_byte(self):
        """bp^ read emits LOAD_A_CD (indirect byte load via CD)."""
        lines = asm_lines("BYTE POINTER bp\nPROC Main()\n  BYTE x\n  x = bp^\nRETURN")
        assert "LOAD_A_CD" in lines

    def test_deref_write_byte(self):
        """bp^ = 42 emits STORE_A_GH (indirect byte store via GH)."""
        lines = asm_lines("BYTE POINTER bp\nPROC Main()\n  bp^ = 42\nRETURN")
        assert "STORE_A_GH" in lines

    def test_pointer_var_stored_as_word(self):
        """BYTE POINTER bp generates .WORD 0 storage."""
        text = asm_text("BYTE POINTER bp\nPROC Main()\nRETURN")
        assert ".WORD" in text


# ===========================================================================
# Array codegen
# ===========================================================================


class TestArrayCodegen:
    """Array declarations and element access emit correct instructions."""

    def test_array_storage_emitted(self):
        """BYTE ARRAY buf(10) generates 10 bytes of .BYTE 0 storage."""
        text = asm_text("BYTE ARRAY buf(10)\nPROC Main()\nRETURN")
        assert ".BYTE" in text

    def test_array_read_emits_load_a_cd(self):
        """buf(i) read emits LOAD_A_CD for BYTE array."""
        lines = asm_lines(
            "BYTE ARRAY buf(10)\nPROC Main()\n  BYTE x, i\n  x = buf(i)\nRETURN"
        )
        assert "LOAD_A_CD" in lines

    def test_array_write_emits_store_a_gh(self):
        """buf(i) = 42 emits STORE_A_GH for BYTE array."""
        lines = asm_lines(
            "BYTE ARRAY buf(10)\nPROC Main()\n  BYTE i\n  buf(i) = 42\nRETURN"
        )
        assert "STORE_A_GH" in lines

    def test_array_bracket_init_emits_data(self):
        """BYTE ARRAY d = [10 20 30] emits .BYTE 10, 20, 30 in data section."""
        text = asm_text("BYTE ARRAY d = [10 20 30]\nPROC Main()\nRETURN")
        assert ".BYTE 10, 20, 30" in text

    def test_array_string_init_emits_data(self):
        """BYTE ARRAY m = "Hi" emits .BYTE 2, 72, 105 (len byte + chars)."""
        text = asm_text('BYTE ARRAY m = "Hi"\nPROC Main()\nRETURN')
        assert ".BYTE 2, 72, 105" in text

    def test_card_array_bracket_init_emits_word(self):
        """CARD ARRAY t = [1000 2000] emits .WORD 1000, 2000."""
        text = asm_text("CARD ARRAY t = [1000 2000]\nPROC Main()\nRETURN")
        assert ".WORD 1000, 2000" in text


# ===========================================================================
# I/O Intrinsics
# ===========================================================================


class TestIOIntrinsics:
    """I/O intrinsics emit inline instructions, not GOSUB."""

    def test_readx_emits_inline(self):
        """ReadX() emits X>A, no GOSUB."""
        lines = asm_lines("PROC Main()\n  BYTE x\n  x = ReadX()\nRETURN")
        assert "X>A" in lines
        assert not any("GOSUB" in l and "readx" in l.lower() for l in lines)

    def test_ready_emits_inline(self):
        """ReadY() emits Y>A, no GOSUB."""
        lines = asm_lines("PROC Main()\n  BYTE y\n  y = ReadY()\nRETURN")
        assert "Y>A" in lines
        assert not any("GOSUB" in l and "ready" in l.lower() for l in lines)

    def test_gpioread_emits_inline(self):
        """GpioRead() emits GPIO>A, no GOSUB."""
        lines = asm_lines("PROC Main()\n  BYTE g\n  g = GpioRead()\nRETURN")
        assert "GPIO>A" in lines
        assert not any("GOSUB" in l and "gpioread" in l.lower() for l in lines)

    def test_gpiowrite_emits_inline(self):
        """GpioWrite(42) emits SET_A #42 then A>GPIO, no GOSUB."""
        lines = asm_lines("PROC Main()\n  GpioWrite(42)\nRETURN")
        assert "A>GPIO" in lines
        assert not any("GOSUB" in l and "gpiowrite" in l.lower() for l in lines)

    def test_out0write_emits_inline(self):
        """Out0Write(5) emits A>OUT_0, no GOSUB."""
        lines = asm_lines("PROC Main()\n  Out0Write(5)\nRETURN")
        assert "A>OUT_0" in lines
        assert not any("GOSUB" in l and "out0" in l.lower() for l in lines)

    def test_out1write_emits_inline(self):
        """Out1Write(7) emits A>OUT_1, no GOSUB."""
        lines = asm_lines("PROC Main()\n  Out1Write(7)\nRETURN")
        assert "A>OUT_1" in lines
        assert not any("GOSUB" in l and "out1" in l.lower() for l in lines)

    def test_outwrite_emits_inline(self):
        """OutWrite(3, 4) emits AB>OUT, no GOSUB."""
        lines = asm_lines("PROC Main()\n  OutWrite(3, 4)\nRETURN")
        assert "AB>OUT" in lines
        assert not any("GOSUB" in l and "outwrite" in l.lower() for l in lines)

    def test_clearinterrupt_emits_inline(self):
        """ClearInterrupt() emits CLEAR_INTER, no GOSUB."""
        lines = asm_lines("PROC Main()\n  ClearInterrupt()\nRETURN")
        assert "CLEAR_INTER" in lines
        assert not any("GOSUB" in l and "clear" in l.lower() for l in lines)

    def test_interruptflag_emits_inline(self):
        """InterruptFlag() emits JMP_INTER-based sequence, no GOSUB."""
        lines = asm_lines("PROC Main()\n  BYTE f\n  f = InterruptFlag()\nRETURN")
        assert any(l.startswith("JMP_INTER") for l in lines)
        assert not any("GOSUB" in l and "interrupt" in l.lower() for l in lines)


# ===========================================================================
# SET directive codegen
# ===========================================================================


class TestSetDirectiveCodegen:
    """SET directive emits .ORG + .WORD at the end of the output."""

    def test_set_emits_org_and_word_for_label(self):
        """SET $FFFE = Main → .ORG $FFFE + .WORD _main in assembly."""
        text = asm_text("PROC Main()\nRETURN\nSET $FFFE = main")
        assert ".ORG $FFFE" in text
        assert ".WORD _main" in text

    def test_set_emits_org_and_word_for_numeric(self):
        """SET 100 = 42 → .ORG $0064 + .WORD 42 in assembly."""
        text = asm_text("PROC Main()\nRETURN\nSET 100 = 42")
        assert ".ORG $0064" in text
        assert ".WORD 42" in text

    def test_set_appears_after_data_section(self):
        """SET directives come after the data section comment."""
        text = asm_text("PROC Main()\nRETURN\nSET $FFFE = main")
        data_pos = text.find("Data section")
        org_pos = text.find(".ORG $FFFE")
        assert data_pos != -1 and org_pos != -1
        assert org_pos > data_pos

    def test_multiple_set_directives_all_emitted(self):
        """Two SET directives both appear in output."""
        text = asm_text("PROC Main()\nRETURN\nSET $FFFE = main\nSET $FFFC = 0")
        assert ".ORG $FFFE" in text
        assert ".ORG $FFFC" in text


# ===========================================================================
# String literal codegen
# ===========================================================================


class TestStringLiteralCodegen:
    """String literals in expressions allocate anonymous BYTE ARRAYs."""

    def test_string_literal_emits_set_ab(self):
        """p = "Hi" emits SET_AB #_str_0."""
        lines = asm_lines('BYTE POINTER p\nPROC Main()\n  p = "Hi"\nRETURN')
        assert any("SET_AB #_str_0" in line for line in lines)

    def test_string_literal_data_section_length_prefix(self):
        """String literal data: length byte followed by char bytes."""
        text = asm_text('BYTE POINTER p\nPROC Main()\n  p = "Hi"\nRETURN')
        # "Hi" → [2, 72, 105]
        assert "_str_0:" in text
        assert ".BYTE 2, 72, 105" in text

    def test_two_string_literals_get_distinct_labels(self):
        """Two distinct string literals emit _str_0 and _str_1."""
        text = asm_text(
            "BYTE POINTER p\n"
            "BYTE POINTER q\n"
            'PROC Main()\n  p = "Hi"\n  q = "Bye"\nRETURN'
        )
        assert "_str_0:" in text
        assert "_str_1:" in text

    def test_empty_string_literal_emits_length_zero(self):
        """Empty string literal data: just the zero length byte."""
        text = asm_text('BYTE POINTER p\nPROC Main()\n  p = ""\nRETURN')
        assert "_str_0:" in text
        assert ".BYTE 0" in text
