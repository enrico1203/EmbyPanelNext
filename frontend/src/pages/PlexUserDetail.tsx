import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, RotateCcw, Trash2, StickyNote, Copy, Check, LoaderCircle, X } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import api from "../api/client";

interface PlexUserDetail {
  invito: number;
  reseller: string | null;
  pmail: string | null;
  date: string | null;
  date_fmt: string | null;
  expiry: number | null;
  expiry_date: string | null;
  days_left: number | null;
  nschermi: number | null;
  server: string | null;
  server_url: string | null;
  fromuser: string | null;
  nota: string | null;
}

interface ProvisioningOptions {
  credito: number;
  prices: Record<string, Record<string, number>>;
  richieste?: string | null;
}

type Notice = { type: "success" | "error"; text: string } | null;

function formatDaysStatus(days: number | null) {
  if (days === null) return "—";
  return days <= 0 ? `Scaduto (${days})` : `${days} giorni`;
}

function ExpiryBadge({ days }: { days: number | null }) {
  if (days === null) return <span style={{ color: "var(--txt-muted)" }}>—</span>;
  const cls = days <= 0 ? { bg: "rgba(239,68,68,.12)", color: "#f87171", border: "rgba(239,68,68,.28)" }
    : days <= 7 ? { bg: "rgba(245,184,75,.12)", color: "var(--gold)", border: "rgba(245,184,75,.28)" }
    : { bg: "rgba(61,213,165,.12)", color: "var(--teal)", border: "rgba(61,213,165,.28)" };
  return (
    <span style={{ background: cls.bg, color: cls.color, border: `1px solid ${cls.border}`, borderRadius: 999, padding: "3px 12px", fontSize: ".78rem", fontWeight: 700 }}>
      {formatDaysStatus(days)}
    </span>
  );
}

function Row({ label, value, accent }: { label: string; value: React.ReactNode; accent?: boolean }) {
  return (
    <div className="detail-row">
      <span className="detail-row-label">{label}</span>
      <span className="detail-row-value" style={{ color: accent ? "#e5a00d" : "var(--txt)", fontWeight: accent ? 700 : 500 }}>
        {value ?? "—"}
      </span>
    </div>
  );
}

const actionBtn = (color: string, bg: string, border: string) => ({
  display: "inline-flex", alignItems: "center", gap: 6,
  padding: "9px 16px", borderRadius: 10, fontSize: ".82rem", fontWeight: 600,
  border: `1px solid ${border}`, background: bg, color, cursor: "pointer",
  transition: "opacity .15s, transform .15s", fontFamily: "inherit",
} as React.CSSProperties);

export default function PlexUserDetail() {
  const { invito } = useParams<{ invito: string }>();
  const navigate = useNavigate();
  const { user: me, refreshUser } = useAuth();
  const isAdmin = me?.ruolo === "admin";

  const [u, setU] = useState<PlexUserDetail | null>(null);
  const isOwner = !!u && me?.username === u.reseller;
  const canEdit = isAdmin || isOwner;
  const [options, setOptions] = useState<ProvisioningOptions | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [notice, setNotice] = useState<Notice>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [showRenew, setShowRenew] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [renewDays, setRenewDays] = useState("30");

  useEffect(() => {
    Promise.all([
      api.get(`/users/plex/${invito}`),
      api.get("/provisioning/options"),
    ])
      .then(([userResponse, optionsResponse]) => {
        setU(userResponse.data);
        setOptions(optionsResponse.data);
      })
      .catch(e => setError(e?.response?.data?.detail ?? e.message))
      .finally(() => setLoading(false));
  }, [invito]);

  const handleCopy = () => {
    if (!u) return;
    const lines = [
      "Dettagli account Plex:",
      "",
      `Email: ${u.pmail ?? "—"}`,
      `URL: https://app.plex.tv`,
      "",
      `Scadenza: ${u.expiry_date ?? "—"}`,
      `Giorni rimanenti: ${formatDaysStatus(u.days_left)}`,
      ...(options?.richieste ? ["", `Richieste: ${options.richieste}`] : []),
    ];
    navigator.clipboard.writeText(lines.join("\n")).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const handleDelete = async () => {
    setSubmitting(true);
    setNotice(null);
    try {
      const response = await api.delete(`/users/plex/${invito}`);
      setConfirmDelete(false);
      setNotice({ type: "success", text: response.data.message });
      navigate("/lista/plex");
    } catch (err: any) {
      setNotice({
        type: "error",
        text: err?.response?.data?.detail ?? "Errore durante la cancellazione dell'utente Plex.",
      });
    } finally {
      setSubmitting(false);
    }
  };

  const monthlyPrice = Number(options?.prices?.plex?.[String(u?.nschermi ?? 1)] ?? 0);
  const renewCost = Math.round((monthlyPrice * ((Number(renewDays) || 0) / 30.416)) * 100) / 100;
  const remainingEstimate = Math.round(((Number(me?.credito ?? 0) - renewCost) * 100)) / 100;
  const pendingDays = Math.max(0, u?.days_left ?? 0);
  const pendingCost = Math.round((monthlyPrice * (pendingDays / 30.416)) * 100) / 100;

  const handleRenew = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setNotice(null);
    try {
      const response = await api.post(`/users/plex/${invito}/renew`, {
        days: Number(renewDays),
      });
      setU(response.data.user);
      setShowRenew(false);
      await refreshUser();
      setNotice({
        type: "success",
        text: `${response.data.message}. Costo: ${Number(response.data.cost ?? 0).toFixed(2)} crediti. Credito residuo: ${Number(response.data.remaining_credit ?? 0).toFixed(2)} crediti.`,
      });
    } catch (err: any) {
      setNotice({
        type: "error",
        text: err?.response?.data?.detail ?? "Errore durante il rinnovo dell'utente Plex.",
      });
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <div className="pg"><div className="loading-wrap"><div className="spinner" /></div></div>;
  if (error) return <div className="pg"><div className="wip-wrap" style={{ color: "#e74c3c" }}><p>Errore: {error}</p></div></div>;
  if (!u) return null;

  return (
    <div className="pg">
      <button onClick={() => navigate("/lista/plex")} style={{ display: "inline-flex", alignItems: "center", gap: 7, fontSize: ".8rem", fontWeight: 600, color: "var(--txt-muted)", background: "none", border: "none", cursor: "pointer", padding: "5px 0", marginBottom: 8 }}>
        <ArrowLeft size={14} /> Lista Plex
      </button>

      <div style={{ marginBottom: 20 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <h1 style={{ fontSize: "1.5rem", fontWeight: 800, letterSpacing: "-.02em", margin: 0 }}>{u.pmail ?? "—"}</h1>
          <span className="pg-badge platform-plex">Plex</span>
        </div>
        <p style={{ fontSize: ".83rem", color: "var(--txt-muted)", margin: "4px 0 0" }}>Dettagli e gestione account</p>
      </div>

      {notice?.type === "success" && <div className="save-success">{notice.text}</div>}
      {notice?.type === "error" && <div className="login-error">{notice.text}</div>}

      <div className="detail-actions" style={{ marginBottom: 22 }}>
        {canEdit && (
          <>
            <button
              style={actionBtn("#a5b8f8", "rgba(108,142,247,.18)", "rgba(108,142,247,.35)")}
              onClick={() => { setNotice(null); setRenewDays("30"); setShowRenew(true); }}
              disabled={submitting}
            >
              <RotateCcw size={14} /> Rinnova
            </button>
            <button style={actionBtn("#f9a8a8", "rgba(239,68,68,.18)", "rgba(239,68,68,.35)")} onClick={() => setConfirmDelete(true)} disabled={submitting}>
              <Trash2 size={14} /> Cancella
            </button>
            <button style={actionBtn("var(--txt-soft)", "var(--bg-3)", "var(--border-2)")} title="Funzionalità in arrivo">
              <StickyNote size={14} /> Nota
            </button>
          </>
        )}
        <button onClick={handleCopy} style={actionBtn(copied ? "var(--teal)" : "var(--txt-soft)", "var(--bg-3)", "var(--border-2)")}>
          {copied ? <><Check size={14} /> Copiato!</> : <><Copy size={14} /> Copia info</>}
        </button>
      </div>

      <div style={{ background: "var(--bg-2)", border: "1px solid var(--border)", borderRadius: 18, overflow: "hidden", marginBottom: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 9, padding: "14px 18px", background: "var(--bg-3)", borderBottom: "1px solid var(--border)", fontSize: ".78rem", fontWeight: 700, color: "var(--txt-soft)", textTransform: "uppercase", letterSpacing: ".1em" }}>
          Dettagli utente Plex
        </div>
        <Row label="Email Plex" value={u.pmail} accent />
        {(isAdmin || !isOwner) && <Row label="Reseller" value={u.reseller} />}
        <Row label="Attivazione" value={u.date_fmt} />
        <Row label="Scadenza" value={u.expiry_date} />
        <Row label="Giorni rimanenti" value={<ExpiryBadge days={u.days_left} />} />
        <Row label="URL" value="https://app.plex.tv" />
        {options?.richieste && (
          <Row
            label="Richieste"
            value={
              <a href={options.richieste} target="_blank" rel="noreferrer" style={{ color: "#e5a00d", fontWeight: 700, textDecoration: "none" }}>
                {options.richieste}
              </a>
            }
          />
        )}
        <Row label="Schermi" value={u.nschermi} />
        <Row label="Invitato da" value={u.fromuser} />
        <div className="detail-row">
          <span className="detail-row-label">Note</span>
          <span className="detail-row-value">{u.nota || "—"}</span>
        </div>
      </div>

      {isAdmin && (
        <div className="detail-summary-card" style={{ marginTop: 16 }}>
          <div className="create-summary-label">Costo pendente (rimborso)</div>
          <div className="create-summary-value">{pendingCost.toFixed(2)} crediti</div>
          <div className="create-summary-meta">Giorni residui: {pendingDays}</div>
          <div className="create-summary-meta">Schermi attuali: {u.nschermi ?? 1}</div>
          <div className="create-summary-meta">Piano: Plex</div>
          <div className="create-summary-meta">Prezzo mensile base: {monthlyPrice.toFixed(2)} crediti</div>
        </div>
      )}

      {confirmDelete && (
        <div className="modal-overlay" onClick={(event) => event.target === event.currentTarget && !submitting && setConfirmDelete(false)}>
          <div className="modal">
            <div className="modal-header">
              <span className="modal-title">Cancella utente Plex</span>
              <button className="btn-ic" onClick={() => setConfirmDelete(false)} disabled={submitting}>
                <X size={16} />
              </button>
            </div>
            <div className="modal-body">
              <p style={{ margin: 0, color: "var(--txt)" }}>
                Vuoi cancellare definitivamente l'utente <strong>{u.pmail}</strong> da Plex e dal database locale?
              </p>
              <div className="create-note">La cancellazione viene anche registrata nei movimenti e non modifica il credito.</div>
            </div>
            <div className="modal-footer">
              <button type="button" className="btn btn-ghost" onClick={() => setConfirmDelete(false)} disabled={submitting}>Annulla</button>
              <button type="button" className="btn btn-primary" onClick={handleDelete} disabled={submitting} style={{ background: "#dc2626", borderColor: "#dc2626" }}>
                {submitting ? <LoaderCircle size={15} className="spin-inline" /> : <Trash2 size={15} />}
                Cancella utente
              </button>
            </div>
          </div>
        </div>
      )}

      {showRenew && (
        <div className="modal-overlay" onClick={(event) => event.target === event.currentTarget && !submitting && setShowRenew(false)}>
          <div className="modal">
            <div className="modal-header">
              <span className="modal-title">Rinnova utente Plex</span>
              <button className="btn-ic" onClick={() => setShowRenew(false)} disabled={submitting}>
                <X size={16} />
              </button>
            </div>
            <form onSubmit={handleRenew}>
              <div className="modal-body">
                <div className="form-group">
                  <label>Giorni da aggiungere</label>
                  <input type="number" min="1" value={renewDays} onChange={(event) => setRenewDays(event.target.value)} />
                </div>
                <div className="detail-summary-card">
                  <div className="create-summary-label">Costo stimato</div>
                  <div className="create-summary-value">{renewCost.toFixed(2)} crediti</div>
                  <div className="create-summary-meta">Schermi Plex: {u.nschermi ?? 1}</div>
                  <div className="create-summary-meta">Prezzo mensile base: {monthlyPrice.toFixed(2)} crediti</div>
                  <div className="create-summary-meta">Credito attuale: {Number(me?.credito ?? 0).toFixed(2)} crediti</div>
                  <div className="create-summary-meta">Credito residuo stimato: {remainingEstimate.toFixed(2)} crediti</div>
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-ghost" onClick={() => setShowRenew(false)} disabled={submitting}>Annulla</button>
                <button type="submit" className="btn btn-primary" disabled={submitting}>
                  {submitting ? <LoaderCircle size={15} className="spin-inline" /> : <RotateCcw size={15} />}
                  Conferma rinnovo
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
