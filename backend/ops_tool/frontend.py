from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404
from django.views.decorators.http import require_GET


@require_GET
def frontend_index(_request):
    return serve_frontend_html("index.html")


@require_GET
def frontend_terminal(_request):
    return serve_frontend_html("terminal.html")


def serve_frontend_html(filename: str):
    frontend_dist_dir = Path(settings.FRONTEND_DIST_DIR)
    html_path = frontend_dist_dir / filename
    try:
        resolved_html_path = html_path.resolve(strict=True)
        resolved_dist_dir = frontend_dist_dir.resolve(strict=True)
    except FileNotFoundError as exc:
        raise Http404("Frontend build output was not found.") from exc

    if resolved_html_path.parent != resolved_dist_dir:
        raise Http404("Frontend entry was not found.")

    return FileResponse(resolved_html_path.open("rb"), content_type="text/html; charset=utf-8")
