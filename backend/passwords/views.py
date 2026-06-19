from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from operations.responses import bad_request

from .models import PasswordRecord
from .serializers import PasswordRecordSerializer
from .services import generate_password


@api_view(["POST"])
def password_generate(request):
    try:
        password = generate_password(
            int(request.data.get("length", 16)),
            bool(request.data.get("include_uppercase", True)),
            bool(request.data.get("include_lowercase", True)),
            bool(request.data.get("include_numbers", True)),
            bool(request.data.get("include_symbols", False)),
        )
        record = PasswordRecord.objects.create(
            project_name=request.data.get("project_name", "").strip(),
            password=password,
            length=len(password),
            include_uppercase=bool(request.data.get("include_uppercase", True)),
            include_lowercase=bool(request.data.get("include_lowercase", True)),
            include_numbers=bool(request.data.get("include_numbers", True)),
            include_symbols=bool(request.data.get("include_symbols", False)),
        )
        return Response(PasswordRecordSerializer(record).data)
    except Exception as error:
        return bad_request(error)


@api_view(["GET", "POST", "DELETE"])
def password_history(request):
    if request.method == "DELETE":
        PasswordRecord.objects.all().delete()
        return Response({"deleted": True})
    if request.method == "POST":
        records = request.data.get("records", request.data)
        if not isinstance(records, list):
            return bad_request("导入数据必须是密码记录数组")

        created = []
        for item in records:
            if not isinstance(item, dict):
                return bad_request("每条密码记录必须是对象")
            password = str(item.get("password", "")).strip()
            if not password:
                return bad_request("密码不能为空")
            record = PasswordRecord.objects.create(
                project_name=str(item.get("project_name", "")).strip(),
                password=password,
                length=int(item.get("length") or len(password)),
                include_uppercase=bool(item.get("include_uppercase", True)),
                include_lowercase=bool(item.get("include_lowercase", True)),
                include_numbers=bool(item.get("include_numbers", True)),
                include_symbols=bool(item.get("include_symbols", False)),
            )
            created.append(record)
        return Response(PasswordRecordSerializer(created, many=True).data, status=status.HTTP_201_CREATED)
    return Response(PasswordRecordSerializer(PasswordRecord.objects.all()[:16], many=True).data)


@api_view(["DELETE"])
def password_history_item(_request, record_id: int):
    PasswordRecord.objects.filter(id=record_id).delete()
    return Response({"deleted": True})
