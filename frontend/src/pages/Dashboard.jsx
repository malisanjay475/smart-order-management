import { useEffect, useState } from "react";
import { api, inr, when } from "../api.js";
import { BarChart, Confidence, STATUS_LABELS, SourceTag, Stat, StatusChip } from "../components/ui.jsx";

export default function Dashboard({ onOpenOrder }) {
  const [data, setData] = useState(null);
  const [recent, setRecent] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;
    const load = () =>
      Promise.all([api("/dashboard"), api("/orders")])
        .then(([d, o]) => {
          if (!alive) return;
          setData(d);
          setRecent(o.slice(0, 6));
        })
        .catch((e) => alive && setError(e.message));
    load();
    const timer = setInterval(load, 3000); // live view of the queue
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, []);

  if (error) return <div className="card error-card">{error}</div>;
  if (!data) return <div className="center-screen"><div className="spinner" /></div>;

  const statusMax = Math.max(1, ...Object.values(data.by_status));
  const dayLabel = (iso) => new Date(iso).toLocaleDateString("en-IN", { weekday: "short" });
  const sources = Object.entries(data.by_source);
  const sourceTotal = sources.reduce((a, [, n]) => a + n, 0) || 1;

  return (
    <div className="page-stack">
      <header className="page-head">
        <div>
          <div className="eyebrow">Overview</div>
          <h1>Operations dashboard</h1>
        </div>
        <span className={`pill ${data.queue_length ? "pill-live" : ""}`}>
          {data.queue_length ? `● ${data.queue_length} in queue` : "● Queue idle"}
        </span>
      </header>

      <div className="stats">
        <Stat label="Total orders" value={data.total_orders} sub={`${data.pending} waiting or on hold`} />
        <Stat label="Revenue" value={inr(data.revenue)} sub="confirmed, shipped and delivered" accent="violet" />
        <Stat label="AI match confidence" value={`${data.avg_confidence}%`} sub="average across all order lines" accent="pink" />
        <Stat label="Avg. processing time" value={`${data.avg_processing_seconds}s`} sub="from received to confirmed" accent="cyan" />
      </div>

      <div className="grid-2">
        <section className="card">
          <h3>Orders, last 7 days</h3>
          <BarChart data={data.per_day} valueKey="orders" labelKey="date" />
          <div className="bar-labels">
            {data.per_day.map((d) => (
              <span key={d.date}><b>{d.orders}</b>{dayLabel(d.date)}</span>
            ))}
          </div>
        </section>

        <section className="card">
          <h3>Order status</h3>
          <div className="hbars">
            {Object.entries(data.by_status).map(([s, n]) => (
              <div key={s} className="hbar">
                <span className="hbar-label">{STATUS_LABELS[s]}</span>
                <div className="hbar-track"><div className={`hbar-fill fill-${s}`} style={{ width: `${(n / statusMax) * 100}%` }} /></div>
                <span className="hbar-num">{n}</span>
              </div>
            ))}
          </div>
          <h3 className="mt">Orders by channel</h3>
          <div className="channel-bar">
            {sources.map(([s, n]) => (
              <div key={s} className={`seg seg-${s}`} style={{ width: `${(n / sourceTotal) * 100}%` }}>
                {s} {Math.round((n / sourceTotal) * 100)}%
              </div>
            ))}
          </div>
        </section>
      </div>

      <div className="grid-3">
        <section className="card span-2">
          <h3>Recent orders</h3>
          <table className="table">
            <thead>
              <tr><th>Order</th><th>Channel</th><th>Items</th><th>AI match</th><th>Total</th><th>Status</th></tr>
            </thead>
            <tbody>
              {recent.map((o) => (
                <tr key={o.id} className="clickable" onClick={() => onOpenOrder(o.id)}>
                  <td><b>{o.code}</b><div className="muted small">{when(o.created_at)}</div></td>
                  <td><SourceTag source={o.source} /></td>
                  <td>{o.item_count}</td>
                  <td><Confidence value={o.ai_confidence} /></td>
                  <td>{inr(o.total)}</td>
                  <td><StatusChip status={o.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <div className="page-stack">
          <section className="card">
            <h3>⚠ Low stock <span className="count pink">{data.low_stock.length}</span></h3>
            {data.low_stock.length === 0 && <p className="muted">All products are above their reorder level.</p>}
            <ul className="mini-list">
              {data.low_stock.slice(0, 5).map((p) => (
                <li key={p.id}>
                  <span>{p.name}</span>
                  <b className="pink-text">{p.stock} left</b>
                </li>
              ))}
            </ul>
          </section>
          <section className="card">
            <h3>Top products</h3>
            <ul className="mini-list">
              {data.top_products.map((p) => (
                <li key={p.name}><span>{p.name}</span><b>{p.quantity}</b></li>
              ))}
            </ul>
          </section>
        </div>
      </div>
    </div>
  );
}
