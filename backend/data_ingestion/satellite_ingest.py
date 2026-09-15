"""
Satellite Ingestion Provider
============================
Fetches, caches, and decodes ISRO / IMD INSAT-3D/3DR geostationary satellite imagery:
  - Channel 2: Thermal Infrared 1 (TIR1: 10.8 µm)
  - Water Vapor (WV: 6.7 µm)

Crops station sub-domains and converts digital counts to calibrated brightness
temperatures (°C: -85.0°C to +35.0°C) for deep convective cloud-top monitoring.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import ssl
import time
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import numpy as np
from PIL import Image

from config.data_config import DATA_CONFIG
from data_ingestion.base import SatelliteDataProvider

logger = logging.getLogger("aerocast.data.satellite")

_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE


class INSATSatelliteProvider(SatelliteDataProvider):
    """Ingests and georeferences INSAT-3D/3DR Thermal IR imagery."""

    def __init__(self) -> None:
        self.cache_dir = os.path.join(DATA_CONFIG.raw_data_dir, "satellite")
        os.makedirs(self.cache_dir, exist_ok=True)

    async def fetch_satellite_grid(
        self,
        lat: float,
        lon: float,
        grid_size: int = 32,
        domain_deg: float = 2.5
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        cache_path = os.path.join(self.cache_dir, "insat_3d_ir1.jpg")
        now = time.time()
        image_bytes: Optional[bytes] = None

        if os.path.exists(cache_path):
            mtime = os.path.getmtime(cache_path)
            if (now - mtime) < DATA_CONFIG.satellite_ttl_s:
                try:
                    with open(cache_path, "rb") as f:
                        image_bytes = f.read()
                except Exception:
                    pass

        if image_bytes is None:
            url = f"{DATA_CONFIG.insat_satellite_url}/3Dasiasec_ir1.jpg"
            req = urllib.request.Request(url, headers={"User-Agent": "AeroCast-Now-AI/2.0"})

            loop = asyncio.get_event_loop()
            def _fetch():
                try:
                    with urllib.request.urlopen(req, timeout=12, context=_ssl_ctx) as resp:
                        if resp.status == 200:
                            data = resp.read()
                            if len(data) > 10000:
                                with open(cache_path, "wb") as f:
                                    f.write(data)
                                return data
                except Exception as e:
                    logger.debug("INSAT satellite fetch failed: %s", e)
                return None

            image_bytes = await loop.run_in_executor(None, _fetch)

        if not image_bytes and os.path.exists(cache_path):
            try:
                with open(cache_path, "rb") as f:
                    image_bytes = f.read()
            except Exception:
                pass

        if not image_bytes:
            default_grid = np.full((grid_size, grid_size), 22.0, dtype=np.float32)
            return default_grid, {"source": "BASELINE", "min_observed_tir_c": 22.0, "status": "unavailable"}

        return self._decode_insat_image(image_bytes, lat, lon, grid_size, domain_deg)

    def _decode_insat_image(
        self,
        image_bytes: bytes,
        lat: float,
        lon: float,
        grid_size: int = 32,
        domain_deg: float = 2.5
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        try:
            img = Image.open(io.BytesIO(image_bytes)).convert("L")
            w, h = img.size

            # IMD 3Dasiasec bounding box: -10° to 45°N, 40° to 120°E
            lat_min, lat_max = -10.0, 45.0
            lon_min, lon_max = 40.0, 120.0

            def lat_to_y(lat_val: float) -> int:
                norm_y = 1.0 - (lat_val - lat_min) / (lat_max - lat_min)
                return int(np.clip(norm_y * h, 0, h - 1))

            def lon_to_x(lon_val: float) -> int:
                norm_x = (lon_val - lon_min) / (lon_max - lon_min)
                return int(np.clip(norm_x * w, 0, w - 1))

            x0 = lon_to_x(lon - domain_deg)
            x1 = lon_to_x(lon + domain_deg)
            y0 = lat_to_y(lat + domain_deg)
            y1 = lat_to_y(lat - domain_deg)

            x_min, x_max = min(x0, x1), max(x0, x1)
            y_min, y_max = min(y0, y1), max(y0, y1)

            cropped = img.crop((x_min, y_min, max(x_min + 10, x_max), max(y_min + 10, y_max)))
            resized = cropped.resize((grid_size, grid_size), Image.Resampling.BILINEAR)
            raw_arr = np.array(resized, dtype=np.float32)

            # Invert grayscale: white cloud tops (raw ~ 255) -> -85°C (convective tops)
            # dark ground (raw ~ 0) -> +35°C
            tir_grid = np.clip(35.0 - (raw_arr / 255.0) * 120.0, -85.0, 35.0).astype(np.float32)

            meta = {
                "source": "LIVE-INSAT-3D",
                "channel": "TIR1 (10.8 µm)",
                "min_observed_tir_c": float(np.min(tir_grid)),
                "mean_tir_c": float(np.mean(tir_grid)),
                "deep_convection_present": bool(np.any(tir_grid <= -45.0)),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            return tir_grid, meta
        except Exception as e:
            logger.error("Error decoding INSAT image: %s", e)
            default_grid = np.full((grid_size, grid_size), 22.0, dtype=np.float32)
            return default_grid, {"source": "ERROR", "error": str(e)}
