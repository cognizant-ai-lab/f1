import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Compass, Maximize, Map, Users, ZoomIn, ZoomOut } from "lucide-react";
import { useTrackMap } from "@/hooks/useTrackMap";
import { smoothTrackPath, detectTurns } from "@/utils/trackGeometry";

const ROTATION_STORAGE_KEY = "trackMap:rotations";
const ZOOM_STORAGE_KEY = "trackMap:zooms";
const PAN_STORAGE_KEY = "trackMap:pans";
const LABEL_MODE_STORAGE_KEY = "trackMap:labelMode";

type LabelMode = "driver" | "team";

function loadSavedRotation(trackName: string): number {
  try {
    const stored = localStorage.getItem(ROTATION_STORAGE_KEY);
    if (stored) {
      const map = JSON.parse(stored) as Record<string, number>;
      return map[trackName] ?? 0;
    }
  } catch { /* ignore */ }
  return 0;
}

function saveRotation(trackName: string, deg: number) {
  try {
    const stored = localStorage.getItem(ROTATION_STORAGE_KEY);
    const map: Record<string, number> = stored ? JSON.parse(stored) : {};
    map[trackName] = deg;
    localStorage.setItem(ROTATION_STORAGE_KEY, JSON.stringify(map));
  } catch { /* ignore */ }
}

function loadSavedZoom(trackName: string): number {
  try {
    const stored = localStorage.getItem(ZOOM_STORAGE_KEY);
    if (stored) {
      const map = JSON.parse(stored) as Record<string, number>;
      return map[trackName] ?? 1;
    }
  } catch { /* ignore */ }
  return 1;
}

function saveZoom(trackName: string, zoom: number) {
  try {
    const stored = localStorage.getItem(ZOOM_STORAGE_KEY);
    const map: Record<string, number> = stored ? JSON.parse(stored) : {};
    map[trackName] = zoom;
    localStorage.setItem(ZOOM_STORAGE_KEY, JSON.stringify(map));
  } catch { /* ignore */ }
}

function loadSavedPan(trackName: string): { x: number; z: number } {
  try {
    const stored = localStorage.getItem(PAN_STORAGE_KEY);
    if (stored) {
      const map = JSON.parse(stored) as Record<string, { x: number; z: number }>;
      return map[trackName] ?? { x: 0, z: 0 };
    }
  } catch { /* ignore */ }
  return { x: 0, z: 0 };
}

function savePan(trackName: string, p: { x: number; z: number }) {
  try {
    const stored = localStorage.getItem(PAN_STORAGE_KEY);
    const map: Record<string, { x: number; z: number }> = stored ? JSON.parse(stored) : {};
    map[trackName] = p;
    localStorage.setItem(PAN_STORAGE_KEY, JSON.stringify(map));
  } catch { /* ignore */ }
}

/** Build an SVG polygon points string for a triangular arrow at (cx, cz) pointing in `heading`. */
function playerArrow(cx: number, cz: number, heading: number, size: number): string {
  const cos = Math.cos(heading);
  const sin = Math.sin(heading);
  const tipX = cx + cos * size;
  const tipZ = cz + sin * size;
  const rearLX = cx - cos * size * 0.5 + sin * size * 0.55;
  const rearLZ = cz - sin * size * 0.5 - cos * size * 0.55;
  const rearRX = cx - cos * size * 0.5 - sin * size * 0.55;
  const rearRZ = cz - sin * size * 0.5 + cos * size * 0.55;
  return `${tipX},${tipZ} ${rearLX},${rearLZ} ${rearRX},${rearRZ}`;
}

export function TrackMap() {
  const state = useTrackMap();
  const [rotation, setRotation] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, z: 0 });
  const [labelMode, setLabelMode] = useState<LabelMode>(() => {
    try {
      return (localStorage.getItem(LABEL_MODE_STORAGE_KEY) as LabelMode) || "driver";
    } catch { return "driver"; }
  });
  const trackNameRef = useRef("");

  const trackName = state?.trackName ?? "";

  // Load saved rotation and zoom when track changes
  useEffect(() => {
    if (trackName && trackName !== trackNameRef.current) {
      trackNameRef.current = trackName;
      setRotation(loadSavedRotation(trackName));
      setZoom(loadSavedZoom(trackName));
      setPan(loadSavedPan(trackName));
    }
  }, [trackName]);

  const handleRotationChange = useCallback((deg: number) => {
    setRotation(deg);
    if (trackName) saveRotation(trackName, deg);
  }, [trackName]);

  const handleZoomChange = useCallback((newZoom: number) => {
    const clamped = Math.max(0.5, Math.min(4, newZoom));
    setZoom(clamped);
    if (trackName) saveZoom(trackName, clamped);
  }, [trackName]);

  const handlePan = useCallback((p: { x: number; z: number }) => {
    setPan(p);
    if (trackName) savePan(trackName, p);
  }, [trackName]);

  const handleToggleLabel = useCallback(() => {
    const next: LabelMode = labelMode === "driver" ? "team" : "driver";
    setLabelMode(next);
    try { localStorage.setItem(LABEL_MODE_STORAGE_KEY, next); } catch { /* ignore */ }
  }, [labelMode]);

  const handleFit = useCallback(() => {
    setZoom(1);
    setPan({ x: 0, z: 0 });
    if (trackName) {
      saveZoom(trackName, 1);
      savePan(trackName, { x: 0, z: 0 });
    }
  }, [trackName]);

  const hasOutline = state && state.trackOutline.length >= 10;
  const hasCars = state && state.cars.some(c => c.active);

  if (!hasOutline) {
    return (
      <div className="bg-card border border-border/50 rounded-md overflow-hidden h-full flex flex-col">
        <Header trackName="" carCount={0} />
        <div className="flex-1 flex items-center justify-center">
          <span className="text-[10px] text-muted-foreground uppercase tracking-wider font-display">
            Waiting for track data…
          </span>
        </div>
      </div>
    );
  }

  return <TrackMapSVG state={state!} hasCars={hasCars ?? false} rotation={rotation} onRotationChange={handleRotationChange} zoom={zoom} onZoomChange={handleZoomChange} pan={pan} onPan={handlePan} onFit={handleFit} labelMode={labelMode} onToggleLabel={handleToggleLabel} />;
}

function TrackMapSVG({
  state,
  hasCars,
  rotation,
  onRotationChange,
  zoom,
  onZoomChange,
  pan,
  onPan,
  onFit,
  labelMode,
  onToggleLabel,
}: {
  state: NonNullable<ReturnType<typeof useTrackMap>>;
  hasCars: boolean;
  rotation: number;
  onRotationChange: (deg: number) => void;
  zoom: number;
  onZoomChange: (z: number) => void;
  pan: { x: number; z: number };
  onPan: (p: { x: number; z: number }) => void;
  onFit: () => void;
  labelMode: LabelMode;
  onToggleLabel: () => void;
}) {
  const { trackOutline, cars, playerIndex, outlineComplete, trackName } = state;

  const activeCars = useMemo(
    () => cars.filter((c, i) => c.active && i !== playerIndex),
    [cars, playerIndex],
  );
  const playerCar = cars[playerIndex];
  const carCount = activeCars.length + (playerCar && (playerCar.x !== 0 || playerCar.z !== 0) ? 1 : 0);

  // Compute bounding box from the track outline
  const bounds = useMemo(() => {
    let minX = Infinity, maxX = -Infinity;
    let minZ = Infinity, maxZ = -Infinity;
    for (const p of trackOutline) {
      if (p.x < minX) minX = p.x;
      if (p.x > maxX) maxX = p.x;
      if (p.z < minZ) minZ = p.z;
      if (p.z > maxZ) maxZ = p.z;
    }
    const padX = Math.max((maxX - minX) * 0.04, 10);
    const padZ = Math.max((maxZ - minZ) * 0.04, 10);
    return {
      x: minX - padX,
      z: minZ - padZ,
      w: maxX - minX + 2 * padX,
      h: maxZ - minZ + 2 * padZ,
      cx: (minX + maxX) / 2,
      cz: (minZ + maxZ) / 2,
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [trackOutline.length, outlineComplete]);

  // Build smooth SVG path
  const smoothPath = useMemo(() => {
    return smoothTrackPath(trackOutline, outlineComplete);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [trackOutline.length, outlineComplete]);

  // Detect turns
  const turns = useMemo(() => {
    if (!outlineComplete) return [];
    return detectTurns(trackOutline, true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [trackOutline.length, outlineComplete]);

  // Scale-relative sizes
  const scale = Math.max(bounds.w, bounds.h);
  const trackWidth = scale * 0.03;
  const centerLineWidth = scale * 0.012;
  const otherR = scale * 0.012;
  const playerSize = scale * 0.018;
  const labelSize = scale * 0.022;
  const turnR = scale * 0.018;
  const turnLabelSize = scale * 0.02;
  const turnOffset = scale * 0.045;

  // Zoomed + panned viewBox
  const zW = bounds.w / zoom;
  const zH = bounds.h / zoom;
  const zX = bounds.cx - zW / 2 + pan.x;
  const zZ = bounds.cz - zH / 2 + pan.z;

  const svgRef = useRef<HTMLDivElement>(null);
  const draggingRef = useRef(false);
  const dragStartRef = useRef({ clientX: 0, clientY: 0, panX: 0, panZ: 0 });

  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.08 : 1 / 1.08;
    onZoomChange(zoom * factor);
  }, [zoom, onZoomChange]);

  const handlePointerDown = useCallback((e: React.PointerEvent) => {
    if (e.button !== 0) return;
    draggingRef.current = true;
    dragStartRef.current = { clientX: e.clientX, clientY: e.clientY, panX: pan.x, panZ: pan.z };
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  }, [pan]);

  const handlePointerMove = useCallback((e: React.PointerEvent) => {
    if (!draggingRef.current || !svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    // Convert pixel delta to SVG coordinate delta
    const scaleX = zW / rect.width;
    const scaleZ = zH / rect.height;
    const dx = (e.clientX - dragStartRef.current.clientX) * scaleX;
    const dz = (e.clientY - dragStartRef.current.clientY) * scaleZ;
    onPan({ x: dragStartRef.current.panX - dx, z: dragStartRef.current.panZ - dz });
  }, [zW, zH, onPan]);

  const handlePointerUp = useCallback(() => {
    draggingRef.current = false;
  }, []);

  return (
    <div className="bg-card border border-border/50 rounded-md overflow-hidden h-full flex flex-col">
      <Header trackName={trackName} carCount={hasCars ? carCount : 0} />
      <div className="flex-1 min-h-0 relative">
        <div
          ref={svgRef}
          className="absolute inset-0 p-1 cursor-grab active:cursor-grabbing"
          onWheel={handleWheel}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
        >
          <svg
            viewBox={`${zX} ${zZ} ${zW} ${zH}`}
            className="w-full h-full"
            preserveAspectRatio="xMidYMid meet"
          >
          <defs>
            <filter id="playerGlow" x="-200%" y="-200%" width="500%" height="500%">
              <feGaussianBlur stdDeviation={scale * 0.006} result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            <filter id="trackGlow" x="-10%" y="-10%" width="120%" height="120%">
              <feGaussianBlur stdDeviation={scale * 0.003} result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          <g transform={`rotate(${rotation} ${bounds.cx} ${bounds.cz})`}>
            {/* Track — thick dark green */}
            <path
              d={smoothPath}
              fill="none"
              stroke="#22863a"
              strokeWidth={trackWidth}
              strokeLinejoin="round"
              strokeLinecap="round"
              filter="url(#trackGlow)"
            />

            {/* Center line — thin light white */}
            <path
              d={smoothPath}
              fill="none"
              stroke="#ffffff"
              strokeWidth={centerLineWidth}
              strokeOpacity={1}
              strokeLinejoin="round"
              strokeLinecap="round"
            />

            {/* Other cars */}
            {activeCars.map((car, i) => (
              <g key={i}>
                <circle
                  cx={car.x}
                  cy={car.z}
                  r={otherR}
                  fill="none"
                  stroke="#1e40af"
                  strokeWidth={otherR * 0.8}
                />
                {car.position > 0 && (
                  <text
                    x={car.x}
                    y={car.z - otherR * 2.2}
                    textAnchor="middle"
                    fill="#93c5fd"
                    fontSize={labelSize}
                    fontFamily="monospace"
                    fontWeight="bold"
                    transform={`rotate(${-rotation} ${car.x} ${car.z})`}
                  >
                    {car.position > 0 ? `${car.position} ` : ""}
                    {labelMode === "team"
                      ? (car.teamAbbreviation || "")
                      : (car.abbreviation || "")}
                  </text>
                )}
              </g>
            ))}

            {/* Player car — glowing red arrow pointing in driving direction */}
            {playerCar && (playerCar.x !== 0 || playerCar.z !== 0) && (
              <>
                <g filter="url(#playerGlow)">
                  <polygon
                    points={playerArrow(playerCar.x, playerCar.z, playerCar.heading, playerSize)}
                    fill="#ef4444"
                  />
                </g>
                <text
                  x={playerCar.x}
                  y={playerCar.z - playerSize * 2}
                  textAnchor="middle"
                  fill="#fca5a5"
                  fontSize={labelSize}
                  fontFamily="monospace"
                  fontWeight="bold"
                  transform={`rotate(${-rotation} ${playerCar.x} ${playerCar.z})`}
                >
                  {playerCar.position > 0 ? `${playerCar.position} ` : ""}YOU
                </text>
              </>
            )}

            {/* Turn indicators */}
            {turns.map((turn) => {
              const tx = turn.x + Math.cos(turn.normalAngle) * turnOffset;
              const tz = turn.z + Math.sin(turn.normalAngle) * turnOffset;
              return (
                <g key={`turn-${turn.number}`} transform={`rotate(${-rotation} ${tx} ${tz})`}>
                  <circle cx={tx} cy={tz} r={turnR} fill="#646464" />
                  <text
                    x={tx}
                    y={tz}
                    textAnchor="middle"
                    dominantBaseline="central"
                    fill="#ffffff"
                    fontSize={turnLabelSize}
                    fontFamily="monospace"
                    fontWeight="bold"
                  >
                    {turn.number}
                  </text>
                </g>
              );
            })}
          </g>
        </svg>
        </div>

        {/* Floating toolbar — top-right */}
        <div className="absolute right-2 top-2 flex flex-col items-center gap-1 bg-card/20 backdrop-blur-sm border border-border/30 rounded-md p-1 z-10">
          <button
            onClick={() => onZoomChange(zoom * 1.15)}
            className="p-1 rounded text-muted-foreground hover:text-primary hover:bg-secondary/50 transition-colors"
            title="Zoom in"
          >
            <ZoomIn className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={() => onZoomChange(zoom / 1.15)}
            className="p-1 rounded text-muted-foreground hover:text-primary hover:bg-secondary/50 transition-colors"
            title="Zoom out"
          >
            <ZoomOut className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={onFit}
            className="p-1 rounded text-muted-foreground hover:text-primary hover:bg-secondary/50 transition-colors"
            title="Fit to viewport"
          >
            <Maximize className="h-3.5 w-3.5" />
          </button>
          <div className="p-0.5">
            <RotationDial rotation={rotation} onChange={onRotationChange} />
          </div>
          <button
            onClick={onToggleLabel}
            className="p-1 rounded text-muted-foreground hover:text-primary hover:bg-secondary/50 transition-colors"
            title={`Labels: ${labelMode === "driver" ? "Driver" : "Team"} (click to toggle)`}
          >
            <Users className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}

/** Draggable compass rotation control. */
function RotationDial({ rotation, onChange }: { rotation: number; onChange: (deg: number) => void }) {
  const dialRef = useRef<HTMLDivElement>(null);
  const draggingRef = useRef(false);
  const startAngleRef = useRef(0);
  const startRotationRef = useRef(0);

  const getAngleFromEvent = useCallback((e: { clientX: number; clientY: number }) => {
    const el = dialRef.current;
    if (!el) return 0;
    const rect = el.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    return Math.atan2(e.clientY - cy, e.clientX - cx) * (180 / Math.PI);
  }, []);

  const onPointerDown = useCallback((e: React.PointerEvent) => {
    e.preventDefault();
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
    draggingRef.current = true;
    startAngleRef.current = getAngleFromEvent(e);
    startRotationRef.current = rotation;
  }, [getAngleFromEvent, rotation]);

  const onPointerMove = useCallback((e: React.PointerEvent) => {
    if (!draggingRef.current) return;
    const currentAngle = getAngleFromEvent(e);
    const delta = currentAngle - startAngleRef.current;
    const newRotation = Math.round(startRotationRef.current + delta) % 360;
    onChange(newRotation);
  }, [getAngleFromEvent, onChange]);

  const onPointerUp = useCallback(() => {
    draggingRef.current = false;
  }, []);

  return (
    <div
      ref={dialRef}
      className="relative w-5 h-5 cursor-grab active:cursor-grabbing select-none"
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      title={`Rotate track (${rotation}°)`}
    >
      <Compass
        className="w-5 h-5 text-muted-foreground hover:text-primary transition-colors"
        style={{ transform: `rotate(${rotation}deg)` }}
      />
    </div>
  );
}

function Header({ trackName, carCount }: { trackName: string; carCount: number }) {
  return (
    <div className="flex items-center gap-2 px-3 py-2 border-b border-border/50 bg-secondary/30">
      <Map className="h-4 w-4 text-primary" />
      <span className="font-display text-sm font-bold tracking-widest uppercase text-foreground">
        Track Map{trackName ? ` — ${trackName}` : ""}
      </span>
      {carCount > 0 && (
        <span className="ml-auto font-display text-[10px] font-bold text-emerald-500">
          {carCount} CARS
        </span>
      )}
    </div>
  );
}
