# 设备管理持久化设计

## 目标

在“公司管理 / 设备管理”中实现可持久化的设备资产管理能力：添加、编辑、删除、批量删除和导出 Excel。交互风格参考主机管理，数据保存到 Django 数据库，刷新页面后不丢失。

## 范围

本次实现覆盖当前设备列表已有字段：

- 资产名称
- 资产类别
- 资产编码
- 规格说明
- 资产状态
- 使用人员
- 品牌名称
- 采购时间
- 备注

同时在后端保存创建时间、更新时间和创建人，用于后续审计或列表扩展。

本次不实现设备导入、标签体系、复制设备、查看详情页、设备分组或附件上传。当前页面已有“复制”“设置标签”“查看”入口如无实际业务需求，应移除或置为后续能力，避免出现不可用按钮。

## 后端架构

新增独立 Django app：`company_assets`。

新增模型 `CompanyDevice`：

- `name`: 必填，资产名称
- `category`: 必填，默认“固定资产”
- `code`: 可选，资产编码
- `spec`: 可选，规格说明
- `status`: 枚举，`using` / `idle` / `repair`
- `user`: 可选，使用人员
- `brand`: 可选，品牌名称
- `purchase_time`: 可选日期
- `remark`: 可选备注
- `created_by`: 可选外键，关联创建人
- `created_at`: 自动创建时间
- `updated_at`: 自动更新时间

排序按 `-created_at, -id`，让新设备优先出现在列表前面。资产编码暂不设唯一约束，避免历史编号为空或重复时阻塞录入。

## 后端 API

新增路由前缀：`/api/company-devices/`。

接口：

- `GET /api/company-devices/`: 返回设备列表
- `POST /api/company-devices/`: 新增设备
- `PUT /api/company-devices/<id>/`: 编辑设备
- `DELETE /api/company-devices/<id>/`: 删除单台设备

API 返回字段使用前端习惯的 camelCase：

- `purchaseTime`
- `createdAt`
- `updatedAt`
- `createdBy`

接口错误返回沿用现有 `{ "error": "..." }` 格式。

## 权限设计

现有 `access_companyDevices` 保留为页面访问权限。

新增设备管理动作权限：

- `action_companyDevices_create`: 添加设备
- `action_companyDevices_edit`: 编辑设备
- `action_companyDevices_delete`: 删除设备
- `action_companyDevices_export`: 导出 Excel
- `action_companyDevices_filter`: 查询和筛选

后端接口按动作权限拦截：

- `GET` 需要页面访问权限
- `POST` 需要 `create`
- `PUT` 需要 `edit`
- `DELETE` 需要 `delete`

前端按钮也按相同动作权限显隐，保持与主机管理一致。

## 前端结构

设备管理继续放在 `frontend/src/features/company/components/DeviceManager.vue`，并新增配套文件：

- `frontend/src/features/company/api/devices.ts`
- `frontend/src/features/company/types.ts`
- `frontend/src/features/company/utils/export.ts`

组件状态：

- `devices`: 后端加载的完整设备列表
- `selectedIds`: 当前勾选设备
- `statusFilter` / `categoryFilter` / `search`: 筛选条件
- `deviceDialog`: 添加/编辑弹窗状态
- `deviceForm`: 表单草稿
- `formErrors`: 基础校验错误
- `isLoading` / `isSaving`: 加载和保存状态

添加和编辑共用一个表单弹窗。列表行操作保留“编辑”“删除”；顶部操作保留“添加”“删除”“导出 Excel”“查询”“重置”。批量删除只对已选设备生效，删除前用确认弹窗或 `window.confirm` 明确提示数量。

## Excel 导出

导出在浏览器端生成 `.xlsx` 文件，复用主机管理已有的轻量 xlsx 生成思路，避免新增前端依赖。

默认导出当前筛选后的设备列表；如果存在勾选设备，则导出已勾选设备。文件名格式：

`company-devices-YYYY-MM-DD.xlsx`

导出列与当前列表字段保持一致：

- 资产名称
- 资产类别
- 资产编码
- 规格说明
- 资产状态
- 使用人员
- 品牌名称
- 采购时间
- 备注

状态值导出为中文：使用中、闲置、维修中。

## 数据流

页面进入设备管理时调用 `listCompanyDevices()` 加载数据。

新增设备：

1. 点击“添加”打开空表单。
2. 前端校验必填字段和日期格式。
3. 调用 `POST /api/company-devices/`。
4. 将返回记录插入列表或重新加载列表。
5. 关闭弹窗并提示成功。

编辑设备：

1. 点击行内“编辑”用当前记录填充表单。
2. 保存时调用 `PUT /api/company-devices/<id>/`。
3. 用返回记录替换本地列表中的旧记录。
4. 关闭弹窗并提示成功。

删除设备：

1. 单行删除或顶部批量删除先确认。
2. 逐条调用 `DELETE /api/company-devices/<id>/`。
3. 从本地列表和选中集合中移除成功删除的记录。
4. 提示删除数量。

## 错误处理

- 加载失败：在页面显示错误提示，并保留刷新按钮。
- 新增/编辑失败：错误显示在弹窗内，不关闭表单。
- 删除失败：保留未删除设备，并提示后端错误。
- 导出失败：提示导出错误，不改变页面状态。
- 无权限：按钮隐藏；后端仍返回 403 兜底。

## 测试

后端测试：

- 创建设备并校验响应字段、创建人、默认状态。
- 编辑设备并校验字段更新。
- 删除设备并校验记录不存在。
- 无权限用户访问动作接口返回 403。
- 有页面访问权限但无删除动作权限时不能删除。

前端测试：

- 设备管理页面包含添加、删除、导出 Excel、编辑按钮。
- 添加/编辑弹窗绑定完整字段。
- 删除按钮在未选中时禁用，选中后可用。
- 导出函数能生成包含中文表头和状态中文值的 xlsx 内容。
- 页面按钮按 `companyDevices` 动作权限显隐。

## 验收标准

- 执行迁移后，设备新增、编辑、删除的数据写入数据库。
- 刷新页面后设备数据仍存在。
- 勾选设备后可批量删除。
- 导出的 Excel 可被 Excel 或 WPS 打开，表头和值正确。
- 普通权限用户只能看到被授权的设备管理按钮。
