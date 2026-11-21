# swarmer: lo sciame di agenti universale per gli agenti di programmazione (versione 5.3)

Uno sciame di professionisti e sottoprofessionisti specialistici, che un coordinatore convoca per una richiesta con
una di otto strategie. Il coordinatore è la sessione dell'agente di programmazione aperta nel progetto (Claude Code,
Codex, Antigravity, Gemini CLI o un altro strumento che legge `AGENTS.md` e le Agent Skills); gli agenti sono i suoi
sottoagenti `sciame-<sigla>`.

**Il setup e l'avvio sono tutti in `sciame.sh`:** `bash sciame/sciame.sh aiuto` li stampa. In breve:

```
bash sciame.sh installa [--lingua it|en]       # una volta per progetto
bash sciame/sciame.sh singolo   "richiesta"     # esperto singolo
bash sciame/sciame.sh ventaglio "richiesta"     # N agenti in parallelo: fette o gara
bash sciame/sciame.sh classica  "richiesta"     # la pipeline a grafo
bash sciame/sciame.sh giuria    "richiesta"     # una proposta, un voto
bash sciame/sciame.sh completa  "richiesta"     # tutto lo sciame, senza voto, poi la classica
bash sciame/sciame.sh plenaria  "richiesta"     # le scelte più gravi: cinque livelli e il voto finale
bash sciame/sciame.sh esperto   "richiesta"     # una competenza che lo sciame non ha ancora
bash sciame/sciame.sh auto      "richiesta"     # sceglie il coordinatore
```

`sciame.sh` passa a `swarmer.sh`, che contiene tutto: i due nomi valgono, come i nomi inglesi dei comandi
(`install`, `single`, …).

Dalla shell, `--cli claude|codex|agy|gemini` sceglie lo strumento da aprire (di difetto: la chiave `cli` di
`.sciame/config.json`, altrimenti il primo, in quest'ordine, la cui destinazione è attiva e che si trova nel PATH).
Le opzioni vanno prima o dopo la richiesta; allo strumento passa solo ciò che segue `--`. Dentro lo strumento le stesse
convocazioni sono le skill `sciame-singolo`, `sciame-ventaglio`, `sciame-classica`, `sciame-giuria`,
`sciame-giuria-leggera`, `sciame-completa`, `sciame-plenaria`, `sciame-esperto` e `sciame` (in Claude Code anche come
comandi con la barra, `/sciame-singolo` …).

## Le destinazioni

Gli agenti e le skill si generano per le destinazioni del progetto (`bash sciame/sciame.sh destinazioni`):

| destinazione | agenti | skill | istruzioni |
|---|---|---|---|
| `claude` | `.claude/agents/sciame-<sigla>.md` | `.claude/skills/` | `CLAUDE.md` |
| `codex` | `.codex/agents/sciame-<sigla>.toml` | `.agents/skills/` | `AGENTS.md` |
| `antigravity` | `.agents/agents/sciame-<sigla>.md` | `.agents/skills/` | `AGENTS.md` |
| `gemini` | `.gemini/agents/sciame-<sigla>.md` | `.agents/skills/` | `GEMINI.md` |
| `agents` | — | `.agents/skills/` | `AGENTS.md` |

Un'installazione nuova prende le destinazioni che trova nel progetto (`.claude/`, `.codex/`, `.gemini/`, `.agents/`,
`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`) più `agents`, o tutte se non ne trova nessuna; `--destinazioni` le sceglie.
Un aggiornamento di un'installazione senza la chiave `destinazioni` resta solo Claude Code. `destinazioni --aggiungi
X`, `--togli X` o un elenco le cambiano: i file generati di una destinazione tolta se ne vanno, quelli del progetto
mai.

## Le strategie

Sono definite in `PIPELINE.md`; giuria, esperti nuovi e plenaria nei dettagli in `GIURIA.md`.

| strategia | per | agenti |
|---|---|---|
| singolo | una domanda chiara di un campo | 1 |
| ventaglio | un lavoro divisibile, o più tentativi in gara con la regola di scelta dichiarata prima | 2–16 |
| classica | decidere, progettare, correggere, dimostrare, misurare | 6–15 |
| giuria | decidere una proposta già istruita: consenso approva, maggioranza rivede, minoranza respinge | 7–11 |
| giuria leggera | decisioni piccole o provabili in fretta: tre giurati, la prova prima del voto, un giro | 5 |
| completa | domande strategiche o aperte, tutti i punti di vista, senza voto | tutti i professionisti più la classica |
| plenaria | i passaggi di fase e le scelte d'impatto enormemente importante | 60–80 e oltre |
| esperto | una competenza che manca: scheda provvisoria, richiesta registrata, creazione alla soglia | 1 |
| auto | non si sa quale: sceglie il coordinatore, la più economica che basta | — |

Ogni consegna segue lo stesso modello (`PIPELINE.md`, «La consegna, in ogni strategia»): scopo e criterio di fatto,
ingressi, spazio di scrittura e spazio vietato, verifica, risposta con FATTO, PROBLEMI o BLOCCATO in testa.

## I ruoli: professionisti e sottoprofessionisti

Il database unico è `db/professionals.json`: ogni voce ha la sigla, il tipo, il genitore (per un
sottoprofessionista), il nucleo, la versione e i testi: l'inglese sempre e completo, le altre lingue facoltative. Un
ruolo senza la lingua dell'installazione si genera dall'inglese con il segno `translation-pending: <lingua>`, e il
coordinatore lo traduce alla prima convocazione con `bash sciame/sciame.sh traduci <sigla> <file.json>`
(sovrapposizione locale `locale/traduzioni/`, mai pubblicata: `locale/LEGGIMI.md` di questa cartella). `AGENTI.md`, gli agenti, le skill e il
catalogo si generano da lì, nella lingua scelta: non si modificano a mano. Le sigle dei ruoli sono dati e sono
le stesse in ogni lingua.

`bash sciame/sciame.sh professionisti` stampa l'albero; `bash sciame/sciame.sh ruoli "domanda"` i ruoli che una
domanda richiama.

## Le lingue

`bash sciame/sciame.sh lingua en` passa all'inglese, `lingua it` all'italiano: agenti, skill e documenti si
rigenerano con i nomi della lingua (in inglese `swarmer-*`, `PREAMBLE.md`, `convene.py`, …). All'installazione:
`--lingua`; un'installazione nuova senza `--lingua` è in inglese. Per una sola convocazione: `lingua=en` in testa alla richiesta, o
`--lingua`. Una lingua nuova si aggiunge con una pull request al repository dello sciame (`CONTRIBUTING.md`).

## Gli override locali

Le schede proprie di un progetto stanno in `sciame/locale/AGENTI.md`. Per la stessa sigla una scheda locale ha
**sempre** la priorità sul ruolo generico; una sigla che c'è solo lì è un ruolo solo locale. La cartella `locale/` può
contenere i dettagli del progetto e non va mai nel repository pubblico: `costruisci`, `approva`, `proponi` e
`verifica` non la distribuiscono, e rifiutano ogni testo pubblico con le parole di `locale/VIETATE.txt`. In un
progetto che ha già uno sciame proprio:

```
bash sciame.sh installa --cartella sciame/skill --locale sciame --gestiti-dal-progetto
```

installa la skill in una cartella sua, prende le schede del progetto come override e non scrive né cancella gli
agenti che il progetto genera da sé in `.claude/agents/`; nelle altre destinazioni (Codex, Antigravity, Gemini CLI) li
genera dalle schede locali, salvo un file del progetto senza la nota. `controlla` segnala un override che il progetto
non ha generato. Le schede locali arrivano negli agenti di ogni destinazione: quei file hanno la riservatezza di
`locale/`.

## Gli esperti nuovi

Una competenza che manca si chiede: nelle consegne con la riga `ESPERTO-MANCANTE`, dal coordinatore con la strategia
esperto. Le richieste vanno in `sciame/RICHIESTE_ESPERTI.md`; `bash sciame/sciame.sh richieste` dice quali sono
arrivate alla soglia. Approvata la creazione, `bash sciame/sciame.sh approva <scheda.json>`:
1. la aggiunge al database;
2. rigenera agenti, skill e documenti;
3. ricostruisce `sciame.sh`, così la copia portabile è sempre aggiornata;
4. scrive la proposta in `sciame/proposte/`.

`bash sciame/sciame.sh proponi <sigla> --invia` apre la pull request al repository pubblico dello sciame (serve `gh`),
sempre in inglese: una voce senza i testi inglesi completi si rifiuta finché `traduci <sigla> <file.json> --lingua en`
non li aggiunge.

## Le estensioni
Un'estensione aggiunge comandi, una skill, documenti e un blocco di istruzioni per il coordinatore, e tiene il proprio
stato sotto `.sciame/`. Ogni estensione viaggia dentro `sciame.sh` (cartella `extensions/`); attivarla è una scelta
del progetto: `bash sciame/sciame.sh estensioni` le elenca, `estensioni --aggiungi <nome>` ne attiva una (chiave
`estensioni` di `.sciame/config.json`, poi rigenera), `estensioni --togli <nome>` la disattiva e lascia la sua
cartella di stato, che è del progetto. La prima è **incroci** (`bash sciame/sciame.sh incroci …`, skill
`sciame-incroci`, documenti `INCROCI.md` e `FORMATI_INCROCI.md`): le decisioni dell'utente, dello sciame e delle
giurie come grafo, i commit per area, e la strada per tornare a un bivio a monte su un ramo nuovo.

## I file di questa cartella

| file | che cosa contiene |
|---|---|
| `swarmer.sh` | un file solo: installa, avvia, aggiorna; porta con sé tutti gli altri |
| `sciame.sh` | il nome di sempre: passa a `swarmer.sh` |
| `db/` | il database unico dei professionisti e dei nuclei (`professionals.json`, `cores.json`) |
| `docs/<lingua>/` | i documenti nelle lingue della skill |
| `i18n/<lingua>.json` | i testi del generatore e dei comandi, e i nomi di ogni lingua |
| `engine/` | il codice: `swarmer.py` (la riga di comando), `generate.py`, `professionals.py`, `convene.py`, `jury.py`, `compat.py` (i nomi italiani della 4.0) |
| `tests/` | le batterie: `bash sciame/sciame.sh prove` |
| `AGENTI.md`, `PIPELINE.md`, `PREAMBOLO.md`, `GIURIA.md`, `AMBIENTE.md`, `ISTRUZIONI_COORDINATORE.md`, `SCHEDA_IPOTESI.md` | generati nella lingua scelta |
| `convoca.py`, `giuria.py`, `genera_agenti.py` | i comandi di sempre, che passano al motore |
| `catalog.json`, `VERSION`, `LANGUAGE`, `ROOT`, `FACTORY.json` | generati e di stato (nella 4.0 `catalogo.json`, `VERSIONE`, `LINGUA`, `RADICE`, `FABBRICA.json`) |
| `locale/`, `RICHIESTE_ESPERTI.md`, `proposte/` | del progetto: mai distribuiti |

## Aggiornare

`bash swarmer.sh -C <progetto> aggiorna`, con il `swarmer.sh` nuovo (o `sciame.sh`, scaricato di nuovo). I file di fabbrica che il progetto non ha cambiato si aggiornano.
Quelli cambiati restano com'erano, e la versione nuova va accanto con il suffisso `.nuovo`. Il database si unisce:
le voci nuove si aggiungono e quelle del progetto restano. Da una 3.x le schede si conservano in una copia di
sicurezza, e `importa-schede` porta nel database quelle che il progetto aveva aggiunto.

**Dalla 4.0.** Lo stesso comando aggiorna un'installazione 4.0: lo stato interno, il motore e il database prendono
i nomi 5.0, mentre i file del progetto (configurazione, schede locali, registro degli esperti, parole vietate,
convocazioni e giurie) non si rinominano mai. Una 4.0 italiana resta italiana, con gli stessi agenti e le stesse
skill (`sciame-*`); `sciame.sh`, `convoca.py`, `giuria.py` e `genera_agenti.py` restano come alias. Il ritorno
alla 4.0 non è supportato.

**Dalla 5.0.** L'aggiornamento alla 5.1 o successiva lascia un'installazione 5.0 com'era: solo Claude Code, gli stessi agenti
byte per byte, le stesse skill (con la sezione nuova su come delegare in ogni strumento). Le altre destinazioni si aggiungono a richiesta:
`bash sciame/sciame.sh destinazioni --aggiungi codex,gemini`.

**Dalla 5.1.** L'aggiornamento alla 5.2 non attiva nessuna estensione
(`bash sciame/sciame.sh estensioni --aggiungi incroci` quando la vuoi) e lascia validi tutti i cancelli già
approvati: una convocazione cominciata prima tiene le regole 1 dei suoi cancelli, una nuova nasce con le regole 2
(`PIPELINE.md`, §«Le regole dei cancelli»).

**Dalla 5.2.** L'aggiornamento alla 5.3 lascia validi tutti i cancelli già approvati: una convocazione tiene le regole
dei suoi cancelli, una nuova nasce con le regole 3, che leggono l'ordine di f4 dai sigilli, e `cancello C FASE --regole 3`
le applica a un cancello nuovo di una convocazione più vecchia. `rifissa` apre un giro nuovo di un ramo, e dopo un G5
«non chiuso» la chiusura successiva va in `f5_2/` (`PIPELINE.md`, §«I rami, gli spazi di lavoro e la chiusura»;
`CHANGELOG.it.md`).
