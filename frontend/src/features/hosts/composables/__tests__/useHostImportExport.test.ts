import { computed } from 'vue';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { useHostImportExport } from '../useHostImportExport';

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('useHostImportExport', () => {
  it('downloads the host import template as xlsx before revoking the blob URL', () => {
    let downloadedBlob: Blob | null = null;
    const link = {
      href: '',
      download: '',
      click: vi.fn(),
      remove: vi.fn(),
    };
    const createObjectURL = vi.fn((blob: Blob) => {
      downloadedBlob = blob;
      return 'blob:host-import-template';
    });
    const revokeObjectURL = vi.fn();
    const setTimeout = vi.fn();

    vi.stubGlobal('URL', { createObjectURL, revokeObjectURL });
    vi.stubGlobal('document', {
      createElement: vi.fn(() => link),
      body: { appendChild: vi.fn() },
    });
    vi.stubGlobal('window', { setTimeout });

    const showToast = vi.fn();
    const manager = useHostImportExport({
      showToast,
      visibleManagedHosts: computed(() => []),
      hostGroupName: () => '',
      loadHostManagement: vi.fn(),
    });

    expect(manager.downloadHostImportTemplate()).toBe(true);

    expect(createObjectURL).toHaveBeenCalledOnce();
    expect(downloadedBlob?.type).toBe('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
    expect(link.href).toBe('blob:host-import-template');
    expect(link.download).toBe('host-import-template.xlsx');
    expect(link.click).toHaveBeenCalledOnce();
    expect(link.remove).toHaveBeenCalledOnce();
    expect(revokeObjectURL).not.toHaveBeenCalled();
    expect(setTimeout).toHaveBeenCalledWith(expect.any(Function), 0);

    const revokeLater = setTimeout.mock.calls[0][0] as () => void;
    revokeLater();
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:host-import-template');
    expect(showToast).toHaveBeenCalledWith('模板已下载', expect.stringContaining('主机分组'));
  });
});
