# La cartella locale dello sciame

Questa cartella è del progetto e **non va mai** nel repository pubblico dello sciame. Qui stanno:
- `AGENTI.md`: schede nel formato di `sciame/AGENTI.md` (titolo `### N. Nome — `sciame-sigla``, righe **In breve**,
  **Nucleo**, **Parole chiave**). Per la stessa sigla una scheda locale ha **sempre** la priorità sul ruolo generico;
  una sigla che c'è solo qui è un ruolo solo locale. Le schede possono contenere i dettagli del progetto. Il loro testo
  va anche negli agenti generati per ogni destinazione attiva (`.claude/agents/`, `.codex/agents/`, `.agents/agents/`,
  `.gemini/agents/`): quei file hanno la stessa riservatezza di questa cartella, e `.agents/` lo leggono molti
  strumenti.
- `GIURIA.md`, `PIPELINE.md`, `PREAMBOLO.md`: regole proprie del progetto, che si aggiungono a quelle generiche o le
  sostituiscono, dichiarandolo.
- `USCITE.md`: i criteri d'uscita delle fasi del progetto, che la clausola dell'obiettivo delle giurie cita.
- `VIETATE.txt`: una parola o un'espressione per riga che non deve mai uscire dal progetto (nomi, codici, persone).
  `approva`, `proponi`, `costruisci` e `verifica` rifiutano ogni testo pubblico che le contiene.

- `traduzioni/<lingua>/<sigla>.json`: le traduzioni dei ruoli che il database pubblico non ha nella lingua
  dell'installazione, registrate da `bash sciame/sciame.sh traduci <sigla> <file.json>` (le fa il coordinatore la
  prima volta che convoca un ruolo segnato `translation-pending`). Non si distribuiscono né si pubblicano mai e
  sopravvivono agli aggiornamenti. Se più avanti il database pubblico porta la sua traduzione, **vale quella
  pubblica**, salvo che la locale sia stata modificata a mano dopo `traduci` (la sua impronta, `sha256_scritto`, non
  corrisponde più): allora resta la locale.

Dopo una modifica: `bash sciame/sciame.sh rigenera`.
