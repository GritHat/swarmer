# La giuria, gli esperti nuovi e la plenaria (protocollo G, versione 4.0 dello sciame)

Questo documento dà le regole complete di tre strategie: **giuria** (§2–§3), **esperto nuovo** (§4) e **plenaria**
(§5). Gli strumenti sono `giuria.py` e la batteria delle prove della skill (§8). Le strategie brevi sono in
`PIPELINE.md`.

## 1. Autorità, delega e clausola dell'obiettivo

**Che cosa decide una giuria.** Una proposta di decisione: la scelta fra opzioni, il testo di un atto, una
precisazione, una regola. `giuria.json` dichiara `autorita`:
- **`raccomandazione`**, di norma: il consenso dà **RACCOMANDATA**, e decide l'utente;
- **`vincolante`**, solo se l'utente ha delegato la decisione per iscritto, voce per voce (il campo `delega` cita lo
  scritto), oppure se la decisione è solo il modo di attuare una decisione già presa dall'utente.

**Che cosa resta sempre all'utente**, salvo una delega espressa e puntuale per quella voce:
- azioni a pagamento, irreversibili o verso l'esterno (pubblicare, inviare dati, servizi a pagamento, GPU in affitto);
- esecuzioni su sistemi o dati reali che non si possono annullare;
- tetti nuovi di calcolo o quote oltre quelle già autorizzate;
- l'adozione o l'abbandono di una candidata, di una linea, di un obiettivo, di una fase;
- deroghe ai principi del progetto;
- il testo che l'utente firma.

Una plenaria (§5) su queste voci dà una raccomandazione. L'utente può revocare in ogni momento una decisione di
giuria.

**La tabella della delega.** Prima di una giuria su decisioni delegate in blocco, il coordinatore scrive e sigilla una
tabella, voce per voce: `delegata`, `riservata` o `mista`, con il motivo. Le voci riservate e quelle miste vanno a
raccomandazione. Una lettura ristretta della delega si presenta all'utente come una lettura, non come l'unica.

**La clausola dell'obiettivo (imperativa): il test T-OB.** Ogni proposta porta in testa, per ogni decisione, quattro
punti, ciascuno con una prova [V] (file e riga):
1. **Bersaglio.** Il criterio d'uscita della fase corrente del progetto che la decisione serve, citato per
   identificativo dal file dei criteri d'uscita del progetto (di norma `sciame/locale/USCITE.md`, scritto dall'utente o con
   lui), oppure un principio del progetto. Una fase senza criteri d'uscita scritti fa fallire il test per costruzione:
   i criteri si scrivono prima, una volta per fase.
2. **Catena.** «Con Dk il criterio U passa dallo stato a allo stato b», oppure «Dk toglie il blocco B, che sta sul
   percorso critico di U», con il file che mostra B fra i blocchi aperti.
3. **Controfattuale.** Senza Dk il criterio resta fermo o slitta, e di quanto. «Nessun effetto» fa fallire il test,
   salvo una correzione d'errore a costo nullo.
4. **Costo.** Le cifre con la fonte, confrontate con il residuo del tetto, e nessuna via più corta già autorizzata.

La clausola regge solo se passano tutti e quattro i punti. Il garante scrive i quattro esiti nel suo voto.
Ogni giurato vota **no** se la clausola non regge.

## 2. La giuria

**Composizione.** La sceglie il coordinatore e la scrive in `giuria.json` prima di aprire la proposta. Il file non
cambia più: `giuria.py` ne registra lo sha256 e rifiuta ogni giro contato con un'altra composizione.
- **Numero dei giurati:** da 5 a 9, in numero dispari.
- **Ci sono sempre:**
  - il garante;
  - un avversario (generatore avversario o rovesciatore);
  - il debugger se la decisione tocca codice;
  - lo statistico se tocca soglie, potenze o cifre;
  - in una giuria vincolante, il logico, il debugger e un avversario.
- **Campi obbligatori:** `tocca_codice` e `tocca_numeri` (sì o no), `autorita`, `delega`, `classificazione`
  (`ordinaria` o `plenaria`).
- **Ruoli ammessi:** solo le sigle dei ruoli dello sciame (`.claude/agents/sciame-*.md`), professionisti o
  sottoprofessionisti. Un esperto provvisorio (§4) è
  segnato `provvisorio` e ha la scheda sigillata `SCHEDA_<ruolo>.md` nella cartella; ce ne sono al più un terzo dei
  giurati.
- **Istanze nuove:** almeno metà dei giurati sono istanze nuove sull'oggetto, cioè non hanno scritto rapporti, passate o
  validazioni sulla proposta né sulle sue fonti dirette (`nuovo_sull_oggetto`).
- **Il relatore** scrive la proposta e le revisioni, e non vota. Non è il coordinatore.
- **Il cancelliere** è un'istanza dell'arbitro: non vota, verifica e conta con `giuria.py`.

**Competenza.** Un giurato che non si ritiene competente lo scrive **prima** di leggere la proposta, in
`RINUNCIA_<ruolo>.md`. Il coordinatore lo sostituisce prima di scrivere `giuria.json`: chi rinuncia non può essere
giurato. Dopo la lettura l'astensione non esiste.

**Indipendenza.**
- I giurati si lanciano in parallelo, ciascuno con la propria cartella.
- Ognuno ha la consegna di non leggere le cartelle degli altri né gli esiti.
- La proposta rivista non porta nomi né conteggi dei voti: solo le righe REVISIONE e CONDIZIONE, senza l'autore.

## 3. La procedura e il voto

**Le righe del protocollo** contano solo fuori dai blocchi ```. Una riga che comincia con una parola chiave ma non è
conforme è un errore, non una riga ignorata.

**Giro 0.**
1. Il relatore scrive `giro_0/PROPOSTA.md`, sigillata. Per ogni decisione `Dk`:
   - `OPZIONI Dk (a) | (b) | …`: l'elenco chiuso delle opzioni della domanda;
   - `OPZIONE Dk <etichetta>`: l'opzione proposta, presa da quell'elenco;
   - `DISPOSITIVO Dk <una riga>`: il nucleo operativo dell'atto, che nessuna revisione può cambiare;
   - `DIPENDE Dk Dj`, se Dk presuppone Dj;
   - il testo completo che diventerebbe atto;
   - il test T-OB;
   - la riga `PLENARIA no: <motivo>` (o `sì`);
   - i rischi con la fonte;
   - le alternative scartate.
2. Ogni giurato, cieco, scrive `giro_0/VOTO_<ruolo>.md`, sigillato. Per ogni `Dk`:
   - `VOTO Dk si|no` («sì» con l'accento vale sì);
   - la motivazione, con prove [V] o [I]. Un no senza nessuna prova [V] torna al giurato una volta; poi vale ed è
     segnalato;
   - per un no, `REVISIONE Dk <la revisione più piccola che mi farebbe votare sì>`, oppure `REVISIONE Dk nessuna`;
   - per un sì, `CONDIZIONE Dk <che cosa una revisione non deve toccare>`, oppure `CONDIZIONE Dk nessuna`;
   - `CLASSE Dk ordinaria|plenaria`: basta una sola «plenaria» perché la decisione vada alla plenaria;
   - facoltativa, `PREFERISCO Dk <altra opzione dell'elenco>`.
3. **Ogni giurato riporta** nella risposta finale i sigilli dei suoi file. Il cancelliere li scrive in `SIGILLI.md`,
   una riga `SIGILLO giro_<r>/<file> <hex>` ciascuno, prima del conto. `giuria.py` rifiuta un file il cui sigillo non è
   quello riportato.

**Il conteggio** (`giuria.py conta`), con n giurati e s voti sì:

| voti | esito |
|---|---|
| s = n (consenso totale) | **APPROVATA**, o RACCOMANDATA se l'autorità è una raccomandazione |
| n/2 < s < n (maggioranza) | **REVISIONE**: si passa al giro successivo |
| s ≤ n/2 (minoranza), compreso s = 0 (consenso sul no) | **RESPINTA** |

**Tre eccezioni al consenso:**
- una `CLASSE plenaria` dà **DA_PLENARIA**;
- se più di metà dei giurati preferisce la stessa altra opzione, l'esito è **DA_RIPROPORRE**: si riparte dal giro 0
  con quella;
- una decisione approvata che dipende da una non approvata non diventa atto:
  - se l'altra è in REVISIONE, si rivotano insieme;
  - se l'altra è respinta o non convergente, l'esito è **SOSPESA** e la decisione torna all'utente con l'altra.

**Giri di revisione (1, 2, 3)**, per le decisioni in REVISIONE:
1. Il relatore scrive `giro_<r>/PROPOSTA.md` con le sole decisioni in revisione. `OPZIONE`, `DISPOSITIVO` e `DIPENDE`
   restano identici; cambiano clausole, condizioni, ordine e formulazione. Ogni pezzo cambiato cita la riga REVISIONE
   a cui risponde, con il diff dal testo del giro precedente.
2. **Non tocca le righe CONDIZIONE dei sì**, che restano vincolanti in tutti i giri successivi. Se una REVISIONE
   chiesta da un no contraddice una CONDIZIONE di un sì, il relatore scrive
   `INCOMPATIBILE Dk <le due righe in conflitto>`. Se il cancelliere lo verifica, e lo scrive in `SIGILLI.md` con la
   riga `INCOMPATIBILE-VERIFICATO giro_<r> Dk`, la decisione è subito **NON_CONVERGENTE** e i voti su di lei non
   contano; senza la verifica, il giro si conta come un giro di revisione.
3. Tutti i giurati rivotano, ciechi, sul testo rivisto. Chi passa da no a sì scrive `CAMBIO Dk <la modifica che
   risponde alla mia REVISIONE>`; senza questa riga il giro è rifiutato. Il passaggio si misura rispetto all'ultimo
   voto espresso dal giurato, anche se cade in un giro scartato come regressivo. Un no di principio (`REVISIONE nessuna`)
   cambia solo davanti a una prova nuova, che il `CAMBIO` cita.
4. **Gli esiti del giro di revisione:**

   | come va il giro | esito |
   |---|---|
   | consenso | APPROVATA (con le eccezioni sopra) |
   | i sì scendono in minoranza | **RESPINTA**: la regola del conteggio, la minoranza respinge |
   | si perde un sì ma la maggioranza resta | revisione **regressiva**: si scarta; la decisione torna al testo e ai voti del giro precedente, resta in REVISIONE e il giro conta nel limite |
   | altrimenti | REVISIONE |

**Il limite: tre giri di revisione**, cioè la seconda, la terza e la quarta passata, fissati dal protocollo. Una
decisione ancora in REVISIONE dopo il giro 3 è **NON_CONVERGENTE**:
- non è approvata;
- torna all'utente con i voti e le righe REVISIONE rimaste;
- «la convergenza non si forza».

**Dopo una RESPINTA.** Il relatore può portare un'altra opzione dello stesso elenco `OPZIONI`, come proposta nuova:
- una volta per opzione;
- in una giuria nuova, che cita la precedente in `giuria.json` (`precedenti`);
- il cancelliere certifica `DIVERSA Dk <motivo>` rispetto al testo respinto.

Se tutte le opzioni sono respinte, la domanda torna all'utente.

**`giuria.py` è l'unica fonte dell'esito.** Ricalcola ogni volta tutti i giri dai file sigillati. Rifiuta:
- un ESITO già scritto che non coincide, cioè un rivoto, un voto cambiato o un ESITO ritoccato;
- un giro contato fuori ordine;
- una voce estranea nella cartella del giro.

**L'atto.** Il coordinatore registra in `.sciame/<giuria>/ATTO.md` le decisioni APPROVATE con la proposta finale, l'esito
(`ESITO_giro_<r>.json`) e i sigilli. Poi attua, se la richiesta lo permette. Le altre si registrano con l'esito. All'utente va un
resoconto breve. Ogni giuria sta in `.sciame/<data>-giuria-<oggetto>/`. Gli agenti scrivono nella loro cartella; il
coordinatore copia e verifica.

## 3bis. La giuria leggera

Per le decisioni piccole e poco influenti (reversibili, locali, senza voci riservate), o dove un errore si scopre con
una prova veloce (al più cinque minuti), una giuria leggera costa meno e prova prima di votare.
- **La giuria**: `"forma": "leggera"` in `giuria.json`; tre giurati: il ruolo più competente per la funzione, un critico
  (avversario, rovesciatore o debugger) e il garante; più il relatore e il cancelliere. Non vale per una plenaria; per una
  voce riservata dà al più una raccomandazione. Le regole di composizione della giuria ordinaria su debugger, statistico
  e passata vincolante non si applicano: la prova le sostituisce.
- **La prova prima del voto**: per ogni `Dk`, `PROVA Dk <comando o controllo>` con l'atteso scritto prima, e
  `ESITO-PROVA Dk passa|fallisce` dopo averla eseguita, prima del voto. Senza le due righe il conto si rifiuta.
- **Gli esiti**: consenso e prova che passa, APPROVATA (o RACCOMANDATA); prova che fallisce, RESPINTA; maggioranza, un
  solo giro di revisione e poi **DA_GIURIA** (la giuria ordinaria, dal giro 0, con la proposta e i voti come ingresso);
  un `CLASSE ordinaria` di un giurato, DA_GIURIA subito; un `CLASSE plenaria`, DA_PLENARIA.
- **La clausola dell'obiettivo** resta, in breve: il garante la verifica come nella giuria ordinaria.

## 4. Gli esperti che non esistono ancora

**La richiesta.** Una riga in `sciame/RICHIESTE_ESPERTI.md` con sei campi:
- la data;
- la convocazione: il percorso della sua cartella in `.sciame/`, che deve esistere;
- il richiedente: la sigla di un ruolo, `coordinatore` o `provvisorio:<sigla>`;
- la competenza, come sigla in minuscolo;
- l'oggetto per cui serviva;
- il motivo, di almeno dieci caratteri: quali ruoli si sono guardati e perché non coprono la competenza.

`giuria.py richieste` normalizza le grafie del richiedente, rifiuta le righe non conformi invece di ignorarle e segnala
le sigle vicine.

**Quando due sigle sono lo stesso esperto.** Il cancelliere unisce due sigle con una riga
`` - `x`: unito a `y`, <motivo> ``: le richieste di x si sommano a y.

**La convocazione su un esperto che non esiste.** Il coordinatore convoca un **esperto provvisorio**:
1. scrive la scheda provvisoria prima di leggere la domanda nel dettaglio, e la sigilla;
2. lancia un agente generico con il preambolo e la scheda;
3. marca il contributo come [provvisorio];
4. registra la convocazione stessa come una richiesta.

L'esperto provvisorio non conta per la propria creazione.

**La soglia di creazione.** Vale una delle due condizioni:
- **(a) contemporanea:** in una convocazione lo chiedono almeno 3 ruoli distinti; in una plenaria, almeno 5, perché
  lì tutti ricevono lo stesso invito;
- **(b) accumulata:** almeno 3 richieste in almeno 2 convocazioni, da almeno 2 ruoli distinti.

Come si contano le richieste:
- un ruolo conta una volta per sigla e per convocazione;
- il coordinatore conta al più una richiesta per sigla, e mai come ruolo distinto;
- l'utente può ordinare la creazione direttamente.

**La creazione**, dopo l'approvazione dell'utente (o di una giuria a cui l'utente l'ha delegata):
1. la scheda in un file JSON, nel formato del database, con i testi in tutte le lingue della skill e, per un
   sottoprofessionista, il genitore;
2. `bash sciame/sciame.sh approva <scheda.json>`: la voce entra nel database, si rigenerano agenti, skill e documenti, si
   ricostruisce `sciame.sh`, le richieste della sigla si chiudono con «creato: n. NN»;
3. `bash sciame/sciame.sh proponi <sigla>` prepara la pull request al repository pubblico; con `--invia --si` la apre.

Una competenza che vale solo per il progetto resta una scheda locale (`sciame/locale/AGENTI.md`) e non si approva.

Nella sessione in cui nasce, il ruolo si lancia come agente generico con la scheda.

## 5. La convocazione plenaria

**Quando.** Solo in due casi:
1. **Il passaggio da una fase maggiore all'altra** del progetto, come il progetto le definisce.
2. **Una scelta d'impatto enormemente importante.** Lo è una scelta che cambia un obiettivo, il principio o una
   direttiva; apre o chiude una linea, una candidata o una fase; è irreversibile; impegna risorse oltre i tetti
   autorizzati.

Come si arriva alla plenaria:
- il coordinatore propone la classificazione con il motivo, nella riga `PLENARIA` di ogni proposta;
- una classificazione sbagliata è un motivo di no;
- basta una `CLASSE plenaria` di un solo giurato per portare la decisione alla plenaria;
- una scelta grave non si taglia in fette ordinarie: il garante lo controlla.

**I cinque livelli.** Ogni livello passa al successivo un fascicolo sigillato, con le previsioni sigillate prima di
cominciare.
1. **Lo sciame intero.** La domanda la scrive il coordinatore, sigillata, con il test T-OB. Ogni ruolo, compresi i
   nuovi e gli esperti provvisori richiesti, scrive un parere breve (al più una pagina) e le richieste di esperti.
2. **La convocazione usuale** del protocollo vigente per l'oggetto, sui pareri del livello 1:
   - la classica per ipotesi, misure e ricerche;
   - la giuria per una proposta già istruita.

   **Se il livello 2 non converge, la plenaria si ferma** e va all'utente con le cause.
3. **La passata critica generale** sull'esito del livello 2: avversario, rovesciatore, debugger, creativo e garante,
   più gli esperti dei sistemi toccati.
4. **Gli arbitri.** Due istanze indipendenti dell'arbitro scrivono ciascuna una convergenza; l'esperto di scelta
   sociale verifica la procedura. Una discordanza su un fatto si separa con una prova. Se la prova non c'è, diventa un
   rischio dichiarato, oppure due opzioni distinte nella proposta finale. Il relatore della votazione è uno dei due
   arbitri.
5. **La votazione finale.** Votano istanze nuove dei **professionisti pertinenti**: quelli che al livello 1 non hanno
   scritto «non pertinente», meno relatore e cancelliere. Un sottoprofessionista vota solo su delega scritta del suo
   professionista, al suo posto e mai insieme a lui. Ogni votante legge la proposta finale e i fascicoli dei livelli
   1–4. Le regole sono quelle del §3, con il consenso di tutti i votanti; la parità non è una maggioranza, e non c'è
   sorteggio. I giri di revisione rifanno solo il voto, non i livelli 3–4. `giuria.json` elenca i votanti e il file
   del livello 1 che ne dà la pertinenza.

**Costo.** Circa 60–70 agenti, più circa 25 per ogni giro di revisione. Il coordinatore lo annuncia prima.

## 6. Limiti dichiarati

- **Un modello solo.** Se i giurati sono istanze dello stesso modello, il teorema di Condorcet non si applica:
  APPROVATA vuol dire «nessun giurato ha trovato un'obiezione che regga», non «verificata». Dove l'ambiente lo
  permette, giurati di modelli diversi rendono il voto più indipendente.
- **La fiducia nel coordinatore resta in tre punti:**
  - `SIGILLI.md` lo scrive il cancelliere dalle risposte finali dei giurati, che il coordinatore riceve;
  - `nuovo_sull_oggetto` si dichiara;
  - il voto cieco poggia sulla consegna, non su una separazione tecnica.

  Il coordinatore li dichiara in ogni resoconto e non li usa mai per sé.
- **Il veto.** Il veto di un solo giurato è voluto: approva solo il consenso. Nelle plenarie l'esito tipico sarà
  REVISIONE o NON_CONVERGENTE.
- **Il voto strategico** si rende visibile (CAMBIO, PREFERISCO, CONDIZIONE), ma non si elimina.

## 7. Le scelte di forma, che un progetto può cambiare

Un progetto può cambiare queste scelte in `sciame/locale/GIURIA.md` (§9), dichiarandolo:
1. tre giri di revisione prima di NON_CONVERGENTE;
2. una revisione che scende in minoranza è RESPINTA;
3. le soglie di creazione degli esperti: 3 in una convocazione, 5 in una plenaria; oppure 3 richieste in 2
   convocazioni da 2 ruoli;
4. nella plenaria la parità è RESPINTA, e vale il consenso dei votanti pertinenti.

## 8. Strumenti

- `python3 -I sciame/giuria.py conta <cartella> <giro>`: ricalcola tutti i giri, scrive `ESITO_giro_<r>.json`. Esce
  con 0 se tutto passa, con 2 e un «ERRORE:» altrimenti.
- `python3 -I sciame/giuria.py richieste [registro]`: le sigle alla soglia del §4 e le sigle vicine.
- `bash sciame/sciame.sh prove`: le batterie della skill, comprese quelle della giuria; da lanciare prima di ogni
  giuria.

## 9. Gli override locali

Un progetto può avere ruoli propri con la stessa sigla di un ruolo generico, e regole proprie. Stanno in
`sciame/locale/`, che non si manda mai al repository pubblico della skill e può contenere i dettagli del progetto:
- `sciame/locale/AGENTI.md`: schede nel formato di `AGENTI.md`; per la stessa sigla la scheda locale ha **sempre** la
  priorità sul ruolo generico, in tutte le strategie, nelle giurie e nelle plenarie;
- `sciame/locale/GIURIA.md`, `PIPELINE.md`, `PREAMBOLO.md`: regole che si aggiungono a quelle generiche o le
  sostituiscono, dichiarandolo;
- `sciame/locale/USCITE.md`: i criteri d'uscita delle fasi del progetto, per la clausola dell'obiettivo.

Un ruolo creato dal progetto con la strategia esperto nuovo ha due schede: quella locale, con i dettagli, e quella
generica, senza, che sola entra nel database e nella proposta al repository.

## 10. Il protocollo G2 (di difetto)

Ogni giuria nuova segue il protocollo G2; `"protocollo": "G1.1"` in `giuria.json` vale solo per ricontare giurie
votate prima di lui, cioè con un `ESITO_giro_0.json` senza la chiave «protocollo» (la variabile `SCIAME_G11_PROVE=1`
serve solo alle batterie di prova, e un ESITO scritto con lei non si riconta senza). Con G2:
- `giuria.json` si sigilla prima del giro 0: la riga `SIGILLO giuria.json <sha>` in `SIGILLI.md`; nessun SIGILLO
  orfano;
- una giuria vincolante ha `"delega": "DELEGA.md"`, sigillato, con una riga `DELEGATA Dk` per ogni decisione delegata;
  le altre danno al più RACCOMANDATA;
- `PREFERISCO` solo fra le `OPZIONI` del giro 0;
- `"precedenti"`: le giurie precedenti sulla stessa domanda; un'opzione già RESPINTA non si ripropone, e un secondo
  DA_RIPROPORRE diventa DA_UTENTE;
- in una plenaria votano i pertinenti di `PERTINENZA.md` (righe `PERTINENTE <ruolo>`, `DELEGA <sotto> <genitore>`), e
  la `CLASSE plenaria` è solo informativa; una giuria leggera non vale mai per una plenaria.
