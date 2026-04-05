"""Preprocessor for macro expansion and file inclusion."""

import re
from pathlib import Path

from .errors import AssemblyError


class PreprocessorError(AssemblyError):
    """Error during preprocessing."""

    pass


class Preprocessor:
    """Handles .INCLUDE and .MACRO/.ENDM expansion.

    Runs before the assembler's tokenization phase, operating on
    raw source lines.

    Macro bodies use \\@ as a unique expansion counter, replaced
    with 0, 1, 2, ... on each invocation to generate unique labels.
    """

    def __init__(self, include_paths: list[Path] | None = None):
        self.include_paths = list(include_paths or [])
        self.macros: dict[str, list[str]] = {}
        self.expansion_counter = 0
        self._included_files: set[str] = set()

    def process(self, source: str, source_file: Path | None = None) -> str:
        """Preprocess source: expand includes, collect macros, expand invocations."""
        if source_file:
            resolved = source_file.resolve()
            self.include_paths.insert(0, resolved.parent)
            self._included_files.add(str(resolved))

        lines = source.split("\n")
        lines = self._process_includes(lines)
        lines = self._collect_macros(lines)
        lines = self._expand_macros(lines)
        return "\n".join(lines)

    def _resolve_include(self, filename: str) -> Path | None:
        """Find an include file in the search paths."""
        for search_path in self.include_paths:
            candidate = search_path / filename
            if candidate.exists():
                return candidate
        return None

    def _process_includes(self, lines: list[str]) -> list[str]:
        """Expand .INCLUDE directives, with cycle detection."""
        result = []
        for line in lines:
            match = re.match(r'^\s*\.INCLUDE\s+"([^"]+)"', line, re.IGNORECASE)
            if match:
                filename = match.group(1)
                include_path = self._resolve_include(filename)
                if include_path is None:
                    raise PreprocessorError(f'Include file not found: "{filename}"')

                resolved = str(include_path.resolve())
                if resolved in self._included_files:
                    continue  # Already included — skip silently
                self._included_files.add(resolved)

                included_source = include_path.read_text()
                included_lines = included_source.split("\n")
                # Recurse for nested includes
                included_lines = self._process_includes(included_lines)
                result.extend(included_lines)
            else:
                result.append(line)
        return result

    def _collect_macros(self, lines: list[str]) -> list[str]:
        """Collect .MACRO/.ENDM definitions and remove them from the source."""
        result = []
        in_macro = False
        macro_name = None
        macro_body: list[str] = []

        for line in lines:
            stripped = line.strip()

            if not in_macro:
                match = re.match(r"^\s*\.MACRO\s+(\S+)", stripped, re.IGNORECASE)
                if match:
                    macro_name = match.group(1).upper()
                    macro_body = []
                    in_macro = True
                    continue
                result.append(line)
            else:
                if re.match(r"^\s*\.ENDM\b", stripped, re.IGNORECASE):
                    if macro_name in self.macros:
                        raise PreprocessorError(f"Duplicate macro: {macro_name}")
                    self.macros[macro_name] = macro_body
                    in_macro = False
                    macro_name = None
                    continue
                macro_body.append(line)

        if in_macro:
            raise PreprocessorError(f"Unterminated macro: {macro_name}")

        return result

    def _expand_macros(self, lines: list[str], depth: int = 0) -> list[str]:
        """Expand macro invocations, recursively for nested macros."""
        if depth > 100:
            raise PreprocessorError("Macro expansion depth limit exceeded (recursive?)")

        result = []
        changed = False

        for line in lines:
            stripped = line.strip()
            # Strip trailing comment for matching
            comment_pos = stripped.find(";")
            code = stripped[:comment_pos].strip() if comment_pos >= 0 else stripped

            if code.upper() in self.macros:
                body = self.macros[code.upper()]
                counter = self.expansion_counter
                self.expansion_counter += 1
                for body_line in body:
                    result.append(body_line.replace("\\@", str(counter)))
                changed = True
            else:
                result.append(line)

        # Re-expand if any macros were expanded (handles nested macros)
        if changed:
            result = self._expand_macros(result, depth + 1)

        return result
