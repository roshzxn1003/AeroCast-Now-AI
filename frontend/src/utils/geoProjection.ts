/**
 * Atmospheric Geographic Coordinate Projection Utilities
 * =======================================================
 * Maps between 2D Cartesian radar / neural network prediction grids (32x32)
 * and spherical geographic coordinates (Latitude, Longitude) on Earth.
 *
 * Domain: Centered at Radar Station (e.g. Chennai DWR 13.0827°N, 80.2707°E)
 * Coverage: 256 km x 256 km domain (half-domain = 128 km).
 * Pixel resolution: ~8.0 km per grid cell at 32x32.
 */

export interface GeoCoordinate {
  lat: number;
  lon: number;
}

export interface GeoBoundingBox {
  minLat: number;
  maxLat: number;
  minLon: number;
  maxLon: number;
}

const KM_PER_DEG_LAT = 111.32;

/**
 * Converts a (y, x) pixel coordinate on the (gridSize, gridSize) grid
 * to geographic (lat, lon) on Earth.
 *
 * @param y Grid row (0 = North/top, gridSize-1 = South/bottom)
 * @param x Grid column (0 = West/left, gridSize-1 = East/right)
 * @param centerLat Latitude of the domain origin (radar station)
 * @param centerLon Longitude of the domain origin (radar station)
 * @param domainRadiusKm Radius of the square bounding domain (half-width, default 128 km)
 * @param gridSize Grid dimension (default 32)
 */
export function gridPixelToGeo(
  y: number,
  x: number,
  centerLat: number,
  centerLon: number,
  domainRadiusKm: number = 128.0,
  gridSize: number = 32
): GeoCoordinate {
  const cosLat = Math.max(0.2, Math.cos((centerLat * Math.PI) / 180.0));
  const kmPerDegLon = KM_PER_DEG_LAT * cosLat;

  // Normalized offset from center: [-1.0, +1.0]
  const normX = ((x + 0.5) / gridSize) * 2.0 - 1.0;
  const normY = 1.0 - ((y + 0.5) / gridSize) * 2.0;

  const dLonKm = normX * domainRadiusKm;
  const dLatKm = normY * domainRadiusKm;

  return {
    lat: centerLat + dLatKm / KM_PER_DEG_LAT,
    lon: centerLon + dLonKm / kmPerDegLon,
  };
}

/**
 * Inverse mapping: converts geographic (lat, lon) into continuous grid pixel coordinates (y, x).
 */
export function geoToGridPixel(
  lat: number,
  lon: number,
  centerLat: number,
  centerLon: number,
  domainRadiusKm: number = 128.0,
  gridSize: number = 32
): { y: number; x: number; inBounds: boolean } {
  const cosLat = Math.max(0.2, Math.cos((centerLat * Math.PI) / 180.0));
  const kmPerDegLon = KM_PER_DEG_LAT * cosLat;

  const dLatKm = (lat - centerLat) * KM_PER_DEG_LAT;
  const dLonKm = (lon - centerLon) * kmPerDegLon;

  const normX = dLonKm / domainRadiusKm; // [-1, +1]
  const normY = dLatKm / domainRadiusKm; // [-1, +1]

  const px = ((normX + 1.0) / 2.0) * gridSize - 0.5;
  const py = ((1.0 - normY) / 2.0) * gridSize - 0.5;

  const inBounds = Math.abs(normX) <= 1.0 && Math.abs(normY) <= 1.0;

  return { y: py, x: px, inBounds };
}

/**
 * Computes geographic bounding box for the radar/model domain.
 */
export function getRadarBoundingBox(
  centerLat: number,
  centerLon: number,
  domainRadiusKm: number = 128.0
): GeoBoundingBox {
  const cosLat = Math.max(0.2, Math.cos((centerLat * Math.PI) / 180.0));
  const dLat = domainRadiusKm / KM_PER_DEG_LAT;
  const dLon = domainRadiusKm / (KM_PER_DEG_LAT * cosLat);

  return {
    minLat: centerLat - dLat,
    maxLat: centerLat + dLat,
    minLon: centerLon - dLon,
    maxLon: centerLon + dLon,
  };
}

/**
 * Standard calibrated IMD / NEXRAD Doppler Reflectivity Color Palette (dBZ).
 */
export function getDbzColor(dbz: number): string {
  if (dbz < 15.0) return 'rgba(0,0,0,0)';
  if (dbz < 20.0) return '#38bdf8'; // Cyan - trace/light rain
  if (dbz < 25.0) return '#0284c7'; // Blue - light rain
  if (dbz < 30.0) return '#10b981'; // Emerald - moderate rain
  if (dbz < 35.0) return '#84cc16'; // Lime - moderate-heavy
  if (dbz < 40.0) return '#eab308'; // Yellow - heavy showers / developing core
  if (dbz < 45.0) return '#f97316'; // Orange - convective cell
  if (dbz < 50.0) return '#ef4444'; // Red - heavy thunderstorm
  if (dbz < 55.0) return '#dc2626'; // Dark Red - severe storm / hail
  if (dbz < 60.0) return '#db2777'; // Pink/Magenta - intense supercell core
  return '#9333ea';                 // Purple - extreme tornadic supercell (> 60 dBZ)
}

/**
 * Standard Vertically Integrated Liquid (VIL) Color Palette (kg/m²).
 */
export function getVilColor(vil: number): string {
  if (vil < 3.0) return 'rgba(0,0,0,0)';
  if (vil < 10.0) return '#38bdf8';
  if (vil < 20.0) return '#10b981';
  if (vil < 30.0) return '#f59e0b';
  if (vil < 45.0) return '#ef4444';
  return '#a855f7';
}

/**
 * Formats coordinates for scientific HUD display.
 */
export function formatCoordinates(lat: number, lon: number): string {
  const latDir = lat >= 0 ? 'N' : 'S';
  const lonDir = lon >= 0 ? 'E' : 'W';
  return `${Math.abs(lat).toFixed(2)}°${latDir}, ${Math.abs(lon).toFixed(2)}°${lonDir}`;
}

/**
 * Calculates a forward projected uncertainty cone along a storm cell's motion vector.
 *
 * @param originLat Current centroid latitude
 * @param originLon Current centroid longitude
 * @param headingDeg Heading in degrees (0 = North, 90 = East)
 * @param speedKmh Forward translation speed in km/h
 * @param leadTimesMin Array of lead times in minutes (e.g. [15, 30, 45, 60])
 */
export function calculateStormTrackPoints(
  originLat: number,
  originLon: number,
  headingDeg: number,
  speedKmh: number,
  leadTimesMin: number[] = [15, 30, 45, 60]
): Array<{ lat: number; lon: number; leadTimeMin: number; uncertaintyRadiusKm: number }> {
  const rad = (headingDeg * Math.PI) / 180.0;
  const cosLat = Math.max(0.2, Math.cos((originLat * Math.PI) / 180.0));

  const track = [{ lat: originLat, lon: originLon, leadTimeMin: 0, uncertaintyRadiusKm: 3.0 }];

  leadTimesMin.forEach((leadMin) => {
    const hours = leadMin / 60.0;
    const distanceKm = speedKmh * hours;

    const dLatKm = distanceKm * Math.cos(rad);
    const dLonKm = distanceKm * Math.sin(rad);

    const lat = originLat + dLatKm / KM_PER_DEG_LAT;
    const lon = originLon + dLonKm / (KM_PER_DEG_LAT * cosLat);

    // Uncertainty expands non-linearly with forecast lead time (~4 km per 15 min)
    const uncertaintyRadiusKm = 3.0 + (leadMin / 15.0) * 4.2;

    track.push({
      lat,
      lon,
      leadTimeMin: leadMin,
      uncertaintyRadiusKm,
    });
  });

  return track;
}
