<script setup lang="ts">
import type { NavGroup, NavItem } from '@app/navigation';
import AppIcon, { type IconName } from '@shared/components/AppIcon.vue';
import type { ToolKey } from '../../types';

withDefaults(
  defineProps<{
    activeTool: ToolKey;
    dashboardItem?: NavItem | null;
    groups: NavGroup[];
    collapsed?: boolean;
    navGroupIcon: (key: string) => IconName;
    navItemIcon: (key: ToolKey) => IconName;
  }>(),
  {
    dashboardItem: null,
    collapsed: false,
  },
);

const emit = defineEmits<{
  select: [index: string];
}>();
</script>

<template>
  <nav class="sidebar-nav workspace-navigation">
    <el-scrollbar class="sidebar-scroll">
      <el-menu
        class="workspace-nav-menu"
        :collapse="collapsed"
        :default-active="activeTool"
        :ellipsis="false"
        :unique-opened="true"
        @select="emit('select', $event)"
      >
        <el-menu-item v-if="dashboardItem" index="dashboard">
          <AppIcon name="dashboard" :size="18" />
          <span>{{ dashboardItem.label }}</span>
        </el-menu-item>
        <el-sub-menu v-for="group in groups" :key="group.key" :index="group.key">
          <template #title>
            <AppIcon :name="navGroupIcon(group.key)" :size="18" />
            <span>{{ group.label }}</span>
          </template>
          <el-menu-item v-for="item in group.items" :key="item.key" :index="item.key">
            <AppIcon :name="navItemIcon(item.key)" :size="18" />
            <span>{{ item.label }}</span>
          </el-menu-item>
        </el-sub-menu>
      </el-menu>
    </el-scrollbar>
  </nav>
</template>
