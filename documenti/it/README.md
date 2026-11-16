# Lo sciame di agenti per Claude Code (versione 4.0)

Uno sciame di professionisti e sottoprofessionisti specialistici, che un coordinatore convoca per una richiesta con
una di otto strategie. Il coordinatore è la sessione di Claude Code aperta nel progetto; gli agenti sono i suoi
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

Dentro Claude Code le stesse convocazioni sono `/sciame-singolo`, `/sciame-ventaglio`, `/sciame-classica`,
`/sciame-giuria`, `/sciame-completa`, `/sciame-plenaria`, `/sciame-esperto` e `/sciame`.

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

Il database unico è `db/professionisti.json`: ogni voce ha la sigla, il tipo, il genitore (per un
sottoprofessionista), il nucleo, la versione e i testi in ogni lingua. `AGENTI.md`, gli agenti, le skill e il
catalogo si generano da lì, nella lingua scelta: non si modificano a mano.

`bash sciame/sciame.sh professionisti` stampa l'albero; `bash sciame/sciame.sh ruoli "domanda"` i ruoli che una
domanda richiama.

## Le lingue

`bash sciame/sciame.sh lingua en` passa all'inglese, `lingua it` all'italiano: agenti, skill e documenti si
rigenerano. All'installazione: `--lingua`. Per una sola convocazione: `lingua=en` in testa alla richiesta, o
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
agenti che il progetto genera da sé.

## Gli esperti nuovi

Una competenza che manca si chiede: nelle consegne con la riga `ESPERTO-MANCANTE`, dal coordinatore con la strategia
esperto. Le richieste vanno in `sciame/RICHIESTE_ESPERTI.md`; `bash sciame/sciame.sh richieste` dice quali sono
arrivate alla soglia. Approvata la creazione, `bash sciame/sciame.sh approva <scheda.json>`:
1. la aggiunge al database;
2. rigenera agenti, skill e documenti;
3. ricostruisce `sciame.sh`, così la copia portabile è sempre aggiornata;
4. scrive la proposta in `sciame/proposte/`.

`bash sciame/sciame.sh proponi <sigla> --invia` apre la pull request al repository pubblico dello sciame (serve `gh`).

## I file di questa cartella

| file | che cosa contiene |
|---|---|
| `sciame.sh` | un file solo: installa, avvia, aggiorna; porta con sé tutti gli altri |
| `db/` | il database unico dei professionisti e dei nuclei |
| `documenti/<lingua>/` | i documenti nelle lingue della skill |
| `i18n/<lingua>.json` | i testi del generatore e dei comandi |
| `motore/` | il codice: `sciame.py` (la riga di comando), `genera.py`, `professionisti.py`, `convoca.py`, `giuria.py` |
| `prove/` | le batterie: `bash sciame/sciame.sh prove` |
| `AGENTI.md`, `PIPELINE.md`, `PREAMBOLO.md`, `GIURIA.md`, `AMBIENTE.md`, `ISTRUZIONI_COORDINATORE.md`, `SCHEDA_IPOTESI.md` | generati nella lingua scelta |
| `convoca.py`, `giuria.py`, `genera_agenti.py` | i comandi di sempre, che passano al motore |
| `catalogo.json`, `VERSIONE`, `LINGUA`, `FABBRICA.json` | generati e di stato |
| `locale/`, `RICHIESTE_ESPERTI.md`, `proposte/` | del progetto: mai distribuiti |

## Aggiornare

`bash sciame-nuovo.sh -C <progetto> aggiorna`. I file di fabbrica che il progetto non ha cambiato si aggiornano.
Quelli cambiati restano com'erano, e la versione nuova va accanto con il suffisso `.nuovo`. Il database si unisce:
le voci nuove si aggiungono e quelle del progetto restano. Da una 3.x le schede si conservano in una copia di
sicurezza, e `importa-schede` porta nel database quelle che il progetto aveva aggiunto.
