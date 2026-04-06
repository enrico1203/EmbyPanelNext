import { useEffect, useState } from "react";
import { Navigate, useParams, useNavigate } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import api from "../api/client";

interface Reseller {
  id: number;
  username: string;
  master: number | null;
  credito: number;
  idtelegram: number | null;
  ruolo: string;
}

export default function ResellerDetail() {
  const { user, refreshUser } = useAuth();
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [reseller, setReseller] = useState<Reseller | null>(null);
  const [loading, setLoading] = useState(true);
  const [amount, setAmount] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const canAccess = user?.ruolo === "admin" || user?.ruolo === "master";
  if (!canAccess) return <Navigate to="/dashboard" replace />;

  useEffect(() => {
    api.get(`/reseller/my-resellers/${id}`)
      .then((r) => setReseller(r.data))
      .catch(() => navigate("/resellers", { replace: true }))
      .finally(() => setLoading(false));
  }, [id]);

  const handleRicarica = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    const amt = parseInt(amount, 10);
    if (isNaN(amt) || amt < 10) {
      setError("Il trasferimento minimo è 10 crediti.");
      return;
    }
    if (amt > (user?.credito ?? 0)) {
      setError("Crediti insufficienti.");
      return;
    }
    setSending(true);
    try {
      const r = await api.post(`/reseller/my-resellers/${id}/ricarica`, { amount: amt });
      setReseller((prev) => prev ? { ...prev, credito: r.data.reseller_new_balance, ruolo: r.data.reseller_ruolo } : prev);
      await refreshUser();
      setSuccess(`Trasferiti ${amt} crediti. Nuovo saldo reseller: ${r.data.reseller_new_balance}`);
      setAmount("");
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Errore durante il trasferimento.");
    } finally {
      setSending(false);
    }
  };

  if (loading) return <div className="pg"><div className="loading-wrap"><div className="spinner" /></div></div>;

  if (!reseller) return null;

  return (
    <div className="pg">
      <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1.5rem" }}>
        <button className="btn btn-ghost" onClick={() => navigate("/resellers")}>
          <ArrowLeft size={15} /> Indietro
        </button>
        <div className="pg-title" style={{ margin: 0 }}>Dettaglio Reseller</div>
      </div>

      <div className="table-card" style={{ marginBottom: "1.5rem" }}>
        <div style={{ padding: "1.25rem 1.5rem", display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: "1rem" }}>
          <div>
            <div style={{ fontSize: ".72rem", color: "var(--txt-muted)", textTransform: "uppercase", letterSpacing: ".06em", marginBottom: ".25rem" }}>ID</div>
            <div style={{ fontWeight: 600, color: "var(--txt-muted)", fontSize: ".85rem" }}>#{reseller.id}</div>
          </div>
          <div>
            <div style={{ fontSize: ".72rem", color: "var(--txt-muted)", textTransform: "uppercase", letterSpacing: ".06em", marginBottom: ".25rem" }}>Username</div>
            <div style={{ fontWeight: 700 }}>{reseller.username}</div>
          </div>
          <div>
            <div style={{ fontSize: ".72rem", color: "var(--txt-muted)", textTransform: "uppercase", letterSpacing: ".06em", marginBottom: ".25rem" }}>Credito</div>
            <div style={{ fontWeight: 700 }}>{reseller.credito}</div>
          </div>
          <div>
            <div style={{ fontSize: ".72rem", color: "var(--txt-muted)", textTransform: "uppercase", letterSpacing: ".06em", marginBottom: ".25rem" }}>Ruolo</div>
            <span className={`role-badge ${reseller.ruolo}`}>{reseller.ruolo}</span>
          </div>
        </div>
      </div>

      <div className="table-card">
        <div style={{ padding: "1.25rem 1.5rem" }}>
          <div style={{ fontWeight: 700, marginBottom: "1rem", fontSize: "1rem" }}>Ricarica Crediti</div>
          <p style={{ fontSize: ".85rem", color: "var(--txt-muted)", marginBottom: "1rem" }}>
            I tuoi crediti: <strong style={{ color: "var(--txt)" }}>{user?.credito}</strong> &nbsp;|&nbsp; Min: 10 &nbsp;|&nbsp; Max: {user?.credito}
          </p>
          <form onSubmit={handleRicarica} style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap", alignItems: "center" }}>
            <input
              type="number"
              className="login-input"
              placeholder="Importo crediti"
              value={amount}
              min={10}
              max={user?.credito}
              onChange={(e) => setAmount(e.target.value)}
              style={{ maxWidth: "200px", flex: "1 1 140px" }}
              disabled={sending}
            />
            <button type="submit" className="btn btn-primary" disabled={sending} style={{ flex: "0 0 auto" }}>
              {sending ? "Invio…" : "Trasferisci"}
            </button>
          </form>
          {error && <div className="login-error" style={{ marginTop: "0.75rem" }}>{error}</div>}
          {success && (
            <div style={{ marginTop: "0.75rem", padding: "0.6rem 1rem", background: "rgba(34,197,94,.1)", border: "1px solid rgba(34,197,94,.3)", borderRadius: "8px", fontSize: ".85rem", color: "#4ade80" }}>
              {success}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
