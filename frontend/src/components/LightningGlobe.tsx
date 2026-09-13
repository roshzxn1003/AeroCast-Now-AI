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
import { Volume2, VolumeX, Sun, Moon, ZoomIn, ZoomOut, Compass, Navigation } from 'lucide-react';

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
 */

const HOME_POV = { lat: 21.0, lng: 80.0, altitude: 1.15 };

const REGIONAL_PRESETS = [
  { id: 'all', label: 'All India', lat: 21.0, lng: 80.0, altitude: 1.65 },
  { id: 'south', label: 'South (Chennai/Blr)', lat: 13.0, lng: 79.5, altitude: 0.38 },
  { id: 'north', label: 'North (Delhi/NCR)', lat: 28.5, lng: 77.5, altitude: 0.38 },
  { id: 'west', label: 'West (Mumbai/Guj)', lat: 19.5, lng: 73.5, altitude: 0.38 },
  { id: 'east', label: 'East (Kolkata/NE)', lat: 23.0, lng: 88.0, altitude: 0.38 },
];

const RIPPLE_STRIKE_COUNT = 80;
const RIPPLE_MAX_AGE_S = 90;

interface LightningGlobeProps {
  onNodeSelect?: (node: ConvectiveNode) => void;
  className?: string;
}

export const LightningGlobe: React.FC<LightningGlobeProps> = ({
  onNodeSelect,
  className,
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const globeRef = useRef<GlobeInstance | null>(null);
  const lightningManagerRef = useRef<ProceduralLightningManager | null>(null);
  const cloudsMeshRef = useRef<THREE.Mesh | null>(null);
  const animFrameRef = useRef<number | null>(null);

  const [ready, setReady] = useState(false);
  const [hovered, setHovered] = useState<ConvectiveNode | null>(null);
  const [selectedCityInfo, setSelectedCityInfo] = useState<CityPreset | null>(null);
  // Held in a ref, not state: this is a comparison baseline for the thunder
  // trigger, and storing it in state made the strike effect re-enter itself.
  const lastStrikeCountRef = useRef(0);

  // Zustand stores
  const convective = useLiveStore((s) => s.convective);
  const lightning = useLiveStore((s) => s.lightning);
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

    globe.pointOfView(HOME_POV, 0);

    // Deep camera controls: minDistance set to 101.5 to unlock deep zoom into India!
    const controls = globe.controls() as {
      autoRotate: boolean;
      autoRotateSpeed: number;
      enableDamping: boolean;
      dampingFactor: number;
      minDistance: number;
      maxDistance: number;
    };
    controls.autoRotate = false;
    controls.autoRotateSpeed = 0.16;
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.minDistance = 101.5; // Surface is radius 100 — allows ultra-close city zoom!
    controls.maxDistance = 650;

    // A globe is a smooth, mostly-curved subject: rendering beyond ~1.5x adds
    // cost without visible benefit, and the transparent layers make every extra
    // fragment expensive.
    const renderer = globe.renderer();
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));

    globeRef.current = globe;

    // -------------------------------------------------------------------------
    // 2. Procedural Lightning Engine Setup
    // -------------------------------------------------------------------------
    const lightningManager = new ProceduralLightningManager(globe.scene());
    lightningManagerRef.current = lightningManager;

    // -------------------------------------------------------------------------
    // 3. Rotating 3D Cloud Sphere
    // -------------------------------------------------------------------------
    new THREE.TextureLoader().load(
      '/textures/clouds.png',
      (cloudsTexture) => {
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
      if (cloudsMeshRef.current) {
        cloudsMeshRef.current.rotation.y += 0.00018; // Slow atmospheric cloud drift
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
      const combinedFeatures = [
        ...countries.features.map((f: any) => ({ ...f, __layer: 'country' })),
        ...(indianStates.features || []).map((f: any) => ({ ...f, __layer: 'state' })),
      ];

      globe
        .polygonsData(combinedFeatures)
        .polygonAltitude((f: any) => (f.__layer === 'state' ? 0.004 : 0.002))
        .polygonCapColor((f: any) => {
          if (f.__layer === 'state') return 'rgba(56, 189, 248, 0.04)';
          const name = f?.properties?.name;
          return name === 'India' ? 'rgba(56, 189, 248, 0.08)' : 'rgba(15, 23, 42, 0.05)';
        })
        .polygonSideColor(() => 'rgba(0,0,0,0)')
        .polygonStrokeColor((f: any) => {
          if (f.__layer === 'state') return 'rgba(56, 189, 248, 0.35)';
          const name = f?.properties?.name;
          return name === 'India' ? 'rgba(56, 189, 248, 0.85)' : 'rgba(148, 163, 184, 0.20)';
        });

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
      observer.disconnect();
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
      lightningManager.dispose();
      globe._destructor?.();
      globeRef.current = null;
    };
  }, [earthTheme]);

  // ---------------------------------------------------------------------------
  // 6. Real-Time Procedural Lightning Discharge & Thunder Audio Sync
  // ---------------------------------------------------------------------------

  useEffect(() => {
    const globe = globeRef.current;
    const lightningManager = lightningManagerRef.current;
    if (!globe || !lightningManager || !ready || strikes.length === 0) return;

    // Trigger visual 3D bolts for newest strikes (< 45s old)
    const freshStrikes = strikes.filter((s) => s.age_s <= 45).slice(0, 15);

    freshStrikes.forEach((strike, idx) => {
      const start = globe.getCoords(strike.lat, strike.lon, 0.045); // Cloud deck height
      const end = globe.getCoords(
        strike.lat + (strike.type === 'IC' ? 0.25 : 0),
        strike.lon + (strike.type === 'IC' ? 0.25 : 0),
        strike.type === 'IC' ? 0.035 : 0.001
      ); // Ground or secondary cloud coordinate

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
        el.className = 'group cursor-pointer pointer-events-auto flex items-center gap-1.5 transform -translate-x-1/2 -translate-y-1/2 transition-transform hover:scale-125';
        el.innerHTML = `
          <div class="relative flex items-center justify-center">
            <span class="animate-ping absolute inline-flex h-3.5 w-3.5 rounded-full bg-cyan-400 opacity-75"></span>
            <span class="relative inline-flex rounded-full h-2.5 w-2.5 bg-cyan-500 border border-white"></span>
          </div>
          <span class="bg-slate-900/90 text-cyan-300 text-[10px] font-bold px-1.5 py-0.5 rounded border border-cyan-500/40 shadow-lg backdrop-blur-sm whitespace-nowrap">
            ${city.name}
          </span>
        `;

        el.addEventListener('click', () => {
          setSelectedCityInfo(city);
          setSelectedStation(city.stationName);
          // Smooth 3D dive directly down to city level!
          globe.pointOfView({ lat: city.lat, lng: city.lng, altitude: 0.18 }, 1400);
        });

        return el;
      });
  }, [ready, setSelectedStation]);

  // ---------------------------------------------------------------------------
  // 10. Camera Zoom & Navigation Helpers
  // ---------------------------------------------------------------------------

  const flyToRegion = useCallback((preset: typeof REGIONAL_PRESETS[0]) => {
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
    globeRef.current?.pointOfView(HOME_POV, 1000);
    setFocusedNode(null);
    setSelectedCityInfo(null);
  }, [setFocusedNode]);

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
    <div className={className} style={{ position: 'relative' }}>
      <div
        ref={containerRef}
        className="absolute inset-0"
        style={{ background: SURFACE.void, cursor: 'grab' }}
        role="img"
        aria-label="Interactive 3D Convective Earth Globe with Procedural Lightning"
      />

      {/* Hovered Sounding Node Tooltip */}
      {hovered && (
        <div
          className="absolute top-4 left-4 z-20 pointer-events-none panel px-3.5 py-2.5 enter backdrop-blur-md"
          style={{ background: 'rgba(11, 15, 20, 0.92)', border: '1px solid rgba(56, 189, 248, 0.3)' }}
        >
          <div className="text-[13px] font-bold text-white flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full" style={{ background: severityColor(hovered.instability) }} />
            {hovered.name}
          </div>
          <div className="text-[11px] text-slate-400">{hovered.region}</div>
          <div className="mt-2 flex items-center gap-3 font-mono text-[11px]">
            <span style={{ color: severityColor(hovered.instability) }}>
              {hovered.instability}
            </span>
            <span className="text-slate-300">CAPE {hovered.cape_j_kg.toFixed(0)} J/kg</span>
            <span className="text-slate-300">LI {hovered.lifted_index_c.toFixed(1)}°C</span>
          </div>
        </div>
      )}

      {/* Selected City Inspector Card */}
      {selectedCityInfo && (
        <div className="absolute top-4 left-4 z-20 panel p-3.5 enter backdrop-blur-md max-w-xs bg-slate-900/95 border border-cyan-500/50 shadow-2xl">
          <div className="flex items-start justify-between">
            <div>
              <div className="text-xs font-bold text-cyan-400 uppercase tracking-wider">
                City Radar Inspection
              </div>
              <div className="text-base font-bold text-white">{selectedCityInfo.name}</div>
              <div className="text-[11px] text-slate-400">{selectedCityInfo.state}</div>
            </div>
            <button
              onClick={() => setSelectedCityInfo(null)}
              className="text-slate-400 hover:text-white text-xs px-1.5 py-0.5 rounded bg-slate-800"
            >
              ✕
            </button>
          </div>
          <div className="mt-2.5 pt-2 border-t border-slate-800 text-[11px] text-slate-300 space-y-1">
            <div className="flex justify-between">
              <span className="text-slate-400">Doppler Radar:</span>
              <span className="font-mono text-cyan-300">{selectedCityInfo.dwrRadarName}</span>
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

      {/* Floating Top-Right Controls: Audio & Day/Night Toggle */}
      <div className="absolute top-4 right-4 z-20 flex items-center gap-2">
        <button
          onClick={toggleSound}
          title={soundEnabled ? 'Mute Thunder Audio' : 'Enable Rolling Thunder Audio'}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all shadow-lg backdrop-blur-md border ${
            soundEnabled
              ? 'bg-cyan-500/20 border-cyan-400/60 text-cyan-300 shadow-cyan-950/50 animate-pulse'
              : 'bg-slate-900/80 border-slate-700/60 text-slate-400 hover:text-white'
          }`}
        >
          {soundEnabled ? <Volume2 className="w-3.5 h-3.5 text-cyan-400" /> : <VolumeX className="w-3.5 h-3.5" />}
          <span>{soundEnabled ? 'THUNDER AUDIO: ON' : 'SOUND: MUTED'}</span>
        </button>

        <button
          onClick={() => setEarthTheme(earthTheme === 'night' ? 'day' : 'night')}
          title="Toggle Earth Day / Night Texture"
          className="p-2 rounded-lg bg-slate-900/80 border border-slate-700/60 text-slate-300 hover:text-white shadow-lg backdrop-blur-md transition-colors"
        >
          {earthTheme === 'night' ? <Moon className="w-3.5 h-3.5 text-cyan-400" /> : <Sun className="w-3.5 h-3.5 text-amber-400" />}
        </button>
      </div>

      {/* Floating Bottom-Center Region Quick-Nav HUD */}
      <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-20 flex items-center gap-1.5 p-1 rounded-xl bg-slate-900/90 border border-slate-700/70 shadow-2xl backdrop-blur-md">
        <div className="flex items-center gap-1 px-1">
          <Navigation className="w-3.5 h-3.5 text-cyan-400" />
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider hidden sm:inline">
            Zoom India:
          </span>
        </div>
        {REGIONAL_PRESETS.map((preset) => (
          <button
            key={preset.id}
            onClick={() => flyToRegion(preset)}
            className="px-2.5 py-1 rounded-lg text-[11px] font-medium text-slate-300 hover:text-white hover:bg-slate-800 transition-colors"
          >
            {preset.label}
          </button>
        ))}
      </div>

      {/* Floating Bottom-Right Camera Navigation Controls */}
      <div className="absolute bottom-4 right-4 z-20 flex flex-col gap-1.5">
        <button
          onClick={() => handleZoom('in')}
          title="Zoom In"
          className="w-8 h-8 rounded-lg bg-slate-900/90 border border-slate-700/70 text-slate-300 hover:text-white grid place-items-center shadow-lg backdrop-blur-md transition-colors"
        >
          <ZoomIn className="w-4 h-4" />
        </button>
        <button
          onClick={() => handleZoom('out')}
          title="Zoom Out"
          className="w-8 h-8 rounded-lg bg-slate-900/90 border border-slate-700/70 text-slate-300 hover:text-white grid place-items-center shadow-lg backdrop-blur-md transition-colors"
        >
          <ZoomOut className="w-4 h-4" />
        </button>
        <button
          onClick={resetView}
          title="Reset to All India View"
          className="w-8 h-8 rounded-lg bg-slate-900/90 border border-slate-700/70 text-slate-300 hover:text-cyan-400 grid place-items-center shadow-lg backdrop-blur-md transition-colors"
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
