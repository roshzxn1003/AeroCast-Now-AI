"""
Live atmospheric observation ingest for AeroCast-Now.

Two independent live providers feed the globe:

  1. Blitzortung.org LDN  -> genuine real-time cloud-to-ground / intra-cloud
     strike geolocations over the Indian domain. Best effort: the network uses
     non-standard ports (3000/8080) which some environments firewall.

  2. Open-Meteo convective analysis -> live CAPE, Lifted Index, CIN,
     precipitation probability and WMO weather codes on an Indian grid. Always
     available over HTTPS.

Provenance is never blurred. Every record carries a `source` field that the UI
renders verbatim as LIVE / LIVE-DERIVED / MODEL so a viewer can always tell
measured data from synthesised data.
"""

from __future__ import annotations

import json
import math
import random
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests

# ==============================================================================
# DOMAIN
# ==============================================================================

# Indian mainland + adjoining seas. Nowcasting domain for the globe view.
INDIA_BBOX = {"lat_min": 6.5, "lat_max": 37.5, "lon_min": 68.0, "lon_max": 97.5}

# Sampling nodes for the live convective analysis. Chosen to cover the major
# convective regimes: Gangetic plain, NE monsoon core, Western Ghats orographic
# belt, central India MCS corridor and the two coastal thunderstorm zones.
CONVECTIVE_NODES: List[Dict[str, Any]] = [
    {"name": "Chennai",        "lat": 13.08, "lon": 80.27, "region": "Tamil Nadu"},
    {"name": "Mumbai",         "lat": 19.08, "lon": 72.88, "region": "Maharashtra"},
    {"name": "Delhi NCR",      "lat": 28.61, "lon": 77.21, "region": "NCR Delhi"},
    {"name": "Kolkata",        "lat": 22.57, "lon": 88.36, "region": "West Bengal"},
    {"name": "Hyderabad",      "lat": 17.39, "lon": 78.49, "region": "Telangana"},
    {"name": "Bengaluru",      "lat": 12.97, "lon": 77.59, "region": "Karnataka"},
    {"name": "Guwahati",       "lat": 26.14, "lon": 91.74, "region": "Assam"},
    {"name": "Jaipur",         "lat": 26.91, "lon": 75.79, "region": "Rajasthan"},
    {"name": "Patna",          "lat": 25.59, "lon": 85.14, "region": "Bihar"},
    {"name": "Bhubaneswar",    "lat": 20.30, "lon": 85.82, "region": "Odisha"},
    {"name": "Nagpur",         "lat": 21.15, "lon": 79.09, "region": "Maharashtra"},
    {"name": "Ahmedabad",      "lat": 23.02, "lon": 72.57, "region": "Gujarat"},
    {"name": "Lucknow",        "lat": 26.85, "lon": 80.95, "region": "Uttar Pradesh"},
    {"name": "Bhopal",         "lat": 23.26, "lon": 77.41, "region": "Madhya Pradesh"},
    {"name": "Raipur",         "lat": 21.25, "lon": 81.63, "region": "Chhattisgarh"},
    {"name": "Visakhapatnam",  "lat": 17.69, "lon": 83.22, "region": "Andhra Pradesh"},
    {"name": "Thiruvananthapuram", "lat": 8.52, "lon": 76.94, "region": "Kerala"},
    {"name": "Kochi",          "lat": 9.93, "lon": 76.27, "region": "Kerala"},
    {"name": "Goa",            "lat": 15.30, "lon": 74.12, "region": "Goa"},
    {"name": "Pune",           "lat": 18.52, "lon": 73.86, "region": "Maharashtra"},
    {"name": "Srinagar",       "lat": 34.08, "lon": 74.80, "region": "J&K"},
    {"name": "Amritsar",       "lat": 31.63, "lon": 74.87, "region": "Punjab"},
    {"name": "Dehradun",       "lat": 30.32, "lon": 78.03, "region": "Uttarakhand"},
    {"name": "Ranchi",         "lat": 23.34, "lon": 85.31, "region": "Jharkhand"},
    {"name": "Shillong",       "lat": 25.58, "lon": 91.89, "region": "Meghalaya"},
    {"name": "Imphal",         "lat": 24.82, "lon": 93.94, "region": "Manipur"},
    {"name": "Agartala",       "lat": 23.83, "lon": 91.28, "region": "Tripura"},
    {"name": "Jodhpur",        "lat": 26.24, "lon": 73.02, "region": "Rajasthan"},
    {"name": "Coimbatore",     "lat": 11.02, "lon": 76.96, "region": "Tamil Nadu"},
    {"name": "Madurai",        "lat": 9.93,  "lon": 78.12, "region": "Tamil Nadu"},
    {"name": "Varanasi",       "lat": 25.32, "lon": 82.97, "region": "Uttar Pradesh"},
    {"name": "Indore",         "lat": 22.72, "lon": 75.86, "region": "Madhya Pradesh"},
    {"name": "Surat",          "lat": 21.17, "lon": 72.83, "region": "Gujarat"},
    {"name": "Vijayawada",     "lat": 16.51, "lon": 80.65, "region": "Andhra Pradesh"},
    {"name": "Mangaluru",      "lat": 12.91, "lon": 74.86, "region": "Karnataka"},
    {"name": "Port Blair",     "lat": 11.62, "lon": 92.73, "region": "Andaman & Nicobar"},
]

# WMO weather codes that indicate an active thunderstorm at the surface.
THUNDERSTORM_CODES = {95, 96, 99}

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

_CONVECTIVE_TTL_S = 300.0   # Open-Meteo refreshes on a 15-min cadence.
_STRIKE_WINDOW_MIN = 30     # Rolling strike history retained for the globe.


# ==============================================================================
# CONVECTIVE INSTABILITY CLASSIFICATION
# ==============================================================================

def classify_instability(cape: float, lifted_index: float) -> str:
    """Operational convective potential category from CAPE and Lifted Index."""
    if cape >= 3500 or lifted_index <= -6:
        return "EXTREME"
    if cape >= 2500 or lifted_index <= -4:
        return "SEVERE"
    if cape >= 1500 or lifted_index <= -2:
        return "MODERATE"
    if cape >= 500:
        return "MARGINAL"
    return "STABLE"


def convective_intensity(node: Dict[str, Any]) -> float:
    """
    Collapse the live sounding into a single 0..1 convective vigour index.

    Weighted so that an observed surface thunderstorm (WMO 95/96/99) dominates,
    since that is a measurement rather than an instability proxy.
    """
    cape = max(0.0, node.get("cape", 0.0) or 0.0)
    li = node.get("lifted_index", 0.0) or 0.0
    pprob = node.get("precipitation_probability", 0.0) or 0.0
    observed_ts = node.get("weather_code") in THUNDERSTORM_CODES

    cape_term = min(1.0, cape / 4000.0) * 0.40
    li_term = min(1.0, max(0.0, -li) / 8.0) * 0.25
    prob_term = (pprob / 100.0) * 0.15
    observed_term = 0.20 if observed_ts else 0.0

    return round(min(1.0, cape_term + li_term + prob_term + observed_term), 4)


# ==============================================================================
# OPEN-METEO LIVE CONVECTIVE ANALYSIS
# ==============================================================================

@dataclass
class _Cache:
    payload: Optional[Dict[str, Any]] = None
    fetched_at: float = 0.0
    lock: threading.Lock = field(default_factory=threading.Lock)


_convective_cache = _Cache()


def _parse_node(raw: Dict[str, Any], node: Dict[str, Any]) -> Dict[str, Any]:
    """Map one Open-Meteo response block onto a convective analysis record."""
    current = raw.get("current", {}) or {}
    hourly = raw.get("hourly", {}) or {}

    def _hour_now(key: str, default: float = 0.0) -> float:
        series = hourly.get(key) or []
        times = hourly.get("time") or []
        if not series:
            return default
        # Align to the current wall-clock hour of the node's own timezone.
        stamp = current.get("time", "")
        idx = 0
        if stamp and times:
            target = stamp[:13]  # YYYY-MM-DDTHH
            for i, t in enumerate(times):
                if t[:13] == target:
                    idx = i
                    break
        value = series[idx] if idx < len(series) else series[0]
        return default if value is None else float(value)

    cape = _hour_now("cape")
    li = _hour_now("lifted_index")
    cin = _hour_now("convective_inhibition")
    pprob = _hour_now("precipitation_probability")
    code = int(current.get("weather_code") or 0)

    record = {
        "name": node["name"],
        "region": node["region"],
        "lat": node["lat"],
        "lon": node["lon"],
        "cape_j_kg": round(cape, 1),
        "lifted_index_c": round(li, 2),
        # Open-Meteo reports CIN as a positive magnitude; meteorological
        # convention is negative (energy opposing ascent).
        "cin_j_kg": round(-abs(cin), 1),
        "precipitation_probability": round(pprob),
        "precipitation_mm": round(float(current.get("precipitation") or 0.0), 2),
        "temperature_c": round(float(current.get("temperature_2m") or 0.0), 1),
        "cloud_cover_pct": round(float(current.get("cloud_cover") or 0.0)),
        "wind_speed_kmh": round(float(current.get("wind_speed_10m") or 0.0), 1),
        "wind_direction_deg": round(float(current.get("wind_direction_10m") or 0.0)),
        "weather_code": code,
        "thunderstorm_observed": code in THUNDERSTORM_CODES,
        "observation_time": current.get("time"),
        "source": "LIVE",
        "provider": "Open-Meteo (ECMWF IFS / DWD ICON blend)",
    }
    record["cape"] = record["cape_j_kg"]
    record["lifted_index"] = record["lifted_index_c"]
    record["instability"] = classify_instability(cape, li)
    record["intensity"] = convective_intensity(record)
    return record


def fetch_live_convective(force: bool = False) -> Dict[str, Any]:
    """
    Batch-query every convective node in a single Open-Meteo request.

    Returns a payload with `nodes`, `status` and `source`. On network failure the
    last good cached payload is served with a `STALE` status rather than raising,
    so the globe degrades gracefully instead of going blank.
    """
    now = time.monotonic()
    with _convective_cache.lock:
        fresh = (
            _convective_cache.payload is not None
            and (now - _convective_cache.fetched_at) < _CONVECTIVE_TTL_S
        )
        if fresh and not force:
            return _convective_cache.payload

    lats = ",".join(str(n["lat"]) for n in CONVECTIVE_NODES)
    lons = ",".join(str(n["lon"]) for n in CONVECTIVE_NODES)
    params = {
        "latitude": lats,
        "longitude": lons,
        "current": "temperature_2m,precipitation,weather_code,cloud_cover,wind_speed_10m,wind_direction_10m",
        "hourly": "cape,lifted_index,convective_inhibition,precipitation_probability",
        "forecast_days": 1,
        "timezone": "auto",
    }

    try:
        resp = requests.get(OPEN_METEO_URL, params=params, timeout=15)
        resp.raise_for_status()
        body = resp.json()
        blocks = body if isinstance(body, list) else [body]

        nodes = [
            _parse_node(block, CONVECTIVE_NODES[i])
            for i, block in enumerate(blocks)
            if i < len(CONVECTIVE_NODES)
        ]

        active = [n for n in nodes if n["thunderstorm_observed"]]
        payload = {
            "status": "LIVE",
            "source": "Open-Meteo convective analysis",
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "node_count": len(nodes),
            "active_thunderstorm_count": len(active),
            "domain": INDIA_BBOX,
            "nodes": nodes,
        }

        with _convective_cache.lock:
            _convective_cache.payload = payload
            _convective_cache.fetched_at = time.monotonic()
        return payload

    except Exception as exc:  # noqa: BLE001 - degrade, never crash the globe
        with _convective_cache.lock:
            if _convective_cache.payload is not None:
                stale = dict(_convective_cache.payload)
                stale["status"] = "STALE"
                stale["error"] = str(exc)
                return stale
        return {
            "status": "UNAVAILABLE",
            "source": "Open-Meteo convective analysis",
            "error": str(exc),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "node_count": 0,
            "active_thunderstorm_count": 0,
            "domain": INDIA_BBOX,
            "nodes": [],
        }


# ==============================================================================
# BLITZORTUNG LIGHTNING DETECTION NETWORK (REAL-TIME STRIKE GEOLOCATIONS)
# ==============================================================================

BLITZORTUNG_HOSTS = [
    "ws1.blitzortung.org",
    "ws7.blitzortung.org",
    "ws8.blitzortung.org",
]
BLITZORTUNG_PORT = 3000


def _lzw_decode(payload: str) -> str:
    """
    Decode Blitzortung's LZW-compressed websocket frames.

    The network ships each frame through a compact LZW variant seeded with the
    single-byte alphabet. This is a direct port of the reference decoder.
    """
    if not payload:
        return ""

    dictionary: Dict[int, str] = {}
    chars = list(payload)
    current = previous = chars[0]
    out = [current]
    code = 256
    next_code = 256

    for i in range(1, len(chars)):
        char_code = ord(chars[i])
        if char_code < code:
            entry = chars[i]
        elif char_code in dictionary:
            entry = dictionary[char_code]
        else:
            entry = previous + current
        out.append(entry)
        current = entry[0]
        dictionary[next_code] = previous + current
        next_code += 1
        previous = entry

    return "".join(out)


def _in_domain(lat: float, lon: float) -> bool:
    return (
        INDIA_BBOX["lat_min"] <= lat <= INDIA_BBOX["lat_max"]
        and INDIA_BBOX["lon_min"] <= lon <= INDIA_BBOX["lon_max"]
    )


class BlitzortungClient:
    """
    Background websocket consumer for the Blitzortung LDN.

    Runs on a daemon thread, keeps a rolling in-domain strike buffer, and
    reconnects with backoff. If the network is unreachable — several
    environments firewall the non-standard port it runs on — `connected` stays
    False and the caller falls back to the derived strike field.
    """

    def __init__(self, buffer_minutes: int = _STRIKE_WINDOW_MIN) -> None:
        self.buffer_minutes = buffer_minutes
        self._strikes: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self.connected = False
        self.last_error: Optional[str] = None
        self.total_received = 0
        self.started_at: Optional[str] = None

    # -- lifecycle ---------------------------------------------------------

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self.started_at = datetime.now(timezone.utc).isoformat()
        self._thread = threading.Thread(
            target=self._run_forever, name="blitzortung-ldn", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    # -- consumption -------------------------------------------------------

    def _run_forever(self) -> None:
        import asyncio

        backoff = 2.0
        while not self._stop.is_set():
            try:
                asyncio.run(self._consume())
                backoff = 2.0
            except Exception as exc:  # noqa: BLE001
                self.connected = False
                self.last_error = f"{type(exc).__name__}: {exc}"
            if self._stop.is_set():
                break
            time.sleep(min(backoff, 60.0))
            backoff *= 2

    async def _consume(self) -> None:
        import asyncio

        try:
            import websockets
        except ImportError:
            self.last_error = "websockets package not installed"
            self._stop.set()
            return

        for host in BLITZORTUNG_HOSTS:
            if self._stop.is_set():
                return
            url = f"ws://{host}:{BLITZORTUNG_PORT}/"
            try:
                async with websockets.connect(url, open_timeout=8, ping_interval=20) as ws:
                    await ws.send(json.dumps({"a": 111}))
                    self.connected = True
                    self.last_error = None
                    while not self._stop.is_set():
                        raw = await asyncio.wait_for(ws.recv(), timeout=45)
                        self._ingest(raw)
            except Exception as exc:  # noqa: BLE001 - try the next mirror
                self.connected = False
                self.last_error = f"{host}: {type(exc).__name__}"
                continue
        raise ConnectionError(self.last_error or "no Blitzortung mirror reachable")

    def _ingest(self, raw: str) -> None:
        try:
            decoded = _lzw_decode(raw) if not raw.lstrip().startswith("{") else raw
            msg = json.loads(decoded)
        except Exception:  # noqa: BLE001 - skip malformed frames
            return

        lat = msg.get("lat")
        lon = msg.get("lon")
        if lat is None or lon is None or not _in_domain(float(lat), float(lon)):
            return

        # Blitzortung timestamps are nanoseconds since the Unix epoch.
        ts_ns = msg.get("time") or 0
        when = (
            datetime.fromtimestamp(ts_ns / 1e9, tz=timezone.utc)
            if ts_ns
            else datetime.now(timezone.utc)
        )

        strike = {
            "lat": round(float(lat), 4),
            "lon": round(float(lon), 4),
            "time": when.isoformat(),
            "age_s": max(0.0, (datetime.now(timezone.utc) - when).total_seconds()),
            # Polarity sign distinguishes cloud-to-ground return stroke type.
            "polarity": int(msg.get("pol") or 0),
            "type": "CG" if msg.get("mcg") else "IC",
            "detectors": len(msg.get("sig") or []),
            "source": "LIVE",
            "provider": "Blitzortung.org LDN",
        }

        self.total_received += 1
        with self._lock:
            self._strikes.append(strike)
            self._prune_locked()

    def _prune_locked(self) -> None:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=self.buffer_minutes)
        self._strikes = [
            s for s in self._strikes
            if datetime.fromisoformat(s["time"]) >= cutoff
        ]

    def snapshot(self) -> List[Dict[str, Any]]:
        with self._lock:
            self._prune_locked()
            return list(self._strikes)


_ldn_client = BlitzortungClient()


def start_lightning_network() -> None:
    """Begin consuming the LDN feed. Safe to call more than once."""
    _ldn_client.start()


def ldn_status() -> Dict[str, Any]:
    return {
        "connected": _ldn_client.connected,
        "buffered_strikes": len(_ldn_client.snapshot()),
        "total_received": _ldn_client.total_received,
        "last_error": _ldn_client.last_error,
        "started_at": _ldn_client.started_at,
        "provider": "Blitzortung.org LDN",
        "transport": f"websocket :{BLITZORTUNG_PORT}",
    }


# ==============================================================================
# DERIVED STRIKE FIELD (LIVE SOUNDING -> PROBABLE FLASH LOCATIONS)
# ==============================================================================

# Great-circle degrees per km at the equator, used to size convective clusters.
_DEG_PER_KM = 1.0 / 111.32


def _cluster_centres(node: Dict[str, Any], rng: random.Random) -> List[Dict[str, float]]:
    """
    Place convective cells around a sounding node.

    Real thunderstorm activity is organised into discrete cells rather than a
    uniform disc, so strikes are drawn around a handful of centroids offset from
    the node itself. Vigorous environments support more, larger cells.
    """
    intensity = node["intensity"]
    n_cells = 1 + int(round(intensity * 3))
    spread_km = 40.0 + intensity * 90.0

    centres = []
    for _ in range(n_cells):
        bearing = rng.uniform(0, 2 * math.pi)
        distance = rng.uniform(0, spread_km)
        d_lat = (distance * math.cos(bearing)) * _DEG_PER_KM
        d_lon = (distance * math.sin(bearing)) * _DEG_PER_KM / max(
            0.2, math.cos(math.radians(node["lat"]))
        )
        centres.append(
            {
                "lat": node["lat"] + d_lat,
                "lon": node["lon"] + d_lon,
                "radius_km": 12.0 + intensity * 28.0,
            }
        )
    return centres


def derive_strike_field(
    convective: Dict[str, Any], window_minutes: int = _STRIKE_WINDOW_MIN
) -> List[Dict[str, Any]]:
    """
    Synthesise a plausible flash field from the live convective analysis.

    This is NOT a measurement. It is a physically-weighted rendering of live
    instability, used only when the LDN feed is unreachable. Flash rate scales
    with the cube of the convective vigour index, matching the strongly
    non-linear observed relationship between CAPE and total lightning.

    Every returned record is tagged LIVE-DERIVED so the UI can label it.
    """
    nodes = convective.get("nodes", [])
    if not nodes:
        return []

    # Seed per refresh bucket: stable within a cycle, evolving between them.
    bucket = int(time.time() // 60)
    rng = random.Random(bucket)

    now = datetime.now(timezone.utc)
    strikes: List[Dict[str, Any]] = []

    for node in nodes:
        intensity = node["intensity"]
        if intensity < 0.25:
            continue  # Environment cannot support electrification.

        # Observed surface thunderstorms get a decisive flash-rate multiplier.
        multiplier = 2.6 if node["thunderstorm_observed"] else 1.0
        expected = int(round((intensity ** 3) * 240 * multiplier))
        if expected <= 0:
            continue

        centres = _cluster_centres(node, rng)
        per_cell = max(1, expected // len(centres))
        for centre in centres:
            for _ in range(per_cell):
                bearing = rng.uniform(0, 2 * math.pi)
                # Gaussian-ish radial fall-off concentrates flashes in the core.
                distance = abs(rng.gauss(0, centre["radius_km"] / 2.0))
                d_lat = (distance * math.cos(bearing)) * _DEG_PER_KM
                d_lon = (distance * math.sin(bearing)) * _DEG_PER_KM / max(
                    0.2, math.cos(math.radians(centre["lat"]))
                )

                lat = centre["lat"] + d_lat
                lon = centre["lon"] + d_lon
                if not _in_domain(lat, lon):
                    continue

                age_s = rng.uniform(0, window_minutes * 60)
                # Roughly 1 in 4 total flashes reaches ground in mature cells.
                is_cg = rng.random() < 0.25

                strikes.append(
                    {
                        "lat": round(lat, 4),
                        "lon": round(lon, 4),
                        "time": (now - timedelta(seconds=age_s)).isoformat(),
                        "age_s": round(age_s, 1),
                        "polarity": -1 if rng.random() < 0.9 else 1,
                        "type": "CG" if is_cg else "IC",
                        "intensity": round(intensity, 3),
                        "region": node["region"],
                        "nearest_node": node["name"],
                        "source": "LIVE-DERIVED",
                        "provider": "Open-Meteo convective analysis",
                    }
                )

    strikes.sort(key=lambda s: s["age_s"])
    return strikes


def get_lightning_field(window_minutes: int = _STRIKE_WINDOW_MIN) -> Dict[str, Any]:
    """
    Return the best available lightning field for the globe.

    Prefers measured LDN strikes; falls back to the derived field when the
    detection network is unreachable. The response always states which.
    """
    measured = _ldn_client.snapshot()
    convective = fetch_live_convective()

    if _ldn_client.connected and measured:
        strikes = measured
        status = "LIVE"
        note = "Measured cloud-to-ground and intra-cloud geolocations from the Blitzortung detection network."
    else:
        strikes = derive_strike_field(convective, window_minutes)
        status = "LIVE-DERIVED"
        note = (
            "Lightning detection network unreachable. Flash field derived from live "
            "CAPE, Lifted Index and observed WMO weather codes — physically weighted, "
            "not measured."
        )

    cg = sum(1 for s in strikes if s["type"] == "CG")
    return {
        "status": status,
        "note": note,
        "window_minutes": window_minutes,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "strike_count": len(strikes),
        "cg_count": cg,
        "ic_count": len(strikes) - cg,
        "flash_rate_per_min": round(len(strikes) / max(1, window_minutes), 1),
        "ldn": ldn_status(),
        "convective_status": convective.get("status"),
        "strikes": strikes,
    }


def get_domain_summary() -> Dict[str, Any]:
    """Headline figures for the globe's status strip."""
    convective = fetch_live_convective()
    nodes = convective.get("nodes", [])
    field = get_lightning_field()

    if nodes:
        hottest = max(nodes, key=lambda n: n["intensity"])
        max_cape = max(n["cape_j_kg"] for n in nodes)
        min_li = min(n["lifted_index_c"] for n in nodes)
    else:
        hottest, max_cape, min_li = None, 0.0, 0.0

    severity_counts: Dict[str, int] = {}
    for node in nodes:
        severity_counts[node["instability"]] = severity_counts.get(node["instability"], 0) + 1

    return {
        "convective_status": convective.get("status"),
        "lightning_status": field["status"],
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "nodes_monitored": len(nodes),
        "active_thunderstorms": convective.get("active_thunderstorm_count", 0),
        "strike_count_30min": field["strike_count"],
        "flash_rate_per_min": field["flash_rate_per_min"],
        "max_cape_j_kg": max_cape,
        "min_lifted_index_c": min_li,
        "severity_distribution": severity_counts,
        "most_unstable": (
            {
                "name": hottest["name"],
                "region": hottest["region"],
                "cape_j_kg": hottest["cape_j_kg"],
                "instability": hottest["instability"],
                "intensity": hottest["intensity"],
            }
            if hottest
            else None
        ),
    }
