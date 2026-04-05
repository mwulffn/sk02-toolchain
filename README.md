# SK-02 Toolchain

En samlet udviklingsvaerktoejskasse til [SK-02 8-bit computeren](https://soerko.dk/CPU_mark2/mark2.html) -- en hjemmebygget 8-bit CPU med custom instruktionssaet.

Toolchainen bestaar af:

- **Assembler** -- fuldt funktionel to-pass assembler med makro- og include-support
- **C-compiler** -- eksperimentel compiler fra et C-subset til SK-02 assembly
- **Simulator** -- CPU-simulator med tekst- og TUI-debugger
- **Standardbibliotek** -- 16 makroer porteret fra den originale Perl-assembler

## Installation

```bash
uv sync
```

Kraever Python 3.13+.

---

## Assembler

**Status: Stabil.** 210 opcodes, 6 direktiver, fuld makro/include-support. Testet med 83 unit tests.

Assembleren er en to-pass assembler der haandterer:
- Alle 210 SK-02 opcodes (simple, immediate og adresse-instruktioner)
- Lokale labels med scoping (`.label` under naermeste globale label)
- Forward references (labels der bruges foer de er defineret)
- `.INCLUDE` med soegesti og cyklus-detektion
- `.MACRO` / `.ENDM` med `\@`-taeller til unikke labels
- Rekursiv makro-expansion (makroer der kalder makroer)
- Tal-formater: `$hex`, `%binaer`, decimal, `'char'`
- Output i binaer- og Intel HEX-format

**Begraensninger:** Ingen aritmetiske udtryk i operander (f.eks. `LABEL+1`), ingen `.DS`/`.SPACE`-direktiv, makroer tager ikke parametre.

### Brug

```bash
# Assembler til binaer
uv run sk02-asm program.asm -o program.bin

# Med include-sti til standardbiblioteket
uv run sk02-asm program.asm -I lib -o program.bin

# Intel HEX format
uv run sk02-asm program.asm -f hex -o program.hex

# Generer listing-fil
uv run sk02-asm program.asm -l program.lst

# Saet origin-adresse (standard: $8000)
uv run sk02-asm program.asm --org 0x9000
```

### Eksempel

```asm
    .INCLUDE "stdlib.asm"

    .ORG $8000
START:
    SET_AB #6       ; A=6, B=0
    SET_CD #7       ; C=7, D=0
    AB_MULT_CD      ; AB = 6 * 7 = 42
    AB>OUT          ; Vis resultat paa 7-segment display
    HALT
```

```bash
uv run sk02-asm multiply.asm -I lib -o multiply.bin
```

---

## Simulator

**Status: Fungerer.** Alle 210 opcodes implementeret (hardware-interrupts er stubbet som no-ops). Tre tilstande: batch, interaktiv tekst og TUI-debugger.

### Batch-tilstand

Koerer programmet og viser sluttilstand:

```bash
uv run python -m simulator program.bin --run
```

```
Loaded 48 bytes from program.bin at $8000
Starting execution...
CPU halted
Executed 230 instructions

Final state:
PC: $8030  RSP: 00  DSP: 00  Flags: Z=1 O=0 I=0
A=$2A B=$00 C=$00 D=$00 E=$00 F=$00 G=$00 H=$00
OUT_0: $2A
```

### Interaktiv debugger

```bash
uv run python -m simulator program.bin
```

Kommandoer: `step [n]`, `run`, `break <addr>`, `clear <addr>`, `regs`, `mem <addr> [len]`, `disasm <addr> [n]`, `set <reg> <val>`, `io`, `reset`, `help`, `quit`.

### TUI-debugger

**Status: Ny, grundlaeggende funktionalitet paa plads.** Kraever `textual`.

```bash
uv run python -m simulator program.bin --tui
```

Funktioner:
- Disassembly-visning med PC-markering og breakpoints
- Register-panel med aendringer fremhaevet i rodt
- I/O-panel (OUT_0, OUT_1, GPIO, X, Y)
- Stak-visning (top 8 entries)
- Memory hex-viewer med inline redigering
- F5 Run, F10 Step Over (springer over GOSUB), F11 Step Into, F9 Breakpoint
- Ctrl+G Gaa til adresse, Ctrl+R Reset, Ctrl+L Indlaes fil

**Begraensninger:** Hardware-interrupts er ikke simuleret. Opcode-opslag genopbygges per instruktion i koeretiden (ydelsesproblem ved lange programmer).

### Genvejsscript

```bash
./sk02-sim program.bin --run     # Batch
./sk02-sim program.bin           # Interaktiv
./sk02-sim program.bin --tui     # TUI-debugger
```

---

## C-compiler

**Status: Eksperimentel.** Grundlaeggende programmer virker (aritmetik, if/else, while, for), men mange C-features mangler eller er fejlbehaefiede. Ingen tests. Brug med forsigtighed.

Compileren oversaetter et C-subset til SK-02 assembly:

```bash
uv run sk02cc program.c -o program.asm
```

### Hvad virker

- Typer: `char` (8-bit), `int` (16-bit)
- Operatorer: `+`, `-`, `&`, `|`, `^`, `<<`, `>>`, `==`, `!=`, `<`, `>`, `<=`, `>=`
- Unaere: `-`, `!`, `~`, `++`, `--` (praefix og postfiks)
- Kontrolflow: `if`/`else`, `while`, `for`, `break`, `continue`, `return`
- Funktioner med op til 2 parametre (ikke-rekursive)
- Globale variable

### Hvad mangler eller er i stykker

- **Ingen multiplikation/division/modulo** (`*`, `/`, `%`) -- compiler crasher
- **Ingen logisk AND/OR** (`&&`, `||`) -- compiler crasher
- **Ingen pointer-dereference eller address-of** (`*ptr`, `&var`) -- compiler crasher
- **Ingen array-adgang** (`arr[i]`) -- compiler crasher
- **Compound assignments er forkerte** (`+=`, `-=` etc.) -- compilerer stille og roligt forkert kode
- **Sammenligningsoperatorer kan give forkerte resultater** for `<` og `>`
- **Ingen rekursion** -- lokale variable bruger statisk lager
- **Ingen C-praprocessor** (`#include`, `#define`)
- **Ingen structs, unions, enums, do-while, switch/case**

### Eksempel

```c
void delay() {
    int i = 1000;
    while (i > 0) {
        i = i - 1;
    }
}

void main() {
    char x = 42;
    char y = 10;
    char result = x + y;
}
```

```bash
uv run sk02cc program.c -o program.asm
uv run sk02-asm program.asm -o program.bin
uv run python -m simulator program.bin --run
```

Eller brug build-scriptet:

```bash
./sk02-build program.c
```

---

## Standardbibliotek

**Status: Porteret fra original Perl-assembler.** 16 makroer i `lib/stdlib.asm`. Bruges med `.INCLUDE "stdlib.asm"` og `-I lib`.

| Makro | Beskrivelse |
|---|---|
| `INPUT_AB` | Laes X/Y-input til A/B, vis paa display, vent paa interrupt |
| `WAIT_INTERUPT` | Vent paa hardware-interrupt |
| `GETCHAR` | Hent numpad-input (4-bit) til A |
| `INIT_DISPLAY` | Initialiser LCD-display |
| `RESET_DISPLAY` | Ryd LCD-display |
| `PRINT_BUFFER` | Udskriv null-termineret streng fra AB til LCD |
| `ABX10` | Gang AB med 10 via shifts |
| `AB_MULT_CD` | 16-bit multiplikation: AB = AB * CD |
| `AB_DIV_CD` | 16-bit division: AB = AB / CD, rest i CD |
| `MEMCOPY` | Kopier null-termineret streng fra AB til CD |
| `MEMCOPY_APPEND` | Tilfoej streng til eksisterende buffer |
| `MEMSET` | Udfyld hukommelse: AB=adresse, C=vaerdi, D=laengde |
| `NUMBER_TO_BUFF` | 16-bit tal til 5-cifret decimal-streng |
| `SHORT_TO_BUFF` | 8-bit tal til 3-cifret decimal-streng |
| `INT_TO_BUFF_SIGN` | Signeret 16-bit til decimal med +/- fortegn |
| `SHORT_TO_BUFF_SIGN` | Signeret 8-bit til decimal med +/- fortegn |

**Bemærk:** Float-formateringsmakroer (`FLOAT_TO_BUFF`, `FLOAT_TO_BUFF_MANTISSA`, `NORMALISE_FLOAT`) er ogsaa inkluderet men udokumenterede her.

---

## Eksempler

Assembly-eksempler i `examples/`:

| Fil | Beskrivelse |
|---|---|
| `simple.asm` | Tael fra 0 til 10, vis paa OUT_0 |
| `macros_test.asm` | 6*7 med `AB_MULT_CD` fra stdlib |
| `nested_macros_test.asm` | Test af nestede makroer (`GETCHAR` kalder `WAIT_INTERUPT`) |
| `comprehensive_test.asm` | Omfattende test: registre, aritmetik, logik, stak, hukommelse, subrutiner |
| `directives.asm` | Test af assembler-direktiver |

C-eksempler:

| Fil | Beskrivelse |
|---|---|
| `hello.c` | LED-blinker med delay-funktion |
| `arithmetic.c` | Aritmetik og bitwise operationer |
| `loops.c` | For/while-loekker |
| `conditionals.c` | If/else og sammenligninger |

---

## Test

```bash
uv run pytest tests/ -v
```

83 tests daekker assembleren (opcodes, labels, direktiver, makroer, preprocessor, symboler, lexer). Compileren og simulatoren har endnu ingen tests.

---

## Projektstruktur

```
sk02/
  src/
    sk02_asm/     -- Assembler (lexer, parser, preprocessor, codegen)
    sk02cc/       -- C-compiler (lexer, parser, AST, codegen)
  simulator/      -- CPU-simulator (cpu, memory, opcodes, text-ui, tui)
  lib/            -- Standardbibliotek (stdlib.asm)
  examples/       -- Eksempelprogrammer
  tests/          -- Unit tests
  docs/           -- Dokumentation
  sk02-sim        -- Genvej til simulator
  sk02-build      -- C-til-binaer build-script
  bin2sim         -- Konverter .bin til simulator-tekstformat
```

## Licens

Se LICENSE-filen for detaljer.
