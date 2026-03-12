/** Track geometry utilities: smooth path generation and turn detection. */

type Point = { x: number; z: number };

// ---------------------------------------------------------------------------
// Catmull-Rom spline smoothing
// ---------------------------------------------------------------------------

/** Convert track outline points to a smooth SVG path using Catmull-Rom splines. */
export function smoothTrackPath(points: Point[], closed: boolean): string {
  const n = points.length;
  if (n < 3) return points.map((p, i) => `${i === 0 ? "M" : "L"}${p.x},${p.z}`).join(" ");

  const get = (i: number): Point => {
    if (closed) return points[((i % n) + n) % n];
    return points[Math.max(0, Math.min(n - 1, i))];
  };

  const parts: string[] = [`M${points[0].x},${points[0].z}`];
  const limit = closed ? n : n - 1;

  for (let i = 0; i < limit; i++) {
    const p0 = get(i - 1);
    const p1 = get(i);
    const p2 = get(i + 1);
    const p3 = get(i + 2);

    // Catmull-Rom to cubic Bezier control points
    const cp1x = p1.x + (p2.x - p0.x) / 6;
    const cp1z = p1.z + (p2.z - p0.z) / 6;
    const cp2x = p2.x - (p3.x - p1.x) / 6;
    const cp2z = p2.z - (p3.z - p1.z) / 6;

    parts.push(`C${cp1x},${cp1z} ${cp2x},${cp2z} ${p2.x},${p2.z}`);
  }

  if (closed) parts.push("Z");
  return parts.join(" ");
}

// ---------------------------------------------------------------------------
// Turn detection
// ---------------------------------------------------------------------------

export interface DetectedTurn {
  /** Normalised position along the track (0-1). */
  norm: number;
  /** Turn number (1-based, sequential around the lap). */
  number: number;
  /** World-coordinate position of the turn apex. */
  x: number;
  z: number;
  /** Outward normal direction (radians) for label offset. */
  normalAngle: number;
}

/** Normalise an angle to [-PI, PI]. */
function wrapAngle(a: number): number {
  while (a > Math.PI) a -= 2 * Math.PI;
  while (a < -Math.PI) a += 2 * Math.PI;
  return a;
}

/**
 * Detect turns in a track outline based on curvature analysis.
 *
 * Algorithm:
 * 1. Compute tangent heading at each outline point.
 * 2. Measure absolute heading change over a small window (w=2 points each side).
 * 3. Derive an adaptive threshold from the curvature distribution (median + 0.5 * IQR-like spread).
 * 4. Find local curvature peaks above the threshold.
 * 5. Cluster nearby peaks (within 2.5% of track length) into single turns.
 * 6. Number turns sequentially around the lap.
 */
export function detectTurns(points: Point[], closed: boolean): DetectedTurn[] {
  const n = points.length;
  if (n < 20) return [];

  // Cumulative arc-length distances
  const dist = [0];
  let totalDist = 0;
  for (let i = 1; i < n; i++) {
    const dx = points[i].x - points[i - 1].x;
    const dz = points[i].z - points[i - 1].z;
    totalDist += Math.sqrt(dx * dx + dz * dz);
    dist.push(totalDist);
  }
  if (closed) {
    const dx = points[0].x - points[n - 1].x;
    const dz = points[0].z - points[n - 1].z;
    totalDist += Math.sqrt(dx * dx + dz * dz);
  }

  const get = (i: number): Point => {
    if (closed) return points[((i % n) + n) % n];
    return points[Math.max(0, Math.min(n - 1, i))];
  };

  // Heading at each point (central difference)
  const headings: number[] = [];
  for (let i = 0; i < n; i++) {
    const prev = get(i - 1);
    const next = get(i + 1);
    headings.push(Math.atan2(next.z - prev.z, next.x - prev.x));
  }

  // Absolute heading change over a tight window (w=1 captures finer turns)
  const w = 1;
  const curvature: number[] = [];
  for (let i = 0; i < n; i++) {
    const lo = ((i - w + n) % n);
    const hi = ((i + w) % n);
    const dh = Math.abs(wrapAngle(headings[hi] - headings[lo]));
    curvature.push(dh);
  }

  // Adaptive threshold: median + 0.3 * (p80 - median)
  const sorted = [...curvature].sort((a, b) => a - b);
  const median = sorted[Math.floor(n * 0.5)];
  const p80 = sorted[Math.floor(n * 0.8)];
  const threshold = median + (p80 - median) * 0.3;

  // Find local maxima above threshold
  const peaks: Array<{ index: number; value: number }> = [];
  for (let i = 1; i < n - 1; i++) {
    if (
      curvature[i] > threshold &&
      curvature[i] >= curvature[i - 1] &&
      curvature[i] >= curvature[i + 1]
    ) {
      peaks.push({ index: i, value: curvature[i] });
    }
  }

  // Cluster nearby peaks (within 2% of track length), keeping the strongest
  const clusterRadius = totalDist * 0.02;
  const clusters: Array<{ bestIndex: number; bestValue: number; lastDist: number }> = [];

  for (const peak of peaks) {
    const pd = dist[peak.index];
    let merged = false;
    for (const cluster of clusters) {
      if (Math.abs(pd - cluster.lastDist) < clusterRadius) {
        if (peak.value > cluster.bestValue) {
          cluster.bestIndex = peak.index;
          cluster.bestValue = peak.value;
        }
        cluster.lastDist = Math.max(cluster.lastDist, pd);
        merged = true;
        break;
      }
    }
    if (!merged) {
      clusters.push({ bestIndex: peak.index, bestValue: peak.value, lastDist: pd });
    }
  }

  // Sort by distance along track
  clusters.sort((a, b) => dist[a.bestIndex] - dist[b.bestIndex]);

  // Build result with outward normal for label placement
  return clusters.map((c, i) => {
    const idx = c.bestIndex;
    const tangent = headings[idx];
    // Normal perpendicular to tangent (pointing left of travel direction)
    const normalAngle = tangent - Math.PI / 2;
    return {
      norm: dist[idx] / totalDist,
      number: i + 1,
      x: points[idx].x,
      z: points[idx].z,
      normalAngle,
    };
  });
}
