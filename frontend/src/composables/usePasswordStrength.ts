import { computed, type Ref } from 'vue';

export interface PasswordRule {
  key: 'length' | 'number' | 'lower' | 'upper';
  label: string;
  message: string;
  valid: boolean;
}

export type PasswordStrengthLevel = 'empty' | 'weak' | 'medium' | 'strong';

export function usePasswordStrength(password: Ref<string>) {
  const rules = computed(() => getPasswordRules(password.value));
  const passedCount = computed(() => rules.value.filter((rule) => rule.valid).length);
  const isStrong = computed(() => rules.value.every((rule) => rule.valid));
  const level = computed<PasswordStrengthLevel>(() => passwordStrengthLevel(password.value, passedCount.value));
  const label = computed(() => passwordStrengthLabel(level.value));
  const hint = computed(() => passwordStrengthHint(password.value, rules.value));

  return {
    rules,
    passedCount,
    isStrong,
    level,
    label,
    className: level,
    hint,
  };
}

export function getPasswordRules(password: string): PasswordRule[] {
  return [
    { key: 'length', label: '长度', message: '密码长度至少为 8 位', valid: password.length >= 8 },
    { key: 'number', label: '数字', message: '需包含数字', valid: /\d/.test(password) },
    { key: 'lower', label: '小写', message: '需包含小写字母', valid: /[a-z]/.test(password) },
    { key: 'upper', label: '大写', message: '需包含大写字母', valid: /[A-Z]/.test(password) },
  ];
}

export function passwordsMismatch(password: string, confirmPassword: string) {
  return Boolean(confirmPassword) && password !== confirmPassword;
}

function passwordStrengthLevel(password: string, passedCount: number): PasswordStrengthLevel {
  if (!password) return 'empty';
  if (passedCount <= 1) return 'weak';
  if (passedCount <= 3) return 'medium';
  return 'strong';
}

function passwordStrengthLabel(level: PasswordStrengthLevel) {
  if (level === 'weak') return '弱';
  if (level === 'medium') return '中';
  if (level === 'strong') return '强';
  return '';
}

function passwordStrengthHint(password: string, rules: PasswordRule[]) {
  if (!password) return '请输入至少8位，包含数字、小写和大写字母的密码。';
  const missing = rules.filter((rule) => !rule.valid).map((rule) => rule.message);
  return missing.length ? missing.join('，') : '密码强度符合要求。';
}
