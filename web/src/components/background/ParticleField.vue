<script setup lang="ts">
/**
 * ParticleField —— Three.js GPU 粒子场
 *
 * 参考来源：
 *   - threejs-journey.com 的 Particles / Galaxy Generator 章节手法
 *     （BufferGeometry + Points + 自定义 ShaderMaterial）
 *   - 替代原先手写的 2D Canvas 粒子（CPU 逐帧连线，性能与观感都受限）
 *
 * 设计约束（暖色杂志风）：
 *   - 粒子取陶土橘与暖褐两色，低透明度，绝不抢正文
 *   - 浅色底用 NormalBlending 而非加法混合（加法在奶油底上会冲白发虚）
 *   - prefers-reduced-motion → 只渲染一帧静态
 *   - 页面隐藏时暂停 rAF；组件卸载时释放 GPU 资源
 *   - WebGL 不可用时静默降级，页面照常工作
 *
 * 两个必须注意的实现细节（都是实测踩到的坑）：
 *   1. `attribute` 只能在顶点着色器声明。fragment 里要用 attribute 必须经
 *      varying 传递，否则着色器编译失败 → 整块背景什么都不画（无报错提示）。
 *   2. `gl_PointSize *= 1.0 / -mv.z` 的透视衰减需要显式焦距常数。
 *      相机在 z=30、粒子分布在 z≈-80~0 时 -mv.z≈90~110，
 *      若不补常数，算出的点径只有 ~1px，等于看不见。
 */
import { onBeforeUnmount, onMounted, shallowRef } from 'vue'
import * as THREE from 'three'

const canvasRef = shallowRef<HTMLCanvasElement | null>(null)

const COUNT = 700
const SPREAD = 46
// 透视焦距常数：让点径在相机距离下落到 2-5 CSS px
const FOCAL = 110

let renderer: THREE.WebGLRenderer | null = null
let scene: THREE.Scene | null = null
let camera: THREE.PerspectiveCamera | null = null
let points: THREE.Points | null = null
let material: THREE.ShaderMaterial | null = null
let geometry: THREE.BufferGeometry | null = null
let raf = 0
let reduced = false
let running = true

const clock = new THREE.Clock()

/* ---------------- 粒子生成（Galaxy Generator 手法） ---------------- */
function buildParticles() {
  geometry = new THREE.BufferGeometry()
  const positions = new Float32Array(COUNT * 3)
  const scales = new Float32Array(COUNT)
  const seeds = new Float32Array(COUNT)
  const ratios = new Float32Array(COUNT)

  for (let i = 0; i < COUNT; i++) {
    const i3 = i * 3
    // 均匀散布 + 轻微向中心聚集，避免边缘空洞
    const r = Math.pow(Math.random(), 0.62) * SPREAD
    const theta = Math.random() * Math.PI * 2
    positions[i3] = Math.cos(theta) * r * (0.9 + Math.random() * 0.5)
    positions[i3 + 1] = (Math.random() - 0.5) * SPREAD * 0.85
    // z 全部压在相机前方（相机 z=30，这里取 -70~10）
    positions[i3 + 2] = -Math.random() * 78 + 10

    // 0.35~1.0：避免极小粒子完全消失、极大粒子抢焦点
    scales[i] = 0.35 + Math.random() * 0.65
    seeds[i] = Math.random() * 100
    ratios[i] = Math.random()
  }

  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))
  geometry.setAttribute('aScale', new THREE.BufferAttribute(scales, 1))
  geometry.setAttribute('aSeed', new THREE.BufferAttribute(seeds, 1))
  geometry.setAttribute('aMix', new THREE.BufferAttribute(ratios, 1))
}

/* ---------------- 着色器 ---------------- */
const vertexShader = /* glsl */ `
  uniform float uTime;
  uniform float uPixelRatio;
  uniform float uSize;
  uniform float uFocal;
  attribute float aScale;
  attribute float aSeed;
  attribute float aMix;
  varying float vSeed;
  varying float vMix;

  void main() {
    vec3 p = position;
    // 极缓慢的漂浮：三轴用不同频率正弦，避免整体旋转感
    p.x += sin(uTime * 0.12 + aSeed) * 1.6;
    p.y += cos(uTime * 0.10 + aSeed * 1.3) * 1.2;
    p.z += sin(uTime * 0.08 + aSeed * 0.7) * 1.4;

    vec4 mv = modelViewMatrix * vec4(p, 1.0);
    gl_Position = projectionMatrix * mv;

    // 近大远小：必须带焦距常数，否则点径只有 ~1px
    float dist = max(-mv.z, 1.0);
    gl_PointSize = uSize * aScale * uPixelRatio * (uFocal / dist);
    vSeed = aSeed;
    vMix = aMix;
  }
`

const fragmentShader = /* glsl */ `
  uniform vec3 uColorA;
  uniform vec3 uColorB;
  uniform float uOpacity;
  varying float vSeed;
  varying float vMix;

  void main() {
    // 圆形软点：丢弃方形边角
    float d = distance(gl_PointCoord, vec2(0.5));
    if (d > 0.5) discard;
    float soft = smoothstep(0.5, 0.02, d);

    vec3 color = mix(uColorA, uColorB, vMix);
    // 呼吸感：极轻微的明度起伏
    float breathe = 0.72 + 0.28 * sin(vSeed * 6.28 + vMix * 3.0);

    gl_FragColor = vec4(color, soft * uOpacity * breathe);
  }
`

/* ---------------- 初始化 ---------------- */
function init() {
  const canvas = canvasRef.value
  if (!canvas) return

  try {
    renderer = new THREE.WebGLRenderer({
      canvas,
      alpha: true,
      antialias: false,
      powerPreference: 'low-power',
    })
  } catch {
    // WebGL 不可用：静默降级
    renderer = null
    return
  }

  scene = new THREE.Scene()
  camera = new THREE.PerspectiveCamera(60, 1, 0.1, 260)
  camera.position.set(0, 0, 30)

  buildParticles()

  material = new THREE.ShaderMaterial({
    uniforms: {
      uTime: { value: 0 },
      uPixelRatio: { value: Math.min(window.devicePixelRatio, 2) },
      uSize: { value: 5.5 },
      uFocal: { value: FOCAL },
      uOpacity: { value: 0.5 },
      // 陶土橘 #b45309 与暖褐 #8a7a63
      uColorA: { value: new THREE.Color('#b45309') },
      uColorB: { value: new THREE.Color('#8a7a63') },
    },
    vertexShader,
    fragmentShader,
    transparent: true,
    depthWrite: false,
    // 浅色底必须用普通混合：加法混合在奶油色上会冲白发虚
    blending: THREE.NormalBlending,
  })

  points = new THREE.Points(geometry!, material)
  scene.add(points)
  resize()
}

function resize() {
  const canvas = canvasRef.value
  if (!canvas || !renderer || !camera) return
  const w = canvas.clientWidth
  const h = canvas.clientHeight
  if (w === 0 || h === 0) return
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.setSize(w, h, false)
  camera.aspect = w / h
  camera.updateProjectionMatrix()
  if (material) material.uniforms.uPixelRatio.value = Math.min(window.devicePixelRatio, 2)
}

function tick() {
  if (!renderer || !scene || !camera || !material) return
  material.uniforms.uTime.value = clock.getElapsedTime()
  if (points) points.rotation.y = material.uniforms.uTime.value * 0.012
  renderer.render(scene, camera)
  if (running) raf = requestAnimationFrame(tick)
}

function start() {
  if (!renderer || !material || !scene || !camera) return
  cancelAnimationFrame(raf)
  running = true
  if (reduced) {
    // 减弱动效：只渲染一帧静态
    material.uniforms.uTime.value = 0
    renderer.render(scene, camera)
    return
  }
  raf = requestAnimationFrame(tick)
}

function onVisibility() {
  if (document.hidden) {
    running = false
    cancelAnimationFrame(raf)
  } else {
    start()
  }
}

onMounted(() => {
  reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  init()
  start()
  window.addEventListener('resize', resize)
  document.addEventListener('visibilitychange', onVisibility)
})

onBeforeUnmount(() => {
  running = false
  cancelAnimationFrame(raf)
  window.removeEventListener('resize', resize)
  document.removeEventListener('visibilitychange', onVisibility)
  // 释放 GPU 资源
  geometry?.dispose()
  material?.dispose()
  renderer?.dispose()
  renderer = null
})
</script>

<template>
  <canvas ref="canvasRef" class="particle-field" aria-hidden="true" />
</template>

<style scoped>
.particle-field {
  position: fixed;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  z-index: 0;
  /* 暖色主题下粒子已很淡，再压一档确保不影响阅读 */
  opacity: 0.6;
}
</style>
