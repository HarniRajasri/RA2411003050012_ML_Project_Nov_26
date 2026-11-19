import { useWidth } from "./useWidth.js";
import { timeOf } from "../services/format.js";

const H = 270;
const M = { l: 38, r: 10, t: 22, b: 48 };

/** One bar per analytics window (default 10 minutes): estimated engagement % with the connected count underneath. */
export default function WindowsChart({ windows, peakIndex }) {
  const [ref, width] = useWidth();
  const iw = width - M.l - M.r;
  const ih = H - M.t - M.b;
  const n = windows.length;
  if (!n) return <div ref={ref} className="empty">No windows yet.</div>;
  const slot = iw / n;
  const bw = Math.max(10, Math.min(72, slot * 0.62));
  const y = (v) => M.t + (1 - v / 100) * ih;
  const everyLabel = slot < 54 ? Math.ceil(54 / slot) : 1;

  return (
    <div ref={ref}>
      <svg className="chart" width={width} height={H} role="img" aria-label="Estimated engagement per time window">
        <defs>
          <pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="6" height="6" fill="#bfe6d9" />
            <line x1="0" y1="0" x2="0" y2="6" stroke="#7cc9b0" strokeWidth="2" />
          </pattern>
        </defs>
        <g className="grid">
          {[0, 25, 50, 75, 100].map((v) => (
            <g key={v}>
              <line x1={M.l} x2={width - M.r} y1={y(v)} y2={y(v)} className={v === 0 ? "strong" : ""} />
              <text x={M.l - 8} y={y(v) + 4} textAnchor="end">{v}%</text>
            </g>
          ))}
        </g>
        {windows.map((w, i) => {
          const cx = M.l + slot * i + slot / 2;
          const has = w.engagement_percentage !== null && w.engagement_percentage !== undefined;
          const partial = w.status !== "complete";
          const isPeak = peakIndex === w.index;
          const show = i % everyLabel === 0;
          return (
            <g key={w.index}>
              {has ? (
                <>
                  <rect x={cx - bw / 2} y={y(w.engagement_percentage)} width={bw} height={y(0) - y(w.engagement_percentage)}
                        fill={partial ? "url(#hatch)" : "var(--engaged)"} stroke={isPeak ? "var(--ink)" : "none"} strokeWidth={isPeak ? 2 : 0} rx="2" />
                  <text x={cx} y={y(w.engagement_percentage) - 6} textAnchor="middle" style={{ fill: "var(--ink)", fontWeight: 600 }}>
                    {w.engagement_percentage.toFixed(0)}%
                  </text>
                </>
              ) : (
                <>
                  <rect x={cx - bw / 2} y={y(12)} width={bw} height={y(0) - y(12)} fill="none" stroke="var(--line-strong)" strokeDasharray="3 3" rx="2" />
                  <text x={cx} y={y(6)} textAnchor="middle">{w.status === "upcoming" ? "later" : "no data"}</text>
                </>
              )}
              {show && (
                <>
                  <text x={cx} y={H - 30} textAnchor="middle">{timeOf(w.window_start, false)}</text>
                  <text x={cx} y={H - 16} textAnchor="middle">{w.connected_students === null ? "" : `${w.connected_students} conn.`}</text>
                </>
              )}
              {isPeak && <text x={cx} y={M.t - 8} textAnchor="middle" style={{ fill: "var(--ink)", fontWeight: 650 }}>Peak</text>}
            </g>
          );
        })}
      </svg>
    </div>
  );
}
