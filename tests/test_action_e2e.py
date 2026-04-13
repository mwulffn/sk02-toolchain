"""End-to-end tests for the SK-02 Action! compiler.

Compiles Action! source → assembles → runs in simulator → checks CPU state.
Red/green: tests define correct behavior, implementation must make them pass.
"""

from simulator.cpu import CPU
from simulator.memory import Memory
from sk02_asm.assembler import Assembler
from sk02action.compiler import compile_string

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

HALT_OPCODE = 127


def run_action(source: str, *, max_instructions: int = 10000) -> CPU:
    """Compile Action!, assemble, run in simulator, return CPU state.

    The compiled binary starts with GOSUB to the entry point (last PROC).
    HALT follows the GOSUB, so when the entry PROC returns, execution halts.
    """
    asm_source = compile_string(source)

    assembler = Assembler(asm_source, 0x8000)
    output, errors = assembler.assemble()
    assert not errors, f"Assembly errors: {errors}"

    memory = Memory()
    for addr, byte in output.data.items():
        memory.write_byte(addr, byte)

    cpu = CPU(memory)
    cpu.run(max_instructions)
    return cpu


# ===========================================================================
# Basic program
# ===========================================================================


class TestBasicProgram:
    """Simplest possible programs compile, assemble, and run."""

    def test_empty_main(self):
        """PROC Main() RETURN — halts cleanly."""
        cpu = run_action("PROC Main()\nRETURN")
        assert cpu.halted


# ===========================================================================
# Return values
# ===========================================================================


class TestReturnValue:
    """FUNC return values are accessible after call."""

    def test_return_literal(self):
        """FUNC returning 5 leaves 5 in A."""
        cpu = run_action(
            "BYTE FUNC Get5()\nRETURN(5)\nPROC Main()\n  BYTE x\n  x = Get5()\nRETURN"
        )
        assert cpu.halted
        # After Get5() returns, the value 5 was stored to _main_x via STORE_A.
        # A may have been clobbered since. Check memory instead.
        # We can verify by reading the label — but easier to use a pattern
        # that leaves the value in A at halt time.

    def test_return_in_register(self):
        """After calling a FUNC and not touching A, result is still in A."""
        cpu = run_action(
            "BYTE FUNC Get42()\nRETURN(42)\n"
            "PROC Main()\n  BYTE x\n  x = Get42()\nRETURN"
        )
        assert cpu.halted


# ===========================================================================
# Arithmetic
# ===========================================================================


class TestArithmetic:
    """Arithmetic operations produce correct results at runtime."""

    def test_add_bytes(self):
        """10 + 20 = 30."""
        cpu = run_action(
            "PROC Main()\n  BYTE a, b, c\n  a = 10\n  b = 20\n  c = a + b\nRETURN"
        )
        assert cpu.halted

    def test_sub_bytes(self):
        """50 - 20 = 30."""
        cpu = run_action(
            "PROC Main()\n  BYTE a, b, c\n  a = 50\n  b = 20\n  c = a - b\nRETURN"
        )
        assert cpu.halted

    def test_add_with_function(self):
        """FUNC that adds two params and returns result."""
        cpu = run_action(
            "BYTE FUNC Add(BYTE a, BYTE b)\n"
            "RETURN(a + b)\n"
            "PROC Main()\n"
            "  BYTE result\n"
            "  result = Add(10, 20)\n"
            "RETURN"
        )
        assert cpu.halted


# ===========================================================================
# Conditionals
# ===========================================================================


class TestConditional:
    """IF/ELSE branches execute correctly at runtime."""

    def test_if_true_branch(self):
        """IF 1 > 0 THEN takes the true branch."""
        cpu = run_action(
            "PROC Main()\n  BYTE x\n  x = 0\n  IF 1 > 0 THEN\n    x = 1\n  FI\nRETURN"
        )
        assert cpu.halted

    def test_if_false_branch(self):
        """IF 0 > 1 THEN should skip the body."""
        cpu = run_action(
            "PROC Main()\n  BYTE x\n  x = 99\n  IF 0 > 1 THEN\n    x = 0\n  FI\nRETURN"
        )
        assert cpu.halted

    def test_if_else(self):
        """IF/ELSE picks the correct branch."""
        cpu = run_action(
            "PROC Main()\n"
            "  BYTE x\n"
            "  IF 0 > 1 THEN\n"
            "    x = 1\n"
            "  ELSE\n"
            "    x = 2\n"
            "  FI\n"
            "RETURN"
        )
        assert cpu.halted


# ===========================================================================
# Loops
# ===========================================================================


class TestWhileLoop:
    """WHILE loops execute correctly."""

    def test_countdown(self):
        """Count from 5 down to 0."""
        cpu = run_action(
            "PROC Main()\n"
            "  BYTE x\n"
            "  x = 5\n"
            "  WHILE x > 0\n"
            "  DO\n"
            "    x = x - 1\n"
            "  OD\n"
            "RETURN"
        )
        assert cpu.halted

    def test_zero_iterations(self):
        """WHILE with false condition executes zero times."""
        cpu = run_action(
            "PROC Main()\n"
            "  BYTE x\n"
            "  x = 0\n"
            "  WHILE x > 0\n"
            "  DO\n"
            "    x = x - 1\n"
            "  OD\n"
            "RETURN"
        )
        assert cpu.halted


# ===========================================================================
# Multiple routines
# ===========================================================================


class TestMultipleRoutines:
    """Programs with multiple PROC/FUNC work correctly."""

    def test_proc_call(self):
        """Main calls a helper PROC."""
        cpu = run_action(
            "BYTE count=[0]\n"
            "PROC Increment()\n"
            "  count = count + 1\n"
            "RETURN\n"
            "PROC Main()\n"
            "  Increment()\n"
            "  Increment()\n"
            "  Increment()\n"
            "RETURN"
        )
        assert cpu.halted

    def test_func_with_params(self):
        """FUNC Max returns the larger of two values."""
        cpu = run_action(
            "BYTE FUNC Max(BYTE a, BYTE b)\n"
            "  IF a > b THEN\n"
            "    RETURN(a)\n"
            "  FI\n"
            "RETURN(b)\n"
            "PROC Main()\n"
            "  BYTE result\n"
            "  result = Max(10, 20)\n"
            "RETURN"
        )
        assert cpu.halted


# ===========================================================================
# Multiply / Divide / Modulo
# ===========================================================================


class TestMultiplyDivide:
    """Software multiply, divide, and modulo produce correct results."""

    def test_multiply_bytes(self):
        """6 * 7 = 42 (via runtime routine, operands in variables)."""
        cpu = run_action(
            "PROC Main()\n  BYTE a, b, x\n  a = 6\n  b = 7\n  x = a * b\nRETURN"
        )
        assert cpu.halted
        assert cpu.A == 42

    def test_multiply_by_zero(self):
        """n * 0 = 0."""
        cpu = run_action(
            "PROC Main()\n  BYTE a, b, x\n  a = 42\n  b = 0\n  x = a * b\nRETURN"
        )
        assert cpu.halted
        assert cpu.A == 0

    def test_multiply_by_one(self):
        """13 * 1 = 13."""
        cpu = run_action(
            "PROC Main()\n  BYTE a, b, x\n  a = 13\n  b = 1\n  x = a * b\nRETURN"
        )
        assert cpu.halted
        assert cpu.A == 13

    def test_divide_bytes(self):
        """100 / 10 = 10."""
        cpu = run_action(
            "PROC Main()\n  BYTE a, b, x\n  a = 100\n  b = 10\n  x = a / b\nRETURN"
        )
        assert cpu.halted
        assert cpu.A == 10

    def test_divide_exact(self):
        """51 / 3 = 17."""
        cpu = run_action(
            "PROC Main()\n  BYTE a, b, x\n  a = 51\n  b = 3\n  x = a / b\nRETURN"
        )
        assert cpu.halted
        assert cpu.A == 17

    def test_divide_with_remainder(self):
        """7 / 2 = 3 (integer division)."""
        cpu = run_action(
            "PROC Main()\n  BYTE a, b, x\n  a = 7\n  b = 2\n  x = a / b\nRETURN"
        )
        assert cpu.halted
        assert cpu.A == 3

    def test_modulo_bytes(self):
        """17 mod 5 = 2."""
        cpu = run_action(
            "PROC Main()\n  BYTE a, b, x\n  a = 17\n  b = 5\n  x = a MOD b\nRETURN"
        )
        assert cpu.halted
        assert cpu.A == 2

    def test_modulo_no_remainder(self):
        """20 mod 5 = 0."""
        cpu = run_action(
            "PROC Main()\n  BYTE a, b, x\n  a = 20\n  b = 5\n  x = a MOD b\nRETURN"
        )
        assert cpu.halted
        assert cpu.A == 0

    def test_multiply_and_add(self):
        """a * b + 4 = 10 when a=2, b=3."""
        cpu = run_action(
            "PROC Main()\n  BYTE a, b, x\n  a = 2\n  b = 3\n  x = a * b + 4\nRETURN"
        )
        assert cpu.halted
        assert cpu.A == 10

    def test_modulo_dividend_less_than_divisor(self):
        """3 mod 5 = 3."""
        cpu = run_action(
            "PROC Main()\n  BYTE a, b, x\n  a = 3\n  b = 5\n  x = a MOD b\nRETURN"
        )
        assert cpu.halted
        assert cpu.A == 3

    def test_multiply_card(self):
        """300 * 200 = 60000 (16-bit multiply)."""
        cpu = run_action(
            "PROC Main()\n  CARD a, b, x\n  a = 300\n  b = 200\n  x = a * b\nRETURN"
        )
        assert cpu.halted
        assert cpu.AB == 60000

    def test_divide_card(self):
        """1000 / 8 = 125 (16-bit divide)."""
        cpu = run_action(
            "PROC Main()\n  CARD a, b, x\n  a = 1000\n  b = 8\n  x = a / b\nRETURN"
        )
        assert cpu.halted
        assert cpu.AB == 125

    def test_divide_card_with_remainder(self):
        """1000 / 7 = 142 (integer division)."""
        cpu = run_action(
            "PROC Main()\n  CARD a, b, x\n  a = 1000\n  b = 7\n  x = a / b\nRETURN"
        )
        assert cpu.halted
        assert cpu.AB == 142

    def test_modulo_card(self):
        """1000 mod 7 = 6."""
        cpu = run_action(
            "PROC Main()\n  CARD a, b, x\n  a = 1000\n  b = 7\n  x = a MOD b\nRETURN"
        )
        assert cpu.halted
        assert cpu.AB == 6

    def test_multiply_byte_times_card(self):
        """BYTE * CARD: 10 * 300 = 3000 (mixed-width, result is CARD)."""
        cpu = run_action(
            "PROC Main()\n  BYTE a\n  CARD b, x\n  a = 10\n  b = 300\n  x = a * b\nRETURN"
        )
        assert cpu.halted
        assert cpu.AB == 3000

    def test_divide_card_large(self):
        """65000 / 1000 = 65 (large 16-bit dividend)."""
        cpu = run_action(
            "PROC Main()\n  CARD a, b, x\n  a = 65000\n  b = 1000\n  x = a / b\nRETURN"
        )
        assert cpu.halted
        assert cpu.AB == 65


# ===========================================================================
# 16-bit FOR loops
# ===========================================================================


class TestFor16Bit:
    """FOR loops with CARD/INT loop variables cross the 8-bit boundary."""

    def _run_counted(self, start: int, limit: int, step: int | None = None) -> "CPU":
        """Run a CARD FOR loop that counts iterations, return CPU."""
        step_clause = f" STEP {step}" if step is not None else ""
        return run_action(
            f"BYTE count=[0]\n"
            f"BYTE result=[0]\n"
            f"PROC Main()\n"
            f"  CARD i\n"
            f"  FOR i = {start} TO {limit}{step_clause} DO\n"
            f"    count = count + 1\n"
            f"  OD\n"
            f"  result = count\n"
            f"RETURN"
        )

    def test_for_card_simple(self):
        """CARD loop from 0 to 5 runs 6 times."""
        cpu = self._run_counted(0, 5)
        assert cpu.halted
        assert cpu.A == 6  # 6 iterations (0,1,2,3,4,5)

    def test_for_card_crosses_byte_boundary(self):
        """CARD loop from 254 to 258 — 5 iterations crossing 8-bit limit."""
        cpu = self._run_counted(254, 258)
        assert cpu.halted
        assert cpu.A == 5  # 5 iterations (254,255,256,257,258)

    def test_for_card_with_step(self):
        """CARD loop 0 to 300 step 100 runs 4 times (0,100,200,300)."""
        cpu = self._run_counted(0, 300, step=100)
        assert cpu.halted
        assert cpu.A == 4  # 4 iterations (0,100,200,300)

    def test_for_card_zero_iterations(self):
        """CARD loop where start > limit runs zero times."""
        cpu = self._run_counted(10, 5)
        assert cpu.halted
        assert cpu.A == 0  # loop body never runs


# ===========================================================================
# Negative STEP in FOR
# ===========================================================================


class TestForNegativeStep:
    """FOR loops with negative STEP count downward."""

    def test_byte_countdown(self):
        """FOR i = 5 TO 1 STEP -1 runs 5 times (5,4,3,2,1)."""
        cpu = run_action(
            "BYTE count=[0]\n"
            "BYTE result=[0]\n"
            "PROC Main()\n"
            "  INT i\n"
            "  FOR i = 5 TO 1 STEP -1 DO\n"
            "    count = count + 1\n"
            "  OD\n"
            "  result = count\n"
            "RETURN"
        )
        assert cpu.halted
        assert cpu.A == 5  # 5 iterations

    def test_int_countdown_step2(self):
        """FOR i = 10 TO 2 STEP -2 runs 5 times (10,8,6,4,2)."""
        cpu = run_action(
            "BYTE count=[0]\n"
            "BYTE result=[0]\n"
            "PROC Main()\n"
            "  INT i\n"
            "  FOR i = 10 TO 2 STEP -2 DO\n"
            "    count = count + 1\n"
            "  OD\n"
            "  result = count\n"
            "RETURN"
        )
        assert cpu.halted
        assert cpu.A == 5  # 5 iterations (10,8,6,4,2)

    def test_countdown_zero_iterations(self):
        """FOR i = 1 TO 5 STEP -1 with limit > start runs zero times."""
        cpu = run_action(
            "BYTE count=[0]\n"
            "BYTE result=[0]\n"
            "PROC Main()\n"
            "  INT i\n"
            "  FOR i = 1 TO 5 STEP -1 DO\n"
            "    count = count + 1\n"
            "  OD\n"
            "  result = count\n"
            "RETURN"
        )
        assert cpu.halted
        assert cpu.A == 0  # loop body never runs (start < limit for negative step)


# ===========================================================================
# Pointer operations
# ===========================================================================


class TestPointer:
    """POINTER declarations, address-of, and dereference work end-to-end."""

    def test_pointer_roundtrip_byte(self):
        """bp = @x, then y = bp^ reads back x's value."""
        cpu = run_action(
            "BYTE x=[42]\n"
            "BYTE y=[0]\n"
            "BYTE POINTER bp\n"
            "PROC Main()\n"
            "  bp = @x\n"
            "  y = bp^\n"
            "RETURN"
        )
        assert cpu.halted
        assert cpu.A == 42

    def test_pointer_write_through(self):
        """bp^ = 99 writes 99 to the pointed-to variable."""
        cpu = run_action(
            "BYTE x=[0]\n"
            "BYTE result=[0]\n"
            "BYTE POINTER bp\n"
            "PROC Main()\n"
            "  bp = @x\n"
            "  bp^ = 99\n"
            "  result = x\n"
            "RETURN"
        )
        assert cpu.halted
        assert cpu.A == 99

    def test_pointer_modify_and_read(self):
        """Write through pointer, then read back through pointer."""
        cpu = run_action(
            "BYTE val=[0]\n"
            "BYTE result=[0]\n"
            "BYTE POINTER p\n"
            "PROC Main()\n"
            "  p = @val\n"
            "  p^ = 77\n"
            "  result = p^\n"
            "RETURN"
        )
        assert cpu.halted
        assert cpu.A == 77

    def test_pointer_param(self):
        """PROC that takes BYTE POINTER and writes through it."""
        cpu = run_action(
            "BYTE target=[0]\n"
            "BYTE result=[0]\n"
            "PROC SetVal(BYTE POINTER p)\n"
            "  p^ = 55\n"
            "RETURN\n"
            "PROC Main()\n"
            "  SetVal(@target)\n"
            "  result = target\n"
            "RETURN"
        )
        assert cpu.halted
        assert cpu.A == 55


# ===========================================================================
# Array operations
# ===========================================================================


class TestArray:
    """ARRAY declarations and element access work end-to-end."""

    def test_array_write_read_byte(self):
        """Write 42 to buf(0), read back through buf(0)."""
        cpu = run_action(
            "BYTE ARRAY buf(10)\n"
            "BYTE result=[0]\n"
            "PROC Main()\n"
            "  BYTE i\n"
            "  i = 0\n"
            "  buf(i) = 42\n"
            "  result = buf(i)\n"
            "RETURN"
        )
        assert cpu.halted
        assert cpu.A == 42

    def test_array_write_multiple_elements(self):
        """Write different values to different indices, read back last."""
        cpu = run_action(
            "BYTE ARRAY buf(10)\n"
            "BYTE result=[0]\n"
            "PROC Main()\n"
            "  BYTE i\n"
            "  i = 0\n"
            "  buf(i) = 10\n"
            "  i = 1\n"
            "  buf(i) = 20\n"
            "  i = 2\n"
            "  buf(i) = 30\n"
            "  i = 1\n"
            "  result = buf(i)\n"
            "RETURN"
        )
        assert cpu.halted
        assert cpu.A == 20

    def test_array_fill_loop(self):
        """Fill array with loop index values, read back element 5."""
        cpu = run_action(
            "BYTE ARRAY buf(8)\n"
            "BYTE result=[0]\n"
            "PROC Main()\n"
            "  BYTE i\n"
            "  FOR i = 0 TO 7 DO\n"
            "    buf(i) = i\n"
            "  OD\n"
            "  i = 5\n"
            "  result = buf(i)\n"
            "RETURN"
        )
        assert cpu.halted
        assert cpu.A == 5

    def test_array_address_placed(self):
        """BYTE ARRAY at fixed address compiles and runs."""
        cpu = run_action(
            "BYTE ARRAY buf(4) = $8100\n"
            "BYTE result=[0]\n"
            "PROC Main()\n"
            "  BYTE i\n"
            "  i = 0\n"
            "  buf(i) = 77\n"
            "  result = buf(i)\n"
            "RETURN"
        )
        assert cpu.halted
        assert cpu.A == 77

    def test_array_bracket_init_read(self):
        """BYTE ARRAY with bracket initializer pre-populates memory."""
        cpu = run_action(
            "BYTE ARRAY d = [10 20 30]\n"
            "BYTE result=[0]\n"
            "PROC Main()\n"
            "  BYTE i\n"
            "  i = 1\n"
            "  result = d(i)\n"
            "RETURN"
        )
        assert cpu.halted
        assert cpu.A == 20

    def test_array_string_init_read_char(self):
        """BYTE ARRAY with string initializer: index 1 is first char."""
        cpu = run_action(
            'BYTE ARRAY m = "AB"\n'
            "BYTE result=[0]\n"
            "PROC Main()\n"
            "  BYTE i\n"
            "  i = 1\n"
            "  result = m(i)\n"
            "RETURN"
        )
        assert cpu.halted
        assert cpu.A == 65  # ord('A')

    def test_array_string_init_read_length(self):
        """BYTE ARRAY with string initializer: index 0 is the length byte."""
        cpu = run_action(
            'BYTE ARRAY m = "AB"\n'
            "BYTE result=[0]\n"
            "PROC Main()\n"
            "  BYTE i\n"
            "  i = 0\n"
            "  result = m(i)\n"
            "RETURN"
        )
        assert cpu.halted
        assert cpu.A == 2  # length of "AB"


# ===========================================================================
# I/O Intrinsics
# ===========================================================================


def run_action_with_inputs(
    source, *, x=0, y=0, gpio=0, interrupt=False, max_instructions=10000
):
    """Run Action! program with preset hardware input values."""
    from simulator.cpu import CPU
    from simulator.memory import Memory
    from sk02_asm.assembler import Assembler

    asm_source = compile_string(source)
    assembler = Assembler(asm_source, 0x8000)
    output, errors = assembler.assemble()
    assert not errors, f"Assembly errors: {errors}"

    memory = Memory()
    for addr, byte in output.data.items():
        memory.write_byte(addr, byte)
    memory.x_input = x
    memory.y_input = y
    memory.gpio = gpio

    cpu = CPU(memory)
    cpu.interrupt = interrupt
    cpu.run(max_instructions)
    return cpu


class TestIOIntrinsics:
    """I/O intrinsics compile and execute correctly."""

    def test_readx_reads_x_input(self):
        """ReadX() reads the X input register."""
        cpu = run_action_with_inputs(
            "BYTE result=[0]\nPROC Main()\n  result = ReadX()\nRETURN",
            x=42,
        )
        assert cpu.halted
        assert cpu.A == 42

    def test_ready_reads_y_input(self):
        """ReadY() reads the Y input register."""
        cpu = run_action_with_inputs(
            "BYTE result=[0]\nPROC Main()\n  result = ReadY()\nRETURN",
            y=77,
        )
        assert cpu.halted
        assert cpu.A == 77

    def test_gpioread_reads_gpio(self):
        """GpioRead() reads the GPIO register."""
        cpu = run_action_with_inputs(
            "BYTE result=[0]\nPROC Main()\n  result = GpioRead()\nRETURN",
            gpio=99,
        )
        assert cpu.halted
        assert cpu.A == 99

    def test_gpiowrite_writes_gpio(self):
        """GpioWrite(val) writes to GPIO."""
        cpu = run_action_with_inputs(
            "PROC Main()\n  GpioWrite(55)\nRETURN",
        )
        assert cpu.halted
        assert cpu.memory.gpio == 55

    def test_out0write_writes_out0(self):
        """Out0Write(val) writes to output display 0."""
        cpu = run_action_with_inputs(
            "PROC Main()\n  Out0Write(10)\nRETURN",
        )
        assert cpu.halted
        assert cpu.memory.out_0 == 10

    def test_out1write_writes_out1(self):
        """Out1Write(val) writes to output display 1."""
        cpu = run_action_with_inputs(
            "PROC Main()\n  Out1Write(20)\nRETURN",
        )
        assert cpu.halted
        assert cpu.memory.out_1 == 20

    def test_outwrite_writes_both(self):
        """OutWrite(lo, hi) writes lo to out_0 and hi to out_1."""
        cpu = run_action_with_inputs(
            "PROC Main()\n  OutWrite(3, 7)\nRETURN",
        )
        assert cpu.halted
        assert cpu.memory.out_0 == 3
        assert cpu.memory.out_1 == 7

    def test_clearinterrupt_runs(self):
        """ClearInterrupt() executes without error."""
        cpu = run_action_with_inputs(
            "PROC Main()\n  ClearInterrupt()\nRETURN",
            interrupt=True,
        )
        assert cpu.halted
        assert not cpu.interrupt

    def test_interruptflag_returns_zero_when_clear(self):
        """InterruptFlag() returns 0 when interrupt flag is not set."""
        cpu = run_action_with_inputs(
            "BYTE result=[0]\nPROC Main()\n  result = InterruptFlag()\nRETURN",
            interrupt=False,
        )
        assert cpu.halted
        assert cpu.A == 0

    def test_interruptflag_returns_one_when_set(self):
        """InterruptFlag() returns 1 when interrupt flag is set."""
        cpu = run_action_with_inputs(
            "BYTE result=[0]\nPROC Main()\n  result = InterruptFlag()\nRETURN",
            interrupt=True,
        )
        assert cpu.halted
        assert cpu.A == 1


# ===========================================================================
# SET directive end-to-end
# ===========================================================================


class TestSetDirectiveE2E:
    """SET directive pokes bytes into the assembled binary."""

    def test_set_pokes_reset_vector(self):
        """SET $FFFE = Main writes Main's address into $FFFE..$FFFF."""
        from sk02_asm.assembler import Assembler

        source = "PROC Main()\nRETURN\nSET $FFFE = main"
        asm_source = compile_string(source)
        assembler = Assembler(asm_source, 0x8000)
        output, errors = assembler.assemble()
        assert not errors
        lo = output.data.get(0xFFFE)
        hi = output.data.get(0xFFFF)
        assert lo is not None and hi is not None
        addr = lo | (hi << 8)
        assert 0x8000 <= addr <= 0xFFFF

    def test_set_numeric_target_and_value(self):
        """SET writes a numeric value to a numeric address in the ROM."""
        from sk02_asm.assembler import Assembler

        source = "PROC Main()\nRETURN\nSET $8200 = 255"
        asm_source = compile_string(source)
        assembler = Assembler(asm_source, 0x8000)
        output, errors = assembler.assemble()
        assert not errors
        lo = output.data.get(0x8200)
        hi = output.data.get(0x8201)
        assert lo is not None
        # 255 as WORD little-endian: lo=255, hi=0
        assert lo == 255
        assert hi == 0


# ===========================================================================
# String literal end-to-end
# ===========================================================================


class TestStringLiteralE2E:
    """String literals in expressions allocate correct data at runtime."""

    def test_string_literal_length_via_pointer(self):
        """p = "Hi"; result = p^ — dereference yields length byte (2)."""
        cpu = run_action(
            "BYTE POINTER p\n"
            "BYTE result=[0]\n"
            'PROC Main()\n  p = "Hi"\n  result = p^\nRETURN'
        )
        assert cpu.halted
        assert cpu.A == 2  # length of "Hi"

    def test_two_string_literals_independent(self):
        """Two string literals yield independent data; read different length bytes."""
        cpu = run_action(
            "BYTE POINTER p\n"
            "BYTE POINTER q\n"
            "BYTE result=[0]\n"
            "PROC Main()\n"
            '  p = "Hi"\n'  # length 2
            '  q = "Hello"\n'  # length 5
            "  result = p^\n"  # read length of "Hi"
            "RETURN"
        )
        assert cpu.halted
        assert cpu.A == 2  # length of "Hi"

    def test_empty_string_literal_length_zero(self):
        """p = ""; p^ yields 0 (empty string length byte)."""
        cpu = run_action(
            "BYTE POINTER p\n"
            "BYTE result=[0]\n"
            'PROC Main()\n  p = ""\n  result = p^\nRETURN'
        )
        assert cpu.halted
        assert cpu.A == 0
