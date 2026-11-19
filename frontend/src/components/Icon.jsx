const PATHS = {
  live: "M3 12h4l2.5-7 4 14 2.5-7H21",
  devices: "M4 6h16v9H4zM9 19h6M12 15v4",
  analytics: "M4 20V10m6 10V4m6 16v-7m4 7H2",
  history: "M4 12a8 8 0 1 0 2.4-5.7M4 4v4h4M12 8v4l3 2",
  demo: "M9 3h6M10 3v6l-5 9a2 2 0 0 0 1.8 3h10.4A2 2 0 0 0 19 18l-5-9V3M8 15h8",
  system: "M12 8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7zM12 3v3m0 12v3M3 12h3m12 0h3M5.6 5.6l2.1 2.1m8.6 8.6 2.1 2.1m0-12.8-2.1 2.1M7.7 16.3l-2.1 2.1",
  play: "M7 4l13 8-13 8z",
  stop: "M6 6h12v12H6z",
  plus: "M12 5v14M5 12h14",
  download: "M12 4v11m0 0-4-4m4 4 4-4M5 20h14",
  refresh: "M20 12a8 8 0 1 1-2.3-5.7M20 4v5h-5",
  x: "M6 6l12 12M18 6 6 18",
  headband: "M4 15c1-6 4-9 8-9s7 3 8 9M6 15v3m12-3v3",
};

export default function Icon({ name, size = 18, stroke = 1.8 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={stroke}
         strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={{ flex: "none" }}>
      <path d={PATHS[name] || PATHS.live} />
    </svg>
  );
}
