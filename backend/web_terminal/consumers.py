from __future__ import annotations

import json
import logging
import socket
import threading
import time

from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer
from django.conf import settings
from django.utils import timezone

from host_management.models import ManagedHost

from .models import TerminalCommandAudit, TerminalSession
from .services import (
    DEFAULT_TERMINAL_COLS,
    DEFAULT_TERMINAL_ROWS,
    LiveTerminalConnection,
    TerminalConnectionError,
    append_audit_output,
    asciicast_event,
    build_rdp_connection_parameters,
    create_rdp_terminal_session,
    create_command_audit,
    guacamole_instruction,
    find_guacamole_instruction_end,
    initialize_session_recording,
    is_guacamole_internal_instruction,
    is_session_audit_enabled,
    open_live_terminal,
    parse_guacamole_instruction,
    read_guacamole_instruction,
    save_session_recording,
    terminal_protocol_for_host,
)


logger = logging.getLogger(__name__)
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


class TerminalConsumer(WebsocketConsumer):
    connection: LiveTerminalConnection | None = None
    session: TerminalSession | None = None
    reader_thread: threading.Thread | None = None
    stop_reader: threading.Event
    transcript_chunks: list[str]
    pending_output: str
    current_cwd: str
    suppress_internal_echo_until: float
    command_buffer: str
    pending_command_audit: TerminalCommandAudit | None
    pending_command_output_chunks: list[str]
    pending_command_output_size: int
    recording_events: list[str]
    recording_last_event_at: object | None
    recording_lock: threading.Lock

    def connect(self):
        self.stop_reader = threading.Event()
        self.transcript_chunks = []
        self.pending_output = ""
        self.current_cwd = ""
        self.suppress_internal_echo_until = 0.0
        self.command_buffer = ""
        self.pending_command_audit = None
        self.pending_command_output_chunks = []
        self.pending_command_output_size = 0
        self.recording_events = []
        self.recording_last_event_at = None
        self.recording_lock = threading.Lock()
        self.accept()

        if not self._is_authenticated():
            self._close_for_unauthenticated()
            return

        host_id = self.scope["url_route"]["kwargs"]["host_id"]
        try:
            host = ManagedHost.objects.get(id=host_id)
            self.connection = open_live_terminal(host)
        except ManagedHost.DoesNotExist:
            self._send_error("请选择要连接的主机")
            self.close()
            return
        except TerminalConnectionError as error:
            self._send_error(str(error))
            self.close()
            return

        self._create_audit_session(host)
        self._send_initial_output()
        self._install_cwd_hook()
        ready_payload = {"type": "ready"}
        if self.session is not None:
            ready_payload["sessionId"] = str(self.session.session_id)
        self.send(text_data=json.dumps(ready_payload, ensure_ascii=False))
        thread_name = f"terminal-{self.session.session_id}" if self.session is not None else f"terminal-host-{host.id}"
        self.reader_thread = threading.Thread(target=self._read_ssh_output, name=thread_name, daemon=True)
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
                data = str(message.get("data", ""))
                self._record_input(data)
                self.connection.send_data(data)
            elif message_type == "resize":
                cols = int(message.get("cols", DEFAULT_TERMINAL_COLS))
                rows = int(message.get("rows", DEFAULT_TERMINAL_ROWS))
                self._record_resize(cols, rows)
                self.connection.resize(cols, rows)
            else:
                self._send_error("不支持的终端消息类型")
        except (TypeError, ValueError):
            self._send_error("终端窗口尺寸不正确")
        except Exception as error:
            self._send_error(f"SSH 连接失败：{error}")
            self.close()

    def disconnect(self, close_code):
        self.stop_reader.set()
        self._record_exit(0 if close_code in (None, 1000) else 1)
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
                        self._record_output(cleaned_output)
                        self._send_to_consumer({"type": "terminal.output", "data": cleaned_output})
                    for path in cwd_paths:
                        self._send_to_consumer({"type": "terminal.cwd", "path": path})
                    continue

                if self.connection.channel.closed or self.connection.channel.exit_status_ready():
                    if self.pending_output:
                        self.transcript_chunks.append(self.pending_output)
                        self._record_output(self.pending_output)
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

    def _create_audit_session(self, host: ManagedHost):
        if not is_session_audit_enabled(self.scope.get("user")):
            self.session = None
            self.recording_last_event_at = None
            return
        try:
            self.session = TerminalSession.objects.create(host=host, transcript=f"connect {host.name}\n")
            initialize_session_recording(self.session, DEFAULT_TERMINAL_COLS, DEFAULT_TERMINAL_ROWS)
            self.recording_last_event_at = self.session.recording_last_event_at
        except Exception:
            logger.exception("Terminal audit session initialization failed; continuing without audit recording.")
            self.session = None
            self.recording_last_event_at = None
            self.send(
                text_data=json.dumps(
                    {
                        "type": "output",
                        "data": "\r\n\x1b[33m[会话审计暂不可用，终端已切换为实时连接模式。请执行数据库迁移后恢复审计。]\x1b[0m\r\n",
                    },
                    ensure_ascii=False,
                )
            )

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
            self._record_output(cleaned_output)
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

    def _record_input(self, data: str):
        if not self.session or not data:
            return
        try:
            self._append_recording_event("i", data)
            self.command_buffer, commands = command_buffer_after_input(self.command_buffer, data)
            for command in commands:
                self._flush_pending_audit_output()
                self.pending_command_audit = create_command_audit(self.session, command, user=self.scope.get("user"))
        except Exception:
            self._disable_audit_session("Terminal input audit failed")

    def _record_output(self, output: str):
        if not self.session or not output:
            return
        try:
            self._append_recording_event("o", output)
            if self.pending_command_audit:
                self.pending_command_output_chunks.append(output)
                self.pending_command_output_size += len(output)
                if self.pending_command_output_size >= AUDIT_OUTPUT_FLUSH_CHARS:
                    self._flush_pending_audit_output()
        except Exception:
            self._disable_audit_session("Terminal output audit failed")

    def _record_resize(self, cols: int, rows: int):
        if not self.session:
            return
        try:
            cols = max(1, min(cols, 300))
            rows = max(1, min(rows, 120))
            self.session.recording_cols = cols
            self.session.recording_rows = rows
            self._append_recording_event("r", f"{cols}x{rows}")
        except Exception:
            self._disable_audit_session("Terminal resize audit failed")

    def _record_exit(self, exit_code: int):
        if not self.session:
            return
        try:
            self._append_recording_event("x", int(exit_code))
        except Exception:
            self._disable_audit_session("Terminal exit audit failed")

    def _append_recording_event(self, event_type: str, data):
        if not self.session or not self.session.recording_started_at:
            return
        with self.recording_lock:
            previous_event_at = self.recording_last_event_at or self.session.recording_last_event_at or self.session.recording_started_at
            event, event_at = asciicast_event(previous_event_at, event_type, data)
            self.recording_events.append(event + "\n")
            self.recording_last_event_at = event_at
            self.session.recording_last_event_at = event_at

    def _flush_pending_audit_output(self):
        if not self.pending_command_audit or not self.pending_command_output_chunks:
            return
        try:
            append_audit_output(self.pending_command_audit, "".join(self.pending_command_output_chunks))
        except Exception:
            self._disable_audit_session("Terminal command output audit flush failed")
            return
        self.pending_command_output_chunks = []
        self.pending_command_output_size = 0

    def _disable_audit_session(self, message: str):
        logger.exception("%s; continuing without audit recording.", message)
        self.session = None
        self.pending_command_audit = None
        self.pending_command_output_chunks = []
        self.pending_command_output_size = 0
        self.recording_events = []
        self.recording_last_event_at = None

    def _close_session(self):
        if self.session is None:
            return

        self._flush_pending_audit_output()
        if self.session is None:
            return
        transcript = "".join(self.transcript_chunks)
        update_fields = ["status", "last_command_at", "recording_cols", "recording_rows", "recording_last_event_at"]
        self.session.status = "closed"
        self.session.last_command_at = timezone.now()
        if transcript:
            self.session.transcript += transcript
            update_fields.append("transcript")
        with self.recording_lock:
            events = list(self.recording_events)
            self.recording_events.clear()
        save_session_recording(self.session, events, update_fields=update_fields)


class RdpTerminalConsumer(WebsocketConsumer):
    guacd_socket: socket.socket | None = None
    session: TerminalSession | None = None
    reader_thread: threading.Thread | None = None
    stop_reader: threading.Event

    def connect(self):
        self.stop_reader = threading.Event()
        self.accept(subprotocol="guacamole")

        if not self._is_authenticated():
            self.close(code=4401)
            return

        host_id = self.scope["url_route"]["kwargs"]["host_id"]
        try:
            host = ManagedHost.objects.get(id=host_id)
            if terminal_protocol_for_host(host) != TerminalSession.PROTOCOL_RDP:
                raise TerminalConnectionError("请选择 Windows 主机使用远程桌面。")
            self.session = create_rdp_terminal_session(host, user=self.scope["user"])
            self.guacd_socket = self._connect_guacd(host)
        except ManagedHost.DoesNotExist:
            self.close(code=4404)
            return
        except TerminalConnectionError as error:
            self._mark_session_error(str(error))
            self.close(code=4500)
            return

        self.send(text_data=guacamole_instruction("", str(self.session.session_id)))
        self.reader_thread = threading.Thread(target=self._read_guacd_output, name=f"rdp-{self.session.session_id}", daemon=True)
        self.reader_thread.start()

    def receive(self, text_data=None, bytes_data=None):
        if not text_data or self.guacd_socket is None:
            return
        if is_guacamole_internal_instruction(text_data):
            self.send(text_data=text_data)
            return
        try:
            self.guacd_socket.sendall(text_data.encode("utf-8"))
        except OSError as error:
            self._mark_session_error(str(error))
            self.close(code=1011)

    def disconnect(self, close_code):
        self.stop_reader.set()
        if self.guacd_socket is not None:
            try:
                self.guacd_socket.close()
            except OSError:
                pass
            self.guacd_socket = None
        if self.reader_thread and self.reader_thread.is_alive() and threading.current_thread() is not self.reader_thread:
            self.reader_thread.join(timeout=1.0)
        self._close_session(close_code)

    def _is_authenticated(self) -> bool:
        user = self.scope.get("user")
        return bool(user and getattr(user, "is_authenticated", False))

    def _connect_guacd(self, host: ManagedHost) -> socket.socket:
        try:
            guacd = socket.create_connection((settings.GUACD_HOST, settings.GUACD_PORT), timeout=15)
        except OSError as error:
            raise TerminalConnectionError(
                f"guacd RDP gateway unavailable ({settings.GUACD_HOST}:{settings.GUACD_PORT}): {error}"
            ) from error
        guacd.settimeout(15)
        try:
            guacd.sendall(guacamole_instruction("select", "rdp").encode("utf-8"))
            args_instruction = parse_guacamole_instruction(read_guacamole_instruction(guacd))
            if not args_instruction or args_instruction[0] != "args":
                raise TerminalConnectionError("guacd 未返回 RDP 参数列表。")

            width, height = self._requested_size()
            params = build_rdp_connection_parameters(host, self.session, width=width, height=height)
            guacd.sendall(guacamole_instruction("size", params["width"], params["height"], "96").encode("utf-8"))
            guacd.sendall(guacamole_instruction("audio").encode("utf-8"))
            guacd.sendall(guacamole_instruction("video").encode("utf-8"))
            guacd.sendall(guacamole_instruction("image", "image/png", "image/jpeg").encode("utf-8"))
            guacd.sendall(guacamole_instruction("connect", *[params.get(name, "") for name in args_instruction[1:]]).encode("utf-8"))
            ready_instruction = parse_guacamole_instruction(read_guacamole_instruction(guacd))
            if not ready_instruction or ready_instruction[0] != "ready":
                raise TerminalConnectionError("guacd RDP 会话未就绪。")
            guacd.settimeout(1.0)
            return guacd
        except Exception:
            guacd.close()
            raise

    def _requested_size(self) -> tuple[int, int]:
        query = self.scope.get("query_string", b"").decode("utf-8", errors="ignore")
        params = dict(item.split("=", 1) for item in query.split("&") if "=" in item)
        return self._requested_dimension(params.get("width"), 1280), self._requested_dimension(params.get("height"), 720)

    def _requested_dimension(self, value, default: int) -> int:
        text = str(value or "").strip().rstrip("?")
        try:
            return int(text or default)
        except ValueError:
            return default

    def _read_guacd_output(self):
        assert self.guacd_socket is not None
        pending = ""
        while not self.stop_reader.is_set():
            try:
                data = self.guacd_socket.recv(65535)
            except socket.timeout:
                continue
            except OSError:
                break
            if not data:
                break
            pending += data.decode("utf-8", errors="replace")
            try:
                messages, pending = self._split_complete_guacamole_messages(pending)
                for message in messages:
                    self.send(text_data=message)
            except Exception:
                break
        if pending and not self.stop_reader.is_set():
            self._mark_session_error("guacd returned an incomplete Guacamole instruction.")
        if not self.stop_reader.is_set():
            self.close()

    def _split_complete_guacamole_messages(self, data: str) -> tuple[list[str], str]:
        messages: list[str] = []
        while data:
            terminator = find_guacamole_instruction_end(data)
            if terminator < 0:
                break
            messages.append(data[:terminator])
            data = data[terminator:]
        return messages, data

    def _mark_session_error(self, message: str) -> None:
        if self.session is None:
            return
        self.session.status = "error"
        self.session.error_message = message[:1000]
        self.session.ended_at = timezone.now()
        self.session.save(update_fields=["status", "error_message", "ended_at"])

    def _close_session(self, close_code) -> None:
        if self.session is None:
            return
        if self.session.status != "error":
            self.session.status = "closed"
        self.session.ended_at = timezone.now()
        update_fields = ["status", "ended_at"]
        if close_code not in (None, 1000) and not self.session.error_message:
            self.session.error_message = f"WebSocket closed with code {close_code}"
            update_fields.append("error_message")
        self.session.save(update_fields=update_fields)
