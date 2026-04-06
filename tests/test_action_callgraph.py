"""Tests for the SK-02 Action! call graph analysis.

Red/green: tests written first, then implementation to pass them.
"""

import pytest

from sk02action.call_graph import CallGraph, RecursionError
from sk02action.lexer import Lexer
from sk02action.parser import Parser

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def build_graph(source: str) -> CallGraph:
    tokens = Lexer(source).tokenize()
    ast = Parser(tokens).parse_program()
    return CallGraph(ast)


# ===========================================================================
# Construction
# ===========================================================================


class TestCallGraphConstruction:
    """Call graph correctly records caller→callee edges."""

    def test_single_call(self):
        graph = build_graph("PROC Foo()\nRETURN\nPROC Main()\n  Foo()\nRETURN")
        assert "foo" in graph.callees("main")

    def test_multiple_calls(self):
        graph = build_graph(
            "PROC A()\nRETURN\nPROC B()\nRETURN\nPROC Main()\n  A()\n  B()\nRETURN"
        )
        callees = graph.callees("main")
        assert "a" in callees
        assert "b" in callees

    def test_chained_calls(self):
        graph = build_graph(
            "PROC C()\nRETURN\n"
            "PROC B()\n  C()\nRETURN\n"
            "PROC A()\n  B()\nRETURN\n"
            "PROC Main()\n  A()\nRETURN"
        )
        assert "b" in graph.callees("a")
        assert "c" in graph.callees("b")

    def test_func_call_in_expression(self):
        graph = build_graph(
            "BYTE FUNC Get5()\nRETURN(5)\nPROC Main()\n  BYTE x\n  x = Get5()\nRETURN"
        )
        assert "get5" in graph.callees("main")

    def test_no_calls(self):
        graph = build_graph("PROC Main()\nRETURN")
        assert graph.callees("main") == set()


# ===========================================================================
# Recursion detection
# ===========================================================================


class TestRecursionDetection:
    """Direct and indirect recursion are detected as errors."""

    def test_direct_recursion(self):
        graph = build_graph("PROC Foo()\n  Foo()\nRETURN\nPROC Main()\nRETURN")
        with pytest.raises(RecursionError, match="foo"):
            graph.check_no_recursion()

    def test_indirect_recursion(self):
        # Test with self-recursion in a func context
        graph2 = build_graph("BYTE FUNC F(BYTE x)\nRETURN(F(x))\nPROC Main()\nRETURN")
        with pytest.raises(RecursionError, match="f"):
            graph2.check_no_recursion()

    def test_no_recursion_passes(self):
        graph = build_graph("PROC Foo()\nRETURN\nPROC Main()\n  Foo()\nRETURN")
        graph.check_no_recursion()  # should not raise


# ===========================================================================
# Overlap query
# ===========================================================================


class TestOverlapQuery:
    """Two routines can overlap if neither calls the other."""

    def test_independent_can_overlap(self):
        graph = build_graph(
            "PROC A()\nRETURN\nPROC B()\nRETURN\nPROC Main()\n  A()\n  B()\nRETURN"
        )
        assert graph.can_overlap("a", "b")

    def test_caller_callee_cannot_overlap(self):
        graph = build_graph(
            "PROC B()\nRETURN\nPROC A()\n  B()\nRETURN\nPROC Main()\n  A()\nRETURN"
        )
        assert not graph.can_overlap("a", "b")
        assert not graph.can_overlap("b", "a")

    def test_transitive_cannot_overlap(self):
        graph = build_graph(
            "PROC C()\nRETURN\n"
            "PROC B()\n  C()\nRETURN\n"
            "PROC A()\n  B()\nRETURN\n"
            "PROC Main()\n  A()\nRETURN"
        )
        assert not graph.can_overlap("a", "c")
