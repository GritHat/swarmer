# L'ambiente: che cosa fa lo sciame con gli strumenti che trova

Lo sciame nasce per Claude Code, ma le sue regole valgono in ogni ambiente che sa leggere le skill nel formato
`skills/<nome>/SKILL.md`. Questo documento dice come il coordinatore adatta una convocazione a ciò che l'ambiente
offre davvero.

<!-- environment -->
## Le capacità, e che cosa fare quando mancano

Prima di convocare, il coordinatore guarda che cosa l'ambiente gli concede davvero, non che cosa ci si aspetterebbe.
Usa solo le capacità che l'ambiente mostra. Quando una manca, tiene le fasi e i controlli della strategia e prende la
strada più vicina onesta, dichiarandola nella risposta.

| capacità | se c'è | se manca |
|---|---|---|
| sottoagenti | un agente per ruolo, con lo strumento che l'ambiente offre (in Claude Code: Agent con `subagent_type: "sciame-<sigla>"`) | il coordinatore fa i ruoli uno dopo l'altro nella stessa sessione, ciascuno con la sua consegna, e scrive in testa alla risposta «ruoli svolti in sequenza dal coordinatore: l'indipendenza è ridotta» |
| sottoagenti in parallelo | le fasi indipendenti nello stesso messaggio, al più cinque alla volta | in fila, con lo stesso ordine delle ondate |
| scelta del modello per ruolo | il modello scritto in `.sciame/config.json` (`bash sciame/sciame.sh modelli`) | il modello della sessione, dichiarato |
| shell | `convoca.py` e `giuria.py` preparano e controllano | i cancelli li controlla il coordinatore con le condizioni scritte, e lo dichiara |
| scritture | ogni agente nella sua cartella in `.sciame/` | le consegne nei prompt, le risposte sono le consegne |
| domande strutturate all'utente | lo strumento dell'ambiente (in Claude Code: AskUserQuestion), con le opzioni e la raccomandata per prima | una sola domanda chiara nel testo |
| rete | lettura di documentazione e fonti pubbliche | «non verificato» su ciò che andava controllato fuori |
| lavori lunghi | i meccanismi dell'ambiente per riprendere (promemoria, attese, cicli) | un `DIARIO.md` nella cartella della convocazione, con il criterio di fatto e i punti di ripresa |

**Mai fingere una capacità.** Non si scrive che un agente, una revisione, una prova o un controllo ha lavorato se
l'ambiente non lo ha riportato. Un fatto che il coordinatore può controllare da sé non si chiede all'utente: si
controlla.

**Il coordinatore resta responsabile.** Le domande all'utente, le approvazioni, l'integrazione e la verifica finale
sono sue. I rapporti degli agenti sono evidenze: prima di dire «fatto», il coordinatore guarda i file prodotti e
riesegue i controlli promessi sul risultato integrato.

**Dove non guardare.** Nessuna convocazione legge le conversazioni o i file di altri progetti, né le cartelle globali
dell'ambiente, salvo che la richiesta lo chieda e indichi dove.
<!-- /environment -->

## I modelli per ruolo

`bash sciame/sciame.sh modelli` mostra e cambia il modello di ogni ruolo o di ogni classe di ruoli, in
`.sciame/config.json`:

```
bash sciame/sciame.sh modelli                       # che cosa c'è
bash sciame/sciame.sh modelli arbitro=opus          # un ruolo
bash sciame/sciame.sh modelli critico=opus          # un nucleo
bash sciame/sciame.sh modelli --tutti=inherit       # tutti come la sessione
```

Il valore finisce nel campo `model` degli agenti generati. Un nome che l'ambiente non conosce non fa danni da sé, ma
l'agente non parte: dopo il cambio, `bash sciame/sciame.sh controlla`.

## Altri ambienti

- **Plugin.** Il repository della skill è anche un plugin: si aggiunge con il gestore dei plugin dell'ambiente (in
  Claude Code: `/plugin marketplace add <proprietario>/<repository>`, poi `/plugin install swarmer`). Il plugin porta
  le skill e gli agenti generici; gli override locali restano nel progetto.
- **Solo skill.** Si copia la cartella `skills/` nella cartella delle skill dell'ambiente: le strategie funzionano
  anche senza agenti di progetto, con i ruoli svolti come dice la tabella qui sopra.
- **Un modello per API**, senza sottoagenti: un programma proprio fa il coordinatore, una chiamata per ruolo, con i
  testi di `sciame/catalog.json` (vedi `ISTRUZIONI_COORDINATORE.md`).
