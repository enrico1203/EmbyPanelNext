import { useEffect, useMemo, useState } from "react";
import { Navigate } from "react-router-dom";
import { Database, Plus, Save, Search, Trash2 } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import api from "../api/client";

type SectionKey = "plex" | "jelly" | "emby";

interface RowMeta {
  _originalInvito: string;
  _dirty: boolean;
  _saving: boolean;
  _deleting: boolean;
  _isNew: boolean;
}

interface PlexUserRow extends RowMeta {
  invito: string;
  id: string;
  pmail: string;
  date: string;
  expiry: string;
  nschermi: string;
  server: string;
  fromuser: string;
  nota: string;
}

interface JellyUserRow extends RowMeta {
  invito: string;
  id: string;
  user: string;
  date: string;
  expiry: string;
  server: string;
  schermi: string;
  k4: string;
  download: string;
  password: string;
  nota: string;
}

interface EmbyUserRow extends RowMeta {
  invito: string;
  id: string;
  user: string;
  date: string;
  expiry: string;
  server: string;
  schermi: string;
  k4: string;
  download: string;
  password: string;
  nota: string;
}

interface UserManagementState {
  plex: PlexUserRow[];
  jelly: JellyUserRow[];
  emby: EmbyUserRow[];
}

interface SearchState {
  plex: string;
  jelly: string;
  emby: string;
}

interface FieldConfig<T> {
  key: keyof T;
  label: string;
  type?: "text" | "number" | "datetime-local";
  placeholder?: string;
}

const plexFields: FieldConfig<PlexUserRow>[] = [
  { key: "invito", label: "Invito", type: "number", placeholder: "auto" },
  { key: "id", label: "ID/Reseller", placeholder: "admin" },
  { key: "pmail", label: "Email Plex", placeholder: "utente@gmail.com" },
  { key: "date", label: "Data", type: "datetime-local" },
  { key: "expiry", label: "Expiry", type: "number", placeholder: "giorni" },
  { key: "nschermi", label: "Schermi", type: "number", placeholder: "2" },
  { key: "server", label: "Server", placeholder: "p1" },
  { key: "fromuser", label: "From User", placeholder: "admin" },
  { key: "nota", label: "Nota", placeholder: "Nota interna" },
];

const jellyFields: FieldConfig<JellyUserRow>[] = [
  { key: "invito", label: "Invito", type: "number", placeholder: "auto" },
  { key: "id", label: "ID/Reseller", placeholder: "admin" },
  { key: "user", label: "Username", placeholder: "utente1" },
  { key: "date", label: "Data", type: "datetime-local" },
  { key: "expiry", label: "Expiry", type: "number", placeholder: "giorni" },
  { key: "server", label: "Server", placeholder: "j1" },
  { key: "schermi", label: "Schermi", type: "number", placeholder: "2" },
  { key: "k4", label: "4K", placeholder: "true / false" },
  { key: "download", label: "Download", placeholder: "true / false" },
  { key: "password", label: "Password", placeholder: "password" },
  { key: "nota", label: "Nota", placeholder: "Nota interna" },
];

const embyFields: FieldConfig<EmbyUserRow>[] = [
  { key: "invito", label: "Invito", type: "number", placeholder: "auto" },
  { key: "id", label: "ID/Reseller", placeholder: "admin" },
  { key: "user", label: "Username", placeholder: "utente1" },
  { key: "date", label: "Data", type: "datetime-local" },
  { key: "expiry", label: "Expiry", type: "number", placeholder: "giorni" },
  { key: "server", label: "Server", placeholder: "e1" },
  { key: "schermi", label: "Schermi", type: "number", placeholder: "2" },
  { key: "k4", label: "4K", placeholder: "true / false" },
  { key: "download", label: "Download", placeholder: "true / false" },
  { key: "password", label: "Password", placeholder: "password" },
  { key: "nota", label: "Nota", placeholder: "Nota interna" },
];

const rowMeta = (originalInvito = "", isNew = false): RowMeta => ({
  _originalInvito: originalInvito,
  _dirty: isNew,
  _saving: false,
  _deleting: false,
  _isNew: isNew,
});

const emptyPlexRow = (): PlexUserRow => ({
  ...rowMeta("", true),
  invito: "",
  id: "",
  pmail: "",
  date: "",
  expiry: "",
  nschermi: "",
  server: "",
  fromuser: "",
  nota: "",
});

const emptyJellyRow = (): JellyUserRow => ({
  ...rowMeta("", true),
  invito: "",
  id: "",
  user: "",
  date: "",
  expiry: "",
  server: "",
  schermi: "",
  k4: "false",
  download: "false",
  password: "",
  nota: "",
});

const emptyEmbyRow = (): EmbyUserRow => ({
  ...rowMeta("", true),
  invito: "",
  id: "",
  user: "",
  date: "",
  expiry: "",
  server: "",
  schermi: "",
  k4: "false",
  download: "false",
  password: "",
  nota: "",
});

const emptyState = (): UserManagementState => ({
  plex: [],
  jelly: [],
  emby: [],
});

function toDateInput(value: string | null | undefined) {
  if (!value) return "";
  const normalized = value.replace(" ", "T");
  return normalized.length >= 16 ? normalized.slice(0, 16) : normalized;
}

function mapResponse(data: any): UserManagementState {
  return {
    plex: Array.isArray(data?.plex)
      ? data.plex.map((row: any) => ({
          ...rowMeta(row.invito != null ? String(row.invito) : ""),
          invito: row.invito != null ? String(row.invito) : "",
          id: row.id ?? "",
          pmail: row.pmail ?? "",
          date: toDateInput(row.date),
          expiry: row.expiry != null ? String(row.expiry) : "",
          nschermi: row.nschermi != null ? String(row.nschermi) : "",
          server: row.server ?? "",
          fromuser: row.fromuser ?? "",
          nota: row.nota ?? "",
        }))
      : [],
    jelly: Array.isArray(data?.jelly)
      ? data.jelly.map((row: any) => ({
          ...rowMeta(row.invito != null ? String(row.invito) : ""),
          invito: row.invito != null ? String(row.invito) : "",
          id: row.id ?? "",
          user: row.user ?? "",
          date: toDateInput(row.date),
          expiry: row.expiry != null ? String(row.expiry) : "",
          server: row.server ?? "",
          schermi: row.schermi != null ? String(row.schermi) : "",
          k4: row.k4 ?? "",
          download: row.download ?? "",
          password: row.password ?? "",
          nota: row.nota ?? "",
        }))
      : [],
    emby: Array.isArray(data?.emby)
      ? data.emby.map((row: any) => ({
          ...rowMeta(row.invito != null ? String(row.invito) : ""),
          invito: row.invito != null ? String(row.invito) : "",
          id: row.id ?? "",
          user: row.user ?? "",
          date: toDateInput(row.date),
          expiry: row.expiry != null ? String(row.expiry) : "",
          server: row.server ?? "",
          schermi: row.schermi != null ? String(row.schermi) : "",
          k4: row.k4 ?? "",
          download: row.download ?? "",
          password: row.password ?? "",
          nota: row.nota ?? "",
        }))
      : [],
  };
}

export default function GestioneUtenti() {
  const { user } = useAuth();
  const [form, setForm] = useState<UserManagementState>(emptyState);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [search, setSearch] = useState<SearchState>({ plex: "", jelly: "", emby: "" });

  if (user?.ruolo !== "admin") return <Navigate to="/dashboard" replace />;

  useEffect(() => {
    api.get("/admin/user-management")
      .then((response) => setForm(mapResponse(response.data)))
      .catch((err) => setError(err?.response?.data?.detail ?? "Errore durante il caricamento delle tabelle utenti."))
      .finally(() => setLoading(false));
  }, []);

  const setSectionRows = (section: SectionKey, rows: PlexUserRow[] | JellyUserRow[] | EmbyUserRow[]) => {
    setForm((prev) => {
      switch (section) {
        case "plex":
          return { ...prev, plex: rows as PlexUserRow[] };
        case "jelly":
          return { ...prev, jelly: rows as JellyUserRow[] };
        case "emby":
          return { ...prev, emby: rows as EmbyUserRow[] };
        default:
          return prev;
      }
    });
  };

  const updateRow = (section: SectionKey, index: number, field: string, value: string) => {
    setError("");
    setSuccess("");
    const update = <T extends RowMeta>(rows: T[]) =>
      rows.map((row, rowIndex) => rowIndex === index ? { ...row, [field]: value, _dirty: true } : row);

    switch (section) {
      case "plex":
        setSectionRows(section, update(form.plex));
        break;
      case "jelly":
        setSectionRows(section, update(form.jelly));
        break;
      case "emby":
        setSectionRows(section, update(form.emby));
        break;
    }
  };

  const setRowFlag = (section: SectionKey, index: number, patch: Partial<RowMeta>) => {
    const update = <T extends RowMeta>(rows: T[]) =>
      rows.map((row, rowIndex) => rowIndex === index ? { ...row, ...patch } : row);
    switch (section) {
      case "plex":
        setSectionRows(section, update(form.plex));
        break;
      case "jelly":
        setSectionRows(section, update(form.jelly));
        break;
      case "emby":
        setSectionRows(section, update(form.emby));
        break;
    }
  };

  const replaceRow = (section: SectionKey, index: number, row: PlexUserRow | JellyUserRow | EmbyUserRow) => {
    const update = <T extends RowMeta>(rows: T[]) => rows.map((current, rowIndex) => rowIndex === index ? (row as unknown as T) : current);
    switch (section) {
      case "plex":
        setSectionRows(section, update(form.plex));
        break;
      case "jelly":
        setSectionRows(section, update(form.jelly));
        break;
      case "emby":
        setSectionRows(section, update(form.emby));
        break;
    }
  };

  const addRow = (section: SectionKey) => {
    setSuccess("");
    setError("");
    switch (section) {
      case "plex":
        setSectionRows(section, [emptyPlexRow(), ...form.plex]);
        break;
      case "jelly":
        setSectionRows(section, [emptyJellyRow(), ...form.jelly]);
        break;
      case "emby":
        setSectionRows(section, [emptyEmbyRow(), ...form.emby]);
        break;
    }
  };

  const toNumberOrNull = (value: string) => {
    const cleaned = value.trim();
    return cleaned ? Number(cleaned) : null;
  };

  const toStringOrNull = (value: string) => {
    const cleaned = value.trim();
    return cleaned || null;
  };

  const toDateOrNull = (value: string) => {
    const cleaned = value.trim();
    return cleaned || null;
  };

  const saveRow = async (section: SectionKey, index: number) => {
    const row = section === "plex" ? form.plex[index] : section === "jelly" ? form.jelly[index] : form.emby[index];
    if (!row) return;
    setError("");
    setSuccess("");
    setRowFlag(section, index, { _saving: true });
    try {
      const payload = {
        original_invito: toNumberOrNull(row._originalInvito),
        row: section === "plex"
          ? {
              invito: toNumberOrNull((row as PlexUserRow).invito),
              id: toStringOrNull((row as PlexUserRow).id),
              pmail: toStringOrNull((row as PlexUserRow).pmail),
              date: toDateOrNull((row as PlexUserRow).date),
              expiry: toNumberOrNull((row as PlexUserRow).expiry),
              nschermi: toNumberOrNull((row as PlexUserRow).nschermi),
              server: toStringOrNull((row as PlexUserRow).server),
              fromuser: toStringOrNull((row as PlexUserRow).fromuser),
              nota: toStringOrNull((row as PlexUserRow).nota),
            }
          : section === "jelly"
            ? {
                invito: toNumberOrNull((row as JellyUserRow).invito),
                id: toStringOrNull((row as JellyUserRow).id),
                user: toStringOrNull((row as JellyUserRow).user),
                date: toDateOrNull((row as JellyUserRow).date),
                expiry: toNumberOrNull((row as JellyUserRow).expiry),
                server: toStringOrNull((row as JellyUserRow).server),
                schermi: toNumberOrNull((row as JellyUserRow).schermi),
                k4: toStringOrNull((row as JellyUserRow).k4),
                download: toStringOrNull((row as JellyUserRow).download),
                password: toStringOrNull((row as JellyUserRow).password),
                nota: toStringOrNull((row as JellyUserRow).nota),
              }
            : {
                invito: toNumberOrNull((row as EmbyUserRow).invito),
                id: toStringOrNull((row as EmbyUserRow).id),
                user: toStringOrNull((row as EmbyUserRow).user),
                date: toDateOrNull((row as EmbyUserRow).date),
                expiry: toNumberOrNull((row as EmbyUserRow).expiry),
                server: toStringOrNull((row as EmbyUserRow).server),
                schermi: toNumberOrNull((row as EmbyUserRow).schermi),
                k4: toStringOrNull((row as EmbyUserRow).k4),
                download: toStringOrNull((row as EmbyUserRow).download),
                password: toStringOrNull((row as EmbyUserRow).password),
                nota: toStringOrNull((row as EmbyUserRow).nota),
              },
      };
      const response = await api.put(`/admin/user-management/${section}/row`, payload);
      const saved = mapResponse({ [section]: [response.data] })[section][0] as PlexUserRow | JellyUserRow | EmbyUserRow;
      replaceRow(section, index, saved);
      setSuccess(`Riga ${section === "plex" ? "Plex" : section === "jelly" ? "Jellyfin" : "Emby"} salvata correttamente.`);
    } catch (err: any) {
      setRowFlag(section, index, { _saving: false });
      setError(err?.response?.data?.detail ?? "Errore durante il salvataggio della riga.");
    }
  };

  const deleteRow = async (section: SectionKey, index: number) => {
    const row = section === "plex" ? form.plex[index] : section === "jelly" ? form.jelly[index] : form.emby[index];
    if (!row) return;
    setError("");
    setSuccess("");

    if (!row.invito) {
      switch (section) {
        case "plex":
          setSectionRows(section, form.plex.filter((_, rowIndex) => rowIndex !== index));
          break;
        case "jelly":
          setSectionRows(section, form.jelly.filter((_, rowIndex) => rowIndex !== index));
          break;
        case "emby":
          setSectionRows(section, form.emby.filter((_, rowIndex) => rowIndex !== index));
          break;
      }
      return;
    }

    setRowFlag(section, index, { _deleting: true });
    try {
      await api.delete(`/admin/user-management/${section}/${row.invito}`);
      switch (section) {
        case "plex":
          setSectionRows(section, form.plex.filter((_, rowIndex) => rowIndex !== index));
          break;
        case "jelly":
          setSectionRows(section, form.jelly.filter((_, rowIndex) => rowIndex !== index));
          break;
        case "emby":
          setSectionRows(section, form.emby.filter((_, rowIndex) => rowIndex !== index));
          break;
      }
      setSuccess(`Riga ${section === "plex" ? "Plex" : section === "jelly" ? "Jellyfin" : "Emby"} rimossa correttamente.`);
    } catch (err: any) {
      setRowFlag(section, index, { _deleting: false });
      setError(err?.response?.data?.detail ?? "Errore durante l'eliminazione della riga.");
    }
  };

  const filteredRows = {
    plex: useMemo(
      () => form.plex.filter((row) => (row.pmail ?? "").toLowerCase().includes(search.plex.toLowerCase())),
      [form.plex, search.plex]
    ),
    jelly: useMemo(
      () => form.jelly.filter((row) => (row.user ?? "").toLowerCase().includes(search.jelly.toLowerCase())),
      [form.jelly, search.jelly]
    ),
    emby: useMemo(
      () => form.emby.filter((row) => (row.user ?? "").toLowerCase().includes(search.emby.toLowerCase())),
      [form.emby, search.emby]
    ),
  };

  const renderSection = <T extends PlexUserRow | JellyUserRow | EmbyUserRow>(options: {
    id: string;
    title: string;
    subtitle: string;
    section: SectionKey;
    rows: T[];
    fields: FieldConfig<T>[];
    addLabel: string;
    searchPlaceholder: string;
    primaryField: keyof T;
  }) => (
    <section id={options.id} className="config-section">
      <div className="config-section-header">
        <div>
          <h2>{options.title}</h2>
          <p>{options.subtitle}</p>
        </div>
        <div className="config-section-actions">
          <span className="config-count">
            {options.rows.length} risultati su {form[options.section].length}
          </span>
          <button type="button" className="btn btn-ghost" onClick={() => addRow(options.section)}>
            <Plus size={15} /> {options.addLabel}
          </button>
        </div>
      </div>

      <label className="search-field" style={{ marginBottom: 14 }}>
        <Search size={16} />
        <input
          type="text"
          value={search[options.section]}
          onChange={(event) => setSearch((prev) => ({ ...prev, [options.section]: event.target.value }))}
          placeholder={options.searchPlaceholder}
        />
      </label>

      {options.rows.length === 0 ? (
        <div className="config-empty">
          <p>Nessuna riga trovata per questa ricerca.</p>
        </div>
      ) : (
        <div className="config-rows">
          {options.rows.map((row) => {
            const realIndex = form[options.section].findIndex((candidate) => candidate === row);
            const rowName = String(row[options.primaryField] ?? "").trim() || `${options.title} #${realIndex + 1}`;
            return (
              <div className="config-row-card" key={`${options.section}-${row._originalInvito || row.invito || realIndex}`}>
                <div className="config-row-header">
                  <div className="config-row-title">
                    <Database size={15} />
                    <span>{rowName}</span>
                  </div>
                  <div className="config-section-actions">
                    {row._dirty && <span className="config-count">Modificato</span>}
                    <button
                      type="button"
                      className="btn btn-primary"
                      onClick={() => saveRow(options.section, realIndex)}
                      disabled={row._saving || row._deleting || !row._dirty}
                    >
                      <Save size={14} /> {row._saving ? "Salvataggio..." : "Salva"}
                    </button>
                    <button
                      type="button"
                      className="config-remove-btn"
                      onClick={() => deleteRow(options.section, realIndex)}
                      aria-label={`Rimuovi riga ${rowName}`}
                      disabled={row._saving || row._deleting}
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                </div>

                <div className="config-fields-grid">
                  {options.fields.map((field) => (
                    <label className="config-field" key={String(field.key)}>
                      <span>{field.label}</span>
                      <input
                        type={field.type ?? "text"}
                        value={String(row[field.key] ?? "")}
                        placeholder={field.placeholder}
                        onChange={(e) => updateRow(options.section, realIndex, String(field.key), e.target.value)}
                      />
                    </label>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );

  return (
    <div className="pg">
      <div className="manage-header">
        <div>
          <div className="pg-title" style={{ marginBottom: "0.35rem" }}>Gestione utenti</div>
          <p className="manage-subtitle">
            Cerca username o email e salva solo il singolo utente modificato, senza ricaricare tutte le tabelle.
          </p>
        </div>
      </div>

      <div className="manage-nav">
        <a href="#plex-users-section" className="manage-nav-link">Plex</a>
        <a href="#jelly-users-section" className="manage-nav-link">Jellyfin</a>
        <a href="#emby-users-section" className="manage-nav-link">Emby</a>
      </div>

      {error && <div className="login-error">{error}</div>}
      {success && <div className="save-success">{success}</div>}

      {loading ? (
        <div className="loading-wrap"><div className="spinner" /></div>
      ) : (
        <div className="manage-sections">
          {renderSection({
            id: "plex-users-section",
            title: "Plex",
            subtitle: "Tabella puser con ricerca live per email e salvataggio per singola riga.",
            section: "plex",
            rows: filteredRows.plex,
            fields: plexFields,
            addLabel: "Aggiungi Plex user",
            searchPlaceholder: "Cerca mail Plex",
            primaryField: "pmail",
          })}
          {renderSection({
            id: "jelly-users-section",
            title: "Jellyfin",
            subtitle: "Tabella juser con ricerca live per username e salvataggio per singola riga.",
            section: "jelly",
            rows: filteredRows.jelly,
            fields: jellyFields,
            addLabel: "Aggiungi Jelly user",
            searchPlaceholder: "Cerca username",
            primaryField: "user",
          })}
          {renderSection({
            id: "emby-users-section",
            title: "Emby",
            subtitle: "Tabella euser con ricerca live per username e salvataggio per singola riga.",
            section: "emby",
            rows: filteredRows.emby,
            fields: embyFields,
            addLabel: "Aggiungi Emby user",
            searchPlaceholder: "Cerca username",
            primaryField: "user",
          })}
        </div>
      )}
    </div>
  );
}
