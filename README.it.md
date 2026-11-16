# swarmer — uno sciame di agenti per Claude Code

*[English](README.md)*

**swarmer** (nella 4.0 *sciame*) è una squadra di agenti specialistici per Claude Code che un coordinatore convoca per
una richiesta, con una di otto strategie. I ruoli sono **professionisti** (le competenze generali) e
**sottoprofessionisti** (le loro specializzazioni), in un database unico, in inglese e, se si vuole, nelle altre lingue della skill. Tutta la skill
(documenti, database e motore) sta in un file solo, `swarmer.sh`, con la sola bash e la libreria standard di Python.
La versione 5.0 succede a `sciame` 4.0 e la aggiorna sul posto.

## Installare

```
# un file solo, in qualunque progetto
curl -fsSLO https://raw.githubusercontent.com/GritHat/swarmer/main/sciame.sh
bash sciame.sh installa --lingua it          # senza --lingua l'installazione è in inglese

# oppure come plugin di Claude Code
/plugin marketplace add GritHat/swarmer
/plugin install swarmer
/sciame-installa it
```

`sciame.sh` è una copia identica di `swarmer.sh`: i due URL valgono. Poi riapri la sessione di Claude Code e convoca
lo sciame (in un'installazione italiana le skill hanno i nomi di sempre):

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

Dalla shell: `bash sciame/sciame.sh <strategia> "richiesta"`; `bash sciame/sciame.sh aiuto` elenca tutti i comandi.
Ogni comando, opzione e valore ha anche il nome inglese (`install`, `single`, `--folder`, …), che vale in ogni
installazione; le opzioni abbreviate non valgono più.

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
  ridotto (`AMBIENTE.md`).

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
| `engine/` | il motore: `swarmer.py` (la riga di comando), `generate.py`, `professionals.py`, `convene.py`, `jury.py`, `compat.py` (i nomi italiani e i formati della 4.0), `head.sh` |
| `wrappers/` | `convene.py` e `jury.py`, copiati alla radice dell'installazione (in italiano anche `convoca.py`, `giuria.py`) |
| `tests/` | le batterie |
| `swarmer.sh` | il file unico: `python3 -I -B engine/swarmer.py --swarm . build --output swarmer.sh` |
| `sciame.sh` | la copia byte per byte di `swarmer.sh`, per l'URL della 4.0 |
| `skills/`, `.claude-plugin/` | il plugin di Claude Code (le skill d'installazione `swarmer-install` e `sciame-installa`, i manifesti) |

Licenza: MIT.
