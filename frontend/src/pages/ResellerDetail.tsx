import { useEffect, useState } from "react";
import { Navigate, useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, Eye, EyeOff, KeyRound, X, Users, Tv, AlertTriangle, Clock3, Layers3, Film, History } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import api from "../api/client";

interface ResellerStats {
  total_users: number;
  emby_users: number;
  jelly_users: number;
  plex_users: number;
  active_users: number;
  expired_users: number;
  expiring_7_days: number;
  total_screens: number;
  total_4k_users: number;
  movements_count: number;
}

interface Reseller {
  id: number;
  username: string;
  master: number | null;
  credito: number;
  idtelegram: number | null;
  ruolo: string;
  stats: ResellerStats;
}

interface Movimento {
  id: number;
  date: string | null;
  type: string | null;
  user: string | null;
  text: string | null;
  costo: number | null;
  saldo: number | null;
}

function actionBtn(color: string, background: string, border: string) {
  return {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    minHeight: 40,
    padding: "0.7rem 1rem",
    borderRadius: 12,
    border: `1px solid ${border}`,
    background,
    color,
    fontSize: ".84rem",
    fontWeight: 700,
    cursor: "pointer",
    transition: "transform .15s ease, opacity .15s ease, box-shadow .15s ease",
  } as const;
}

function StatCard({
  icon,
  label,
  value,
  accent,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  value: React.ReactNode;
  accent?: string;
  onClick?: () => void;
}) {
  return (
    <div className="stat-card" onClick={onClick} style={onClick ? { cursor: "pointer" } : undefined} title={onClick ? "Apri dettagli" : undefined}>
      <div
        className="stat-icon"
        style={accent ? {
          color: accent,
          background: `${accent}22`,
          border: `1px solid ${accent}44`,
        } : {}}
      >
        {icon}
      </div>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
    </div>
  );
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString("it-IT", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
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
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [passwordSaving, setPasswordSaving] = useState(false);
  const [passwordError, setPasswordError] = useState("");
  const [passwordSuccess, setPasswordSuccess] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showMovementsModal, setShowMovementsModal] = useState(false);
  const [movements, setMovements] = useState<Movimento[]>([]);
  const [movementsLoading, setMovementsLoading] = useState(false);
  const [movementsError, setMovementsError] = useState("");

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
    const amt = Number.parseFloat(amount);
    if (Number.isNaN(amt) || amt < 0.1) {
      setError("Il trasferimento minimo è 0.1 crediti.");
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
      setSuccess(`Trasferiti ${amt.toFixed(2)} crediti. Nuovo saldo reseller: ${r.data.reseller_new_balance}`);
      setAmount("");
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Errore durante il trasferimento.");
    } finally {
      setSending(false);
    }
  };

  const openPasswordModal = () => {
    setPassword("");
    setPasswordConfirm("");
    setPasswordError("");
    setPasswordSuccess("");
    setShowPassword(false);
    setShowPasswordModal(true);
  };

  const closePasswordModal = () => {
    if (passwordSaving) return;
    setShowPasswordModal(false);
  };

  const openMovementsModal = async () => {
    setShowMovementsModal(true);
    setMovementsLoading(true);
    setMovementsError("");
    try {
      const response = await api.get(`/reseller/my-resellers/${id}/movimenti?limit=200`);
      setMovements(response.data);
    } catch (err: any) {
      setMovementsError(err?.response?.data?.detail ?? "Errore durante il caricamento dei movimenti.");
    } finally {
      setMovementsLoading(false);
    }
  };

  const handlePasswordSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordError("");
    setPasswordSuccess("");

    if (password.trim().length < 6) {
      setPasswordError("La password deve contenere almeno 6 caratteri.");
      return;
    }
    if (password !== passwordConfirm) {
      setPasswordError("Le password non coincidono.");
      return;
    }

    setPasswordSaving(true);
    try {
      const response = await api.post(`/reseller/my-resellers/${id}/password`, {
        password: password.trim(),
      });
      setReseller(response.data);
      setPasswordSuccess("Password aggiornata con successo.");
      setPassword("");
      setPasswordConfirm("");
      setTimeout(() => {
        setShowPasswordModal(false);
      }, 800);
    } catch (err: any) {
      setPasswordError(err?.response?.data?.detail ?? "Errore durante il cambio password.");
    } finally {
      setPasswordSaving(false);
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

      <div style={{ marginBottom: 20 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <h1 style={{ fontSize: "1.5rem", fontWeight: 800, letterSpacing: "-.02em", margin: 0 }}>{reseller.username}</h1>
          <span className={`role-badge ${reseller.ruolo}`}>{reseller.ruolo}</span>
        </div>
        <p style={{ fontSize: ".83rem", color: "var(--txt-muted)", margin: "4px 0 0" }}>
          Gestione rapida del reseller e delle sue operazioni.
        </p>
      </div>

      <div className="detail-actions" style={{ marginBottom: 22 }}>
        <button
          style={actionBtn("var(--txt-soft)", "var(--bg-3)", "var(--border-2)")}
          onClick={openPasswordModal}
        >
          <KeyRound size={15} /> Cambia Password
        </button>
      </div>

      <div className="table-card" style={{ marginBottom: "1.5rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 9, padding: "14px 18px", background: "var(--bg-3)", borderBottom: "1px solid var(--border)", fontSize: ".78rem", fontWeight: 700, color: "var(--txt-soft)", textTransform: "uppercase", letterSpacing: ".1em" }}>
          Profilo reseller
        </div>
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
          <div>
            <div style={{ fontSize: ".72rem", color: "var(--txt-muted)", textTransform: "uppercase", letterSpacing: ".06em", marginBottom: ".25rem" }}>Telegram ID</div>
            <div style={{ fontWeight: 600 }}>{reseller.idtelegram ?? "—"}</div>
          </div>
        </div>
      </div>

      <div className="table-card">
        <div style={{ padding: "1.25rem 1.5rem" }}>
          <div style={{ fontWeight: 700, marginBottom: "1rem", fontSize: "1rem" }}>Ricarica Crediti</div>
          <p style={{ fontSize: ".85rem", color: "var(--txt-muted)", marginBottom: "1rem" }}>
            I tuoi crediti: <strong style={{ color: "var(--txt)" }}>{user?.credito}</strong> &nbsp;|&nbsp; Min: 0.1 &nbsp;|&nbsp; Max: {user?.credito}
          </p>
          <form onSubmit={handleRicarica} style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap", alignItems: "center" }}>
            <input
              type="number"
              className="login-input"
              placeholder="Importo crediti"
              value={amount}
              min={0.1}
              step={0.1}
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

      <div className="cards-grid" style={{ marginTop: 24 }}>
        <StatCard icon={<Users size={18} />} label="Utenti totali" value={reseller.stats.total_users} accent="#6c8ef7" />
        <StatCard icon={<Tv size={18} />} label="Utenti Emby" value={reseller.stats.emby_users} accent="#f5b84b" />
        <StatCard icon={<Tv size={18} />} label="Utenti Jellyfin" value={reseller.stats.jelly_users} accent="#00a4dc" />
        <StatCard icon={<Tv size={18} />} label="Utenti Plex" value={reseller.stats.plex_users} accent="#e5a00d" />
        <StatCard icon={<Users size={18} />} label="Utenti attivi" value={reseller.stats.active_users} accent="#3dd5a5" />
        <StatCard icon={<AlertTriangle size={18} />} label="Utenti scaduti" value={reseller.stats.expired_users} accent="#ef4444" />
        <StatCard icon={<Clock3 size={18} />} label="Scadono entro 7 giorni" value={reseller.stats.expiring_7_days} accent="#f97316" />
        <StatCard icon={<Layers3 size={18} />} label="Schermi totali" value={reseller.stats.total_screens} accent="#a78bfa" />
        <StatCard icon={<Film size={18} />} label="Utenti con 4K" value={reseller.stats.total_4k_users} accent="#14b8a6" />
        <StatCard icon={<History size={18} />} label="Movimenti registrati" value={reseller.stats.movements_count} accent="#94a3b8" onClick={openMovementsModal} />
      </div>

      {showPasswordModal && (
        <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && closePasswordModal()}>
          <div className="modal-card" style={{ maxWidth: 420 }}>
            <div className="modal-header">
              <h3>Cambia Password</h3>
              <button className="btn-ic" onClick={closePasswordModal} disabled={passwordSaving}>
                <X size={15} />
              </button>
            </div>

            <form onSubmit={handlePasswordSubmit}>
              <div className="modal-body">
                <div className="form-group">
                  <label>Nuova password</label>
                  <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                    <input
                      type={showPassword ? "text" : "password"}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Almeno 6 caratteri"
                      autoFocus
                      disabled={passwordSaving}
                    />
                    <button
                      type="button"
                      className="btn-ic"
                      onClick={() => setShowPassword((prev) => !prev)}
                      disabled={passwordSaving}
                      title={showPassword ? "Nascondi" : "Mostra"}
                    >
                      {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                    </button>
                  </div>
                </div>
                <div className="form-group">
                  <label>Conferma password</label>
                  <input
                    type={showPassword ? "text" : "password"}
                    value={passwordConfirm}
                    onChange={(e) => setPasswordConfirm(e.target.value)}
                    placeholder="Ripeti la password"
                    disabled={passwordSaving}
                  />
                </div>
                {passwordError && <div className="login-error">{passwordError}</div>}
                {passwordSuccess && (
                  <div style={{ marginTop: "0.75rem", padding: "0.6rem 1rem", background: "rgba(34,197,94,.1)", border: "1px solid rgba(34,197,94,.3)", borderRadius: "8px", fontSize: ".85rem", color: "#4ade80" }}>
                    {passwordSuccess}
                  </div>
                )}
              </div>

              <div className="modal-footer">
                <button type="button" className="btn btn-ghost" onClick={closePasswordModal} disabled={passwordSaving}>
                  Annulla
                </button>
                <button type="submit" className="btn btn-primary" disabled={passwordSaving}>
                  {passwordSaving ? "Salvataggio..." : "Salva Password"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showMovementsModal && (
        <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && setShowMovementsModal(false)}>
          <div className="modal-card" style={{ maxWidth: 980 }}>
            <div className="modal-header">
              <h3>Movimenti di {reseller.username}</h3>
              <button className="btn-ic" onClick={() => setShowMovementsModal(false)}>
                <X size={15} />
              </button>
            </div>

            <div className="modal-body">
              {movementsLoading ? (
                <div className="loading-wrap"><div className="spinner" /></div>
              ) : movementsError ? (
                <div className="login-error">{movementsError}</div>
              ) : movements.length === 0 ? (
                <div className="wip-wrap" style={{ minHeight: 180 }}>
                  <p>Nessun movimento trovato per questo reseller.</p>
                </div>
              ) : (
                <div className="table-card" style={{ margin: 0 }}>
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Data</th>
                          <th>Tipo</th>
                          <th>Causale</th>
                          <th style={{ textAlign: "right" }}>Importo</th>
                          <th style={{ textAlign: "right" }}>Saldo</th>
                        </tr>
                      </thead>
                      <tbody>
                        {movements.map((movement) => (
                          <tr key={movement.id}>
                            <td style={{ color: "var(--txt-muted)", fontSize: ".78rem", whiteSpace: "nowrap" }}>{formatDate(movement.date)}</td>
                            <td style={{ fontWeight: 700, fontSize: ".82rem" }}>{movement.type ?? "—"}</td>
                            <td style={{ color: "var(--txt-muted)", fontSize: ".85rem" }}>{movement.text ?? "—"}</td>
                            <td style={{ textAlign: "right", fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>
                              {movement.costo != null ? movement.costo.toFixed(2) : "—"}
                            </td>
                            <td style={{ textAlign: "right", color: "var(--txt-muted)", fontSize: ".85rem", fontVariantNumeric: "tabular-nums" }}>
                              {movement.saldo != null ? movement.saldo.toFixed(2) : "—"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>

            <div className="modal-footer">
              <button type="button" className="btn btn-primary" onClick={() => setShowMovementsModal(false)}>
                Chiudi
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
