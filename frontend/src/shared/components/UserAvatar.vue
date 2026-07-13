<script setup lang="ts">
import { computed } from 'vue';

import { getAvatarInitial, type AvatarIdentity } from '../../utils/avatar';

const props = withDefaults(
  defineProps<AvatarIdentity & {
    src?: string | null;
    alt?: string;
    size?: 'sm' | 'md' | 'lg' | 'xl';
  }>(),
  {
    src: '',
    alt: '',
    size: 'md',
  },
);

const hasImage = computed(() => Boolean(props.src?.trim()));
const initial = computed(() => getAvatarInitial(props));
</script>

<template>
  <span class="user-avatar" :class="[`user-avatar-${size}`, { 'has-image': hasImage }]">
    <img v-if="hasImage" :src="src || ''" :alt="alt" />
    <span v-else class="user-avatar-initial" aria-hidden="true">{{ initial }}</span>
  </span>
</template>

<style scoped>
.user-avatar {
  display: inline-grid;
  place-items: center;
  flex: 0 0 auto;
  overflow: hidden;
  border-radius: 8px;
  background: linear-gradient(135deg, #7c3aed, #a855f7);
  color: #fff;
  font-weight: 900;
  line-height: 1;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.18);
}

.user-avatar-sm {
  width: 28px;
  height: 28px;
  font-size: 13px;
}

.user-avatar-md {
  width: 38px;
  height: 38px;
  font-size: 17px;
}

.user-avatar-lg {
  width: 72px;
  height: 72px;
  font-size: 30px;
}

.user-avatar-xl {
  width: 80px;
  height: 80px;
  font-size: 34px;
}

.user-avatar img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.user-avatar-initial {
  display: block;
  transform: translateY(-0.02em);
}
</style>
