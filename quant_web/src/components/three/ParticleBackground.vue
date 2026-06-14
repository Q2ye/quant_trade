<template>
  <div ref="containerRef" class="particle-bg"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from "vue";
import * as THREE from "three";

const props = withDefaults(
  defineProps<{
    particleCount?: number;
    color?: string;
    size?: number;
    opacity?: number;
    parallax?: number; // mouse parallax strength, 0 = off
  }>(),
  {
    particleCount: 1000,
    color: "#2196F3",
    size: 0.02,
    opacity: 0.4,
    parallax: 0.3,
  },
);

const containerRef = ref<HTMLElement | null>(null);

let scene: THREE.Scene | null = null;
let camera: THREE.PerspectiveCamera | null = null;
let renderer: THREE.WebGLRenderer | null = null;
let particles: THREE.Points | null = null;
let animationId = 0;
let isPageVisible = true;
let resizeObserver: ResizeObserver | null = null;

// mouse position in normalized coords [-1, 1]
const mouse = { x: 0, y: 0 };
const target = { x: 0, y: 0 };

const ZOOM = 0.8; // 与 CSS --zoom-scale 保持一致
function onMouseMove(e: MouseEvent) {
  mouse.x = (e.clientX / window.innerWidth / ZOOM) * 2 - 1;
  mouse.y = -(e.clientY / window.innerHeight / ZOOM) * 2 + 1;
}

function init(): boolean {
  const container = containerRef.value;
  if (!container) return false;

  // WebGL fallback check
  try {
    const testCanvas = document.createElement("canvas");
    const gl =
      testCanvas.getContext("webgl") ||
      testCanvas.getContext("experimental-webgl");
    if (!gl) throw new Error("WebGL not supported");
  } catch {
    console.warn(
      "[ParticleBackground] WebGL unavailable — falling back to CSS gradient",
    );
    return false;
  }

  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(
    75,
    container.clientWidth / Math.max(container.clientHeight, 1),
    0.1,
    1000,
  );
  camera.position.z = 5;

  renderer = new THREE.WebGLRenderer({ alpha: true, antialias: false });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(container.clientWidth, container.clientHeight);
  container.appendChild(renderer.domElement);

  const geometry = new THREE.BufferGeometry();
  const positions = new Float32Array(props.particleCount * 3);
  for (let i = 0; i < props.particleCount * 3; i += 3) {
    positions[i] = (Math.random() - 0.5) * 10;
    positions[i + 1] = (Math.random() - 0.5) * 10;
    positions[i + 2] = (Math.random() - 0.5) * 10;
  }
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));

  const material = new THREE.PointsMaterial({
    color: new THREE.Color(props.color),
    size: props.size,
    transparent: true,
    opacity: props.opacity,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });

  particles = new THREE.Points(geometry, material);
  scene.add(particles);

  // ResizeObserver on container — more accurate than window resize
  resizeObserver = new ResizeObserver(() => {
    if (!container || !renderer || !camera) return;
    const w = container.clientWidth;
    const h = container.clientHeight;
    renderer.setSize(w, h);
    camera.aspect = w / Math.max(h, 1);
    camera.updateProjectionMatrix();
  });
  resizeObserver.observe(container);

  window.addEventListener("mousemove", onMouseMove, { passive: true });
  document.addEventListener("visibilitychange", onVisibilityChange);

  return true;
}

function startLoop() {
  if (animationId) return;
  function loop() {
    animationId = requestAnimationFrame(loop);
    if (!isPageVisible) return;

    // Smooth mouse parallax
    target.x += (mouse.x - target.x) * 0.05;
    target.y += (mouse.y - target.y) * 0.05;

    if (particles) {
      // base rotation
      particles.rotation.x += 0.0002;
      particles.rotation.y += 0.0003;
      // mouse parallax offset
      particles.position.x = target.x * props.parallax;
      particles.position.y = target.y * props.parallax;
      // natural drift on Z axis
      particles.rotation.z += 0.0001;
    }

    if (renderer && scene && camera) {
      renderer.render(scene, camera);
    }
  }
  loop();
}

function stopLoop() {
  if (animationId) {
    cancelAnimationFrame(animationId);
    animationId = 0;
  }
}

function onVisibilityChange() {
  isPageVisible = !document.hidden;
  if (isPageVisible) {
    startLoop();
  } else {
    stopLoop();
  }
}

onMounted(() => {
  if (init()) {
    startLoop();
  }
});

onUnmounted(() => {
  stopLoop();
  resizeObserver?.disconnect();
  window.removeEventListener("mousemove", onMouseMove);
  document.removeEventListener("visibilitychange", onVisibilityChange);

  if (renderer) {
    renderer.dispose();
    if (
      containerRef.value &&
      renderer.domElement.parentNode === containerRef.value
    ) {
      containerRef.value.removeChild(renderer.domElement);
    }
    renderer = null;
  }
  if (particles) {
    particles.geometry.dispose();
    (particles.material as THREE.Material).dispose();
    particles = null;
  }
  scene = null;
  camera = null;
});
</script>

<style scoped>
.particle-bg {
  position: absolute;
  inset: 0;
  z-index: 1;
  pointer-events: none;
  overflow: hidden;
}
</style>
