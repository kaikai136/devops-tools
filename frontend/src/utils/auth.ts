import type { AuthEntry } from '../types';

export function normalizeTotpAlgorithm(value: string) {
  return value.replace('-', '').toUpperCase() || 'SHA1';
}

export function formatTotpAlgorithm(value: string) {
  const normalized = normalizeTotpAlgorithm(value);
  return normalized.replace('SHA', 'SHA-');
}

export function formatBackupTimestamp(date = new Date()) {
  return `${date.getFullYear()}${String(date.getMonth() + 1).padStart(2, '0')}${String(date.getDate()).padStart(2, '0')}-${String(date.getHours()).padStart(2, '0')}${String(date.getMinutes()).padStart(2, '0')}${String(date.getSeconds()).padStart(2, '0')}`;
}

export function buildOtpAuthUri(entry: Pick<AuthEntry, 'issuer' | 'account_name' | 'secret' | 'digits' | 'period' | 'algorithm'>) {
  const issuer = entry.issuer || 'Authenticator';
  const account = entry.account_name || 'Account';
  const label = encodeURIComponent(`${issuer}:${account}`);
  const params = new URLSearchParams({
    secret: entry.secret,
    issuer,
    digits: String(entry.digits),
    period: String(entry.period),
    algorithm: normalizeTotpAlgorithm(entry.algorithm),
  });
  return `otpauth://totp/${label}?${params.toString()}`;
}
