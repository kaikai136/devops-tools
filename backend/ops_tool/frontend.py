from mimetypes import guess_type
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


@require_GET
def frontend_asset(_request, path: str):
    return serve_frontend_file(path)


def serve_frontend_html(filename: str):
    return serve_frontend_file(filename, content_type="text/html; charset=utf-8")


def serve_frontend_file(filename: str, content_type: str | None = None):
    frontend_dist_dir = Path(settings.FRONTEND_DIST_DIR)
    file_path = frontend_dist_dir / filename
    try:
        resolved_file_path = file_path.resolve(strict=True)
        resolved_dist_dir = frontend_dist_dir.resolve(strict=True)
    except FileNotFoundError as exc:
        raise Http404("Frontend build output was not found.") from exc

    if resolved_file_path.parent != resolved_dist_dir or not resolved_file_path.is_file():
        raise Http404("Frontend asset was not found.")

    response_type = content_type or guess_type(resolved_file_path.name)[0] or "application/octet-stream"
    return FileResponse(resolved_file_path.open("rb"), content_type=response_type)
