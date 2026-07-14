from __future__ import annotations

import ast
from importlib import import_module
from pathlib import Path

from django.test import SimpleTestCase

from web_terminal.services import (
    TerminalConnectionError,
    find_guacamole_instruction_end,
    guacamole_element,
    guacamole_instruction,
    is_guacamole_internal_instruction,
    parse_guacamole_instruction,
    read_guacamole_instruction,
)


class FakeSocket:
    def __init__(self, chunks):
        self.chunks = list(chunks)
        self.recv_sizes = []

    def recv(self, size):
        self.recv_sizes.append(size)
        return self.chunks.pop(0) if self.chunks else b""


class GuacamoleProtocolCharacterizationTests(SimpleTestCase):

    def test_guacamole_module_is_pure_and_has_exact_protocol_exports(self):
        module_path = Path(__file__).parents[1] / "services" / "guacamole.py"
        source = module_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_modules = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        imported_modules.update(
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )
        self.assertFalse(any(name.startswith("django") for name in imported_modules))
        self.assertFalse(any(name.endswith("models") or ".models" in name for name in imported_modules))

        module = import_module("web_terminal.services.guacamole")
        self.assertEqual(
            module.__all__,
            [
                "guacamole_instruction",
                "guacamole_element",
                "parse_guacamole_instruction",
                "is_guacamole_internal_instruction",
                "read_guacamole_instruction",
                "find_guacamole_instruction_end",
            ],
        )

    def test_encoding_preserves_character_length_and_wire_format(self):
        self.assertEqual(guacamole_element("\u7ec8\u7aef"), "2.\u7ec8\u7aef")
        self.assertEqual(
            guacamole_instruction("", "ping", 12345, "a,b;c"),
            "0.,4.ping,5.12345,5.a,b;c;",
        )

    def test_parser_round_trips_empty_and_delimiter_containing_elements(self):
        instruction = guacamole_instruction("", "ping", "a,b;c", "\u7ec8\u7aef")

        self.assertEqual(
            parse_guacamole_instruction(instruction),
            ["", "ping", "a,b;c", "\u7ec8\u7aef"],
        )
        self.assertTrue(is_guacamole_internal_instruction(instruction))
        self.assertFalse(is_guacamole_internal_instruction(guacamole_instruction("sync", "1")))
        self.assertFalse(is_guacamole_internal_instruction("invalid"))

    def test_parser_preserves_exact_invalid_payload_errors(self):
        cases = (
            ("3.foo", "Guacamole \u6307\u4ee4\u4e0d\u5b8c\u6574"),
            ("x.foo;", "Guacamole \u6307\u4ee4\u957f\u5ea6\u65e0\u6548"),
            ("3.foo!", "Guacamole \u6307\u4ee4\u5206\u9694\u7b26\u65e0\u6548"),
            ("3.foo;extra", "Guacamole \u6307\u4ee4\u5305\u542b\u591a\u4f59\u6570\u636e"),
            ("", "Guacamole \u6307\u4ee4\u4e0d\u5b8c\u6574"),
        )
        for payload, message in cases:
            with self.subTest(payload=payload):
                with self.assertRaisesMessage(TerminalConnectionError, message):
                    parse_guacamole_instruction(payload)

    def test_find_instruction_end_preserves_split_and_invalid_behavior(self):
        first = guacamole_instruction("sync", "123")
        second = guacamole_instruction("ack", "456")

        self.assertEqual(find_guacamole_instruction_end(first + second), len(first))
        self.assertEqual(find_guacamole_instruction_end(first[:-1]), -1)
        self.assertEqual(find_guacamole_instruction_end(""), -1)
        with self.assertRaisesMessage(TerminalConnectionError, "Guacamole \u6307\u4ee4\u957f\u5ea6\u65e0\u6548"):
            find_guacamole_instruction_end("x.foo;")
        with self.assertRaisesMessage(TerminalConnectionError, "Guacamole \u6307\u4ee4\u5206\u9694\u7b26\u65e0\u6548"):
            find_guacamole_instruction_end("3.foo!")

    def test_reader_preserves_chunking_first_instruction_and_replacement_decode(self):
        first = guacamole_instruction("sync", "\u7ec8\u7aef")
        trailing = guacamole_instruction("ack", "1")
        encoded = (first + trailing).encode("utf-8")
        source = FakeSocket([encoded[:5], encoded[5:]])

        self.assertEqual(read_guacamole_instruction(source), first)
        self.assertEqual(source.recv_sizes, [8192, 8192])

        invalid_utf8 = FakeSocket([b"4.test,1.\xff;"])
        self.assertEqual(parse_guacamole_instruction(read_guacamole_instruction(invalid_utf8)), ["test", "\ufffd"])

    def test_reader_preserves_closed_and_oversized_errors(self):
        with self.assertRaisesMessage(TerminalConnectionError, "guacd \u8fde\u63a5\u5df2\u5173\u95ed"):
            read_guacamole_instruction(FakeSocket([b""]))

        with self.assertRaisesMessage(TerminalConnectionError, "guacd \u6307\u4ee4\u8fc7\u5927"):
            read_guacamole_instruction(FakeSocket([b"3.foo"]), max_chars=5)
