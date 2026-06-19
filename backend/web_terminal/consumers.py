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


class TerminalConsumer(WebsocketConsumer):
    connection: LiveTerminalConnection | None = None
    session: TerminalSession | None = None
    reader_thread: threading.Thread | None = None
    stop_reader: threading.Event
    transcript_chunks: list[str]

    def connect(self):
        self.stop_reader = threading.Event()
        self.transcript_chunks = []
        self.accept()

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

        self.send(text_data=json.dumps({"type": "ready", "sessionId": str(self.session.session_id)}, ensure_ascii=False))
        self.reader_thread = threading.Thread(target=self._read_ssh_output, name=f"terminal-{self.session.session_id}", daemon=True)
        self.reader_thread.start()

    def receive(self, text_data=None, bytes_data=None):
        if not text_data or self.connection is None:
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

    def terminal_closed(self, event):
        self.send(text_data=json.dumps({"type": "closed", "reason": event["reason"]}, ensure_ascii=False))
        self.close()

    def terminal_error(self, event):
        self._send_error(event["message"])

    def _read_ssh_output(self):
        assert self.connection is not None

        while not self.stop_reader.is_set():
            try:
                output = self.connection.read_raw()
                if output:
                    self.transcript_chunks.append(output)
                    self._send_to_consumer({"type": "terminal.output", "data": output})
                    continue

                if self.connection.channel.closed or self.connection.channel.exit_status_ready():
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
