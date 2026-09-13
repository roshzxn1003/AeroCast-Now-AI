import * as THREE from 'three';

/**
 * Procedural 3D Fractal Lightning Engine.
 *
 * Simulates real stepped-leader convective lightning discharges:
 * - 3D Recursive midpoint fractal subdivision for jagged geometry
 * - Branching fork leaders splitting off at natural bifurcation angles
 * - Multi-stroke return flickers (microsecond double/triple strikes)
 * - Cloud-to-Ground (CG) vs Intra-Cloud (IC / Spider crawler) morphologies
 * - Ground impact flash crater & expanding electric shockwaves
 */

export interface LightningStrikeParams {
  id: string;
  start: THREE.Vector3; // Cloud charge center
  end: THREE.Vector3;   // Ground impact or secondary cloud center
  type: 'CG' | 'IC';
  age_ms: number;
  duration_ms: number;
  intensity: number;
}

export class ProceduralLightningManager {
  private scene: THREE.Scene;
  private activeStrikes: Map<string, ActiveStrikeMesh> = new Map();
  private flashLight: THREE.PointLight;

  constructor(scene: THREE.Scene) {
    this.scene = scene;

    // Transient point light for realistic atmospheric cloud & ground illumination
    this.flashLight = new THREE.PointLight(0x7dd3fc, 0, 80, 1.8);
    this.scene.add(this.flashLight);
  }

  /**
   * Spawns a new procedural lightning bolt.
   */
  public triggerStrike(
    id: string,
    startCoords: THREE.Vector3,
    endCoords: THREE.Vector3,
    type: 'CG' | 'IC' = 'CG',
    intensity = 1.0,
  ) {
    // If strike already exists, refresh it
    if (this.activeStrikes.has(id)) {
      this.removeStrike(id);
    }

    const group = new THREE.Group();

    // 1. Generate main jagged trunk
    const mainBranch = this.generateFractalBranch(startCoords, endCoords, 4, 1.8 * intensity);
    group.add(mainBranch.core);
    group.add(mainBranch.glow);

    // 2. Generate 1-3 secondary fork branches
    const forkCount = type === 'CG' ? Math.floor(1 + Math.random() * 3) : Math.floor(2 + Math.random() * 3);
    const points = mainBranch.points;

    for (let i = 0; i < forkCount; i++) {
      if (points.length < 6) break;
      // Pick an intermediate point on the main trunk
      const branchIdx = Math.floor(points.length * (0.25 + Math.random() * 0.5));
      const forkStart = points[branchIdx].clone();

      // Branch shoots outward at an acute angle and downward
      const dir = endCoords.clone().sub(startCoords).normalize();
      const perp = new THREE.Vector3(
        (Math.random() - 0.5),
        (Math.random() - 0.5),
        (Math.random() - 0.5)
      ).cross(dir).normalize();

      const forkLength = startCoords.distanceTo(endCoords) * (0.35 + Math.random() * 0.35);
      const forkEnd = forkStart.clone()
        .add(dir.clone().multiplyScalar(forkLength * 0.6))
        .add(perp.clone().multiplyScalar(forkLength * 0.5));

      const forkBranch = this.generateFractalBranch(forkStart, forkEnd, 3, 1.2 * intensity);
      group.add(forkBranch.core);
      group.add(forkBranch.glow);
    }

    // 3. Ground impact crater flash disc (for Cloud-to-Ground)
    let impactMesh: THREE.Mesh | null = null;
    if (type === 'CG') {
      const craterGeo = new THREE.RingGeometry(0.2, 1.8, 24);
      const craterMat = new THREE.MeshBasicMaterial({
        color: 0x67e8f9,
        transparent: true,
        opacity: 0.95,
        side: THREE.DoubleSide,
        depthWrite: false,
      });
      impactMesh = new THREE.Mesh(craterGeo, craterMat);
      impactMesh.position.copy(endCoords);
      impactMesh.lookAt(new THREE.Vector3(0, 0, 0)); // Align with globe surface
      group.add(impactMesh);
    }

    this.scene.add(group);

    // Position atmospheric flash light at the strike core
    this.flashLight.position.copy(type === 'CG' ? endCoords.clone().lerp(startCoords, 0.25) : startCoords);
    this.flashLight.intensity = 8.0 * intensity;
    this.flashLight.color.setHex(type === 'CG' ? 0xe0f2fe : 0xc084fc);

    const activeStrike: ActiveStrikeMesh = {
      id,
      group,
      startTime: performance.now(),
      duration: 380, // 380ms total multi-stroke lifespan
      type,
      impactMesh,
      intensity,
      materials: [
        mainBranch.core.material as THREE.LineBasicMaterial,
        mainBranch.glow.material as THREE.LineBasicMaterial,
      ],
    };

    this.activeStrikes.set(id, activeStrike);
  }

  /**
   * Generates a jagged 3D fractal polyline using recursive midpoint displacement.
   */
  private generateFractalBranch(
    start: THREE.Vector3,
    end: THREE.Vector3,
    iterations = 4,
    displacement = 1.5,
  ): { core: THREE.Line; glow: THREE.Line; points: THREE.Vector3[] } {
    let points: THREE.Vector3[] = [start.clone(), end.clone()];

    for (let iter = 0; iter < iterations; iter++) {
      const newPoints: THREE.Vector3[] = [];
      const currentDisp = displacement / Math.pow(1.65, iter);

      for (let i = 0; i < points.length - 1; i++) {
        const p1 = points[i];
        const p2 = points[i + 1];
        const mid = p1.clone().add(p2).multiplyScalar(0.5);

        // Vector perpendicular to the segment
        const dir = p2.clone().sub(p1);
        const randomVec = new THREE.Vector3(
          Math.random() - 0.5,
          Math.random() - 0.5,
          Math.random() - 0.5
        ).normalize();
        const perp = randomVec.cross(dir).normalize();

        // Displace the midpoint
        mid.add(perp.multiplyScalar(currentDisp * (Math.random() * 2 - 1)));

        newPoints.push(p1);
        newPoints.push(mid);
      }
      newPoints.push(points[points.length - 1]);
      points = newPoints;
    }

    const geometry = new THREE.BufferGeometry().setFromPoints(points);

    // Pure white hot core line
    const coreMat = new THREE.LineBasicMaterial({
      color: 0xffffff,
      transparent: true,
      opacity: 1.0,
      linewidth: 2,
      depthWrite: false,
    });
    const core = new THREE.Line(geometry, coreMat);

    // Electric cyan/blue outer halo glow line
    const glowMat = new THREE.LineBasicMaterial({
      color: 0x38bdf8,
      transparent: true,
      opacity: 0.85,
      linewidth: 4,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
    const glow = new THREE.Line(geometry, glowMat);

    return { core, glow, points };
  }

  /**
   * Called every animation frame to update return stroke flickers and clean up expired bolts.
   */
  public update() {
    const now = performance.now();
    let maxLightIntensity = 0;

    this.activeStrikes.forEach((strike, id) => {
      const elapsed = now - strike.startTime;
      const progress = elapsed / strike.duration;

      if (progress >= 1.0) {
        this.removeStrike(id);
        return;
      }

      // Exact multi-stroke return flicker curve:
      // Stroke 1: 0 - 50ms (peak 1.0 -> dip 0.25)
      // Stroke 2 (Return stroke): 50 - 130ms (peak 0.95 -> dip 0.35)
      // Stroke 3: 130 - 200ms (peak 0.65)
      // Decay: 200 - 380ms (fade out to 0)
      let brightness = 0;

      if (elapsed < 50) {
        brightness = 1.0 - (elapsed / 50) * 0.7; // 1.0 -> 0.3
      } else if (elapsed < 120) {
        const t = (elapsed - 50) / 70;
        brightness = 0.3 + Math.sin(t * Math.PI) * 0.65; // return burst up to 0.95
      } else if (elapsed < 200) {
        const t = (elapsed - 120) / 80;
        brightness = 0.4 + Math.sin(t * Math.PI) * 0.4; // secondary flicker
      } else {
        const t = (elapsed - 200) / 180;
        brightness = 0.35 * (1 - t * t); // smooth plasma decay
      }

      brightness = Math.max(0, Math.min(1, brightness)) * strike.intensity;

      // Update bolt materials
      strike.materials.forEach((mat) => {
        mat.opacity = brightness;
      });

      // Expand and fade impact crater
      if (strike.impactMesh) {
        const scale = 1.0 + progress * 2.5;
        strike.impactMesh.scale.set(scale, scale, 1);
        const mat = strike.impactMesh.material as THREE.MeshBasicMaterial;
        mat.opacity = (1 - progress) * 0.85;
      }

      if (brightness > maxLightIntensity) {
        maxLightIntensity = brightness;
      }
    });

    // Fade atmospheric point light
    this.flashLight.intensity = maxLightIntensity * 7.5;
  }

  private removeStrike(id: string) {
    const strike = this.activeStrikes.get(id);
    if (!strike) return;

    this.scene.remove(strike.group);
    strike.group.traverse((obj) => {
      if ((obj as THREE.Mesh).geometry) {
        (obj as THREE.Mesh).geometry.dispose();
      }
      if ((obj as THREE.Mesh).material) {
        const m = (obj as THREE.Mesh).material;
        if (Array.isArray(m)) m.forEach((mat) => mat.dispose());
        else m.dispose();
      }
    });

    this.activeStrikes.delete(id);
  }

  public clear() {
    this.activeStrikes.forEach((_, id) => this.removeStrike(id));
    this.flashLight.intensity = 0;
  }

  public dispose() {
    this.clear();
    this.scene.remove(this.flashLight);
    this.flashLight.dispose();
  }
}

interface ActiveStrikeMesh {
  id: string;
  group: THREE.Group;
  startTime: number;
  duration: number;
  type: 'CG' | 'IC';
  impactMesh: THREE.Mesh | null;
  intensity: number;
  materials: THREE.LineBasicMaterial[];
}
