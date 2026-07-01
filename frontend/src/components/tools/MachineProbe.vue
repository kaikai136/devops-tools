<script setup lang="ts">
import { useAppContext } from '../../appContext';
import PingProbe from './machine/PingProbe.vue';
import PortScanner from './machine/PortScanner.vue';

const { activeTool, canUseAnyPageAction, canUsePageAction } = useAppContext();
</script>

<template>
  <section v-if="activeTool === 'ports'" class="machine-probe-grid">
    <template v-if="canUseAnyPageAction('ports', ['ping', 'port_scan', 'export_ping'])">
      <PingProbe v-if="canUseAnyPageAction('ports', ['ping', 'export_ping'])" />
      <PortScanner v-if="canUsePageAction('ports', 'port_scan')" />
    </template>
    <div v-else class="permission-empty">暂无可用功能</div>
  </section>
</template>
