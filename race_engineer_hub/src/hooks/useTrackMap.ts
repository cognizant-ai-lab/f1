import { useEffect, useRef, useState } from "react";
import { TRACK_OUTLINES } from "@/data/trackOutlines";

export interface CarPosition {
  x: number;
  z: number;
  /** Heading angle in radians (direction of travel along the track). */
  heading: number;
  position: number;
  lapDistance: number;
  active: boolean;
  /** 3-letter driver abbreviation (e.g. "VER", "HAM"). Empty if unavailable. */
  abbreviation: string;
  /** Team abbreviation (e.g. "RBR", "MER"). Empty if unavailable. */
  teamAbbreviation: string;
}

export interface TrackMapState {
  trackOutline: Array<{ x: number; z: number }>;
  cars: CarPosition[];
  playerIndex: number;
  outlineComplete: boolean;
  trackName: string;
}

const WS_URL = "ws://localhost:8765";
const RECONNECT_INTERVAL_MS = 2000;
/** Minimum squared distance (metres) between consecutive dynamic outline points. */
const MIN_DIST_SQ = 25; // 5 m

function distSq(a: { x: number; z: number }, b: { x: number; z: number }): number {
  const dx = a.x - b.x;
  const dz = a.z - b.z;
  return dx * dx + dz * dz;
}

// ---------------------------------------------------------------------------
// Static outline helpers
// ---------------------------------------------------------------------------

interface StaticTrackData {
  points: Array<{ x: number; z: number }>;
  /** Cumulative arc-length distance at each point. */
  distances: number[];
  totalLength: number;
}

/** Load and precompute cumulative distances for a static track outline. */
function loadStaticTrack(trackName: string): StaticTrackData | null {
  const coords = TRACK_OUTLINES[trackName];
  if (!coords) return null;

  // Negate Z to mirror top-down view
  const points = coords.map(([x, z]) => ({ x, z: -z }));
  const distances = [0];
  let total = 0;
  for (let i = 1; i < points.length; i++) {
    const dx = points[i].x - points[i - 1].x;
    const dz = points[i].z - points[i - 1].z;
    total += Math.sqrt(dx * dx + dz * dz);
    distances.push(total);
  }
  return { points, distances, totalLength: total };
}

/** Find the point on the static outline at a given normalised position (0-1). */
function staticPointAtNorm(track: StaticTrackData, norm: number): { x: number; z: number } {
  // Clamp to [0, 1)
  const n = ((norm % 1) + 1) % 1;
  const targetDist = n * track.totalLength;
  // Binary search for the segment containing targetDist
  let lo = 0;
  let hi = track.distances.length - 1;
  while (lo < hi - 1) {
    const mid = (lo + hi) >> 1;
    if (track.distances[mid] <= targetDist) lo = mid;
    else hi = mid;
  }
  // Interpolate between lo and hi
  const segLen = track.distances[hi] - track.distances[lo];
  const t = segLen > 0 ? (targetDist - track.distances[lo]) / segLen : 0;
  return {
    x: track.points[lo].x + t * (track.points[hi].x - track.points[lo].x),
    z: track.points[lo].z + t * (track.points[hi].z - track.points[lo].z),
  };
}

/** Compute the tangent direction (heading) at a normalised position on the track. */
function trackHeadingAtNorm(track: StaticTrackData, norm: number): number {
  const epsilon = 0.002; // small step for finite difference
  const a = staticPointAtNorm(track, norm - epsilon);
  const b = staticPointAtNorm(track, norm + epsilon);
  return Math.atan2(b.z - a.z, b.x - a.x);
}

/**
 * Map car positions onto the static track outline using normalised lap distance.
 * Falls back to raw world coordinates when static data is unavailable.
 */
function mapCarsToOutline(
  cars: CarPosition[],
  staticTrack: StaticTrackData | null,
  trackLength: number,
): CarPosition[] {
  if (!staticTrack || trackLength <= 0) return cars;

  return cars.map((car) => {
    if (!car.active) return car;
    const norm = car.lapDistance / trackLength;
    const pt = staticPointAtNorm(staticTrack, norm);
    const heading = trackHeadingAtNorm(staticTrack, norm);
    return { ...car, x: pt.x, z: pt.z, heading };
  });
}

export function useTrackMap(): TrackMapState | null {
  const [state, setState] = useState<TrackMapState | null>(null);

  // Dynamic outline built from the player's live positions (fallback when no static data)
  const dynamicOutlineRef = useRef<Array<{ x: number; z: number }>>([]);
  const dynamicCompleteRef = useRef(false);
  const maxLapDistRef = useRef(0);

  const staticTrackRef = useRef<StaticTrackData | null>(null);

  const prevSessionTimeRef = useRef(0);
  const prevTrackNameRef = useRef("");

  useEffect(() => {
    let unmounted = false;
    let ws: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout>;

    function connect() {
      if (unmounted) return;
      ws = new WebSocket(WS_URL);

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          const trackMap = msg.trackMap;
          const sessionTime: number = msg.sessionTime ?? 0;
          const trackName: string = msg.session?.trackName ?? "";
          const trackLength: number = msg.session?.trackLength ?? 0;

          // Session reset — clear dynamic outline
          if (sessionTime < prevSessionTimeRef.current) {
            dynamicOutlineRef.current = [];
            dynamicCompleteRef.current = false;
            maxLapDistRef.current = 0;
          }
          prevSessionTimeRef.current = sessionTime;

          // Track change — reload static data, reset dynamic outline
          if (trackName !== prevTrackNameRef.current) {
            prevTrackNameRef.current = trackName;
            dynamicOutlineRef.current = [];
            dynamicCompleteRef.current = false;
            maxLapDistRef.current = 0;
            staticTrackRef.current = trackName ? loadStaticTrack(trackName) : null;
          }

          const playerIndex: number = trackMap?.playerIndex ?? 0;
          const rawCars: CarPosition[] = trackMap?.cars ?? [];
          const player = rawCars[playerIndex];

          // Accumulate dynamic outline from player position (fallback for unknown tracks)
          if (player && !dynamicCompleteRef.current && (player.x !== 0 || player.z !== 0)) {
            const dynOutline = dynamicOutlineRef.current;
            const last = dynOutline.length > 0 ? dynOutline[dynOutline.length - 1] : null;
            if (!last || distSq(last, player) > MIN_DIST_SQ) {
              dynOutline.push({ x: player.x, z: player.z });
            }
            const ld = player.lapDistance ?? 0;
            if (maxLapDistRef.current > 500 && ld < maxLapDistRef.current - 500) {
              dynamicCompleteRef.current = true;
            }
            if (ld > maxLapDistRef.current) {
              maxLapDistRef.current = ld;
            }
          }

          const staticTrack = staticTrackRef.current;

          // Choose outline: prefer static, fall back to dynamic
          let outline: Array<{ x: number; z: number }>;
          let outlineComplete: boolean;

          if (staticTrack) {
            outline = staticTrack.points;
            outlineComplete = true;
          } else if (dynamicCompleteRef.current || dynamicOutlineRef.current.length >= 20) {
            outline = dynamicOutlineRef.current;
            outlineComplete = dynamicCompleteRef.current;
          } else {
            outline = dynamicOutlineRef.current;
            outlineComplete = false;
          }

          // Map car positions onto the outline via normalised lap distance
          const cars = mapCarsToOutline(rawCars, staticTrack, trackLength);

          setState({
            trackOutline: outline,
            cars,
            playerIndex,
            outlineComplete,
            trackName,
          });
        } catch {
          // ignore malformed messages
        }
      };

      ws.onclose = () => {
        if (!unmounted) {
          reconnectTimer = setTimeout(connect, RECONNECT_INTERVAL_MS);
        }
      };
      ws.onerror = () => ws?.close();
    }

    connect();

    return () => {
      unmounted = true;
      clearTimeout(reconnectTimer);
      ws?.close();
    };
  }, []);

  return state;
}
