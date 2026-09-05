<script setup lang="ts">
import { useAppContext } from '@app/context';
import AppIcon from '@shared/components/AppIcon.vue';

const {
  activeTool,
  passwordLength,
  passwordOptions,
  togglePasswordOption,
  passwordOptionText,
  passwordProject,
  passwordResult,
  generatePassword,
  clearPasswordRecords,
  passwordHistory,
  formatRecordTime,
  deletePassword,
  copyText,
  canUsePageAction,
  canUseAnyPageAction,
} = useAppContext();
</script>

<template>
  <section v-if="activeTool === 'password'" class="password-page">
    <template v-if="canUseAnyPageAction('password', ['generate', 'copy', 'delete', 'clear', 'import', 'export'])">
      <article class="panel password-generator-panel">
        <div class="password-panel-head">
          <div>
            <h2>密码生成器</h2>
            <p>可通过顶部导出选择保存路径，也可以导入历史记录。</p>
          </div>
        </div>
        <div class="password-length-box">
          <div>
            <span>密码长度</span>
            <strong>{{ passwordLength }} 位</strong>
          </div>
          <NativeSlider v-model="passwordLength" :min="6" :max="64" />
        </div>
        <div class="password-option-grid">
          <NativeCheckbox :model-value="passwordOptions.include_uppercase" border @change="togglePasswordOption('include_uppercase')">大写字母</NativeCheckbox>
          <NativeCheckbox :model-value="passwordOptions.include_lowercase" border @change="togglePasswordOption('include_lowercase')">小写字母</NativeCheckbox>
          <NativeCheckbox :model-value="passwordOptions.include_numbers" border @change="togglePasswordOption('include_numbers')">数字</NativeCheckbox>
          <NativeCheckbox :model-value="passwordOptions.include_symbols" border @change="togglePasswordOption('include_symbols')">符号</NativeCheckbox>
        </div>
        <p class="password-policy">当前规则：{{ passwordLength }} 位 · {{ passwordOptionText() }}</p>
        <div class="password-info-box">
          <div class="password-info-head">
            <h3>密码信息</h3>
            <NativeButton v-if="canUsePageAction('password', 'copy')" :disabled="!passwordResult" @click="copyText(passwordResult, '已复制生成结果。')">
              复制
            </NativeButton>
          </div>
          <div class="password-field-grid">
            <label>
              <span>项目名称</span>
              <NativeInput v-model="passwordProject" type="textarea" :rows="3" placeholder="未填写项目名称" />
            </label>
            <label>
              <span>生成结果</span>
              <NativeInput v-model="passwordResult" class="password-result-field" type="textarea" :rows="3" readonly placeholder="点击生成密码" />
            </label>
          </div>
        </div>
        <div class="password-actions">
          <NativeButton v-if="canUsePageAction('password', 'generate')" type="primary" @click="generatePassword">生成密码</NativeButton>
          <NativeButton v-if="canUsePageAction('password', 'clear')" :disabled="!passwordHistory.length" @click="clearPasswordRecords">清空记录</NativeButton>
        </div>
      </article>

      <article class="panel password-record-panel">
        <div class="password-record-head">
          <h2>生成记录</h2>
          <NativeTag type="info" effect="plain">{{ passwordHistory.length }} 条</NativeTag>
        </div>
        <NativeTable :data="passwordHistory" row-key="id" class="password-record-list" empty-text="还没有生成记录。">
          <NativeTableColumn label="密码" min-width="220">
            <template #default="{ row }">
              <strong
                class="password-copy-target"
                title="双击复制密码"
                @dblclick.stop="canUsePageAction('password', 'copy') && copyText(row.password, `已复制 ${row.project_name || '未填写项目名称'} 的密码。`)"
              >
                {{ row.password }}
              </strong>
            </template>
          </NativeTableColumn>
          <NativeTableColumn label="项目" min-width="160">
            <template #default="{ row }">{{ row.project_name || '未填写项目名称' }}</template>
          </NativeTableColumn>
          <NativeTableColumn label="规则" min-width="160">
            <template #default="{ row }">{{ row.length }} 位 · {{ passwordOptionText(row) }}</template>
          </NativeTableColumn>
          <NativeTableColumn label="时间" min-width="170">
            <template #default="{ row }">{{ formatRecordTime(row.created_at) }}</template>
          </NativeTableColumn>
          <NativeTableColumn label="操作" width="150" fixed="right">
            <template #default="{ row }">
              <NativeButton v-if="canUsePageAction('password', 'copy')" size="small" @click="copyText(row.password, `已复制 ${row.project_name || '未填写项目名称'} 的密码。`)">
                复制
              </NativeButton>
              <NativeButton v-if="canUsePageAction('password', 'delete')" size="small" type="danger" @click="deletePassword(row)">
                <AppIcon name="trash" :size="14" />
              </NativeButton>
            </template>
          </NativeTableColumn>
        </NativeTable>
      </article>
    </template>
    <div v-else class="permission-empty">暂无可用功能</div>
  </section>
</template>
