from django.core.management.base import BaseCommand

from web_terminal.gateway.server import run_gateway_server


class Command(BaseCommand):
    help = "Run the SSH/SFTP/SCP gateway service."

    def handle(self, *args, **options):
        run_gateway_server()
