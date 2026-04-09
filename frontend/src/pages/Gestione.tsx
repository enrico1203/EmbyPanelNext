import { FormEvent, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { Database, Plus, Save, Trash2 } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import api from "../api/client";

type SectionKey = "emby" | "plex" | "jelly";

interface PlexRow {
  nome: string;
  url: string;
  token: string;
  capienza: string;
}

interface EmbyRow {
  nome: string;
  url: string;
  https: string;
  api: string;
  user: string;
  password: string;
  percorso: string;
  tipo: string;
  limite: string;
  capienza: string;
}

interface JellyRow {
  nome: string;
  url: string;
  https: string;
  api: string;
}

interface ManagementState {
  plex: PlexRow[];
  emby: EmbyRow[];
  jelly: JellyRow[];
}

interface FieldConfig<T> {
  key: keyof T;
  label: string;
  type?: "text" | "number";
  placeholder?: string;
}

const embyFields: FieldConfig<EmbyRow>[] = [
  { key: "nome", label: "Nome", placeholder: "es. emby-main" },
  { key: "url", label: "URL HTTP", placeholder: "http://..." },
  { key: "https", label: "URL HTTPS", placeholder: "https://..." },
  { key: "api", label: "API Key", placeholder: "Chiave API" },
  { key: "user", label: "User", placeholder: "Utente login" },
  { key: "password", label: "Password", placeholder: "Password login" },
  { key: "percorso", label: "Percorso", placeholder: "/mnt/media" },
  { key: "tipo", label: "Tipo", placeholder: "es. cloud" },
  { key: "limite", label: "Limite", placeholder: "es. 4K" },
  { key: "capienza", label: "Capienza", type: "number", placeholder: "0" },
];

const plexFields: FieldConfig<PlexRow>[] = [
  { key: "nome", label: "Nome", placeholder: "es. plex-main" },
  { key: "url", label: "URL", placeholder: "https://..." },
  { key: "token", label: "Token", placeholder: "Token Plex" },
  { key: "capienza", label: "Capienza", type: "number", placeholder: "50" },
];

const jellyFields: FieldConfig<JellyRow>[] = [
  { key: "nome", label: "Nome", placeholder: "es. jelly-main" },
  { key: "url", label: "URL HTTP", placeholder: "http://..." },
  { key: "https", label: "URL HTTPS", placeholder: "https://..." },
  { key: "api", label: "API Key", placeholder: "Chiave API" },
];

const emptyEmbyRow = (): EmbyRow => ({
  nome: "",
  url: "",
  https: "",
  api: "",
  user: "",
  password: "",
  percorso: "",
  tipo: "",
  limite: "",
  capienza: "",
});

const emptyPlexRow = (): PlexRow => ({
  nome: "",
  url: "",
  token: "",
  capienza: "",
});

const emptyJellyRow = (): JellyRow => ({
  nome: "",
  url: "",
  https: "",
  api: "",
});

const emptyState = (): ManagementState => ({
  plex: [],
  emby: [],
  jelly: [],
});

function mapResponse(data: any): ManagementState {
  return {
    plex: Array.isArray(data?.plex)
      ? data.plex.map((row: any) => ({
          nome: row.nome ?? "",
          url: row.url ?? "",
          token: row.token ?? "",
          capienza: row.capienza != null ? String(row.capienza) : "",
        }))
      : [],
    emby: Array.isArray(data?.emby)
      ? data.emby.map((row: any) => ({
          nome: row.nome ?? "",
          url: row.url ?? "",
          https: row.https ?? "",
          api: row.api ?? "",
          user: row.user ?? "",
          password: row.password ?? "",
          percorso: row.percorso ?? "",
          tipo: row.tipo ?? "",
          limite: row.limite ?? "",
          capienza: row.capienza != null ? String(row.capienza) : "",
        }))
      : [],
    jelly: Array.isArray(data?.jelly)
      ? data.jelly.map((row: any) => ({
          nome: row.nome ?? "",
          url: row.url ?? "",
          https: row.https ?? "",
          api: row.api ?? "",
        }))
      : [],
  };
}

export default function Gestione() {
  const { user } = useAuth();
  const [form, setForm] = useState<ManagementState>(emptyState);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  if (user?.ruolo !== "admin") return <Navigate to="/dashboard" replace />;

  useEffect(() => {
    api.get("/admin/management")
      .then((response) => {
        setForm(mapResponse(response.data));
      })
      .catch((err) => {
        setError(err?.response?.data?.detail ?? "Errore durante il caricamento dei dati.");
      })
      .finally(() => setLoading(false));
  }, []);

  const setSectionRows = (section: SectionKey, rows: PlexRow[] | EmbyRow[] | JellyRow[]) => {
    setForm((prev) => {
      switch (section) {
        case "emby":
          return { ...prev, emby: rows as EmbyRow[] };
        case "plex":
          return { ...prev, plex: rows as PlexRow[] };
        case "jelly":
          return { ...prev, jelly: rows as JellyRow[] };
        default:
          return prev;
      }
    });
  };

  const updateRow = (section: SectionKey, index: number, field: string, value: string) => {
    setSuccess("");
    switch (section) {
      case "emby":
        setSectionRows(
          section,
          form.emby.map((row, rowIndex) =>
            rowIndex === index ? { ...row, [field]: value } : row
          )
        );
        break;
      case "plex":
        setSectionRows(
          section,
          form.plex.map((row, rowIndex) =>
            rowIndex === index ? { ...row, [field]: value } : row
          )
        );
        break;
      case "jelly":
        setSectionRows(
          section,
          form.jelly.map((row, rowIndex) =>
            rowIndex === index ? { ...row, [field]: value } : row
          )
        );
        break;
    }
  };

  const addRow = (section: SectionKey) => {
    setSuccess("");
    switch (section) {
      case "emby":
        setSectionRows(section, [...form.emby, emptyEmbyRow()]);
        break;
      case "plex":
        setSectionRows(section, [...form.plex, emptyPlexRow()]);
        break;
      case "jelly":
        setSectionRows(section, [...form.jelly, emptyJellyRow()]);
        break;
    }
  };

  const removeRow = (section: SectionKey, index: number) => {
    setSuccess("");
    switch (section) {
      case "emby":
        setSectionRows(section, form.emby.filter((_, rowIndex) => rowIndex !== index));
        break;
      case "plex":
        setSectionRows(section, form.plex.filter((_, rowIndex) => rowIndex !== index));
        break;
      case "jelly":
        setSectionRows(section, form.jelly.filter((_, rowIndex) => rowIndex !== index));
        break;
    }
  };

  const handleSave = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    setSuccess("");
    setSaving(true);

    try {
      const payload = {
        plex: form.plex.map((row) => ({
          nome: row.nome.trim(),
          url: row.url.trim(),
          token: row.token.trim(),
          capienza: row.capienza.trim() ? Number(row.capienza) : null,
        })),
        emby: form.emby.map((row) => ({
          nome: row.nome.trim(),
          url: row.url.trim() || null,
          https: row.https.trim() || null,
          api: row.api.trim() || null,
          user: row.user.trim() || null,
          password: row.password.trim() || null,
          percorso: row.percorso.trim() || null,
          tipo: row.tipo.trim() || null,
          limite: row.limite.trim() || null,
          capienza: row.capienza.trim() ? Number(row.capienza) : null,
        })),
        jelly: form.jelly.map((row) => ({
          nome: row.nome.trim(),
          url: row.url.trim() || null,
          https: row.https.trim() || null,
          api: row.api.trim() || null,
        })),
      };

      const response = await api.put("/admin/management", payload);
      setForm(mapResponse(response.data));
      setSuccess("Modifiche salvate correttamente.");
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Errore durante il salvataggio.");
    } finally {
      setSaving(false);
    }
  };

  const renderSection = <T extends PlexRow | EmbyRow | JellyRow>(
    options: {
      id: string;
      title: string;
      subtitle: string;
      section: SectionKey;
      rows: T[];
      fields: FieldConfig<T>[];
      addLabel: string;
    }
  ) => (
    <section id={options.id} className="config-section">
      <div className="config-section-header">
        <div>
          <h2>{options.title}</h2>
          <p>{options.subtitle}</p>
        </div>
        <div className="config-section-actions">
          <span className="config-count">
            {options.rows.length} rig{options.rows.length === 1 ? "a" : "he"}
          </span>
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => addRow(options.section)}
          >
            <Plus size={15} /> {options.addLabel}
          </button>
        </div>
      </div>

      {options.rows.length === 0 ? (
        <div className="config-empty">
          <p>Nessuna riga presente in questa sezione.</p>
        </div>
      ) : (
        <div className="config-rows">
          {options.rows.map((row, index) => (
            <div className="config-row-card" key={`${options.section}-${index}`}>
              <div className="config-row-header">
                <div className="config-row-title">
                  <Database size={15} />
                  <span>{options.title} #{index + 1}</span>
                </div>
                <button
                  type="button"
                  className="config-remove-btn"
                  onClick={() => removeRow(options.section, index)}
                  aria-label={`Rimuovi riga ${index + 1}`}
                >
                  <Trash2 size={15} />
                </button>
              </div>

              <div className="config-fields-grid">
                {options.fields.map((field) => (
                  <label className="config-field" key={String(field.key)}>
                    <span>{field.label}</span>
                    <input
                      type={field.type ?? "text"}
                      value={String(row[field.key] ?? "")}
                      placeholder={field.placeholder}
                      onChange={(e) =>
                        updateRow(
                          options.section,
                          index,
                          String(field.key),
                          e.target.value
                        )
                      }
                    />
                  </label>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );

  return (
    <div className="pg">
      <form onSubmit={handleSave} className="manage-form">
        <div className="manage-header">
          <div>
            <div className="pg-title" style={{ marginBottom: "0.35rem" }}>Gestione</div>
            <p className="manage-subtitle">
              Configura e salva i dati di Emby, Plex e Jellyfin dal pannello admin.
            </p>
          </div>
          <button className="btn btn-primary" type="submit" disabled={saving || loading}>
            <Save size={15} /> {saving ? "Salvataggio..." : "Salva"}
          </button>
        </div>

        <div className="manage-nav">
          <a href="#emby-section" className="manage-nav-link">Emby</a>
          <a href="#plex-section" className="manage-nav-link">Plex</a>
          <a href="#jelly-section" className="manage-nav-link">Jellyfin</a>
        </div>

        {error && <div className="login-error">{error}</div>}
        {success && <div className="save-success">{success}</div>}

        {loading ? (
          <div className="loading-wrap"><div className="spinner" /></div>
        ) : (
          <div className="manage-sections">
            {renderSection({
              id: "emby-section",
              title: "Emby",
              subtitle: "Modifica tutti i campi della tabella emby.",
              section: "emby",
              rows: form.emby,
              fields: embyFields,
              addLabel: "Aggiungi Emby",
            })}

            {renderSection({
              id: "plex-section",
              title: "Plex",
              subtitle: "Gestisci nome, URL e token dei server Plex.",
              section: "plex",
              rows: form.plex,
              fields: plexFields,
              addLabel: "Aggiungi Plex",
            })}

            {renderSection({
              id: "jelly-section",
              title: "Jellyfin",
              subtitle: "Gestisci i server Jellyfin e le loro API key.",
              section: "jelly",
              rows: form.jelly,
              fields: jellyFields,
              addLabel: "Aggiungi Jellyfin",
            })}
          </div>
        )}

        {!loading && (
          <div className="manage-footer">
            <button className="btn btn-primary" type="submit" disabled={saving}>
              <Save size={15} /> {saving ? "Salvataggio..." : "Salva Modifiche"}
            </button>
          </div>
        )}
      </form>
    </div>
  );
}
