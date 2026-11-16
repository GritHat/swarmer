# Contribuire

*[English](CONTRIBUTING.md)*

Sono benvenuti tre tipi di contributo, ciascuno come pull request.

## 1. Un professionista o un sottoprofessionista nuovo

Aggiungi una voce a `db/professionals.json` (formato 2; la forma è in [CONTRIBUTING.md](CONTRIBUTING.md)):
- `id` (la sigla) in minuscolo, parole unite da `-`, nuova, diversa dal nome di una strategia (in inglese o in
  italiano) e da `local`, `locale`, `light`, `leggera`; le sigle sono dati e restano le stesse in ogni lingua;
- un sottoprofessionista (`"type": "subprofessional"`) ha come `parent` un professionista dello stesso nucleo (un
  livello solo);
- i testi in **inglese**, completi (la CI rifiuta una voce senza); le altre lingue sono facoltative, e complete se ci
  sono: un'installazione in una lingua che la voce non ha genera l'agente dall'inglese con il segno
  `translation-pending: <lingua>` e lo traduce in locale al primo uso (`traduci`); il corpo segue la struttura delle schede (missione, competenze,
  domande che si pone sempre, metodi e strumenti, consegne tipiche, limiti, con chi si confronta), senza titoli `#`;
- nella pull request, quale competenza manca allo sciame e perché i ruoli vicini non la coprono;
- nessun dettaglio di progetti privati, nessun segreto, nessun dato personale.

Prima di aprirla:

```
python3 -I -B engine/swarmer.py --sciame . verifica
python3 -I -B engine/swarmer.py --sciame . costruisci --uscita swarmer.sh
for t in tests/test_*.py; do python3 -I -B "$t"; done
```

`costruisci` scrive `swarmer.sh` e la sua copia `sciame.sh`. Da un progetto con lo sciame installato,
`bash sciame/sciame.sh approva scheda.json` e `bash sciame/sciame.sh proponi <sigla> --invia` fanno lo stesso e aprono
la pull request con `gh`. Una scheda nel formato 1 della 4.0 (`sigla`, `tipo`, `testi`, …) si accetta ancora.

## 2. Una lingua nuova

- `i18n/<codice>.json` con esattamente le chiavi e i segnaposto di `i18n/en.json`, comprese le sezioni `commands`,
  `options` e `values` (i nomi della lingua, come alias dei nomi inglesi: nessun alias può essere uguale a un altro
  nome canonico o a un altro alias dello stesso spazio dei nomi) e `files` (i nomi dei documenti e dei file del
  progetto);
- `docs/<codice>/` con tutti i documenti di `docs/en/`, con gli stessi nomi canonici e gli stessi segni `<!-- … -->`
  byte per byte; `_HELP.txt` ha una riga per ogni comando;
- i testi di ogni voce di `db/professionals.json` e di `db/cores.json` nella lingua nuova;
- le etichette delle schede per la lingua in `engine/compat.py` (`LABELS`).

Le righe del protocollo di giurie e convocazioni (`VOTO`, `OPZIONE`, `REVISIONE`, … e le forme inglesi) le leggono i
programmi: una lingua che vuole parole sue le aggiunge in `engine/compat.py`, con le prove. `verifica` controlla che
blocchi, chiavi e segnaposto coincidano fra le lingue e che nessun alias collida.

## 3. Correzioni e miglioramenti

Una modifica al motore arriva con una prova in `tests/` che fallisce prima e passa dopo. Solo la libreria standard;
codice, commenti e messaggi sono in inglese, e ogni messaggio per l'utente viene da `i18n/`. Le parole italiane nel
codice stanno solo in `engine/compat.py` (e nei blocchi di `engine/head.sh` che `costruisci` genera da `i18n/`).
