import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { Search, X } from "lucide-react";
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

interface EditForm {
  username: string;
  master: string;
  credito: string;
  idtelegram: string;
  ruolo: string;
  password: string;
}

export default function ManageResellers() {
  const { user } = useAuth();
  const [resellers, setResellers] = useState<Reseller[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Reseller | null>(null);
  const [form, setForm] = useState<EditForm>({ username: "", master: "", credito: "", idtelegram: "", ruolo: "", password: "" });
  const [saving, setSaving] = useState(false);

  if (user?.ruolo !== "admin") return <Navigate to="/dashboard" replace />;

  const load = async () => {
    try {
      const res = await api.get("/admin/resellers");
      setResellers(res.data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const normalizedSearch = search.trim().toLowerCase();
  const filteredResellers = resellers.filter((reseller) =>
    reseller.username.toLowerCase().includes(normalizedSearch)
  );

  const openEdit = (r: Reseller) => {
    setSelected(r);
    setForm({
      username: r.username,
      master: r.master?.toString() ?? "",
      credito: r.credito.toString(),
      idtelegram: r.idtelegram?.toString() ?? "",
      ruolo: r.ruolo,
      password: "",
    });
  };

  const handleSave = async () => {
    if (!selected) return;
    setSaving(true);
    try {
      const payload: Record<string, unknown> = {
        username: form.username,
        credito: parseInt(form.credito) || 0,
        ruolo: form.ruolo,
        master: form.master ? parseInt(form.master) : null,
        idtelegram: form.idtelegram ? parseInt(form.idtelegram) : null,
      };
      if (form.password) payload.password = form.password;
      await api.put(`/admin/resellers/${selected.id}`, payload);
      await load();
      setSelected(null);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="pg">
      <div className="pg-title">Gestisci Reseller</div>

      {!loading && resellers.length > 0 && (
        <div className="page-toolbar">
          <label className="search-field" htmlFor="admin-resellers-search">
            <Search size={16} />
            <input
              id="admin-resellers-search"
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
      ) : filteredResellers.length === 0 ? (
        <div className="wip-wrap">
          <p>{resellers.length === 0 ? "Nessun reseller trovato." : `Nessun reseller trovato per "${search.trim()}".`}</p>
        </div>
      ) : (
        <div className="table-card">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Username</th>
                  <th>Master</th>
                  <th>Credito</th>
                  <th>Telegram ID</th>
                  <th>Ruolo</th>
                </tr>
              </thead>
              <tbody>
                {filteredResellers.map((r) => (
                  <tr key={r.id} onClick={() => openEdit(r)}>
                    <td style={{ color: "var(--txt-muted)", fontSize: ".78rem" }}>{r.id}</td>
                    <td style={{ fontWeight: 600 }}>{r.username}</td>
                    <td>{r.master ?? "—"}</td>
                    <td>{r.credito}</td>
                    <td>{r.idtelegram ?? "—"}</td>
                    <td>
                      <span className={`role-badge ${r.ruolo}`}>{r.ruolo}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <AnimatePresence>
        {selected && (
          <motion.div
            className="modal-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setSelected(null)}
          >
            <motion.div
              className="modal-card"
              initial={{ opacity: 0, y: 16, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 16, scale: 0.97 }}
              transition={{ duration: 0.18 }}
              onClick={(e) => e.stopPropagation()}
            >
              <div className="modal-header">
                <h3>Modifica #{selected.id} — {selected.username}</h3>
                <button className="btn-ic" onClick={() => setSelected(null)}>
                  <X size={15} />
                </button>
              </div>

              <div className="modal-body">
                {(["username", "master", "credito", "idtelegram"] as const).map((field) => (
                  <div className="form-group" key={field}>
                    <label>{field.charAt(0).toUpperCase() + field.slice(1)}</label>
                    <input
                      value={form[field]}
                      type={field === "username" ? "text" : "number"}
                      onChange={(e) => setForm({ ...form, [field]: e.target.value })}
                      placeholder={field === "master" || field === "idtelegram" ? "Opzionale" : ""}
                    />
                  </div>
                ))}
                <div className="form-group">
                  <label>Ruolo</label>
                  <select value={form.ruolo} onChange={(e) => setForm({ ...form, ruolo: e.target.value })}>
                    <option value="reseller">Reseller</option>
                    <option value="admin">Admin</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>Nuova Password (vuoto = invariata)</label>
                  <input
                    type="password"
                    value={form.password}
                    onChange={(e) => setForm({ ...form, password: e.target.value })}
                    placeholder="••••••••"
                  />
                </div>
              </div>

              <div className="modal-footer">
                <button className="btn btn-ghost" onClick={() => setSelected(null)}>Annulla</button>
                <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
                  {saving ? "Salvataggio..." : "Salva"}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
