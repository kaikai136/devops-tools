from __future__ import annotations

from ..services import find_guacamole_instruction_end


CWD_MARKER_START = "\x1b]1337;CaptainCwd="

CWD_MARKER_END = "\x07"

CWD_HOOK_SCRIPT = (
    "__captain_last_cwd=\"$PWD\"\n"
    "__captain_emit_cwd(){\n"
    "  if [ \"$PWD\" != \"$__captain_last_cwd\" ]; then\n"
    "    __captain_last_cwd=\"$PWD\"\n"
    "    printf '\\033]1337;CaptainCwd=%s\\007' \"$PWD\"\n"
    "  fi\n"
    "}\n"
    "if [ -n \"$ZSH_VERSION\" ]; then\n"
    "  autoload -Uz add-zsh-hook 2>/dev/null && add-zsh-hook precmd __captain_emit_cwd || precmd_functions+=(__captain_emit_cwd)\n"
    "else\n"
    "  case \"$PROMPT_COMMAND\" in\n"
    "    *__captain_emit_cwd*) ;;\n"
    "    '') PROMPT_COMMAND='__captain_emit_cwd' ;;\n"
    "    *) PROMPT_COMMAND=\"__captain_emit_cwd; $PROMPT_COMMAND\" ;;\n"
    "  esac\n"
    "fi\n"
)

CWD_HOOK_INSTALL_SCRIPT = (
    "__captain_last_cwd=\"$PWD\"; "
    "__captain_emit_cwd(){ if [ \"$PWD\" != \"$__captain_last_cwd\" ]; then "
    "__captain_last_cwd=\"$PWD\"; printf '\\033]1337;CaptainCwd=%s\\007' \"$PWD\"; fi; }; "
    "if [ -n \"$ZSH_VERSION\" ]; then "
    "autoload -Uz add-zsh-hook 2>/dev/null && add-zsh-hook precmd __captain_emit_cwd || precmd_functions+=(__captain_emit_cwd); "
    "else case \"$PROMPT_COMMAND\" in *__captain_emit_cwd*) ;; '') PROMPT_COMMAND='__captain_emit_cwd' ;; "
    "*) PROMPT_COMMAND=\"__captain_emit_cwd; $PROMPT_COMMAND\" ;; esac; fi\n"
)

CWD_HOOK_ECHO_OFF = "stty -echo 2>/dev/null\n"

CWD_HOOK_ECHO_ON = "stty echo 2>/dev/null\n"

CWD_HOOK_ECHO_FRAGMENTS = tuple(
    fragment
    for fragment in [CWD_HOOK_ECHO_OFF.strip(), CWD_HOOK_ECHO_ON.strip(), CWD_HOOK_INSTALL_SCRIPT.strip(), *CWD_HOOK_SCRIPT.splitlines()]
    if fragment
)

AUDIT_OUTPUT_FLUSH_CHARS = 65536

def strip_cwd_markers(output: str) -> tuple[str, list[str]]:
    cleaned, paths, pending = strip_cwd_markers_with_pending(output)
    return cleaned + pending, paths

def strip_cwd_markers_with_pending(output: str) -> tuple[str, list[str], str]:
    cleaned_parts: list[str] = []
    paths: list[str] = []
    cursor = 0

    while True:
        start = output.find(CWD_MARKER_START, cursor)
        if start < 0:
            cleaned_parts.append(output[cursor:])
            break

        cleaned_parts.append(output[cursor:start])
        path_start = start + len(CWD_MARKER_START)
        end = output.find(CWD_MARKER_END, path_start)
        if end < 0:
            return "".join(cleaned_parts), paths, output[start:]

        path = output[path_start:end].strip()
        if path:
            paths.append(path)
        cursor = end + len(CWD_MARKER_END)

    return "".join(cleaned_parts), paths, ""

def filter_changed_cwd_paths(paths: list[str], current_path: str) -> tuple[list[str], str]:
    changed_paths: list[str] = []

    for path in paths:
        if path == current_path:
            continue
        changed_paths.append(path)
        current_path = path

    return changed_paths, current_path

def strip_cwd_hook_install_echo(output: str) -> str:
    cleaned = output.replace("\x1b[200~", "").replace("\x1b[201~", "")
    internal_lines = {fragment.strip() for fragment in CWD_HOOK_ECHO_FRAGMENTS}
    visible_lines: list[str] = []
    for line in cleaned.splitlines(keepends=True):
        if line.strip() in internal_lines:
            continue
        visible_lines.append(line)
    return "".join(visible_lines)

def command_buffer_after_input(buffer: str, data: str) -> tuple[str, list[str]]:
    commands: list[str] = []
    in_escape = False
    for char in data:
        if in_escape:
            if char.isalpha() or char in "~":
                in_escape = False
            continue
        if char == "\x1b":
            in_escape = True
            continue
        if char in "\r\n":
            command = buffer.strip()
            if command:
                commands.append(command)
            buffer = ""
            continue
        if char in ("\x03", "\x04"):
            commands.append("^C" if char == "\x03" else "^D")
            buffer = ""
            continue
        if char in ("\x7f", "\b"):
            buffer = buffer[:-1]
            continue
        if char >= " ":
            buffer += char
    return buffer, commands


def split_complete_guacamole_messages(data: str) -> tuple[list[str], str]:
    messages: list[str] = []
    while data:
        terminator = find_guacamole_instruction_end(data)
        if terminator < 0:
            break
        messages.append(data[:terminator])
        data = data[terminator:]
    return messages, data
