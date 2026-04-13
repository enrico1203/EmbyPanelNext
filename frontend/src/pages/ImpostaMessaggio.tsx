import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { MessageSquare, Eye, Edit3, Save, Trash2 } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import api from "../api/client";

/* ── Mini markdown renderer ───────────────────────────────────
   Supporta: **bold**, *italic*, - elenchi, emoji, righe vuote  */
function renderMarkdown(raw: string): React.ReactNode[] {
  const lines = raw.split("\n");
  const nodes: React.ReactNode[] = [];
  let listItems: string[] = [];
  let key = 0;

  const flushList = () => {
    if (!listItems.length) return;
    nodes.push(
      <ul key={key++} style={{ margin: "6px 0 6px 1.2rem", padding: 0 }}>
        {listItems.map((item, i) => (
          <li key={i} style={{ marginBottom: 4, lineHeight: 1.65 }}>
            {renderInline(item)}
          </li>
        ))}
      </ul>
    );
    listItems = [];
  };

  const renderInline = (text: string): React.ReactNode[] => {
    // **bold** e *italic*
    const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*)/g);
    return parts.map((part, i) => {
      if (part.startsWith("**") && part.endsWith("**")) {
        return <strong key={i}>{part.slice(2, -2)}</strong>;
      }
      if (part.startsWith("*") && part.endsWith("*")) {
        return <em key={i}>{part.slice(1, -1)}</em>;
      }
      return <span key={i}>{part}</span>;
    });
  };

  for (const line of lines) {
    const trimmed = line.trim();

    if (/^[-•]\s+/.test(trimmed)) {
      listItems.push(trimmed.replace(/^[-•]\s+/, ""));
      continue;
    }

    flushList();

    if (trimmed === "") {
      nodes.push(<div key={key++} style={{ height: 8 }} />);
      continue;
    }

    nodes.push(
      <div key={key++} style={{ lineHeight: 1.7 }}>
        {renderInline(trimmed)}
      </div>
    );
  }

  flushList();
  return nodes;
}

export default function ImpostaMessaggio() {
  const { user } = useAuth();
  const isMasterOrAdmin = user?.ruolo === "admin" || user?.ruolo === "master";

  const [testo, setTesto] = useState("");
  const [testoSalvato, setTestoSalvato] = useState<string | null>(null);
  const [tab, setTab] = useState<"editor" | "preview">("editor");
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<{ ok: boolean; msg: string } | null>(null);
  const [loading, setLoading] = useState(true);

  if (!isMasterOrAdmin) return <Navigate to="/dashboard" replace />;

  useEffect(() => {
    api.get("/reseller/messaggio")
      .then(r => {
        const msg = r.data.messaggio ?? "";
        setTesto(msg);
        setTestoSalvato(msg);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const charCount = testo.length;
  const MAX = 4000;
  const isDirty = testo !== testoSalvato;

  const handleSave = async () => {
    setSaving(true);
    setFeedback(null);
    try {
      await api.put("/reseller/messaggio", { messaggio: testo || null });
      setTestoSalvato(testo);
      setFeedback({ ok: true, msg: "Messaggio salvato correttamente." });
    } catch {
      setFeedback({ ok: false, msg: "Errore durante il salvataggio." });
    } finally {
      setSaving(false);
    }
  };

  const handleClear = () => {
    setTesto("");
  };

  return (
    <div className="pg">
      <div className="pg-title">
        <MessageSquare size={22} style={{ color: "var(--red)" }} />
        Imposta Messaggio
      </div>

      <div style={{ maxWidth: 780 }}>
        {/* Descrizione */}
        <p style={{
          fontSize: ".9rem", color: "var(--txt-soft)", lineHeight: 1.65,
          marginBottom: 24,
          padding: "14px 16px",
          borderRadius: 12,
          background: "rgba(108,142,247,.08)",
          border: "1px solid rgba(108,142,247,.18)",
        }}>
          Il messaggio che imposti qui viene mostrato nella dashboard di tutti i reseller che hanno te come master.
          Supporta <strong>**grassetto**</strong>, <em>*corsivo*</em>, elenchi con <code>-</code> e <strong>emoji</strong> 🎉
        </p>

        {loading ? (
          <div style={{ height: 200, borderRadius: 14, background: "var(--bg-3)", animation: "sk-pulse 1.4s ease-in-out infinite" }} />
        ) : (
          <>
            {/* Tab bar */}
            <div style={{ display: "flex", gap: 6, marginBottom: 12 }}>
              {(["editor", "preview"] as const).map(t => (
                <button
                  key={t}
                  onClick={() => setTab(t)}
                  style={{
                    display: "flex", alignItems: "center", gap: 6,
                    padding: "7px 14px", borderRadius: 9,
                    border: "1px solid",
                    borderColor: tab === t ? "var(--red)" : "var(--border)",
                    background: tab === t ? "var(--red-dim)" : "transparent",
                    color: tab === t ? "var(--red)" : "var(--txt-soft)",
                    fontSize: ".8rem", fontWeight: 600,
                    cursor: "pointer", transition: "all .15s",
                  }}
                >
                  {t === "editor" ? <Edit3 size={14} /> : <Eye size={14} />}
                  {t === "editor" ? "Editor" : "Anteprima"}
                </button>
              ))}
            </div>

            {/* Editor */}
            {tab === "editor" && (
              <div style={{ position: "relative" }}>
                <textarea
                  value={testo}
                  onChange={e => setTesto(e.target.value)}
                  maxLength={MAX}
                  placeholder={"Scrivi qui il tuo messaggio...\n\nEsempio:\n**Aggiornamento importante** 📢\n- Nuovi prezzi da lunedì\n- Contattami su Telegram per info\n\nBuon lavoro a tutti! 🚀"}
                  style={{
                    width: "100%",
                    minHeight: 260,
                    padding: "16px",
                    borderRadius: 14,
                    border: "1px solid var(--border-2)",
                    background: "var(--bg-2)",
                    color: "var(--txt)",
                    fontSize: ".92rem",
                    lineHeight: 1.65,
                    resize: "vertical",
                    outline: "none",
                    fontFamily: "'Plus Jakarta Sans', system-ui, sans-serif",
                    transition: "border-color .15s",
                  }}
                  onFocus={e => (e.target.style.borderColor = "var(--red)")}
                  onBlur={e => (e.target.style.borderColor = "var(--border-2)")}
                />
                <div style={{
                  position: "absolute", bottom: 10, right: 14,
                  fontSize: ".72rem", color: charCount > MAX * 0.9 ? "#e74c3c" : "var(--txt-muted)",
                  fontWeight: 600,
                }}>
                  {charCount}/{MAX}
                </div>
              </div>
            )}

            {/* Preview */}
            {tab === "preview" && (
              <div style={{
                minHeight: 260,
                padding: "20px 22px",
                borderRadius: 14,
                border: "1px solid rgba(245,184,75,.28)",
                background: "linear-gradient(145deg, rgba(245,184,75,.12), rgba(245,184,75,.04) 55%, rgba(255,255,255,.01))",
                color: "var(--txt)",
                fontSize: ".95rem",
              }}>
                {testo.trim() ? (
                  renderMarkdown(testo)
                ) : (
                  <span style={{ color: "var(--txt-muted)", fontStyle: "italic" }}>
                    Nessun contenuto — scrivi qualcosa nell'editor.
                  </span>
                )}
              </div>
            )}

            {/* Actions */}
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 14, flexWrap: "wrap" }}>
              <button
                onClick={handleSave}
                disabled={saving || !isDirty || charCount > MAX}
                style={{
                  display: "flex", alignItems: "center", gap: 7,
                  padding: "9px 20px", borderRadius: 10,
                  background: isDirty && charCount <= MAX ? "var(--red)" : "var(--bg-3)",
                  color: isDirty && charCount <= MAX ? "#fff" : "var(--txt-muted)",
                  border: "none", cursor: isDirty && charCount <= MAX ? "pointer" : "not-allowed",
                  fontSize: ".87rem", fontWeight: 700,
                  transition: "background .15s, opacity .15s",
                  opacity: saving ? 0.6 : 1,
                }}
              >
                <Save size={15} />
                {saving ? "Salvataggio…" : "Salva messaggio"}
              </button>

              <button
                onClick={handleClear}
                disabled={!testo}
                style={{
                  display: "flex", alignItems: "center", gap: 7,
                  padding: "9px 16px", borderRadius: 10,
                  background: "transparent",
                  color: testo ? "#e74c3c" : "var(--txt-muted)",
                  border: "1px solid",
                  borderColor: testo ? "rgba(231,76,60,.35)" : "var(--border)",
                  cursor: testo ? "pointer" : "not-allowed",
                  fontSize: ".87rem", fontWeight: 600,
                  transition: "all .15s",
                }}
              >
                <Trash2 size={14} />
                Cancella
              </button>

              {isDirty && (
                <span style={{ fontSize: ".78rem", color: "var(--txt-muted)", fontStyle: "italic" }}>
                  Modifiche non salvate
                </span>
              )}
            </div>

            {/* Feedback */}
            {feedback && (
              <div style={{
                marginTop: 14,
                padding: "11px 16px",
                borderRadius: 10,
                background: feedback.ok ? "rgba(61,213,165,.1)" : "rgba(231,76,60,.1)",
                border: `1px solid ${feedback.ok ? "rgba(61,213,165,.3)" : "rgba(231,76,60,.3)"}`,
                color: feedback.ok ? "#3dd5a5" : "#e74c3c",
                fontSize: ".87rem", fontWeight: 600,
              }}>
                {feedback.msg}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
