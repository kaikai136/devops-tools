from django.core.management.base import BaseCommand

from system_management.services import cleanup_expired_logs


class Command(BaseCommand):
    help = "Delete expired logs and RDP recordings according to the log_retention system setting."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Only count records and files that would be deleted.")

    def handle(self, *args, **options):
        result = cleanup_expired_logs(dry_run=options["dry_run"])
        prefix = "dryRun=true " if options["dry_run"] else ""
        self.stdout.write(
            prefix
            + " ".join(
                [
                    f"loginLogs={result['loginLogs']}",
                    f"operationLogs={result['operationLogs']}",
                    f"terminalCommandAudits={result['terminalCommandAudits']}",
                    f"terminalFileAudits={result['terminalFileAudits']}",
                    f"terminalSessions={result['terminalSessions']}",
                    f"rdpRecordings={result['rdpRecordings']}",
                ]
            )
        )
