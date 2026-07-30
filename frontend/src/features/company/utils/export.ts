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
  if (status === 'repair') return '维修';
  if (status === 'scrapped') return '报废';
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

function buildXlsxWorkbookFromRows(
  rows: CompanyDeviceExportRow[],
  columns: readonly CompanyDeviceExportColumn[],
  sheetName: string,
) {
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
  const columnXml = columns
    .map((column, index) => `<col min="${index + 1}" max="${index + 1}" width="${Math.max(10, column.width)}" customWidth="1"/>`)
    .join('');
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
