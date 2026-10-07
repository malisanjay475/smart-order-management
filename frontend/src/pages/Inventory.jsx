import { useEffect, useState } from "react";
import { api, inr } from "../api.js";

const EMPTY = { sku: "", name: "", aliases: "", category: "General", unit: "pcs", price: "", stock: "", reorder_level: 10 };

export default function Inventory() {
  const [products, setProducts] = useState([]);
  const [query, setQuery] = useState("");
  const [edits, setEdits] = useState({});
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  const load = () => api("/products").then(setProducts).catch((e) => setError(e.message));
  useEffect(() => { load(); }, []);

  async function save(p) {
    setError(""); setMsg("");
    const e = edits[p.id];
    try {
      const res = await api(`/products/${p.id}`, {
        method: "PATCH",
        body: { stock: Number(e.stock ?? p.stock), price: Number(e.price ?? p.price) },
      });
      setEdits({ ...edits, [p.id]: undefined });
      setMsg(res.orders_retried ? `${p.name} saved. ${res.orders_retried} order(s) on hold sent back to the queue.` : `${p.name} saved.`);
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function add(e) {
    e.preventDefault();
    setError(""); setMsg("");
    try {
      await api("/products", { method: "POST", body: { ...form, price: Number(form.price), stock: Number(form.stock), reorder_level: Number(form.reorder_level) } });
      setForm(EMPTY); setAdding(false); setMsg("Product added. The AI can now recognise it in orders."); load();
    } catch (err) {
      setError(err.message);
    }
  }

  const q = query.toLowerCase();
  const shown = products.filter((p) => !q || `${p.name} ${p.sku} ${p.category} ${p.aliases}`.toLowerCase().includes(q));
  const low = products.filter((p) => p.low_stock).length;
  const value = products.reduce((s, p) => s + p.price * p.stock, 0);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  return (
    <div className="page-stack">
      <header className="page-head">
        <div>
          <div className="eyebrow">Catalog & stock</div>
          <h1>Inventory</h1>
        </div>
        <button className="primary slim" onClick={() => setAdding(!adding)}>{adding ? "Close" : "+ Add product"}</button>
      </header>

      <div className="stats three">
        <div className="card stat"><div className="muted small upper">Products</div><div className="stat-value">{products.length}</div></div>
        <div className="card stat stat-pink"><div className="muted small upper">Low stock</div><div className="stat-value">{low}</div></div>
        <div className="card stat stat-violet"><div className="muted small upper">Stock value</div><div className="stat-value">{inr(value)}</div></div>
      </div>

      {adding && (
        <form className="card add-form" onSubmit={add}>
          <label>SKU<input value={form.sku} onChange={set("sku")} required placeholder="ELC-120" /></label>
          <label>Name<input value={form.name} onChange={set("name")} required /></label>
          <label className="wide">Other names the AI should recognise (comma-separated)<input value={form.aliases} onChange={set("aliases")} placeholder="e.g. usb hub, usb splitter" /></label>
          <label>Category<input value={form.category} onChange={set("category")} /></label>
          <label>Unit<input value={form.unit} onChange={set("unit")} /></label>
          <label>Price (₹)<input type="number" min="1" step="0.01" value={form.price} onChange={set("price")} required /></label>
          <label>Stock<input type="number" min="0" value={form.stock} onChange={set("stock")} required /></label>
          <label>Reorder level<input type="number" min="0" value={form.reorder_level} onChange={set("reorder_level")} /></label>
          <button className="primary slim">Save product</button>
        </form>
      )}

      {msg && <p className="ok-text">{msg}</p>}
      {error && <p className="error">{error}</p>}

      <section className="card">
        <input className="search" placeholder="Search by name, SKU, category or alias…" value={query} onChange={(e) => setQuery(e.target.value)} />
        <table className="table">
          <thead><tr><th>SKU</th><th>Product</th><th>Category</th><th>Price</th><th>Stock level</th><th>Stock</th><th /></tr></thead>
          <tbody>
            {shown.map((p) => {
              const e = edits[p.id] || {};
              const pct = Math.min(100, (p.stock / Math.max(p.reorder_level * 4, 1)) * 100);
              const dirty = e.stock !== undefined || e.price !== undefined;
              return (
                <tr key={p.id}>
                  <td className="mono">{p.sku}</td>
                  <td><b>{p.name}</b><div className="muted small">{p.aliases.split(",").slice(0, 3).join(", ")}</div></td>
                  <td>{p.category}</td>
                  <td><input className="qty" type="number" value={e.price ?? p.price} onChange={(ev) => setEdits({ ...edits, [p.id]: { ...e, price: ev.target.value } })} /></td>
                  <td>
                    <div className="stock-bar"><div className={`stock-fill ${p.low_stock ? "low" : ""}`} style={{ width: `${pct}%` }} /></div>
                    <div className={`small ${p.low_stock ? "pink-text" : "muted"}`}>{p.low_stock ? `Reorder (level ${p.reorder_level})` : `Reorder at ${p.reorder_level}`}</div>
                  </td>
                  <td><input className="qty" type="number" min="0" value={e.stock ?? p.stock} onChange={(ev) => setEdits({ ...edits, [p.id]: { ...e, stock: ev.target.value } })} /></td>
                  <td>{dirty && <button className="primary slim" onClick={() => save(p)}>Save</button>}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>
    </div>
  );
}
