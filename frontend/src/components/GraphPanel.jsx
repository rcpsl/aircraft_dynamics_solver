import { useState, useRef } from 'react';
import { ZONES, ZONE_COLORS } from '../constants';

const W = 300, H = 300, NODE_R = 16;

export default function GraphPanel({ M, adjacency, stationZones }) {
  function initPositions() {
    const cx = W / 2, cy = H / 2;
    const r = Math.min(W, H) / 2 - 48;
    return Array.from({ length: M }, (_, i) => ({
      x: cx + r * Math.cos((2 * Math.PI * i) / M - Math.PI / 2),
      y: cy + r * Math.sin((2 * Math.PI * i) / M - Math.PI / 2),
    }));
  }

  const [positions,  setPositions]  = useState(initPositions);
  const [isDragging, setIsDragging] = useState(false);
  const dragging = useRef(null);
  const svgRef   = useRef(null);

  const edges = [];
  for (let i = 0; i < M; i++)
    for (let j = i + 1; j < M; j++) {
      const fwd = adjacency[i]?.[j] === 1;
      const bwd = adjacency[j]?.[i] === 1;
      if (fwd || bwd) edges.push({ i, j, fwd, bwd });
    }

  function edgePts(i, j) {
    const { x: x1, y: y1 } = positions[i];
    const { x: x2, y: y2 } = positions[j];
    const len = Math.hypot(x2 - x1, y2 - y1);
    if (len === 0) return null;
    const ux = (x2 - x1) / len, uy = (y2 - y1) / len;
    return {
      x1: x1 + ux * NODE_R, y1: y1 + uy * NODE_R,
      x2: x2 - ux * NODE_R, y2: y2 - uy * NODE_R,
    };
  }

  function startDrag(e, idx) {
    e.preventDefault();
    const rect = svgRef.current.getBoundingClientRect();
    dragging.current = {
      idx,
      ox: (e.clientX - rect.left) - positions[idx].x,
      oy: (e.clientY - rect.top)  - positions[idx].y,
    };
    setIsDragging(true);
  }

  function onMove(e) {
    if (!dragging.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    const { idx, ox, oy } = dragging.current;
    const x = Math.max(NODE_R, Math.min(W - NODE_R, e.clientX - rect.left - ox));
    const y = Math.max(NODE_R, Math.min(H - NODE_R, e.clientY - rect.top  - oy));
    setPositions(prev => prev.map((p, i) => i === idx ? { x, y } : p));
  }

  function stopDrag() { dragging.current = null; setIsDragging(false); }

  return (
    <div>
      <svg ref={svgRef} width={W} height={H}
        style={{ display: "block", margin: "0 auto", cursor: isDragging ? "grabbing" : "default" }}
        onMouseMove={onMove} onMouseUp={stopDrag} onMouseLeave={stopDrag}
      >
        <defs>
          <marker id="arr" markerWidth="9" markerHeight="6" refX="9" refY="3" orient="auto-start-reverse">
            <path d="M0,0 L0,6 L9,3 z" fill="#78716c" />
          </marker>
        </defs>
        {edges.map(({ i, j, fwd, bwd }) => {
          const p = edgePts(i, j);
          if (!p) return null;
          return (
            <line key={`e${i}-${j}`} x1={p.x1} y1={p.y1} x2={p.x2} y2={p.y2}
              stroke="#a8a29e" strokeWidth="1.5"
              markerEnd={fwd ? "url(#arr)" : undefined}
              markerStart={bwd ? "url(#arr)" : undefined}
            />
          );
        })}
        {positions.map(({ x, y }, idx) => {
          const zone = ZONES[(stationZones?.[idx] || 1) - 1];
          return (
            <g key={`n${idx}`} style={{ cursor: "grab" }} onMouseDown={e => startDrag(e, idx)}>
              <circle cx={x} cy={y} r={NODE_R} fill={ZONE_COLORS[zone.category]} stroke="#1c1917" strokeWidth="1.5" />
              <text x={x} y={y} textAnchor="middle" dominantBaseline="central"
                fontSize="12" fontWeight="700" fill="#ffffff"
                style={{ userSelect: "none", pointerEvents: "none" }}>
                {idx + 1}
              </text>
            </g>
          );
        })}
      </svg>
      <button className="config-btn" style={{ marginTop: "10px", width: "100%" }}
        onClick={() => setPositions(initPositions())}>
        Reset Layout
      </button>
    </div>
  );
}
