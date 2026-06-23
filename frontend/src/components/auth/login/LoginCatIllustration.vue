<script setup lang="ts">
import { ref } from 'vue';

const catSvg = ref<SVGSVGElement | null>(null);

function getSvgElement() {
  return catSvg.value;
}

defineExpose({ getSvgElement });
</script>

<template>
  <div class="cat-box">
    <div class="cat-shadow"></div>
    <svg ref="catSvg" class="cat-svg" viewBox="0 0 420 340" xmlns="http://www.w3.org/2000/svg" aria-label="黄色机器猫插画">
      <defs>
        <linearGradient id="bodyYellow" x1="112" y1="110" x2="302" y2="300" gradientUnits="userSpaceOnUse">
          <stop offset="0" stop-color="#ffe26a" />
          <stop offset="0.56" stop-color="#ffd049" />
          <stop offset="1" stop-color="#f2af24" />
        </linearGradient>
        <linearGradient id="earYellow" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stop-color="#ffe46b" />
          <stop offset="1" stop-color="#f5b52e" />
        </linearGradient>
        <linearGradient id="eyeGlow" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stop-color="#fffbdc" />
          <stop offset="1" stop-color="#fff0a4" />
        </linearGradient>
        <filter id="softShadow" x="-20%" y="-20%" width="140%" height="150%">
          <feDropShadow dx="0" dy="8" stdDeviation="8" flood-color="#1f2937" flood-opacity="0.2" />
        </filter>
      </defs>

      <path d="M132 150 C172 64 250 64 292 150" fill="none" stroke="#9aa5b8" stroke-width="12" stroke-linecap="round" opacity="0.55" />
      <g class="cat-body-group">
        <path d="M115 247 C115 207 138 179 173 170 C184 150 195 143 210 143 C225 143 236 150 247 170 C282 179 305 207 305 247 C305 277 290 292 261 292 L159 292 C129 292 115 277 115 247 Z" fill="url(#bodyYellow)" stroke="#c98f1c" stroke-width="4" filter="url(#softShadow)" />
        <path d="M248 288 C265 300 290 297 301 281 C282 284 264 284 248 288 Z" fill="#efb232" opacity="0.88" />
      </g>

      <g class="cat-neck-group">
        <path d="M190 165 C196 155 204 151 210 151 C216 151 224 155 230 165 L228 208 C222 214 217 216 210 216 C203 216 198 214 192 208 Z" fill="#f8c439" stroke="#c98f1c" stroke-width="3" opacity="0.98" />
        <path d="M198 168 C203 162 207 159 210 159 C213 159 217 162 222 168 L221 203 C217 207 214 209 210 209 C206 209 203 207 199 203 Z" fill="#ffd95c" opacity="0.55" />
      </g>

      <g class="cat-head-group">
        <g transform="rotate(-39 127 112)" filter="url(#softShadow)">
          <rect x="102" y="57" width="50" height="84" rx="17" fill="url(#earYellow)" stroke="#d99a1a" stroke-width="3" />
          <rect x="116" y="80" width="25" height="42" rx="9" fill="#ff9a83" opacity="0.68" />
        </g>
        <g transform="rotate(39 291 112)" filter="url(#softShadow)">
          <rect x="266" y="57" width="50" height="84" rx="17" fill="url(#earYellow)" stroke="#d99a1a" stroke-width="3" />
          <rect x="280" y="80" width="25" height="42" rx="9" fill="#ff9a83" opacity="0.68" />
        </g>
        <path d="M129 188 C129 140 165 104 210 104 C255 104 291 140 291 188 C291 214 276 230 249 236 L171 236 C144 230 129 214 129 188 Z" fill="url(#bodyYellow)" stroke="#c98f1c" stroke-width="4" filter="url(#softShadow)" />
        <ellipse cx="210" cy="176" rx="72" ry="53" fill="#ffdc63" opacity="0.48" />
        <ellipse cx="168" cy="184" rx="34" ry="27" fill="url(#eyeGlow)" opacity="0.96" />
        <ellipse cx="252" cy="184" rx="34" ry="27" fill="url(#eyeGlow)" opacity="0.96" />
        <ellipse class="cat-eye-white" cx="183" cy="173" rx="16" ry="22" fill="#ffffff" stroke="#dfe5ef" stroke-width="2.5" />
        <ellipse class="cat-eye-white" cx="235" cy="173" rx="16" ry="22" fill="#ffffff" stroke="#dfe5ef" stroke-width="2.5" />
        <g class="cat-pupil" data-eye-x="183" data-eye-y="173">
          <circle cx="183" cy="175" r="8" fill="#1f2937" />
          <circle cx="180" cy="171" r="3.2" fill="#ffffff" />
        </g>
        <g class="cat-pupil" data-eye-x="235" data-eye-y="173">
          <circle cx="235" cy="175" r="8" fill="#1f2937" />
          <circle cx="232" cy="171" r="3.2" fill="#ffffff" />
        </g>
        <path d="M207 189 C214 187 221 187 228 189 C225 198 217 203 210 199 C205 197 204 193 207 189Z" fill="#ff6f8d" />
        <path d="M209 200 C199 210 188 209 183 202" fill="none" stroke="#76551e" stroke-width="4" stroke-linecap="round" />
        <path d="M210 200 C219 210 230 209 235 202" fill="none" stroke="#76551e" stroke-width="4" stroke-linecap="round" />
        <g class="cat-whiskers-group">
          <path d="M143 210 L104 215" stroke="#b88622" stroke-width="4" stroke-linecap="round" opacity="0.75" />
          <path d="M145 223 L104 228" stroke="#b88622" stroke-width="4" stroke-linecap="round" opacity="0.75" />
          <path d="M277 210 L316 215" stroke="#b88622" stroke-width="4" stroke-linecap="round" opacity="0.75" />
          <path d="M275 223 L316 228" stroke="#b88622" stroke-width="4" stroke-linecap="round" opacity="0.75" />
        </g>
      </g>
      <path d="M138 278 C166 287 250 287 282 278" stroke="#e1a12b" stroke-width="5" stroke-linecap="round" opacity="0.38" />
    </svg>
  </div>
</template>
