/**
 * Progressive raster tile layer — the globe's answer to Google Maps zoom.
 *
 * The globe ships a single 4096x2048 texture for the whole Earth. That is
 * roughly 10 km per pixel at the equator, while the camera is allowed down to
 * ~1.5% of the globe radius above the surface, where the viewport spans under
 * a degree. Magnifying a 10 km/px image that far is why close zoom looked like
 * a smear: there is simply no detail in the texture to reveal.
 *
 * This replaces the base texture, once the camera is close enough to care,
 * with a standard XYZ tile pyramid: as the camera descends, the layer picks a
 * higher zoom level, so ground resolution improves with the camera instead of
 * staying fixed. At the closest altitude it serves ~38 m/px — about 250x the
 * detail the base texture holds.
 *
 * Like `districtLayer`, this touches none of globe.gl's layer accessors — it
 * owns its own meshes in the scene and tracks the camera through OrbitControls.
 */

import * as THREE from 'three';
import type { GlobeInstance } from 'globe.gl';

export type TileStyle = 'satellite' | 'satellite-clean';

interface RasterSource {
  url: (z: number, x: number, y: number) => string;
  /** Raised slightly above the base so an overlay never z-fights it. */
  altitudeBias: number;
  /** Skip this source below the given zoom, where it adds clutter not detail. */
  minZoom?: number;
}

interface StyleSpec {
  sources: RasterSource[];
  /** Required by the provider's terms; surfaced in the UI. */
  attribution: string;
  maxZoom: number;
}

const esri = (service: string) => (z: number, x: number, y: number) =>
  `https://server.arcgisonline.com/ArcGIS/rest/services/${service}/MapServer/tile/${z}/${y}/${x}`;

/** True-colour satellite imagery. The only basemap: this is the Earth. */
const IMAGERY: RasterSource = {
  url: esri('World_Imagery'),
  altitudeBias: 0,
};

/**
 * Place names, as a transparent overlay.
 *
 * Without it, satellite imagery at city zoom is detailed but anonymous — you
 * can see a storm sitting on a town and not know which town. Held back until
 * z6, below which the names collide into noise.
 */
const PLACE_LABELS: RasterSource = {
  url: esri('Reference/World_Boundaries_and_Places'),
  altitudeBias: 0.00002,
  minZoom: 6,
};

/**
 * Basemap styles.
 *
 * Esri is used rather than the more obvious OpenStreetMap or CARTO: OSM's
 * public tile servers actively block this pattern of use and return an
 * "access blocked" image, and CARTO's keyless tiles come back stamped
 * "API KEY REQUIRED". Both answer HTTP 200 while doing so, so neither failure
 * shows up as an error — only as a ruined map.
 *
 * There is deliberately no grey cartographic canvas here. A flat grey
 * basemap under a weather product reads as missing data; true-colour imagery
 * reads as the Earth, which is what the storms are actually sitting on.
 */
const STYLES: Record<TileStyle, StyleSpec> = {
  satellite: {
    sources: [IMAGERY, PLACE_LABELS],
    attribution: 'Imagery © Esri, Maxar, Earthstar Geographics',
    maxZoom: 17,
  },
  'satellite-clean': {
    sources: [IMAGERY],
    attribution: 'Imagery © Esri, Maxar, Earthstar Geographics',
    maxZoom: 17,
  },
};

// -- Tuning -------------------------------------------------------------------

/**
 * Above this camera altitude the base texture is adequate — the whole country
 * or more is in frame and tiles would cost hundreds of requests to show detail
 * nobody can resolve.
 */
export const TILE_VISIBLE_ALTITUDE = 0.38;

const MIN_ZOOM = 3;
/**
 * Ceiling on tile *positions* per view. Each position may carry more than one
 * source (imagery plus the label overlay), so the mesh count is a multiple of
 * this.
 */
const MAX_TILES = 110;
/** Retained off-screen tile meshes, so panning back is instant. */
const CACHE_LIMIT = 500;

/** Coverage padding beyond the screen edge, as a multiple of the visible span. */
const TILE_MARGIN = 1.18;

/** Mesh subdivision per tile. Enough that a tile follows the curve smoothly. */
const TILE_SEGMENTS = 8;

/**
 * Base render altitude.
 *
 * Not a cosmetic value. The globe has radius 100 and the camera runs a 125000
 * unit far plane, so the depth buffer cannot resolve a hair's separation at
 * this range: at 0.0012 the opaque base sphere won every depth test and the
 * imagery never appeared at all. This sits high enough to clear that, and
 * below the district fills so district colour still reads on top.
 */
const TILE_ALTITUDE = 0.0026;

/** Per-zoom-level altitude step, so a finer level never z-fights its parent. */
const LEVEL_STEP = 0.00004;

const FADE_MS = 260;

/**
 * Basemap colour grading.
 *
 * Dark mode: natural deep nocturnal palette matching earth-night.jpg.
 * Day mode: true-colour natural satellite photography.
 */
const THEME_TARGETS = {
  day: {
    saturation: 1.0,
    contrast: 1.05,
    brightness: 0.0,
    tint: [1.0, 1.0, 1.0] as const,
  },
  night: {
    saturation: 0.35,
    contrast: 1.18,
    brightness: -0.15,
    tint: [0.75, 0.88, 1.05] as const,
  },
};

const tileUniforms = {
  uSaturation: { value: THEME_TARGETS.night.saturation },
  uContrast: { value: THEME_TARGETS.night.contrast },
  uBrightness: { value: THEME_TARGETS.night.brightness },
  uTint: { value: new THREE.Vector3(...THEME_TARGETS.night.tint) },
};

let themeAnimFrame: number | null = null;

export function setTileGrade(theme: 'day' | 'night', immediate = false): void {
  const target = THEME_TARGETS[theme];
  if (themeAnimFrame != null) {
    cancelAnimationFrame(themeAnimFrame);
    themeAnimFrame = null;
  }

  if (immediate) {
    tileUniforms.uSaturation.value = target.saturation;
    tileUniforms.uContrast.value = target.contrast;
    tileUniforms.uBrightness.value = target.brightness;
    tileUniforms.uTint.value.set(target.tint[0], target.tint[1], target.tint[2]);
    return;
  }

  const startSat = tileUniforms.uSaturation.value;
  const startCont = tileUniforms.uContrast.value;
  const startBright = tileUniforms.uBrightness.value;
  const startR = tileUniforms.uTint.value.x;
  const startG = tileUniforms.uTint.value.y;
  const startB = tileUniforms.uTint.value.z;

  const startTime = performance.now();
  const DURATION_MS = 450;

  function step() {
    const elapsed = performance.now() - startTime;
    const progress = Math.min(1, elapsed / DURATION_MS);
    const ease = 0.5 - 0.5 * Math.cos(progress * Math.PI);

    tileUniforms.uSaturation.value = startSat + (target.saturation - startSat) * ease;
    tileUniforms.uContrast.value = startCont + (target.contrast - startCont) * ease;
    tileUniforms.uBrightness.value = startBright + (target.brightness - startBright) * ease;
    tileUniforms.uTint.value.set(
      startR + (target.tint[0] - startR) * ease,
      startG + (target.tint[1] - startG) * ease,
      startB + (target.tint[2] - startB) * ease,
    );

    if (progress < 1) {
      themeAnimFrame = requestAnimationFrame(step);
    } else {
      themeAnimFrame = null;
    }
  }
  themeAnimFrame = requestAnimationFrame(step);
}

/**
 * Inject the grade into a MeshBasicMaterial.
 *
 * `customProgramCacheKey` matters: without it three.js compiles a separate
 * shader program per material, and there is one material per tile.
 */
function applyGrade(material: THREE.MeshBasicMaterial): void {
  material.onBeforeCompile = (shader) => {
    shader.uniforms.uSaturation = tileUniforms.uSaturation;
    shader.uniforms.uContrast = tileUniforms.uContrast;
    shader.uniforms.uBrightness = tileUniforms.uBrightness;
    shader.uniforms.uTint = tileUniforms.uTint;

    shader.fragmentShader = shader.fragmentShader
      .replace(
        'void main() {',
        `uniform float uSaturation;
         uniform float uContrast;
         uniform float uBrightness;
         uniform vec3 uTint;
         void main() {`,
      )
      .replace(
        '#include <map_fragment>',
        `#include <map_fragment>
         {
           float luma = dot(diffuseColor.rgb, vec3(0.2126, 0.7152, 0.0722));
           vec3 graded = mix(vec3(luma), diffuseColor.rgb, uSaturation);
           graded = (graded - 0.5) * uContrast + 0.5 + uBrightness;
           diffuseColor.rgb = clamp(graded * uTint, 0.0, 1.0);
         }`,
      );
  };
  material.customProgramCacheKey = () => 'aerocast-tile-grade';
}


// -- Slippy-map maths ---------------------------------------------------------

const MERCATOR_LAT_LIMIT = 85.0511;

const lonOfTile = (x: number, z: number) => (x / 2 ** z) * 360 - 180;

/** Latitude at a fractional tile row — the inverse Mercator projection. */
function latOfTile(y: number, z: number): number {
  const n = Math.PI - (2 * Math.PI * y) / 2 ** z;
  return (180 / Math.PI) * Math.atan(Math.sinh(n));
}

/** Fractional tile row for a latitude. */
function tileOfLat(lat: number, z: number): number {
  const clamped = Math.max(-MERCATOR_LAT_LIMIT, Math.min(MERCATOR_LAT_LIMIT, lat));
  const rad = (clamped * Math.PI) / 180;
  return ((1 - Math.asinh(Math.tan(rad)) / Math.PI) / 2) * 2 ** z;
}

/**
 * Tile zoom level for a camera altitude.
 *
 * Derived from how much of the globe the viewport spans: the visible width is
 * roughly `altitude * 52` degrees, and the layer wants about five tiles across
 * that width, so a tile should subtend `altitude * 10.4` degrees. Solving
 * `360 / 2^z = altitude * 10.4` gives the level below.
 */
function zoomForAltitude(altitude: number, maxZoom: number): number {
  const raw = Math.log2(34.6 / Math.max(altitude, 1e-4));
  return Math.max(MIN_ZOOM, Math.min(maxZoom, Math.round(raw)));
}

// -- Layer --------------------------------------------------------------------

interface Tile {
  key: string;
  z: number;
  /** Index into the active style's `sources`. */
  source: number;
  mesh: THREE.Mesh;
  material: THREE.MeshBasicMaterial;
  texture: THREE.Texture | null;
  loaded: boolean;
  fadeStart: number;
  lastUsed: number;
}

export interface TileLayerHandle {
  setStyle(style: TileStyle): void;
  setVisible(visible: boolean): void;
  setTheme?(theme: 'night' | 'day'): void;
  /** Provider attribution for the current style. */
  attribution(): string;
  /** Current tile zoom level, or null when the layer is dormant. */
  zoom(): number | null;
  dispose(): void;
}

export interface TileLayerOptions {
  style?: TileStyle;
  /** Fires when the served zoom level changes, for status display. */
  onZoomChange?: (zoom: number | null) => void;
}

export function attachTileLayer(
  globe: GlobeInstance,
  options: TileLayerOptions = {},
): TileLayerHandle {
  const scene = globe.scene();
  const group = new THREE.Group();
  // The group's renderOrder is deliberately left at 0.
  //
  // three.js reads `groupOrder` from a Group's renderOrder and compares it
  // BEFORE each object's own renderOrder. Setting it here to order tiles under
  // the district layer did the exact opposite: it lifted every tile above the
  // district meshes, which sit directly on the scene at groupOrder 0, and the
  // choropleth vanished under the basemap. Ordering is expressed per mesh
  // instead -- tiles at ~1.x, district fill at 2, borders at 3.
  scene.add(group);

  const loader = new THREE.TextureLoader();
  loader.setCrossOrigin('anonymous');

  // Tiles are viewed at a grazing angle near the horizon, where anisotropic
  // filtering is the difference between legible imagery and a smear.
  const maxAnisotropy = Math.min(
    8,
    globe.renderer().capabilities.getMaxAnisotropy?.() ?? 1,
  );

  const camera = globe.camera();
  const tileCentre = new THREE.Vector3();
  const towardCamera = new THREE.Vector3();

  /**
   * Is this coordinate on the near face of the globe?
   *
   * With depth testing off, a tile behind the Earth would otherwise paint
   * straight through it. A point faces the camera when its surface normal and
   * the direction to the camera agree.
   */
  function facesCamera(lat: number, lon: number): boolean {
    const c = globe.getCoords(lat, lon, 0);
    tileCentre.set(c.x, c.y, c.z);
    towardCamera.copy(camera.position).sub(tileCentre);
    return tileCentre.dot(towardCamera) > 0;
  }

  const tiles = new Map<string, Tile>();
  const tileKey = (source: number, z: number, x: number, y: number) =>
    `${style}/${source}/${z}/${x}/${y}`;
  let style: TileStyle = options.style ?? 'satellite';
  let visible = true;
  let currentZoom: number | null = null;
  let disposed = false;

  // ---------------------------------------------------------------------------
  // Geometry
  // ---------------------------------------------------------------------------

  /**
   * Build a tile's mesh.
   *
   * Vertices are placed at evenly spaced *Mercator* rows rather than evenly
   * spaced latitudes, and UVs run linearly across the grid. That makes the
   * projection exact rather than approximate: spacing vertices by latitude
   * would bow the imagery, most visibly at the top and bottom of each tile.
   */
  function buildGeometry(
    x: number,
    y: number,
    z: number,
    bias: number,
  ): THREE.BufferGeometry {
    const altitude = TILE_ALTITUDE + z * LEVEL_STEP + bias;
    const lon0 = lonOfTile(x, z);
    const lon1 = lonOfTile(x + 1, z);

    const positions: number[] = [];
    const uvs: number[] = [];
    const indices: number[] = [];

    for (let j = 0; j <= TILE_SEGMENTS; j++) {
      const v = j / TILE_SEGMENTS;
      const lat = latOfTile(y + v, z);
      for (let i = 0; i <= TILE_SEGMENTS; i++) {
        const u = i / TILE_SEGMENTS;
        const lon = lon0 + u * (lon1 - lon0);
        const p = globe.getCoords(lat, lon, altitude);
        positions.push(p.x, p.y, p.z);
        // Image row 0 is the northern edge, while texture V runs upward.
        uvs.push(u, 1 - v);
      }
    }

    const stride = TILE_SEGMENTS + 1;
    for (let j = 0; j < TILE_SEGMENTS; j++) {
      for (let i = 0; i < TILE_SEGMENTS; i++) {
        const a = j * stride + i;
        const b = a + 1;
        const c = a + stride;
        const d = c + 1;
        indices.push(a, c, b, b, c, d);
      }
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    geo.setAttribute('uv', new THREE.Float32BufferAttribute(uvs, 2));
    geo.setIndex(indices);
    return geo;
  }

  // ---------------------------------------------------------------------------
  // Tile lifecycle
  // ---------------------------------------------------------------------------

  function createTile(x: number, y: number, z: number, source: number): Tile {
    const spec = STYLES[style].sources[source];
    const key = tileKey(source, z, x, y);
    const material = new THREE.MeshBasicMaterial({
      transparent: true,
      opacity: 0,
      depthWrite: false,
      // Depth testing is ON, and TILE_ALTITUDE is what makes that safe.
      //
      // Turning it off was tempting -- it guarantees the tiles beat the opaque
      // base sphere -- but a transparent mesh with no depth test paints over
      // every opaque object in the scene, and the storm-cell columns are
      // opaque. They disappeared completely under the basemap. Lifting the
      // tiles far enough to clear the depth buffer's resolution at this range
      // keeps them above the base sphere while still letting anything standing
      // on the surface occlude them correctly.
      depthTest: true,
      side: THREE.FrontSide,
    });
    applyGrade(material);

    const mesh = new THREE.Mesh(
      buildGeometry(x, y, z, spec.altitudeBias),
      material,
    );
    // Higher zoom draws over lower; the label overlay draws over both.
    mesh.renderOrder = 1 + z / 100 + source / 10;
    mesh.visible = false;
    group.add(mesh);

    const tile: Tile = {
      key,
      z,
      source,
      mesh,
      material,
      texture: null,
      loaded: false,
      fadeStart: 0,
      lastUsed: performance.now(),
    };

    loader.load(
      spec.url(z, x, y),
      (texture) => {
        if (disposed || !tiles.has(key)) {
          texture.dispose();
          return;
        }
        texture.colorSpace = THREE.SRGBColorSpace;
        // Tiles butt edge to edge; repeating or mirroring at the seam shows as
        // a bright line between them.
        texture.wrapS = THREE.ClampToEdgeWrapping;
        texture.wrapT = THREE.ClampToEdgeWrapping;
        texture.minFilter = THREE.LinearFilter;
        texture.generateMipmaps = false;
        texture.anisotropy = maxAnisotropy;

        tile.texture = texture;
        tile.material.map = texture;
        tile.material.needsUpdate = true;
        tile.loaded = true;
        tile.fadeStart = performance.now();
        tile.mesh.visible = visible;
        startFading();
        // The camera has usually stopped by the time tiles land, and sync is
        // driven by camera movement -- so without this the outgoing level is
        // never retired and stays magnified over the new one.
        scheduleSync();
      },
      undefined,
      () => {
        // A missing tile is normal at the edge of a provider's coverage. Leave
        // the slot empty so the base texture shows through.
        tile.loaded = true;
        scheduleSync();
      },
    );

    tiles.set(key, tile);
    return tile;
  }

  function destroyTile(tile: Tile) {
    group.remove(tile.mesh);
    tile.mesh.geometry.dispose();
    tile.texture?.dispose();
    tile.material.dispose();
    tiles.delete(tile.key);
  }

  /** Drop the least recently used tiles once the cache is over budget. */
  function trimCache(keep: Set<string>) {
    if (tiles.size <= CACHE_LIMIT) return;
    const evictable = [...tiles.values()]
      .filter((t) => !keep.has(t.key))
      .sort((a, b) => a.lastUsed - b.lastUsed);
    let excess = tiles.size - CACHE_LIMIT;
    for (const tile of evictable) {
      if (excess-- <= 0) break;
      destroyTile(tile);
    }
  }

  // ---------------------------------------------------------------------------
  // Fade ticker — runs only while something is actually fading in
  // ---------------------------------------------------------------------------

  let fadeFrame: number | null = null;

  function startFading() {
    if (fadeFrame == null) fadeFrame = requestAnimationFrame(stepFade);
  }

  function stepFade() {
    fadeFrame = null;
    if (disposed) return;
    const now = performance.now();
    let stillFading = false;

    for (const tile of tiles.values()) {
      if (!tile.texture) continue;
      const target = tile.mesh.visible ? 1 : 0;
      const t = Math.min(1, (now - tile.fadeStart) / FADE_MS);
      tile.material.opacity = target * t;
      if (t < 1) stillFading = true;
    }

    if (stillFading) startFading();
  }

  // ---------------------------------------------------------------------------
  // Viewport sync
  // ---------------------------------------------------------------------------

  /**
   * The lat/lon window currently on screen.
   *
   * Derived by unprojecting the viewport's own corners and edge midpoints
   * rather than from a formula around the camera centre. A formula has to
   * assume the visible region is a lat/lon rectangle centred on the camera,
   * and it is not: the globe is a sphere, so what the screen shows is a
   * curved patch that tilts and widens with latitude. Approximating it left
   * the basemap covering ~84% of the viewport, and the shortfall appeared as
   * a hard-edged box of imagery with dark globe around it.
   *
   * Returns null when the viewport looks past the limb into space, in which
   * case the caller falls back to the horizon cap.
   */
  function visibleBounds(): { halfLon: number; halfLat: number } | null {
    // The renderer's canvas is the coordinate space `toGlobeCoords` expects.
    const canvas = globe.renderer().domElement;
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    if (!w || !h) return null;
    const samples: [number, number][] = [
      [0, 0], [w, 0], [0, h], [w, h],
      [w / 2, 0], [w / 2, h], [0, h / 2], [w, h / 2],
    ];

    const pov = globe.pointOfView();
    let maxDLon = 0;
    let maxDLat = 0;
    let hits = 0;

    for (const [x, y] of samples) {
      const c = globe.toGlobeCoords(x, y);
      if (!c) continue;
      hits++;
      // Normalise across the antimeridian relative to the view centre.
      let dLon = c.lng - pov.lng;
      if (dLon > 180) dLon -= 360;
      if (dLon < -180) dLon += 360;
      maxDLon = Math.max(maxDLon, Math.abs(dLon));
      maxDLat = Math.max(maxDLat, Math.abs(c.lat - pov.lat));
    }

    // Fewer than half the probes on the globe means the limb is in view.
    if (hits < samples.length / 2) return null;
    return { halfLon: maxDLon, halfLat: maxDLat };
  }

  /** Angular radius of the visible cap, for when the limb is in frame. */
  function horizonHalfAngle(altitude: number): number {
    return (Math.acos(1 / (1 + altitude)) * 180) / Math.PI;
  }

  function desiredTiles(): { z: number; coords: [number, number][] } | null {
    const pov = globe.pointOfView();
    if (pov.altitude >= TILE_VISIBLE_ALTITUDE) return null;

    const maxZoom = STYLES[style].maxZoom;
    let z = zoomForAltitude(pov.altitude, maxZoom);

    const bounds = visibleBounds();
    const horizon = horizonHalfAngle(pov.altitude);

    // Pad past the screen edge so a pan reveals loaded tiles rather than a
    // growing empty margin, and never ask for more than the visible cap.
    const halfLon = Math.min(
      horizon * 1.1,
      Math.max(0.4, (bounds?.halfLon ?? horizon) * TILE_MARGIN),
    );
    const halfLat = Math.min(
      horizon * 1.1,
      Math.max(0.3, (bounds?.halfLat ?? horizon) * TILE_MARGIN),
    );

    for (; z >= MIN_ZOOM; z--) {
      const n = 2 ** z;
      const x0 = Math.floor(((pov.lng - halfLon + 180) / 360) * n);
      const x1 = Math.floor(((pov.lng + halfLon + 180) / 360) * n);
      const y0 = Math.floor(tileOfLat(pov.lat + halfLat, z));
      const y1 = Math.floor(tileOfLat(pov.lat - halfLat, z));

      const cols = x1 - x0 + 1;
      const rows = Math.max(0, Math.min(n - 1, y1) - Math.max(0, y0) + 1);
      if (cols * rows <= MAX_TILES) {
        const coords: [number, number][] = [];
        for (let x = x0; x <= x1; x++) {
          for (let y = Math.max(0, y0); y <= Math.min(n - 1, y1); y++) {
            // Wrap longitude so panning across the antimeridian still resolves.
            coords.push([((x % n) + n) % n, y]);
          }
        }
        return { z, coords };
      }
    }
    return null;
  }

  function sync() {
    if (disposed) return;

    const desired = desiredTiles();

    if (!desired || !visible) {
      if (currentZoom !== null) {
        currentZoom = null;
        options.onZoomChange?.(null);
      }
      for (const tile of tiles.values()) tile.mesh.visible = false;
      return;
    }

    const { z, coords: allCoords } = desired;
    const now = performance.now();
    const keep = new Set<string>();
    const sources = STYLES[style].sources;

    // Drop anything on the far hemisphere before it is ever requested.
    const coords = allCoords.filter(([x, y]) => {
      const lon = lonOfTile(x + 0.5, z);
      const lat = latOfTile(y + 0.5, z);
      return facesCamera(lat, lon);
    });
    if (!coords.length) return;

    for (let source = 0; source < sources.length; source++) {
      if (z < (sources[source].minZoom ?? 0)) continue;

      for (const [x, y] of coords) {
        const key = tileKey(source, z, x, y);
        keep.add(key);
        const existing = tiles.get(key);
        if (existing) {
          existing.lastUsed = now;
          if (!existing.mesh.visible && existing.texture) {
            existing.mesh.visible = true;
            existing.fadeStart = now;
            startFading();
          }
        } else {
          createTile(x, y, z, source);
        }
      }
    }

    // Hold the outgoing level on screen until the incoming base imagery has
    // fully arrived. Swapping immediately would flash the blurry base texture
    // on every zoom step, which is exactly the artefact this layer exists to
    // remove. Only source 0 gates the swap: waiting on the label overlay too
    // would stall the handover behind the less important layer.
    const incomingReady = coords.every((c) => tiles.get(tileKey(0, z, c[0], c[1]))?.loaded);

    for (const tile of tiles.values()) {
      if (keep.has(tile.key)) continue;
      // Only base imagery is held over while the next level loads. A label
      // tile from a coarser level would be stretched to several times its
      // intended size -- place names rendered metres tall across the map.
      const holdOver = tile.z !== z && tile.source === 0 && tile.texture !== null;
      tile.mesh.visible = holdOver && !incomingReady;
      if (tile.mesh.visible) tile.lastUsed = now;
    }

    trimCache(keep);

    if (z !== currentZoom) {
      currentZoom = z;
      options.onZoomChange?.(z);
    }
  }

  let frame: number | null = null;

  /**
   * Declared as a hoisted function, not a const: tile load callbacks created
   * in `createTile` call it, and those are defined earlier in the file.
   */
  function scheduleSync() {
    if (frame == null) {
      frame = requestAnimationFrame(() => {
        frame = null;
        sync();
      });
    }
  }

  const controls = globe.controls();
  controls.addEventListener('change', scheduleSync);
  window.addEventListener('resize', scheduleSync);
  sync();

  return {
    setStyle(next) {
      if (next === style) return;
      style = next;
      // Tile keys are namespaced by style, so the old set is simply dropped.
      for (const tile of [...tiles.values()]) destroyTile(tile);
      currentZoom = null;
      sync();
    },

    setVisible(next) {
      visible = next;
      sync();
    },

    setTheme(theme) {
      setTileGrade(theme);
    },

    attribution: () => STYLES[style].attribution,
    zoom: () => currentZoom,

    dispose() {
      disposed = true;
      if (frame != null) cancelAnimationFrame(frame);
      if (fadeFrame != null) cancelAnimationFrame(fadeFrame);
      controls.removeEventListener('change', scheduleSync);
      window.removeEventListener('resize', scheduleSync);
      for (const tile of [...tiles.values()]) destroyTile(tile);
      scene.remove(group);
    },
  };
}
