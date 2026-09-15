import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Globe, { GlobeInstance } from 'globe.gl';
import * as THREE from 'three';
import { useLiveStore } from '../store/liveStore';
import { useNowcastStore } from '../store/nowcastStore';
import { ConvectiveNode, Strike } from '../types/nowcast';
import { ACCENT, FLASH, severityColor, SURFACE } from '../design/tokens';
import { ProceduralLightningManager } from '../effects/lightningGenerator';
import { thunderAudio } from '../effects/thunderAudio';
import { MAJOR_INDIAN_CITIES, CityPreset } from '../utils/weatherInterpreter';
import { DistrictOverlay } from './DistrictOverlay';
import {
  Volume2,
  VolumeX,
  Sun,
  Moon,
  ZoomIn,
  ZoomOut,
  Compass,
  Navigation,
  FileText,
  RotateCw,
  Maximize2,
  Minimize2,
  Zap,
  Radio,
  X,
} from 'lucide-react';
import { ProvenanceBadge } from './ui';

/**
 * Deep, Photorealistic 3D Earth Globe with Procedural Lightning Simulation.
 *
 * Capabilities:
 * - Photorealistic satellite basemap & 3D mountain elevation bump map
 * - Independent rotating 3D atmospheric cloud deck
 * - Deep, unrestricted zoom into India down to city/street level (minDistance 101.5)
 * - Indian state boundary outlines
 * - 3D procedural fractal jagged lightning bolts with stepped leaders & return strokes
 * - Ground impact flash craters and atmospheric cloud illumination
 * - Web Audio API spatial rolling thunder audio with on-screen mute control
 * - Indian city beacons with weather status badges & 1-click smooth camera flight
 * - Floating glassmorphic HUD for regional navigation & camera presets
 * - All 734 India districts: boundaries, live convective choropleth, search
 *   and per-district readout (see DistrictOverlay / globe/districtLayer)
 */

const HOME_CENTRE = { lat: 21.0, lng: 80.0 };

/**
 * Camera distance needed to frame India for a given viewport.
 *
 * globe.gl fits its field of view vertically, so a narrow portrait pane crops
 * the country badly at the altitude that suits a wide desktop pane. Pulling the
 * camera back on small and tall viewports keeps the whole domain visible.
 */
function homeAltitude(width: number, height: number): number {
  if (width < 640) return 2.3;
  if (height > width) return 1.8;
  if (width < 1100) return 1.5;
  return 1.15;
}

function homePov(el: HTMLElement | null) {
  const rect = el?.getBoundingClientRect();
  return {
    ...HOME_CENTRE,
    altitude: homeAltitude(rect?.width || window.innerWidth, rect?.height || window.innerHeight),
  };
}

const REGIONAL_PRESETS = [
  { id: 'all', label: 'All India', lat: 21.0, lng: 80.0, altitude: 1.65 },
  { id: 'tamil-nadu', label: 'Tamil Nadu (38 Dists)', lat: 11.1271, lng: 78.6569, altitude: 0.48 },
  { id: 'south', label: 'South (Chennai/Blr)', lat: 13.0, lng: 79.5, altitude: 0.38 },
  { id: 'north', label: 'North (Delhi/NCR)', lat: 28.5, lng: 77.5, altitude: 0.38 },
  { id: 'west', label: 'West (Mumbai/Guj)', lat: 19.5, lng: 73.5, altitude: 0.38 },
  { id: 'east', label: 'East (Kolkata/NE)', lat: 23.0, lng: 88.0, altitude: 0.38 },
];

/**
 * Cloud-deck fade window, in camera altitude.
 *
 * The deck is a 1024px whole-Earth texture floating above the surface. Far out
 * it reads as weather; close in it is a blur sitting on top of the tile
 * basemap, hiding exactly the detail the tiles are there to show. So it fades
 * out over this range and is gone by the time street-level imagery is legible.
 */
const CLOUD_FADE_START = 0.9;
const CLOUD_FADE_END = 0.22;

const RIPPLE_STRIKE_COUNT = 30;
const RIPPLE_MAX_AGE_S = 90;

interface LightningGlobeProps {
  onNodeSelect?: (node: ConvectiveNode) => void;
  onOpenStateReport?: (stateSlug: string) => void;
  targetFocus?: { lat: number; lng: number; altitude?: number } | null;
  className?: string;
}

export const LightningGlobe: React.FC<LightningGlobeProps> = ({
  onNodeSelect,
  onOpenStateReport,
  targetFocus,
  className,
}) => {
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const globeRef = useRef<GlobeInstance | null>(null);
  const lightningManagerRef = useRef<ProceduralLightningManager | null>(null);
  const stateBordersRef = useRef<THREE.LineSegments | null>(null);
  const cloudsMeshRef = useRef<THREE.Mesh | null>(null);
  const animFrameRef = useRef<number | null>(null);

  const [ready, setReady] = useState(false);
  const [hovered, setHovered] = useState<ConvectiveNode | null>(null);
  const [selectedCityInfo, setSelectedCityInfo] = useState<CityPreset | null>(null);
  const [isAutoRotating, setIsAutoRotating] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [activePresetId, setActivePresetId] = useState('all');

  // Held in a ref, not state: this is a comparison baseline for the thunder
  // trigger, and storing it in state made the strike effect re-enter itself.
  const lastStrikeCountRef = useRef(0);

  const targetCloudOpacityRef = useRef(0.38);
  const currentCloudOpacityRef = useRef(0.38);

  // Zustand stores
  const convective = useLiveStore((s) => s.convective);
  const lightning = useLiveStore((s) => s.lightning);
  const summary = useLiveStore((s) => s.summary);
  const focusedNode = useLiveStore((s) => s.focusedNode);
  const setFocusedNode = useLiveStore((s) => s.setFocusedNode);

  const {
    earthTheme,
    setEarthTheme,
    soundEnabled,
    setSoundEnabled,
    setSelectedStation,
  } = useNowcastStore();

  const nodes = useMemo(() => convective?.nodes ?? [], [convective]);
  const strikes = useMemo(() => lightning?.strikes ?? [], [lightning]);

  const rippleStrikes = useMemo(
    () =>
      strikes
        .filter((s) => s.age_s <= RIPPLE_MAX_AGE_S)
        .slice(0, RIPPLE_STRIKE_COUNT),
    [strikes],
  );

  // ---------------------------------------------------------------------------
  // 1. Initialize Globe with Deep Camera Zoom & Photorealistic Textures
  // ---------------------------------------------------------------------------

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    // High-resolution satellite textures (offline-ready from public/textures/)
    const globeImage = earthTheme === 'night' ? '/textures/earth-night.jpg' : '/textures/earth-blue-marble.jpg';

    const globe = new Globe(el, { animateIn: true })
      .backgroundColor('rgba(0,0,0,0)')
      .globeImageUrl(globeImage)
      .bumpImageUrl('/textures/earth-topology.png')
      .backgroundImageUrl('/textures/night-sky.jpg')
      .showAtmosphere(true)
      .atmosphereColor(earthTheme === 'night' ? '#38bdf8' : '#60a5fa')
      .atmosphereAltitude(0.18)
      .showGraticules(false);

    const controls = globe.controls() as unknown as {
      autoRotate: boolean;
      autoRotateSpeed: number;
      enableDamping: boolean;
      dampingFactor: number;
      minDistance: number;
      maxDistance: number;
      enableRotate: boolean;
      enableZoom: boolean;
      enablePan: boolean;
      minPolarAngle: number;
      maxPolarAngle: number;
      rotateSpeed: number;
      zoomSpeed: number;
    };

    // Labels are only legible once the camera is close enough that the cities
    // are not crowded into a few pixels of each other.
    const LABEL_ALTITUDE = 1.4;
    let labelsShown: boolean | null = null;
    const syncLabels = (altitude: number) => {
      const show = altitude < LABEL_ALTITUDE;
      if (show === labelsShown) return;
      labelsShown = show;
      el.classList.toggle('show-city-names', show);
    };
    /**
     * Scale the sounding columns and the drag speed to the camera altitude.
     *
     * Both are fixed fractions of the globe radius, which is right when the
     * whole country is in frame and wrong once it is not: a column 11% of the
     * Earth's radius tall becomes a skyscraper straddling the viewport at city
     * zoom, and a drag that spins the planet at that altitude is unusable.
     * Recomputed only when the altitude has moved enough to matter, because
     * re-applying a globe.gl accessor rebuilds that layer.
     */
    let lastScaleBand = -1;
    const syncScale = (altitude: number) => {
      const scale = Math.min(1, Math.max(0.08, Math.sqrt(altitude / 1.2)));

      // Drag speed: calm, slow, natural, and controlled. Prevents overshooting or jumping.
      controls.rotateSpeed = Math.min(0.20, Math.max(0.10, 0.10 + altitude * 0.05));

      const band = Math.round(scale * 12);
      if (band === lastScaleBand) return;
      lastScaleBand = band;

      globe
        .pointAltitude((d) => (0.008 + (d as ConvectiveNode).intensity * 0.11) * scale)
        .pointRadius(
          (d) =>
            ((d as ConvectiveNode).thunderstorm_observed ? 0.22 : 0.13) *
            (0.35 + 0.65 * scale),
        );
    };

    globe.onZoom((pov: { altitude: number }) => {
      syncLabels(pov.altitude);
      syncScale(pov.altitude);
    });

    const initialPov = homePov(el);
    globe.pointOfView(initialPov, 0);
    syncLabels(initialPov.altitude);
    syncScale(initialPov.altitude);

    controls.autoRotate = false;
    controls.autoRotateSpeed = 0.22;
    controls.enableDamping = true;
    controls.dampingFactor = 0.22; // Weighted, tactile rotation that tracks cursor naturally without sliding away
    controls.zoomSpeed = 0.35;     // Gentle, controlled scroll wheel steps
    controls.minDistance = 101.5;  // Surface is radius 100 — allows ultra-close city zoom!
    controls.maxDistance = 650;

    // Double-click to smoothly zoom into clicked coordinates
    const onDblClick = (ev: MouseEvent) => {
      const rect = el.getBoundingClientRect();
      const coords = globe.toGlobeCoords(ev.clientX - rect.left, ev.clientY - rect.top);
      if (coords) {
        const current = globe.pointOfView();
        const targetAlt = Math.max(0.18, current.altitude * 0.65);
        globe.pointOfView({ lat: coords.lat, lng: coords.lng, altitude: targetAlt }, 800);
      }
    };
    el.addEventListener('dblclick', onDblClick);

    // Unrestricted orbit: the camera may travel over either pole and all the
    // way around, so any point on Earth can be brought into view by dragging
    // alone. OrbitControls clamps nothing here, and panning stays off because
    // moving the orbit target off the planet's centre is what makes a globe
    // feel broken rather than free.
    controls.enableRotate = true;
    controls.enableZoom = true;
    controls.enablePan = false;
    controls.minPolarAngle = 0;
    controls.maxPolarAngle = Math.PI;

    // A globe is a smooth, mostly-curved subject: rendering beyond ~1.5x adds
    // cost without visible benefit, and the transparent layers make every extra
    // fragment expensive.
    const renderer = globe.renderer();
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));

    globeRef.current = globe;

    // Development-only handle for render profiling (draw calls, triangle count,
    // texture memory). Stripped from production builds.
    if (import.meta.env.DEV) {
      (window as unknown as { __globe?: unknown }).__globe = globe;
    }

    // -------------------------------------------------------------------------
    // 2. Procedural Lightning Engine Setup
    // -------------------------------------------------------------------------
    const lightningManager = new ProceduralLightningManager(globe.scene());
    lightningManagerRef.current = lightningManager;

    // -------------------------------------------------------------------------
    // 3. Rotating 3D Cloud Sphere
    // -------------------------------------------------------------------------
    // Guards the async texture load against a superseded run of this effect.
    // Under StrictMode the effect mounts twice, and without this the first
    // run's callback lands after the second globe exists and overwrites
    // cloudsMeshRef with a mesh belonging to the destroyed globe. The live
    // deck is then orphaned: never rotated, never faded, permanently opaque.
    let cancelled = false;

    new THREE.TextureLoader().load(
      '/textures/clouds.png',
      (cloudsTexture) => {
        if (cancelled) {
          cloudsTexture.dispose();
          return;
        }

        cloudsTexture.wrapS = THREE.RepeatWrapping;
        cloudsTexture.wrapT = THREE.ClampToEdgeWrapping;

        const cloudRadius = globe.getGlobeRadius() * 1.004;
        const cloudGeo = new THREE.SphereGeometry(cloudRadius, 48, 32);
        const cloudMat = new THREE.MeshPhongMaterial({
          map: cloudsTexture,
          transparent: true,
          opacity: earthTheme === 'night' ? 0.45 : 0.72,
          depthWrite: false,
          blending: THREE.NormalBlending,
        });

        const cloudsMesh = new THREE.Mesh(cloudGeo, cloudMat);
        cloudsMeshRef.current = cloudsMesh;
        globe.scene().add(cloudsMesh);
      },
      undefined,
      (err) => console.warn('Cloud texture notice:', err)
    );

    // -------------------------------------------------------------------------
    // 4. Animation Loop for Lightning Flickers & Cloud Rotation
    // -------------------------------------------------------------------------
    const animate = () => {
      // Smoothly interpolate cloud opacity towards target theme opacity
      currentCloudOpacityRef.current +=
        (targetCloudOpacityRef.current - currentCloudOpacityRef.current) * 0.06;

      const clouds = cloudsMeshRef.current;
      if (clouds) {
        clouds.rotation.y += 0.00018; // Slow atmospheric cloud drift

        const { altitude } = globe.pointOfView();
        const t = Math.max(
          0,
          Math.min(1, (altitude - CLOUD_FADE_END) / (CLOUD_FADE_START - CLOUD_FADE_END)),
        );
        (clouds.material as THREE.MeshPhongMaterial).opacity = currentCloudOpacityRef.current * t;
        clouds.visible = t > 0.01;
      }
      lightningManagerRef.current?.update();
      animFrameRef.current = requestAnimationFrame(animate);
    };
    animFrameRef.current = requestAnimationFrame(animate);

    // -------------------------------------------------------------------------
    // 5. Load Country & Indian State Boundaries
    // -------------------------------------------------------------------------
    Promise.all([
      fetch('/geo/countries.geojson').then((r) => r.json()).catch(() => ({ features: [] })),
      fetch('/geo/indian_states.geojson').then((r) => r.json()).catch(() => ({ features: [] })),
    ]).then(([countries, indianStates]) => {
      // Only India is drawn as a polygon. The globe already carries a
      // photographic Earth texture, so outlining all 177 countries added no
      // information while costing a cap mesh, a side mesh and a stroke line
      // each — by far the largest contributor to per-frame draw calls.
      const indiaOutline = (countries.features || []).filter(
        (f: any) => f?.properties?.name === 'India',
      );
      const combinedFeatures = indiaOutline.map((f: any) => ({ ...f, __layer: 'country' }));

      // State boundaries are drawn as ONE merged line mesh rather than as 35
      // polygon features. globe.gl builds a cap mesh and a stroke line per ring,
      // and these 35 states carry 154 rings between them — roughly 300 extra
      // draw calls every frame for what is visually a set of thin lines.
      // Flattening them into a single LineSegments geometry costs exactly one.
      const borderPositions: number[] = [];
      const pushRing = (ring: number[][]) => {
        for (let i = 0; i < ring.length - 1; i++) {
          const a = globe.getCoords(ring[i][1], ring[i][0], 0.004);
          const b = globe.getCoords(ring[i + 1][1], ring[i + 1][0], 0.004);
          borderPositions.push(a.x, a.y, a.z, b.x, b.y, b.z);
        }
      };
      (indianStates.features || []).forEach((f: any) => {
        const geom = f.geometry;
        if (!geom) return;
        if (geom.type === 'Polygon') geom.coordinates.forEach(pushRing);
        else if (geom.type === 'MultiPolygon')
          geom.coordinates.forEach((poly: number[][][]) => poly.forEach(pushRing));
      });

      if (borderPositions.length) {
        const borderGeo = new THREE.BufferGeometry();
        borderGeo.setAttribute(
          'position',
          new THREE.Float32BufferAttribute(borderPositions, 3),
        );
        const borderMat = new THREE.LineBasicMaterial({
          color: new THREE.Color('#38bdf8'),
          transparent: true,
          opacity: 0.38,
          depthWrite: false,
        });
        const borderMesh = new THREE.LineSegments(borderGeo, borderMat);
        stateBordersRef.current = borderMesh;
        globe.scene().add(borderMesh);
      }

      globe
        .polygonsData(combinedFeatures)
        .polygonAltitude(0.002)
        .polygonCapColor(() => 'rgba(56, 189, 248, 0.08)')
        .polygonSideColor(() => 'rgba(0,0,0,0)')
        .polygonStrokeColor(() => 'rgba(56, 189, 248, 0.85)');

      setReady(true);
    });

    // Handle responsive container resize
    const resize = () => {
      const { width, height } = el.getBoundingClientRect();
      if (width && height) globe.width(width).height(height);
    };
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(el);

    return () => {
      cancelled = true;
      el.removeEventListener('dblclick', onDblClick);
      cloudsMeshRef.current = null;
      observer.disconnect();
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
      lightningManager.dispose();
      if (stateBordersRef.current) {
        stateBordersRef.current.geometry.dispose();
        (stateBordersRef.current.material as THREE.Material).dispose();
        stateBordersRef.current = null;
      }
      globe._destructor?.();
      globeRef.current = null;
    };
  }, []);

  // ---------------------------------------------------------------------------
  // Dynamic Earth Theme Synchronization (Smooth transition without reload)
  // ---------------------------------------------------------------------------
  useEffect(() => {
    const globe = globeRef.current;
    if (!globe || !ready) return;
    targetCloudOpacityRef.current = earthTheme === 'night' ? 0.38 : 0.70;
    const globeImage =
      earthTheme === 'night' ? '/textures/earth-night.jpg' : '/textures/earth-blue-marble.jpg';
    globe.globeImageUrl(globeImage);
    globe.atmosphereColor(earthTheme === 'night' ? '#38bdf8' : '#60a5fa');
    globe.atmosphereAltitude(earthTheme === 'night' ? 0.14 : 0.18);
  }, [earthTheme, ready]);

  // ---------------------------------------------------------------------------
  // 6. Real-Time Procedural Lightning Discharge & Thunder Audio Sync
  // ---------------------------------------------------------------------------

  useEffect(() => {
    const globe = globeRef.current;
    const lightningManager = lightningManagerRef.current;
    if (!globe || !lightningManager || !ready || strikes.length === 0) return;

    // Trigger visual 3D bolts for newest strikes (< 45s old)
    const freshStrikes = strikes.filter((s) => s.age_s <= 45).slice(0, 12);

    freshStrikes.forEach((strike, idx) => {
      const start = globe.getCoords(strike.lat, strike.lon, 0.045); // Cloud deck height
      // Ground or secondary cloud coordinate.
      //
      // The cloud-to-ground terminus sits at 0.005, not at the surface: the
      // tile basemap occupies up to ~0.0030, so a bolt ending at 0.001 had its
      // final segment and its entire ground-impact flash buried under the map.
      // This keeps the strike point visibly on top of the terrain.
      const end = globe.getCoords(
        strike.lat + (strike.type === 'IC' ? 0.25 : 0),
        strike.lon + (strike.type === 'IC' ? 0.25 : 0),
        strike.type === 'IC' ? 0.038 : 0.005
      );

      if (start && end) {
        const startVec = new THREE.Vector3(start.x, start.y, start.z);
        const endVec = new THREE.Vector3(end.x, end.y, end.z);
        const intensity = Math.min(1.0, 0.6 + Math.random() * 0.4);

        // Procedural fractal bolt trigger
        lightningManager.triggerStrike(
          `strike-${idx}-${strike.lat.toFixed(2)}-${strike.lon.toFixed(2)}`,
          startVec,
          endVec,
          strike.type,
          intensity
        );
      }
    });

    // Play synthesized rolling thunder sound if strike count increased
    if (strikes.length > lastStrikeCountRef.current && soundEnabled) {
      const newest = strikes[0];
      // Stereo pan based on strike longitude relative to central Indian meridian (80°E)
      const pan = Math.max(-0.8, Math.min(0.8, (newest.lon - 80.0) / 12.0));
      thunderAudio.play(0.85, newest.type === 'CG', pan);
    }
    lastStrikeCountRef.current = strikes.length;
  }, [strikes, ready, soundEnabled]);

  // ---------------------------------------------------------------------------
  // 7. Convective Sounding Nodes (Vigour Columns)
  // ---------------------------------------------------------------------------

  const handleNodeClick = useCallback(
    (node: ConvectiveNode) => {
      setFocusedNode(node);
      onNodeSelect?.(node);
      const globe = globeRef.current;
      if (globe) {
        globe.pointOfView({ lat: node.lat, lng: node.lon, altitude: 0.42 }, 1100);
      }
    },
    [onNodeSelect, setFocusedNode]
  );

  useEffect(() => {
    const globe = globeRef.current;
    if (!globe || !ready) return;

    globe
      .pointsData(nodes as unknown as object[])
      .pointLat((d) => (d as ConvectiveNode).lat)
      .pointLng((d) => (d as ConvectiveNode).lon)
      .pointColor((d) => severityColor((d as ConvectiveNode).instability))
      .pointAltitude((d) => 0.008 + (d as ConvectiveNode).intensity * 0.11)
      .pointRadius((d) => ((d as ConvectiveNode).thunderstorm_observed ? 0.22 : 0.13))
      .pointsMerge(false)
      .pointsTransitionDuration(600)
      .onPointClick((d) => handleNodeClick(d as ConvectiveNode))
      .onPointHover((d) => {
        setHovered((d as ConvectiveNode) ?? null);
        if (containerRef.current) {
          containerRef.current.style.cursor = d ? 'pointer' : 'grab';
        }
      });
  }, [nodes, ready, handleNodeClick]);

  // ---------------------------------------------------------------------------
  // 8. Surface Shockwave Rings
  // ---------------------------------------------------------------------------

  useEffect(() => {
    const globe = globeRef.current;
    if (!globe || !ready) return;

    globe
      .ringsData(rippleStrikes as unknown as object[])
      .ringLat((d) => (d as Strike).lat)
      .ringLng((d) => (d as Strike).lon)
      .ringColor((d: object) => {
        const strike = d as Strike;
        const base = strike.type === 'CG' ? FLASH.cg : FLASH.ic;
        return (t: number) => withAlpha(base, 1 - t);
      })
      .ringMaxRadius((d) => ((d as Strike).type === 'CG' ? 3.4 : 2.0))
      .ringPropagationSpeed(2.2)
      .ringRepeatPeriod((d) => ((d as Strike).type === 'CG' ? 800 : 1300))
      .ringAltitude(0.008);
  }, [rippleStrikes, ready]);

  // ---------------------------------------------------------------------------
  // 9. Interactive Indian City Beacons (Deep Zoom Markers)
  // ---------------------------------------------------------------------------

  useEffect(() => {
    const globe = globeRef.current;
    if (!globe || !ready) return;

    globe
      .htmlElementsData(MAJOR_INDIAN_CITIES)
      .htmlLat((d) => (d as CityPreset).lat)
      .htmlLng((d) => (d as CityPreset).lng)
      .htmlAltitude(0.015)
      .htmlElement((d: object) => {
        const city = d as CityPreset;
        const el = document.createElement('div');
        // The marker dot is centred exactly on the city's coordinate and the
        // name is positioned beside it. Laying the two out as a centred flex
        // row, as this previously did, pushed the dot half a label-width off
        // its true position — an error that grew with the length of the name.
        el.className =
          'group cursor-pointer pointer-events-auto relative transform -translate-x-1/2 -translate-y-1/2 transition-transform hover:scale-110';
        const onLeft = city.labelSide === 'left';
        el.innerHTML = `
          <div class="relative flex items-center justify-center w-2 h-2">
            <span class="w-2 h-2 rounded-full bg-cyan-400 ring-1 ring-white/80 shadow-sm transition-all duration-200 group-hover:scale-125 group-hover:bg-white"></span>
          </div>
          <span class="city-name absolute top-1/2 -translate-y-1/2 ${onLeft ? 'right-full mr-2' : 'left-full ml-2'} text-[11px] font-semibold text-slate-100 tracking-tight select-none whitespace-nowrap drop-shadow-[0_1px_2px_rgba(0,0,0,0.95)] drop-shadow-[0_0_8px_rgba(0,0,0,0.85)] transition-colors duration-150 group-hover:text-cyan-300">
            ${city.name}
          </span>
        `;

        el.addEventListener('click', () => {
          setSelectedCityInfo(city);
          setSelectedStation(city.stationName);
          const matchNode = (nodes as ConvectiveNode[]).find(
            (n) =>
              n.name.toLowerCase().includes(city.name.toLowerCase()) ||
              city.name.toLowerCase().includes(n.name.toLowerCase())
          );
          if (matchNode) setFocusedNode(matchNode);
          // Smooth 3D dive directly down to city level!
          globe.pointOfView({ lat: city.lat, lng: city.lng, altitude: 0.18 }, 1400);
        });

        return el;
      });
  }, [ready, setSelectedStation, setFocusedNode, nodes]);

  // ---------------------------------------------------------------------------
  // 10. Camera Zoom & Navigation Helpers
  // ---------------------------------------------------------------------------

  const flyToRegion = useCallback((preset: typeof REGIONAL_PRESETS[0]) => {
    setActivePresetId(preset.id);
    globeRef.current?.pointOfView({ lat: preset.lat, lng: preset.lng, altitude: preset.altitude }, 1200);
    setSelectedCityInfo(null);
  }, []);

  const handleZoom = useCallback((direction: 'in' | 'out') => {
    const globe = globeRef.current;
    if (!globe) return;
    const current = globe.pointOfView();
    const factor = direction === 'in' ? 0.65 : 1.45;
    const targetAlt = Math.max(0.03, Math.min(2.5, current.altitude * factor));
    globe.pointOfView({ ...current, altitude: targetAlt }, 400);
  }, []);

  const resetView = useCallback(() => {
    setActivePresetId('all');
    globeRef.current?.pointOfView(homePov(containerRef.current), 1000);
    setFocusedNode(null);
    setSelectedCityInfo(null);
  }, [setFocusedNode]);

  useEffect(() => {
    if (ready && globeRef.current && targetFocus) {
      globeRef.current.pointOfView(
        { lat: targetFocus.lat, lng: targetFocus.lng, altitude: targetFocus.altitude ?? 0.16 },
        1400
      );
    }
  }, [ready, targetFocus]);

  useEffect(() => {
    const globe = globeRef.current;
    if (!globe) return;
    const controls = globe.controls() as any;
    if (controls) {
      controls.autoRotate = isAutoRotating;
      controls.autoRotateSpeed = 0.22;
    }
  }, [isAutoRotating]);

  useEffect(() => {
    const onFsChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };
    document.addEventListener('fullscreenchange', onFsChange);
    return () => document.removeEventListener('fullscreenchange', onFsChange);
  }, []);

  const toggleFullscreen = useCallback(() => {
    if (!document.fullscreenElement) {
      wrapperRef.current?.requestFullscreen().catch(() => {});
    } else {
      document.exitFullscreen().catch(() => {});
    }
  }, []);

  const toggleSound = useCallback(() => {
    const next = !soundEnabled;
    setSoundEnabled(next);
    thunderAudio.setEnabled(next);
    if (next) {
      // Play brief test clap on activation
      thunderAudio.play(0.5, true, 0);
    }
  }, [soundEnabled, setSoundEnabled]);

  return (
    <div ref={wrapperRef} className={className}>
      <div
        ref={containerRef}
        className="absolute inset-0"
        style={{ background: SURFACE.void, cursor: 'grab' }}
        role="img"
        aria-label="Interactive 3D Convective Earth Globe with Procedural Lightning"
      />

      {/* District layer: boundaries, live choropleth, search, detail panel & unified legend */}
      <DistrictOverlay
        globe={ready ? globeRef.current : null}
        container={containerRef.current}
        renderTopDock={(searchElement) => (
          <div className="absolute top-3 inset-x-3 z-30 flex items-center justify-between gap-2 sm:gap-3 pointer-events-none">
            {/* Left: Live Convective Strike Monitor */}
            <div className="pointer-events-auto flex items-center gap-2 sm:gap-2.5 px-2.5 sm:px-3 py-1.5 rounded-xl bg-slate-900/90 border border-white/10 shadow-xl backdrop-blur-md shrink-0">
              <div className="flex items-center gap-1.5">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-amber-500" />
                </span>
                <Zap className="w-3.5 h-3.5 text-amber-400" />
              </div>
              <div className="flex items-baseline gap-1.5">
                <span className="font-mono text-base sm:text-lg font-bold leading-none text-amber-300">
                  {(summary?.strike_count_30min ?? 0).toLocaleString()}
                </span>
                <span className="text-[10px] uppercase font-mono tracking-wider text-slate-400 hidden sm:inline">
                  Flashes / 30m
                </span>
              </div>
              {lightning?.status && <ProvenanceBadge provenance={lightning.status} className="hidden md:inline-flex" />}
            </div>

            {/* Center: DistrictSearch Integrated in Flexbox (No collision) */}
            <div className="flex-1 max-w-xs sm:max-w-sm mx-auto pointer-events-auto min-w-0">
              {searchElement}
            </div>

            {/* Right: Mission Control Cluster */}
            <div className="pointer-events-auto flex items-center gap-1.5 shrink-0">
              <button
                onClick={() => onOpenStateReport?.('tamil-nadu')}
                title="Tamil Nadu 38-District Convective Intelligence & Warning Hub"
                className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl bg-cyan-950/90 border border-cyan-500/40 text-cyan-300 hover:text-white hover:bg-cyan-900/90 shadow-lg backdrop-blur-md transition-all font-mono text-xs font-bold tracking-wider hover:border-cyan-400"
              >
                <Radio className="w-3.5 h-3.5 text-cyan-400" />
                <span className="hidden sm:inline">TN Hub</span>
              </button>

              {/* Grouped Mission Toolbar */}
              <div className="flex items-center rounded-xl bg-slate-900/90 border border-white/10 p-0.5 shadow-lg backdrop-blur-md">
                <button
                  onClick={() => setEarthTheme(earthTheme === 'night' ? 'day' : 'night')}
                  title={`Switch to ${earthTheme === 'night' ? 'Daylight Marble' : 'Night Lights'} Texture`}
                  className="p-1.5 rounded-lg text-slate-300 hover:text-white hover:bg-slate-800/80 transition-colors"
                >
                  {earthTheme === 'night' ? (
                    <Moon className="w-3.5 h-3.5 text-cyan-400" />
                  ) : (
                    <Sun className="w-3.5 h-3.5 text-amber-400" />
                  )}
                </button>

                <button
                  onClick={toggleSound}
                  title={soundEnabled ? 'Mute Thunder Audio' : 'Enable Rolling Thunder Audio'}
                  className={`p-1.5 rounded-lg transition-colors ${
                    soundEnabled
                      ? 'text-cyan-300 bg-cyan-500/20'
                      : 'text-slate-400 hover:text-white hover:bg-slate-800/80'
                  }`}
                >
                  {soundEnabled ? <Volume2 className="w-3.5 h-3.5 text-cyan-400" /> : <VolumeX className="w-3.5 h-3.5" />}
                </button>

                <button
                  onClick={() => setIsAutoRotating((v) => !v)}
                  title={isAutoRotating ? 'Pause Orbit' : 'Auto-Rotate Earth'}
                  className={`p-1.5 rounded-lg transition-colors ${
                    isAutoRotating
                      ? 'text-cyan-300 bg-cyan-500/20'
                      : 'text-slate-400 hover:text-white hover:bg-slate-800/80'
                  }`}
                >
                  <RotateCw className={`w-3.5 h-3.5 ${isAutoRotating ? 'animate-spin' : ''}`} style={{ animationDuration: '6s' }} />
                </button>

                <button
                  onClick={toggleFullscreen}
                  title={isFullscreen ? 'Exit Fullscreen' : 'Fullscreen Globe View'}
                  className="p-1.5 rounded-lg text-slate-300 hover:text-white hover:bg-slate-800/80 transition-colors"
                >
                  {isFullscreen ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
                </button>
              </div>
            </div>
          </div>
        )}
      />

      {/* -------------------------------------- Hovered Sounding Node Tooltip HUD */}
      {hovered && (
        <div
          className="absolute top-[4.25rem] left-1/2 -translate-x-1/2 z-25 pointer-events-none flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-slate-900/95 border border-cyan-500/40 shadow-2xl backdrop-blur-md enter whitespace-nowrap"
        >
          <div className="flex items-center gap-1.5 text-xs font-bold text-white">
            <span className="w-2 h-2 rounded-full shrink-0" style={{ background: severityColor(hovered.instability) }} />
            <span>{hovered.name}</span>
            <span className="text-[10px] text-slate-400 font-normal">({hovered.region})</span>
          </div>
          <span className="text-slate-600">|</span>
          <div className="flex items-center gap-2 font-mono text-[11px]">
            <span style={{ color: severityColor(hovered.instability) }}>
              {hovered.instability}
            </span>
            <span className="text-slate-300">CAPE {hovered.cape_j_kg.toFixed(0)} J/kg</span>
            <span className="text-slate-300">LI {hovered.lifted_index_c.toFixed(1)}°C</span>
          </div>
        </div>
      )}

      {/* ---------------------------------------- Selected City Radar Inspector */}
      {selectedCityInfo && (
        <div className="absolute top-16 left-3 z-30 panel p-3.5 enter backdrop-blur-md max-w-xs bg-slate-900/95 border border-cyan-500/50 shadow-2xl rounded-2xl">
          <div className="flex items-start justify-between">
            <div>
              <div className="text-[10px] font-bold text-cyan-400 uppercase tracking-wider flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 ring-1 ring-cyan-300/60" />
                City Radar Inspection
              </div>
              <div className="text-base font-bold text-white mt-0.5">{selectedCityInfo.name}</div>
              <div className="text-[11px] text-slate-400">{selectedCityInfo.state}</div>
            </div>
            <button
              onClick={() => setSelectedCityInfo(null)}
              className="text-slate-400 hover:text-white text-xs p-1 rounded-lg bg-slate-800 hover:bg-slate-700 transition-colors ml-2"
              title="Close inspection"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
          <div className="mt-2.5 pt-2 border-t border-slate-800 text-[11px] text-slate-300 space-y-1">
            <div className="flex justify-between">
              <span className="text-slate-400">Doppler Radar:</span>
              <span className="font-mono text-cyan-300 font-semibold">{selectedCityInfo.dwrRadarName}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Scan Range:</span>
              <span className="font-mono text-slate-200">250 km Radius</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Status:</span>
              <span className="text-emerald-400 font-semibold">● ACTIVE NOWCAST</span>
            </div>
          </div>
        </div>
      )}

      {/* ------------------------------------------- Bottom-Center Regional HUD */}
      <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-20 hidden md:flex items-center gap-1 p-1 rounded-2xl bg-slate-900/90 border border-white/10 shadow-2xl backdrop-blur-md">
        <div className="flex items-center gap-1 pl-2 pr-1">
          <Navigation className="w-3.5 h-3.5 text-cyan-400" />
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
            Quick Nav:
          </span>
        </div>
        {REGIONAL_PRESETS.map((preset) => {
          const isActive = activePresetId === preset.id;
          return (
            <button
              key={preset.id}
              onClick={() => {
                setActivePresetId(preset.id);
                flyToRegion(preset);
              }}
              className={`px-2.5 py-1 rounded-xl text-[11px] font-medium whitespace-nowrap shrink-0 transition-all ${
                isActive
                  ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm font-semibold'
                  : 'text-slate-300 hover:text-white hover:bg-slate-800/80 border border-transparent'
              }`}
            >
              {preset.label}
            </button>
          );
        })}
      </div>

      {/* ------------------------------------------- Bottom-Right Camera Navigation */}
      <div className="absolute bottom-4 right-4 z-20 flex flex-col gap-1.5">
        <button
          onClick={() => handleZoom('in')}
          title="Zoom In (+)"
          className="w-8 h-8 rounded-xl bg-slate-900/90 border border-white/10 text-slate-300 hover:text-white hover:bg-slate-800/90 grid place-items-center shadow-lg backdrop-blur-md transition-all hover:border-cyan-500/40"
        >
          <ZoomIn className="w-4 h-4" />
        </button>
        <button
          onClick={() => handleZoom('out')}
          title="Zoom Out (-)"
          className="w-8 h-8 rounded-xl bg-slate-900/90 border border-white/10 text-slate-300 hover:text-white hover:bg-slate-800/90 grid place-items-center shadow-lg backdrop-blur-md transition-all hover:border-cyan-500/40"
        >
          <ZoomOut className="w-4 h-4" />
        </button>
        <button
          onClick={resetView}
          title="Reset to All India View"
          className="w-8 h-8 rounded-xl bg-slate-900/90 border border-white/10 text-slate-300 hover:text-cyan-400 hover:bg-slate-800/90 grid place-items-center shadow-lg backdrop-blur-md transition-all hover:border-cyan-500/40"
        >
          <Compass className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};

function withAlpha(hex: string, alpha: number): string {
  const n = parseInt(hex.replace('#', ''), 16);
  const r = (n >> 16) & 255;
  const g = (n >> 8) & 255;
  const b = n & 255;
  return `rgba(${r},${g},${b},${Math.max(0, Math.min(1, alpha)).toFixed(3)})`;
}
