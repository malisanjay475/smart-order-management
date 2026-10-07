import { useEffect, useState } from "react";
import { api, getToken, setToken } from "./api.js";
import Login from "./pages/Login.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import NewOrder from "./pages/NewOrder.jsx";
import Orders from "./pages/Orders.jsx";
import Inventory from "./pages/Inventory.jsx";

const ADMIN_PAGES = [
  { id: "dashboard", label: "Dashboard", icon: "◆" },
  { id: "new", label: "AI Order Intake", icon: "✦" },
  { id: "orders", label: "Orders", icon: "≡" },
  { id: "inventory", label: "Inventory", icon: "▦" },
];
const CUSTOMER_PAGES = [
  { id: "new", label: "Place Order", icon: "✦" },
  { id: "orders", label: "My Orders", icon: "≡" },
];

export default function App() {
  const [user, setUser] = useState(null);
  const [checking, setChecking] = useState(Boolean(getToken()));
  const [page, setPage] = useState("dashboard");
  const [openOrder, setOpenOrder] = useState(null);

  useEffect(() => {
    if (getToken()) {
      api("/auth/me")
        .then(onLogin)
        .catch(() => setToken(null))
        .finally(() => setChecking(false));
    }
    const out = () => setUser(null);
    window.addEventListener("som-logout", out);
    return () => window.removeEventListener("som-logout", out);
  }, []);

  function onLogin(u) {
    setUser(u);
    setPage(u.role === "admin" ? "dashboard" : "new");
  }

  function logout() {
    setToken(null);
    setUser(null);
  }

  function showOrder(id) {
    setOpenOrder(id);
    setPage("orders");
  }

  if (checking) return <div className="center-screen"><div className="spinner" /></div>;
  if (!user) return <Login onLogin={onLogin} />;

  const pages = user.role === "admin" ? ADMIN_PAGES : CUSTOMER_PAGES;
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="logo-dot" />
          <span>Smart<span className="gradient">Orders</span></span>
        </div>
        <nav>
          {pages.map((p) => (
            <button key={p.id} className={`nav-item ${page === p.id ? "active" : ""}`} onClick={() => setPage(p.id)}>
              <span className="nav-icon">{p.icon}</span>
              {p.label}
            </button>
          ))}
        </nav>
        <div className="who">
          <div className="avatar">{user.name[0]}</div>
          <div>
            <div className="who-name">{user.name}</div>
            <div className="muted small">{user.role === "admin" ? "Administrator" : "Customer"}</div>
          </div>
          <button className="ghost small-btn" onClick={logout}>Log out</button>
        </div>
      </aside>

      <main className="main">
        {page === "dashboard" && <Dashboard onOpenOrder={showOrder} />}
        {page === "new" && <NewOrder user={user} onPlaced={showOrder} />}
        {page === "orders" && <Orders user={user} openId={openOrder} setOpenId={setOpenOrder} />}
        {page === "inventory" && <Inventory />}
        <footer className="footer">
          AI-Powered Smart Order Management System · Major Project · Sanjay (O22BCA16074) · BCA, Chandigarh University
        </footer>
      </main>
    </div>
  );
}
