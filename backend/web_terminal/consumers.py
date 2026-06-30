from __future__ import annotations

import json
import threading
import time

from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer
from django.utils import timezone

from host_management.models import ManagedHost

from .models import TerminalSession
from .services import LiveTerminalConnection, TerminalConnectionError, open_live_terminal


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


class TerminalConsumer(WebsocketConsumer):
    connection: LiveTerminalConnection | None = None
    session: TerminalSession | None = None
    reader_thread: threading.Thread | None = None
    stop_reader: threading.Event
    transcript_chunks: list[str]
    pending_output: str
    current_cwd: str
    suppress_internal_echo_until: float

    def connect(self):
        self.stop_reader = threading.Event()
        self.transcript_chunks = []
        self.pending_output = ""
        self.current_cwd = ""
        self.suppress_internal_echo_until = 0.0
        self.accept()

        if not self._is_authenticated():
            self._close_for_unauthenticated()
            return

        host_id = self.scope["url_route"]["kwargs"]["host_id"]
        try:
            host = ManagedHost.objects.get(id=host_id)
            self.connection = open_live_terminal(host)
            self.session = TerminalSession.objects.create(host=host, transcript=f"connect {host.name}\n")
        except ManagedHost.DoesNotExist:
            self._send_error("请选择要连接的主机")
            self.close()
            return
        except TerminalConnectionError as error:
            self._send_error(str(error))
            self.close()
            return

        self._send_initial_output()
        self._install_cwd_hook()
        self.send(text_data=json.dumps({"type": "ready", "sessionId": str(self.session.session_id)}, ensure_ascii=False))
        self.reader_thread = threading.Thread(target=self._read_ssh_output, name=f"terminal-{self.session.session_id}", daemon=True)
        self.reader_thread.start()

    def receive(self, text_data=None, bytes_data=None):
        if not text_data or self.connection is None:
            return
        if not self._is_authenticated():
            self._close_for_unauthenticated()
            return

        try:
            message = json.loads(text_data)
        except json.JSONDecodeError:
            self._send_error("终端消息格式不正确")
            return

        message_type = message.get("type")
        try:
            if message_type == "input":
                self.connection.send_data(str(message.get("data", "")))
            elif message_type == "resize":
                self.connection.resize(int(message.get("cols", 120)), int(message.get("rows", 36)))
            else:
                self._send_error("不支持的终端消息类型")
        except (TypeError, ValueError):
            self._send_error("终端窗口尺寸不正确")
        except Exception as error:
            self._send_error(f"SSH 连接失败：{error}")
            self.close()

    def disconnect(self, close_code):
        self.stop_reader.set()
        if self.connection is not None:
            try:
                self.connection.close()
            except Exception:
                pass

        if self.reader_thread and self.reader_thread.is_alive() and threading.current_thread() is not self.reader_thread:
            self.reader_thread.join(timeout=1.0)

        self._close_session()

    def terminal_output(self, event):
        self.send(text_data=json.dumps({"type": "output", "data": event["data"]}, ensure_ascii=False))

    def terminal_cwd(self, event):
        self.send(text_data=json.dumps({"type": "cwd", "path": event["path"]}, ensure_ascii=False))

    def terminal_closed(self, event):
        self.send(text_data=json.dumps({"type": "closed", "reason": event["reason"]}, ensure_ascii=False))
        self.close()

    def terminal_error(self, event):
        self._send_error(event["message"])

    def _read_ssh_output(self):
        assert self.connection is not None

        next_auth_check = 0.0
        while not self.stop_reader.is_set():
            try:
                now = time.monotonic()
                if now >= next_auth_check:
                    next_auth_check = now + 1.0
                    if not self._is_authenticated():
                        self._send_to_consumer({"type": "terminal.error", "message": "请先登录"})
                        self._send_to_consumer({"type": "terminal.closed", "reason": "请先登录"})
                        return

                output = self.connection.read_raw()
                if output:
                    if time.monotonic() < self.suppress_internal_echo_until:
                        output = strip_cwd_hook_install_echo(output)
                    cleaned_output, cwd_paths, self.pending_output = strip_cwd_markers_with_pending(self.pending_output + output)
                    cwd_paths, self.current_cwd = filter_changed_cwd_paths(cwd_paths, self.current_cwd)
                    if cleaned_output:
                        self.transcript_chunks.append(cleaned_output)
                        self._send_to_consumer({"type": "terminal.output", "data": cleaned_output})
                    for path in cwd_paths:
                        self._send_to_consumer({"type": "terminal.cwd", "path": path})
                    continue

                if self.connection.channel.closed or self.connection.channel.exit_status_ready():
                    if self.pending_output:
                        self.transcript_chunks.append(self.pending_output)
                        self._send_to_consumer({"type": "terminal.output", "data": self.pending_output})
                        self.pending_output = ""
                    self._send_to_consumer({"type": "terminal.closed", "reason": "SSH 会话已关闭"})
                    return
            except Exception as error:
                if not self.stop_reader.is_set():
                    self._send_to_consumer({"type": "terminal.error", "message": f"读取 SSH 输出失败：{error}"})
                    self._send_to_consumer({"type": "terminal.closed", "reason": "SSH 会话已关闭"})
                return

            time.sleep(0.03)

    def _send_to_consumer(self, event: dict):
        if self.channel_layer is None:
            return
        try:
            async_to_sync(self.channel_layer.send)(self.channel_name, event)
        except Exception:
            self.stop_reader.set()

    def _send_error(self, message: str):
        self.send(text_data=json.dumps({"type": "error", "message": message}, ensure_ascii=False))

    def _close_for_unauthenticated(self):
        self._send_error("请先登录")
        self.close()

    def _is_authenticated(self) -> bool:
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            return False

        session = self.scope.get("session")
        session_key = getattr(session, "session_key", None)
        if not session_key:
            return False

        try:
            return bool(session.exists(session_key))
        except Exception:
            return False

    def _send_initial_output(self):
        if self.connection is None:
            return
        try:
            output = self.connection.read_available_raw(timeout=3.0, idle_timeout=0.35)
        except Exception:
            return
        if not output:
            return
        cleaned_output, cwd_paths, self.pending_output = strip_cwd_markers_with_pending(output)
        cwd_paths, self.current_cwd = filter_changed_cwd_paths(cwd_paths, self.current_cwd)
        if cleaned_output:
            self.transcript_chunks.append(cleaned_output)
            self.send(text_data=json.dumps({"type": "output", "data": cleaned_output}, ensure_ascii=False))
        for path in cwd_paths:
            self.send(text_data=json.dumps({"type": "cwd", "path": path}, ensure_ascii=False))

    def _install_cwd_hook(self):
        if self.connection is None:
            return
        echo_disabled = False
        try:
            self.suppress_internal_echo_until = time.monotonic() + 2.0
            self.connection.send_data(CWD_HOOK_ECHO_OFF)
            echo_disabled = True
            self._drain_cwd_hook_output()
            self.connection.send_data(CWD_HOOK_INSTALL_SCRIPT)
            self._drain_cwd_hook_output()
        except Exception:
            pass
        finally:
            if echo_disabled and self.connection is not None:
                try:
                    self.connection.send_data(CWD_HOOK_ECHO_ON)
                    self._drain_cwd_hook_output()
                except Exception:
                    pass

    def _drain_cwd_hook_output(self):
        if self.connection is None:
            return
        try:
            self.connection.read_available_raw(timeout=0.8, idle_timeout=0.12)
        except Exception:
            pass

    def _close_session(self):
        if self.session is None:
            return

        transcript = "".join(self.transcript_chunks)
        update_fields = ["status", "last_command_at"]
        self.session.status = "closed"
        self.session.last_command_at = timezone.now()
        if transcript:
            self.session.transcript += transcript
            update_fields.append("transcript")
        self.session.save(update_fields=update_fields)
