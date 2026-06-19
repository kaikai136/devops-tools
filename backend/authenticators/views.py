from django.db import IntegrityError
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from operations.responses import bad_request

from .models import AuthenticatorEntry
from .serializers import AuthenticatorEntrySerializer
from .services import (
    build_totp_uri,
    generate_qr_data_url,
    generate_totp,
    normalize_totp_algorithm,
    normalize_totp_secret,
)


@api_view(["GET", "POST", "DELETE"])
def authenticators(request):
    if request.method == "GET":
        entries = AuthenticatorEntry.objects.all()
        data = AuthenticatorEntrySerializer(entries, many=True).data
        for item, entry in zip(data, entries, strict=False):
            item["totp"] = generate_totp(entry)
        return Response(data)

    if request.method == "DELETE":
        AuthenticatorEntry.objects.all().delete()
        return Response({"deleted": True})

    try:
        entry = AuthenticatorEntry.objects.create(
            issuer=request.data.get("issuer", "").strip(),
            account_name=request.data.get("account_name", "").strip(),
            secret=normalize_totp_secret(request.data.get("secret", "")),
            digits=max(6, min(8, int(request.data.get("digits", 6)))),
            period=max(15, min(60, int(request.data.get("period", 30)))),
            algorithm=normalize_totp_algorithm(request.data.get("algorithm", "SHA1")),
        )
        return Response(AuthenticatorEntrySerializer(entry).data, status=status.HTTP_201_CREATED)
    except IntegrityError:
        return bad_request("该双因子认证条目已经存在")
    except Exception as error:
        return bad_request(error)


@api_view(["PUT", "DELETE"])
def authenticator_detail(request, entry_id: int):
    try:
        entry = AuthenticatorEntry.objects.get(id=entry_id)
    except AuthenticatorEntry.DoesNotExist:
        return Response({"error": "条目不存在"}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "DELETE":
        entry.delete()
        return Response({"deleted": True})

    try:
        entry.issuer = request.data.get("issuer", entry.issuer).strip()
        entry.account_name = request.data.get("account_name", entry.account_name).strip()
        entry.secret = normalize_totp_secret(request.data.get("secret", entry.secret))
        entry.digits = max(6, min(8, int(request.data.get("digits", entry.digits))))
        entry.period = max(15, min(60, int(request.data.get("period", entry.period))))
        entry.algorithm = normalize_totp_algorithm(request.data.get("algorithm", entry.algorithm))
        entry.save()
        return Response(AuthenticatorEntrySerializer(entry).data)
    except IntegrityError:
        return bad_request("该双因子认证条目已经存在")
    except Exception as error:
        return bad_request(error)


@api_view(["GET"])
def authenticator_code(_request, entry_id: int):
    try:
        entry = AuthenticatorEntry.objects.get(id=entry_id)
        return Response(generate_totp(entry))
    except AuthenticatorEntry.DoesNotExist:
        return Response({"error": "条目不存在"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as error:
        return bad_request(error)


@api_view(["GET"])
def authenticator_qrcode(_request, entry_id: int):
    try:
        entry = AuthenticatorEntry.objects.get(id=entry_id)
        uri = build_totp_uri(entry)
        return Response({"uri": uri, "data_url": generate_qr_data_url(uri)})
    except AuthenticatorEntry.DoesNotExist:
        return Response({"error": "条目不存在"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as error:
        return bad_request(error)
