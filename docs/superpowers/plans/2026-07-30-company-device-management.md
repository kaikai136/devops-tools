# Company Device Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build persistent company device management with add, edit, delete, batch delete, and Excel export.

**Architecture:** Add a focused Django app named `company_assets` for the persisted device model, serializer, API, permissions, and tests. Keep the Vue device page inside the existing `features/company` area, using a small API module and a pure Excel export utility so table behavior, data access, and export formatting stay separate.

**Tech Stack:** Django, Django REST Framework, Vue 3 Composition API, TypeScript, Vitest, browser Blob download, existing lightweight xlsx zip writer pattern.

## Global Constraints

- Device data must save to the Django database and survive page refresh.
- Implement only add, edit, delete, batch delete, and Excel export.
- Covered fields: asset name, category, code, spec, status, user, brand, purchase time, remark.
- Save created time, updated time, and creator in the backend.
- Do not add device import, tag management, copy device, detail page, device grouping, attachments, or new frontend dependencies.
- Export `.xlsx` in the browser and name files `company-devices-YYYY-MM-DD.xlsx`.
- Use permissions `access_companyDevices`, `action_companyDevices_create`, `action_companyDevices_edit`, `action_companyDevices_delete`, `action_companyDevices_export`, and `action_companyDevices_filter`.
- Preserve existing uncommitted user changes outside files touched for this feature.

---

## File Structure

- Create `backend/company_assets/`: owns persisted company devices.
- Create `backend/company_assets/models.py`: defines `CompanyDevice`.
- Create `backend/company_assets/serializers.py`: maps model fields to frontend camelCase API fields.
- Create `backend/company_assets/views.py`: implements list, create, update, and delete endpoints with feature permissions.
- Create `backend/company_assets/urls.py`: exposes `/api/company-devices/`.
- Create `backend/company_assets/tests.py`: covers API persistence and permission behavior.
- Create `backend/company_assets/migrations/0001_initial.py`: creates the database table.
- Modify `backend/ops_tool/settings.py`: installs `company_assets`.
- Modify `backend/operations/urls.py`: includes `company_assets.urls`.
- Modify `backend/system_management/services.py`: adds device action permission definitions.
- Modify `backend/system_management/middleware.py`: records operation logs for device writes.
- Create `frontend/src/features/company/types.ts`: frontend device and export types.
- Create `frontend/src/features/company/api/devices.ts`: frontend device API client.
- Create `frontend/src/features/company/utils/export.ts`: pure export rows and xlsx workbook builder.
- Create `frontend/src/features/company/utils/__tests__/deviceExport.test.ts`: export utility tests.
- Modify `frontend/src/features/company/components/DeviceManager.vue`: replaces local demo state with persisted management.
- Modify `frontend/src/features/company/__tests__/DeviceManager.structure.test.ts`: freezes structure, permissions, API wiring, and modal fields.
- Modify `frontend/src/styles/tools/device-manager.css`: styles the editor modal, error state, loading state, and disabled buttons.

---

### Task 1: Backend Persistence, API, And Permissions

**Files:**
- Create: `backend/company_assets/__init__.py`
- Create: `backend/company_assets/apps.py`
- Create: `backend/company_assets/models.py`
- Create: `backend/company_assets/serializers.py`
- Create: `backend/company_assets/views.py`
- Create: `backend/company_assets/urls.py`
- Create: `backend/company_assets/tests.py`
- Create: `backend/company_assets/migrations/__init__.py`
- Create: `backend/company_assets/migrations/0001_initial.py`
- Modify: `backend/ops_tool/settings.py`
- Modify: `backend/operations/urls.py`
- Modify: `backend/system_management/services.py`
- Modify: `backend/system_management/middleware.py`
- Test: `backend/company_assets/tests.py`

**Interfaces:**
- Produces: `CompanyDevice` model.
- Produces: API functions `listCompanyDevices`, `createCompanyDevice`, `updateCompanyDevice`, and `deleteCompanyDevice` will call `/api/company-devices/`.
- Produces: response shape with `id`, `name`, `category`, `code`, `spec`, `status`, `user`, `brand`, `purchaseTime`, `remark`, `createdAt`, `updatedAt`, `createdBy`.

- [ ] **Step 1: Write the failing backend API test**

Create `backend/company_assets/__init__.py` as an empty file.

Create `backend/company_assets/tests.py`:

```python
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase

from system_management.services import (
    FEATURE_PERMISSION_CODE_BY_KEY,
    PAGE_ACTION_PERMISSION_CODE_BY_KEY,
    ensure_feature_permissions,
)

from .models import CompanyDevice


def grant_company_device_permissions(user, *actions, access=True):
    ensure_feature_permissions()
    role = Group.objects.create(name=f"company-device-permissions-{user.id}-{Group.objects.count()}")
    permissions = []
    if access:
        permissions.append(Permission.objects.get(codename=FEATURE_PERMISSION_CODE_BY_KEY["companyDevices"]))
    permissions.extend(
        Permission.objects.get(codename=PAGE_ACTION_PERMISSION_CODE_BY_KEY[("companyDevices", action)])
        for action in actions
    )
    role.permissions.add(*permissions)
    user.groups.add(role)


class CompanyDeviceApiTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.staff = User.objects.create_user(username="staff", password="pass", is_staff=True)
        self.viewer = User.objects.create_user(username="viewer", password="pass", is_staff=False)

    def test_staff_can_create_list_update_and_delete_company_devices(self):
        self.client.force_login(self.staff)

        create_response = self.client.post(
            "/api/company-devices/",
            data={
                "name": "笔记本",
                "category": "固定资产",
                "code": "NB-001",
                "spec": "i7/32GB/1TB",
                "status": "using",
                "user": "张三",
                "brand": "ThinkPad",
                "purchaseTime": "2026-07-20",
                "remark": "研发使用",
            },
            content_type="application/json",
        )

        self.assertEqual(create_response.status_code, 201)
        created = create_response.json()
        self.assertEqual(created["name"], "笔记本")
        self.assertEqual(created["purchaseTime"], "2026-07-20")
        self.assertEqual(created["createdBy"], "staff")
        self.assertTrue(CompanyDevice.objects.filter(code="NB-001", created_by=self.staff).exists())

        list_response = self.client.get("/api/company-devices/")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json()[0]["code"], "NB-001")

        update_response = self.client.put(
            f"/api/company-devices/{created['id']}/",
            data={
                "name": "笔记本 Pro",
                "category": "固定资产",
                "code": "NB-001",
                "spec": "i9/64GB/2TB",
                "status": "repair",
                "user": "李四",
                "brand": "ThinkPad",
                "purchaseTime": None,
                "remark": "返修中",
            },
            content_type="application/json",
        )

        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.json()["name"], "笔记本 Pro")
        self.assertEqual(update_response.json()["purchaseTime"], None)
        self.assertEqual(update_response.json()["status"], "repair")

        delete_response = self.client.delete(f"/api/company-devices/{created['id']}/")

        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(delete_response.json(), {"deleted": True})
        self.assertFalse(CompanyDevice.objects.filter(id=created["id"]).exists())

    def test_company_device_create_requires_name(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            "/api/company-devices/",
            data={"name": "", "category": "固定资产", "status": "using"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("资产名称", response.json()["error"])

    def test_company_device_action_permissions_are_enforced(self):
        self.client.force_login(self.viewer)

        denied_list = self.client.get("/api/company-devices/")
        self.assertEqual(denied_list.status_code, 403)

        grant_company_device_permissions(self.viewer)

        allowed_list = self.client.get("/api/company-devices/")
        denied_create = self.client.post(
            "/api/company-devices/",
            data={"name": "台式机", "category": "固定资产", "status": "using"},
            content_type="application/json",
        )

        self.assertEqual(allowed_list.status_code, 200)
        self.assertEqual(denied_create.status_code, 403)

        grant_company_device_permissions(self.viewer, "create")
        create_response = self.client.post(
            "/api/company-devices/",
            data={"name": "台式机", "category": "固定资产", "status": "idle"},
            content_type="application/json",
        )
        device_id = create_response.json()["id"]

        denied_edit = self.client.put(
            f"/api/company-devices/{device_id}/",
            data={"name": "台式机 A", "category": "固定资产", "status": "using"},
            content_type="application/json",
        )
        denied_delete = self.client.delete(f"/api/company-devices/{device_id}/")

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(denied_edit.status_code, 403)
        self.assertEqual(denied_delete.status_code, 403)

        grant_company_device_permissions(self.viewer, "edit", "delete")

        allowed_edit = self.client.put(
            f"/api/company-devices/{device_id}/",
            data={"name": "台式机 A", "category": "固定资产", "status": "using"},
            content_type="application/json",
        )
        allowed_delete = self.client.delete(f"/api/company-devices/{device_id}/")

        self.assertEqual(allowed_edit.status_code, 200)
        self.assertEqual(allowed_delete.status_code, 200)
```

- [ ] **Step 2: Run backend tests and verify the red failure**

Run:

```powershell
wsl.exe --cd /mnt/c/Users/kaikai/Desktop/django-vue/backend -e env APP_CONFIG_FILE=/mnt/c/Users/kaikai/Desktop/django-vue/config/local.app.conf /root/venv-opstool/bin/python manage.py test company_assets --noinput
```

Expected: FAIL because `company_assets.models` or the installed app is not implemented yet.

- [ ] **Step 3: Implement the backend app**

Create `backend/company_assets/apps.py`:

```python
from django.apps import AppConfig


class CompanyAssetsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "company_assets"
```

Create `backend/company_assets/models.py`:

```python
from django.conf import settings
from django.db import models


class CompanyDevice(models.Model):
    STATUS_USING = "using"
    STATUS_IDLE = "idle"
    STATUS_REPAIR = "repair"
    STATUS_CHOICES = [
        (STATUS_USING, "使用中"),
        (STATUS_IDLE, "闲置"),
        (STATUS_REPAIR, "维修中"),
    ]

    name = models.CharField(max_length=160)
    category = models.CharField(max_length=80, default="固定资产")
    code = models.CharField(max_length=120, blank=True)
    spec = models.CharField(max_length=260, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_USING)
    user = models.CharField(max_length=120, blank=True)
    brand = models.CharField(max_length=120, blank=True)
    purchase_time = models.DateField(null=True, blank=True)
    remark = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="company_devices",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["category"]),
            models.Index(fields=["code"]),
        ]

    def __str__(self) -> str:
        return self.name
```

Create `backend/company_assets/serializers.py`:

```python
from rest_framework import serializers

from .models import CompanyDevice


class CompanyDeviceSerializer(serializers.ModelSerializer):
    purchaseTime = serializers.DateField(source="purchase_time", required=False, allow_null=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)
    createdBy = serializers.SerializerMethodField()

    class Meta:
        model = CompanyDevice
        fields = [
            "id",
            "name",
            "category",
            "code",
            "spec",
            "status",
            "user",
            "brand",
            "purchaseTime",
            "remark",
            "createdAt",
            "updatedAt",
            "createdBy",
        ]

    def validate_name(self, value: str) -> str:
        name = value.strip()
        if not name:
            raise serializers.ValidationError("请输入资产名称")
        return name

    def validate_category(self, value: str) -> str:
        return value.strip() or "固定资产"

    def validate_code(self, value: str) -> str:
        return value.strip()

    def validate_spec(self, value: str) -> str:
        return value.strip()

    def validate_user(self, value: str) -> str:
        return value.strip()

    def validate_brand(self, value: str) -> str:
        return value.strip()

    def validate_remark(self, value: str) -> str:
        return value.strip()

    def get_createdBy(self, device: CompanyDevice) -> str:
        return device.created_by.username if device.created_by_id and device.created_by else "system"
```

Create `backend/company_assets/views.py`:

```python
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from accounts.permissions import require_feature_permission
from operations.responses import get_object_or_error, serializer_bad_request

from .models import CompanyDevice
from .serializers import CompanyDeviceSerializer


def company_device_permission(request, action_key: str | None = None):
    return require_feature_permission(request, "companyDevices", action_key, "没有设备管理权限")


@api_view(["GET", "POST"])
def company_devices(request):
    action = "create" if request.method == "POST" else None
    auth_error = company_device_permission(request, action)
    if auth_error:
        return auth_error

    if request.method == "GET":
        devices = CompanyDevice.objects.select_related("created_by").all()
        return Response(CompanyDeviceSerializer(devices, many=True).data)

    serializer = CompanyDeviceSerializer(data=request.data)
    if not serializer.is_valid():
        return serializer_bad_request(serializer)
    creator = request.user if request.user.is_authenticated else None
    device = serializer.save(created_by=creator)
    return Response(CompanyDeviceSerializer(device).data, status=status.HTTP_201_CREATED)


@api_view(["PUT", "DELETE"])
def company_device_detail(request, device_id: int):
    action = "delete" if request.method == "DELETE" else "edit"
    auth_error = company_device_permission(request, action)
    if auth_error:
        return auth_error

    device, error = get_object_or_error(
        CompanyDevice,
        queryset=CompanyDevice.objects.select_related("created_by"),
        id=device_id,
        error_message="设备不存在",
    )
    if error:
        return error

    if request.method == "DELETE":
        device.delete()
        return Response({"deleted": True})

    serializer = CompanyDeviceSerializer(device, data=request.data, partial=True)
    if not serializer.is_valid():
        return serializer_bad_request(serializer)
    device = serializer.save()
    return Response(CompanyDeviceSerializer(device).data)
```

Create `backend/company_assets/urls.py`:

```python
from django.urls import path

from . import views

urlpatterns = [
    path("company-devices/", views.company_devices),
    path("company-devices/<int:device_id>/", views.company_device_detail),
]
```

Create `backend/company_assets/migrations/__init__.py` as an empty file.

Modify `backend/ops_tool/settings.py` by adding `"company_assets",` in `INSTALLED_APPS` after `"bulk_execution",`.

Modify `backend/operations/urls.py` by adding:

```python
    path("", include("company_assets.urls")),
```

after the `bulk_execution.urls` include.

Modify `backend/system_management/services.py` by adding these entries to `PAGE_ACTION_PERMISSION_DEFINITIONS` after the `accounts` actions:

```python
    ("companyDevices", "create", "添加设备"),
    ("companyDevices", "edit", "编辑设备"),
    ("companyDevices", "delete", "删除设备"),
    ("companyDevices", "export", "导出 Excel"),
    ("companyDevices", "filter", "查询筛选"),
```

Modify `backend/system_management/middleware.py` by adding this audit rule after the host/account rules:

```python
    AuditRule("/api/company-devices/", "设备管理"),
```

Generate the migration:

```powershell
wsl.exe --cd /mnt/c/Users/kaikai/Desktop/django-vue/backend -e env APP_CONFIG_FILE=/mnt/c/Users/kaikai/Desktop/django-vue/config/local.app.conf /root/venv-opstool/bin/python manage.py makemigrations company_assets
```

Expected: creates `backend/company_assets/migrations/0001_initial.py`.

- [ ] **Step 4: Run backend tests and verify green**

Run:

```powershell
wsl.exe --cd /mnt/c/Users/kaikai/Desktop/django-vue/backend -e env APP_CONFIG_FILE=/mnt/c/Users/kaikai/Desktop/django-vue/config/local.app.conf /root/venv-opstool/bin/python manage.py test company_assets --noinput
```

Expected: PASS with all `CompanyDeviceApiTests` passing.

- [ ] **Step 5: Commit backend persistence**

Run:

```powershell
git add backend/company_assets backend/ops_tool/settings.py backend/operations/urls.py backend/system_management/services.py backend/system_management/middleware.py
git commit -m "feat: 添加设备管理后端"
```

Expected: commit only backend files for this task.

---

### Task 2: Frontend Device API And Excel Export Utilities

**Files:**
- Create: `frontend/src/features/company/types.ts`
- Create: `frontend/src/features/company/api/devices.ts`
- Create: `frontend/src/features/company/utils/export.ts`
- Create: `frontend/src/features/company/utils/__tests__/deviceExport.test.ts`

**Interfaces:**
- Consumes: backend response shape from Task 1.
- Produces: `CompanyDevice`, `CompanyDevicePayload`, `listCompanyDevices()`, `createCompanyDevice(payload)`, `updateCompanyDevice(id, payload)`, `deleteCompanyDevice(id)`.
- Produces: `companyDeviceExportColumns`, `companyDeviceStatusText(status)`, `buildCompanyDeviceExportRows(devices)`, `buildCompanyDeviceXlsxWorkbook(devices)`.

- [ ] **Step 1: Write the failing frontend export utility test**

Create `frontend/src/features/company/utils/__tests__/deviceExport.test.ts`:

```typescript
import { describe, expect, it } from 'vitest';

import type { CompanyDevice } from '../../types';
import {
  buildCompanyDeviceExportRows,
  buildCompanyDeviceXlsxWorkbook,
  companyDeviceExportColumns,
  companyDeviceStatusText,
} from '../export';

const device: CompanyDevice = {
  id: 1,
  name: '笔记本',
  category: '固定资产',
  code: 'NB-001',
  spec: 'i7/32GB/1TB',
  status: 'repair',
  user: '张三',
  brand: 'ThinkPad',
  purchaseTime: '2026-07-20',
  remark: '返修中',
  createdAt: '2026-07-20T01:02:03Z',
  updatedAt: '2026-07-21T01:02:03Z',
  createdBy: 'admin',
};

describe('company device export utilities', () => {
  it('keeps the device export columns in table order', () => {
    expect(companyDeviceExportColumns).toEqual([
      { field: 'name', label: '资产名称', width: 22 },
      { field: 'category', label: '资产类别', width: 16 },
      { field: 'code', label: '资产编码', width: 18 },
      { field: 'spec', label: '规格说明', width: 28 },
      { field: 'status', label: '资产状态', width: 14 },
      { field: 'user', label: '使用人员', width: 16 },
      { field: 'brand', label: '品牌名称', width: 16 },
      { field: 'purchaseTime', label: '采购时间', width: 16 },
      { field: 'remark', label: '备注', width: 28 },
    ]);
  });

  it('serializes status values and empty fields for export rows', () => {
    expect(companyDeviceStatusText('using')).toBe('使用中');
    expect(companyDeviceStatusText('idle')).toBe('闲置');
    expect(companyDeviceStatusText('repair')).toBe('维修中');
    expect(buildCompanyDeviceExportRows([{ ...device, code: '', purchaseTime: null }])).toEqual([
      {
        name: '笔记本',
        category: '固定资产',
        code: '',
        spec: 'i7/32GB/1TB',
        status: '维修中',
        user: '张三',
        brand: 'ThinkPad',
        purchaseTime: '',
        remark: '返修中',
      },
    ]);
  });

  it('builds an xlsx workbook containing Chinese headers and values', () => {
    const workbook = new TextDecoder().decode(buildCompanyDeviceXlsxWorkbook([device]));

    expect(workbook).toContain('设备清单');
    expect(workbook).toContain('资产名称');
    expect(workbook).toContain('资产状态');
    expect(workbook).toContain('笔记本');
    expect(workbook).toContain('维修中');
  });
});
```

- [ ] **Step 2: Run frontend export test and verify red**

Run:

```powershell
npm --prefix frontend run test:run -- src/features/company/utils/__tests__/deviceExport.test.ts
```

Expected: FAIL because `features/company/types` and `features/company/utils/export` do not exist.

- [ ] **Step 3: Implement frontend types and API client**

Create `frontend/src/features/company/types.ts`:

```typescript
export type CompanyDeviceStatus = 'using' | 'idle' | 'repair';

export interface CompanyDevice {
  id: number;
  name: string;
  category: string;
  code: string;
  spec: string;
  status: CompanyDeviceStatus;
  user: string;
  brand: string;
  purchaseTime: string | null;
  remark: string;
  createdAt: string | null;
  updatedAt: string | null;
  createdBy: string;
}

export interface CompanyDevicePayload {
  name: string;
  category: string;
  code: string;
  spec: string;
  status: CompanyDeviceStatus;
  user: string;
  brand: string;
  purchaseTime: string | null;
  remark: string;
}

export type CompanyDeviceExportField =
  | 'name'
  | 'category'
  | 'code'
  | 'spec'
  | 'status'
  | 'user'
  | 'brand'
  | 'purchaseTime'
  | 'remark';

export type CompanyDeviceExportRow = Record<CompanyDeviceExportField, string>;

export interface CompanyDeviceExportColumn {
  field: CompanyDeviceExportField;
  label: string;
  width: number;
}
```

Create `frontend/src/features/company/api/devices.ts`:

```typescript
import { apiDelete, apiGet, apiPost, apiPut } from '../../../api';
import type { CompanyDevice, CompanyDevicePayload } from '../types';

const baseUrl = '/api/company-devices';

export function listCompanyDevices() {
  return apiGet<CompanyDevice[]>(`${baseUrl}/`);
}

export function createCompanyDevice(payload: CompanyDevicePayload) {
  return apiPost<CompanyDevice>(`${baseUrl}/`, payload);
}

export function updateCompanyDevice(deviceId: number, payload: CompanyDevicePayload) {
  return apiPut<CompanyDevice>(`${baseUrl}/${deviceId}/`, payload);
}

export function deleteCompanyDevice(deviceId: number) {
  return apiDelete<{ deleted: boolean }>(`${baseUrl}/${deviceId}/`);
}
```

- [ ] **Step 4: Implement the Excel export utility**

Create `frontend/src/features/company/utils/export.ts` with a self-contained xlsx writer:

```typescript
import type {
  CompanyDevice,
  CompanyDeviceExportColumn,
  CompanyDeviceExportRow,
  CompanyDeviceStatus,
} from '../types';

export const companyDeviceExportColumns: readonly CompanyDeviceExportColumn[] = [
  { field: 'name', label: '资产名称', width: 22 },
  { field: 'category', label: '资产类别', width: 16 },
  { field: 'code', label: '资产编码', width: 18 },
  { field: 'spec', label: '规格说明', width: 28 },
  { field: 'status', label: '资产状态', width: 14 },
  { field: 'user', label: '使用人员', width: 16 },
  { field: 'brand', label: '品牌名称', width: 16 },
  { field: 'purchaseTime', label: '采购时间', width: 16 },
  { field: 'remark', label: '备注', width: 28 },
];

export function companyDeviceStatusText(status: CompanyDeviceStatus) {
  if (status === 'idle') return '闲置';
  if (status === 'repair') return '维修中';
  return '使用中';
}

export function buildCompanyDeviceExportRows(devices: readonly CompanyDevice[]): CompanyDeviceExportRow[] {
  return devices.map((device) => ({
    name: device.name || '',
    category: device.category || '',
    code: device.code || '',
    spec: device.spec || '',
    status: companyDeviceStatusText(device.status),
    user: device.user || '',
    brand: device.brand || '',
    purchaseTime: device.purchaseTime || '',
    remark: device.remark || '',
  }));
}

export function buildCompanyDeviceXlsxWorkbook(devices: readonly CompanyDevice[]) {
  return buildXlsxWorkbookFromRows(buildCompanyDeviceExportRows(devices), companyDeviceExportColumns, '设备清单');
}

function buildXlsxWorkbookFromRows(rows: CompanyDeviceExportRow[], columns: readonly CompanyDeviceExportColumn[], sheetName: string) {
  const worksheet = buildXlsxWorksheet(rows, columns);
  return createZip([
    { name: '[Content_Types].xml', content: stringToBytes('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>') },
    { name: '_rels/.rels', content: stringToBytes('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>') },
    { name: 'xl/workbook.xml', content: stringToBytes(`<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="${escapeXml(sheetName)}" sheetId="1" r:id="rId1"/></sheets></workbook>`) },
    { name: 'xl/_rels/workbook.xml.rels', content: stringToBytes('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>') },
    { name: 'xl/styles.xml', content: stringToBytes('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="2"><font><sz val="11"/><name val="Microsoft YaHei"/></font><font><b/><sz val="11"/><name val="Microsoft YaHei"/></font></fonts><fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="2"><xf numFmtId="49" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="49" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>') },
    { name: 'xl/worksheets/sheet1.xml', content: stringToBytes(worksheet) },
  ]);
}

function buildXlsxWorksheet(rows: CompanyDeviceExportRow[], columns: readonly CompanyDeviceExportColumn[]) {
  const columnXml = columns.map((column, index) => `<col min="${index + 1}" max="${index + 1}" width="${Math.max(10, column.width)}" customWidth="1"/>`).join('');
  const header = `<row r="1">${columns.map((column, index) => buildXlsxCell(1, index + 1, column.label, 1)).join('')}</row>`;
  const body = rows
    .map((row, rowIndex) => {
      const excelRow = rowIndex + 2;
      return `<row r="${excelRow}">${columns.map((column, columnIndex) => buildXlsxCell(excelRow, columnIndex + 1, row[column.field])).join('')}</row>`;
    })
    .join('');
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><cols>${columnXml}</cols><sheetData>${header}${body}</sheetData></worksheet>`;
}

function buildXlsxCell(row: number, column: number, value: string, style = 0) {
  const ref = `${columnName(column)}${row}`;
  return `<c r="${ref}" t="inlineStr"${style ? ` s="${style}"` : ''}><is><t>${escapeXml(value)}</t></is></c>`;
}

function columnName(index: number) {
  let name = '';
  let current = index;
  while (current > 0) {
    current -= 1;
    name = String.fromCharCode(65 + (current % 26)) + name;
    current = Math.floor(current / 26);
  }
  return name;
}

function createZip(files: Array<{ name: string; content: Uint8Array }>) {
  const localParts: Uint8Array[] = [];
  const centralParts: Uint8Array[] = [];
  let offset = 0;
  for (const file of files) {
    const name = stringToBytes(file.name);
    const crc = crc32(file.content);
    const localHeader = concatBytes([
      uint32(0x04034b50),
      uint16(20),
      uint16(0),
      uint16(0),
      uint16(0),
      uint16(0),
      uint32(crc),
      uint32(file.content.length),
      uint32(file.content.length),
      uint16(name.length),
      uint16(0),
      name,
    ]);
    localParts.push(localHeader, file.content);
    centralParts.push(concatBytes([
      uint32(0x02014b50),
      uint16(20),
      uint16(20),
      uint16(0),
      uint16(0),
      uint16(0),
      uint16(0),
      uint32(crc),
      uint32(file.content.length),
      uint32(file.content.length),
      uint16(name.length),
      uint16(0),
      uint16(0),
      uint16(0),
      uint16(0),
      uint32(0),
      uint32(offset),
      name,
    ]));
    offset += localHeader.length + file.content.length;
  }
  const centralOffset = offset;
  const centralDirectory = concatBytes(centralParts);
  const endRecord = concatBytes([
    uint32(0x06054b50),
    uint16(0),
    uint16(0),
    uint16(files.length),
    uint16(files.length),
    uint32(centralDirectory.length),
    uint32(centralOffset),
    uint16(0),
  ]);
  return concatBytes([...localParts, centralDirectory, endRecord]);
}

function stringToBytes(value: string) {
  return new TextEncoder().encode(value);
}

function concatBytes(parts: Uint8Array[]) {
  const total = parts.reduce((sum, part) => sum + part.length, 0);
  const result = new Uint8Array(total);
  let offset = 0;
  for (const part of parts) {
    result.set(part, offset);
    offset += part.length;
  }
  return result;
}

function uint16(value: number) {
  const bytes = new Uint8Array(2);
  new DataView(bytes.buffer).setUint16(0, value, true);
  return bytes;
}

function uint32(value: number) {
  const bytes = new Uint8Array(4);
  new DataView(bytes.buffer).setUint32(0, value >>> 0, true);
  return bytes;
}

function crc32(bytes: Uint8Array) {
  let crc = 0xffffffff;
  for (const byte of bytes) {
    crc ^= byte;
    for (let index = 0; index < 8; index += 1) {
      crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0);
    }
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function escapeXml(value: string) {
  return value.replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f&<>"']/g, (char) => {
    if (char === '&') return '&amp;';
    if (char === '<') return '&lt;';
    if (char === '>') return '&gt;';
    if (char === '"') return '&quot;';
    if (char === "'") return '&apos;';
    return '';
  });
}
```

- [ ] **Step 5: Run frontend export test and verify green**

Run:

```powershell
npm --prefix frontend run test:run -- src/features/company/utils/__tests__/deviceExport.test.ts
```

Expected: PASS.

- [ ] **Step 6: Commit frontend API and export utilities**

Run:

```powershell
git add frontend/src/features/company/types.ts frontend/src/features/company/api/devices.ts frontend/src/features/company/utils
git commit -m "feat: 添加设备导出工具"
```

Expected: commit only Task 2 frontend utility files.

---

### Task 3: Persisted Device Manager UI

**Files:**
- Modify: `frontend/src/features/company/components/DeviceManager.vue`
- Modify: `frontend/src/features/company/__tests__/DeviceManager.structure.test.ts`
- Modify: `frontend/src/styles/tools/device-manager.css`

**Interfaces:**
- Consumes: `CompanyDevice`, `CompanyDevicePayload`, and API/export functions from Task 2.
- Consumes: app context functions `showToast`, `requestConfirm`, and `canUsePageAction`.
- Produces: a device page that loads from the backend, opens create/edit modal forms, deletes single or selected devices, and exports selected or filtered devices.

- [ ] **Step 1: Update the component structure test first**

Replace the second test in `frontend/src/features/company/__tests__/DeviceManager.structure.test.ts` with this test:

```typescript
  it('renders persisted device management controls, permissions, and editor fields', () => {
    const root = templateRoot('features/company/components/DeviceManager.vue');
    const source = readSource('features/company/components/DeviceManager.vue');

    expect(findByClass(root, 'section', 'device-manager-page')).toHaveLength(1);
    expect(source).toContain('listCompanyDevices');
    expect(source).toContain('createCompanyDevice');
    expect(source).toContain('updateCompanyDevice');
    expect(source).toContain('deleteCompanyDevice');
    expect(source).toContain('buildCompanyDeviceXlsxWorkbook');
    expect(source).toContain("canUsePageAction('companyDevices', 'create')");
    expect(source).toContain("canUsePageAction('companyDevices', 'edit')");
    expect(source).toContain("canUsePageAction('companyDevices', 'delete')");
    expect(source).toContain("canUsePageAction('companyDevices', 'export')");
    expect(source).toContain("canUsePageAction('companyDevices', 'filter')");
    expect(source).toContain('资产列表');
    expect(source).toContain('添加');
    expect(source).toContain('删除');
    expect(source).toContain('导出Excel');
    expect(source).toContain('编辑');
    expect(source).not.toContain('复制');
    expect(source).not.toContain('设置标签');
    expect(source).not.toContain('查看');
    for (const header of ['序号', '资产名称', '资产类别', '资产编码', '规格说明', '资产状态', '使用人员', '品牌名称', '采购时间', '备注', '操作']) {
      expect(source).toContain(`<th>${header}</th>`);
    }
    for (const label of ['资产名称', '资产类别', '资产编码', '规格说明', '资产状态', '使用人员', '品牌名称', '采购时间', '备注']) {
      expect(source).toContain(`<span>${label}</span>`);
    }
    expect(findByClass(root, 'form', 'device-form-modal')).toHaveLength(1);
  });
```

Keep the first navigation test unchanged.

- [ ] **Step 2: Run component structure test and verify red**

Run:

```powershell
npm --prefix frontend run test:run -- src/features/company/__tests__/DeviceManager.structure.test.ts
```

Expected: FAIL because `DeviceManager.vue` still uses local demo data and placeholder buttons.

- [ ] **Step 3: Replace local demo state with persisted UI logic**

In `frontend/src/features/company/components/DeviceManager.vue`, implement these script-level pieces:

```typescript
import { computed, onMounted, ref, watch } from 'vue';

import { useAppContext } from '@app/context';
import AppIcon from '@shared/components/AppIcon.vue';
import {
  createCompanyDevice,
  deleteCompanyDevice,
  listCompanyDevices,
  updateCompanyDevice,
} from '../api/devices';
import type { CompanyDevice, CompanyDevicePayload, CompanyDeviceStatus } from '../types';
import { buildCompanyDeviceXlsxWorkbook, companyDeviceStatusText } from '../utils/export';

interface DeviceDialogState {
  mode: 'create' | 'edit';
  deviceId: number | null;
}

type DeviceFormErrors = Partial<Record<keyof CompanyDevicePayload, string>>;

const { canUsePageAction, requestConfirm, showToast } = useAppContext();
const devices = ref<CompanyDevice[]>([]);
const selectedIds = ref<Set<number>>(new Set());
const statusFilter = ref<'' | CompanyDeviceStatus>('');
const categoryFilter = ref('');
const search = ref('');
const page = ref(1);
const pageSize = 10;
const isLoading = ref(false);
const isSaving = ref(false);
const loadError = ref('');
const dialogError = ref('');
const deviceDialog = ref<DeviceDialogState | null>(null);
const deviceForm = ref<CompanyDevicePayload>(createDeviceDraft());
const formErrors = ref<DeviceFormErrors>({});
```

Use these functions for behavior:

```typescript
function createDeviceDraft(device?: CompanyDevice | null): CompanyDevicePayload {
  return {
    name: device?.name ?? '',
    category: device?.category ?? '固定资产',
    code: device?.code ?? '',
    spec: device?.spec ?? '',
    status: device?.status ?? 'using',
    user: device?.user ?? '',
    brand: device?.brand ?? '',
    purchaseTime: device?.purchaseTime ?? null,
    remark: device?.remark ?? '',
  };
}

function devicePayload(form: CompanyDevicePayload): CompanyDevicePayload {
  return {
    name: form.name.trim(),
    category: form.category.trim() || '固定资产',
    code: form.code.trim(),
    spec: form.spec.trim(),
    status: form.status,
    user: form.user.trim(),
    brand: form.brand.trim(),
    purchaseTime: form.purchaseTime || null,
    remark: form.remark.trim(),
  };
}

function validateDeviceForm() {
  const errors: DeviceFormErrors = {};
  if (!deviceForm.value.name.trim()) errors.name = '请输入资产名称';
  if (!deviceForm.value.category.trim()) errors.category = '请输入资产类别';
  formErrors.value = errors;
  return Object.keys(errors).length === 0;
}

async function loadDevices() {
  isLoading.value = true;
  loadError.value = '';
  try {
    devices.value = await listCompanyDevices();
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : '设备列表加载失败';
  } finally {
    isLoading.value = false;
  }
}

function openCreateDeviceDialog() {
  deviceDialog.value = { mode: 'create', deviceId: null };
  deviceForm.value = createDeviceDraft();
  formErrors.value = {};
  dialogError.value = '';
}

function openEditDeviceDialog(device: CompanyDevice) {
  deviceDialog.value = { mode: 'edit', deviceId: device.id };
  deviceForm.value = createDeviceDraft(device);
  formErrors.value = {};
  dialogError.value = '';
}

function closeDeviceDialog() {
  if (isSaving.value) return;
  deviceDialog.value = null;
  dialogError.value = '';
}

async function saveDeviceDialog() {
  if (!deviceDialog.value || isSaving.value || !validateDeviceForm()) return;
  isSaving.value = true;
  dialogError.value = '';
  try {
    const payload = devicePayload(deviceForm.value);
    const saved = deviceDialog.value.mode === 'edit' && deviceDialog.value.deviceId
      ? await updateCompanyDevice(deviceDialog.value.deviceId, payload)
      : await createCompanyDevice(payload);
    devices.value = deviceDialog.value.mode === 'edit'
      ? devices.value.map((device) => (device.id === saved.id ? saved : device))
      : [saved, ...devices.value];
    showToast('保存成功', `设备「${saved.name}」已保存。`);
    closeDeviceDialog();
  } catch (error) {
    dialogError.value = error instanceof Error ? error.message : '设备保存失败';
  } finally {
    isSaving.value = false;
  }
}
```

Use `requestConfirm` for deletion:

```typescript
function confirmDeleteDevice(device: CompanyDevice) {
  requestConfirm('删除设备', `确定删除设备「${device.name}」？`, '删除', async () => {
    await deleteCompanyDevice(device.id);
    devices.value = devices.value.filter((item) => item.id !== device.id);
    const next = new Set(selectedIds.value);
    next.delete(device.id);
    selectedIds.value = next;
    showToast('删除成功', `设备「${device.name}」已删除。`);
  });
}

function confirmDeleteSelectedDevices() {
  const selectedDevices = devices.value.filter((device) => selectedIds.value.has(device.id));
  if (!selectedDevices.length) return;
  requestConfirm('批量删除设备', `确定删除选中的 ${selectedDevices.length} 台设备？`, '删除', async () => {
    for (const device of selectedDevices) {
      await deleteCompanyDevice(device.id);
    }
    const deletedIds = new Set(selectedDevices.map((device) => device.id));
    devices.value = devices.value.filter((device) => !deletedIds.has(device.id));
    selectedIds.value = new Set();
    showToast('删除成功', `已删除 ${selectedDevices.length} 台设备。`);
  });
}
```

Use this export behavior:

```typescript
function exportDevices() {
  const selectedDevices = filteredDevices.value.filter((device) => selectedIds.value.has(device.id));
  const exportRows = selectedDevices.length ? selectedDevices : filteredDevices.value;
  if (!exportRows.length) {
    showToast('导出失败', '当前没有可导出的设备。');
    return;
  }
  const date = new Date().toISOString().slice(0, 10);
  downloadFile(buildCompanyDeviceXlsxWorkbook(exportRows), `company-devices-${date}.xlsx`, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
  showToast('导出成功', `已导出 ${exportRows.length} 台设备。`);
}

function downloadFile(content: BlobPart, filename: string, type: string) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}
```

Keep pagination, filtering, checkbox toggles, and `statusText` behavior, but derive `statusText` by calling `companyDeviceStatusText`.

- [ ] **Step 4: Update the template**

In `DeviceManager.vue`, keep the table layout and replace placeholder buttons with permission-aware controls:

```vue
<button v-if="canUsePageAction('companyDevices', 'delete')" class="device-button danger" type="button" :disabled="!selectedIds.size" @click="confirmDeleteSelectedDevices">删除</button>
<button v-if="canUsePageAction('companyDevices', 'create')" class="device-button primary" type="button" @click="openCreateDeviceDialog"><AppIcon name="plus" :size="15" />添加</button>
<button v-if="canUsePageAction('companyDevices', 'export')" class="device-button primary" type="button" @click="exportDevices"><AppIcon name="download" :size="15" />导出Excel</button>
```

Wrap filters with `v-if="canUsePageAction('companyDevices', 'filter')"` and keep query/reset controls inside that permission boundary.

For row actions, use:

```vue
<button v-if="canUsePageAction('companyDevices', 'edit')" class="device-button primary" type="button" @click="openEditDeviceDialog(device)">编辑</button>
<button v-if="canUsePageAction('companyDevices', 'delete')" class="device-button danger" type="button" @click="confirmDeleteDevice(device)">删除</button>
```

Add the editor form at the end of the section:

```vue
<div v-if="deviceDialog" class="modal-backdrop">
  <form class="device-form-modal" @submit.prevent="saveDeviceDialog">
    <button class="modal-close" type="button" :disabled="isSaving" @click="closeDeviceDialog"><AppIcon name="x" :size="16" /></button>
    <h2>{{ deviceDialog.mode === 'edit' ? '编辑设备' : '添加设备' }}</h2>
    <p v-if="dialogError" class="device-form-error">{{ dialogError }}</p>
    <label :class="{ invalid: formErrors.name }">
      <span>资产名称</span>
      <input v-model="deviceForm.name" autofocus />
      <em v-if="formErrors.name">{{ formErrors.name }}</em>
    </label>
    <label :class="{ invalid: formErrors.category }">
      <span>资产类别</span>
      <input v-model="deviceForm.category" list="device-category-options" />
      <em v-if="formErrors.category">{{ formErrors.category }}</em>
    </label>
    <datalist id="device-category-options">
      <option value="固定资产"></option>
      <option value="耗材"></option>
    </datalist>
    <label><span>资产编码</span><input v-model="deviceForm.code" /></label>
    <label><span>规格说明</span><input v-model="deviceForm.spec" /></label>
    <label>
      <span>资产状态</span>
      <select v-model="deviceForm.status">
        <option value="using">使用中</option>
        <option value="idle">闲置</option>
        <option value="repair">维修中</option>
      </select>
    </label>
    <label><span>使用人员</span><input v-model="deviceForm.user" /></label>
    <label><span>品牌名称</span><input v-model="deviceForm.brand" /></label>
    <label><span>采购时间</span><input v-model="deviceForm.purchaseTime" type="date" /></label>
    <label class="device-form-wide"><span>备注</span><textarea v-model="deviceForm.remark" rows="3"></textarea></label>
    <div class="device-form-actions">
      <button type="button" :disabled="isSaving" @click="closeDeviceDialog">取消</button>
      <button class="primary" type="submit" :disabled="isSaving">{{ isSaving ? '保存中...' : '保存' }}</button>
    </div>
  </form>
</div>
```

- [ ] **Step 5: Update device manager styles**

Add modal and state styles to `frontend/src/styles/tools/device-manager.css`:

```css
.device-loading,
.device-load-error {
  min-height: 86px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: #64748b;
}

.device-load-error {
  color: #b91c1c;
}

.device-button svg {
  flex: 0 0 auto;
}

.device-form-modal {
  position: relative;
  width: min(760px, calc(100vw - 36px));
  max-height: calc(100vh - 48px);
  overflow: auto;
  border-radius: 6px;
  background: #fff;
  padding: 22px 24px 20px;
  box-shadow: 0 24px 60px rgba(15, 23, 42, 0.22);
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px 16px;
}

.device-form-modal h2,
.device-form-error,
.device-form-wide,
.device-form-actions {
  grid-column: 1 / -1;
}

.device-form-modal h2 {
  margin: 0 32px 4px 0;
  color: #111827;
  font-size: 18px;
  font-weight: 700;
}

.device-form-modal label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: #374151;
  font-size: 13px;
  font-weight: 600;
}

.device-form-modal input,
.device-form-modal select,
.device-form-modal textarea {
  width: 100%;
  border: 1px solid #d3dbe7;
  border-radius: 4px;
  background: #fff;
  padding: 0 10px;
  color: #111827;
  font: inherit;
}

.device-form-modal input,
.device-form-modal select {
  height: 34px;
}

.device-form-modal textarea {
  min-height: 76px;
  padding-top: 8px;
  resize: vertical;
}

.device-form-modal label.invalid input {
  border-color: #ef4444;
}

.device-form-modal em,
.device-form-error {
  color: #dc2626;
  font-size: 12px;
  font-style: normal;
  font-weight: 500;
}

.device-form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding-top: 6px;
}

.device-form-actions button {
  height: 34px;
  border: 1px solid #d3dbe7;
  border-radius: 4px;
  background: #fff;
  padding: 0 16px;
  color: #1f2937;
  cursor: pointer;
  font-weight: 700;
}

.device-form-actions button.primary {
  border-color: #087cff;
  background: #087cff;
  color: #fff;
}
```

Add a media query:

```css
@media (max-width: 760px) {
  .device-form-modal {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 6: Run component test and verify green**

Run:

```powershell
npm --prefix frontend run test:run -- src/features/company/__tests__/DeviceManager.structure.test.ts
```

Expected: PASS.

- [ ] **Step 7: Commit persisted device UI**

Run:

```powershell
git add frontend/src/features/company/components/DeviceManager.vue frontend/src/features/company/__tests__/DeviceManager.structure.test.ts frontend/src/styles/tools/device-manager.css
git commit -m "feat: 实现设备管理前端"
```

Expected: commit only Task 3 frontend UI files.

---

### Task 4: End-To-End Verification

**Files:**
- No production file changes expected.
- Uses all files from Tasks 1, 2, and 3.

**Interfaces:**
- Consumes: backend app, API, frontend API client, export utility, and component.
- Produces: verified implementation ready for user testing.

- [ ] **Step 1: Run backend targeted tests**

Run:

```powershell
wsl.exe --cd /mnt/c/Users/kaikai/Desktop/django-vue/backend -e env APP_CONFIG_FILE=/mnt/c/Users/kaikai/Desktop/django-vue/config/local.app.conf /root/venv-opstool/bin/python manage.py test company_assets --noinput
```

Expected: PASS.

- [ ] **Step 2: Run frontend targeted tests**

Run:

```powershell
npm --prefix frontend run test:run -- src/features/company/__tests__/DeviceManager.structure.test.ts src/features/company/utils/__tests__/deviceExport.test.ts
```

Expected: PASS.

- [ ] **Step 3: Run migration check**

Run:

```powershell
wsl.exe --cd /mnt/c/Users/kaikai/Desktop/django-vue/backend -e env APP_CONFIG_FILE=/mnt/c/Users/kaikai/Desktop/django-vue/config/local.app.conf /root/venv-opstool/bin/python manage.py migrate --check
```

Expected: PASS if local database already has the new migration applied, or a clear unapplied migration message if the user still needs to run `manage.py migrate`.

- [ ] **Step 4: Run frontend build**

Run:

```powershell
npm --prefix frontend run build
```

Expected: PASS and Vite build completes without TypeScript errors.

- [ ] **Step 5: Inspect final diff**

Run:

```powershell
git status --short
git diff --stat
```

Expected: only feature files from this plan remain changed, plus pre-existing user changes that were present before implementation.

- [ ] **Step 6: Final commit**

If Tasks 1 through 3 were not already committed task-by-task, commit the remaining feature files:

```powershell
git add backend/company_assets backend/ops_tool/settings.py backend/operations/urls.py backend/system_management/services.py backend/system_management/middleware.py frontend/src/features/company frontend/src/styles/tools/device-manager.css
git commit -m "feat: 实现设备管理持久化"
```

Expected: no unrelated files staged.
