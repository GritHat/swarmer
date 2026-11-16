## New language: <code>

- [ ] `i18n/<code>.json` with exactly the keys and placeholders of `i18n/en.json`, including the sections `commands`,
      `options`, `values` and `files` (the names of the language; an alias must not collide with another name).
- [ ] `docs/<code>/` with every document under its canonical name, block markers identical to `docs/en/`.
- [ ] Texts in `<code>` for every entry of `db/professionals.json` and `db/cores.json`.
- [ ] Card labels for `<code>` in `engine/compat.py` (`LABELS`); the protocol lines are read in English and Italian.
- [ ] `verify` and the test batteries pass; `swarmer.sh` and `sciame.sh` rebuilt.
- [ ] The texts of the language name every target, not a single tool (see `docs/en/ENVIRONMENT.md`).
