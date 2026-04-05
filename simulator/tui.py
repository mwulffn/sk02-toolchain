"""Textual-based TUI debugger for the SK-02 simulator."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Footer, Input, Label, Static

from sk02_asm.opcodes import OPCODES, OperandType

from .cpu import CPU
from .memory import Memory

# ---------------------------------------------------------------------------
# Cached opcode map (avoids rebuilding on every instruction in opcodes.py)
# ---------------------------------------------------------------------------
OPCODE_MAP: dict[int, tuple[str, object]] = {
    op.value: (name, op) for name, op in OPCODES.items()
}

# Opcodes that call subroutines (for step-over logic)
GOSUB_OPCODE = OPCODES["GOSUB"].value        # 32 — 3-byte instruction
GOSUB_COMP_OPCODE = OPCODES["GOSUB_COMP"].value  # 125 — 1-byte instruction


@dataclass
class DisasmLine:
    address: int
    text: str       # formatted disassembly text
    size: int       # instruction size in bytes


def tui_disassemble(memory: Memory, start: int, count: int) -> list[DisasmLine]:
    """Disassemble `count` instructions starting at `start` using cached map."""
    lines: list[DisasmLine] = []
    addr = start & 0xFFFF
    for _ in range(count):
        byte = memory.read_byte(addr)
        if byte in OPCODE_MAP:
            name, opcode = OPCODE_MAP[byte]
            if opcode.operand == OperandType.NONE:
                lines.append(DisasmLine(addr, f"${addr:04X}  {name}", 1))
                addr = (addr + 1) & 0xFFFF
            elif opcode.operand == OperandType.IMM8:
                operand = memory.read_byte((addr + 1) & 0xFFFF)
                lines.append(DisasmLine(addr, f"${addr:04X}  {name:<12} #${operand:02X}", 2))
                addr = (addr + 2) & 0xFFFF
            else:  # IMM16 or ADDR16
                lo = memory.read_byte((addr + 1) & 0xFFFF)
                hi = memory.read_byte((addr + 2) & 0xFFFF)
                operand = lo | (hi << 8)
                lines.append(DisasmLine(addr, f"${addr:04X}  {name:<12} ${operand:04X}", 3))
                addr = (addr + 3) & 0xFFFF
        else:
            lines.append(DisasmLine(addr, f"${addr:04X}  DB           ${byte:02X}", 1))
            addr = (addr + 1) & 0xFFFF
    return lines


def snapshot(cpu: CPU) -> dict:
    """Capture all CPU state into a plain dict."""
    return {
        "A": cpu.A, "B": cpu.B, "C": cpu.C, "D": cpu.D,
        "E": cpu.E, "F": cpu.F, "G": cpu.G, "H": cpu.H,
        "AB": cpu.AB, "CD": cpu.CD, "EF": cpu.EF, "GH": cpu.GH,
        "PC": cpu.PC,
        "Z": int(cpu.zero), "O": int(cpu.overflow), "I": int(cpu.interrupt),
        "RSP": cpu.return_sp, "DSP": cpu.data_sp,
        "count": cpu.instruction_count,
        "halted": cpu.halted,
        "out_0": cpu.memory.out_0, "out_1": cpu.memory.out_1,
        "gpio": cpu.memory.gpio,
        "x_input": cpu.memory.x_input, "y_input": cpu.memory.y_input,
    }


# ---------------------------------------------------------------------------
# Modal screens
# ---------------------------------------------------------------------------

class GoToAddressScreen(ModalScreen):
    """Dialog to enter a hex address."""

    BINDINGS = [Binding("escape", "dismiss(None)", "Cancel")]

    def __init__(self, title: str = "Go to address") -> None:
        super().__init__()
        self._title = title

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(self._title, id="dialog-title")
            yield Input(placeholder="$8000 or 32768", id="addr-input")
            yield Label("Enter hex ($XXXX), or decimal. Esc to cancel.", id="dialog-hint")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        try:
            if raw.startswith("$"):
                addr = int(raw[1:], 16)
            elif raw.startswith("0x") or raw.startswith("0X"):
                addr = int(raw, 0)
            else:
                addr = int(raw)
            addr &= 0xFFFF
            self.dismiss(addr)
        except ValueError:
            self.query_one("#dialog-hint", Label).update(
                f"[red]Invalid address: {raw!r}[/red]"
            )


class LoadFileScreen(ModalScreen):
    """Dialog to enter a file path."""

    BINDINGS = [Binding("escape", "dismiss(None)", "Cancel")]

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("Load binary file", id="dialog-title")
            yield Input(placeholder="path/to/program.bin", id="file-input")
            yield Label("Enter path to binary. Esc to cancel.", id="dialog-hint")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        path = event.value.strip()
        if path:
            self.dismiss(path)
        else:
            self.dismiss(None)


# ---------------------------------------------------------------------------
# Widgets
# ---------------------------------------------------------------------------

class RegistersPanel(Static):
    """Displays all CPU registers and flags; highlights changed values."""

    def __init__(self, **kwargs) -> None:
        super().__init__("", **kwargs)
        self._prev: dict = {}

    def refresh_state(self, snap: dict) -> None:
        prev = self._prev

        def fmt(key: str, fmtstr: str, width: int = 2) -> str:
            val = snap[key]
            formatted = fmtstr.format(val)
            if prev and prev.get(key) != val:
                return f"[bold red]{formatted}[/bold red]"
            return formatted

        def r8(k: str) -> str:
            return fmt(k, "${:02X}")

        def r16(k: str) -> str:
            return fmt(k, "${:04X}")

        def flag(k: str) -> str:
            return fmt(k, "{}")

        lines = [
            "─── Registers ───────────",
            f" A ={r8('A')}  B ={r8('B')}  C ={r8('C')}  D ={r8('D')}",
            f" E ={r8('E')}  F ={r8('F')}  G ={r8('G')}  H ={r8('H')}",
            "─────────────────────────",
            f" AB={r16('AB')}    CD={r16('CD')}",
            f" EF={r16('EF')}    GH={r16('GH')}",
            "─────────────────────────",
            f" PC={r16('PC')}",
            f" Z={flag('Z')}  O={flag('O')}  I={flag('I')}",
            f" RSP={fmt('RSP', '{:02X}')}  DSP={fmt('DSP', '{:02X}')}",
            "─────────────────────────",
            f" Insns: {snap['count']}",
        ]
        self.update("\n".join(lines))
        self._prev = dict(snap)


class IOPanel(Static):
    """Displays I/O register values."""

    def __init__(self, **kwargs) -> None:
        super().__init__("", **kwargs)

    def refresh_state(self, snap: dict) -> None:
        lines = [
            "─── I/O ─────────────────",
            f" OUT_0 = ${snap['out_0']:02X}  ({snap['out_0']:3d})",
            f" OUT_1 = ${snap['out_1']:02X}  ({snap['out_1']:3d})",
            f" GPIO  = ${snap['gpio']:02X}  ({snap['gpio']:3d})",
            "─────────────────────────",
            f" X     = ${snap['x_input']:02X}  ({snap['x_input']:3d})",
            f" Y     = ${snap['y_input']:02X}  ({snap['y_input']:3d})",
        ]
        self.update("\n".join(lines))


class StackPanel(Static):
    """Shows the top entries of the data stack."""

    def __init__(self, **kwargs) -> None:
        super().__init__("", **kwargs)

    def refresh_state(self, cpu: CPU) -> None:
        lines = ["─── Stack ───────────────"]
        if cpu.data_sp == 0:
            lines.append(" (empty)")
        else:
            count = min(cpu.data_sp, 8)
            for i in range(count - 1, -1, -1):
                idx = (cpu.data_sp - 1 - i) & 0xFF
                val = cpu.data_stack[idx]
                marker = " ◄" if i == 0 else "  "
                lines.append(f" [{cpu.data_sp - 1 - i:3d}] ${val:02X}{marker}")
        self.update("\n".join(lines))


class DisassemblyView(ScrollableContainer, can_focus=True):
    """Scrollable disassembly around PC with cursor and breakpoint markers."""

    BINDINGS = [
        Binding("up", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("f9", "toggle_breakpoint", "Breakpoint", show=False),
    ]

    cursor_index: reactive[int] = reactive(0)

    def __init__(self, breakpoints: set, **kwargs) -> None:
        super().__init__(**kwargs)
        self._breakpoints = breakpoints
        self._lines: list[DisasmLine] = []
        self._pc_index: int = 0

    class ToggleBreakpoint(Message):
        def __init__(self, address: int) -> None:
            super().__init__()
            self.address = address

    def refresh_disasm(self, memory: Memory, pc: int) -> None:
        """Disassemble ~48 instructions centred on PC and rebuild children."""
        # Start ~16 instructions before PC
        back_addr = max(0, pc - 48)
        # We can't cheaply reverse-decode, so just start a bit before and scan forward
        # to find PC — disassemble from back_addr until we pass pc
        lines = tui_disassemble(memory, back_addr, 80)

        # Find pc index
        pc_idx = 0
        for i, line in enumerate(lines):
            if line.address == pc:
                pc_idx = i
                break

        # Keep a window of ~40 lines around pc
        start = max(0, pc_idx - 10)
        self._lines = lines[start:start + 40]
        self._pc_index = pc_idx - start
        self.cursor_index = self._pc_index
        self._rebuild()

    def _rebuild(self) -> None:
        self.remove_children()
        for i, line in enumerate(self._lines):
            bp = line.address in self._breakpoints
            is_pc = i == self._pc_index
            is_cursor = i == self.cursor_index

            if is_pc:
                prefix = "►"
            elif bp:
                prefix = "●"
            else:
                prefix = " "

            text = f" {prefix} {line.text}"

            classes = "disasm-line"
            if is_pc:
                classes += " pc-line"
            if bp:
                classes += " bp-line"
            if is_cursor and not is_pc:
                classes += " cursor-line"

            lbl = Label(text, classes=classes)
            lbl.styles.width = "100%"
            self.mount(lbl)

        # Scroll cursor into view
        if self._lines:
            target = min(self.cursor_index, len(self._lines) - 1)
            self.scroll_to_widget(list(self.query("Label").results(Label))[target])

    def action_cursor_up(self) -> None:
        if self.cursor_index > 0:
            self.cursor_index -= 1
            self._rebuild()

    def action_cursor_down(self) -> None:
        if self.cursor_index < len(self._lines) - 1:
            self.cursor_index += 1
            self._rebuild()

    def action_toggle_breakpoint(self) -> None:
        if self._lines and 0 <= self.cursor_index < len(self._lines):
            addr = self._lines[self.cursor_index].address
            self.post_message(self.ToggleBreakpoint(addr))

    def selected_address(self) -> int | None:
        if self._lines and 0 <= self.cursor_index < len(self._lines):
            return self._lines[self.cursor_index].address
        return None

    def goto_address(self, memory: Memory, addr: int) -> None:
        lines = tui_disassemble(memory, addr, 40)
        self._lines = lines
        self._pc_index = -1  # no pc marker (user navigated away)
        self.cursor_index = 0
        self._rebuild()


class MemoryView(ScrollableContainer, can_focus=True):
    """Scrollable hex+ASCII memory viewer with inline byte editing."""

    BINDINGS = [
        Binding("up", "scroll_up_row", "Up", show=False),
        Binding("down", "scroll_down_row", "Down", show=False),
        Binding("pageup", "page_up", "PgUp", show=False),
        Binding("pagedown", "page_down", "PgDn", show=False),
    ]

    ROWS = 16
    COLS = 16

    def __init__(self, memory: Memory, **kwargs) -> None:
        super().__init__(**kwargs)
        self._memory = memory
        self._base = 0x8000
        self._edit_addr: int | None = None
        self._edit_nibble: str = ""

    def _render_row(self, row_addr: int) -> str:
        hex_bytes = []
        ascii_chars = []
        for col in range(self.COLS):
            addr = (row_addr + col) & 0xFFFF
            b = self._memory.read_byte(addr)
            is_edit = (self._edit_addr == addr)
            if is_edit:
                hex_bytes.append(f"[bold yellow]{self._edit_nibble}_[/bold yellow]")
            else:
                hex_bytes.append(f"{b:02X}")
            ascii_chars.append(chr(b) if 32 <= b < 127 else ".")

        hex_str = " ".join(hex_bytes)
        ascii_str = "".join(ascii_chars)
        return f"${row_addr:04X}  {hex_str}  {ascii_str}"

    def render_rows(self) -> None:
        self.remove_children()
        for r in range(self.ROWS):
            row_addr = (self._base + r * self.COLS) & 0xFFFF
            lbl = Label(self._render_row(row_addr), classes="mem-row")
            lbl.styles.width = "100%"
            self.mount(lbl)

    def action_scroll_up_row(self) -> None:
        self._base = max(0, self._base - self.COLS)
        self.render_rows()

    def action_scroll_down_row(self) -> None:
        self._base = min(0xFFFF - self.COLS * self.ROWS + 1, self._base + self.COLS)
        self.render_rows()

    def action_page_up(self) -> None:
        self._base = max(0, self._base - self.COLS * self.ROWS)
        self.render_rows()

    def action_page_down(self) -> None:
        self._base = min(0xFFFF - self.COLS * self.ROWS + 1, self._base + self.COLS * self.ROWS)
        self.render_rows()

    def goto_address(self, addr: int) -> None:
        self._base = addr & 0xFFF0  # align to 16
        self.render_rows()

    def on_key(self, event) -> None:
        """Handle hex digit input for editing."""
        key = event.key
        if key in "0123456789abcdefABCDEF" and self.has_focus:
            if self._edit_addr is None:
                # Begin editing at base
                self._edit_addr = self._base
                self._edit_nibble = key.upper()
            else:
                # Second nibble — commit byte
                byte_val = int(self._edit_nibble + key.upper(), 16)
                self._memory.write_byte(self._edit_addr, byte_val)
                self._edit_addr = (self._edit_addr + 1) & 0xFFFF
                self._edit_nibble = ""
                if self._edit_addr >= self._base + self.COLS * self.ROWS:
                    self._base = (self._base + self.COLS) & 0xFFFF
            self.render_rows()
            event.stop()
        elif key == "escape":
            self._edit_addr = None
            self._edit_nibble = ""
            self.render_rows()
            event.stop()


# ---------------------------------------------------------------------------
# Main App
# ---------------------------------------------------------------------------

class SK02Debugger(App):
    """SK-02 TUI Debugger."""

    CSS = """
    Screen {
        layout: vertical;
    }

    #main-area {
        height: 3fr;
        layout: horizontal;
    }

    #disasm-panel {
        width: 3fr;
        border: solid $primary-darken-2;
        border-title-color: $primary;
    }

    #right-col {
        width: 36;
        layout: vertical;
    }

    #registers {
        height: 3fr;
        border: solid $primary-darken-2;
        padding: 0 1;
    }

    #io-panel {
        height: auto;
        border: solid $primary-darken-2;
        padding: 0 1;
    }

    #stack-panel {
        height: auto;
        border: solid $primary-darken-2;
        padding: 0 1;
    }

    #memory-panel {
        height: 1fr;
        border: solid $primary-darken-2;
        border-title-color: $primary;
        padding: 0 1;
    }

    .disasm-line {
        color: $text;
    }

    .pc-line {
        background: $accent-darken-2;
        color: $text;
        text-style: bold;
    }

    .cursor-line {
        background: $primary-darken-3;
    }

    .bp-line {
        color: $error;
    }

    .mem-row {
        color: $text-muted;
    }

    #status-bar {
        height: 1;
        background: $primary-darken-2;
        color: $text;
        padding: 0 1;
    }

    #dialog {
        width: 50;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
        margin: 4 8;
    }

    #dialog-title {
        text-style: bold;
        margin-bottom: 1;
    }

    #dialog-hint {
        color: $text-muted;
        margin-top: 1;
    }
    """

    BINDINGS = [
        Binding("f5", "run_cpu", "Run", show=True),
        Binding("f10", "step_over", "Step Over", show=True),
        Binding("f11", "step_into", "Step Into", show=True),
        Binding("f9", "toggle_bp", "Breakpoint", show=True),
        Binding("ctrl+g", "goto_address", "Go To", show=True),
        Binding("ctrl+r", "reset_cpu", "Reset", show=True),
        Binding("ctrl+l", "load_file", "Load", show=True),
        Binding("ctrl+q", "quit", "Quit", show=True),
        Binding("escape", "stop_run", "Stop", show=False),
    ]

    status_text: reactive[str] = reactive("Ready")

    def __init__(self, binary: str | None = None, origin: int = 0x8000) -> None:
        super().__init__()
        self._binary = binary
        self._origin = origin
        self.memory = Memory()
        self.cpu = CPU(self.memory)
        self.breakpoints: set[int] = set()
        self._snap: dict = snapshot(self.cpu)
        self._stop_requested = False
        self._temp_breakpoints: set[int] = set()

    def compose(self) -> ComposeResult:
        with Horizontal(id="main-area"):
            disasm = DisassemblyView(self.breakpoints, id="disasm-panel")
            disasm.border_title = "Disassembly"
            yield disasm
            with Vertical(id="right-col"):
                yield RegistersPanel(id="registers")
                yield IOPanel(id="io-panel")
                yield StackPanel(id="stack-panel")
        mem = MemoryView(self.memory, id="memory-panel")
        mem.border_title = "Memory"
        yield mem
        yield Label("", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        if self._binary:
            self._load_binary(self._binary, self._origin)
        self._refresh_all()

    # --- Internal helpers ---------------------------------------------------

    def _load_binary(self, path: str, origin: int = 0x8000) -> None:
        try:
            data = Path(path).read_bytes()
            self.memory.load_binary(data, origin)
            self.cpu.reset()
            self.cpu.PC = origin
            self._snap = snapshot(self.cpu)
            self.status_text = f"Loaded {len(data)} bytes from {Path(path).name} at ${origin:04X}"
            self._refresh_all()
        except OSError as e:
            self.status_text = f"[red]Load error: {e}[/red]"

    def _refresh_all(self) -> None:
        snap = snapshot(self.cpu)

        self.query_one(RegistersPanel).refresh_state(snap)
        self.query_one(IOPanel).refresh_state(snap)
        self.query_one(StackPanel).refresh_state(self.cpu)

        disasm = self.query_one(DisassemblyView)
        disasm.refresh_disasm(self.memory, self.cpu.PC)
        disasm._breakpoints = self.breakpoints
        disasm._rebuild()

        mem = self.query_one(MemoryView)
        mem.render_rows()

        state = "HALTED" if self.cpu.halted else "RUNNING" if not self._stop_requested else "STOPPED"
        snap_prev = self._snap
        self._snap = snap
        self.query_one("#status-bar", Label).update(
            f" {state} | PC=${self.cpu.PC:04X} | {self.cpu.instruction_count} insns | "
            "F5 Run  F10 Step Over  F11 Step  F9 BP  Ctrl+G Goto  Ctrl+R Reset  Ctrl+L Load"
        )

    # --- Actions ------------------------------------------------------------

    def action_step_into(self) -> None:
        self._stop_requested = True
        if not self.cpu.halted:
            self.cpu.step()
        self._refresh_all()

    def action_step_over(self) -> None:
        self._stop_requested = True
        if self.cpu.halted:
            return
        opcode_byte = self.memory.read_byte(self.cpu.PC)
        if opcode_byte == GOSUB_OPCODE:
            # GOSUB is 3 bytes — step over means run to PC+3
            ret_addr = (self.cpu.PC + 3) & 0xFFFF
            self._temp_breakpoints.add(ret_addr)
            self._run_worker()
        elif opcode_byte == GOSUB_COMP_OPCODE:
            # GOSUB_COMP is 1 byte
            ret_addr = (self.cpu.PC + 1) & 0xFFFF
            self._temp_breakpoints.add(ret_addr)
            self._run_worker()
        else:
            self.cpu.step()
            self._refresh_all()

    def action_run_cpu(self) -> None:
        if self.cpu.halted:
            return
        self._stop_requested = False
        self._run_worker()

    def action_stop_run(self) -> None:
        self._stop_requested = True

    def action_toggle_bp(self) -> None:
        disasm = self.query_one(DisassemblyView)
        addr = disasm.selected_address()
        if addr is not None:
            if addr in self.breakpoints:
                self.breakpoints.discard(addr)
            else:
                self.breakpoints.add(addr)
            disasm._breakpoints = self.breakpoints
            disasm._rebuild()

    def action_reset_cpu(self) -> None:
        self._stop_requested = True
        self.cpu.reset()
        self._snap = snapshot(self.cpu)
        self._refresh_all()

    def action_goto_address(self) -> None:
        focused = self.focused

        def handle(addr: int | None) -> None:
            if addr is None:
                return
            if isinstance(focused, DisassemblyView):
                focused.goto_address(self.memory, addr)
            else:
                self.query_one(MemoryView).goto_address(addr)

        self.push_screen(GoToAddressScreen("Go to address"), handle)

    def action_load_file(self) -> None:
        def handle(path: str | None) -> None:
            if path:
                self._load_binary(path, self._origin)

        self.push_screen(LoadFileScreen(), handle)

    # --- Message handlers ---------------------------------------------------

    @on(DisassemblyView.ToggleBreakpoint)
    def on_toggle_breakpoint(self, event: DisassemblyView.ToggleBreakpoint) -> None:
        addr = event.address
        if addr in self.breakpoints:
            self.breakpoints.discard(addr)
        else:
            self.breakpoints.add(addr)
        disasm = self.query_one(DisassemblyView)
        disasm._breakpoints = self.breakpoints
        disasm._rebuild()

    # --- Worker for F5/step-over run ----------------------------------------

    class CpuStopped(Message):
        pass

    @work(thread=True)
    def _run_worker(self) -> None:
        """Execute instructions in a background thread, posting updates."""
        all_bp = self.breakpoints | self._temp_breakpoints
        batch = 500
        while not self._stop_requested and not self.cpu.halted:
            for _ in range(batch):
                if self._stop_requested or self.cpu.halted:
                    break
                self.cpu.step()
                if self.cpu.PC in all_bp:
                    self._temp_breakpoints.discard(self.cpu.PC)
                    self._stop_requested = True
                    break
        self.post_message(self.CpuStopped())

    @on(CpuStopped)
    def on_cpu_stopped(self) -> None:
        self._stop_requested = True
        self._refresh_all()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_tui(binary: str | None = None, origin: int = 0x8000) -> None:
    """Launch the TUI debugger."""
    app = SK02Debugger(binary=binary, origin=origin)
    app.run()
