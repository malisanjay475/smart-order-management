// Small shared UI pieces.

export const STATUS_LABELS = {
  received: "Received",
  processing: "Processing",
  confirmed: "Confirmed",
  on_hold: "On hold",
  shipped: "Shipped",
  delivered: "Delivered",
  cancelled: "Cancelled",
};

export function StatusChip({ status }) {
  return <span className={`status status-${status}`}>{STATUS_LABELS[status] || status}</span>;
}

export function SourceTag({ source }) {
  const icons = { text: "💬", email: "✉", pdf: "📄", manual: "✎" };
  return <span className="source-tag">{icons[source] || "•"} {source}</span>;
}

export function Confidence({ value }) {
  const tone = value >= 90 ? "high" : value >= 80 ? "mid" : "low";
  return (
    <div className={`conf conf-${tone}`} title={`AI match confidence ${value}%`}>
      <div className="conf-track"><div className="conf-fill" style={{ width: `${value}%` }} /></div>
      <span>{Math.round(value)}%</span>
    </div>
  );
}

export function Stat({ label, value, sub, accent = "cyan" }) {
  return (
    <div className={`card stat stat-${accent}`}>
      <div className="muted small upper">{label}</div>
      <div className="stat-value">{value}</div>
      {sub && <div className="muted small">{sub}</div>}
    </div>
  );
}

export function BarChart({ data, valueKey, labelKey, height = 180 }) {
  const max = Math.max(1, ...data.map((d) => d[valueKey]));
  const w = 100 / data.length;
  return (
    <svg className="bar-chart" viewBox={`0 0 100 ${height / 3}`} preserveAspectRatio="none" role="img">
      <defs>
        <linearGradient id="barGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#22d3ee" />
          <stop offset="100%" stopColor="#7c3aed" />
        </linearGradient>
      </defs>
      {data.map((d, i) => {
        const h = (d[valueKey] / max) * (height / 3 - 4);
        return (
          <rect key={d[labelKey]} x={i * w + w * 0.2} y={height / 3 - h} width={w * 0.6} height={Math.max(h, 0.4)}
            rx="1.2" fill="url(#barGrad)">
            <title>{`${d[labelKey]}: ${d[valueKey]}`}</title>
          </rect>
        );
      })}
    </svg>
  );
}
