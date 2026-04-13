import { useEffect, useMemo, useState } from "react";
import { CircleDollarSign, MailPlus, Sparkles, Tv, Tv2 } from "lucide-react";
import api from "../api/client";

type PrezzoRow = {
  servizio: string;
  streaming: number;
  prezzo_mensile: number | null;
};

type PrezziMap = Record<string, Record<number, number | null>>;

const SERVICES = [
  {
    key: "emby_normale",
    label: "Emby Normale",
    icon: Tv,
    accent: "#f5b84b",
    badge: "Classico",
    description: "L'opzione Emby piu accessibile, pensata per utilizzi standard e rinnovi flessibili.",
  },
  {
    key: "emby_premium",
    label: "Emby Premium",
    icon: Sparkles,
    accent: "#8b5cf6",
    badge: "Premium",
    description: "La fascia Emby con priorita alta, perfetta per chi vuole il livello premium disponibile.",
  },
  {
    key: "jellyfin",
    label: "Jellyfin",
    icon: Tv2,
    accent: "#00a4dc",
    badge: "Open",
    description: "Formula Jellyfin con prezzi mensili in crediti e calcolo proporzionale sui giorni.",
  },
  {
    key: "plex",
    label: "Plex",
    icon: MailPlus,
    accent: "#e5a00d",
    badge: "Invite",
    description: "Inviti Plex con listino dedicato per numero di schermi, espresso sempre in crediti.",
  },
] as const;

function buildMap(rows: PrezzoRow[]): PrezziMap {
  const map: PrezziMap = {};
  for (const service of SERVICES) {
    map[service.key] = { 1: null, 2: null, 3: null, 4: null };
  }
  for (const row of rows) {
    if (map[row.servizio]) {
      map[row.servizio][row.streaming] = row.prezzo_mensile;
    }
  }
  return map;
}

function formatCredits(value: number | null) {
  if (value == null) return "Non disponibile";
  return `${value.toFixed(2)} crediti`;
}

export default function PublicPrezzi() {
  const [rows, setRows] = useState<PrezzoRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get("/prezzi")
      .then((response) => setRows(response.data))
      .catch((err: any) => {
        setError(err?.response?.data?.detail ?? "Errore durante il caricamento dei prezzi.");
      })
      .finally(() => setLoading(false));
  }, []);

  const prices = useMemo(() => buildMap(rows), [rows]);

  if (loading) {
    return (
      <div className="pg">
        <div className="loading-wrap"><div className="spinner" /></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="pg">
        <div className="login-error">{error}</div>
      </div>
    );
  }

  return (
    <div className="pg">
      <div className="price-showcase-hero">
        <div className="price-showcase-copy">
          <div className="price-showcase-kicker">Listino</div>
          <h1 className="price-showcase-title">Prezzi dei servizi</h1>
          <p className="price-showcase-subtitle">
            Tutti i valori sono espressi in crediti mensili. Il pannello usa questi prezzi come base
            anche per i calcoli proporzionali su giorni e rinnovi.
          </p>
        </div>
        <div className="price-showcase-highlight">
          <div className="price-showcase-highlight-icon">
            <CircleDollarSign size={20} />
          </div>
          <div>
            <div className="price-showcase-highlight-label">Valuta interna</div>
            <div className="price-showcase-highlight-value">Crediti</div>
          </div>
        </div>
      </div>

      <div className="price-showcase-grid">
        {SERVICES.map((service) => {
          const Icon = service.icon;
          const values = prices[service.key] ?? { 1: null, 2: null, 3: null, 4: null };
          const available = Object.values(values).filter((value): value is number => value !== null);
          const fromPrice = available.length ? Math.min(...available) : null;

          return (
            <section
              key={service.key}
              className="price-service-card"
              style={{
                ["--price-accent" as any]: service.accent,
              }}
            >
              <div className="price-service-top">
                <div className="price-service-icon">
                  <Icon size={18} />
                </div>
                <span className="price-service-badge">{service.badge}</span>
              </div>

              <div className="price-service-name">{service.label}</div>
              <div className="price-service-desc">{service.description}</div>

              <div className="price-service-from">
                <span className="price-service-from-label">Da</span>
                <span className="price-service-from-value">
                  {fromPrice == null ? "—" : `${fromPrice.toFixed(2)} crediti`}
                </span>
                <span className="price-service-from-period">al mese</span>
              </div>

              <div className="price-tier-list">
                {[1, 2, 3, 4].map((screens) => (
                  <div key={screens} className="price-tier-row">
                    <div className="price-tier-left">
                      <span className="price-tier-screen">{screens}</span>
                      <span className="price-tier-label">{screens === 1 ? "schermo" : "schermi"}</span>
                    </div>
                    <div className="price-tier-value">
                      {formatCredits(values[screens])}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          );
        })}
      </div>
    </div>
  );
}
