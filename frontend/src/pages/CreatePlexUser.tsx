import { useEffect, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { LoaderCircle, MailPlus, Send } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import api from "../api/client";

interface ProvisioningOptions {
  plex_free_days: number;
  plex_gmail_only: boolean;
  plex_available_slots: number;
}

interface ProvisioningResult {
  invito: number;
  message: string;
  server: string;
  expiry_days: number;
}

export default function CreatePlexUser() {
  const { user, refreshUser } = useAuth();
  const navigate = useNavigate();
  const [options, setOptions] = useState<ProvisioningOptions | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState<ProvisioningResult | null>(null);

  useEffect(() => {
    api.get("/provisioning/options")
      .then((response) => setOptions(response.data))
      .catch((err: any) => setError(err?.response?.data?.detail ?? "Errore durante il caricamento configurazione Plex."))
      .finally(() => setLoading(false));
  }, []);

  if (!user) return <Navigate to="/login" replace />;

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    setSuccess(null);
    try {
      const response = await api.post("/provisioning/plex", { email });
      setSuccess(response.data);
      await refreshUser();
      navigate(`/lista/plex/${response.data.invito}`);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Errore durante l'invio dell'invito Plex.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="pg">
      <div className="manage-header">
        <div>
          <div className="pg-title" style={{ marginBottom: "0.35rem" }}>
            <MailPlus size={18} />
            <span>Crea Utente Plex</span>
          </div>
          <p className="manage-subtitle">
            Invito solo verso email Gmail. L'account parte gratis con {options?.plex_free_days ?? 3} giorni.
          </p>
        </div>
      </div>

      {error && <div className="login-error">{error}</div>}
      {success && (
        <div className="save-success">
          {success.message}. Server: {success.server}. Scadenza iniziale: {success.expiry_days} giorni. Costo: 0 crediti.
        </div>
      )}

      {loading ? (
        <div className="loading-wrap"><div className="spinner" /></div>
      ) : (
        <div className="create-grid">
          <section className="config-section">
            <div className="config-section-header">
              <div>
                <h2>Invito Gmail</h2>
                <p>Prima di inviare l'invito, la mail deve essere gia registrata su app.plex.tv.</p>
              </div>
            </div>

            <div className="create-note create-note-danger">
              La mail deve essere gia registrata su <strong>app.plex.tv</strong>. Sono accettate solo email Gmail.
            </div>

            <form className="manage-form" onSubmit={handleSubmit} style={{ marginTop: "18px" }}>
              <div className="config-fields-grid" style={{ gridTemplateColumns: "1fr" }}>
                <label className="config-field">
                  <span>Email Gmail</span>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => {
                      setError("");
                      setSuccess(null);
                      setEmail(e.target.value);
                    }}
                    placeholder="nome@gmail.com"
                    autoComplete="off"
                  />
                </label>
              </div>

              <div className="manage-footer">
                <button className="btn btn-primary" type="submit" disabled={submitting}>
                  {submitting ? <LoaderCircle size={15} className="spin-inline" /> : <Send size={15} />}
                  Invia invito Plex
                </button>
              </div>
            </form>
          </section>

          <aside className="create-summary">
            <div className="create-summary-label">Riepilogo</div>
            <div className="create-summary-value">0.00 crediti</div>
            <div className="create-summary-meta">Scadenza iniziale: {options?.plex_free_days ?? 3} giorni</div>
            <div className="create-summary-meta">Solo Gmail: {options?.plex_gmail_only ? "si" : "no"}</div>
            <div className="create-summary-meta">Posti disponibili Plex: {options?.plex_available_slots ?? 0}</div>
          </aside>
        </div>
      )}
    </div>
  );
}
