/**
 * Plain-English Weather Interpreter for AeroCast-Now.
 *
 * Converts complex meteorological parameters (dBZ, VIL, CAPE, LI, SCIT, 2-sigma jump)
 * into intuitive, friendly, actionable explanations for ordinary citizens,
 * farmers, students, and emergency responders.
 */

export type ThreatLevel = 'SAFE' | 'WATCH' | 'WARNING' | 'DANGER';

export interface ThreatAssessment {
  level: ThreatLevel;
  badgeText: string;
  headline: string;
  subhead: string;
  colorHex: string;
  bgRgba: string;
  safetyActions: string[];
}

export interface CityPreset {
  id: string;
  name: string;
  state: string;
  lat: number;
  lng: number;
  stationName: string;
  dwrRadarName: string;
  /**
   * Which side of the marker the name sits on. Defaults to the right; set to
   * 'left' where a neighbour would otherwise collide (Bengaluru sits almost due
   * west of Chennai at the same latitude).
   */
  labelSide?: 'left' | 'right';
}

export const MAJOR_INDIAN_CITIES: CityPreset[] = [
  { id: 'chennai', name: 'Chennai', state: 'Tamil Nadu', lat: 13.0827, lng: 80.2707, stationName: 'Chennai DWR (Sriharikota/Port)', dwrRadarName: 'Chennai Doppler Radar' },
  { id: 'bengaluru', name: 'Bengaluru', state: 'Karnataka', lat: 12.9716, lng: 77.5946, stationName: 'Bengaluru DWR', dwrRadarName: 'Bengaluru Radar', labelSide: 'left' },
  { id: 'mumbai', name: 'Mumbai', state: 'Maharashtra', lat: 19.0760, lng: 72.8777, stationName: 'Mumbai DWR (Colaba)', dwrRadarName: 'Mumbai DWR' },
  { id: 'delhi', name: 'Delhi NCR', state: 'Delhi', lat: 28.6139, lng: 77.2090, stationName: 'Delhi DWR (Mausam Bhavan)', dwrRadarName: 'Mausam Bhavan DWR' },
  { id: 'kolkata', name: 'Kolkata', state: 'West Bengal', lat: 22.5726, lng: 88.3639, stationName: 'Kolkata DWR', dwrRadarName: 'Kolkata DWR' },
  { id: 'hyderabad', name: 'Hyderabad', state: 'Telangana', lat: 17.3850, lng: 78.4867, stationName: 'Hyderabad DWR', dwrRadarName: 'Hyderabad DWR' },
  { id: 'ahmedabad', name: 'Ahmedabad', state: 'Gujarat', lat: 23.0225, lng: 72.5714, stationName: 'Jaipur DWR', dwrRadarName: 'Western DWR', labelSide: 'left' },
  { id: 'kochi', name: 'Kochi', state: 'Kerala', lat: 9.9312, lng: 76.2673, stationName: 'Kochi DWR', dwrRadarName: 'Kochi DWR' },
  { id: 'guwahati', name: 'Guwahati', state: 'Assam', lat: 26.1445, lng: 91.7362, stationName: 'Guwahati DWR', dwrRadarName: 'Guwahati DWR' },
  { id: 'bhubaneswar', name: 'Bhubaneswar', state: 'Odisha', lat: 20.2961, lng: 85.8245, stationName: 'Bhubaneswar DWR', dwrRadarName: 'Bhubaneswar DWR' },
  { id: 'patna', name: 'Patna', state: 'Bihar', lat: 25.5941, lng: 85.1376, stationName: 'Patna DWR', dwrRadarName: 'Patna DWR' },
  { id: 'jaipur', name: 'Jaipur', state: 'Rajasthan', lat: 26.9124, lng: 75.7873, stationName: 'Jaipur DWR', dwrRadarName: 'Jaipur DWR', labelSide: 'left' },
];

/**
 * Evaluates the overall atmospheric situation into a simple 4-tier alert status.
 */
export function assessThunderstormThreat(
  hasJump: boolean,
  activeCellsCount: number,
  maxDbz: number,
  strikeCount30m: number,
): ThreatAssessment {
  if (hasJump || maxDbz >= 52 || strikeCount30m > 1200) {
    return {
      level: 'DANGER',
      badgeText: '🔴 EXTREME DANGER',
      headline: 'Violent Thunderstorm & Lightning Surge Active',
      subhead: 'Severe lightning, damaging winds, and possible hail arriving in 15–45 minutes.',
      colorHex: '#ef4444',
      bgRgba: 'rgba(239, 68, 68, 0.15)',
      safetyActions: [
        'Seek immediate shelter inside a sturdy enclosed building or hardtop vehicle.',
        'Unplug sensitive electronics and avoid contact with plumbing or wired phones.',
        'Never take shelter under tall trees, metal poles, or open verandas.',
        'Stay indoors for at least 30 minutes after the last sound of thunder.',
      ],
    };
  }

  if (activeCellsCount > 0 || maxDbz >= 40 || strikeCount30m > 400) {
    return {
      level: 'WARNING',
      badgeText: '🟠 SEVERE WARNING',
      headline: 'Thunderstorms and Frequent Lightning Nearby',
      subhead: 'Heavy rainfall and cloud-to-ground lightning occurring in the region.',
      colorHex: '#f97316',
      bgRgba: 'rgba(249, 115, 22, 0.15)',
      safetyActions: [
        'Avoid open sports grounds, lakes, and farming fields.',
        'Drive with extreme caution and keep your vehicle headlights on.',
        'Keep smartphones charged in case of local power grid tripping.',
      ],
    };
  }

  if (maxDbz >= 28 || strikeCount30m > 50) {
    return {
      level: 'WATCH',
      badgeText: '🟡 THUNDERSTORM WATCH',
      headline: 'Rain Clouds Developing — Watch the Skies',
      subhead: 'Moderate rain showers with isolated thunder possible over the next hour.',
      colorHex: '#eab308',
      bgRgba: 'rgba(234, 179, 8, 0.12)',
      safetyActions: [
        'Keep an umbrella or raincoat handy before heading outdoors.',
        'Check back for updates if heading out for travel or outdoor events.',
      ],
    };
  }

  return {
    level: 'SAFE',
    badgeText: '🟢 CALM & SAFE',
    headline: 'No Severe Thunderstorms Detected',
    subhead: 'Atmospheric conditions are stable. Low likelihood of convective storms.',
    colorHex: '#10b981',
    bgRgba: 'rgba(16, 185, 129, 0.12)',
    safetyActions: [
      'Normal outdoor activities can proceed safely.',
      'AeroCast AI continues monitoring real-time satellite and radar feeds.',
    ],
  };
}

/**
 * Translates radar reflectivity (dBZ) into ordinary rainfall descriptions.
 */
export function interpretRadarDbz(dbz: number): { label: string; description: string; color: string } {
  if (dbz >= 60) return { label: 'Violent Storm & Hail', description: 'Destructive cloud core with possible hailstones', color: '#9333ea' };
  if (dbz >= 50) return { label: 'Torrential Downpour', description: 'Intense blinding rain with violent thunder', color: '#ef4444' };
  if (dbz >= 40) return { label: 'Heavy Thunderstorm', description: 'Heavy pouring rain with frequent lightning flashes', color: '#f97316' };
  if (dbz >= 30) return { label: 'Moderate Rain', description: 'Standard rainfall; streets may become slick', color: '#eab308' };
  if (dbz >= 20) return { label: 'Light Passing Showers', description: 'Mild drizzle or light rain showers', color: '#38bdf8' };
  return { label: 'Clear / Overcast', description: 'No significant rain detected', color: '#64748b' };
}

/**
 * Translates CAPE (Convective Available Potential Energy) into simple terms.
 */
export function interpretCape(capeJkg: number): { label: string; simpleExplanation: string } {
  if (capeJkg >= 3000) return { label: 'Explosive Energy', simpleExplanation: 'Extreme heat & moisture acting as rocket fuel for storms.' };
  if (capeJkg >= 2000) return { label: 'High Energy', simpleExplanation: 'Atmosphere is charged; thunderstorm clouds can erupt quickly.' };
  if (capeJkg >= 1000) return { label: 'Moderate Energy', simpleExplanation: 'Scattered storm clouds possible in the afternoon/evening.' };
  return { label: 'Stable', simpleExplanation: 'Air is calm; storms are unlikely to develop.' };
}
