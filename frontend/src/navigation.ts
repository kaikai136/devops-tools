import type { ToolKey } from './types';

type NavGroupKey = 'network' | 'host' | 'security' | 'system';

export interface NavItem {
  key: ToolKey;
  label: string;
  desc: string;
}

export interface NavGroup {
  key: NavGroupKey;
  label: string;
  items: NavItem[];
}

export const navGroups: NavGroup[] = [
  {
    key: 'network' as const,
    label: '网络工具',
    items: [
      { key: 'ip' as const, label: 'IP 探活', desc: '1-254 主机在线探测' },
      { key: 'ports' as const, label: '机器探测', desc: 'Ping 连通性与端口扫描' },
      { key: 'subnet' as const, label: 'IPv4 子网划分', desc: 'CIDR 计算与子网拆分' },
    ],
  },
  {
    key: 'host' as const,
    label: '主机管理',
    items: [
      { key: 'hosts' as const, label: '主机管理', desc: '分组资产、验证状态与终端入口' },
      { key: 'accounts' as const, label: '账号管理', desc: '用户账号、状态与权限管理' },
    ],
  },
  {
    key: 'security' as const,
    label: '安全工具',
    items: [
      { key: 'auth' as const, label: '双因子认证', desc: 'TOTP 动态口令' },
      { key: 'password' as const, label: '密码生成器', desc: '强密码生成与记录' },
      { key: 'commandRules' as const, label: '命令管理', desc: 'Web 终端风险命令拦截与记录' },
    ],
  },
  {
    key: 'system' as const,
    label: '系统管理',
    items: [
      { key: 'loginLogs' as const, label: '登录日志', desc: '查看用户登录时间、来源与状态' },
      { key: 'users' as const, label: '用户管理', desc: '维护系统用户与账号状态' },
      { key: 'roles' as const, label: '角色管理', desc: '配置角色权限与授权范围' },
      { key: 'systemSettings' as const, label: '系统设置', desc: '管理系统基础参数与偏好' },
    ],
  },
];
