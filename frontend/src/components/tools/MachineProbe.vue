<script setup lang="ts">
import { useAppContext } from '../../appContext';
import PingProbe from './machine/PingProbe.vue';
import PortScanner from './machine/PortScanner.vue';

const { activeTool } = useAppContext();
</script>

<template>
  <section v-if="activeTool === 'ports'" class="machine-probe-grid">
    <PingProbe />
    <PortScanner />
  </section>
</template>