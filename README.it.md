# swarmer — uno sciame di agenti universale per gli agenti di programmazione

*[English](README.md)*

**swarmer** (nella 4.0 *sciame*) è una squadra di agenti specialistici per gli agenti di programmazione — Claude Code,
Codex, Antigravity, Gemini CLI e ogni strumento che legge `AGENTS.md` e le Agent Skills — che un coordinatore convoca
per una richiesta, con una di otto strategie. I ruoli sono **professionisti** (le competenze generali) e
**sottoprofessionisti** (le loro specializzazioni), in un database unico, in inglese e, se si vuole, nelle altre lingue della skill. Tutta la skill
(documenti, database e motore) sta in un file solo, `swarmer.sh`, con la sola bash e la libreria standard di Python.
La versione 5.2 aggiunge le estensioni facoltative, la prima delle quali è incroci (le decisioni di un progetto come
grafo, e la via del ritorno a un bivio a monte), e cancelli più severi per le convocazioni; la 5.1 l'ha resa
universale (la 5.0 era solo per Claude Code, e succedeva a `sciame` 4.0, che aggiorna sul posto).

## Installare

```
# un file solo, in qualunque progetto
curl -fsSLO https://raw.githubusercontent.com/GritHat/swarmer/main/sciame.sh
bash sciame.sh installa --lingua it          # senza --lingua l'installazione è in inglese
bash sciame.sh installa --lingua it --destinazioni codex,gemini   # solo alcuni strumenti (di difetto: quelli del progetto)

# oppure, in Claude Code, come plugin (uno dei modi d'installazione)
/plugin marketplace add GritHat/swarmer
/plugin install swarmer
/sciame-installa it

# oppure da Agensi (agensi.io): SKILL.md e un piccolo script che legge ruoli e protocollo a richiesta
# dal catalogo pubblicato su GitHub Pages (niente da installare); swarmer-crossroads è un'inserzione a parte,
# facoltativa, per i progetti che hanno già swarmer 5.2+ con incroci attiva
```

`sciame.sh` è una copia identica di `swarmer.sh`: i due URL valgono. Poi riapri la sessione del tuo agente di
programmazione e convoca lo sciame con una skill (in Claude Code anche come comando con la barra; in Codex, Antigravity
e Gemini CLI nominando la skill nel prompt; in un'installazione italiana le skill hanno i nomi di sempre):

| strategia | skill | per | agenti |
|---|---|---|---|
| singolo | `/sciame-singolo` | una domanda chiara di un campo | 1 |
| ventaglio | `/sciame-ventaglio` | un lavoro divisibile in fette parallele, o una gara con la regola di scelta dichiarata prima | 2–16 |
| classica | `/sciame-classica` | decidere, progettare, correggere, dimostrare, misurare: corsie cieche, triage, torneo dei falsificatori, rami, verdetti | 6–15 |
| giuria | `/sciame-giuria` | decidere una proposta istruita: il consenso approva, la maggioranza rivede (al più 3 giri, senza regressioni), la minoranza respinge | 7–11 |
| giuria leggera | `/sciame-giuria-leggera` | decisioni piccole e poco influenti, o dove una prova veloce scopre l'errore: tre giurati, prova prima del voto, un giro, poi la giuria ordinaria | 5 |
| completa | `/sciame-completa` | domande strategiche o aperte: tutti i professionisti, ciechi, senza voto, poi una classica | tutti + classica |
| plenaria | `/sciame-plenaria` | passaggi di fase e scelte enormemente importanti: completa, convocazione usuale, passata critica, due arbitri, voto finale | 60–80 e oltre |
| esperto | `/sciame-esperto` | una competenza che manca: scheda provvisoria, richiesta registrata, ruolo creato alla soglia | 1 |
| auto | `/sciame` | sceglie il coordinatore la strategia più economica che basta, e lo dice | — |

Dalla shell: `bash sciame/sciame.sh <strategia> "richiesta" [--cli claude|codex|agy|gemini]` apre lo strumento con
la skill. Le opzioni dello sciame vanno prima o dopo la richiesta; allo strumento passa solo ciò che segue `--`
(`… singolo "richiesta" --cli claude -- --permission-mode plan`), e ogni altra parola in più è un errore.
`bash sciame/sciame.sh aiuto` elenca tutti i comandi.
Ogni comando, opzione e valore ha anche il nome inglese (`install`, `single`, `--folder`, …), che vale in ogni
installazione; le opzioni abbreviate non valgono più.

## Estensioni

Ogni estensione viaggia dentro `sciame.sh`; un progetto attiva quelle che vuole con
`bash sciame/sciame.sh estensioni --aggiungi <nome>` (e `--togli`), che aggiunge la sua skill, i suoi documenti e il
suo blocco a ogni skill di strategia.

| estensione | skill | per |
|---|---|---|
| incroci (crossroads) | `/sciame-incroci` | le decisioni dell'utente, dello sciame e delle giurie come grafo, con le opzioni scartate e le ragioni; commit per area; quando il progetto è bloccato, la decisione a monte, la sua sintesi in pagine limitate e la sua inversione su un ramo nuovo (`bash sciame/sciame.sh incroci …`) |

## Con quali strumenti funziona

swarmer non è legato a un solo strumento: genera i suoi agenti e le sue skill per ogni **destinazione** del progetto,
e il coordinatore è l'agente di programmazione che vi apri.

| destinazione | strumento | agenti | skill | istruzioni | si apre con |
|---|---|---|---|---|---|
| `claude` | Claude Code | `.claude/agents/sciame-<sigla>.md` | `.claude/skills/<skill>/SKILL.md` | `CLAUDE.md` | `claude` |
| `codex` | Codex CLI (OpenAI) | `.codex/agents/sciame-<sigla>.toml` | `.agents/skills/<skill>/SKILL.md` | `AGENTS.md` | `codex` |
| `antigravity` | Antigravity (app e `agy`) | `.agents/agents/sciame-<sigla>.md` | `.agents/skills/<skill>/SKILL.md` | `AGENTS.md` | `agy` |
| `gemini` | Gemini CLI | `.gemini/agents/sciame-<sigla>.md` | `.agents/skills/<skill>/SKILL.md` | `GEMINI.md` | `gemini` |
| `agents` | ogni strumento che legge lo standard aperto | — | `.agents/skills/<skill>/SKILL.md` | `AGENTS.md` | — |

Un'installazione nuova prende le destinazioni che trova nel progetto (`.claude/`, `.codex/`, `.gemini/`, `.agents/`,
`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`) più `agents`, o tutte in un progetto vuoto; `--destinazioni claude,codex,…` le
sceglie, e `bash sciame/sciame.sh destinazioni [--aggiungi X] [--togli X]` le cambia dopo (i file generati di una
destinazione tolta se ne vanno, quelli del progetto mai; una destinazione inattiva non si tocca né si esamina).
`disable-model-invocation` (completa, plenaria) c'è solo in Claude Code: nelle skill comuni il divieto sta nella
descrizione. Le skill comuni a Codex, Antigravity, Gemini CLI e allo
standard aperto si scrivono una volta sola, in `.agents/skills/`. In uno strumento senza sottoagenti il coordinatore
svolge i ruoli in sequenza e lo dice. `istruzioni` scrive il paragrafo dello sciame nel file di istruzioni di ogni
destinazione attiva, solo quando lo si chiede.

## Che cosa la distingue

- **Ogni consegna basta da sola**: scopo e criterio di fatto, ingressi, spazio di scrittura e spazio vietato, la
  verifica da eseguire, e una risposta che comincia con FATTO, PROBLEMI o BLOCCATO. I rapporti degli agenti sono
  evidenze, non prove: il coordinatore riesegue i controlli promessi sul risultato integrato.
- **Le decisioni sono verificabili**: i voti delle giurie sono sigillati (sha256), ciechi, ricontati dai file da
  `giuria.py`, con una clausola dell'obiettivo (bersaglio, catena, controfattuale, costo) che ogni proposta deve
  passare.
- **Lo sciame cresce quando serve**: le competenze mancanti si chiedono con un motivo; tre richiedenti in una
  convocazione, o tre richieste in due convocazioni, fanno un professionista nuovo, che entra nel database, negli
  agenti e in `swarmer.sh`.
- **Gli override locali**: le schede proprie di un progetto stanno in `sciame/locale/`, hanno sempre la priorità sui
  ruoli generici, possono contenere i dettagli privati del progetto e non si pubblicano mai.
- **Onesto sull'ambiente**: senza sottoagenti, shell o scritture, il coordinatore tiene le fasi e dice che cosa si è
  ridotto (`AMBIENTE.md`). Sa come delega ogni strumento (Agent in Claude Code, l'avvio per nome in Codex,
  `invoke_subagent` in Antigravity, lo strumento del sottoagente in Gemini CLI, dove `@nome` è la scorciatoia dell'utente) e i suoi limiti.

## Lingue

Inglese (di difetto) e italiano. Si cambia con `bash sciame/sciame.sh lingua it` (agenti, skill e documenti si
rigenerano con i nomi della lingua), o per una convocazione con `lingua=it`. In un'installazione italiana tutto ciò che
si scrive nel progetto è italiano: la cartella `sciame/`, gli agenti e le skill `sciame-*`, `GIURIA.md`, le righe del
protocollo; le righe di giurie e convocazioni si leggono nelle due lingue. Le lingue nuove si propongono con una pull
request: vedi [CONTRIBUTING.it.md](CONTRIBUTING.it.md).

## Aggiornare dalla 4.0

```
curl -fsSLO https://raw.githubusercontent.com/GritHat/swarmer/main/sciame.sh
bash sciame.sh -C <progetto> aggiorna
```

L'aggiornamento rinomina solo ciò che è dello sciame (il motore, il database, lo stato interno: `FABBRICA.json` →
`FACTORY.json`, `catalogo.json` → `catalog.json`, …) e mai i file del progetto: configurazione, schede locali,
registro degli esperti, parole vietate, convocazioni e giurie restano con i loro nomi, e ogni ESITO già votato si
riconta identico byte per byte. Una 4.0 italiana resta italiana, con gli stessi agenti e le stesse skill `sciame-*`;
una 4.0 inglese passa a `swarmer-*` e ai nomi inglesi, con `sciame.sh`, `convoca.py` e `giuria.py` come alias. Un
aggiornamento interrotto riprende con lo stesso comando.

## Aggiornare dalla 5.1

Lo stesso `aggiorna` non attiva nessuna estensione (`bash sciame/sciame.sh estensioni --aggiungi incroci` quando la
vuoi) e lascia validi tutti i cancelli già approvati: una convocazione cominciata prima tiene le regole 1 dei suoi
cancelli, una nuova nasce con le regole 2, e `cancello C FASE --regole 2` le applica a un cancello nuovo di una
convocazione più vecchia.

## Aggiornare dalla 5.0

Lo stesso `aggiorna` lascia un'installazione 5.0 com'era: solo Claude Code, gli stessi agenti byte per byte, le
stesse skill (il loro testo guadagna la sezione su come delegare in ogni strumento), la configurazione intatta; le
cartelle degli altri strumenti non si toccano né si esaminano. Gli altri strumenti si aggiungono quando servono:
`bash sciame/sciame.sh destinazioni --aggiungi codex,gemini`.

**Il ritorno alla 4.0 non è supportato**: un `sciame.sh` 4.0 non riconosce `FACTORY.json`, `engine/` né i segni della
5.0. Le altre rotture: le opzioni abbreviate si rifiutano; le giurie nuove leggono anche le righe inglesi, e le righe
quasi conformi in `SIGILLI.md`, `DELEGA.md` e `PERTINENZA.md`, o un gettone di giro che non nomina un giro, sono
errori.

## Proporre un professionista nuovo

Apri una pull request che aggiunge una voce a `db/professionals.json`, con i testi inglesi completi (obbligatori; le
altre lingue sono facoltative, e un'installazione traduce quella che manca al primo uso)
(modello: `.github/PULL_REQUEST_TEMPLATE/nuovo_professionista.md`), oppure da un progetto con lo sciame installato:
`bash sciame/sciame.sh approva scheda.json` e poi `bash sciame/sciame.sh proponi <sigla> --invia`.

## La struttura del repository

| percorso | contenuto |
|---|---|
| `db/` | il database unico dei professionisti, dei sottoprofessionisti e dei nuclei (`professionals.json`, `cores.json`) |
| `docs/<lingua>/` | i documenti, una cartella per lingua, con i nomi canonici inglesi |
| `i18n/<lingua>.json` | i testi del generatore e dei comandi, e i nomi localizzati di comandi, opzioni, valori e file |
| `engine/` | il motore: `swarmer.py` (la riga di comando), `generate.py` (i generatori di ogni destinazione), `professionals.py`, `convene.py`, `jury.py`, `compat.py` (i nomi italiani e i formati della 4.0), `head.sh` |
| `wrappers/` | `convene.py` e `jury.py`, copiati alla radice dell'installazione (in italiano anche `convoca.py`, `giuria.py`) |
| `extensions/` | le estensioni, una cartella ciascuna (`extension.json`, `engine/`, `docs/<lingua>/`, `i18n/<lingua>.json`): `crossroads` |
| `tests/` | le batterie |
| `swarmer.sh` | il file unico: `python3 -I -B engine/swarmer.py --swarm . build --output swarmer.sh` |
| `sciame.sh` | la copia byte per byte di `swarmer.sh`, per l'URL della 4.0 |
| `agensi/` | l'edizione per Agensi: `SKILL.md` e `scripts/swarm.py`, che legge a richiesta il catalogo che `.github/scripts/agensi.py` genera da `db/` e `docs/en/` (un file JSON per ruolo, strategia e documento) e `.github/workflows/agensi.yml` pubblica su GitHub Pages (`gh-pages`, `api/v1/`, con le pagine della documentazione in `docs/`), con il pacchetto come release; `agensi/crossroads/`, il pacchetto a parte di sole istruzioni `swarmer-crossroads` (`SKILL.md`, più `references/COMMANDS.md` generato dalla guida dell'estensione), pubblicato per conto suo |
| `skills/` | le skill d'installazione `swarmer-install` e `sciame-installa` (formato Agent Skills: ogni strumento che legge le skill) |
| `.claude-plugin/` | i manifesti del plugin di Claude Code, uno dei modi d'installazione |

## Sostieni il progetto

swarmer è libero e con licenza MIT. Se ti fa risparmiare tempo, puoi sostenerne lo sviluppo su
[Ko-fi](https://ko-fi.com/GritHat).

Licenza: MIT.
