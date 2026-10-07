import { useEffect, useRef, useState } from "react";
import { api, inr } from "../api.js";
import { Confidence } from "../components/ui.jsx";

const SAMPLES = {
  chat: "Hi, please send 10 wireless mice, 5 USB-C cables and three keybords.\nAlso need 2 dozen A4 paper reams urgently by Friday.",
  email:
    "Subject: Purchase order - new office setup\n\nDear Sales Team,\n\nPlease process the following order:\n- 4x HDMI cable 2m\n- Ergonomic office chair 2 nos\n- half a dozen whiteboard markers\n- 20 sticky notes\n- 1 quantum flux capacitor\n\nKindly deliver by 15 Oct.\n\nRegards,\nNeha Kapoor",
};

export default function NewOrder({ user, onPlaced }) {
  const [text, setText] = useState("");
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);
  const [lines, setLines] = useState([]);
  const [priority, setPriority] = useState("normal");
  const [products, setProducts] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const fileInput = useRef(null);

  useEffect(() => {
    api("/products").then(setProducts).catch((e) => setError(e.message));
  }, []);

  const byId = Object.fromEntries(products.map((p) => [p.id, p]));

  async function runExtract() {
    setError("");
    setBusy(true);
    try {
      const form = new FormData();
      form.append("text", text);
      if (file) form.append("file", file);
      const data = await api("/orders/extract", { method: "POST", form });
      setResult(data);
      setPriority(data.priority);
      setLines(data.items.map((i) => ({ product_id: i.product_id, quantity: i.quantity, confidence: i.confidence, source_text: i.source_text })));
      if (data.items.length === 0) setError("No products were recognised. Check the spelling or add items manually below.");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  function update(i, patch) {
    setLines(lines.map((l, j) => (j === i ? { ...l, ...patch } : l)));
  }

  function addLine(source_text = "") {
    const first = products[0];
    if (first) setLines([...lines, { product_id: first.id, quantity: 1, confidence: 100, source_text, manual: true }]);
  }

  async function place() {
    setError("");
    setBusy(true);
    try {
      const order = await api("/orders", {
        method: "POST",
        body: {
          source: result?.source || "manual",
          raw_text: result?.raw_text || text,
          priority,
          items: lines.map((l) => ({ product_id: Number(l.product_id), quantity: Number(l.quantity), confidence: l.manual ? 100 : l.confidence })),
        },
      });
      onPlaced(order.id);
    } catch (e) {
      setError(e.message);
      setBusy(false);
    }
  }

  const total = lines.reduce((sum, l) => sum + (byId[l.product_id]?.price || 0) * Number(l.quantity || 0), 0);

  return (
    <div className="page-stack">
      <header className="page-head">
        <div>
          <div className="eyebrow">{user.role === "admin" ? "AI order intake" : "New order"}</div>
          <h1>Turn any message into an order</h1>
        </div>
        <span className="pill">Offline NLP · No API key</span>
      </header>

      <div className="grid-intake">
        <section className="card intake">
          <div className="card-title">
            <span className="step">1</span>
            <h3>Paste the order or upload a file</h3>
          </div>
          <div className="sample-row">
            <span className="muted small">Try a sample:</span>
            <button className="chip-btn" onClick={() => { setText(SAMPLES.chat); setFile(null); }}>💬 Chat message</button>
            <button className="chip-btn" onClick={() => { setText(SAMPLES.email); setFile(null); }}>✉ Email</button>
          </div>
          <textarea
            rows={9}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="e.g. Please send 10 wireless mice and 5 USB-C cables by Friday"
          />
          <div
            className={`dropzone ${file ? "has-file" : ""}`}
            onClick={() => fileInput.current.click()}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => { e.preventDefault(); setFile(e.dataTransfer.files[0]); }}
            role="button"
            tabIndex={0}
          >
            {file ? (
              <><b>{file.name}</b><span className="muted small"> · click to change</span></>
            ) : (
              <>📎 Drop a <b>.pdf</b> purchase order, <b>.eml</b> email or <b>.txt</b> file here</>
            )}
            <input ref={fileInput} type="file" accept=".pdf,.eml,.txt" hidden onChange={(e) => setFile(e.target.files[0] || null)} />
          </div>
          {file && <button className="link-btn left" onClick={() => setFile(null)}>Remove file</button>}
          <button className="primary" onClick={runExtract} disabled={busy || (!text.trim() && !file)}>
            {busy && !result ? "Reading order…" : "✦ Extract order with AI"}
          </button>
        </section>

        <section className="card review">
          <div className="card-title">
            <span className="step">2</span>
            <h3>Review and confirm</h3>
            {result && <span className="muted small push">read from {result.source}</span>}
          </div>

          {!result && lines.length === 0 && (
            <div className="empty">
              <div className="empty-ring" />
              <p className="muted">The extracted products, quantities and AI confidence will appear here. You can correct anything before placing the order.</p>
            </div>
          )}

          {result && (
            <div className="insights">
              <div><span className="muted small">Lines found</span><b>{result.items.length}</b></div>
              <div><span className="muted small">AI confidence</span><b>{result.confidence}%</b></div>
              <div><span className="muted small">Priority</span><b className={priority === "high" ? "pink-text" : ""}>{priority}</b></div>
              <div><span className="muted small">Delivery</span><b>{result.delivery_hint || "—"}</b></div>
            </div>
          )}

          {lines.length > 0 && (
            <table className="table edit-table">
              <thead>
                <tr><th>Product</th><th>Qty</th><th>AI match</th><th>Stock</th><th>Total</th><th /></tr>
              </thead>
              <tbody>
                {lines.map((l, i) => {
                  const p = byId[l.product_id];
                  const short = p && p.stock < l.quantity;
                  return (
                    <tr key={i}>
                      <td>
                        <select value={l.product_id} onChange={(e) => update(i, { product_id: Number(e.target.value), manual: true })}>
                          {products.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
                        </select>
                        {l.source_text && <div className="muted small quote">“{l.source_text}”</div>}
                      </td>
                      <td><input className="qty" type="number" min="1" value={l.quantity} onChange={(e) => update(i, { quantity: e.target.value })} /></td>
                      <td>{l.manual ? <span className="muted small">manual</span> : <Confidence value={l.confidence} />}</td>
                      <td className={short ? "pink-text" : "ok-text"}>{p ? (short ? `only ${p.stock}` : "✓ ok") : ""}</td>
                      <td>{p ? inr(p.price * l.quantity) : ""}</td>
                      <td><button className="icon-btn" title="Remove" onClick={() => setLines(lines.filter((_, j) => j !== i))}>✕</button></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}

          {result?.unmatched?.length > 0 && (
            <div className="unmatched">
              <b>Not in the catalog</b>
              {result.unmatched.map((u, i) => (
                <div key={i} className="unmatched-row">
                  <span>“{u.text}”</span>
                  <button className="link-btn" onClick={() => addLine(u.text)}>Map to a product</button>
                </div>
              ))}
            </div>
          )}

          {(result || lines.length > 0) && (
            <>
              <div className="review-foot">
                <button className="ghost" onClick={() => addLine()}>+ Add item</button>
                <label className="toggle">
                  <input type="checkbox" checked={priority === "high"} onChange={(e) => setPriority(e.target.checked ? "high" : "normal")} />
                  High priority
                </label>
                <div className="total">Total <b>{inr(total)}</b></div>
              </div>
              <button className="primary" onClick={place} disabled={busy || lines.length === 0}>
                {busy && result ? "Placing order…" : `Place order (${lines.length} item${lines.length === 1 ? "" : "s"})`}
              </button>
            </>
          )}
          {error && <p className="error">{error}</p>}
        </section>
      </div>
    </div>
  );
}
