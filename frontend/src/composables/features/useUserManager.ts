import { computed, onMounted, ref, watch } from 'vue';

import { apiDelete, apiGet, apiPost, apiPut } from '../../api';
import { useColumnVisibility, type TableColumnOption } from '../useColumnVisibility';
import { passwordsMismatch, usePasswordStrength } from '../usePasswordStrength';
import { errorMessage } from '../../utils/errors';

export interface SystemUser {
  id: number;
  username: string;
  email: string;
  firstName: string;
  isActive: boolean;
  isStaff: boolean;
  isSuperuser: boolean;
  isBuiltinAdmin?: boolean;
  canLogin?: boolean;
  twoFactorEnabled?: boolean;
  twoFactorRequired?: boolean;
  twoFactorResetRequired?: boolean;
  twoFactorStatus?: 'disabled' | 'required' | 'enabled';
  sessionAuditEnabled?: boolean;
  lastLogin: string | null;
  dateJoined: string | null;
  roleIds: number[];
}

export interface SystemRole {
  id: number;
  name: string;
  permissionIds?: number[];
}

type ListApiResponse<T> = T[] | { results?: T[]; data?: T[]; items?: T[] };

export interface UserForm {
  username: string;
  email: string;
  firstName: string;
  password: string;
  confirmPassword: string;
  mfaFlag: string;
  isActive: boolean;
  isStaff: boolean;
  roleIds: number[];
}

export type UserStatusFilter = 'all' | 'active' | 'disabled';
export type UserColumnKey = 'username' | 'name' | 'roles' | 'status' | 'lastLogin' | 'sessionAudit' | 'twoFactor' | 'actions';
export type UserColumnOption = TableColumnOption<UserColumnKey>;
export type UserDialogState = { mode: 'create' | 'edit'; userId: number | null };
export type MessageTone = 'error' | 'success';
export type UserFormErrors = Partial<Record<'username' | 'firstName' | 'password' | 'confirmPassword', string>>;

export const userColumnOptions: readonly UserColumnOption[] = [
  { key: 'username', label: '登录名', width: 'minmax(120px, 1fr)' },
  { key: 'name', label: '姓名', width: 'minmax(110px, 0.9fr)' },
  { key: 'roles', label: '角色', width: 'minmax(120px, 1fr)' },
  { key: 'status', label: '状态', width: 'minmax(120px, 1fr)' },
  { key: 'lastLogin', label: '最近登录', width: 'minmax(210px, 1.8fr)' },
  { key: 'sessionAudit', label: '会话审计', width: 'minmax(130px, 0.9fr)' },
  { key: 'twoFactor', label: '2FA', width: 'minmax(170px, 1fr)' },
  { key: 'actions', label: '操作', width: 'minmax(300px, 2fr)' },
];

const USER_MANAGER_CACHE_TTL_MS = 60_000;
let userManagerCache: { users: SystemUser[]; roles: SystemRole[]; loadedAt: number } | null = null;

export function useUserManager({ setActiveTool }: { setActiveTool: (key: 'roles' | 'auth') => void }) {
  const users = ref<SystemUser[]>([]);
  const roles = ref<SystemRole[]>([]);
  const search = ref('');
  const statusFilter = ref<UserStatusFilter>('all');
  const isLoading = ref(false);
  const message = ref('');
  const messageTone = ref<MessageTone>('error');
  const page = ref(1);
  const pageSize = ref(10);
  const dialog = ref<UserDialogState | null>(null);
  const resetPasswordUser = ref<SystemUser | null>(null);
  const resetTwoFactorTarget = ref<SystemUser | null>(null);
  const deleteTarget = ref<SystemUser | null>(null);
  const form = ref<UserForm>(emptyUserForm());
  const formErrors = ref<UserFormErrors>({});
  const submitAttempted = ref(false);
  const resetPassword = ref('');
  const showPassword = ref(false);
  const columnsOpen = ref(false);
  const fullscreen = ref(false);

  const columnManager = useColumnVisibility(userColumnOptions, {
    storageKey: 'ops-tool.user-manager.columns',
    fallbackKey: 'username',
  });

  const tableStyle = computed(() => ({
    '--user-table-columns': columnManager.visibleColumns.value.map((column) => column.width).join(' ') || 'minmax(180px, 1fr)',
  }));

  const formPassword = computed({
    get: () => form.value.password,
    set: (value: string) => {
      form.value.password = value;
    },
  });
  const passwordMeter = usePasswordStrength(formPassword);
  const resetPasswordMeter = usePasswordStrength(resetPassword);
  const passwordMismatch = computed(() => passwordsMismatch(form.value.password, form.value.confirmPassword));
  const visibleFormErrors = computed<UserFormErrors>(() => (submitAttempted.value ? formErrors.value : {}));
  const roleNameById = computed(() => new Map(roles.value.map((role) => [role.id, role.name])));

  const filteredUsers = computed(() => {
    const query = search.value.trim().toLowerCase();
    return users.value.filter((user) => {
      const statusMatched =
        statusFilter.value === 'all' ||
        (statusFilter.value === 'active' && user.isActive) ||
        (statusFilter.value === 'disabled' && !user.isActive);
      const searchMatched =
        !query ||
        [user.username, user.firstName, user.email, roleNames(user)]
          .filter(Boolean)
          .some((value) => String(value).toLowerCase().includes(query));
      return statusMatched && searchMatched;
    });
  });

  const totalPages = computed(() => Math.max(1, Math.ceil(filteredUsers.value.length / pageSize.value)));
  const pagedUsers = computed(() => {
    const start = (page.value - 1) * pageSize.value;
    return filteredUsers.value.slice(start, start + pageSize.value);
  });

  const statusCounts = computed(() => ({
    total: users.value.length,
    active: users.value.filter((user) => user.isActive).length,
    disabled: users.value.filter((user) => !user.isActive).length,
  }));

  const primaryRoleId = computed({
    get: () => (form.value.roleIds[0] ? String(form.value.roleIds[0]) : ''),
    set: (value: string) => {
      form.value.roleIds = value ? [Number(value)] : [];
    },
  });
  const dialogTitle = computed(() => (dialog.value?.mode === 'edit' ? '编辑账户' : '新建账户'));
  const dialogSubmitText = computed(() => (dialog.value?.mode === 'edit' ? '保存' : '确定'));

  let loadUsersRequestId = 0;

  onMounted(() => loadUsers(true));

  watch([search, statusFilter, pageSize], () => {
    page.value = 1;
  });

  watch(totalPages, (next) => {
    if (page.value > next) page.value = next;
  });

  async function loadUsers(force = false) {
    const requestId = ++loadUsersRequestId;
    const now = Date.now();
    if (!force && userManagerCache && now - userManagerCache.loadedAt < USER_MANAGER_CACHE_TTL_MS) {
      users.value = [...userManagerCache.users];
      roles.value = [...userManagerCache.roles];
      clearMessage();
      return;
    }

    if (userManagerCache) {
      users.value = [...userManagerCache.users];
      roles.value = [...userManagerCache.roles];
    }

    isLoading.value = true;
    clearMessage();

    const [userResult, roleResult] = await Promise.allSettled([
      apiGet<ListApiResponse<Record<string, unknown>>>('/api/system/users/'),
      apiGet<ListApiResponse<Record<string, unknown>>>('/api/system/role-options/'),
    ]);
    if (requestId !== loadUsersRequestId) return;

    if (userResult.status === 'fulfilled') {
      users.value = listFromResponse(userResult.value, '用户列表').map(normalizeSystemUser);
    } else {
      if (!users.value.length) users.value = userManagerCache ? [...userManagerCache.users] : [];
      if (!roles.value.length && userManagerCache) roles.value = [...userManagerCache.roles];
      setError(errorMessage(userResult.reason));
      isLoading.value = false;
      return;
    }

    if (roleResult.status === 'fulfilled') {
      roles.value = listFromResponse(roleResult.value, '角色选项').map(normalizeSystemRole);
    } else {
      roles.value = userManagerCache ? [...userManagerCache.roles] : [];
      setError(`账户类别加载失败：${errorMessage(roleResult.reason)}`);
    }

    syncUserManagerCache();
    isLoading.value = false;
  }

  function refreshUsers() {
    return loadUsers(true);
  }

  function openCreateDialog() {
    clearMessage();
    showPassword.value = false;
    submitAttempted.value = false;
    formErrors.value = {};
    form.value = emptyUserForm();
    dialog.value = { mode: 'create', userId: null };
  }

  function openEditDialog(user: SystemUser) {
    if (user.isBuiltinAdmin) {
      setError('内置管理员信息固定，不允许编辑');
      return;
    }
    clearMessage();
    showPassword.value = false;
    submitAttempted.value = false;
    formErrors.value = {};
    form.value = {
      username: user.username,
      email: user.email,
      firstName: user.firstName,
      password: '',
      confirmPassword: '',
      mfaFlag: '',
      isActive: user.isActive,
      isStaff: user.isStaff,
      roleIds: [...user.roleIds],
    };
    dialog.value = { mode: 'edit', userId: user.id };
  }

  async function saveUser() {
    clearMessage();
    submitAttempted.value = true;
    const payload = userPayloadFromForm();
    if (!validateUserPayload(payload)) return;

    try {
      const saved =
        dialog.value?.mode === 'edit' && dialog.value.userId
          ? await apiPut<SystemUser>(`/api/system/users/${dialog.value.userId}/`, payload)
          : await apiPost<SystemUser>('/api/system/users/', payload);
      replaceUser(saved);
      syncUserManagerCache();
      dialog.value = null;
      setSuccess(saved.canLogin ? `账号 ${saved.username} 已创建，可使用初始密码登录。` : `账号 ${saved.username} 已保存，启用后即可登录。`);
    } catch (error) {
      setError(errorMessage(error));
    }
  }

  async function toggleUserStatus(user: SystemUser) {
    if (user.isBuiltinAdmin) {
      setError('内置管理员必须保持启用');
      return;
    }
    clearMessage();
    try {
      const saved = await apiPut<SystemUser>(`/api/system/users/${user.id}/`, {
        ...userPayload(user),
        isActive: !user.isActive,
      });
      replaceUser(saved);
      syncUserManagerCache();
    } catch (error) {
      setError(errorMessage(error));
    }
  }

  function openResetPassword(user: SystemUser) {
    if (user.isBuiltinAdmin) {
      setError('内置管理员密码由系统固定，不允许重置');
      return;
    }
    clearMessage();
    resetPassword.value = '';
    resetPasswordUser.value = user;
  }

  async function saveResetPassword() {
    if (!resetPasswordUser.value) return;
    const password = resetPassword.value.trim();
    if (!password) {
      setError('请输入新密码');
      return;
    }
    if (!resetPasswordMeter.isStrong.value) {
      setError('新密码至少 8 位，并包含数字、小写字母和大写字母');
      return;
    }

    try {
      const user = resetPasswordUser.value;
      const saved = await apiPut<SystemUser>(`/api/system/users/${user.id}/`, {
        ...userPayload(user),
        password,
      });
      replaceUser(saved);
      syncUserManagerCache();
      resetPasswordUser.value = null;
      resetPassword.value = '';
    } catch (error) {
      setError(errorMessage(error));
    }
  }

  async function enableUserTwoFactor(user: SystemUser) {
    if (user.isBuiltinAdmin) {
      setError('内置管理员不允许在用户列表中操作 2FA');
      return;
    }
    clearMessage();
    try {
      const saved = await apiPost<SystemUser>(`/api/system/users/${user.id}/2fa/enable/`, {});
      replaceUser(saved);
      syncUserManagerCache();
      setSuccess(`已要求 ${saved.username} 下次登录绑定 2FA。`);
    } catch (error) {
      setError(errorMessage(error));
    }
  }

  async function disableUserTwoFactor(user: SystemUser) {
    if (user.isBuiltinAdmin) {
      setError('内置管理员不允许在用户列表中操作 2FA');
      return;
    }
    clearMessage();
    try {
      const saved = await apiPost<SystemUser>(`/api/system/users/${user.id}/2fa/disable/`, {});
      replaceUser(saved);
      syncUserManagerCache();
      setSuccess(`${saved.username} 的 2FA 已关闭，下次登录无需验证码。`);
    } catch (error) {
      setError(errorMessage(error));
    }
  }

  function openResetTwoFactor(user: SystemUser) {
    clearMessage();
    if (user.isBuiltinAdmin) {
      setError('内置管理员不允许在用户列表中操作 2FA');
      return;
    }
    resetTwoFactorTarget.value = user;
  }

  async function resetUserTwoFactor() {
    if (!resetTwoFactorTarget.value) return;
    clearMessage();
    try {
      const user = resetTwoFactorTarget.value;
      const saved = await apiPost<SystemUser>(`/api/system/users/${user.id}/2fa/reset/`, {});
      replaceUser(saved);
      syncUserManagerCache();
      resetTwoFactorTarget.value = null;
      setSuccess(`${saved.username} 的 2FA 已重置，下次登录需要重新绑定。`);
    } catch (error) {
      setError(errorMessage(error));
    }
  }

  async function toggleUserSessionAudit(user: SystemUser) {
    if (user.isBuiltinAdmin) {
      setError('内置管理员不允许在用户列表中操作会话审计');
      return;
    }
    clearMessage();
    const enabled = !sessionAuditEnabled(user);
    try {
      const saved = await apiPost<SystemUser>(`/api/system/users/${user.id}/session-audit/`, { enabled });
      replaceUser(saved);
      syncUserManagerCache();
      setSuccess(`${saved.username} 的会话审计已${sessionAuditEnabled(saved) ? '开启' : '关闭'}。`);
    } catch (error) {
      setError(errorMessage(error));
    }
  }

  function openDeleteUser(user: SystemUser) {
    clearMessage();
    if (user.isBuiltinAdmin) {
      setError('内置管理员不允许删除');
      return;
    }
    deleteTarget.value = user;
  }

  async function deleteUser() {
    if (!deleteTarget.value) return;
    if (deleteTarget.value.isBuiltinAdmin) {
      setError('内置管理员不允许删除');
      deleteTarget.value = null;
      return;
    }
    clearMessage();
    try {
      const userId = deleteTarget.value.id;
      await apiDelete(`/api/system/users/${userId}/`);
      users.value = users.value.filter((user) => user.id !== userId);
      syncUserManagerCache();
      deleteTarget.value = null;
    } catch (error) {
      setError(errorMessage(error));
    }
  }

  function roleNames(user: SystemUser) {
    const names = user.roleIds
      .map((roleId) => roleNameById.value.get(roleId))
      .filter(Boolean);
    if (user.isBuiltinAdmin) names.unshift('内置管理员');
    if (user.isSuperuser) names.unshift('超级管理员');
    if (user.isStaff && !names.length) names.push('管理员');
    return names.join('、');
  }

  function loginStateText(user: SystemUser) {
    if (user.canLogin === false) return user.isActive ? '待设置密码' : '已禁用';
    return user.isActive ? '可登录' : '已禁用';
  }

  function twoFactorStatusClass(user: SystemUser) {
    return user.twoFactorStatus ?? 'disabled';
  }

  function sessionAuditEnabled(user: SystemUser) {
    return user.sessionAuditEnabled !== false;
  }

  function openRoleManager() {
    dialog.value = null;
    setActiveTool('roles');
  }

  function openMfaHelp() {
    dialog.value = null;
    setActiveTool('auth');
  }

  function setPage(nextPage: number) {
    page.value = Math.min(Math.max(1, nextPage), totalPages.value);
  }

  function setPageSize(nextPageSize: number) {
    pageSize.value = nextPageSize;
  }

  function closeAccountDialog() {
    dialog.value = null;
    submitAttempted.value = false;
    formErrors.value = {};
  }

  function closeResetPasswordDialog() {
    resetPasswordUser.value = null;
  }

  function closeResetTwoFactorDialog() {
    resetTwoFactorTarget.value = null;
  }

  function closeDeleteDialog() {
    deleteTarget.value = null;
  }

  function clearMessage() {
    message.value = '';
    messageTone.value = 'error';
  }

  function setError(value: string) {
    messageTone.value = 'error';
    message.value = value;
  }

  function setSuccess(value: string) {
    messageTone.value = 'success';
    message.value = value;
  }

  function replaceUser(user: SystemUser) {
    const index = users.value.findIndex((item) => item.id === user.id);
    if (index >= 0) {
      users.value.splice(index, 1, user);
    } else {
      users.value = [user, ...users.value];
    }
  }

  function syncUserManagerCache() {
    userManagerCache = {
      users: [...users.value],
      roles: [...roles.value],
      loadedAt: Date.now(),
    };
  }

  function validateUserPayload(payload: ReturnType<typeof userPayloadFromForm>) {
    const errors: UserFormErrors = {};
    if (!payload.username) {
      errors.username = '请输入登录名';
    }
    if (!payload.firstName) {
      errors.firstName = '请输入姓名';
    }
    if (dialog.value?.mode === 'create' && !payload.password) {
      errors.password = '请输入初始密码';
    }
    if (dialog.value?.mode === 'create' && payload.password && !passwordMeter.isStrong.value) {
      errors.password = '密码至少 8 位，并包含数字、小写字母和大写字母';
    }
    if (dialog.value?.mode === 'edit' && payload.password && !passwordMeter.isStrong.value) {
      errors.password = '密码至少 8 位，并包含数字、小写字母和大写字母';
    }
    if ((dialog.value?.mode === 'create' || payload.password) && !form.value.confirmPassword.trim()) {
      errors.confirmPassword = '请再次输入密码';
    } else if (payload.password && form.value.password !== form.value.confirmPassword) {
      errors.confirmPassword = '两次输入的密码不一致';
    }
    formErrors.value = errors;
    return !Object.keys(errors).length;
  }

  function userPayloadFromForm() {
    return {
      username: form.value.username.trim(),
      email: form.value.email.trim(),
      firstName: form.value.firstName.trim(),
      password: form.value.password.trim(),
      isActive: form.value.isActive,
      isStaff: form.value.isStaff,
      roleIds: form.value.roleIds,
    };
  }

  function userPayload(user: SystemUser) {
    return {
      username: user.username,
      email: user.email,
      firstName: user.firstName,
      isActive: user.isActive,
      isStaff: user.isStaff,
      roleIds: user.roleIds,
    };
  }

  return {
    users,
    roles,
    search,
    statusFilter,
    isLoading,
    message,
    messageTone,
    page,
    pageSize,
    dialog,
    resetPasswordUser,
    resetTwoFactorTarget,
    deleteTarget,
    form,
    formErrors: visibleFormErrors,
    submitAttempted,
    resetPassword,
    showPassword,
    columnsOpen,
    fullscreen,
    columnVisibility: columnManager.visibility,
    visibleColumns: columnManager.visibleColumns,
    allColumnsVisible: columnManager.allColumnsVisible,
    someColumnsVisible: columnManager.someColumnsVisible,
    tableStyle,
    filteredUsers,
    pagedUsers,
    totalPages,
    statusCounts,
    passwordRules: passwordMeter.rules,
    resetPasswordRules: resetPasswordMeter.rules,
    isPasswordStrong: passwordMeter.isStrong,
    isResetPasswordStrong: resetPasswordMeter.isStrong,
    passwordMismatch,
    passwordStrength: passwordMeter.passedCount,
    resetPasswordStrength: resetPasswordMeter.passedCount,
    passwordStrengthText: passwordMeter.label,
    resetPasswordStrengthText: resetPasswordMeter.label,
    passwordStrengthClass: passwordMeter.className,
    resetPasswordStrengthClass: resetPasswordMeter.className,
    passwordHint: passwordMeter.hint,
    resetPasswordHint: resetPasswordMeter.hint,
    primaryRoleId,
    dialogTitle,
    dialogSubmitText,
    loadUsers,
    refreshUsers,
    openCreateDialog,
    openEditDialog,
    saveUser,
    toggleUserStatus,
    openResetPassword,
    saveResetPassword,
    enableUserTwoFactor,
    disableUserTwoFactor,
    openResetTwoFactor,
    resetUserTwoFactor,
    toggleUserSessionAudit,
    openDeleteUser,
    deleteUser,
    closeAccountDialog,
    closeResetPasswordDialog,
    closeResetTwoFactorDialog,
    closeDeleteDialog,
    roleNames,
    loginStateText,
    twoFactorStatusClass,
    sessionAuditEnabled,
    openRoleManager,
    openMfaHelp,
    setPage,
    setPageSize,
    isColumnVisible: columnManager.isColumnVisible,
    isOnlyVisibleColumn: columnManager.isOnlyVisibleColumn,
    updateColumnVisibility: columnManager.updateColumnVisibility,
    toggleAllColumns: columnManager.toggleAllColumns,
    resetColumns: columnManager.resetColumns,
  };
}

export function emptyUserForm(): UserForm {
  return {
    username: '',
    email: '',
    firstName: '',
    password: '',
    confirmPassword: '',
    mfaFlag: '',
    isActive: true,
    isStaff: false,
    roleIds: [],
  };
}

function listFromResponse<T>(payload: ListApiResponse<T>, label: string): T[] {
  if (Array.isArray(payload)) return payload;
  if (payload && typeof payload === 'object') {
    if (Array.isArray(payload.results)) return payload.results;
    if (Array.isArray(payload.data)) return payload.data;
    if (Array.isArray(payload.items)) return payload.items;
  }
  throw new Error(`${label}返回格式异常`);
}

function normalizeSystemUser(raw: Record<string, unknown>): SystemUser {
  return {
    id: numberValue(raw.id),
    username: stringValue(raw.username),
    email: stringValue(raw.email),
    firstName: stringValue(raw.firstName ?? raw.first_name ?? raw.displayName),
    isActive: booleanValue(raw.isActive ?? raw.is_active, true),
    isStaff: booleanValue(raw.isStaff ?? raw.is_staff),
    isSuperuser: booleanValue(raw.isSuperuser ?? raw.is_superuser),
    isBuiltinAdmin: booleanValue(raw.isBuiltinAdmin ?? raw.is_builtin_admin),
    canLogin: optionalBooleanValue(raw.canLogin ?? raw.can_login),
    twoFactorEnabled: optionalBooleanValue(raw.twoFactorEnabled ?? raw.two_factor_enabled),
    twoFactorRequired: optionalBooleanValue(raw.twoFactorRequired ?? raw.two_factor_required),
    twoFactorResetRequired: optionalBooleanValue(raw.twoFactorResetRequired ?? raw.two_factor_reset_required),
    twoFactorStatus: twoFactorStatusValue(raw.twoFactorStatus ?? raw.two_factor_status),
    sessionAuditEnabled: booleanValue(raw.sessionAuditEnabled ?? raw.session_audit_enabled, true),
    lastLogin: nullableStringValue(raw.lastLogin ?? raw.last_login),
    dateJoined: nullableStringValue(raw.dateJoined ?? raw.date_joined),
    roleIds: numberArrayValue(raw.roleIds ?? raw.role_ids ?? raw.groups),
  };
}

function normalizeSystemRole(raw: Record<string, unknown>): SystemRole {
  return {
    id: numberValue(raw.id),
    name: stringValue(raw.name),
    permissionIds: numberArrayValue(raw.permissionIds ?? raw.permission_ids),
  };
}

function stringValue(value: unknown) {
  return value == null ? '' : String(value);
}

function nullableStringValue(value: unknown) {
  return value == null || value === '' ? null : String(value);
}

function numberValue(value: unknown) {
  const number = Number(value);
  return Number.isFinite(number) ? number : 0;
}

function booleanValue(value: unknown, fallback = false) {
  if (typeof value === 'boolean') return value;
  if (typeof value === 'string') return ['1', 'true', 'yes', 'on'].includes(value.trim().toLowerCase());
  if (value == null) return fallback;
  return Boolean(value);
}

function optionalBooleanValue(value: unknown) {
  return value == null ? undefined : booleanValue(value);
}

function numberArrayValue(value: unknown) {
  if (!Array.isArray(value)) return [];
  return value.map(numberValue).filter((item) => item > 0);
}

function twoFactorStatusValue(value: unknown): SystemUser['twoFactorStatus'] {
  return value === 'enabled' || value === 'required' ? value : 'disabled';
}
