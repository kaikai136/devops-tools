from django.core.management.base import BaseCommand

from web_terminal.services import cleanup_expired_rdp_recordings


class Command(BaseCommand):
    help = "Delete expired RDP recording files and clear their session metadata."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Only count recording files that would be deleted.")

    def handle(self, *args, **options):
        result = cleanup_expired_rdp_recordings(dry_run=options["dry_run"])
        prefix = "dryRun=true " if options["dry_run"] else ""
        self.stdout.write(f"{prefix}deleted={result['deleted']}")
