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
  lastLogin: string | null;
  dateJoined: string | null;
  roleIds: number[];
}

export interface SystemRole {
  id: number;
  name: string;
  permissionIds: number[];
}

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
export type UserColumnKey = 'username' | 'name' | 'roles' | 'status' | 'lastLogin' | 'actions';
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
  { key: 'actions', label: '操作', width: 'minmax(300px, 2fr)' },
];

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

  onMounted(loadUsers);

  watch([search, statusFilter, pageSize], () => {
    page.value = 1;
  });

  watch(totalPages, (next) => {
    if (page.value > next) page.value = next;
  });

  async function loadUsers() {
    isLoading.value = true;
    clearMessage();
    try {
      users.value = await apiGet<SystemUser[]>('/api/system/users/');
      try {
        roles.value = await apiGet<SystemRole[]>('/api/system/roles/');
      } catch (error) {
        roles.value = [];
        setError(`用户已加载，角色信息加载失败：${errorMessage(error)}`);
      }
    } catch (error) {
      users.value = [];
      roles.value = [];
      setError(errorMessage(error));
    } finally {
      isLoading.value = false;
    }
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
      resetPasswordUser.value = null;
      resetPassword.value = '';
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
      deleteTarget.value = null;
    } catch (error) {
      setError(errorMessage(error));
    }
  }

  function roleNames(user: SystemUser) {
    const names = user.roleIds
      .map((roleId) => roles.value.find((role) => role.id === roleId)?.name)
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
    openCreateDialog,
    openEditDialog,
    saveUser,
    toggleUserStatus,
    openResetPassword,
    saveResetPassword,
    openDeleteUser,
    deleteUser,
    closeAccountDialog,
    closeResetPasswordDialog,
    closeDeleteDialog,
    roleNames,
    loginStateText,
    openRoleManager,
    openMfaHelp,
    setPage,
    setPageSize,
    isColumnVisible: columnManager.isColumnVisible,
    isOnlyVisibleColumn: columnManager.isOnlyVisibleColumn,
    updateColumnVisibility: columnManager.updateColumnVisibility,
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
