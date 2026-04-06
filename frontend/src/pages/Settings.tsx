import { useEffect, useState } from "react";
import { Send, Check } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import api from "../api/client";

export default function Settings() {
  const { user, refreshUser } = useAuth();
  const [telegram, setTelegram] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (user?.idtelegram != null) {
      setTelegram(String(user.idtelegram));
    }
  }, [user]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSaved(false);

    const val = telegram.trim();
    const parsed = val === "" ? null : parseInt(val, 10);
    if (val !== "" && (isNaN(parsed!) || String(parsed) !== val)) {
      setError("Inserisci un ID Telegram numerico valido.");
      return;
    }

    setSaving(true);
    try {
      await api.patch("/auth/me", { idtelegram: parsed });
      await refreshUser();
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Errore durante il salvataggio.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="pg">
      <div className="pg-title">Impostazioni</div>

      <div className="table-card" style={{ maxWidth: 480 }}>
        <div style={{ padding: "1.25rem 1.5rem" }}>
          <div style={{ fontWeight: 700, fontSize: "1rem", marginBottom: "0.25rem" }}>Profilo</div>
          <p style={{ fontSize: ".85rem", color: "var(--txt-muted)", marginBottom: "1.5rem" }}>
            Modifica le informazioni del tuo account.
          </p>

          {/* Read-only info */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginBottom: "1.5rem" }}>
            <div>
              <div className="modal-label">Username</div>
              <div style={{
                padding: "9px 13px",
                background: "var(--bg-3)",
                border: "1px solid var(--border-2)",
                borderRadius: "var(--radius-sm)",
                fontSize: ".9rem",
                color: "var(--txt-muted)",
              }}>{user?.username ?? "—"}</div>
            </div>
            <div>
              <div className="modal-label">Ruolo</div>
              <div style={{
                padding: "9px 13px",
                background: "var(--bg-3)",
                border: "1px solid var(--border-2)",
                borderRadius: "var(--radius-sm)",
                fontSize: ".9rem",
              }}>
                <span className={`role-badge ${user?.ruolo}`}>{user?.ruolo ?? "—"}</span>
              </div>
            </div>
          </div>

          {/* Telegram form */}
          <form onSubmit={handleSubmit}>
            <div className="modal-label">ID Telegram</div>
            <p style={{ fontSize: ".78rem", color: "var(--txt-muted)", marginBottom: "0.5rem" }}>
              Lascia vuoto per rimuoverlo.
            </p>
            <div style={{ display: "flex", gap: "0.6rem", alignItems: "center", flexWrap: "wrap" }}>
              <input
                type="number"
                className="login-input"
                style={{ flex: "1 1 180px", maxWidth: "260px" }}
                placeholder="es. 123456789"
                value={telegram}
                onChange={(e) => setTelegram(e.target.value)}
                disabled={saving}
              />
              <button type="submit" className="btn btn-primary" disabled={saving} style={{ flex: "0 0 auto" }}>
                {saved
                  ? <><Check size={14} /> Salvato</>
                  : saving
                    ? "Salvataggio…"
                    : <><Send size={14} /> Salva</>
                }
              </button>
            </div>
            {error && <div className="login-error" style={{ marginTop: "0.6rem" }}>{error}</div>}
          </form>
        </div>
      </div>
    </div>
  );
}
