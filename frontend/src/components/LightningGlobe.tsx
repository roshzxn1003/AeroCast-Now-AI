import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Globe, { GlobeInstance } from 'globe.gl';
import * as THREE from 'three';
import { useLiveStore } from '../store/liveStore';
import { useNowcastStore } from '../store/nowcastStore';
import { ConvectiveNode, GridPoint, StormCell, Strike } from '../types/nowcast';
import { FLASH, severityColor, SURFACE } from '../design/tokens';
import { ProceduralLightningManager } from '../effects/lightningGenerator';
import { thunderAudio } from '../effects/thunderAudio';
import { MAJOR_INDIAN_CITIES, CityPreset } from '../utils/weatherInterpreter';
import { gridPixelToGeo, getDbzColor, getVilColor } from '../utils/geoProjection';
import { DistrictOverlay } from './DistrictOverlay';
import { GlobeLayerControl } from './GlobeLayerControl';
import { StormCellIntelCard } from './StormCellIntelCard';
import { GlobeTimelineScrubber } from './GlobeTimelineScrubber';
import {
  Volume2,
  VolumeX,
  Sun,
  Moon,
  ZoomIn,
  ZoomOut,
  Compass,
  Navigation,
  RotateCw,
  Maximize2,
  Minimize2,
  Zap,
  Radio,
  X,
} from 'lucide-react';
import { ProvenanceBadge } from './ui';

/**
 * Deep, Photorealistic 3D Earth Globe with Advanced Meteorological Intelligence.
 *
 * Phase 6 Capabilities:
 * - Real-time Doppler Radar & AI Nowcast Grid (ConvLSTM rollout) projected to true (lat, lon)
 * - Layer Control HUD: Doppler Radar, Lightning, Storm Cells, AI Prediction, Motion Vectors, Soundings, Districts
 * - Storm Motion Kinematic Vectors (T0 -> +15m -> +30m -> +60m) with directional particle dash flow
 * - Expanding uncertainty rings for forecast horizons
 * - Interactive Storm Cell Markers & Telemetry Inspection Card with camera dive
 * - Forecast Timeline Scrubber (-45m Observed to +120m AI Nowcast)
 * - 3D procedural fractal lightning simulation & spatial rolling thunder audio
 * - Seamless integration with all 734 India district boundaries & choropleth
 */

const HOME_CENTRE = { lat: 21.0, lng: 80.0 };

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
  const radarMeshRef = useRef<THREE.InstancedMesh | null>(null);
  const animFrameRef = useRef<number | null>(null);
  const flashOverlayRef = useRef<HTMLDivElement | null>(null);
  const strikeTimerRef = useRef<number | null>(null);

  const [ready, setReady] = useState(false);
  const [hovered, setHovered] = useState<ConvectiveNode | null>(null);
  const [selectedCityInfo, setSelectedCityInfo] = useState<CityPreset | null>(null);
  const [isAutoRotating, setIsAutoRotating] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [activePresetId, setActivePresetId] = useState('all');

  const lastStrikeCountRef = useRef(0);
  const targetCloudOpacityRef = useRef(0.38);
  const currentCloudOpacityRef = useRef(0.38);

  // Zustand stores
  const convective = useLiveStore((s) => s.convective);
  const lightning = useLiveStore((s) => s.lightning);
  const summary = useLiveStore((s) => s.summary);
  const setFocusedNode = useLiveStore((s) => s.setFocusedNode);

  const {
    earthTheme,
    setEarthTheme,
    soundEnabled,
    setSoundEnabled,
    setSelectedStation,
    nowcastData,
    timeIndex,
    layers,
    radarOpacity,
    setSelectedStormCell,
    channelMode,
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
  // Meteorological Data Availability & Active Timestep Field Selection
  // ---------------------------------------------------------------------------
  const hasRadarData = Boolean(
    nowcastData?.observation?.dbz_grid?.length ||
    nowcastData?.observation?.history_grids?.length
  );
  const hasLightningData = Boolean(
    (lightning?.strikes?.length ?? 0) > 0 ||
    (nowcastData?.observation?.flash_rate_fpm ?? 0) > 0
  );
  const hasStormCells = Boolean(
    (nowcastData?.observation?.storm_cells?.length ?? 0) > 0 ||
    (nowcastData?.forecast?.some((f) => (f.cells?.length ?? 0) > 0))
  );
  const hasPrediction = Boolean(
    (nowcastData?.forecast?.length ?? 0) > 0 ||
    (nowcastData?.forecast_grids?.length ?? 0) > 0
  );
  const hasSoundings = Boolean((convective?.nodes?.length ?? 0) > 0);

  const currentCells: StormCell[] = useMemo(() => {
    if (!nowcastData) return [];
    if (timeIndex <= 3) {
      return nowcastData.observation?.storm_cells ?? [];
    }
    const fc = nowcastData.forecast?.[timeIndex - 4];
    return fc?.cells ?? [];
  }, [nowcastData, timeIndex]);

  const activeGrid: GridPoint[] = useMemo(() => {
    if (!nowcastData) return [];
    if (timeIndex <= 3) {
      const history = nowcastData.observation?.history_grids ?? [];
      const frame = history[timeIndex];
      if (frame) return channelMode === 'vil' ? frame.vil : frame.dbz;
      return nowcastData.observation?.dbz_grid ?? [];
    }
    const grid = nowcastData.forecast_grids?.[timeIndex - 4];
    if (!grid) return [];
    return channelMode === 'vil' ? grid.vil : grid.dbz;
  }, [nowcastData, timeIndex, channelMode]);

  const stationCoords = useMemo(() => {
    if (nowcastData?.location) {
      return {
        lat: nowcastData.location.lat,
        lon: nowcastData.location.lon,
        range_km: 256,
      };
    }
    return { lat: 13.0827, lon: 80.2707, range_km: 256 };
  }, [nowcastData]);

  // ---------------------------------------------------------------------------
  // 1. Initialize Globe with Deep Camera Zoom & Photorealistic Textures
  // ---------------------------------------------------------------------------

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

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

    const LABEL_ALTITUDE = 1.4;
    let labelsShown: boolean | null = null;
    const syncLabels = (altitude: number) => {
      const show = altitude < LABEL_ALTITUDE;
      if (show === labelsShown) return;
      labelsShown = show;
      el.classList.toggle('show-city-names', show);
    };

    let lastScaleBand = -1;
    const syncScale = (altitude: number) => {
      const scale = Math.min(1, Math.max(0.08, Math.sqrt(altitude / 1.2)));
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
    controls.dampingFactor = 0.22;
    controls.zoomSpeed = 0.35;
    controls.minDistance = 101.5;
    controls.maxDistance = 650;

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

    controls.enableRotate = true;
    controls.enableZoom = true;
    controls.enablePan = false;
    controls.minPolarAngle = 0;
    controls.maxPolarAngle = Math.PI;

    const renderer = globe.renderer();
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));

    globeRef.current = globe;

    if (import.meta.env.DEV) {
      (window as unknown as { __globe?: unknown }).__globe = globe;
    }

    // -------------------------------------------------------------------------
    // 2. Procedural Lightning Engine Setup
    // -------------------------------------------------------------------------
    const lightningManager = new ProceduralLightningManager(globe.scene(), (intensity) => {
      if (flashOverlayRef.current) {
        flashOverlayRef.current.style.opacity = (intensity * 0.45).toFixed(3);
      }
    });
    lightningManagerRef.current = lightningManager;

    // -------------------------------------------------------------------------
    // 3. Rotating 3D Cloud Sphere
    // -------------------------------------------------------------------------
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
    // 4. InstancedMesh for Doppler Radar & AI Prediction Overlay (Phase 6)
    // -------------------------------------------------------------------------
    const discGeo = new THREE.CircleGeometry(0.18, 8);
    const discMat = new THREE.MeshBasicMaterial({
      transparent: true,
      opacity: 0.75,
      depthWrite: false,
      side: THREE.DoubleSide,
    });
    const radarMesh = new THREE.InstancedMesh(discGeo, discMat, 1024);
    radarMesh.count = 0;
    radarMeshRef.current = radarMesh;
    globe.scene().add(radarMesh);

    // -------------------------------------------------------------------------
    // 5. Animation Loop for Lightning Flickers & Cloud Rotation
    // -------------------------------------------------------------------------
    const animate = () => {
      currentCloudOpacityRef.current +=
        (targetCloudOpacityRef.current - currentCloudOpacityRef.current) * 0.06;

      const clouds = cloudsMeshRef.current;
      if (clouds) {
        clouds.rotation.y += 0.00018;

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
    // 6. Load Country & Indian State Boundaries
    // -------------------------------------------------------------------------
    Promise.all([
      fetch('/geo/countries.geojson').then((r) => r.json()).catch(() => ({ features: [] })),
      fetch('/geo/indian_states.geojson').then((r) => r.json()).catch(() => ({ features: [] })),
    ]).then(([countries, indianStates]) => {
      const indiaOutline = (countries.features || []).filter(
        (f: any) => f?.properties?.name === 'India',
      );
      const combinedFeatures = indiaOutline.map((f: any) => ({ ...f, __layer: 'country' }));

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
      if (radarMeshRef.current) {
        radarMeshRef.current.geometry.dispose();
        (radarMeshRef.current.material as THREE.Material).dispose();
        globe.scene().remove(radarMeshRef.current);
        radarMeshRef.current = null;
      }
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
  // Dynamic Earth Basemap & Atmosphere Sync
  // ---------------------------------------------------------------------------
  useEffect(() => {
    const globe = globeRef.current;
    if (!globe || !ready) return;
    targetCloudOpacityRef.current = earthTheme === 'night' ? 0.38 : 0.70;
    if (layers.earth) {
      const globeImage =
        earthTheme === 'night' ? '/textures/earth-night.jpg' : '/textures/earth-blue-marble.jpg';
      globe.globeImageUrl(globeImage);
      globe.atmosphereColor(earthTheme === 'night' ? '#38bdf8' : '#60a5fa');
      globe.atmosphereAltitude(earthTheme === 'night' ? 0.14 : 0.18);
      globe.showAtmosphere(true);
    } else {
      globe.showAtmosphere(false);
    }
  }, [earthTheme, ready, layers.earth]);

  // ---------------------------------------------------------------------------
  // State & District Boundaries Visibility
  // ---------------------------------------------------------------------------
  useEffect(() => {
    if (stateBordersRef.current) {
      stateBordersRef.current.visible = layers.districts;
    }
  }, [layers.districts]);

  // ---------------------------------------------------------------------------
  // 7. Render Doppler Radar & AI Prediction Grid on 3D Globe
  // ---------------------------------------------------------------------------
  useEffect(() => {
    const globe = globeRef.current;
    const mesh = radarMeshRef.current;
    if (!globe || !mesh || !ready) return;

    const isObserved = timeIndex <= 3;
    const isForecast = timeIndex > 3;
    const isVisible = (isObserved && layers.radar) || (isForecast && layers.aiPrediction);

    if (!isVisible || activeGrid.length === 0) {
      mesh.count = 0;
      mesh.instanceMatrix.needsUpdate = true;
      return;
    }

    const minThreshold = channelMode === 'vil' ? 1.0 : 12.0;
    const filtered = activeGrid.filter((pt) => pt.v >= minThreshold);
    const count = Math.min(1024, filtered.length);
    mesh.count = count;

    (mesh.material as THREE.MeshBasicMaterial).opacity =
      radarOpacity * (isForecast ? 0.88 : 1.0);
    (mesh.material as THREE.MeshBasicMaterial).needsUpdate = true;

    const dummy = new THREE.Object3D();
    const up = new THREE.Vector3(0, 0, 1);

    for (let i = 0; i < count; i++) {
      const pt = filtered[i];
      const { lat, lon } = gridPixelToGeo(
        pt.y,
        pt.x,
        stationCoords.lat,
        stationCoords.lon,
        stationCoords.range_km,
        32
      );
      const c = globe.getCoords(lat, lon, 0.005);
      if (c) {
        const pos = new THREE.Vector3(c.x, c.y, c.z);
        const normal = pos.clone().normalize();
        dummy.position.copy(pos);
        dummy.quaternion.setFromUnitVectors(up, normal);
        dummy.updateMatrix();
        mesh.setMatrixAt(i, dummy.matrix);

        const colorHex = channelMode === 'vil' ? getVilColor(pt.v) : getDbzColor(pt.v);
        mesh.setColorAt(i, new THREE.Color(colorHex));
      }
    }

    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
  }, [activeGrid, ready, timeIndex, layers.radar, layers.aiPrediction, radarOpacity, channelMode, stationCoords]);

  // ---------------------------------------------------------------------------
  // 8. Storm Motion Vectors & Trajectory Paths
  // ---------------------------------------------------------------------------
  useEffect(() => {
    const globe = globeRef.current;
    if (!globe || !ready) return;

    if (!layers.stormTracks || currentCells.length === 0) {
      globe.pathsData([]);
      return;
    }

    const paths = currentCells.map((cell) => {
      const p0 = gridPixelToGeo(
        cell.centroid_pixel[0],
        cell.centroid_pixel[1],
        stationCoords.lat,
        stationCoords.lon,
        stationCoords.range_km,
        32
      );
      const p15 = gridPixelToGeo(
        cell.projected_15min[0],
        cell.projected_15min[1],
        stationCoords.lat,
        stationCoords.lon,
        stationCoords.range_km,
        32
      );
      const p30 = gridPixelToGeo(
        cell.projected_30min[0],
        cell.projected_30min[1],
        stationCoords.lat,
        stationCoords.lon,
        stationCoords.range_km,
        32
      );
      const p60 = gridPixelToGeo(
        cell.projected_60min[0],
        cell.projected_60min[1],
        stationCoords.lat,
        stationCoords.lon,
        stationCoords.range_km,
        32
      );

      return {
        cell_id: cell.cell_id,
        coords: [
          [p0.lat, p0.lon, 0.009],
          [p15.lat, p15.lon, 0.009],
          [p30.lat, p30.lon, 0.009],
          [p60.lat, p60.lon, 0.009],
        ],
        color: cell.color || '#38bdf8',
      };
    });

    globe
      .pathsData(paths)
      .pathPoints((d: any) => d.coords)
      .pathColor((d: any) => d.color)
      .pathStroke(2.6)
      .pathDashLength(0.35)
      .pathDashGap(0.12)
      .pathDashAnimateTime(1600);
  }, [layers.stormTracks, currentCells, stationCoords, ready]);

  // ---------------------------------------------------------------------------
  // 9. Surface Shockwaves & Forecast Uncertainty Rings
  // ---------------------------------------------------------------------------
  const combinedRings = useMemo(() => {
    const list: any[] = [];

    // Lightning strike ripples
    if (layers.lightning) {
      rippleStrikes.forEach((s) => {
        const base = s.type === 'CG' ? FLASH.cg : FLASH.ic;
        list.push({
          lat: s.lat,
          lon: s.lon,
          maxRadius: s.type === 'CG' ? 3.4 : 2.0,
          propagationSpeed: 2.2,
          repeatPeriod: s.type === 'CG' ? 800 : 1300,
          colorFn: (t: number) => withAlpha(base, 1 - t),
        });
      });
    }

    // Storm motion forecast uncertainty cones (+30m, +60m)
    if (layers.stormTracks && currentCells.length > 0) {
      currentCells.forEach((cell) => {
        const p30 = gridPixelToGeo(
          cell.projected_30min[0],
          cell.projected_30min[1],
          stationCoords.lat,
          stationCoords.lon,
          stationCoords.range_km,
          32
        );
        const p60 = gridPixelToGeo(
          cell.projected_60min[0],
          cell.projected_60min[1],
          stationCoords.lat,
          stationCoords.lon,
          stationCoords.range_km,
          32
        );

        list.push({
          lat: p30.lat,
          lon: p30.lon,
          maxRadius: 2.8,
          propagationSpeed: 0.8,
          repeatPeriod: 1400,
          colorFn: (t: number) => withAlpha(cell.color || '#38bdf8', (1 - t) * 0.7),
        });

        list.push({
          lat: p60.lat,
          lon: p60.lon,
          maxRadius: 4.8,
          propagationSpeed: 0.8,
          repeatPeriod: 1800,
          colorFn: (t: number) => withAlpha(cell.color || '#818cf8', (1 - t) * 0.5),
        });
      });
    }

    return list;
  }, [layers.lightning, layers.stormTracks, rippleStrikes, currentCells, stationCoords]);

  useEffect(() => {
    const globe = globeRef.current;
    if (!globe || !ready) return;

    globe
      .ringsData(combinedRings)
      .ringLat((d: any) => d.lat)
      .ringLng((d: any) => d.lon)
      .ringColor((d: any) => d.colorFn)
      .ringMaxRadius((d: any) => d.maxRadius)
      .ringPropagationSpeed((d: any) => d.propagationSpeed)
      .ringRepeatPeriod((d: any) => d.repeatPeriod)
      .ringAltitude(0.008);
  }, [combinedRings, ready]);

  // ---------------------------------------------------------------------------
  // 10. Procedural Lightning Discharges & Thunder Visual Loop
  // ---------------------------------------------------------------------------
  useEffect(() => {
    const globe = globeRef.current;
    const lightningManager = lightningManagerRef.current;

    // Clean up any existing scheduled loop timer
    if (strikeTimerRef.current !== null) {
      window.clearTimeout(strikeTimerRef.current);
      strikeTimerRef.current = null;
    }

    if (
      !globe ||
      !lightningManager ||
      !ready ||
      !layers.lightning ||
      layers.lightningMode === 'density'
    ) {
      lightningManager?.clear();
      return;
    }

    interface DischargeTarget {
      lat: number;
      lon: number;
      type: 'CG' | 'IC';
      intensity: number;
    }

    const targets: DischargeTarget[] = [];

    // 1. Add real recent lightning strikes
    if (strikes.length > 0) {
      const recent = strikes.filter((s) => s.age_s <= 300);
      const pool = recent.length > 0 ? recent : strikes.slice(0, 30);
      pool.forEach((s) => {
        targets.push({
          lat: s.lat,
          lon: s.lon,
          type: s.type,
          intensity: Math.min(1.0, 0.65 + Math.random() * 0.35),
        });
      });
    }

    // 2. Add active severe convective storm cells if available
    if (currentCells && currentCells.length > 0) {
      currentCells
        .filter((c) => c.max_dbz >= 36)
        .forEach((cell) => {
          const pt = gridPixelToGeo(
            cell.centroid_pixel[0],
            cell.centroid_pixel[1],
            stationCoords.lat,
            stationCoords.lon,
            stationCoords.range_km,
            32
          );
          targets.push({
            lat: pt.lat,
            lon: pt.lon,
            type: Math.random() > 0.4 ? 'CG' : 'IC',
            intensity: Math.min(1.0, 0.6 + (cell.max_dbz - 36) / 25),
          });
        });
    }

    // If no lightning or convective targets active, keep scene quiet
    if (targets.length === 0) {
      lightningManager.clear();
      return;
    }

    let isDisposed = false;
    let strikeIndex = 0;

    const fireDischarge = (target: DischargeTarget) => {
      if (isDisposed || !globe || !lightningManagerRef.current) return;

      // Add slight spatial jitter (+-0.12 deg) across thundercloud footprint
      const jitterLat = target.lat + (Math.random() - 0.5) * 0.24;
      const jitterLon = target.lon + (Math.random() - 0.5) * 0.24;
      const isIC = target.type === 'IC' || Math.random() < 0.35;

      const start = globe.getCoords(jitterLat, jitterLon, 0.048);
      const end = globe.getCoords(
        jitterLat + (isIC ? (Math.random() - 0.5) * 0.28 : 0),
        jitterLon + (isIC ? (Math.random() - 0.5) * 0.28 : 0),
        isIC ? 0.038 : 0.005
      );

      if (start && end) {
        const startVec = new THREE.Vector3(start.x, start.y, start.z);
        const endVec = new THREE.Vector3(end.x, end.y, end.z);
        strikeIndex = (strikeIndex + 1) % 1000;

        lightningManagerRef.current.triggerStrike(
          `strike-loop-${strikeIndex}-${Date.now()}`,
          startVec,
          endVec,
          isIC ? 'IC' : 'CG',
          target.intensity
        );

        // Acoustic thunder sync with physical speed-of-sound propagation delay
        if (soundEnabled) {
          const pan = Math.max(-0.85, Math.min(0.85, (jitterLon - 80.0) / 12.0));
          const acousticDelayMs = isIC ? 160 + Math.random() * 180 : 70 + Math.random() * 100;
          window.setTimeout(() => {
            if (!isDisposed) {
              thunderAudio.play(target.intensity * 0.85, !isIC, pan);
            }
          }, acousticDelayMs);
        }
      }
    };

    const scheduleNextStrike = () => {
      if (isDisposed) return;

      // Pick a target from active pool
      const target = targets[Math.floor(Math.random() * targets.length)];
      fireDischarge(target);

      // 18% chance of rapid double-stroke in the same convective cell
      if (Math.random() < 0.18) {
        window.setTimeout(() => {
          if (!isDisposed) {
            fireDischarge(target);
          }
        }, 130 + Math.random() * 90);
      }

      // Dynamic thunder cadence: faster for high storm count, slower for isolated strikes
      const baseDelay = targets.length > 15 ? 750 : targets.length > 5 ? 1200 : 1800;
      const nextInterval = baseDelay + Math.random() * 950;

      strikeTimerRef.current = window.setTimeout(scheduleNextStrike, nextInterval);
    };

    // Kick off visual loop immediately
    scheduleNextStrike();

    return () => {
      isDisposed = true;
      if (strikeTimerRef.current !== null) {
        window.clearTimeout(strikeTimerRef.current);
        strikeTimerRef.current = null;
      }
      lightningManager.clear();
    };
  }, [
    strikes,
    currentCells,
    stationCoords,
    ready,
    soundEnabled,
    layers.lightning,
    layers.lightningMode,
  ]);

  // ---------------------------------------------------------------------------
  // 11. Convective Sounding Nodes (Vigour Columns)
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
      .pointsData(layers.soundingNodes ? (nodes as unknown as object[]) : [])
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
  }, [nodes, ready, handleNodeClick, layers.soundingNodes]);

  // ---------------------------------------------------------------------------
  // 12. Interactive Indian Cities & Active Storm Cell HTML Badges
  // ---------------------------------------------------------------------------
  const htmlItems = useMemo(() => {
    const items: any[] = MAJOR_INDIAN_CITIES.map((c) => ({ ...c, itemType: 'city' }));

    if (layers.stormCells && currentCells.length > 0) {
      currentCells.forEach((cell) => {
        const geo = gridPixelToGeo(
          cell.centroid_pixel[0],
          cell.centroid_pixel[1],
          stationCoords.lat,
          stationCoords.lon,
          stationCoords.range_km,
          32
        );
        items.push({
          itemType: 'stormCell',
          cell,
          lat: geo.lat,
          lng: geo.lon,
        });
      });
    }

    return items;
  }, [layers.stormCells, currentCells, stationCoords]);

  useEffect(() => {
    const globe = globeRef.current;
    if (!globe || !ready) return;

    globe
      .htmlElementsData(htmlItems)
      .htmlLat((d: any) => d.lat)
      .htmlLng((d: any) => d.lng)
      .htmlAltitude((d: any) => (d.itemType === 'stormCell' ? 0.022 : 0.015))
      .htmlElement((d: any) => {
        if (d.itemType === 'stormCell') {
          const cell = d.cell as StormCell;
          const el = document.createElement('div');
          el.className =
            'group cursor-pointer pointer-events-auto relative transform -translate-x-1/2 -translate-y-1/2 transition-transform hover:scale-125 select-none';
          const cellColor = cell.color || '#ef4444';
          el.innerHTML = `
            <div class="relative flex items-center justify-center">
              <span class="animate-ping absolute inline-flex h-6 w-6 rounded-full opacity-60" style="background-color: ${cellColor}"></span>
              <span class="relative inline-flex rounded-full h-3.5 w-3.5 ring-2 ring-white shadow-lg" style="background-color: ${cellColor}"></span>
              <div class="absolute left-full ml-1.5 top-1/2 -translate-y-1/2 flex items-center gap-1 px-1.5 py-0.5 rounded-md bg-slate-900/90 border border-white/20 shadow-md whitespace-nowrap">
                <span class="font-mono text-[10px] font-bold text-white">${cell.cell_id}</span>
                <span class="font-mono text-[9px] text-amber-300 font-semibold">${cell.max_dbz.toFixed(0)} dBZ</span>
              </div>
            </div>
          `;
          el.addEventListener('click', (ev) => {
            ev.stopPropagation();
            setSelectedStormCell(cell);
            globe.pointOfView({ lat: d.lat, lng: d.lng, altitude: 0.25 }, 1100);
          });
          return el;
        }

        // City beacon
        const city = d as CityPreset;
        const el = document.createElement('div');
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
          globe.pointOfView({ lat: city.lat, lng: city.lng, altitude: 0.18 }, 1400);
        });

        return el;
      });
  }, [htmlItems, ready, setSelectedStation, setFocusedNode, nodes, setSelectedStormCell]);

  // ---------------------------------------------------------------------------
  // 13. Camera Zoom & Navigation Helpers
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
        aria-label="Interactive 3D Convective Earth Globe with Real Radar and AI Nowcasting"
      />

      {/* Visual Thunder Atmospheric Flash Vignette */}
      <div
        ref={flashOverlayRef}
        className="absolute inset-0 pointer-events-none z-10 transition-opacity duration-75"
        style={{
          opacity: 0,
          background:
            'radial-gradient(ellipse at center, rgba(224,242,254,0.22) 0%, rgba(56,189,248,0.12) 45%, rgba(14,165,233,0.02) 100%)',
          mixBlendMode: 'screen',
        }}
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
              {/* Step 44: Explicit 5-State Operational Mode & Provenance Badge */}
              {(() => {
                const prov = nowcastData?.provenance?.toUpperCase() || '';
                const mode = (nowcastData?.mode || '').toLowerCase();
                const freshness = nowcastData?.freshness?.overall_status?.toLowerCase();
                const isStale = freshness === 'stale' || freshness === 'delayed';

                if (prov.includes('SIMULAT') || mode === 'simulated') {
                  return (
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold tracking-wider bg-purple-500/20 text-purple-300 border border-purple-500/40">
                      <span className="w-1.5 h-1.5 rounded-full bg-purple-400" />
                      SIMULATION
                    </span>
                  );
                } else if (prov.includes('HISTORICAL') || prov.includes('REPLAY')) {
                  return (
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold tracking-wider bg-blue-500/20 text-blue-300 border border-blue-500/40">
                      <span className="w-1.5 h-1.5 rounded-full bg-blue-400" />
                      HISTORICAL
                    </span>
                  );
                } else if (isStale) {
                  return (
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold tracking-wider bg-rose-500/20 text-rose-300 border border-rose-500/40 animate-pulse">
                      <span className="w-1.5 h-1.5 rounded-full bg-rose-400" />
                      STALE OBS
                    </span>
                  );
                } else if (prov.includes('HYBRID') || prov.includes('FALLBACK') || mode === 'degraded') {
                  return (
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold tracking-wider bg-amber-500/20 text-amber-300 border border-amber-500/40">
                      <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                      DEGRADED
                    </span>
                  );
                } else {
                  return (
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold tracking-wider bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-sm shadow-emerald-500/20">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                      LIVE
                    </span>
                  );
                }
              })()}

              {/* Step 43: Relative Freshness Badge */}
              {nowcastData?.timestamp && (
                <span
                  title={`Generated at: ${nowcastData.timestamp}`}
                  className="text-[9px] font-mono px-2 py-0.5 rounded-full hidden md:inline-flex items-center gap-1 text-slate-300 bg-slate-900/70 border border-slate-700/50"
                >
                  ⏱ Live Sync
                </span>
              )}
            </div>

            {/* Center: DistrictSearch Integrated in Flexbox */}
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

      {/* -------------------------------------- Globe Layer Control HUD (Phase 6) */}
      <GlobeLayerControl
        hasRadarData={hasRadarData}
        hasLightningData={hasLightningData}
        hasStormCells={hasStormCells}
        hasPrediction={hasPrediction}
        hasSoundings={hasSoundings}
      />

      {/* -------------------------------------- Storm Cell Intel Card (Phase 6) */}
      <StormCellIntelCard
        onFocusCell={(lat, lon) => {
          globeRef.current?.pointOfView({ lat, lng: lon, altitude: 0.22 }, 1200);
        }}
      />

      {/* -------------------------------------- Globe Forecast Timeline Scrubber (Phase 6) */}
      <GlobeTimelineScrubber />

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
