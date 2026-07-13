import { describe, expect, it } from 'vitest';

import {
  hostExportColumnOptions as compatibilityHostExportColumnOptions,
  useHostManager as compatibilityUseHostManager,
} from '../../../../composables/features/useHostManager';
import type {
  HostExportColumnKey as CompatibilityHostExportColumnKey,
  HostExportColumnOption as CompatibilityHostExportColumnOption,
  HostExportOptions as CompatibilityHostExportOptions,
  HostExportScope as CompatibilityHostExportScope,
  HostTransferFormat as CompatibilityHostTransferFormat,
} from '../../../../composables/features/useHostManager';
import {
  hostExportColumnOptions as featureHostExportColumnOptions,
  useHostManager as featureUseHostManager,
} from '../useHostManager';
import type {
  HostExportColumnKey as FeatureHostExportColumnKey,
  HostExportColumnOption as FeatureHostExportColumnOption,
  HostExportOptions as FeatureHostExportOptions,
  HostExportScope as FeatureHostExportScope,
  HostTransferFormat as FeatureHostTransferFormat,
} from '../useHostManager';

type Equal<Left, Right> =
  (<Value>() => Value extends Left ? 1 : 2) extends
  (<Value>() => Value extends Right ? 1 : 2)
    ? true
    : false;

const publicTypeCompatibility: [
  Equal<CompatibilityHostTransferFormat, FeatureHostTransferFormat>,
  Equal<CompatibilityHostExportScope, FeatureHostExportScope>,
  Equal<CompatibilityHostExportColumnKey, FeatureHostExportColumnKey>,
  Equal<CompatibilityHostExportColumnOption, FeatureHostExportColumnOption>,
  Equal<CompatibilityHostExportOptions, FeatureHostExportOptions>,
] = [true, true, true, true, true];

void publicTypeCompatibility;

describe('useHostManager compatibility exports', () => {
  it('keeps old and feature-local runtime exports identical', () => {
    expect(compatibilityUseHostManager).toBe(featureUseHostManager);
    expect(compatibilityHostExportColumnOptions).toBe(featureHostExportColumnOptions);
  });
});
