"""
Build a web-sized India district (ADM2) asset for the 3D globe.

Source: geoBoundaries gbOpen IND ADM2 (2021), 735 districts, 8 MB raw.
That is far too heavy to ship to a browser, and geoBoundaries carries no
parent-state attribution, so this script does three things:

  1. Simplifies every ring with Douglas-Peucker and clamps coordinate
     precision to 4 dp (~11 m) -- well below what is visible at the closest
     camera altitude the globe allows.
  2. Assigns each district its parent state by point-in-polygon of the
     district centroid against the existing indian_states.geojson, falling
     back to the nearest state centroid for districts whose centroid lands
     in a coastline gap between the two datasets.
  3. Emits a geometry-free index for the search bar, so typeahead does not
     need the multi-megabyte polygon payload.

Output properties are single-letter to keep the payload small:
    d = district name, s = state name, c = [lon, lat] centroid
"""
import json
import math
import sys
import numpy as np

SRC = sys.argv[1]
STATES = sys.argv[2]
OUT_GEO = sys.argv[3]
OUT_INDEX = sys.argv[4]

TOLERANCE = 0.008      # degrees (~0.9 km) -- crisp at max zoom, cheap at min
PRECISION = 4          # decimal places (~11 m)
MIN_RING_AREA = 1e-5   # deg^2 -- drops slivers and single-pixel islands


def douglas_peucker(pts: np.ndarray, tol: float) -> np.ndarray:
    """Iterative Douglas-Peucker. Iterative, not recursive: some coastal rings
    run to thousands of vertices and blow the recursion limit."""
    n = len(pts)
    if n < 3:
        return pts
    keep = np.zeros(n, dtype=bool)
    keep[0] = keep[n - 1] = True
    stack = [(0, n - 1)]
    while stack:
        lo, hi = stack.pop()
        if hi <= lo + 1:
            continue
        a, b = pts[lo], pts[hi]
        seg = b - a
        seg_len2 = seg.dot(seg)
        rel = pts[lo + 1:hi] - a
        if seg_len2 == 0:
            dist = np.hypot(rel[:, 0], rel[:, 1])
        else:
            # Perpendicular distance from each interior point to segment a->b.
            t = np.clip((rel @ seg) / seg_len2, 0.0, 1.0)
            proj = np.outer(t, seg)
            dist = np.hypot(*(rel - proj).T)
        idx = int(np.argmax(dist))
        if dist[idx] > tol:
            split = lo + 1 + idx
            keep[split] = True
            stack.append((lo, split))
            stack.append((split, hi))
    return pts[keep]


def ring_area(ring: np.ndarray) -> float:
    """Absolute shoelace area in square degrees."""
    x, y = ring[:, 0], ring[:, 1]
    return abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))) / 2.0


def ring_centroid(ring: np.ndarray):
    """Polygon centroid via the shoelace formula, with a mean-of-vertices
    fallback for degenerate (zero-area) rings."""
    x, y = ring[:, 0], ring[:, 1]
    xn, yn = np.roll(x, -1), np.roll(y, -1)
    cross = x * yn - xn * y
    a = cross.sum() / 2.0
    if abs(a) < 1e-12:
        return float(x.mean()), float(y.mean())
    cx = ((x + xn) * cross).sum() / (6.0 * a)
    cy = ((y + yn) * cross).sum() / (6.0 * a)
    return float(cx), float(cy)


def simplify_ring(coords, tol):
    pts = np.asarray(coords, dtype=float)
    if len(pts) < 4:
        return None
    closed = np.allclose(pts[0], pts[-1])
    if closed:
        pts = pts[:-1]
    if ring_area(pts) < MIN_RING_AREA:
        return None
    simplified = douglas_peucker(np.vstack([pts, pts[:1]]), tol)
    if len(simplified) < 4:
        return None
    out = np.round(simplified, PRECISION)
    # Rounding can collapse adjacent vertices onto each other.
    dedup = [out[0]]
    for p in out[1:]:
        if not np.array_equal(p, dedup[-1]):
            dedup.append(p)
    if len(dedup) < 4:
        return None
    if not np.array_equal(dedup[0], dedup[-1]):
        dedup.append(dedup[0])
    return [[float(a), float(b)] for a, b in dedup]


def rings_of(geom):
    """Flatten Polygon/MultiPolygon into a list of (ring, is_outer)."""
    t = geom.get("type")
    if t == "Polygon":
        polys = [geom["coordinates"]]
    elif t == "MultiPolygon":
        polys = geom["coordinates"]
    else:
        return []
    out = []
    for poly in polys:
        for i, ring in enumerate(poly):
            out.append((ring, i == 0))
    return out


def point_in_ring(lon, lat, ring) -> bool:
    """Standard ray-casting test."""
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > lat) != (yj > lat):
            x_cross = (xj - xi) * (lat - yi) / (yj - yi) + xi
            if lon < x_cross:
                inside = not inside
        j = i
    return inside


# ---------------------------------------------------------------------------
# State lookup table, built once from the existing 35-feature state file.
# ---------------------------------------------------------------------------
states = json.load(open(STATES))
state_entries = []
for f in states["features"]:
    name = f["properties"].get("NAME_1")
    polys = []
    t = f["geometry"]["type"]
    raw = [f["geometry"]["coordinates"]] if t == "Polygon" else f["geometry"]["coordinates"]
    for poly in raw:
        outer = poly[0]
        holes = poly[1:]
        arr = np.asarray(outer, dtype=float)
        polys.append({
            "outer": outer,
            "holes": holes,
            "bbox": (arr[:, 0].min(), arr[:, 1].min(), arr[:, 0].max(), arr[:, 1].max()),
        })
    all_pts = np.vstack([np.asarray(p["outer"], dtype=float) for p in polys])
    state_entries.append({
        "name": name,
        "polys": polys,
        "centroid": (float(all_pts[:, 0].mean()), float(all_pts[:, 1].mean())),
    })


def state_for(lon, lat):
    for st in state_entries:
        for p in st["polys"]:
            x0, y0, x1, y1 = p["bbox"]
            if not (x0 <= lon <= x1 and y0 <= lat <= y1):
                continue
            if point_in_ring(lon, lat, p["outer"]) and not any(
                point_in_ring(lon, lat, h) for h in p["holes"]
            ):
                return st["name"]
    # Coastline mismatch between the two datasets -- snap to nearest state.
    best, best_d = None, float("inf")
    for st in state_entries:
        cx, cy = st["centroid"]
        d = (cx - lon) ** 2 + (cy - lat) ** 2
        if d < best_d:
            best, best_d = st["name"], d
    return best


# ---------------------------------------------------------------------------
# Corrections. The state file is pre-2014 GADM: it predates Telangana and
# Ladakh and still uses retired state names, while the ADM2 file is 2021 and
# already splits those districts out. Point-in-polygon therefore lands them in
# the wrong parent, so the reorganisations are applied by name.
# ---------------------------------------------------------------------------
TELANGANA = {
    "Adilabad", "Bhadradri", "Hydrabad", "Jagtial", "Jangaon", "Jayashankar",
    "Jogulamba", "Kamareddy", "Karimnagar", "Khammam", "Komaram Bheem",
    "Mahabubabad", "Mahabubnagar", "Mancherial", "Medak", "Medchal", "Mulugu",
    "Nagarkurnool", "Nalgonda", "Narayanpet", "Nirmal", "Nizamabad",
    "Peddapalli", "Rajanna Sircilla", "Rangareddy", "Sangareddy", "Siddipet",
    "Suryapet", "Vikarabad", "Wanaparthy", "Warangal (R)", "Warangal (U)",
    "Yadadri Bhongiri",
}
LADAKH = {"Leh(Ladakh)", "Kargil"}
# Enclaves of one UT that sit geographically inside another state.
ENCLAVES = {"Yanam": "Puducherry", "Mahe": "Puducherry"}

# Retired state names carried by the 2015-era GADM state file.
STATE_RENAME = {
    "Orissa": "Odisha",
    "Uttaranchal": "Uttarakhand",
    "Jammu and Kashmir": "Jammu & Kashmir",
    "Andaman and Nicobar": "Andaman & Nicobar",
    "Dadra and Nagar Haveli": "Dadra & Nagar Haveli",
    "Daman and Diu": "Daman & Diu",
    "NCT of Delhi": "Delhi",
}

# Districts whose source name is a bare compass direction -- unusable in a
# search box on its own.
DELHI_BARE = {"Central", "East", "North", "North East", "North West",
              "Shahdara", "South", "South East", "South West", "West"}

# Placeholder rows in the source with no real geometry attribution.
SKIP_NAMES = {"DATA NOT AVAILABLE"}


def resolve(name, state):
    """Apply the reorganisation corrections, returning (name, state)."""
    if name in TELANGANA:
        state = "Telangana"
    elif name in LADAKH:
        state = "Ladakh"
    elif name in ENCLAVES:
        state = ENCLAVES[name]
    state = STATE_RENAME.get(state, state)
    if state == "Delhi" and name in DELHI_BARE:
        name = f"{name} Delhi"
    if name == "Hydrabad":
        name = "Hyderabad"
    if name == "Leh(Ladakh)":
        name = "Leh"
    return name, state


# ---------------------------------------------------------------------------
# Main pass.
# ---------------------------------------------------------------------------
src = json.load(open(SRC))
features = []
index = []
dropped = 0
snapped = 0

for feat in src["features"]:
    name = (feat["properties"].get("shapeName") or "").strip()
    if not name or name in SKIP_NAMES:
        dropped += 1
        continue

    simplified_polys = []
    largest_ring, largest_area = None, 0.0
    current = None

    for ring, is_outer in rings_of(feat["geometry"]):
        s = simplify_ring(ring, TOLERANCE)
        if s is None:
            continue
        arr = np.asarray(s, dtype=float)
        if is_outer:
            current = [s]
            simplified_polys.append(current)
            a = ring_area(arr)
            if a > largest_area:
                largest_area, largest_ring = a, arr
        elif current is not None:
            current.append(s)

    simplified_polys = [p for p in simplified_polys if p]
    if not simplified_polys or largest_ring is None:
        dropped += 1
        continue

    clon, clat = ring_centroid(largest_ring)
    clon, clat = round(clon, 4), round(clat, 4)
    name, st = resolve(name, state_for(clon, clat))

    all_pts = np.vstack([np.asarray(p[0], dtype=float) for p in simplified_polys])
    bbox = [
        round(float(all_pts[:, 0].min()), 4), round(float(all_pts[:, 1].min()), 4),
        round(float(all_pts[:, 0].max()), 4), round(float(all_pts[:, 1].max()), 4),
    ]

    geom = (
        {"type": "Polygon", "coordinates": simplified_polys[0]}
        if len(simplified_polys) == 1
        else {"type": "MultiPolygon", "coordinates": simplified_polys}
    )
    features.append({
        "type": "Feature",
        "properties": {"d": name, "s": st, "c": [clon, clat]},
        "geometry": geom,
    })
    index.append({"d": name, "s": st, "c": [clon, clat], "b": bbox})

out = {"type": "FeatureCollection", "features": features}
with open(OUT_GEO, "w") as f:
    json.dump(out, f, separators=(",", ":"))
with open(OUT_INDEX, "w") as f:
    json.dump({"count": len(index), "districts": index}, f, separators=(",", ":"))

verts = sum(
    len(r)
    for feat in features
    for poly in ([feat["geometry"]["coordinates"]] if feat["geometry"]["type"] == "Polygon" else feat["geometry"]["coordinates"])
    for r in poly
)
print(f"districts written : {len(features)}  (dropped {dropped})")
print(f"total vertices    : {verts}")
states_seen = sorted({f['properties']['s'] for f in features})
print(f"states covered    : {len(states_seen)}")
