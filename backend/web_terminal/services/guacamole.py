from __future__ import annotations

from .errors import TerminalConnectionError


__all__ = [
    "guacamole_instruction",
    "guacamole_element",
    "parse_guacamole_instruction",
    "is_guacamole_internal_instruction",
    "read_guacamole_instruction",
    "find_guacamole_instruction_end",
]


def guacamole_instruction(*elements) -> str:
    return ",".join(guacamole_element(element) for element in elements) + ";"


def guacamole_element(value) -> str:
    text = str(value)
    return f"{len(text)}.{text}"


def parse_guacamole_instruction(data: str) -> list[str]:
    elements: list[str] = []
    cursor = 0
    while cursor < len(data):
        length_end = data.find(".", cursor)
        if length_end < 0:
            raise TerminalConnectionError("Guacamole 指令不完整")
        try:
            length = int(data[cursor:length_end])
        except ValueError as error:
            raise TerminalConnectionError("Guacamole 指令长度无效") from error
        value_start = length_end + 1
        value_end = value_start + length
        if value_end >= len(data):
            raise TerminalConnectionError("Guacamole 指令不完整")
        elements.append(data[value_start:value_end])
        terminator = data[value_end]
        cursor = value_end + 1
        if terminator == ";":
            if cursor != len(data):
                raise TerminalConnectionError("Guacamole 指令包含多余数据")
            return elements
        if terminator != ",":
            raise TerminalConnectionError("Guacamole 指令分隔符无效")
    raise TerminalConnectionError("Guacamole 指令不完整")


def is_guacamole_internal_instruction(data: str) -> bool:
    try:
        elements = parse_guacamole_instruction(data)
    except TerminalConnectionError:
        return False
    return bool(elements) and elements[0] == ""


def read_guacamole_instruction(source, *, max_chars: int = 1024 * 1024) -> str:
    chunks: list[str] = []
    total = 0
    while total < max_chars:
        data = source.recv(8192)
        if not data:
            raise TerminalConnectionError("guacd 连接已关闭")
        text = data.decode("utf-8", errors="replace")
        chunks.append(text)
        total += len(text)
        combined = "".join(chunks)
        terminator = find_guacamole_instruction_end(combined)
        if terminator >= 0:
            return combined[:terminator]
    raise TerminalConnectionError("guacd 指令过大")


def find_guacamole_instruction_end(data: str) -> int:
    cursor = 0
    while cursor < len(data):
        length_end = data.find(".", cursor)
        if length_end < 0:
            return -1
        try:
            length = int(data[cursor:length_end])
        except ValueError as error:
            raise TerminalConnectionError("Guacamole 指令长度无效") from error
        value_end = length_end + 1 + length
        if value_end >= len(data):
            return -1
        terminator = data[value_end]
        cursor = value_end + 1
        if terminator == ";":
            return cursor
        if terminator != ",":
            raise TerminalConnectionError("Guacamole 指令分隔符无效")
    return -1
