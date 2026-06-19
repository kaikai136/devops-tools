export const navGroups = [
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
    ],
  },
];
