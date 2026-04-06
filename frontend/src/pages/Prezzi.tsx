import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { Save } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import api from "../api/client";

const SERVIZI: [string, string][] = [
  ["emby_normale", "Emby Normale"],
  ["emby_premium", "Emby Premium"],
  ["jellyfin", "Jellyfin"],
  ["plex", "Plex"],
];

type PrezziMap = Record<string, Record<number, string>>;

function buildEmpty(): PrezziMap {
  const map: PrezziMap = {};
  for (const [key] of SERVIZI) {
    map[key] = { 1: "", 2: "", 3: "", 4: "" };
  }
  return map;
}

export default function Prezzi() {
  const { user } = useAuth();
  if (user?.ruolo !== "admin") return <Navigate to="/dashboard" replace />;

  const [values, setValues] = useState<PrezziMap>(buildEmpty());
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    api.get("/admin/prezzi").then((r) => {
      const map = buildEmpty();
      for (const row of r.data) {
        if (map[row.servizio]) {
          map[row.servizio][row.streaming] =
            row.prezzo_mensile != null ? String(row.prezzo_mensile) : "";
        }
      }
      setValues(map);
    }).finally(() => setLoading(false));
  }, []);

  const handleChange = (servizio: string, schermi: number, val: string) => {
    setValues((prev) => ({
      ...prev,
      [servizio]: { ...prev[servizio], [schermi]: val },
    }));
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess(false);

    const prezzi: { servizio: string; streaming: number; prezzo_mensile: number | null }[] = [];
    for (const [servizio] of SERVIZI) {
      for (let s = 1; s <= 4; s++) {
        const raw = values[servizio][s].trim();
        if (raw === "") {
          prezzi.push({ servizio, streaming: s, prezzo_mensile: null });
        } else {
          const n = parseFloat(raw);
          if (isNaN(n) || n < 0) {
            setError(`Valore non valido per ${servizio} / ${s} schermi.`);
            return;
          }
          prezzi.push({ servizio, streaming: s, prezzo_mensile: Math.round(n * 100) / 100 });
        }
      }
    }

    setSaving(true);
    try {
      await api.put("/admin/prezzi", { prezzi });
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Errore durante il salvataggio.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="pg">
      <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1.5rem", flexWrap: "wrap" }}>
        <div className="pg-title" style={{ margin: 0 }}>Gestione Prezzi</div>
        <span style={{
          padding: "3px 10px",
          borderRadius: "999px",
          fontSize: ".72rem",
          fontWeight: 700,
          background: "rgba(61,213,165,0.12)",
          color: "#3dd5a5",
          border: "1px solid rgba(61,213,165,0.3)",
          letterSpacing: ".05em",
          textTransform: "uppercase",
        }}>Admin</span>
      </div>

      <div className="table-card" style={{ maxWidth: 700 }}>
        <div style={{ padding: "1rem 1.5rem 0.5rem", fontSize: ".83rem", color: "var(--txt-muted)" }}>
          Modifica i prezzi mensili per servizio e numero di schermi. Lascia vuoto per impostare come non configurato.
        </div>

        {loading ? (
          <div className="loading-wrap" style={{ padding: "2rem" }}><div className="spinner" /></div>
        ) : (
          <form onSubmit={handleSave}>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Servizio</th>
                    <th>1 schermo</th>
                    <th>2 schermi</th>
                    <th>3 schermi</th>
                    <th>4 schermi</th>
                  </tr>
                </thead>
                <tbody>
                  {SERVIZI.map(([key, label]) => (
                    <tr key={key}>
                      <td style={{ fontWeight: 700, whiteSpace: "nowrap" }}>{label}</td>
                      {[1, 2, 3, 4].map((s) => (
                        <td key={s} style={{ padding: "8px 10px" }}>
                          <input
                            type="number"
                            step="0.01"
                            min="0"
                            className="login-input"
                            style={{ width: "100%", minWidth: 80, padding: "7px 10px", fontSize: ".85rem" }}
                            placeholder="—"
                            value={values[key][s]}
                            onChange={(e) => handleChange(key, s, e.target.value)}
                            disabled={saving}
                          />
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div style={{ padding: "1rem 1.5rem", display: "flex", alignItems: "center", gap: "1rem", flexWrap: "wrap" }}>
              <button type="submit" className="btn btn-primary" disabled={saving}>
                <Save size={14} />
                {saving ? "Salvataggio…" : "Salva prezzi"}
              </button>
              {success && (
                <span style={{ fontSize: ".85rem", color: "#4ade80" }}>Prezzi salvati con successo.</span>
              )}
              {error && (
                <span style={{ fontSize: ".85rem", color: "var(--red)" }}>{error}</span>
              )}
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
