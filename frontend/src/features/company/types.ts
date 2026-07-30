export type CompanyDeviceStatus = 'using' | 'idle' | 'repair' | 'scrapped';

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
