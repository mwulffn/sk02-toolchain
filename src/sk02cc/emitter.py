"""Assembly output buffer and label generator for SK02-C codegen."""


class Emitter:
    """Buffers assembly lines and generates unique local labels."""

    def __init__(self):
        self._output: list[str] = []
        self._label_counter: int = 0

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    def emit(self, line: str) -> None:
        """Append a line to the output buffer."""
        self._output.append(line)

    def emit_comment(self, comment: str) -> None:
        """Append a comment line."""
        self._output.append(f"; {comment}")

    def get_output(self) -> str:
        """Return the assembled output as a single string."""
        return "\n".join(self._output)

    # ------------------------------------------------------------------
    # Labels
    # ------------------------------------------------------------------

    def new_label(self, prefix: str = "L") -> str:
        """Return a fresh unique local label like ``.L0``, ``.shift_left3``."""
        label = f".{prefix}{self._label_counter}"
        self._label_counter += 1
        return label
