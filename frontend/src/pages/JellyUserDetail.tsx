import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, RotateCcw, Trash2, Film, Key, StickyNote, Copy, Check, LoaderCircle, X } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import api from "../api/client";

interface JellyUserDetailData {
  invito: number;
  reseller: string | null;
  user: string | null;
  date: string | null;
  date_fmt: string | null;
  expiry: number | null;
  expiry_date: string | null;
  days_left: number | null;
  server: string | null;
  server_url: string | null;
  server_https: string | null;
  schermi: number | null;
  k4: string | null;
  download: string | null;
  password: string | null;
  nota: string | null;
}

interface ProvisioningOptions {
  credito: number;
  prices: Record<string, Record<string, number>>;
  free_days_threshold: number;
}

interface JellyActionResponse {
  message: string;
  user: JellyUserDetailData;
  cost?: number | null;
  remaining_credit?: number | null;
}

type ModalType = "renew" | "delete" | "password" | "note" | null;
type Notice = { type: "success" | "error"; text: string } | null;

function ExpiryBadge({ days }: { days: number | null }) {
  if (days === null) return <span style={{ color: "var(--txt-muted)" }}>—</span>;
  const cls = days <= 0
    ? { bg: "rgba(239,68,68,.12)", color: "#f87171", border: "rgba(239,68,68,.28)" }
    : days <= 7
      ? { bg: "rgba(245,184,75,.12)", color: "var(--gold)", border: "rgba(245,184,75,.28)" }
      : { bg: "rgba(61,213,165,.12)", color: "var(--teal)", border: "rgba(61,213,165,.28)" };
  return (
    <span style={{ background: cls.bg, color: cls.color, border: `1px solid ${cls.border}`, borderRadius: 999, padding: "3px 12px", fontSize: ".78rem", fontWeight: 700 }}>
      {days <= 0 ? "Scaduto" : `${days} giorni`}
    </span>
  );
}

function Row({ label, value, accent }: { label: string; value: React.ReactNode; accent?: boolean }) {
  return (
    <div className="detail-row">
      <span className="detail-row-label">{label}</span>
      <span className="detail-row-value" style={{ color: accent ? "#00a4dc" : "var(--txt)", fontWeight: accent ? 700 : 500 }}>
        {value ?? "—"}
      </span>
    </div>
  );
}

function calcCost(monthlyPrice: number, days: number, freeDaysThreshold: number) {
  if (!days || days <= freeDaysThreshold) return 0;
  return Math.round(monthlyPrice * (days / 30.416) * 100) / 100;
}

const actionBtn = (color: string, bg: string, border: string) => ({
  display: "inline-flex", alignItems: "center", gap: 6,
  padding: "9px 16px", borderRadius: 10, fontSize: ".82rem", fontWeight: 600,
  border: `1px solid ${border}`, background: bg, color, cursor: "pointer",
  transition: "opacity .15s, transform .15s", fontFamily: "inherit",
} as React.CSSProperties);

export default function JellyUserDetail() {
  const { invito } = useParams<{ invito: string }>();
  const navigate = useNavigate();
  const { user: me, refreshUser } = useAuth();
  const isAdmin = me?.ruolo === "admin";

  const [u, setU] = useState<JellyUserDetailData | null>(null);
  const [options, setOptions] = useState<ProvisioningOptions | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [notice, setNotice] = useState<Notice>(null);
  const [modal, setModal] = useState<ModalType>(null);
  const [submitting, setSubmitting] = useState<string | null>(null);
  const [renewDays, setRenewDays] = useState("30");
  const [renewScreens, setRenewScreens] = useState("1");
  const [newPassword, setNewPassword] = useState("");
  const [noteValue, setNoteValue] = useState("");

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);

    Promise.all([
      api.get(`/users/jelly/${invito}`),
      api.get("/provisioning/options"),
    ])
      .then(([userResponse, optionsResponse]) => {
        if (!active) return;
        setU(userResponse.data);
        setOptions(optionsResponse.data);
        setNoteValue(userResponse.data.nota ?? "");
        setRenewScreens(String(userResponse.data.schermi ?? 1));
      })
      .catch((err: any) => {
        if (!active) return;
        setError(err?.response?.data?.detail ?? err.message ?? "Errore durante il caricamento dell'utente Jellyfin.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [invito]);

  const openModal = (type: ModalType) => {
    if (!u) return;
    setNotice(null);
    if (type === "renew") {
      setRenewDays("30");
      setRenewScreens(String(u.schermi ?? 1));
    }
    if (type === "password") {
      setNewPassword("");
    }
    if (type === "note") {
      setNoteValue(u.nota ?? "");
    }
    setModal(type);
  };

  const closeModal = () => {
    if (submitting) return;
    setModal(null);
  };

  const handleCopy = () => {
    if (!u) return;
    const lines = [
      "Dettagli account Jellyfin:",
      "",
      `Username: ${u.user ?? "—"}`,
      `Password: ${u.password ?? "—"}`,
      `Attivazione: ${u.date_fmt ?? "—"}`,
      `Scadenza: ${u.expiry_date ?? "—"}`,
      `Giorni rimanenti: ${u.days_left ?? "—"}`,
      `Server: ${u.server ?? "—"}`,
      `HTTP: ${u.server_url ?? "—"}`,
      `HTTPS: ${u.server_https ? `${u.server_https}:443` : "—"}`,
      `Schermi: ${u.schermi ?? "—"}`,
      `4K: ${u.k4 ?? "—"}`,
      `Download: ${u.download ?? "—"}`,
      `Note: ${u.nota ?? "—"}`,
    ];
    navigator.clipboard.writeText(lines.join("\n")).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const monthlyPrice = Number(options?.prices?.jellyfin?.[renewScreens] ?? 0);
  const renewCost = calcCost(monthlyPrice, Number(renewDays) || 0, options?.free_days_threshold ?? 3);
  const remainingEstimate = Math.round(((Number(me?.credito ?? 0) - renewCost) * 100)) / 100;
  const selectedScreens = Number(renewScreens) || 0;
  const currentScreens = Number(u?.schermi ?? 1);
  const renewRuleBlocked = !!u && (u.days_left ?? 0) > 7 && selectedScreens < currentScreens;

  const runAction = async (
    actionKey: string,
    request: Promise<{ data: JellyActionResponse }>,
    successMessage?: (response: JellyActionResponse) => string,
  ) => {
    setSubmitting(actionKey);
    setNotice(null);
    try {
      const response = (await request).data;
      setU(response.user);
      setNoteValue(response.user.nota ?? "");
      setRenewScreens(String(response.user.schermi ?? 1));
      setModal(null);
      if (response.remaining_credit !== undefined && response.remaining_credit !== null) {
        await refreshUser();
      }
      setNotice({
        type: "success",
        text: successMessage ? successMessage(response) : response.message,
      });
    } catch (err: any) {
      setNotice({
        type: "error",
        text: err?.response?.data?.detail ?? `Errore durante l'azione ${actionKey}.`,
      });
    } finally {
      setSubmitting(null);
    }
  };

  const handleRenew = async (event: React.FormEvent) => {
    event.preventDefault();
    await runAction(
      "renew",
      api.post(`/users/jelly/${invito}/renew`, {
        days: Number(renewDays),
        screens: Number(renewScreens),
      }),
      (response) => `${response.message}. Costo: ${(response.cost ?? 0).toFixed(2)}€. Credito residuo: ${(response.remaining_credit ?? 0).toFixed(2)}€.`,
    );
  };

  const handleDelete = async () => {
    setSubmitting("delete");
    setNotice(null);
    try {
      const response = await api.delete(`/users/jelly/${invito}`);
      setModal(null);
      setNotice({ type: "success", text: response.data.message });
      navigate("/lista/jelly");
    } catch (err: any) {
      setNotice({
        type: "error",
        text: err?.response?.data?.detail ?? "Errore durante la cancellazione dell'utente Jellyfin.",
      });
    } finally {
      setSubmitting(null);
    }
  };

  const handlePassword = async (event: React.FormEvent) => {
    event.preventDefault();
    await runAction(
      "password",
      api.post(`/users/jelly/${invito}/password`, { password: newPassword }),
    );
  };

  const handleNote = async (event: React.FormEvent) => {
    event.preventDefault();
    await runAction(
      "note",
      api.post(`/users/jelly/${invito}/note`, { nota: noteValue }),
    );
  };

  const handleToggle4k = async (enabled: boolean) => {
    const action = enabled ? "enable-4k" : "disable-4k";
    await runAction(
      action,
      api.post(`/users/jelly/${invito}/${action}`),
    );
  };

  if (loading) return <div className="pg"><div className="loading-wrap"><div className="spinner" /></div></div>;
  if (error) return <div className="pg"><div className="wip-wrap" style={{ color: "#e74c3c" }}><p>Errore: {error}</p></div></div>;
  if (!u) return null;

  return (
    <div className="pg">
      <button onClick={() => navigate("/lista/jelly")} style={{ display: "inline-flex", alignItems: "center", gap: 7, fontSize: ".8rem", fontWeight: 600, color: "var(--txt-muted)", background: "none", border: "none", cursor: "pointer", padding: "5px 0", marginBottom: 8 }}>
        <ArrowLeft size={14} /> Lista Jellyfin
      </button>

      <div style={{ marginBottom: 20 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <h1 style={{ fontSize: "1.5rem", fontWeight: 800, letterSpacing: "-.02em", margin: 0 }}>{u.user ?? "—"}</h1>
          <span className="pg-badge platform-jelly">Jellyfin</span>
        </div>
        <p style={{ fontSize: ".83rem", color: "var(--txt-muted)", margin: "4px 0 0" }}>Dettagli e gestione account</p>
      </div>

      {notice?.type === "success" && <div className="save-success">{notice.text}</div>}
      {notice?.type === "error" && <div className="login-error">{notice.text}</div>}

      <div className="detail-actions" style={{ marginBottom: 22 }}>
        <button style={actionBtn("#a5b8f8", "rgba(108,142,247,.18)", "rgba(108,142,247,.35)")} onClick={() => openModal("renew")} disabled={!!submitting}>
          <RotateCcw size={14} /> Rinnova
        </button>
        <button style={actionBtn("#f9a8a8", "rgba(239,68,68,.18)", "rgba(239,68,68,.35)")} onClick={() => openModal("delete")} disabled={!!submitting}>
          <Trash2 size={14} /> Cancella
        </button>
        <button style={actionBtn("var(--gold)", "rgba(245,184,75,.18)", "rgba(245,184,75,.35)")} onClick={() => handleToggle4k(false)} disabled={!!submitting || (u.k4 ?? "").toLowerCase() !== "true"}>
          <Film size={14} /> Togli 4K
        </button>
        <button style={actionBtn("var(--teal)", "rgba(61,213,165,.16)", "rgba(61,213,165,.32)")} onClick={() => handleToggle4k(true)} disabled={!!submitting || (u.k4 ?? "").toLowerCase() === "true"}>
          <Film size={14} /> Metti 4K
        </button>
        <button style={actionBtn("#86efac", "rgba(34,197,94,.16)", "rgba(34,197,94,.32)")} onClick={() => openModal("password")} disabled={!!submitting}>
          <Key size={14} /> Cambia Password
        </button>
        <button style={actionBtn("var(--txt-soft)", "var(--bg-3)", "var(--border-2)")} onClick={() => openModal("note")} disabled={!!submitting}>
          <StickyNote size={14} /> Nota
        </button>
        <button onClick={handleCopy} style={actionBtn(copied ? "var(--teal)" : "var(--txt-soft)", "var(--bg-3)", "var(--border-2)")}>
          {copied ? <><Check size={14} /> Copiato!</> : <><Copy size={14} /> Copia info</>}
        </button>
      </div>

      <div style={{ background: "var(--bg-2)", border: "1px solid var(--border)", borderRadius: 18, overflow: "hidden", marginBottom: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 9, padding: "14px 18px", background: "var(--bg-3)", borderBottom: "1px solid var(--border)", fontSize: ".78rem", fontWeight: 700, color: "var(--txt-soft)", textTransform: "uppercase", letterSpacing: ".1em" }}>
          Dettagli utente Jellyfin
        </div>
        <Row label="Username" value={u.user} accent />
        <Row label="Password" value={u.password} />
        {isAdmin && <Row label="Reseller" value={u.reseller} />}
        <Row label="Attivazione" value={u.date_fmt} />
        <Row label="Scadenza" value={u.expiry_date} />
        <Row label="Giorni rimanenti" value={<ExpiryBadge days={u.days_left} />} />
        <Row label="Server" value={u.server} />
        <Row label="HTTP" value={u.server_url} />
        <Row label="HTTPS" value={u.server_https ? `${u.server_https}:443` : null} />
        <Row label="Porta HTTPS" value={u.server_https ? "443" : null} />
        <Row label="Schermi" value={u.schermi} />
        <Row label="4K" value={u.k4} />
        <Row label="Download" value={u.download} />
        <div className="detail-row">
          <span className="detail-row-label">Note</span>
          <span className="detail-row-value">{u.nota || "—"}</span>
        </div>
      </div>

      {modal && (
        <div className="modal-overlay" onClick={(event) => event.target === event.currentTarget && closeModal()}>
          <div className="modal">
            <div className="modal-header">
              <span className="modal-title">
                {modal === "renew" && "Rinnova utente Jellyfin"}
                {modal === "delete" && "Cancella utente Jellyfin"}
                {modal === "password" && "Cambia password"}
                {modal === "note" && "Aggiorna nota"}
              </span>
              <button className="btn-ic" onClick={closeModal} disabled={!!submitting}>
                <X size={16} />
              </button>
            </div>

            {modal === "renew" && (
              <form onSubmit={handleRenew}>
                <div className="modal-body">
                  <div className="detail-modal-grid">
                    <div className="form-group">
                      <label>Giorni da aggiungere</label>
                      <input type="number" min="1" value={renewDays} onChange={(event) => setRenewDays(event.target.value)} />
                    </div>
                    <div className="form-group">
                      <label>Schermi</label>
                      <select value={renewScreens} onChange={(event) => setRenewScreens(event.target.value)}>
                        <option value="1">1</option>
                        <option value="2">2</option>
                        <option value="3">3</option>
                        <option value="4">4</option>
                      </select>
                    </div>
                  </div>

                  <div className="create-note">
                    Se l'utente scade tra più di 7 giorni, gli schermi possono restare uguali o aumentare ma non diminuire.
                  </div>
                  {renewRuleBlocked && (
                    <div className="login-error" style={{ margin: 0 }}>
                      Con {u.days_left} giorni residui non puoi scendere da {currentScreens} a {selectedScreens} schermi.
                    </div>
                  )}
                  <div className="detail-summary-card">
                    <div className="create-summary-label">Costo stimato</div>
                    <div className="create-summary-value">{renewCost.toFixed(2)}€</div>
                    <div className="create-summary-meta">Prezzo mensile base: {monthlyPrice.toFixed(2)}€</div>
                    <div className="create-summary-meta">Credito attuale: {Number(me?.credito ?? 0).toFixed(2)}€</div>
                    <div className="create-summary-meta">Credito residuo stimato: {remainingEstimate.toFixed(2)}€</div>
                  </div>
                </div>
                <div className="modal-footer">
                  <button type="button" className="btn btn-ghost" onClick={closeModal} disabled={!!submitting}>Annulla</button>
                  <button type="submit" className="btn btn-primary" disabled={!!submitting || renewRuleBlocked}>
                    {submitting === "renew" ? <LoaderCircle size={15} className="spin-inline" /> : <RotateCcw size={15} />}
                    Conferma rinnovo
                  </button>
                </div>
              </form>
            )}

            {modal === "delete" && (
              <>
                <div className="modal-body">
                  <p style={{ margin: 0, color: "var(--txt)" }}>
                    Vuoi cancellare definitivamente l'utente <strong>{u.user}</strong> da Jellyfin e dal database locale?
                  </p>
                  <div className="create-note">La cancellazione non modifica il credito e non può essere annullata.</div>
                </div>
                <div className="modal-footer">
                  <button type="button" className="btn btn-ghost" onClick={closeModal} disabled={!!submitting}>Annulla</button>
                  <button type="button" className="btn btn-primary" onClick={handleDelete} disabled={!!submitting} style={{ background: "#dc2626", borderColor: "#dc2626" }}>
                    {submitting === "delete" ? <LoaderCircle size={15} className="spin-inline" /> : <Trash2 size={15} />}
                    Cancella utente
                  </button>
                </div>
              </>
            )}

            {modal === "password" && (
              <form onSubmit={handlePassword}>
                <div className="modal-body">
                  <div className="form-group">
                    <label>Nuova password</label>
                    <input type="text" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} placeholder="Almeno 5 caratteri e un numero" />
                  </div>
                </div>
                <div className="modal-footer">
                  <button type="button" className="btn btn-ghost" onClick={closeModal} disabled={!!submitting}>Annulla</button>
                  <button type="submit" className="btn btn-primary" disabled={!!submitting}>
                    {submitting === "password" ? <LoaderCircle size={15} className="spin-inline" /> : <Key size={15} />}
                    Salva password
                  </button>
                </div>
              </form>
            )}

            {modal === "note" && (
              <form onSubmit={handleNote}>
                <div className="modal-body">
                  <div className="form-group">
                    <label>Nota</label>
                    <textarea
                      value={noteValue}
                      onChange={(event) => setNoteValue(event.target.value)}
                      placeholder="Scrivi una nota interna per questo utente"
                      rows={5}
                      style={{
                        width: "100%",
                        padding: "10px 12px",
                        borderRadius: "var(--radius-sm)",
                        border: "1px solid var(--border-2)",
                        background: "var(--bg-3)",
                        color: "var(--txt)",
                        fontFamily: "inherit",
                        fontSize: ".92rem",
                        resize: "vertical",
                        minHeight: 120,
                      }}
                    />
                  </div>
                </div>
                <div className="modal-footer">
                  <button type="button" className="btn btn-ghost" onClick={closeModal} disabled={!!submitting}>Annulla</button>
                  <button type="submit" className="btn btn-primary" disabled={!!submitting}>
                    {submitting === "note" ? <LoaderCircle size={15} className="spin-inline" /> : <StickyNote size={15} />}
                    Salva nota
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
