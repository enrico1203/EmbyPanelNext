import { useEffect, useMemo, useState } from "react";
import { Navigate } from "react-router-dom";
import { LoaderCircle, Save, Tv } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import api from "../api/client";

interface ProvisioningOptions {
  credito: number;
  prices: Record<string, Record<string, number>>;
  free_days_threshold: number;
}

interface ProvisioningResult {
  message: string;
  server: string;
  cost: number;
  remaining_credit: number;
}

function calcCost(monthlyPrice: number, days: number, freeDaysThreshold: number) {
  if (!days || days <= freeDaysThreshold) return 0;
  return Math.round(monthlyPrice * (days / 30.416) * 100) / 100;
}

export default function CreateEmbyUser() {
  const { user, refreshUser } = useAuth();
  const [options, setOptions] = useState<ProvisioningOptions | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState<ProvisioningResult | null>(null);
  const [form, setForm] = useState({
    username: "",
    password: "",
    accountType: "normale",
    expiryDays: "30",
    screens: "1",
  });

  useEffect(() => {
    api.get("/provisioning/options")
      .then((response) => setOptions(response.data))
      .catch((err: any) => setError(err?.response?.data?.detail ?? "Errore durante il caricamento dei prezzi."))
      .finally(() => setLoading(false));
  }, []);

  if (!user) return <Navigate to="/login" replace />;

  const monthlyPrice = useMemo(() => {
    if (!options) return 0;
    const service = form.accountType === "premium" ? "emby_premium" : "emby_normale";
    return options.prices?.[service]?.[form.screens] ?? 0;
  }, [form.accountType, form.screens, options]);

  const cost = useMemo(() => {
    if (!options) return 0;
    return calcCost(monthlyPrice, Number(form.expiryDays) || 0, options.free_days_threshold);
  }, [form.expiryDays, monthlyPrice, options]);

  const remainingCredit = useMemo(() => {
    const current = Number(user.credito ?? 0);
    return user.ruolo === "admin" ? current : Math.round((current - cost) * 100) / 100;
  }, [cost, user.credito, user.ruolo]);

  const setField = (key: string, value: string) => {
    setError("");
    setSuccess(null);
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    setSuccess(null);
    try {
      const response = await api.post("/provisioning/emby", {
        username: form.username,
        password: form.password,
        account_type: form.accountType,
        expiry_days: Number(form.expiryDays),
        screens: Number(form.screens),
      });
      setSuccess(response.data);
      setForm({
        username: "",
        password: "",
        accountType: form.accountType,
        expiryDays: "30",
        screens: "1",
      });
      await refreshUser();
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Errore durante la creazione dell'utente Emby.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="pg">
      <div className="manage-header">
        <div>
          <div className="pg-title" style={{ marginBottom: "0.35rem" }}>
            <Tv size={18} />
            <span>Crea Utente Emby</span>
          </div>
          <p className="manage-subtitle">
            Emby normale va nel server normale meno usato. Emby premium usa il premium meno usato ma solo con `limite = no`.
          </p>
        </div>
      </div>

      {error && <div className="login-error">{error}</div>}
      {success && (
        <div className="save-success">
          {success.message}. Server: {success.server}. Costo: {success.cost.toFixed(2)} crediti. Credito residuo: {success.remaining_credit.toFixed(2)} crediti.
        </div>
      )}

      {loading ? (
        <div className="loading-wrap"><div className="spinner" /></div>
      ) : (
        <div className="create-grid">
          <section className="config-section">
            <div className="config-section-header">
              <div>
                <h2>Dati account</h2>
                <p>Username alfanumerico, password di almeno 5 caratteri con almeno un numero.</p>
              </div>
            </div>

            <form className="manage-form" onSubmit={handleSubmit}>
              <div className="config-fields-grid">
                <label className="config-field">
                  <span>Username</span>
                  <input type="text" value={form.username} onChange={(e) => setField("username", e.target.value)} placeholder="Inserisci username" />
                </label>
                <label className="config-field">
                  <span>Password</span>
                  <input type="text" value={form.password} onChange={(e) => setField("password", e.target.value)} placeholder="Inserisci password" />
                </label>
                <label className="config-field">
                  <span>Tipo Emby</span>
                  <select value={form.accountType} onChange={(e) => setField("accountType", e.target.value)}>
                    <option value="normale">Normale</option>
                    <option value="premium">Premium</option>
                  </select>
                </label>
                <label className="config-field">
                  <span>Scadenza in giorni</span>
                  <input type="number" min="1" value={form.expiryDays} onChange={(e) => setField("expiryDays", e.target.value)} />
                </label>
                <label className="config-field">
                  <span>Streaming contemporanei</span>
                  <select value={form.screens} onChange={(e) => setField("screens", e.target.value)}>
                    <option value="1">1</option>
                    <option value="2">2</option>
                    <option value="3">3</option>
                    <option value="4">4</option>
                  </select>
                </label>
              </div>

              <div className="manage-footer">
                <button className="btn btn-primary" type="submit" disabled={submitting}>
                  {submitting ? <LoaderCircle size={15} className="spin-inline" /> : <Save size={15} />}
                  Crea utente Emby
                </button>
              </div>
            </form>
          </section>

          <aside className="create-summary">
            <div className="create-summary-label">Riepilogo</div>
            <div className="create-summary-value">{cost.toFixed(2)} crediti</div>
            <div className="create-summary-meta">Prezzo mensile base: {monthlyPrice.toFixed(2)} crediti</div>
            <div className="create-summary-meta">Credito attuale: {Number(user.credito ?? 0).toFixed(2)} crediti</div>
            <div className="create-summary-meta">Credito residuo stimato: {remainingCredit.toFixed(2)} crediti</div>
            <div className="create-note" style={{ marginTop: "14px" }}>
              Fino a {options?.free_days_threshold ?? 3} giorni il costo resta a 0 crediti.
            </div>
          </aside>
        </div>
      )}
    </div>
  );
}
