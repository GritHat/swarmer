## Proposta di professionisti nuovi per lo sciame

Questa pull request aggiunge al database `db/professionals.json`:

- `swarmer-<sigla>` (professionista | sottoprofessionista di `swarmer-<genitore>`): <nome>

- [ ] Ogni voce ha i testi inglesi completi (obbligatori: la CI rifiuta una voce senza); le altre lingue sono facoltative.
- [ ] La sigla è nuova, in minuscolo, e non è il nome di una strategia.
- [ ] Un sottoprofessionista ha come genitore un professionista dello stesso nucleo.
- [ ] Nessun dettaglio di un progetto privato, nessun segreto: `python3 -I -B engine/swarmer.py --sciame . verifica` passa.
- [ ] `swarmer.sh` e `sciame.sh` sono ricostruiti: `python3 -I -B engine/swarmer.py --sciame . costruisci --uscita swarmer.sh`.
- [ ] Il motivo: quale competenza manca allo sciame, e perché i ruoli vicini non la coprono.
- [ ] I testi non nominano un solo strumento: il ruolo vale in ogni destinazione (Claude Code, Codex, Antigravity,
      Gemini CLI, lo standard aperto); `python3 -I -B tests/test_targets.py` passa.
