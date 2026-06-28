<script setup lang="ts">
import { useAppContext } from '../../appContext';
import type { SecurityCommandAction, SecurityCommandMatchType } from '../../types';
import AppIcon from '../common/AppIcon.vue';

const {
  filteredCommandRules,
  commandRecords,
  commandRuleSearch,
  commandRuleMessage,
  commandRuleStats,
  commandRuleDialog,
  isCommandRuleLoading,
  isCommandRecordLoading,
  loadCommandRules,
  loadCommandRecords,
  openCommandRuleDialog,
  closeCommandRuleDialog,
  saveCommandRuleDialog,
  toggleCommandRule,
  deleteCommandRule,
} = useAppContext();

const matchTypeLabels: Record<SecurityCommandMatchType, string> = {
  command: '命令',
  regex: '正则',
};

const actionLabels: Record<SecurityCommandAction, string> = {
  block: '阻断并告警',
  warn: '告警但放行',
};

function formatCommandTime(value: string) {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('zh-CN', { hour12: false });
}
</script>

<template>
  <section class="command-rule-page">
    <article class="command-rule-summary">
      <div>
        <span>规则总数</span>
        <strong>{{ commandRuleStats.total }}</strong>
      </div>
      <div>
        <span>已激活</span>
        <strong>{{ commandRuleStats.enabled }}</strong>
      </div>
      <div>
        <span>阻断记录</span>
        <strong>{{ commandRuleStats.blockedRecords }}</strong>
      </div>
    </article>

    <article class="command-rule-panel">
      <header class="command-rule-toolbar">
        <label>
          <AppIcon name="search" :size="15" />
          <input v-model="commandRuleSearch" type="search" placeholder="搜索名称、命令内容或备注" />
        </label>
        <div>
          <button type="button" :disabled="isCommandRuleLoading" @click="loadCommandRules">
            <AppIcon name="refresh" :size="15" />
            刷新
          </button>
          <button class="primary" type="button" @click="openCommandRuleDialog()">
            <AppIcon name="plus" :size="15" />
            新增
          </button>
        </div>
      </header>

      <p v-if="commandRuleMessage" class="command-rule-message">{{ commandRuleMessage }}</p>

      <div class="command-rule-table">
        <div class="command-rule-row head">
          <span>名称</span>
          <span>类型</span>
          <span>命令内容</span>
          <span>处置动作</span>
          <span>激活状态</span>
          <span>管理</span>
          <span>操作</span>
        </div>
        <p v-if="isCommandRuleLoading" class="command-rule-empty">加载中...</p>
        <p v-else-if="!filteredCommandRules.length" class="command-rule-empty">暂无命令规则</p>
        <div v-for="rule in filteredCommandRules" v-else :key="rule.id" class="command-rule-row">
          <strong>{{ rule.name }}</strong>
          <span>{{ matchTypeLabels[rule.matchType] }}</span>
          <code>{{ rule.content }}</code>
          <em :class="['command-rule-action', rule.action]">{{ actionLabels[rule.action] }}</em>
          <i :class="['command-rule-status', { active: rule.enabled }]">{{ rule.enabled ? '已激活' : '已禁用' }}</i>
          <span>{{ rule.ignoreCase ? '忽略大小写' : '区分大小写' }}</span>
          <div class="command-rule-actions">
            <button type="button" @click="openCommandRuleDialog(rule)">编辑</button>
            <button type="button" @click="toggleCommandRule(rule)">{{ rule.enabled ? '禁用' : '激活' }}</button>
            <button class="danger" type="button" @click="deleteCommandRule(rule)">删除</button>
          </div>
        </div>
      </div>
    </article>

    <article class="command-record-panel">
      <header class="command-record-toolbar">
        <h2>命令记录</h2>
        <button type="button" :disabled="isCommandRecordLoading" @click="loadCommandRecords">
          <AppIcon name="refresh" :size="15" />
          刷新
        </button>
      </header>
      <div class="command-record-table">
        <div class="command-record-row head">
          <span>时间</span>
          <span>用户</span>
          <span>主机</span>
          <span>命令</span>
          <span>规则</span>
          <span>处置</span>
        </div>
        <p v-if="isCommandRecordLoading" class="command-rule-empty">加载中...</p>
        <p v-else-if="!commandRecords.length" class="command-rule-empty">暂无命令记录</p>
        <div v-for="record in commandRecords" v-else :key="record.id" class="command-record-row">
          <span>{{ formatCommandTime(record.createdAt) }}</span>
          <span>{{ record.userName || '-' }}</span>
          <span>{{ record.hostName || record.hostIp || '-' }}</span>
          <code>{{ record.command }}</code>
          <strong>{{ record.ruleName || '-' }}</strong>
          <em :class="['command-rule-action', record.action]">{{ record.blocked ? '已阻断' : '已告警' }}</em>
        </div>
      </div>
    </article>

    <Teleport to="body">
      <div v-if="commandRuleDialog.visible" class="command-rule-dialog-backdrop" @click.self="closeCommandRuleDialog">
        <article class="command-rule-dialog">
          <header>
            <strong>{{ commandRuleDialog.mode === 'create' ? '新增命令规则' : '编辑命令规则' }}</strong>
            <button type="button" title="关闭" aria-label="关闭" @click="closeCommandRuleDialog">
              <AppIcon name="x" :size="16" />
            </button>
          </header>
          <div class="command-rule-dialog-body">
            <p v-if="commandRuleDialog.error" class="command-rule-message">{{ commandRuleDialog.error }}</p>
            <label>
              <span>名称</span>
              <input v-model="commandRuleDialog.draft.name" type="text" />
            </label>
            <label>
              <span>类型</span>
              <select v-model="commandRuleDialog.draft.matchType">
                <option value="command">命令</option>
                <option value="regex">正则表达式</option>
              </select>
            </label>
            <label>
              <span>内容</span>
              <textarea v-model="commandRuleDialog.draft.content" rows="6" placeholder="每行一条命令或正则表达式"></textarea>
            </label>
            <label>
              <span>处置动作</span>
              <select v-model="commandRuleDialog.draft.action">
                <option value="block">阻断并告警</option>
                <option value="warn">告警但放行</option>
              </select>
            </label>
            <label>
              <span>备注</span>
              <textarea v-model="commandRuleDialog.draft.remark" rows="3"></textarea>
            </label>
            <div class="command-rule-switches">
              <label>
                <input v-model="commandRuleDialog.draft.ignoreCase" type="checkbox" />
                <span>忽略大小写</span>
              </label>
              <label>
                <input v-model="commandRuleDialog.draft.enabled" type="checkbox" />
                <span>激活</span>
              </label>
            </div>
          </div>
          <footer>
            <button type="button" @click="closeCommandRuleDialog">取消</button>
            <button class="primary" type="button" :disabled="commandRuleDialog.saving" @click="saveCommandRuleDialog">
              {{ commandRuleDialog.saving ? '保存中...' : '提交' }}
            </button>
          </footer>
        </article>
      </div>
    </Teleport>
  </section>
</template>
