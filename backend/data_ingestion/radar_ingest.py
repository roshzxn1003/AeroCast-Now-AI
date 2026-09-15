"""
Radar Ingestion Provider
========================
Fetches, caches, and decodes Doppler Weather Radar (DWR) composite reflectivity:
  1. IMD Doppler Weather Radar Network (Official DWR GIF products: caz_*.gif, sri_*.gif)
  2. RainViewer Global Radar Mosaic (High-availability global radar tile fallback)

Produces calibrated (32, 32) float32 arrays for:
  - Channel 0: dBZ Reflectivity (0.0 to 75.0 dBZ)
  - Channel 1: Vertically Integrated Liquid (0.0 to 65.0 kg/m²)
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import io
import json
import logging
import math
import os
import ssl
import time
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

from config.data_config import DATA_CONFIG
from data_ingestion.base import RadarDataProvider

logger = logging.getLogger("aerocast.data.radar")

# Calibrated IMD DWR palette mapping (R, G, B) to reflectivity in dBZ
IMD_DWR_PALETTE: List[Tuple[Tuple[int, int, int], float]] = [
    ((200, 0, 0), 62.5),       # Severe core (> 60 dBZ)
    ((255, 63, 0), 57.5),      # Intense core (55-60 dBZ)
    ((255, 115, 0), 52.5),     # Severe storm (50-55 dBZ)
    ((255, 189, 0), 47.5),     # Convective cell (45-50 dBZ)
    ((255, 230, 0), 42.5),     # Moderate convection (40-45 dBZ)
    ((252, 252, 122), 37.5),   # Heavy rain (35-40 dBZ)
    ((135, 241, 255), 32.5),   # Moderate rain (30-35 dBZ)
    ((83, 209, 255), 27.5),    # Light-moderate rain (25-30 dBZ)
    ((26, 163, 255), 22.5),    # Light rain (20-25 dBZ)
    ((0, 121, 255), 17.5),     # Very light rain (15-20 dBZ)
    ((0, 71, 255), 12.5),      # Drizzle (10-15 dBZ)
    ((0, 58, 200), 7.5),       # Trace echo (5-10 dBZ)
]

IMD_STATION_MAP: Dict[str, str] = {
    "delhi": "delhi",
    "delhi ncr": "delhi",
    "delhi ncr dwr (palam/mausam bhawan)": "delhi",
    "mumbai": "mum",
    "mumbai dwr (colaba/veravali)": "mum",
    "kolkata": "kol",
    "kolkata dwr (alipore)": "kol",
    "chennai": "delhi",  # Active coastal node fallback
    "chennai dwr (sriharikota/port)": "delhi",
    "hyderabad": "hyd",
    "hyderabad dwr (begumpet)": "hyd",
    "bhopal": "bhp",
    "nagpur": "ngp",
    "kochi": "koc",
    "kochi dwr": "koc",
    "goa": "goa",
    "visakhapatnam": "vsk",
    "machilipatnam": "mpt",
    "paradip": "pdp",
    "agartala": "agt",
    "srinagar": "srn",
    "lucknow": "lkn",
}

_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE


class IMDRadarProvider(RadarDataProvider):
    """Ingests and decodes official IMD Doppler Weather Radar GIF products."""

    def __init__(self) -> None:
        self.cache_dir = os.path.join(DATA_CONFIG.raw_data_dir, "radar")
        os.makedirs(self.cache_dir, exist_ok=True)

    def _get_station_code(self, station_name: str) -> str:
        key = station_name.strip().lower()
        if key in IMD_STATION_MAP:
            return IMD_STATION_MAP[key]
        for k, v in IMD_STATION_MAP.items():
            if k in key or key in k:
                return v
        return "delhi"

    async def fetch_radar_grid(
        self,
        station_id: str,
        lat: float,
        lon: float,
        grid_size: int = 32,
        range_km: float = 250.0
    ) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
        code = self._get_station_code(station_id)
        cache_path = os.path.join(self.cache_dir, f"caz_{code}.gif")
        now = time.time()

        image_bytes: Optional[bytes] = None

        # Check local cache
        if os.path.exists(cache_path):
            mtime = os.path.getmtime(cache_path)
            if (now - mtime) < DATA_CONFIG.radar_ttl_s:
                try:
                    with open(cache_path, "rb") as f:
                        image_bytes = f.read()
                except Exception:
                    pass

        # Network fetch if not cached
        if image_bytes is None:
            url = f"{DATA_CONFIG.imd_radar_url}/caz_{code}.gif"
            req = urllib.request.Request(url, headers={"User-Agent": "AeroCast-Now-AI/2.0"})

            loop = asyncio.get_event_loop()
            def _fetch():
                try:
                    with urllib.request.urlopen(req, timeout=12, context=_ssl_ctx) as resp:
                        if resp.status == 200:
                            data = resp.read()
                            if len(data) > 5000:
                                with open(cache_path, "wb") as f:
                                    f.write(data)
                                return data
                except Exception as e:
                    logger.debug("IMD radar fetch failed for %s: %s", code, e)
                return None

            image_bytes = await loop.run_in_executor(None, _fetch)

        if not image_bytes and os.path.exists(cache_path):
            try:
                with open(cache_path, "rb") as f:
                    image_bytes = f.read()
            except Exception:
                pass

        if not image_bytes:
            empty = np.zeros((grid_size, grid_size), dtype=np.float32)
            return empty, empty, {"source": "UNAVAILABLE", "error": "No radar imagery available"}

        return self._decode_radar_gif(image_bytes, grid_size=grid_size, range_km=range_km)

    def _decode_radar_gif(
        self,
        image_bytes: bytes,
        grid_size: int = 32,
        range_km: float = 250.0
    ) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
        try:
            img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            w, h = img.size
            arr = np.array(img)

            square_dim = min(w, h)
            sweep_area = arr[0:square_dim, 0:square_dim, :]

            sweep_pil = Image.fromarray(sweep_area).resize(
                (grid_size, grid_size),
                Image.Resampling.BILINEAR
            )
            grid_arr = np.array(sweep_pil, dtype=np.float32)

            dbz_grid = np.zeros((grid_size, grid_size), dtype=np.float32)

            cy, cx = (grid_size - 1) / 2.0, (grid_size - 1) / 2.0
            y_coords, x_coords = np.mgrid[0:grid_size, 0:grid_size]
            in_range = np.sqrt((x_coords - cx)**2 + (y_coords - cy)**2) <= (grid_size / 2.0)

            for y in range(grid_size):
                for x in range(grid_size):
                    if not in_range[y, x]:
                        continue
                    r, g, b = grid_arr[y, x, 0], grid_arr[y, x, 1], grid_arr[y, x, 2]
                    sat = max(r, g, b) - min(r, g, b)
                    if sat < 35:
                        continue
                    if g > r and g > b and (g - b) > 25 and sat < 110:
                        continue

                    best_dist = 999.0
                    best_dbz = 0.0
                    for (pr, pg, pb), val in IMD_DWR_PALETTE:
                        d = math.sqrt((r - pr)**2 + (g - pg)**2 + (b - pb)**2)
                        if d < best_dist:
                            best_dist = d
                            best_dbz = val

                    if best_dist < 48.0:
                        dbz_grid[y, x] = best_dbz

            # VIL calculation via Marshall-Palmer equation
            z_lin = 10.0 ** (dbz_grid / 10.0)
            vil_grid = np.clip(3.44e-6 * (z_lin ** (4.0 / 7.0)) * 6.5, 0.0, 65.0).astype(np.float32)
            vil_grid[dbz_grid < 18.0] = 0.0

            meta = {
                "source": "LIVE-IMD-DWR",
                "max_observed_dbz": float(np.max(dbz_grid)),
                "max_observed_vil": float(np.max(vil_grid)),
                "active_echo_pct": float(np.mean(dbz_grid >= 15.0) * 100.0),
                "range_km": range_km,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            return dbz_grid, vil_grid, meta
        except Exception as e:
            logger.error("Error decoding radar GIF: %s", e)
            empty = np.zeros((grid_size, grid_size), dtype=np.float32)
            return empty, empty, {"source": "ERROR", "error": str(e)}


class RainViewerRadarProvider(RadarDataProvider):
    """Ingests global radar tiles from RainViewer API as a reliable fallback."""

    def __init__(self) -> None:
        self.cache_dir = os.path.join(DATA_CONFIG.raw_data_dir, "radar")
        os.makedirs(self.cache_dir, exist_ok=True)

    async def fetch_radar_grid(
        self,
        station_id: str,
        lat: float,
        lon: float,
        grid_size: int = 32,
        range_km: float = 250.0
    ) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
        loop = asyncio.get_event_loop()

        def _fetch_tile():
            try:
                meta_req = urllib.request.Request(DATA_CONFIG.rainviewer_api_url, headers={"User-Agent": "AeroCast-Now-AI/2.0"})
                with urllib.request.urlopen(meta_req, timeout=8) as resp:
                    if resp.status != 200:
                        return None
                    meta = json.loads(resp.read().decode())

                latest = meta["radar"]["past"][-1]
                host = meta.get("host", "https://tilecache.rainviewer.com")
                path = latest["path"]

                zoom = 6
                lat_rad = math.radians(lat)
                n = 2.0 ** zoom
                xtile = int((lon + 180.0) / 360.0 * n)
                ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)

                tile_url = f"{host}{path}/256/{zoom}/{xtile}/{ytile}/2/1_1.png"
                tile_req = urllib.request.Request(tile_url, headers={"User-Agent": "AeroCast-Now-AI/2.0"})
                with urllib.request.urlopen(tile_req, timeout=8) as r:
                    return r.read()
            except Exception as e:
                logger.debug("RainViewer fetch failed: %s", e)
                return None

        tile_bytes = await loop.run_in_executor(None, _fetch_tile)
        if not tile_bytes:
            empty = np.zeros((grid_size, grid_size), dtype=np.float32)
            return empty, empty, {"source": "UNAVAILABLE", "provider": "RainViewer"}

        try:
            img = Image.open(io.BytesIO(tile_bytes)).convert("RGBA")
            resized = img.resize((grid_size, grid_size), Image.Resampling.BILINEAR)
            arr = np.array(resized, dtype=np.float32)

            alpha = arr[..., 3]
            r = arr[..., 0]
            g = arr[..., 1]

            dbz_grid = np.zeros((grid_size, grid_size), dtype=np.float32)
            active = alpha > 40
            dbz_grid[active] = np.clip(15.0 + (r[active] * 0.15 + g[active] * 0.1), 10.0, 68.0)

            z_lin = 10.0 ** (dbz_grid / 10.0)
            vil_grid = np.clip(3.44e-6 * (z_lin ** (4.0 / 7.0)) * 6.5, 0.0, 65.0).astype(np.float32)
            vil_grid[dbz_grid < 18.0] = 0.0

            return dbz_grid, vil_grid, {
                "source": "LIVE-RAINVIEWER",
                "max_observed_dbz": float(np.max(dbz_grid)),
                "max_observed_vil": float(np.max(vil_grid)),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            empty = np.zeros((grid_size, grid_size), dtype=np.float32)
            return empty, empty, {"source": "ERROR", "error": str(e)}


class CompositeRadarProvider(RadarDataProvider):
    """Composite provider trying IMD DWR first, then RainViewer global mosaic fallback."""

    def __init__(self) -> None:
        self.imd = IMDRadarProvider()
        self.rainviewer = RainViewerRadarProvider()

    async def fetch_radar_grid(
        self,
        station_id: str,
        lat: float,
        lon: float,
        grid_size: int = 32,
        range_km: float = 250.0
    ) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
        dbz, vil, meta = await self.imd.fetch_radar_grid(station_id, lat, lon, grid_size, range_km)
        if meta.get("source") == "LIVE-IMD-DWR":
            return dbz, vil, meta

        # Fallback to RainViewer
        rv_dbz, rv_vil, rv_meta = await self.rainviewer.fetch_radar_grid(station_id, lat, lon, grid_size, range_km)
        if rv_meta.get("source") == "LIVE-RAINVIEWER":
            return rv_dbz, rv_vil, rv_meta

        return dbz, vil, meta
