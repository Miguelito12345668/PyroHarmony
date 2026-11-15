// Animation 3D : globe tournant avec points chauds
import * as THREE from 'https://unpkg.com/three@0.160.0/build/three.module.js';

const canvas = document.getElementById('hero-canvas');
if (!canvas) throw new Error('Canvas not found');

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 1000);
camera.position.z = 3.5;

const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

// Groupe contenant la Terre et les points chauds
const earthGroup = new THREE.Group();
scene.add(earthGroup);

// --- 1. Sphère wireframe (Terre) ---
const earthGeo = new THREE.IcosahedronGeometry(1, 4);
const earthMat = new THREE.MeshBasicMaterial({
  color: 0x2a3541,
  wireframe: true,
  transparent: true,
  opacity: 0.35
});
const earth = new THREE.Mesh(earthGeo, earthMat);
earthGroup.add(earth);

// --- 2. Sphère interne (halo) ---
const glowGeo = new THREE.SphereGeometry(0.98, 32, 32);
const glowMat = new THREE.MeshBasicMaterial({
  color: 0xfb923c,
  transparent: true,
  opacity: 0.03
});
earthGroup.add(new THREE.Mesh(glowGeo, glowMat));

// --- 3. Points chauds sur le Cameroun (coordonnées) ---
// Cameroun : lat ~4°N, lon ~12°E
// Formule : convertir lat/lon en x,y,z sur une sphère de rayon 1
function latLonToVec3(lat, lon, radius = 1.02) {
  const phi = (90 - lat) * (Math.PI / 180);
  const theta = (lon + 180) * (Math.PI / 180);
  return new THREE.Vector3(
    -radius * Math.sin(phi) * Math.cos(theta),
    radius * Math.cos(phi),
    radius * Math.sin(phi) * Math.sin(theta)
  );
}

// Points chauds générés autour du Cameroun
const firePoints = [];
const numFires = 200;
for (let i = 0; i < numFires; i++) {
  // Distribution dans la bbox du Cameroun
  const lat = 1.6 + Math.random() * (13.1 - 1.6);
  const lon = 8.5 + Math.random() * (16.2 - 8.5);
  const intensity = Math.random();
  
  // Position en 3D
  const pos = latLonToVec3(lat, lon, 1.01 + intensity * 0.02);
  
  // Couleur : jaune → rouge selon l'intensité
  const color = new THREE.Color().lerpColors(
    new THREE.Color(0xfbbf24),
    new THREE.Color(0xdc2626),
    intensity
  );
  
  // Petit point 3D
  const pointGeo = new THREE.SphereGeometry(0.008 + intensity * 0.012, 8, 8);
  const pointMat = new THREE.MeshBasicMaterial({ color });
  const point = new THREE.Mesh(pointGeo, pointMat);
  point.position.copy(pos);
  point.userData = { baseY: pos.y, intensity, phase: Math.random() * Math.PI * 2 };
  earthGroup.add(point);
  firePoints.push(point);
}

// --- 4. Lignes reliant les points (effet réseau) ---
const lineMaterial = new THREE.LineBasicMaterial({
  color: 0xfb923c,
  transparent: true,
  opacity: 0.08
});
for (let i = 0; i < 30; i++) {
  const start = firePoints[Math.floor(Math.random() * firePoints.length)];
  const end = firePoints[Math.floor(Math.random() * firePoints.length)];
  const points = [start.position.clone(), end.position.clone()];
  const geometry = new THREE.BufferGeometry().setFromPoints(points);
  const line = new THREE.Line(geometry, lineMaterial);
  earthGroup.add(line);
}

// --- 5. Étoiles en arrière-plan ---
const starsGeo = new THREE.BufferGeometry();
const starsCount = 500;
const starPositions = new Float32Array(starsCount * 3);
for (let i = 0; i < starsCount * 3; i += 3) {
  const r = 15 + Math.random() * 20;
  const theta = Math.random() * Math.PI * 2;
  const phi = Math.acos(2 * Math.random() - 1);
  starPositions[i] = r * Math.sin(phi) * Math.cos(theta);
  starPositions[i + 1] = r * Math.sin(phi) * Math.sin(theta);
  starPositions[i + 2] = r * Math.cos(phi);
}
starsGeo.setAttribute('position', new THREE.BufferAttribute(starPositions, 3));
const starsMat = new THREE.PointsMaterial({
  color: 0xffffff,
  size: 0.03,
  transparent: true,
  opacity: 0.6
});
scene.add(new THREE.Points(starsGeo, starsMat));

// --- 6. Animation ---
let lastTime = 0;
function animate(time) {
  requestAnimationFrame(animate);
  const delta = (time - lastTime) / 1000;
  lastTime = time;
  
  // Rotation lente de la Terre
  earthGroup.rotation.y += delta * 0.15;
  
  // Pulsation des points chauds
  firePoints.forEach((point, i) => {
    const scale = 1 + Math.sin(time * 0.002 + point.userData.phase) * 0.3;
    point.scale.setScalar(scale);
  });
}
animate(0);

// --- 7. Responsive ---
window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});

// --- 8. Effet de parallaxe au scroll ---
window.addEventListener('scroll', () => {
  const scrollY = window.scrollY;
  if (scrollY < window.innerHeight) {
    earthGroup.rotation.x = scrollY * 0.0003;
    camera.position.z = 3.5 + scrollY * 0.001;
  }
});