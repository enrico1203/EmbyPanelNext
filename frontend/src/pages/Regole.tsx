import { BookOpenText, CirclePlay, Server, Store, Tag, Tv2, Users } from "lucide-react";

const RULE_SECTIONS = [
  {
    id: "vendita",
    title: "Regole Vendita",
    subtitle: "Prezzi, visibilita pubblica e rapporto con il master.",
    icon: <Tag size={18} />,
    defaultOpen: true,
    items: [
      "<strong>Vietato</strong> vendere sotto a 6 euro al mese.",
      "<strong>Vietato</strong> scrivere i prezzi del servizio in gruppi/canali pubblici.",
      "<strong>Vietato</strong> mettere foto/video del servizio in gruppi/canali pubblici.",
      "<strong>ESTREMAMENTE VIETATO</strong> dare i contatti o metodi di pagamento del proprio master ai clienti senza permesso.",
    ],
  },
  {
    id: "utenti",
    title: "Regole Utenti",
    subtitle: "Scadenze, prove e uso corretto degli account.",
    icon: <Users size={18} />,
    items: [
      "Gli utenti si cancellano definitivamente in automatico dopo 7 giorni dalla scadenza.",
      "E impossibile recuperare un utente eliminato.",
      "Gli account Emby sono personali: vietato dare 1 account a diversi clienti che non si conoscono.",
      "Non creare account con username prova, prova1, test. Se un utente vuole rinnovare deve usare lo stesso account, scegliendo un nome significativo.",
      "La prova gratuita minima e di 24 ore e la massima e di 3 giorni.",
    ],
  },
  {
    id: "streaming",
    title: "Regole Streaming",
    subtitle: "Comportamenti da evitare durante la riproduzione.",
    icon: <CirclePlay size={18} />,
    items: [
      "Vietato convertire file 4k in risoluzioni inferiori.",
      "Se abilitando i film 4k un utente riscontra problemi di riproduzione o buffering, questi devono essere disabilitati.",
      'Guida problemi di rete: <a href="https://telegra.ph/Guida-problemi-di-rete-EmbyItaly-03-14" target="_blank" rel="noopener noreferrer">telegra.ph/Guida-problemi-di-rete-EmbyItaly-03-14</a>',
    ],
  },
  {
    id: "server",
    title: "Server Normale vs Premium Emby",
    subtitle: "Differenze pratiche e uso delle app ufficiali.",
    icon: <Server size={18} />,
    items: [
      "Nessuna differenza di contenuti o prestazioni.",
      "Server Premium: e consentito usare le app Emby ufficiali su un massimo di 2-3 dispositivi (controllo periodico).",
      'Server Normale: l\'app ufficiale funziona solo su TV Samsung e LG; su altri dispositivi si usa il browser (preferibilmente Chrome) oppure le app disponibili <a href="https://t.me/StreamingItalia_bot?start=app" target="_blank" rel="noopener noreferrer">qui</a> (Android, AndroidTV, macOS, iOS con Infuse).',
    ],
  },
  {
    id: "plex",
    title: "Plex",
    subtitle: "Regole specifiche per inviti e utilizzo.",
    icon: <Tv2 size={18} />,
    items: [
      "1 account, 2 streaming contemporanei. Nessun limite di dispositivi per l'utente.",
      '<strong>IMPORTANTE E OBBLIGATORIO</strong>: prima di invitare un cliente, il cliente deve essersi registrato con una sua mail su <a href="https://app.plex.tv" target="_blank" rel="noopener noreferrer">app.plex.tv</a>.',
      'Applicazioni disponibili per quasi tutti i dispositivi: <a href="https://www.plex.tv/apps-devices/#players" target="_blank" rel="noopener noreferrer">plex.tv/apps</a>',
      "Errori riproduzione: impostare la qualita di riproduzione su massimo e togliere il limite dati mobili nelle impostazioni dell'app Plex.",
      "Su Plex gli utenti vengono cancellati appena scadono (rinnovare per tempo).",
      "Una volta ogni 6 mesi (o se vengono rilevati abusi) gli utenti dovranno riaccettare l'invito nella mail o dall'account Plex.",
    ],
  },
  {
    id: "resell",
    title: "Regole Resell",
    subtitle: "Requisiti minimi e comportamento commerciale.",
    icon: <Store size={18} />,
    items: [
      "Minimo 5 utenti attivi richiesti entro 2 mesi dall'attivazione.",
      "Non abusare delle prove gratuite: 1 cliente, 1 prova.",
      "Vietato fornire l'username o metodi di pagamento del proprio master ai clienti senza autorizzazione.",
      "Se il credito va in negativo, ricarica al piu presto; oltre un certo limite non sara piu possibile creare o rinnovare utenti e l'account verra disabilitato.",
    ],
  },
  {
    id: "master-reseller",
    title: "Regole Master/Reseller",
    subtitle: "Ricariche, passaggio di ruolo e rapporto tra master e reseller.",
    icon: <Users size={18} />,
    items: [
      "La ricarica minima verso un reseller e di 0.1 crediti.",
      "Se un reseller riceve una ricarica di 100 crediti, diventa Master e puo creare a sua volta altri reseller.",
      "E vietato aprire piu account reseller con persone diverse per aggirare le regole o frammentare la gestione.",
      "Per cambiare master devono essere d'accordo sia il master attuale sia il reseller interessato.",
    ],
  },
];

export default function Regole() {
  return (
    <div className="pg">
      <div className="pg-title" style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <span>Regole</span>
      </div>

      <div className="rules-intro-card">
        <div className="rules-intro-icon">
          <BookOpenText size={20} />
        </div>
        <div>
          <div className="rules-intro-title">Regole e linee guida</div>
          <div className="rules-intro-subtitle">Resta allineato alle policy per evitare blocchi o disservizi.</div>
        </div>
      </div>

      <div className="rules-page">
        {RULE_SECTIONS.map((section) => (
          <details key={section.id} className="rule-accordion" open={section.defaultOpen}>
            <summary className="rule-summary">
              <div className="rule-summary-main">
                <div className="rule-summary-icon">{section.icon}</div>
                <div>
                  <div className="rule-summary-title">{section.title}</div>
                  <div className="rule-summary-subtitle">{section.subtitle}</div>
                </div>
              </div>
              <span className="rule-summary-chevron" aria-hidden="true">⌄</span>
            </summary>

            <div className="rule-panel">
              <ul className="rule-list">
                {section.items.map((item, index) => (
                  <li key={`${section.id}-${index}`} dangerouslySetInnerHTML={{ __html: item }} />
                ))}
              </ul>
            </div>
          </details>
        ))}
      </div>
    </div>
  );
}
