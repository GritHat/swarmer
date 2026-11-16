## Proposta di professionisti nuovi per lo sciame

Questa pull request aggiunge al database `db/professionisti.json`:

{voci}

- [ ] Ogni voce ha i testi in tutte le lingue del repository (oggi italiano e inglese).
- [ ] La sigla è nuova, in minuscolo, e non è il nome di una strategia.
- [ ] Un sottoprofessionista ha come genitore un professionista dello stesso nucleo.
- [ ] Nessun dettaglio di un progetto privato, nessun segreto: `python3 -I motore/sciame.py --sciame . verifica` passa.
- [ ] `sciame.sh` è ricostruito: `python3 -I motore/sciame.py --sciame . costruisci --uscita sciame.sh`.
- [ ] Il motivo: quale competenza manca allo sciame, e perché i ruoli vicini non la coprono.
