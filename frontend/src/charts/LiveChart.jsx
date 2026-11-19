import { useMemo, useState } from "react";
import { useWidth } from "./useWidth.js";
import { timeOf } from "../services/format.js";

const H = 240;
const M = { l: 38, r: 14, t: 14, b: 26 };

/** Estimated engagement (%) of connected students over the current class, one point about every 2 seconds. */
export default function LiveChart({ history }) {
  const [ref, width] = useWidth();
  const [hover, setHover] = useState(null);

  const pts = useMemo(() => history.map((p) => ({ ...p, ms: new Date(p.t).getTime() })), [history]);
  const iw = width - M.l - M.r;
  const ih = H - M.t - M.b;

  if (pts.length < 2) {
    return (
      <div ref={ref} style={{ height: H, display: "grid", placeItems: "center" }} className="muted">
        Waiting for the first estimates. The chart fills in as headbands send telemetry.
      </div>
    );
  }

  const t0 = pts[0].ms;
  const t1 = Math.max(pts[pts.length - 1].ms, t0 + 60000);
  const x = (ms) => M.l + ((ms - t0) / (t1 - t0)) * iw;
  const y = (v) => M.t + (1 - v / 100) * ih;

  // segments split on gaps (null engagement) so "no data" is never drawn as zero
  const segs = [];
  let cur = [];
  for (const p of pts) {
    if (p.engagement === null || p.engagement === undefined) {
      if (cur.length) segs.push(cur);
      cur = [];
    } else cur.push(p);
  }
  if (cur.length) segs.push(cur);
  const line = (s) => s.map((p, i) => `${i ? "L" : "M"}${x(p.ms).toFixed(1)},${y(p.engagement).toFixed(1)}`).join("");
  const area = (s) => `${line(s)}L${x(s[s.length - 1].ms).toFixed(1)},${y(0)}L${x(s[0].ms).toFixed(1)},${y(0)}Z`;

  const withSeconds = t1 - t0 < 5 * 60 * 1000;
  const nTicks = Math.max(2, Math.min(6, Math.floor(iw / (withSeconds ? 130 : 110))));
  const xticks = Array.from({ length: nTicks + 1 }, (_, i) => t0 + ((t1 - t0) * i) / nTicks);

  const onMove = (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    const ms = t0 + ((e.clientX - r.left - M.l) / iw) * (t1 - t0);
    let best = 0;
    let bd = Infinity;
    pts.forEach((p, i) => {
      const d = Math.abs(p.ms - ms);
      if (d < bd) {
        bd = d;
        best = i;
      }
    });
    setHover(best);
  };
  const hp = hover !== null ? pts[hover] : null;

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <svg className="chart" width={width} height={H} role="img"
           aria-label="Estimated engagement over time for the current class"
           onMouseMove={onMove} onMouseLeave={() => setHover(null)}>
        <g className="grid">
          {[0, 25, 50, 75, 100].map((v) => (
            <g key={v}>
              <line x1={M.l} x2={width - M.r} y1={y(v)} y2={y(v)} className={v === 0 ? "strong" : ""} />
              <text x={M.l - 8} y={y(v) + 4} textAnchor="end">{v}%</text>
            </g>
          ))}
        </g>
        {xticks.map((t, i) => (
          <text key={i} x={x(t)} y={H - 7} textAnchor={i === 0 ? "start" : i === xticks.length - 1 ? "end" : "middle"}>{timeOf(new Date(t).toISOString(), withSeconds)}</text>
        ))}
        {segs.map((s, i) => (
          <g key={i}>
            <path d={area(s)} fill="var(--engaged)" opacity="0.12" />
            <path d={line(s)} fill="none" stroke="var(--engaged)" strokeWidth="2" strokeLinejoin="round" />
          </g>
        ))}
        {hp && (
          <g>
            <line x1={x(hp.ms)} x2={x(hp.ms)} y1={M.t} y2={M.t + ih} stroke="var(--ink-3)" strokeDasharray="3 3" />
            {hp.engagement !== null && hp.engagement !== undefined && <circle cx={x(hp.ms)} cy={y(hp.engagement)} r="4" fill="var(--engaged)" stroke="#fff" strokeWidth="1.5" />}
          </g>
        )}
      </svg>
      <div className="small muted" style={{ position: "absolute", top: 0, right: 14, minHeight: 18 }}>
        {hp
          ? `${timeOf(hp.t)}  |  ${hp.engagement === null || hp.engagement === undefined ? "no estimate" : hp.engagement.toFixed(0) + "% estimated engaged"}  |  ${hp.connected} connected`
          : ""}
      </div>
    </div>
  );
}
