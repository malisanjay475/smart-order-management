import { useEffect, useState } from "react";
import { api, inr, when } from "../api.js";
import { Confidence, STATUS_LABELS, SourceTag, StatusChip } from "../components/ui.jsx";

const NEXT = {
  received: ["cancelled"],
  on_hold: ["cancelled"],
  confirmed: ["shipped", "cancelled"],
  shipped: ["delivered"],
};
const PIPELINE = ["received", "processing", "confirmed", "shipped", "delivered"];

export default function Orders({ user, openId, setOpenId }) {
  const [orders, setOrders] = useState([]);
  const [filter, setFilter] = useState("");
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState("");
  const isAdmin = user.role === "admin";

  useEffect(() => {
    let alive = true;
    const load = () =>
      api("/orders").then((o) => alive && setOrders(o)).catch((e) => alive && setError(e.message));
    load();
    const t = setInterval(load, 2000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  useEffect(() => {
    if (!openId) { setDetail(null); return; }
    let alive = true;
    const load = () => api(`/orders/${openId}`).then((d) => alive && setDetail(d)).catch((e) => setError(e.message));
    load();
    const t = setInterval(load, 1500); // watch the worker update the order live
    return () => { alive = false; clearInterval(t); };
  }, [openId]);

  async function changeStatus(status) {
    try {
      setDetail(await api(`/orders/${detail.id}/status`, { method: "PATCH", body: { status } }));
    } catch (e) {
      setError(e.message);
    }
  }

  const shown = filter ? orders.filter((o) => o.status === filter) : orders;
  const counts = orders.reduce((a, o) => ({ ...a, [o.status]: (a[o.status] || 0) + 1 }), {});
  const actions = detail ? (NEXT[detail.status] || []).filter((s) => isAdmin || s === "cancelled") : [];
  const step = detail ? PIPELINE.indexOf(detail.status) : -1;

  return (
    <div className="page-stack">
      <header className="page-head">
        <div>
          <div className="eyebrow">{isAdmin ? "All orders" : "My orders"}</div>
          <h1>Orders</h1>
        </div>
        <span className="pill">Auto-refresh · live queue</span>
      </header>

      <div className="filters">
        <button className={`chip-btn ${!filter ? "on" : ""}`} onClick={() => setFilter("")}>All {orders.length}</button>
        {Object.keys(STATUS_LABELS).filter((s) => counts[s]).map((s) => (
          <button key={s} className={`chip-btn ${filter === s ? "on" : ""}`} onClick={() => setFilter(s)}>
            {STATUS_LABELS[s]} {counts[s]}
          </button>
        ))}
      </div>
      {error && <p className="error">{error}</p>}

      <div className={`orders-layout ${detail ? "with-detail" : ""}`}>
        <section className="card">
          {shown.length === 0 && <p className="muted">No orders yet.</p>}
          <table className="table">
            <thead>
              <tr><th>Order</th>{isAdmin && <th>Customer</th>}<th>Channel</th><th>AI match</th><th>Total</th><th>Status</th></tr>
            </thead>
            <tbody>
              {shown.map((o) => (
                <tr key={o.id} className={`clickable ${openId === o.id ? "selected" : ""}`} onClick={() => setOpenId(o.id)}>
                  <td>
                    <b>{o.code}</b> {o.priority === "high" && <span className="prio">HIGH</span>}
                    <div className="muted small">{when(o.created_at)} · {o.item_count} item(s)</div>
                  </td>
                  {isAdmin && <td>{o.customer}</td>}
                  <td><SourceTag source={o.source} /></td>
                  <td><Confidence value={o.ai_confidence} /></td>
                  <td>{inr(o.total)}</td>
                  <td><StatusChip status={o.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        {detail && (
          <section className="card detail">
            <div className="detail-head">
              <div>
                <h2>{detail.code}</h2>
                <div className="muted small">{detail.customer} · <SourceTag source={detail.source} /></div>
              </div>
              <button className="icon-btn" onClick={() => setOpenId(null)} title="Close">✕</button>
            </div>

            {detail.status === "cancelled" || detail.status === "on_hold" ? (
              <div className={`banner banner-${detail.status}`}><StatusChip status={detail.status} /></div>
            ) : (
              <div className="pipeline">
                {PIPELINE.map((s, i) => (
                  <div key={s} className={`pipe ${i <= step ? "done" : ""} ${i === step ? "current" : ""}`}>
                    <span className="pipe-dot" />
                    <span className="small">{STATUS_LABELS[s]}</span>
                  </div>
                ))}
              </div>
            )}

            <table className="table compact">
              <thead><tr><th>Item</th><th>Qty</th><th>Match</th><th>Amount</th></tr></thead>
              <tbody>
                {detail.items.map((i) => (
                  <tr key={i.product_id}>
                    <td>{i.name}<div className="muted small">{i.sku} {i.status === "short" && <span className="pink-text">· short</span>}</div></td>
                    <td>{i.quantity}</td>
                    <td>{Math.round(i.match_score)}%</td>
                    <td>{inr(i.line_total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="total right">Total <b>{inr(detail.total)}</b></div>

            {detail.raw_text && (
              <details className="raw">
                <summary>Original message</summary>
                <pre>{detail.raw_text}</pre>
              </details>
            )}

            <h3 className="mt">Timeline</h3>
            <ol className="timeline">
              {detail.events.map((e, i) => (
                <li key={i}><span className="muted small">{when(e.time)}</span><div>{e.message}</div></li>
              ))}
            </ol>

            {actions.length > 0 && (
              <div className="actions">
                {actions.map((s) => (
                  <button key={s} className={s === "cancelled" ? "ghost danger" : "primary slim"} onClick={() => changeStatus(s)}>
                    {s === "cancelled" ? "Cancel order" : `Mark as ${STATUS_LABELS[s].toLowerCase()}`}
                  </button>
                ))}
              </div>
            )}
          </section>
        )}
      </div>
    </div>
  );
}
