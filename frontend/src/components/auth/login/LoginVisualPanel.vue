<script setup lang="ts">
import AppIcon from '../../common/AppIcon.vue';
</script>

<template>
  <aside class="login-left-panel">
    <div class="login-brand-mesh" aria-hidden="true"></div>
    <div class="login-brand-shine" aria-hidden="true"></div>
    <div class="login-brand-glow" aria-hidden="true"></div>

    <div class="login-brand-row">
      <div class="login-logo-wrap">
        <img src="/ops-captain-icon.png" alt="运维船长" />
      </div>
      <div class="login-brand-text">
        <strong>运维船长</strong>
        <span>Management Platform</span>
      </div>
    </div>

    <div class="login-brand-content">
      <div class="login-brand">
        <h1>欢迎登录<br />管理平台</h1>
        <p>面向日常巡检、网络诊断和安全管理的内部工作台。</p>
      </div>

      <ul class="login-feature-tags" aria-label="平台能力">
        <li><span><AppIcon name="zap" :size="14" /></span>极速开发体验</li>
        <li><span><AppIcon name="dashboard" :size="14" /></span>现代化 UI 设计</li>
        <li><span><AppIcon name="shield" :size="14" /></span>企业级安全保障</li>
      </ul>

      <div class="login-illustration" aria-hidden="true">
        <div class="login-orbit login-orbit-1"></div>
        <div class="login-orbit login-orbit-2"></div>
        <div class="login-preview">
          <div class="login-preview-bar"><span></span><span></span><span></span></div>
          <div class="login-preview-body">
            <div class="login-preview-sidebar"></div>
            <div class="login-preview-main">
              <div class="login-preview-chart"></div>
              <div class="login-preview-cards"><span></span><span></span><span></span></div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <p class="login-copyright">© 2026 运维船长 Team</p>
  </aside>
</template>
