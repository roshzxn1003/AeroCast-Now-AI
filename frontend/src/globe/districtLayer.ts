/**
 * District boundary, choropleth and picking layer for the 3D globe.
 *
 * This attaches to an existing globe.gl instance without using any of its
 * layer accessors. That is deliberate and load-bearing:
 *
 *   - globe.gl's `polygonsData` builds a cap mesh, a side mesh and a stroke
 *     line per ring. For 734 districts that is several thousand draw calls per
 *     frame — the same problem the state borders were already flattened to
 *     solve. Everything here is merged into exactly three meshes: one fill,
 *     one border set, one highlight.
 *   - `polygonsData`, `pointsData`, `ringsData` and `htmlElementsData` are all
 *     already claimed by LightningGlobe, and those accessors are setters, not
 *     subscriptions. Touching one would silently delete an existing layer.
 *
 * For the same reason zoom is tracked through the OrbitControls `change`
 * event rather than `globe.onZoom`, which would replace the label-visibility
 * handler the globe installs at startup.
 */

import * as THREE from 'three';
import type { GlobeInstance } from 'globe.gl';
import {
  District,
  DistrictGeometry,
  DistrictLocator,
  loadDistrictGeometry,
} from '../services/districts';
import { SEVERITY_COLOR, SeverityLevel } from '../design/tokens';

// -- Render altitudes ---------------------------------------------------------
// Ordered so nothing z-fights, and all above the tile basemap, whose top
// level reaches ~0.0030. The country polygon sits at 0.002 and the state
// border mesh at 0.004, both owned by LightningGlobe.
const FILL_ALTITUDE = 0.0044;
const BORDER_ALTITUDE = 0.0052;
const HIGHLIGHT_ALTITUDE = 0.0095;

/**
 * Camera altitude below which district boundaries appear.
 *
 * Above this the whole country is in frame and 734 subdivisions read as noise
 * over the state outlines; below it the user has committed to a region and the
 * districts become the useful unit.
 */
export const BORDER_VISIBLE_ALTITUDE = 1.05;

/**
 * Camera altitude below which district name labels appear.
 *
 * Sits above the altitude `flyTo` settles at for a large district, so that
 * selecting one from search always lands with its neighbours named.
 */
const LABEL_VISIBLE_ALTITUDE = 0.7;

/** Most labels drawn at once, nearest the camera centre first. */
const MAX_LABELS = 45;

/** Pointer travel, in px, above which a pointerup is a drag and not a click. */
const CLICK_SLOP_PX = 5;

export interface DistrictLayerOptions {
  onHover?: (district: District | null) => void;
  onSelect?: (district: District | null) => void;
  /** Fires when the visible district set changes, for weather prefetching. */
  onViewportChange?: (visible: District[], altitude: number) => void;
}

export interface DistrictLayerHandle {
  /** Recolour the choropleth. Districts absent from the map render neutral. */
  setSeverity(bySeverity: Map<string, SeverityLevel>): void;
  setSelected(id: string | null): void;
  setHovered(id: string | null): void;
  /** Toggle the whole layer without tearing it down. */
  setVisible(visible: boolean): void;
  /** Look up a district by id, once geometry has loaded. */
  get(id: string): DistrictGeometry | undefined;
  /** Fly the camera to frame a district. */
  flyTo(id: string, ms?: number): void;
  dispose(): void;
}

// -----------------------------------------------------------------------------
// Triangulation
// -----------------------------------------------------------------------------

/**
 * Ear-clipping triangulation of a simple polygon.
 *
 * District rings arrive already simplified to ~95 vertices each, are simple
 * (non-self-intersecting) and have no holes, which is exactly the case
 * ear clipping handles well — so this avoids pulling in a triangulation
 * dependency for 60 lines of work. Returns flat index triples into `ring`.
 */
function earClip(ring: number[][]): number[] {
  const n = ring.length;
  if (n < 3) return [];

  const indices = Array.from({ length: n }, (_, i) => i);
  // Ear clipping requires a known winding; normalise to counter-clockwise.
  if (signedArea(ring) < 0) indices.reverse();

  const out: number[] = [];
  let guard = indices.length * 3;

  while (indices.length > 3 && guard-- > 0) {
    let clipped = false;

    for (let i = 0; i < indices.length; i++) {
      const prev = indices[(i - 1 + indices.length) % indices.length];
      const curr = indices[i];
      const next = indices[(i + 1) % indices.length];

      const a = ring[prev];
      const b = ring[curr];
      const c = ring[next];

      // Reflex vertices cannot be ears.
      if (cross(a, b, c) <= 0) continue;

      // An ear may not contain any other vertex of the polygon.
      let contains = false;
      for (const j of indices) {
        if (j === prev || j === curr || j === next) continue;
        if (pointInTriangle(ring[j], a, b, c)) {
          contains = true;
          break;
        }
      }
      if (contains) continue;

      out.push(prev, curr, next);
      indices.splice(i, 1);
      clipped = true;
      break;
    }

    // Degenerate ring (collinear run, duplicated vertices): stop rather than
    // spin. The partial fan already emitted is still a valid surface.
    if (!clipped) break;
  }

  if (indices.length === 3) out.push(indices[0], indices[1], indices[2]);
  return out;
}

const signedArea = (ring: number[][]): number => {
  let a = 0;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    a += (ring[j][0] - ring[i][0]) * (ring[j][1] + ring[i][1]);
  }
  return a / 2;
};

const cross = (a: number[], b: number[], c: number[]): number =>
  (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);

function pointInTriangle(p: number[], a: number[], b: number[], c: number[]): boolean {
  const d1 = cross(a, b, p);
  const d2 = cross(b, c, p);
  const d3 = cross(c, a, p);
  const neg = d1 < 0 || d2 < 0 || d3 < 0;
  const pos = d1 > 0 || d2 > 0 || d3 > 0;
  return !(neg && pos);
}

// -----------------------------------------------------------------------------
// Attachment
// -----------------------------------------------------------------------------

interface VertexRange {
  start: number;
  count: number;
}

/**
 * Districts with no live reading are drawn fully transparent rather than in a
 * neutral tint. A grey wash over an unscored district is indistinguishable
 * from a reading of "calm", which is the one thing a weather map must never
 * imply about data it does not have. Absence of colour means absence of data;
 * the boundary line still shows the district is there.
 */
const UNSCORED_ALPHA = 0;

export async function attachDistrictLayer(
  globe: GlobeInstance,
  container: HTMLElement,
  options: DistrictLayerOptions = {},
): Promise<DistrictLayerHandle> {
  const districts = await loadDistrictGeometry();
  const locator = new DistrictLocator(districts);
  const byId = new Map(districts.map((d) => [d.id, d]));
  const scene = globe.scene();

  // ---------------------------------------------------------------------------
  // Build the merged fill mesh
  // ---------------------------------------------------------------------------

  const fillPositions: number[] = [];
  const fillColors: number[] = [];
  const fillRanges = new Map<string, VertexRange>();

  for (const district of districts) {
    const start = fillPositions.length / 3;

    for (const ring of district.rings) {
      // The closing vertex duplicates the first and would produce degenerate
      // ears.
      const open = ring.slice(0, -1);
      if (open.length < 3) continue;

      for (const idx of earClip(open)) {
        const [lon, lat] = open[idx];
        const v = globe.getCoords(lat, lon, FILL_ALTITUDE);
        fillPositions.push(v.x, v.y, v.z);
        // RGBA: alpha carries "has a reading", independent of the material
        // opacity that fades the whole layer with camera altitude.
        fillColors.push(0, 0, 0, UNSCORED_ALPHA);
      }
    }

    const count = fillPositions.length / 3 - start;
    if (count > 0) fillRanges.set(district.id, { start, count });
  }

  const fillGeometry = new THREE.BufferGeometry();
  fillGeometry.setAttribute(
    'position',
    new THREE.Float32BufferAttribute(fillPositions, 3),
  );
  const colorAttr = new THREE.Float32BufferAttribute(fillColors, 4);
  colorAttr.setUsage(THREE.DynamicDrawUsage);
  fillGeometry.setAttribute('color', colorAttr);

  const fillMaterial = new THREE.MeshBasicMaterial({
    vertexColors: true,
    transparent: true,
    opacity: 0.34,
    depthWrite: false,
    side: THREE.FrontSide,
    blending: THREE.NormalBlending,
  });
  const fillMesh = new THREE.Mesh(fillGeometry, fillMaterial);
  fillMesh.renderOrder = 2;
  fillMesh.visible = false;
  scene.add(fillMesh);

  // ---------------------------------------------------------------------------
  // Build the merged border mesh
  // ---------------------------------------------------------------------------

  const borderPositions: number[] = [];
  for (const district of districts) {
    for (const ring of district.rings) {
      for (let i = 0; i < ring.length - 1; i++) {
        const a = globe.getCoords(ring[i][1], ring[i][0], BORDER_ALTITUDE);
        const b = globe.getCoords(ring[i + 1][1], ring[i + 1][0], BORDER_ALTITUDE);
        borderPositions.push(a.x, a.y, a.z, b.x, b.y, b.z);
      }
    }
  }

  const borderGeometry = new THREE.BufferGeometry();
  borderGeometry.setAttribute(
    'position',
    new THREE.Float32BufferAttribute(borderPositions, 3),
  );
  const borderMaterial = new THREE.LineBasicMaterial({
    // Boundaries are reference, not content. Over satellite imagery a bright
    // hairline on all 734 districts turns the map into a net; this stays light
    // enough to read as a graticule and lets the ground show through.
    color: new THREE.Color('#dbeafe'),
    transparent: true,
    opacity: 0.18,
    depthWrite: false,
  });
  const borderMesh = new THREE.LineSegments(borderGeometry, borderMaterial);
  borderMesh.renderOrder = 3;
  borderMesh.visible = false;
  scene.add(borderMesh);

  // ---------------------------------------------------------------------------
  // Highlight outline, rebuilt on hover and selection
  // ---------------------------------------------------------------------------

  const highlightGeometry = new THREE.BufferGeometry();
  highlightGeometry.setAttribute(
    'position',
    new THREE.Float32BufferAttribute(new Float32Array(0), 3),
  );
  const highlightMaterial = new THREE.LineBasicMaterial({
    color: new THREE.Color('#4cc2ff'),
    transparent: true,
    opacity: 0.95,
    depthWrite: false,
  });
  const highlightMesh = new THREE.LineSegments(highlightGeometry, highlightMaterial);
  highlightMesh.renderOrder = 5;
  scene.add(highlightMesh);

  const hoverGeometry = new THREE.BufferGeometry();
  hoverGeometry.setAttribute(
    'position',
    new THREE.Float32BufferAttribute(new Float32Array(0), 3),
  );
  const hoverMaterial = new THREE.LineBasicMaterial({
    color: new THREE.Color('#e9eef4'),
    transparent: true,
    opacity: 0.6,
    depthWrite: false,
  });
  const hoverMesh = new THREE.LineSegments(hoverGeometry, hoverMaterial);
  hoverMesh.renderOrder = 4;
  scene.add(hoverMesh);

  function outlineFor(id: string | null): Float32Array {
    const district = id ? byId.get(id) : undefined;
    if (!district) return new Float32Array(0);
    const pts: number[] = [];
    for (const ring of district.rings) {
      for (let i = 0; i < ring.length - 1; i++) {
        const a = globe.getCoords(ring[i][1], ring[i][0], HIGHLIGHT_ALTITUDE);
        const b = globe.getCoords(ring[i + 1][1], ring[i + 1][0], HIGHLIGHT_ALTITUDE);
        pts.push(a.x, a.y, a.z, b.x, b.y, b.z);
      }
    }
    return new Float32Array(pts);
  }

  function applyOutline(mesh: THREE.LineSegments, id: string | null) {
    const positions = outlineFor(id);
    mesh.geometry.dispose();
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    mesh.geometry = geo;
    mesh.visible = positions.length > 0;
  }

  // ---------------------------------------------------------------------------
  // Labels
  // ---------------------------------------------------------------------------

  const labelRoot = document.createElement('div');
  labelRoot.className = 'district-label-layer';
  container.appendChild(labelRoot);

  /** Live label elements, keyed by district id, so panning reuses nodes. */
  const labelEls = new Map<string, HTMLElement>();

  const camera = globe.camera();
  const worldPos = new THREE.Vector3();
  const toCamera = new THREE.Vector3();

  /**
   * Is this coordinate on the near face of the globe?
   *
   * `getScreenCoords` happily projects points on the far side, which would
   * otherwise scatter labels for districts hidden behind the Earth across the
   * visible hemisphere. A point faces the camera when its surface normal and
   * the direction to the camera agree.
   */
  function facesCamera(lat: number, lon: number): boolean {
    const c = globe.getCoords(lat, lon, 0);
    worldPos.set(c.x, c.y, c.z);
    toCamera.copy(camera.position).sub(worldPos);
    return worldPos.dot(toCamera) > 0;
  }

  interface Placed {
    left: number;
    top: number;
    right: number;
    bottom: number;
  }

  /** Approximate rendered width: 11px type averages ~5.6px per character. */
  const labelWidth = (name: string) => name.length * 5.6 + 10;
  const LABEL_HEIGHT = 16;
  const LABEL_GAP = 3;

  function clearLabels() {
    if (!labelEls.size) return;
    labelRoot.replaceChildren();
    labelEls.clear();
  }

  function renderLabels(visible: DistrictGeometry[], altitude: number) {
    if (altitude >= LABEL_VISIBLE_ALTITUDE || !layerVisible) {
      clearLabels();
      return;
    }

    const pov = globe.pointOfView();
    const { width, height } = container.getBoundingClientRect();

    // Nearest the view centre wins: those are what the user is looking at, and
    // they get first claim on the screen space.
    const candidates = [...visible].sort(
      (a, b) => sqDist(a.centroid, pov) - sqDist(b.centroid, pov),
    );

    const placedBoxes: Placed[] = [];
    const survivors: { d: DistrictGeometry; x: number; y: number }[] = [];

    for (const d of candidates) {
      if (survivors.length >= MAX_LABELS) break;

      const [lon, lat] = d.centroid;
      if (!facesCamera(lat, lon)) continue;

      const screen = globe.getScreenCoords(lat, lon, 0.006);
      if (!screen || !Number.isFinite(screen.x) || !Number.isFinite(screen.y)) continue;
      if (screen.x < 0 || screen.y < 0 || screen.x > width || screen.y > height) continue;

      const halfW = labelWidth(d.name) / 2;
      const box: Placed = {
        left: screen.x - halfW - LABEL_GAP,
        right: screen.x + halfW + LABEL_GAP,
        top: screen.y - LABEL_HEIGHT / 2 - LABEL_GAP,
        bottom: screen.y + LABEL_HEIGHT / 2 + LABEL_GAP,
      };

      // Greedy declutter: a label that would collide with one already placed is
      // dropped rather than nudged. Nudging moves a name off the district it
      // names, which on a map is worse than showing one fewer name.
      const collides = placedBoxes.some(
        (p) =>
          box.left < p.right &&
          box.right > p.left &&
          box.top < p.bottom &&
          box.bottom > p.top,
      );
      if (collides) continue;

      placedBoxes.push(box);
      survivors.push({ d, x: screen.x, y: screen.y });
    }

    const keep = new Set(survivors.map((s) => s.d.id));
    for (const [id, el] of labelEls) {
      if (!keep.has(id)) {
        el.remove();
        labelEls.delete(id);
      }
    }

    for (const { d, x, y } of survivors) {
      let el = labelEls.get(d.id);
      if (!el) {
        el = document.createElement('span');
        el.className = 'district-label';
        el.textContent = d.name;
        labelRoot.appendChild(el);
        labelEls.set(d.id, el);
      }
      el.style.transform = `translate(-50%,-50%) translate(${x}px,${y}px)`;
    }
  }

  const sqDist = (c: [number, number], pov: { lat: number; lng: number }) =>
    (c[0] - pov.lng) ** 2 + (c[1] - pov.lat) ** 2;

  // ---------------------------------------------------------------------------
  // Viewport tracking
  // ---------------------------------------------------------------------------

  let layerVisible = true;
  let frame: number | null = null;

  function currentViewport(): { visible: DistrictGeometry[]; altitude: number } {
    const pov = globe.pointOfView();
    // Half-width of the visible window, widening as the camera pulls back.
    const span = Math.max(1.5, pov.altitude * 26);
    return {
      altitude: pov.altitude,
      visible: locator.within(
        pov.lng - span,
        pov.lat - span * 0.62,
        pov.lng + span,
        pov.lat + span * 0.62,
      ),
    };
  }

  let lastAltitude = -1;
  let lastReported = '';

  function sync() {
    frame = null;
    const { visible, altitude } = currentViewport();

    const showBorders = layerVisible && altitude < BORDER_VISIBLE_ALTITUDE;
    borderMesh.visible = showBorders;
    fillMesh.visible = showBorders;

    // Boundaries fade in over the last stretch of the approach rather than
    // popping into existence at the threshold.
    if (showBorders) {
      const t = Math.min(1, (BORDER_VISIBLE_ALTITUDE - altitude) / 0.45);

      // How far into the close-range view the camera is: 0 at regional
      // altitude, 1 once the tile basemap is showing streets and place names.
      const closeUp = Math.min(1, Math.max(0, (0.35 - altitude) / 0.3));

      // The choropleth is a regional instrument: at a glance it says which
      // districts are dangerous. Close in that job is done, and a flat wash of
      // colour would only bury the basemap detail the user zoomed in to read
      // -- so the fill recedes to a tint while the boundaries firm up.
      // Tuned to sit over satellite imagery. The hazard wash has to be read
      // as a tint on real ground, not as a replacement for it, so it peaks
      // well below opaque and recedes further once the camera is close enough
      // for the imagery itself to be the point.
      fillMaterial.opacity = (0.14 + t * 0.26) * (1 - 0.72 * closeUp);
      borderMaterial.opacity = 0.1 + t * 0.16 + 0.14 * closeUp;
    }

    renderLabels(visible, altitude);

    if (Math.abs(altitude - lastAltitude) > 1e-4) lastAltitude = altitude;

    const signature = `${visible.length}:${visible[0]?.id ?? ''}:${
      visible[visible.length - 1]?.id ?? ''
    }`;
    if (signature !== lastReported) {
      lastReported = signature;
      options.onViewportChange?.(visible, altitude);
    }
  }

  const scheduleSync = () => {
    if (frame == null) frame = requestAnimationFrame(sync);
  };

  const controls = globe.controls();
  controls.addEventListener('change', scheduleSync);
  window.addEventListener('resize', scheduleSync);
  sync();

  // ---------------------------------------------------------------------------
  // Picking
  // ---------------------------------------------------------------------------

  let hoveredId: string | null = null;
  let selectedId: string | null = null;

  function districtAtPointer(ev: PointerEvent): DistrictGeometry | null {
    const rect = container.getBoundingClientRect();
    const coords = globe.toGlobeCoords(ev.clientX - rect.left, ev.clientY - rect.top);
    if (!coords) return null;
    return locator.locate(coords.lng, coords.lat);
  }

  let hoverFrame: number | null = null;
  let pointerEvent: PointerEvent | null = null;

  const onPointerMove = (ev: PointerEvent) => {
    if (!layerVisible || lastAltitude >= BORDER_VISIBLE_ALTITUDE) {
      if (hoveredId) setHovered(null);
      return;
    }
    pointerEvent = ev;
    if (hoverFrame != null) return;
    hoverFrame = requestAnimationFrame(() => {
      hoverFrame = null;
      if (!pointerEvent) return;
      const hit = districtAtPointer(pointerEvent);
      if ((hit?.id ?? null) !== hoveredId) {
        setHovered(hit?.id ?? null);
        options.onHover?.(hit ?? null);
      }
    });
  };

  const onPointerLeave = () => {
    if (hoveredId) {
      setHovered(null);
      options.onHover?.(null);
    }
  };

  // Distinguish a click from the tail of an orbit drag.
  let downAt: { x: number; y: number } | null = null;
  const onPointerDown = (ev: PointerEvent) => {
    downAt = { x: ev.clientX, y: ev.clientY };
  };

  const onPointerUp = (ev: PointerEvent) => {
    const start = downAt;
    downAt = null;
    if (!start || !layerVisible) return;
    if (Math.hypot(ev.clientX - start.x, ev.clientY - start.y) > CLICK_SLOP_PX) return;
    if (lastAltitude >= BORDER_VISIBLE_ALTITUDE) return;

    const hit = districtAtPointer(ev);
    // A click on empty ocean or outside India clears the selection, which is
    // the only way back out of a district without using the panel.
    setSelected(hit?.id ?? null);
    options.onSelect?.(hit ?? null);
  };

  container.addEventListener('pointermove', onPointerMove);
  container.addEventListener('pointerleave', onPointerLeave);
  container.addEventListener('pointerdown', onPointerDown);
  container.addEventListener('pointerup', onPointerUp);

  // ---------------------------------------------------------------------------
  // Handle
  // ---------------------------------------------------------------------------

  function setHovered(id: string | null) {
    hoveredId = id;
    // The selected outline already covers this district; a second, dimmer
    // outline on top of it only muddies the edge.
    applyOutline(hoverMesh, id === selectedId ? null : id);
  }

  function setSelected(id: string | null) {
    selectedId = id;
    applyOutline(highlightMesh, id);
    if (hoveredId === id) applyOutline(hoverMesh, null);
  }

  return {
    setSeverity(bySeverity) {
      const colors = colorAttr.array as Float32Array;
      const colour = new THREE.Color();
      for (const [id, range] of fillRanges) {
        const level = bySeverity.get(id);
        const alpha = level ? 1 : UNSCORED_ALPHA;
        if (level) colour.set(SEVERITY_COLOR[level]);
        else colour.setRGB(0, 0, 0);
        const end = (range.start + range.count) * 4;
        for (let i = range.start * 4; i < end; i += 4) {
          colors[i] = colour.r;
          colors[i + 1] = colour.g;
          colors[i + 2] = colour.b;
          colors[i + 3] = alpha;
        }
      }
      colorAttr.needsUpdate = true;
    },

    setSelected,
    setHovered,

    setVisible(visible) {
      layerVisible = visible;
      highlightMesh.visible = visible && highlightMesh.geometry.getAttribute('position').count > 0;
      hoverMesh.visible = visible && hoverMesh.geometry.getAttribute('position').count > 0;
      scheduleSync();
    },

    get: (id) => byId.get(id),

    flyTo(id, ms = 1100) {
      const d = byId.get(id);
      if (!d) return;
      const [minLon, minLat, maxLon, maxLat] = d.bbox;
      // Frame the district: altitude scaled off its larger extent so a small
      // urban district and a large desert one both fill a similar share of the
      // viewport.
      const extent = Math.max(maxLon - minLon, maxLat - minLat);
      const altitude = Math.min(0.45, Math.max(0.06, extent * 0.3));
      globe.pointOfView({ lat: d.centroid[1], lng: d.centroid[0], altitude }, ms);
    },

    dispose() {
      if (frame != null) cancelAnimationFrame(frame);
      if (hoverFrame != null) cancelAnimationFrame(hoverFrame);
      controls.removeEventListener('change', scheduleSync);
      window.removeEventListener('resize', scheduleSync);
      container.removeEventListener('pointermove', onPointerMove);
      container.removeEventListener('pointerleave', onPointerLeave);
      container.removeEventListener('pointerdown', onPointerDown);
      container.removeEventListener('pointerup', onPointerUp);
      labelRoot.remove();

      for (const mesh of [fillMesh, borderMesh, highlightMesh, hoverMesh]) {
        scene.remove(mesh);
        mesh.geometry.dispose();
        (mesh.material as THREE.Material).dispose();
      }
    },
  };
}
