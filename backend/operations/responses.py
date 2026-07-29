from rest_framework import status
from rest_framework.response import Response


def bad_request(error: Exception | str) -> Response:
    return Response({"error": str(error)}, status=status.HTTP_400_BAD_REQUEST)


def not_found(message: str) -> Response:
    return Response({"error": message}, status=status.HTTP_404_NOT_FOUND)


def get_object_or_error(model, *, error_message: str = "资源不存在", queryset=None, **lookup):
    """按 lookup 取单个对象。

    返回 ``(instance, None)`` 或 ``(None, not_found(error_message))``,替代各视图里
    重复的 ``try: Model.objects.get(...) except Model.DoesNotExist`` 样板。
    典型用法::

        host, error = get_object_or_error(ManagedHost, id=host_id, error_message="主机不存在")
        if error:
            return error

    需要 ``select_related`` 等预取时传入定制 ``queryset``(``model`` 仅用于取
    ``DoesNotExist`` 异常类)::

        host, error = get_object_or_error(
            ManagedHost,
            queryset=ManagedHost.objects.select_related("created_by"),
            id=host_id,
            error_message="主机不存在",
        )
    """
    manager = queryset if queryset is not None else model.objects
    try:
        return manager.get(**lookup), None
    except model.DoesNotExist:
        return None, not_found(error_message)


def first_serializer_error(errors):
    if isinstance(errors, dict):
        first = next(iter(errors.values()))
        if isinstance(first, list) and first:
            return first[0]
        return first
    if isinstance(errors, list) and errors:
        return errors[0]
    return errors


def serializer_bad_request(serializer) -> Response:
    return bad_request(first_serializer_error(serializer.errors))


def bounded_int(value, *, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return min(max(number, minimum), maximum)


def paginate_queryset(
    queryset,
    request,
    *,
    serializer=None,
    serialize=None,
    default_page_size: int = 20,
    max_page_size: int = 100,
) -> dict:
    """统一分页,返回可直接放进 ``Response`` 的字典。

    输出同时含 ``total`` 与 ``count``(数值相同),兼容读取任一字段的前端;
    另含 ``results``、``page``、``pageSize``、``hasNext``。

    ``serializer`` 传 DRF Serializer 类(以 ``many=True`` 序列化当页),
    或用 ``serialize`` 传一个 ``callable(object_list) -> list`` 自定义序列化;
    两者都不传时 ``results`` 为当页对象列表原样。
    """
    page = bounded_int(request.query_params.get("page", 1), default=1, minimum=1, maximum=1000000)
    page_size = bounded_int(
        request.query_params.get("pageSize", request.query_params.get("limit", default_page_size)),
        default=default_page_size,
        minimum=1,
        maximum=max_page_size,
    )
    total = queryset.count()
    start = (page - 1) * page_size
    end = start + page_size
    object_list = queryset[start:end]

    if serializer is not None:
        results = serializer(object_list, many=True).data
    elif serialize is not None:
        results = serialize(object_list)
    else:
        results = list(object_list)

    return {
        "results": results,
        "total": total,
        "count": total,
        "page": page,
        "pageSize": page_size,
        "hasNext": end < total,
    }
