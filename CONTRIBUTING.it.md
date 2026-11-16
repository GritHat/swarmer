# Contribuire

*[English](CONTRIBUTING.md)*

Sono benvenuti tre tipi di contributo, ciascuno come pull request.

## 1. Un professionista o un sottoprofessionista nuovo

Aggiungi una voce a `db/professionisti.json` (la forma è in [CONTRIBUTING.md](CONTRIBUTING.md)):
- `sigla` in minuscolo, parole unite da `-`, nuova, diversa dal nome di una strategia;
- un sottoprofessionista ha come `genitore` un professionista dello stesso nucleo (un livello solo);
- i testi in **tutte** le lingue del repository; il corpo segue la struttura delle schede (missione, competenze,
  domande che si pone sempre, metodi e strumenti, consegne tipiche, limiti, con chi si confronta), senza titoli `#`;
- nella pull request, quale competenza manca allo sciame e perché i ruoli vicini non la coprono;
- nessun dettaglio di progetti privati, nessun segreto, nessun dato personale.

Prima di aprirla:

```
python3 -I motore/sciame.py --sciame . verifica
python3 -I motore/sciame.py --sciame . costruisci --uscita sciame.sh
for p in prove/prova_*.py; do python3 -I "$p"; done
```

Da un progetto con lo sciame installato, `bash sciame/sciame.sh approva scheda.json` e
`bash sciame/sciame.sh proponi <sigla> --invia` fanno lo stesso e aprono la pull request con `gh`.

## 2. Una lingua nuova

- `i18n/<codice>.json` con esattamente le chiavi di `i18n/it.json`;
- `documenti/<codice>/` con tutti i documenti di `documenti/it/`, gli stessi segni `<!-- … -->` byte per byte e le
  stesse parole chiave del protocollo (`VOTO`, `OPZIONE`, `REVISIONE`, … le leggono i programmi e non si traducono);
- i testi di ogni voce di `db/professionisti.json` e di `db/nuclei.json` nella lingua nuova;
- le etichette delle schede per la lingua in `motore/professionisti.py` (`ETICHETTE`).

`verifica` controlla che blocchi e chiavi coincidano fra le lingue.

## 3. Correzioni e miglioramenti

Una modifica al motore arriva con una prova in `prove/` che fallisce prima e passa dopo. Solo la libreria standard.
