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
    expect(companyDeviceStatusText('repair')).toBe('维修');
    expect(companyDeviceStatusText('scrapped')).toBe('报废');
    expect(buildCompanyDeviceExportRows([{ ...device, code: '', purchaseTime: null }])).toEqual([
      {
        name: '笔记本',
        category: '固定资产',
        code: '',
        spec: 'i7/32GB/1TB',
        status: '维修',
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
    expect(workbook).toContain('维修');
  });
});
