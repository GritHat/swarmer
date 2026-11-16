# Le richieste di esperti che non esistono ancora

Ogni riga è una richiesta. La portano qui il coordinatore, dalle righe `ESPERTO-MANCANTE` delle consegne, o chi
convoca un esperto provvisorio. Il motivo dice quali ruoli si sono guardati e perché non coprono la competenza: una
riga senza motivo non conta. `bash sciame/sciame.sh richieste` elenca le competenze arrivate alla soglia:
- 3 ruoli distinti in una convocazione, 5 in una plenaria;
- oppure 3 richieste in 2 convocazioni da 2 ruoli.

Il coordinatore conta una volta sola per competenza. La convocazione è il percorso della sua cartella in `.sciame/`,
relativo alla radice del progetto.

| data | convocazione | richiedente | competenza | oggetto | motivo |
|---|---|---|---|---|---|

## Chiuse

Una riga per competenza: `` - `sigla`: creato, n. NN (data) `` oppure `` - `sigla`: unito a `altra`, motivo ``.
