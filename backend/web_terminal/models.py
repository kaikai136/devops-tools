import uuid

from django.db import models

from host_management.models import ManagedHost


class TerminalSession(models.Model):
    session_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    host = models.ForeignKey(ManagedHost, related_name="terminal_sessions", on_delete=models.CASCADE)
    status = models.CharField(max_length=20, default="connected")
    transcript = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_command_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.host.name} · {self.session_id}"
