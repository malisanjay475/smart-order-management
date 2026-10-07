import { useState } from "react";
import { api, setToken } from "../api.js";

const DEMO = {
  admin: { email: "admin@smartorders.local", password: "admin123" },
  customer: { email: "customer@smartorders.local", password: "customer123" },
};

export default function Login({ onLogin }) {
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  async function submit(e, override) {
    e?.preventDefault();
    setError("");
    setBusy(true);
    try {
      const body = override || (mode === "login" ? { email: form.email, password: form.password } : form);
      const data = await api(mode === "login" || override ? "/auth/login" : "/auth/register", {
        method: "POST",
        body,
      });
      setToken(data.token);
      onLogin(data.user);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-wrap">
      <section className="login-hero">
        <div className="brand big">
          <span className="logo-dot" />
          <span>Smart<span className="gradient">Orders</span></span>
        </div>
        <h1>
          Orders in plain English.<br />
          <span className="gradient">Processed by AI.</span>
        </h1>
        <p className="muted">
          Paste a message, forward an email or upload a PDF purchase order. The NLP engine finds every product and
          quantity, checks stock and queues the order for processing automatically.
        </p>
        <div className="hero-steps">
          <div><b>01</b> Read text, email or PDF</div>
          <div><b>02</b> Match items to the catalog</div>
          <div><b>03</b> Check and reserve stock</div>
        </div>
      </section>

      <form className="card login-card" onSubmit={submit}>
        <h2>{mode === "login" ? "Welcome back" : "Create a customer account"}</h2>
        {mode === "register" && (
          <label>Name<input value={form.name} onChange={set("name")} required minLength={2} /></label>
        )}
        <label>Email<input type="email" value={form.email} onChange={set("email")} required /></label>
        <label>
          Password
          <input type="password" value={form.password} onChange={set("password")} required minLength={mode === "register" ? 6 : 1} />
        </label>
        {error && <p className="error">{error}</p>}
        <button className="primary" disabled={busy}>{busy ? "Please wait…" : mode === "login" ? "Log in" : "Sign up"}</button>
        <button type="button" className="link-btn" onClick={() => setMode(mode === "login" ? "register" : "login")}>
          {mode === "login" ? "New customer? Create an account" : "Have an account? Log in"}
        </button>
        <div className="demo-box">
          <span className="muted small">Demo accounts</span>
          <div className="demo-btns">
            <button type="button" className="ghost" onClick={() => submit(null, DEMO.admin)}>Admin demo</button>
            <button type="button" className="ghost" onClick={() => submit(null, DEMO.customer)}>Customer demo</button>
          </div>
        </div>
      </form>
    </div>
  );
}
