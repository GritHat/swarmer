# La cartella locale dello sciame

Questa cartella è del progetto e **non va mai** nel repository pubblico dello sciame. Qui stanno:
- `AGENTI.md`: schede nel formato di `sciame/AGENTI.md` (titolo `### N. Nome — `sciame-sigla``, righe **In breve**,
  **Nucleo**, **Parole chiave**). Per la stessa sigla una scheda locale ha **sempre** la priorità sul ruolo generico;
  una sigla che c'è solo qui è un ruolo solo locale. Le schede possono contenere i dettagli del progetto.
- `GIURIA.md`, `PIPELINE.md`, `PREAMBOLO.md`: regole proprie del progetto, che si aggiungono a quelle generiche o le
  sostituiscono, dichiarandolo.
- `USCITE.md`: i criteri d'uscita delle fasi del progetto, che la clausola dell'obiettivo delle giurie cita.
- `VIETATE.txt`: una parola o un'espressione per riga che non deve mai uscire dal progetto (nomi, codici, persone).
  `approva`, `proponi`, `costruisci` e `verifica` rifiutano ogni testo pubblico che le contiene.

Dopo una modifica: `bash sciame/sciame.sh rigenera`.
