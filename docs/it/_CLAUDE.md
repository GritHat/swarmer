## Sciame di agenti

Questo progetto ha uno sciame di agenti specialistici in `sciame/`: professionisti e sottoprofessionisti, agenti
`sciame-<sigla>` (in `.claude/agents/`, `.codex/agents/`, `.agents/agents/` o `.gemini/agents/`, secondo lo
strumento). Si convoca solo quando l'utente lo chiede, con la skill di una strategia (in `.claude/skills/` o
`.agents/skills/`; in Claude Code anche come comando con la barra): **singolo** (`sciame-singolo`), **ventaglio**
(`sciame-ventaglio`), **classica** (`sciame-classica`), **giuria** (`sciame-giuria`), **giuria leggera**
(`sciame-giuria-leggera`), **completa** (`sciame-completa`), **plenaria** (`sciame-plenaria`), **esperto nuovo**
(`sciame-esperto`) o **auto** (`sciame`).
Le regole sono in `sciame/PREAMBOLO.md`, le strategie in `sciame/PIPELINE.md`, giuria e plenaria in
`sciame/GIURIA.md`, le schede in `sciame/AGENTI.md`; le schede locali in `sciame/locale/` hanno la priorità.
