import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, RotateCcw, Trash2, Film, Key, StickyNote, Copy, Check } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import api from "../api/client";

interface JellyUserDetail {
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

function ExpiryBadge({ days }: { days: number | null }) {
  if (days === null) return <span style={{ color: "var(--txt-muted)" }}>—</span>;
  const cls = days <= 0 ? { bg: "rgba(239,68,68,.12)", color: "#f87171", border: "rgba(239,68,68,.28)" }
    : days <= 7 ? { bg: "rgba(245,184,75,.12)", color: "var(--gold)", border: "rgba(245,184,75,.28)" }
    : { bg: "rgba(61,213,165,.12)", color: "var(--teal)", border: "rgba(61,213,165,.28)" };
  return (
    <span style={{ background: cls.bg, color: cls.color, border: `1px solid ${cls.border}`, borderRadius: 999, padding: "3px 12px", fontSize: ".78rem", fontWeight: 700 }}>
      {days <= 0 ? "Scaduto" : `${days} giorni`}
    </span>
  );
}

function Row({ label, value, accent }: { label: string; value: React.ReactNode; accent?: boolean }) {
  return (
    <div style={{
      display: "grid", gridTemplateColumns: "180px 1fr", alignItems: "center",
      padding: "11px 18px", borderBottom: "1px solid var(--border)",
      fontSize: ".875rem", transition: "background .12s",
    }}
      onMouseEnter={e => (e.currentTarget.style.background = "rgba(255,255,255,.025)")}
      onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
    >
      <span style={{ color: "var(--txt-muted)", fontWeight: 600, fontSize: ".75rem", textTransform: "uppercase", letterSpacing: ".09em" }}>
        {label}
      </span>
      <span style={{ color: accent ? "#00a4dc" : "var(--txt)", fontWeight: accent ? 700 : 500, wordBreak: "break-all" }}>
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

export default function JellyUserDetail() {
  const { invito } = useParams<{ invito: string }>();
  const navigate = useNavigate();
  const { user: me } = useAuth();
  const isAdmin = me?.ruolo === "admin";

  const [u, setU] = useState<JellyUserDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    api.get(`/users/jelly/${invito}`)
      .then(r => setU(r.data))
      .catch(e => setError(e?.response?.data?.detail ?? e.message))
      .finally(() => setLoading(false));
  }, [invito]);

  const handleCopy = () => {
    if (!u) return;
    const lines = [
      "📊 Dettagli account Jellyfin:",
      "",
      `👤 Username: ${u.user ?? "—"}`,
      `🔑 Password: ${u.password ?? "—"}`,
      `📅 Attivazione: ${u.date_fmt ?? "—"}`,
      `⏰ Scadenza: ${u.expiry_date ?? "—"}`,
      `⏳ Giorni rimanenti: ${u.days_left ?? "—"}`,
      `💻 Server: ${u.server ?? "—"}`,
      `🌐 HTTP: ${u.server_url ?? "—"}`,
      `🔐 HTTPS: ${u.server_https ? `${u.server_https}:443` : "—"}`,
      `🖥️ Schermi: ${u.schermi ?? "—"}`,
      `🎬 4K: ${u.k4 ?? "—"}`,
      `📥 Download: ${u.download ?? "—"}`,
      `📝 Note: ${u.nota ?? "—"}`,
    ];
    navigator.clipboard.writeText(lines.join("\n")).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
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

      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 22 }}>
        <button style={actionBtn("#a5b8f8", "rgba(108,142,247,.18)", "rgba(108,142,247,.35)")} title="Funzionalità in arrivo">
          <RotateCcw size={14} /> Rinnova
        </button>
        <button style={actionBtn("#f9a8a8", "rgba(239,68,68,.18)", "rgba(239,68,68,.35)")} title="Funzionalità in arrivo">
          <Trash2 size={14} /> Cancella
        </button>
        <button style={actionBtn("var(--gold)", "rgba(245,184,75,.18)", "rgba(245,184,75,.35)")} title="Funzionalità in arrivo">
          <Film size={14} /> Togli 4K
        </button>
        <button style={actionBtn("var(--teal)", "rgba(61,213,165,.16)", "rgba(61,213,165,.32)")} title="Funzionalità in arrivo">
          <Film size={14} /> Metti 4K
        </button>
        <button style={actionBtn("#86efac", "rgba(34,197,94,.16)", "rgba(34,197,94,.32)")} title="Funzionalità in arrivo">
          <Key size={14} /> Cambia Password
        </button>
        <button style={actionBtn("var(--txt-soft)", "var(--bg-3)", "var(--border-2)")} title="Funzionalità in arrivo">
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
        <div style={{ display: "grid", gridTemplateColumns: "180px 1fr", alignItems: "center", padding: "11px 18px", fontSize: ".875rem" }}>
          <span style={{ color: "var(--txt-muted)", fontWeight: 600, fontSize: ".75rem", textTransform: "uppercase", letterSpacing: ".09em" }}>Note</span>
          <span style={{ color: "var(--txt)", fontWeight: 500 }}>{u.nota || "—"}</span>
        </div>
      </div>
    </div>
  );
}
