from __future__ import annotations

import socket
import threading

from channels.generic.websocket import WebsocketConsumer
from django.conf import settings
from django.utils import timezone

from accounts.permissions import has_feature_permission
from host_management.models import ManagedHost

from ..models import TerminalSession
from ..services import (
    TerminalConnectionError,
    build_rdp_connection_parameters,
    create_rdp_terminal_session,
    guacamole_instruction,
    is_guacamole_internal_instruction,
    parse_guacamole_instruction,
    read_guacamole_instruction,
    terminal_protocol_for_host,
)
from .protocol import split_complete_guacamole_messages


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
        if not self._has_terminal_permission():
            self.close(code=4403)
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
        if not user or not getattr(user, "is_authenticated", False):
            return False

        session = self.scope.get("session")
        session_key = getattr(session, "session_key", None)
        if not session_key:
            return False

        try:
            return bool(session.exists(session_key))
        except Exception:
            return False

    def _has_terminal_permission(self) -> bool:
        return has_feature_permission(self.scope.get("user"), "hosts", "terminal")

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
        return split_complete_guacamole_messages(data)

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
