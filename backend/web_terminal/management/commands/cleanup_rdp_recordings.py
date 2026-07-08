from django.core.management.base import BaseCommand

from web_terminal.services import cleanup_expired_rdp_recordings


class Command(BaseCommand):
    help = "Delete expired RDP recording files and clear their session metadata."

    def handle(self, *args, **options):
        result = cleanup_expired_rdp_recordings()
        self.stdout.write(f"deleted={result['deleted']}")
