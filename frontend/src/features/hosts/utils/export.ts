import type {
  ExportColumn,
  ExportRow,
  HostExportColumnKey,
  HostExportColumnOption,
  HostManagementExport,
  ManagedHost,
} from '../types';

export const hostExportColumnOptions: readonly HostExportColumnOption[] = [
  { field: 'group', label: '主机分组', width: 18 },
  { field: 'name', label: '节点', width: 22 },
  { field: 'ip', label: 'IP地址', width: 24 },
  { field: 'machine', label: '机器名称', width: 24 },
  { field: 'systemArch', label: '系统架构', width: 16 },
  { field: 'systemType', label: '系统类型', width: 16 },
  { field: 'config', label: '配置信息', width: 18 },
  { field: 'platformType', label: '平台类型', width: 16 },
  { field: 'user', label: '用户', width: 16 },
  { field: 'port', label: '端口', width: 10 },
  { field: 'createdAt', label: '创建时间', width: 22 },
  { field: 'updatedAt', label: '更新时间', width: 22 },
  { field: 'creator', label: '创建者', width: 16 },
  { field: 'remark', label: '备注', width: 28 },
  { field: 'status', label: '状态', width: 14 },
] as const;

export function buildHostExportPayload(
  hosts: ManagedHost[],
  columns: readonly HostExportColumnOption[],
  groupName: (groupId: number) => string,
): HostManagementExport {
  return {
    version: 1,
    groups: [],
    credentials: [],
    hosts: hosts.map((host) =>
      columns.reduce<ExportRow>((row, column) => {
        row[column.field] = formatHostExportValue(host, column.field, groupName);
        return row;
      }, {}),
    ),
  };
}

export function formatHostExportValue(
  host: ManagedHost,
  field: HostExportColumnKey,
  groupName: (groupId: number) => string,
): string | number | boolean | null {
  if (field === 'group') return groupName(host.group);
  if (field === 'ip') return [host.publicIp, host.privateIp].filter(Boolean).join('\n');
  if (field === 'machine') return host.verified ? host.machineName || '' : '';
  if (field === 'config') return host.verified && host.cpu > 0 && host.memory > 0 ? `${host.cpu}核 ${host.memory}GB` : '';
  if (field === 'platformType') return host.platformType || (host.os === 'windows' ? 'windows' : 'linux');
  if (field === 'user') return host.loginUser || '';
  if (field === 'status') return host.verified ? '已验证' : host.verifyStatus === 'failed' ? '验证失败' : '未验证';
  if (field === 'createdAt') return host.createdAt || '';
  if (field === 'updatedAt') return host.updatedAt || '';
  if (field === 'creator') return host.creator || '';
  if (field === 'remark') return host.remark || '';
  if (field === 'port') return host.port || 22;
  if (field === 'systemArch') return host.systemArch || '';
  if (field === 'systemType') return host.systemType || '';
  return host.name;
}

const exportSheets: Array<{ key: keyof HostManagementExport; title: string; columns: ExportColumn[] }> = [
  {
    key: 'hosts',
    title: '主机清单',
    columns: [{ field: 'name', label: '名称', width: 34 }],
  },
];

export function buildXlsxWorkbook(payload: HostManagementExport, hostColumns: readonly ExportColumn[] = exportSheets[0].columns) {
  const rows = payload.hosts;
  const worksheet = buildXlsxWorksheet(rows, hostColumns);
  return createZip([
    { name: '[Content_Types].xml', content: stringToBytes(`<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>`) },
    { name: '_rels/.rels', content: stringToBytes(`<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>`) },
    { name: 'xl/workbook.xml', content: stringToBytes(`<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="主机清单" sheetId="1" r:id="rId1"/></sheets></workbook>`) },
    { name: 'xl/_rels/workbook.xml.rels', content: stringToBytes(`<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>`) },
    { name: 'xl/styles.xml', content: stringToBytes(`<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="2"><font><sz val="11"/><name val="Microsoft YaHei"/></font><font><b/><sz val="11"/><name val="Microsoft YaHei"/></font></fonts><fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="2"><xf numFmtId="49" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="49" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>`) },
    { name: 'xl/worksheets/sheet1.xml', content: stringToBytes(worksheet) },
  ]);
}

function buildXlsxWorksheet(rows: ExportRow[], columns: readonly ExportColumn[]) {
  const columnXml = columns.map((column, index) => `<col min="${index + 1}" max="${index + 1}" width="${Math.max(10, column.width)}" customWidth="1"/>`).join('');
  const header = `<row r="1">${columns.map((column, index) => buildXlsxCell(1, index + 1, column.label, 1)).join('')}</row>`;
  const body = rows
    .map((row, rowIndex) => {
      const excelRow = rowIndex + 2;
      return `<row r="${excelRow}">${columns.map((column, columnIndex) => buildXlsxCell(excelRow, columnIndex + 1, formatExportCell(column.field, row[column.field]))).join('')}</row>`;
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

    centralParts.push(
      concatBytes([
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
      ]),
    );

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
  const view = new DataView(bytes.buffer);
  view.setUint16(0, value, true);
  return bytes;
}

function uint32(value: number) {
  const bytes = new Uint8Array(4);
  const view = new DataView(bytes.buffer);
  view.setUint32(0, value >>> 0, true);
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

export function buildExcelWorkbook(payload: HostManagementExport, hostColumns: readonly ExportColumn[] = exportSheets[0].columns) {
  const sheetsConfig: Array<{ key: keyof HostManagementExport; title: string; columns: readonly ExportColumn[] }> = [
    { key: 'hosts', title: '主机清单', columns: hostColumns },
  ];
  const sheets = sheetsConfig
    .map((sheet) => {
      const rows = payload[sheet.key] as ExportRow[];
      const colgroup = sheet.columns.map((column) => `<col style="width:${column.width * 8}px">`).join('');
      const header = sheet.columns.map((column) => `<th data-field="${escapeHtml(column.field)}">${escapeHtml(column.label)}</th>`).join('');
      const body = rows
        .map((row) => `<tr>${sheet.columns.map((column) => `<td>${escapeHtml(formatExportCell(column.field, row[column.field]))}</td>`).join('')}</tr>`)
        .join('');
      return `<table id="sheet-${sheet.key}" data-sheet="${sheet.key}"><caption>${sheet.title}</caption><colgroup>${colgroup}</colgroup><thead><tr>${header}</tr></thead><tbody>${body}</tbody></table>`;
    })
    .join('<br>');

  return `<!doctype html><html><head><meta charset="utf-8"><style>body{font-family:"Microsoft YaHei",Arial,sans-serif;color:#1f2937}table{border-collapse:collapse;margin-bottom:28px;table-layout:fixed}caption{font-size:18px;font-weight:700;text-align:left;padding:12px 0 10px;color:#0f172a}th,td{border:1px solid #d9e2ef;padding:8px 10px;mso-number-format:"\\@";white-space:pre-wrap;vertical-align:middle}th{background:#eef4ff;color:#173252;font-weight:700;text-align:center}td{background:#fff}tbody tr:nth-child(even) td{background:#f8fbff}</style></head><body>${sheets}</body></html>`;
}

export function parseExcelWorkbook(text: string): HostManagementExport {
  const document = new DOMParser().parseFromString(text, 'text/html');
  return {
    version: 1,
    groups: parseExcelSheet(document, 'groups'),
    hosts: parseExcelSheet(document, 'hosts'),
    credentials: parseExcelSheet(document, 'credentials'),
  };
}

function parseExcelSheet(document: Document, key: string): ExportRow[] {
  const table = document.querySelector(`#sheet-${key}, table[data-sheet="${key}"]`);
  if (!table) return [];
  const rows = Array.from(table.querySelectorAll('tr'));
  const headers = Array.from(rows.shift()?.querySelectorAll('th,td') ?? []).map((cell) =>
    resolveExportField(cell.getAttribute('data-field') || normalizeCell(cell.textContent)),
  );
  if (!headers.length) return [];

  return rows
    .map((row) => {
      const cells = Array.from(row.querySelectorAll('td,th'));
      return headers.reduce<ExportRow>((result, field, index) => {
        if (field) result[field] = parseExportCell(field, normalizeCell(cells[index]?.textContent));
        return result;
      }, {});
    })
    .filter((row) => Object.values(row).some((value) => value !== ''));
}

export function parseExportCell(field: string, value: string): string | number | boolean {
  if (['sortOrder', 'port', 'cpu', 'memory'].includes(field)) return Number.parseInt(value || '0', 10);
  if (field === 'verified') return ['true', '1', 'yes', '是', '已验证', 'verified'].includes(value.toLowerCase());
  return value;
}

function resolveExportField(value: string) {
  const normalized = normalizeCell(value);
  return excelHeaderAliases[normalized] ?? exportSheets.flatMap((sheet) => sheet.columns).find((column) => column.label === normalized || column.field === normalized)?.field ?? normalized;
}

const excelHeaderAliases: Record<string, string> = {
  名称: 'name',
  节点: 'name',
  机器别名: 'name',
  账号名称: 'name',
  分组名称: 'name',
  分组路径: 'path',
  上级路径: 'parentPath',
  排序: 'sortOrder',
  主机分组: 'groupPath',
  '公网 IP': 'publicIp',
  '内网 IP': 'privateIp',
  端口: 'port',
  机器名称: 'machineName',
  CPU: 'cpu',
  '内存(GB)': 'memory',
  系统: 'os',
  验证状态: 'verified',
  备注: 'remark',
  密钥文件名: 'privateKeyName',
};

export function formatExportCell(field: string, value: string | number | boolean | null | undefined) {
  if (value === null || value === undefined) return '';
  if (field === 'verified') return value ? '已验证' : '未验证';
  return String(value);
}

function normalizeCell(value: string | null | undefined) {
  return (value ?? '').replace(/\u00a0/g, ' ').trim();
}

function escapeHtml(value: string) {
  return value.replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char] ?? char);
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
