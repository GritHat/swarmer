## Lingua nuova: <codice>

- [ ] `i18n/<codice>.json` con esattamente le chiavi e i segnaposto di `i18n/en.json`, comprese le sezioni `commands`,
      `options`, `values` e `files` (i nomi della lingua; un alias non deve collidere con un altro nome).
- [ ] `docs/<codice>/` con tutti i documenti sotto il nome canonico, segni dei blocchi identici a `docs/en/`.
- [ ] I testi in `<codice>` di ogni voce di `db/professionals.json` e di `db/cores.json`.
- [ ] Le etichette delle schede per `<codice>` in `engine/compat.py` (`LABELS`); le righe del protocollo si leggono in
      inglese e in italiano.
- [ ] `verifica` e le batterie passano; `swarmer.sh` e `sciame.sh` ricostruiti.
