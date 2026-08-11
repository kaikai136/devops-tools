from __future__ import annotations

import shlex

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

# vim 等全屏程序重绘时 SSH 会把一屏内容拆成很多小片段返回,逐片推送会让
# channel layer 的单通道队列(默认容量 100)被瞬间打满,因此先在读取线程内合并。
OUTPUT_COALESCE_MAX_CHARS = 262144

OUTPUT_COALESCE_WINDOW_MS = 20

ALTERNATE_SCREEN_ENTER_SEQUENCES = (
    "\x1b[?47h",
    "\x1b[?1047h",
    "\x1b[?1049h",
)

ALTERNATE_SCREEN_EXIT_SEQUENCES = (
    "\x1b[?47l",
    "\x1b[?1047l",
    "\x1b[?1049l",
)

INTERACTIVE_TERMINAL_COMMANDS = {
    'bash',
    'fish',
    'fzf',
    'htop',
    'less',
    'man',
    'mc',
    'more',
    'most',
    'mysql',
    'nano',
    'nvim',
    'nvimdiff',
    'psql',
    'ranger',
    'sh',
    'sqlite3',
    'ssh',
    'sudoedit',
    'telnet',
    'top',
    'view',
    'vigr',
    'vipw',
    'vi',
    'vim',
    'vimdiff',
    'vimtutor',
    'visudo',
    'watch',
    'zsh',
}

COMMAND_WRAPPER_PREFIXES = {'env', 'nice', 'nohup', 'setsid', 'sudo', 'timeout'}
ENV_OPTIONS_WITH_ARGUMENT = {'-S', '--split-string', '-u', '--unset'}
NICE_OPTIONS_WITH_ARGUMENT = {'-n', '--adjustment'}
SUDO_OPTIONS_WITH_ARGUMENT = {
    '-C',
    '--chdir',
    '--chroot',
    '--close-from',
    '-D',
    '-g',
    '--group',
    '-h',
    '--host',
    '-p',
    '--prompt',
    '-R',
    '-r',
    '--role',
    '-T',
    '-t',
    '--type',
    '-u',
    '--user',
}
TIMEOUT_OPTIONS_WITH_ARGUMENT = {'-k', '--kill-after', '-s', '--signal'}

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


def alternate_screen_state_after_output(active: bool, output: str) -> bool:
    latest_index = -1
    next_active = active
    for sequence in ALTERNATE_SCREEN_ENTER_SEQUENCES:
        index = output.rfind(sequence)
        if index > latest_index:
            latest_index = index
            next_active = True
    for sequence in ALTERNATE_SCREEN_EXIT_SEQUENCES:
        index = output.rfind(sequence)
        if index > latest_index:
            latest_index = index
            next_active = False
    return next_active


def should_continue_coalescing_output(size: int, elapsed_ms: float) -> bool:
    return size < OUTPUT_COALESCE_MAX_CHARS and elapsed_ms < OUTPUT_COALESCE_WINDOW_MS


def output_has_alternate_screen_sequence(output: str) -> bool:
    return any(sequence in output for sequence in (*ALTERNATE_SCREEN_ENTER_SEQUENCES, *ALTERNATE_SCREEN_EXIT_SEQUENCES))

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


def is_interactive_terminal_command(command: str) -> bool:
    normalized = command.strip()
    if not normalized:
        return False

    try:
        tokens = shlex.split(normalized, posix=True)
    except ValueError:
        tokens = normalized.split()

    if not tokens:
        return False

    index = 0
    while index < len(tokens):
        head = tokens[index].rsplit('/', 1)[-1].lower()
        if head not in COMMAND_WRAPPER_PREFIXES:
            break

        index += 1
        index = skip_command_wrapper_arguments(tokens, index, head)

    if index >= len(tokens):
        return False

    command_name = tokens[index].rsplit('/', 1)[-1].lower()
    return command_name in INTERACTIVE_TERMINAL_COMMANDS


def skip_command_wrapper_arguments(tokens: list[str], index: int, wrapper: str) -> int:
    if wrapper == 'env':
        while index < len(tokens):
            token = tokens[index]
            if token.startswith('-'):
                index = skip_option(tokens, index, ENV_OPTIONS_WITH_ARGUMENT)
                continue
            if '=' in token and token.split('=', 1)[0]:
                index += 1
                continue
            break
        return index

    if wrapper == 'nice':
        return skip_options(tokens, index, NICE_OPTIONS_WITH_ARGUMENT)

    if wrapper == 'sudo':
        return skip_options(tokens, index, SUDO_OPTIONS_WITH_ARGUMENT)

    if wrapper == 'timeout':
        index = skip_options(tokens, index, TIMEOUT_OPTIONS_WITH_ARGUMENT)
        if index < len(tokens) and not tokens[index].startswith('-'):
            index += 1
        return index

    return skip_options(tokens, index, set())


def skip_options(tokens: list[str], index: int, options_with_argument: set[str]) -> int:
    while index < len(tokens) and tokens[index].startswith('-'):
        index = skip_option(tokens, index, options_with_argument)
    return index


def skip_option(tokens: list[str], index: int, options_with_argument: set[str]) -> int:
    token = tokens[index]
    option_name = token.split('=', 1)[0]
    index += 1
    if option_name in options_with_argument and '=' not in token and index < len(tokens):
        index += 1
    return index


def split_complete_guacamole_messages(data: str) -> tuple[list[str], str]:
    messages: list[str] = []
    while data:
        terminator = find_guacamole_instruction_end(data)
        if terminator < 0:
            break
        messages.append(data[:terminator])
        data = data[terminator:]
    return messages, data
