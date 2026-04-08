import { useEffect, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { ChevronRight, Plus, X, Copy, Check, Eye, EyeOff, Search } from "lucide-react";
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

interface CreatedResult {
  id: number;
  username: string;
  credito: number;
  ruolo: string;
  password_generata: string;
}

export default function MyResellers() {
  const { user, refreshUser } = useAuth();
  const navigate = useNavigate();
  const [resellers, setResellers] = useState<Reseller[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  // modal state
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState({ username: "", credito: "", idtelegram: "" });
  const [creating, setCreating] = useState(false);
  const [formError, setFormError] = useState("");
  const [created, setCreated] = useState<CreatedResult | null>(null);
  const [copied, setCopied] = useState(false);
  const [showPass, setShowPass] = useState(false);

  const canAccess = user?.ruolo === "admin" || user?.ruolo === "master";
  if (!canAccess) return <Navigate to="/dashboard" replace />;

  useEffect(() => {
    api.get("/reseller/my-resellers")
      .then((r) => setResellers(r.data))
      .finally(() => setLoading(false));
  }, []);

  const normalizedSearch = search.trim().toLowerCase();
  const filteredResellers = resellers.filter((reseller) =>
    reseller.username.toLowerCase().includes(normalizedSearch)
  );

  const openModal = () => {
    setForm({ username: "", credito: "", idtelegram: "" });
    setFormError("");
    setCreated(null);
    setCopied(false);
    setShowPass(false);
    setShowModal(true);
  };

  const closeModal = () => {
    setShowModal(false);
    setCreated(null);
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError("");
    const credito = Number.parseFloat(form.credito);
    if (!form.username.trim()) { setFormError("Username obbligatorio."); return; }
    if (Number.isNaN(credito) || credito < 0.1) { setFormError("Il credito minimo è 0.1."); return; }
    if (credito > (user?.credito ?? 0)) { setFormError("Crediti insufficienti."); return; }

    setCreating(true);
    try {
      const payload: any = { username: form.username.trim(), credito };
      if (form.idtelegram.trim()) payload.idtelegram = parseInt(form.idtelegram.trim(), 10);

      const r = await api.post("/reseller/my-resellers", payload);
      setCreated(r.data);
      await refreshUser();
      setResellers((prev) => [
        ...prev,
        {
          id: r.data.id,
          username: r.data.username,
          master: user!.id,
          credito: r.data.credito,
          idtelegram: payload.idtelegram ?? null,
          ruolo: r.data.ruolo,
        },
      ]);
    } catch (err: any) {
      setFormError(err?.response?.data?.detail ?? "Errore durante la creazione.");
    } finally {
      setCreating(false);
    }
  };

  const copyPassword = () => {
    if (!created) return;
    navigator.clipboard.writeText(created.password_generata).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <div className="pg">
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1.5rem", flexWrap: "wrap", gap: "0.75rem" }}>
        <div className="pg-title" style={{ margin: 0 }}>I Miei Reseller</div>
        <button className="btn btn-primary" onClick={openModal}>
          <Plus size={15} /> Nuovo Reseller
        </button>
      </div>

      {!loading && resellers.length > 0 && (
        <div className="page-toolbar">
          <label className="search-field" htmlFor="reseller-search">
            <Search size={16} />
            <input
              id="reseller-search"
              type="text"
              placeholder="Cerca username"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              autoComplete="off"
            />
          </label>
          <div className="toolbar-meta">
            {filteredResellers.length} risultat{filteredResellers.length === 1 ? "o" : "i"}
          </div>
        </div>
      )}

      {loading ? (
        <div className="loading-wrap"><div className="spinner" /></div>
      ) : resellers.length === 0 ? (
        <div className="wip-wrap">
          <p>Nessun reseller associato al tuo account.</p>
        </div>
      ) : filteredResellers.length === 0 ? (
        <div className="wip-wrap">
          <p>Nessun reseller trovato per “{search.trim()}”.</p>
        </div>
      ) : (
        <div className="table-card">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Username</th>
                  <th>Credito</th>
                  <th>Ruolo</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {filteredResellers.map((r) => (
                  <tr key={r.id} onClick={() => navigate(`/resellers/${r.id}`)}>
                    <td style={{ color: "var(--txt-muted)", fontSize: ".78rem" }}>{r.id}</td>
                    <td style={{ fontWeight: 600 }}>{r.username}</td>
                    <td>{r.credito}</td>
                    <td><span className={`role-badge ${r.ruolo}`}>{r.ruolo}</span></td>
                    <td style={{ textAlign: "right", color: "var(--txt-muted)" }}>
                      <ChevronRight size={15} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && closeModal()}>
          <div className="modal" style={{ maxWidth: 420 }}>
            <div className="modal-header">
              <span className="modal-title">{created ? "Reseller Creato" : "Nuovo Reseller"}</span>
              <button className="btn-ic" onClick={closeModal}><X size={16} /></button>
            </div>

            {!created ? (
              <form onSubmit={handleCreate}>
                <div className="modal-body" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                  <div>
                    <label className="modal-label">Username</label>
                    <input
                      className="login-input"
                      style={{ width: "100%" }}
                      placeholder="es. mario_rossi"
                      value={form.username}
                      onChange={(e) => setForm({ ...form, username: e.target.value })}
                      disabled={creating}
                      autoFocus
                    />
                  </div>
                  <div>
                    <label className="modal-label">
                        Crediti iniziali
                        <span style={{ color: "var(--txt-muted)", fontWeight: 400, marginLeft: "0.5rem" }}>
                        (min 0.1, disponibili: {user?.credito})
                      </span>
                    </label>
                    <input
                      type="number"
                      className="login-input"
                      style={{ width: "100%" }}
                      placeholder="0.1"
                      min={0.1}
                      step={0.1}
                      max={user?.credito}
                      value={form.credito}
                      onChange={(e) => setForm({ ...form, credito: e.target.value })}
                      disabled={creating}
                    />
                    {form.credito && parseInt(form.credito) >= 100 && (
                      <p style={{ marginTop: "0.4rem", fontSize: ".78rem", color: "var(--red)" }}>
                        ≥ 100 crediti → il reseller sarà creato come <strong>master</strong>
                      </p>
                    )}
                  </div>
                  <div>
                    <label className="modal-label">
                      ID Telegram
                      <span style={{ color: "var(--txt-muted)", fontWeight: 400, marginLeft: "0.5rem" }}>(opzionale)</span>
                    </label>
                    <input
                      type="number"
                      className="login-input"
                      style={{ width: "100%" }}
                      placeholder="es. 123456789"
                      value={form.idtelegram}
                      onChange={(e) => setForm({ ...form, idtelegram: e.target.value })}
                      disabled={creating}
                    />
                  </div>
                  {formError && <div className="login-error">{formError}</div>}
                  <p style={{ fontSize: ".78rem", color: "var(--txt-muted)", margin: 0 }}>
                    La password verrà generata automaticamente (16 caratteri complessi).
                  </p>
                </div>
                <div className="modal-footer">
                  <button type="button" className="btn btn-ghost" onClick={closeModal} disabled={creating}>Annulla</button>
                  <button type="submit" className="btn btn-primary" disabled={creating}>
                    {creating ? "Creazione…" : "Crea Reseller"}
                  </button>
                </div>
              </form>
            ) : (
              <>
                <div className="modal-body" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                  <div style={{ padding: "1rem", background: "rgba(34,197,94,.07)", border: "1px solid rgba(34,197,94,.25)", borderRadius: "10px" }}>
                    <p style={{ fontSize: ".82rem", color: "#4ade80", marginBottom: "0.5rem", fontWeight: 600 }}>Reseller creato con successo!</p>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem", fontSize: ".82rem" }}>
                      <span style={{ color: "var(--txt-muted)" }}>Username</span>
                      <span style={{ fontWeight: 700 }}>{created.username}</span>
                      <span style={{ color: "var(--txt-muted)" }}>Crediti</span>
                      <span style={{ fontWeight: 700 }}>{created.credito}</span>
                      <span style={{ color: "var(--txt-muted)" }}>Ruolo</span>
                      <span><span className={`role-badge ${created.ruolo}`}>{created.ruolo}</span></span>
                    </div>
                  </div>

                  <div>
                    <label className="modal-label" style={{ marginBottom: "0.4rem", display: "block" }}>
                      Password generata
                    </label>
                    <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                      <div style={{
                        flex: 1,
                        background: "var(--bg-3)",
                        border: "1px solid var(--border-2)",
                        borderRadius: "8px",
                        padding: "0.6rem 0.9rem",
                        fontFamily: "monospace",
                        fontSize: ".9rem",
                        letterSpacing: showPass ? ".04em" : ".1em",
                        wordBreak: "break-all",
                        color: showPass ? "var(--txt)" : "var(--txt-muted)",
                      }}>
                        {showPass ? created.password_generata : "●".repeat(created.password_generata.length)}
                      </div>
                      <button className="btn-ic" title={showPass ? "Nascondi" : "Mostra"} onClick={() => setShowPass(!showPass)}>
                        {showPass ? <EyeOff size={15} /> : <Eye size={15} />}
                      </button>
                      <button className="btn-ic" title="Copia" onClick={copyPassword}>
                        {copied ? <Check size={15} style={{ color: "#4ade80" }} /> : <Copy size={15} />}
                      </button>
                    </div>
                    <p style={{ marginTop: "0.4rem", fontSize: ".75rem", color: "var(--red)" }}>
                      Copia e salva la password ora — non sarà più visualizzabile.
                    </p>
                  </div>
                </div>
                <div className="modal-footer">
                  <button className="btn btn-primary" onClick={closeModal}>Chiudi</button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
