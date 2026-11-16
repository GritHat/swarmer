# Le convocazioni dello sciame: otto strategie

**Stato.** Versione 5.0 (swarmer) del 16 novembre 2026: le strategie e le regole sono quelle della 4.0, con
i nomi inglesi accanto agli italiani (§«Che cosa cambia»). La 4.0 aggiunse alle quattro strategie della 3.1 (singolo, classica, completa, auto)
aggiunge:
- la **giuria**, che decide una proposta con un voto;
- la **plenaria**, per i passaggi di fase e le scelte d'impatto enormemente importante;
- il **ventaglio**, che divide un lavoro in fette parallele o mette più agenti in gara sulla stessa consegna;
- l'**esperto nuovo**, che convoca una competenza che lo sciame non ha ancora e la fa crescere quando serve davvero.

I ruoli sono **professionisti** (le competenze generali) e **sottoprofessionisti** (le loro specializzazioni), in un
database unico, `db/professionals.json`. La sua forma pubblica è inglese: ogni voce ha i testi inglesi completi, le
altre lingue sono facoltative. Una voce senza la lingua dell'installazione si genera dal testo inglese ed è segnata
`translation-pending: <lingua>`; il coordinatore la traduce la prima volta che la convoca
(`bash sciame/sciame.sh traduci <sigla> <file.json>`), e la traduzione resta nella sovrapposizione locale
della cartella dello sciame, `locale/traduzioni/<lingua>/<sigla>.json`, mai distribuita né pubblicata, che sopravvive agli aggiornamenti.
Se più avanti il database pubblico porta la sua traduzione, vale quella pubblica, salvo che la locale sia stata
modificata a mano.

| strategia | che cosa fa | quando | quanti agenti | costo |
|---|---|---|---|---|
| **singolo** | un solo specialista, il più adatto | domanda chiara di un campo, compito piccolo, ruolo nominato | 1 | basso |
| **ventaglio** | N agenti in parallelo: fette di un lavoro, oppure una gara con la regola di scelta dichiarata prima | copertura larga, lavori divisibili, più tentativi indipendenti | 2–16 | basso o medio |
| **classica** | la pipeline a grafo: contratto, due corsie cieche, triage, torneo, squadre per ipotesi, prove, verdetti | decisione, progetto, difetto, prova, alternative, rischio | 6–15 | medio |
| **giuria** | una proposta, una giuria che vota: consenso approva, maggioranza rivede, minoranza respinge | decidere fra opzioni già istruite, il testo di un atto, una regola | 7–11 | medio |
| **completa** | tutto lo sciame insieme in una tornata cieca, senza voto; il consolidamento entra nella classica | domanda strategica o aperta, molti campi, «tutti i punti di vista» | tutti i professionisti più la classica | alto |
| **plenaria** | completa, convocazione usuale, passata critica, due arbitri, voto finale con consenso | passaggi di fase, scelte enormemente importanti, irreversibili | 60–80 e oltre | molto alto |
| **esperto** | un esperto che non esiste ancora, con una scheda provvisoria; la richiesta si registra | manca una competenza | 1 più la scheda | basso |
| **auto** | sceglie il coordinatore fra le altre, e i ruoli | sempre, quando non si sa | secondo la scelta | secondo la scelta |

I blocchi fra i segni `<!-- strategia:… -->` sono il testo che il generatore copia nelle skill di convocazione e nel
catalogo: vanno tenuti completi e brevi. Il resto del documento li spiega e li motiva.

<!-- brief -->
## La consegna, in ogni strategia

Ogni agente parte da zero: la consegna basta da sola. Contiene sempre:
- **il ruolo** e la fase;
- **lo scopo**, in una frase, e il **criterio di fatto**: il controllo che dice se il lavoro è finito e buono, scritto
  prima;
- **gli ingressi**: il testo della richiesta per intero e i percorsi assoluti dei file da leggere;
- **lo spazio di scrittura**: la sola cartella in cui l'agente scrive, diversa per ogni agente che scrive;
- **lo spazio vietato**: che cosa non tocca, non legge o non esegue;
- **la verifica**: il comando o il controllo che l'agente esegue prima di consegnare, se ha gli strumenti;
- **la forma della risposta**, con in testa una delle tre parole d'esito:
  - **FATTO**: il criterio di fatto è soddisfatto, con le prove;
  - **PROBLEMI**: il lavoro c'è, ma con difetti elencati, uno per riga, ciascuno con la prova;
  - **BLOCCATO**: non si può andare avanti, con la causa e che cosa servirebbe;
- **i limiti**: tempo, lunghezza, risorse.

Il rapporto di un agente è un'evidenza, non una prova: il coordinatore riesegue i controlli promessi sul risultato
integrato prima di dichiararlo. Un agente che si ferma o non risponde si dichiara: il lavoro prosegue senza di lui e
la sua parte resta scoperta, scritta come tale. Non si dice mai che un agente, una revisione o una prova ha lavorato
se l'ambiente non lo ha riportato.
<!-- /brief -->

<!-- strategy:single -->
## Singolo, in breve

Quando: la richiesta è di un solo campo ed è chiara (una spiegazione, una revisione, una traduzione, un calcolo, un
compito piccolo), oppure l'utente nomina il ruolo.
1. Scegli il ruolo più adatto, dal suo «in breve» e dalle sue parole chiave. Se l'utente ne nomina uno, è quello.
2. Scrivi una consegna completa, perché lo specialista non vede niente altro:
   - la domanda;
   - gli ingressi, compreso il testo della richiesta per intero;
   - il risultato atteso e la sua forma;
   - i limiti e i divieti.
3. Lo specialista lavora e si rilegge con le sue «domande che si pone sempre».
4. Tu controlli il risultato contro la domanda. Se manca qualcosa o c'è un errore evidente, fai una sola ripresa,
   con la richiesta precisa.
5. Rispondi con il risultato, con la parola d'esito (FATTO, PROBLEMI, BLOCCATO) e ciò che non è verificato.
<!-- /strategy:single -->

<!-- strategy:fan-out -->
## Ventaglio, in breve (N agenti in parallelo)

Quando: il lavoro si divide in parti indipendenti (file, moduli, capitoli, casi, fonti), oppure servono più tentativi
indipendenti dello stesso compito per sceglierne uno.
1. **La forma**, scritta prima di lanciare:
   - **fette:** ogni agente ha una parte diversa; la copertura richiede un esito per ogni fetta;
   - **gara:** tutti hanno la stessa consegna; la **regola di scelta** è dichiarata prima: il primo che soddisfa il
     criterio di fatto, la classifica di tutti con il criterio scritto, oppure il migliore di N;
   - **mista:** fette, e su qualcuna una gara.
2. **N** è il numero totale di agenti, non quanti girano insieme: al più cinque alla volta. Il ruolo di ogni agente
   viene dal profilo, o è quello nominato; in una gara fra ruoli o modelli diversi, ogni braccio è dichiarato prima.
3. **Le consegne** seguono «La consegna, in ogni strategia», con la fetta o il braccio della gara. Ogni agente che
   scrive ha la sua cartella, `.sciame/<convocazione>/agente-<n>/`, oppure un ramo o una copia di lavoro sua.
4. **La raccolta.** Leggi solo gli esiti finali:
   - nelle fette, ogni fetta deve avere un esito; quelle senza esito sono scoperte e lo dici;
   - nella gara applichi la regola dichiarata, mai un'altra scelta dopo.
5. **La risposta** è una tabella, una riga per fetta o per braccio (esito, prova, file); poi i problemi, uno per riga
   con la prova; poi le parti scoperte; poi, nella gara, la regola applicata. Niente copia dei rapporti grezzi.
6. **La verifica finale** la fai tu sul risultato integrato: un'evidenza degli agenti non è una prova.
<!-- /strategy:fan-out -->

<!-- strategy:classic -->
## Classica, in breve (la pipeline a grafo, ampliata)

Quando: c'è da decidere, progettare, correggere, dimostrare o misurare; ci sono alternative; un errore costa; c'è un
rischio da controllare. I ruoli di ogni fase vengono dal profilo del compito (tabella «Profili»).

**f0, il contratto (tuo).** Contiene:
- la domanda, una sola;
- il criterio che decide se la risposta è buona: una misura o un controllo, mai un meccanismo;
- gli ingressi;
- i principi e i vincoli del progetto, e le esclusioni;
- la quota di agenti e di tempo, divisa in tre terzi;
- il profilo.

Se la richiesta è ambigua, l'analista dei requisiti la chiarisce. Se il criterio è una misura, il metrologo controlla
che misuri ciò che dice.

**f1, due corsie cieche, in parallelo.** Ciascun ruolo riceve solo la sua consegna e il contratto.
- La corsia A, conservativa, ha uno o due specialisti del profilo: diagnosi, vincoli, due proposte con i
  controesempi possibili.
- La corsia B, divergente, ha il creativo (al più quattro idee tradotte) e il rovesciatore (al più due rovesciamenti).
- Ogni idea porta l'enunciato, il guadagno atteso, i vincoli, chi la può provare e il falsificatore più economico:
  al più cinque minuti, con l'esito atteso scritto prima.
- Le corsie non si leggono fra loro, e tu non leggi niente finché non hanno consegnato tutte.

**f2, traduzione, firme, triage, torneo, selezione.**
1. Un ruolo senza idee in gara (il traduttore del profilo) scrive una scheda per idea:
   - l'oggetto;
   - l'enunciato preciso;
   - il tipo;
   - i rischi;
   - l'ipotesi critica e il controesempio candidato;
   - come la si verifica.

   Niente fusioni: due idee sono la stessa solo se enunciato e tipo coincidono.
2. Ogni autore firma le schede delle sue idee: «fedele» oppure «si perde: …», e chi «si perde» ha la sua versione
   come scheda a parte.
3. L'arbitro fa il triage: assegna gli H# con una classe fra TESTARE, RIFORMULARE, APERTA e SMENTITA (solo con una
   prova), e mette in ordine le prime tre.
4. L'avversario esegue il falsificatore di ogni H# TESTARE o APERTA (senza strumenti, lo svolge a ragionamento).
   Una smentita vale per l'idea solo se la decide un controllo che non condivide il prototipo.
5. L'arbitro propone al più tre H# più una radicale, e tu decidi.

**f3, una squadra per H# scelta.** Ogni ramo è indipendente dagli altri.
- Il responsabile scrive la soluzione: passi, invarianti, costo, «dipende da», «invalidata se cambia».
- Un altro ruolo scrive la prova o la verifica.
- Il metrologo scrive il piano delle misure, con le soglie, prima delle prove.
- L'avversario prepara l'attacco.
- Se serve, si stima il costo (analista economico, sistemista delle prestazioni).

**f4, le prove, dalla più economica.** Le classi di prova:
1. a mano, o esaustiva su un caso piccolo (al più cinque minuti);
2. con un oracolo indipendente;
3. una prova realistica;
4. una prova su scala;
5. una prova a pagamento o irreversibile, solo con il sì dell'utente.

La classe k parte solo dopo l'esito della k−1. L'ordine dei compiti:
- prima le controprove dell'avversario;
- poi il debugger sulle anomalie e, se le controprove reggono, le misure;
- poi lo statistico sui numeri.

Un fallimento ferma il ramo e ne conserva il controesempio.

**f5, verdetti e chiusura.**
- Per ogni H#, il dossier con lo stato per proprietà: correttezza, completezza, efficacia, costo.
- Ogni risultato fondante passa quattro verifiche:
  1. la rilettura;
  2. l'audit delle ipotesi nascoste, da un ruolo non coinvolto;
  3. i controesempi;
  4. il consolidamento dell'arbitro.
- L'arbitro chiude solo se ci sono queste tre condizioni:
  - almeno una H# provata;
  - nessuna contraddizione aperta su una conclusione adottata;
  - ogni previsione risolta, o dichiarata non risolta con la prova che la deciderebbe.

**f6, l'integrazione (tua).** Integri solo ciò che la richiesta permette, e porti all'utente al più tre decisioni ad
alta leva.

**Sempre.**
- Un'anomalia va al debugger prima di essere usata.
- Una contraddizione K# va ai due ruoli che la sostengono e all'avversario, con una domanda binaria e al più due
  passaggi.
- Al più cinque agenti alla volta.
- Speso il primo terzo della quota, passi al verdetto con ciò che c'è.
<!-- /strategy:classic -->

<!-- strategy:full -->
## Completa, in breve (tutto lo sciame, poi la classica)

Quando: la domanda è strategica o aperta, tocca molti campi, chiede tutti i punti di vista, oppure una classica non è
bastata.
1. **f0, il contratto**, come nella classica.
2. **f1 larga, la tornata globale.**
   - Ci sono tutti i ruoli dello sciame, salvo l'arbitro, a ondate di al più cinque.
   - Ognuno è cieco agli altri e ha la stessa consegna: il contratto, e un contributo dal proprio punto di vista di al
     più mezza pagina. Sono da una a tre osservazioni o proposte, ciascuna con la prova o il falsificatore.
   - Un ruolo che non ha niente da dire scrive «non pertinente: …» in una riga, e va bene.
3. **f1c, il consolidamento dell'arbitro.** Prima per nucleo, poi d'insieme:
   - i fatti F#, con lo stato;
   - le contraddizioni K#;
   - le idee candidate, con la loro origine;
   - le domande aperte.

   Non si vota.
4. **L'innesto nella classica.** Le idee candidate entrano in f2 come schede d'ingresso, e da lì si prosegue come
   nella classica: traduzione, firme, triage, torneo, selezione, f3, f4, f5, f6. La corsia A e la corsia B non si
   rifanno: la tornata globale le contiene.
<!-- /strategy:full -->

<!-- strategy:auto -->
## Auto, in breve (la scelta del coordinatore)

Scegli prima di lanciare agenti, e scrivi la scelta in una riga in testa alla risposta, per esempio: «Sciame: auto,
scelta classica, profilo codice (c'è da scegliere fra due correzioni).»
- **singolo:** la richiesta è chiara, di un solo campo, e un errore si vede e costa poco; oppure chiede una
  spiegazione, una traduzione, una revisione, un riassunto, un calcolo.
- **classica:** c'è da decidere, progettare, correggere, dimostrare o misurare; ci sono alternative; un errore costa;
  c'è un rischio da controllare.
- **completa:** la domanda è strategica o aperta, tocca almeno tre nuclei, chiede tutti i punti di vista, oppure una
  classica precedente non è bastata.
- **ventaglio:** il lavoro si divide in parti indipendenti, oppure servono più tentativi dello stesso compito.
- **giuria:** c'è una proposta già istruita, con opzioni chiare, da decidere; l'esito è una raccomandazione, salvo una
  delega scritta dell'utente.
- **giuria leggera:** la decisione è piccola e poco influente, oppure un errore si scopre con una prova veloce: tre
  giurati, la prova prima del voto, un giro solo, poi la giuria ordinaria se serve.
- **plenaria:** solo per un passaggio da una fase maggiore all'altra o per una scelta d'impatto enormemente
  importante (cambia un obiettivo, apre o chiude una linea, è irreversibile, impegna risorse oltre i limiti dati); la
  propone il coordinatore, la conferma l'utente.
- **esperto:** la richiesta chiede una competenza che nessun ruolo ha (lo dice la ricerca nelle parole chiave e negli
  «in breve»).

In dubbio fra due strategie, scegli la più economica che soddisfa il criterio di successo. Mai la completa per una
richiesta di poche righe con una risposta verificabile.

I ruoli sono quelli del profilo, più quelli le cui parole chiave compaiono nella richiesta. Un sottoprofessionista
si convoca al posto del suo professionista quando la richiesta cade nella sua specializzazione; altrimenti si
convoca il professionista.
<!-- /strategy:auto -->

<!-- strategy:jury -->
## Giuria, in breve (una proposta, un voto)

Quando: c'è da decidere una proposta già istruita: una scelta fra opzioni, il testo di un atto, una regola. Le
regole complete sono in `GIURIA.md`; qui c'è ciò che serve per convocarla.
1. **L'autorità.** Di norma l'esito è una **raccomandazione** all'utente. Diventa **vincolante** solo se l'utente ha
   delegato per iscritto, voce per voce. Le azioni a pagamento, irreversibili o verso l'esterno restano sempre
   all'utente.
2. **La giuria**, scritta in `giuria.json` prima di aprire la proposta, sigillata (`SIGILLO giuria.json <sha>` in `SIGILLI.md`, protocollo G2 di `GIURIA.md` §10) e da lì in poi immutata:
   - da 5 a 9 giurati, in numero dispari, almeno metà istanze nuove sull'oggetto;
   - sempre il garante dell'obiettivo e un avversario; il debugger se la decisione tocca codice, lo statistico se
     tocca numeri; in una giuria vincolante anche il logico e il debugger;
   - un relatore che scrive la proposta e non vota; un arbitro come cancelliere, che conta e non vota.
3. **La proposta**, sigillata, ha per ogni decisione `Dk` le righe `OPZIONI`, `OPZIONE`, `DISPOSITIVO` ed
   eventualmente `DIPENDE`, il testo dell'atto, la **clausola dell'obiettivo** (bersaglio, catena, controfattuale,
   costo, ciascuno con una prova) e la riga `PLENARIA no|sì` con il motivo.
4. **I voti**, ciechi e sigillati: per ogni `Dk` le righe `VOTO`, `REVISIONE` (per un no) o `CONDIZIONE` (per un sì),
   `CLASSE ordinaria|plenaria`, e facoltativa `PREFERISCO`. Ogni giurato riporta i propri sigilli nella risposta
   finale, e il cancelliere li scrive in `SIGILLI.md`.
5. **Il conto** lo fa `python3 -I sciame/giuria.py conta <cartella> <giro>`:
   - consenso totale: APPROVATA, o RACCOMANDATA se l'autorità è una raccomandazione;
   - maggioranza: REVISIONE, cioè un giro con una revisione piccola che non tocca le CONDIZIONE dei sì;
   - minoranza o consenso sul no: RESPINTA.
6. **Al più tre giri di revisione.** Una revisione che fa perdere un sì si scarta; una che porta i sì in minoranza
   respinge; dopo il terzo giro la decisione è NON_CONVERGENTE e torna all'utente.
7. **La risposta**: le decisioni con l'esito, i voti, le revisioni, i limiti dichiarati della procedura.
<!-- /strategy:jury -->

<!-- strategy:light-jury -->
## Giuria leggera, in breve (decisioni piccole, prova prima del voto)

Quando: una decisione piccola e poco influente (reversibile, locale, senza voci riservate), oppure una scelta in cui un
errore si scopre con una prova veloce, al più cinque minuti. Si preferisce provare prima e coordinare poco.
1. **La giuria**, in `giuria.json` con `"forma": "leggera"`: tre giurati, cioè il ruolo più competente per la funzione,
   un critico (avversario, rovesciatore o debugger) e il garante dell'obiettivo; più il relatore e il cancelliere.
2. **La prova prima del voto.** Per ogni `Dk` la proposta porta, oltre a `OPZIONI`, `OPZIONE`, `DISPOSITIVO` e alla
   clausola dell'obiettivo in breve:
   - `PROVA Dk <comando o controllo>`, con l'atteso scritto prima;
   - `ESITO-PROVA Dk passa|fallisce`, dopo averla eseguita e prima del voto.
3. **I voti** come nella giuria, con `CLASSE Dk leggera|ordinaria|plenaria`.
4. **Gli esiti** (`giuria.py conta`):
   - consenso e prova che passa: APPROVATA, o RACCOMANDATA;
   - prova che fallisce: RESPINTA, anche con il consenso;
   - maggioranza: un solo giro di revisione, poi **DA_GIURIA**, cioè la giuria ordinaria;
   - un giurato che scrive `CLASSE ordinaria` la manda subito alla giuria ordinaria (DA_GIURIA); `plenaria`, alla
     plenaria.
5. **Il costo** è di cinque agenti. Non vale per le voci riservate in forma vincolante, né per una plenaria.
<!-- /strategy:light-jury -->

<!-- strategy:plenary -->
## Plenaria, in breve (per le scelte più gravi)

Quando: solo per il passaggio da una fase maggiore all'altra di un progetto, o per una scelta d'impatto enormemente
importante. La propone il coordinatore con il motivo, e la conferma l'utente. Costa da 60 a 80 agenti e oltre:
dichiaralo prima.
1. **Livello 1, la completa:** tutti i professionisti, a ondate, ciechi, con un parere breve e le richieste di
   esperti; chi non c'entra scrive «non pertinente».
2. **Livello 2, la convocazione usuale** per l'oggetto: la classica, o la giuria se la domanda è una proposta già
   istruita. Se non converge, la plenaria si ferma e torna all'utente con le cause.
3. **Livello 3, la passata critica:** avversario, rovesciatore, debugger, creativo, garante e gli esperti dei sistemi
   toccati, sull'esito del livello 2.
4. **Livello 4, due arbitri** indipendenti scrivono ciascuno una convergenza; dove discordano su un fatto, una prova
   li separa, altrimenti la discordanza diventa un rischio dichiarato o due opzioni.
5. **Livello 5, il voto finale** con le regole della giuria e il consenso fra i votanti: votano istanze nuove dei
   professionisti che al livello 1 non hanno scritto «non pertinente»; un sottoprofessionista vota solo su delega del
   suo professionista, e mai insieme a lui.
<!-- /strategy:plenary -->

<!-- strategy:expert -->
## Esperto nuovo, in breve (una competenza che lo sciame non ha)

Quando: la richiesta chiede una competenza che nessun professionista né sottoprofessionista copre.
1. **Cerca prima**: `bash sciame/sciame.sh ruoli "<la richiesta>"` e gli «in breve». Se un ruolo la copre, usa
   quello.
2. **La scheda provvisoria**, scritta prima di leggere la domanda nel dettaglio, nel formato delle schede: nome,
   in breve, genitore (il professionista più vicino, se è una specializzazione), parole chiave, missione,
   competenze, domande, limiti. Si sigilla.
3. **Lancia** un agente generico con il preambolo e la scheda; il suo contributo è marcato [provvisorio].
4. **Registra la richiesta** in `sciame/RICHIESTE_ESPERTI.md`, con il motivo: quali ruoli hai guardato e perché non
   bastano. Lo stesso fanno gli agenti che, in una convocazione, chiedono un esperto che non c'è.
5. **La soglia.** `bash sciame/sciame.sh richieste` dice quali competenze sono arrivate alla soglia: tre ruoli nella
   stessa convocazione (cinque in una plenaria), oppure tre richieste in due convocazioni da due ruoli.
6. **L'approvazione.** Alla soglia proponi all'utente la creazione, con la scheda definitiva in inglese (obbligatorio per il database pubblico) e, se vuoi, nella lingua
   dell'installazione.
   Approvata, `bash sciame/sciame.sh approva <file della scheda>` la aggiunge al database, rigenera agenti, skill e
   `sciame.sh`, e prepara la proposta per il repository pubblico.
<!-- /strategy:expert -->

<!-- profiles -->
## Profili per tipo di compito

| profilo | nome | per | f1, corsia A | f1, corsia B | f2, traduce | f3, per H# | f4, per H# |
|---|---|---|---|---|---|---|---|
| `code` | codice | scrivere o cambiare codice | architetto, sviluppatore | creativo, rovesciatore | logico | sviluppatore (soluzione), tester (verifica), avversario | avversario, debugger, tester |
| `defect` | difetto | bug, errori, anomalie | debugger, sviluppatore | rovesciatore | logico | debugger (causa), tester (test che fallisce prima), avversario | avversario, debugger, prestazioni se è lentezza |
| `architecture` | architettura | progetto di un sistema, scelte tecniche | architetto, requisiti | creativo, rovesciatore | logico | architetto (soluzione), sicurezza, ottimizzazione, avversario | avversario, prestazioni, economista |
| `test` | prova | matematica, logica, correttezza | formalista, matematico | rovesciatore | logico | formalista (prova), logico (rilettura), avversario | avversario |
| `data` | dati | analisi, statistica, misure, esperimenti | statistico, metrologo | creativo, rovesciatore | logico | dati (soluzione), metrologo (piano), statistico, avversario | avversario, debugger, statistico |
| `ai` | ia | modelli, prompt, agenti, addestramento | llm, ml | creativo, rovesciatore | logico | llm o ml (soluzione), metrologo, sicurezza, avversario | avversario, statistico, debugger |
| `research` | ricerca | stato dell'arte, confronti | ricercatore, esperto-dominio | creativo, machine-intelligence | logico | ricercatore (sintesi), fonti, avversario | fonti, avversario |
| `writing` | scrittura | testi, documenti, lettere | redattore, esperto-dominio | creativo, rovesciatore | requisiti | redattore (testo), lettore, fonti, avversario | lettore, fonti |
| `study` | studio | spiegare, imparare, ripassare | didatta, esperto-dominio | creativo, visualizzatore | redattore | didatta (spiegazione), visualizzatore, lettore | lettore, avversario |
| `decision` | decisione | scegliere fra opzioni, acquisti, investimenti | requisiti, economista | rovesciatore, creativo | logico | economista (confronto), normativo, pianificatore, avversario | avversario, statistico |
| `plan` | piano | progetti, organizzazione, calendari | pianificatore, requisiti | rovesciatore | logico | pianificatore (piano), economista, avversario | avversario |
| `security` | sicurezza | rischi, privacy, permessi | sicurezza, infrastruttura | rovesciatore, creativo | logico | sicurezza (contromisure), normativo, avversario | avversario, debugger |
| `device` | dispositivo | hardware, firmware, tablet, protocolli | embedded, infrastruttura | creativo, rovesciatore | logico | embedded (procedura), sicurezza, metrologo, avversario | avversario, debugger, metrologo |
| `interface` | interfaccia | UX, pannelli, flussi, testi d'interfaccia | interfacce, requisiti | creativo, rovesciatore | logico | interfacce (proposta), lettore, redattore, avversario | lettore, avversario |
| `perception` | percezione | rilevare, segmentare e riconoscere da immagini e nuvole di punti | visione, nuvole-punti | creativo, rovesciatore | logico | visione (soluzione), validazione, metrologo, avversario | avversario, debugger, validazione, statistico |
| `motion` | movimento | scene che cambiano con il movimento: oggetti mobili, cambiamenti, eventi | scene-dinamiche, slam | creativo, rovesciatore | logico | scene-dinamiche (soluzione), validazione, tracciamento, metrologo, avversario | avversario, debugger, validazione, statistico |
| `estimation` | stima | stimatori dello stato, filtri di Kalman, fusione delle misure | kalman, fusione | rovesciatore, creativo | logico | kalman (soluzione), matematico, metrologo, avversario | avversario, debugger, statistico |
| `tracking` | tracciamento | seguire più oggetti nel tempo: associazione, identità, previsione | tracciamento, kalman | creativo, rovesciatore | logico | tracciamento (soluzione), validazione, metrologo, avversario | avversario, debugger, statistico |
| `localization` | localizzazione | moto proprio, odometria, SLAM, mappe | slam, kalman | creativo, rovesciatore | logico | slam (soluzione), fusione, metrologo, avversario | avversario, debugger, statistico |
| `sensors` | sensori | scelta, montaggio, sincronizzazione e calibrazione di LiDAR, camere, radar, unità inerziali | lidar, sensori | rovesciatore, creativo | logico | lidar (soluzione), fusione, metrologo, avversario | avversario, debugger, metrologo |
| `latency` | latenza | percezione in tempo reale: latenza, sincronizzazione dei flussi, calcolo a bordo | tempo-reale, prestazioni | creativo, rovesciatore | logico | tempo-reale (soluzione), ottimizzazione, metrologo, avversario | avversario, debugger, prestazioni |
| `general` | generale | tutto il resto | logico, machine-intelligence | creativo, rovesciatore | formalista | secondo il caso, metrologo, logico (prova), avversario | avversario, debugger, statistico |

Valgono in tutti i profili:
- in f2, le firme degli autori, il triage e la selezione dell'arbitro, il torneo dell'avversario;
- in f4, il debugger su ogni anomalia di qualunque fase;
- in f5, l'arbitro per la chiusura.

Il traduttore non deve avere idee in gara: se è già in corsia A, traduce il formalista, o il logico se il formalista è
in gara. Si aggiunge ogni ruolo le cui parole chiave compaiono nella richiesta, entro la quota. L'esperto di dominio
ha nella consegna il campo in cui parla.

Nei profili della percezione (`percezione`, `movimento`, `stima`, `tracciamento`, `localizzazione`, `sensori`,
`latenza`) il responsabile di f3 è il primo ruolo indicato. Se il compito è di un altro campo (una nuvola di punti nel
profilo `percezione`, una camera nel profilo `sensori`), lo cambi con `seleziona --responsabile`.
<!-- /profiles -->

---

## Perché otto strategie

Le prime versioni dello sciame conoscevano due modi.
- **Le tornate di v1**: tutti i ruoli sulla stessa domanda, e un arbitro che legge tutto. Erano costose: un solo punto
  aperto faceva rifare la tornata a tutti.
- **La convocazione a grafo di v2**: poche ipotesi separate, fermate presto quando cadono, con cancelli controllabili.

Le due servono a cose diverse, e nella maggior parte delle richieste quotidiane non serve nessuna delle due: basta lo
specialista giusto.
- **Singolo:** per le richieste piccole, una sola consegna ben scritta allo specialista giusto vale più di uno sciame.
- **Classica:** è la v2 resa generale. Separa le ipotesi, le mette alla prova dalla più economica e dichiara che cosa
  è provato.
- **Completa:** è la tornata globale di v1, senza voto. Serve quando non si sa ancora dove guardare, e il suo
  risultato non è una conclusione: entra nella classica come materiale da vagliare.
- **Auto:** fa la scelta al posto dell'utente, con le regole scritte sopra, e la dichiara.
- **Ventaglio:** quando il lavoro è grande ma divisibile, o quando conviene confrontare tentativi indipendenti. La
  regola di scelta scritta prima impedisce di scegliere dopo il risultato che piace.
- **Giuria:** una decisione già istruita non chiede altre ipotesi, ma un giudizio indipendente e verificabile. Il voto
  con il consenso, le revisioni piccole senza regressione e il limite dei giri lo rendono tale.
- **Plenaria:** le scelte più gravi meritano tutti i punti di vista, una prova critica e un voto, nell'ordine.
- **Esperto nuovo:** uno sciame fisso invecchia. Le competenze mancanti si chiedono con un motivo, e diventano ruoli
  solo quando più convocazioni le chiedono.

## Principi che non si negoziano

- **Il criterio prima del meccanismo.** Il contratto dice come si riconosce una buona risposta, mai quale soluzione
  adottare.
- **Le prove prima delle conclusioni.** Le regole del `PREAMBOLO.md`: stati distinti, previsioni con l'ora prima delle
  prove, numeri con il file.
- **L'indipendenza per classe d'errore.** Ogni controllo dichiara che cosa condivide con ciò che controlla. Solo un
  controllo che non condivide il difetto lo può escludere. Un modo comune (due controlli che sbagliano allo stesso
  modo) si chiude sulla classe, non sul singolo testimone.
- **Le previsioni congelate.**
  - Si scrivono prima della prova che le decide, con l'ora e la soglia.
  - Se cambia la premessa (versione, dati, configurazione), la previsione resta, segnata «premessa cambiata», e prova
    il modello, non il meccanismo.
  - Una prova decide solo se parte dopo la registrazione.
- **Le scritture.**
  - Gli agenti scrivono solo nello spazio della convocazione.
  - Integra il coordinatore, e solo ciò che la richiesta permette.
  - Le azioni irreversibili, a pagamento o verso l'esterno le decide l'utente.
- **La convergenza non si forza.** Una soluzione incompleta si dichiara con le cause. Un'accettazione per difetto
  (finito il tempo, si prende ciò che c'è) non è un «non risolto»: è una decisione mancante, e si dichiara.

## La strategia classica nei dettagli

Il grafo è f0 → f1 → f2 → un ramo f3 → f4 per ogni H# scelta → f5 → f6. Le dipendenze sono fra file e cancelli, non
fra nomi di ruoli: un compito parte appena i suoi ingressi sono congelati. I rami delle H# non si aspettano fra loro;
solo f5 aspetta tutti i rami.

### I cancelli

Ogni fase finisce con un cancello, che il coordinatore approva dopo aver letto i file. Con i file lo controlla
`convoca.py cancello`, che lega con lo sha256 i file della fase: un file cambiato dopo
l'approvazione rende il cancello non valido. Un cancello non si approva perché i file esistono.

| cancello | condizioni |
|---|---|
| G0 | contratto completo: domanda, criterio, ingressi, vincoli, quota, profilo |
| G1 | consegne di tutte le corsie (o «non consegnato» dopo due arresti), nessun canarino di una corsia nell'altra, la foto delle letture fatta prima di leggere |
| G2 | firme degli autori prima del sigillo del triage, sigillo prima del torneo, selezione solo fra gli H# del triage, controfirma dell'arbitro |
| G3 (per H#) | soluzione, verifica, piano delle misure e previsioni congelati; le soglie raggiungibili e con una prova che le possa decidere |
| G4 (per H#) | controprove prima di ogni costo; classi in ordine; previsioni sigillate prima delle loro prove; le anomalie spiegate o dichiarate; dossier completo |
| G5 | le condizioni di chiusura dell'arbitro e le quattro verifiche dei risultati fondanti |

### La cecità delle corsie

- Ogni corsia scrive in una cartella dal nome casuale. La mappa delle cartelle la conosce solo il coordinatore.
- Ogni consegna comincia con il canarino della sua corsia: G1 rifiuta se il canarino di una corsia compare nell'altra.
  Il canarino scopre una copia, non una lettura.
- Appena le corsie hanno consegnato, prima di leggere, `convoca.py fotografa` registra per ogni file se è stato letto
  dopo l'ultima scrittura. È un indizio, non una prova.
- Gli agenti sono tutti lo stesso utente: i permessi non impediscono di leggere, quindi la cecità sta
  nelle consegne, nei canarini e nella disciplina del coordinatore.
- Senza file (gli agenti senza strumenti), la cecità è data dal fatto che ogni agente riceve solo la sua consegna.

### La sentinella

Nelle classiche con almeno due rami, in f2, f3 e f4 lavora un ruolo non convocato, estratto a caso. Ha venti minuti in
sola lettura e consegna:
- un presupposto condiviso, messo alla prova con un controllo esterno;
- le cifre e gli identificativi del dossier, ricontati dai file.

Un suo K# entra solo con un file. Serve a trovare ciò che nessun profilo avrebbe convocato.

### Le anomalie: il debugger

- **Che cos'è un'anomalia:**
  - un esito che contraddice una previsione;
  - un tempo o una memoria fuori scala rispetto a un caso vicino;
  - una divergenza fra due implementazioni o con un oracolo;
  - un errore, un «non deciso» o un valore di difetto che nessuno spiega.
- **Va al debugger** prima di entrare in un verdetto, con i soli file coinvolti, il sintomo con la cifra e il caso
  vicino che funziona.
- **Il debugger consegna** la causa provata: una riproduzione minima che fallisce prima della correzione e passa dopo.
  Consegna anche la classe del difetto, dove altro può esserci e la correzione con il suo test.
- **Senza causa provata** l'anomalia resta «non spiegata», e non sostiene nessuna affermazione.

### Le contraddizioni: i cicli locali

- Una K# va ai due ruoli che la sostengono e all'avversario, con i soli file coinvolti, una domanda binaria e la prova
  che la decide. Se è un'anomalia del codice, il terzo è il debugger.
- Si fanno al più due passaggi; poi la K# resta APERTA, con il costo dell'esperimento decisivo.
- Se tocca una conclusione adottata, l'adozione si sospende e la K# va all'utente.

### L'audit delle ipotesi nascoste

Si applica a ogni **risultato fondante**, cioè a un enunciato su cui poggia una certificazione, un'adozione o una
chiusura. Le quattro verifiche sono distinte:

| | verifica | chi | che cosa |
|---|---|---|---|
| V1 | la rilettura | un ruolo non autore | la validità dei passaggi rispetto alle premesse dichiarate |
| V2 | l'audit delle ipotesi nascoste | un ruolo non coinvolto né nella costruzione né in V1 (di norma il rovesciatore o un'istanza nuova del debugger) | le condizioni necessarie non dette: versioni, rappresentazioni dei dati, codifiche, cache e stato, ordine delle chiamate, bordi, domini vuoti, limiti operativi, differenze fra la teoria e il comportamento del sistema |
| V3 | i controesempi | un avversario non autore | casi minimi e limite, test metamorfici e differenziali, con le previsioni prima |
| V4 | il consolidamento | l'arbitro | lo stato, fra cinque: dimostrazione incondizionata; dimostrazione condizionata, con le premesse e il dominio; evidenza sperimentale, con l'insieme esaminato; controesempio certificato; questione aperta |

L'indipendenza è per istanza: un'istanza nuova di un ruolo, che non ha letto i giudizi degli altri, conta come
indipendente. Un audit negativo («nessuna ipotesi nascosta trovata») è un requisito procedurale, non una garanzia.

### Il dossier

Ogni H# ha un ID stabile (H-001) e un dossier dal modello `SCHEDA_IPOTESI.md`, che l'arbitro completa con il verdetto,
campo per campo, con i rimandi ai file del ramo. Un campo vuoto si scrive «manca».

## La strategia completa nei dettagli

- **Le ondate.** Al più cinque agenti alla volta, nucleo per nucleo, in quest'ordine:
  1. il nucleo critico (senza l'arbitro);
  2. i nuclei del profilo;
  3. gli altri.

  Ogni agente vede solo la propria consegna.
- **La consegna** è la stessa per tutti, cambia solo il ruolo: il contratto, la richiesta, e «dal tuo punto di vista:
  al più tre osservazioni o proposte, ciascuna con la prova o il falsificatore; se il tuo campo non c'entra,
  "non pertinente" e perché, in una riga».
- **Il consolidamento dell'arbitro** si fa per nucleo e poi d'insieme. Contiene:
  - i fatti con lo stato;
  - le contraddizioni;
  - le idee candidate con l'origine (ruolo e file);
  - le domande aperte;
  - i ruoli da chiamare nelle fasi seguenti.
- **L'innesto.** Le idee candidate diventano schede d'ingresso di f2, e i loro autori le firmano come nella classica.
  Il traduttore deve essere un ruolo senza idee fra le candidate: di norma un'istanza nuova del logico.
- **I costi.** Una completa costa quanto una tornata di v1 più una classica. Per questo «auto» la sceglie solo nei casi
  scritti sopra.

## Risorse

- **La quota.** Il contratto fissa il numero di agenti e il tempo, e li divide in tre terzi:
  1. le fasi fino a f3;
  2. verdetto e risposta;
  3. una riserva per riprese e agenti fermati.

  Speso il primo terzo, si passa al verdetto con ciò che c'è.
- **I tempi massimi** di riferimento: singolo 15 minuti, classica 60, completa 120 (undici ondate, poi la classica).
  Li fissa il contratto, e l'utente può fermare in ogni momento.
- **Gli agenti** sono al più cinque alla volta. Un agente fermato si rilancia con la sua sola consegna e il suo
  `stato.md`; dopo due arresti la sua consegna è «non consegnata».
- **I processi pesanti** vanno uno alla volta per agente, con `timeout`. GPU e servizi a pagamento solo con il sì
  dell'utente.

## Come si svolge nei diversi ambienti

- **In un progetto, con i file.** Il coordinatore è la sessione di Claude Code aperta nella radice del progetto, e
  gli agenti sono i suoi sottoagenti `sciame-<sigla>`.
  - La convocazione sta in `.sciame/<AAAAMMGG-HHMM>-<nome>/` dentro il progetto.
  - `sciame/convoca.py` prepara lo scheletro e controlla i cancelli.
  - I documenti completi sono in `sciame/`.
- **Senza shell o senza scritture.** Le fasi sono le stesse. Le consegne stanno nei prompt, le risposte degli agenti
  sono le consegne, e i cancelli li controlla il coordinatore con le condizioni scritte sopra.
- **Con un modello raggiunto per API,** che non lancia agenti: un programma proprio fa il coordinatore, una chiamata
  per ruolo, con i testi di `sciame/catalog.json` (`ISTRUZIONI_COORDINATORE.md` dice quali chiamate). Le fasi f3 e
  f4 sono condensate: niente esecuzioni, solo critiche e verifiche a ragionamento.
- **L'isolamento.** Gli agenti lavorano con i permessi della sessione che li lancia. Dove un compito esegue codice non
  fidato, installa pacchetti o tocca un dispositivo, la sessione va aperta in un ambiente isolato (un contenitore,
  una macchina a perdere): lo sciame non lo fa da sé.

## Dossier e consegne

- Le consegne non dicono «esamina il progetto». Danno:
  - gli ingressi, con il percorso assoluto o il testo;
  - il file d'uscita;
  - la prova minima, la soglia e il tempo;
  - la classe massima di prova;
  - i divieti e il destinatario.
- Gli ID provvisori portano il prefisso del ruolo (`creativo-2`); gli H#, F# e K# definitivi li assegna l'arbitro.
- La risposta all'utente comincia con una riga «Sciame: <strategia>. Ruoli: <ruoli>.». Poi viene il risultato, con
  gli stati di ciò che afferma, gli aperti e al più tre decisioni che spettano a lui.

## Che cosa cambia

**Rispetto alla 4.0.**
- **Il nome** è swarmer: lo script è `swarmer.sh` (`sciame.sh` resta come alias), il codice è in `engine/`, i
  documenti in `docs/<lingua>/`, il database in `db/professionals.json` (formato 2; il formato 1 si legge).
- **Due lingue piene.** Ogni comando, opzione e valore ha il nome inglese e quello italiano, e tutti e due valgono
  in ogni installazione; le abbreviazioni delle opzioni non valgono più. In un'installazione italiana tutto ciò che
  si scrive nel progetto è italiano: `sciame/`, `.sciame/`, `sciame-<sigla>`, `MANIFESTO.json`, `giuria.json`.
- **Le righe di protocollo** si leggono nelle due lingue (`GIURIA.md`, §11); le giurie già votate si ricontano
  identiche.
- **I profili** hanno l'id inglese (`code`, `defect`, …); il nome italiano vale come alias.

**Rispetto alla 3.1.**
- **Professionisti e sottoprofessionisti** in un database unico (`db/professionisti.json` nella 4.0), nelle lingue della skill;
  `AGENTI.md` è generato da lì.
- **Quattro strategie nuove:** ventaglio, giuria, plenaria, esperto nuovo; la completa resta l'esplorazione senza
  voto e diventa il livello 1 della plenaria.
- **La consegna comune** a tutte le strategie, con il criterio di fatto, lo spazio di scrittura e di divieto, la
  verifica e le tre parole d'esito.
- **Le lingue:** italiano e inglese, scelte con `bash sciame/sciame.sh lingua <codice>` o all'installazione; altre
  lingue si aggiungono con una proposta al repository.
- **L'installazione sovrapposta** in un progetto che ha già uno sciame proprio: non tocca i suoi file e i suoi agenti.
- **L'ambiente** (`AMBIENTE.md`): che cosa fare quando un ambiente non ha i sottoagenti, la shell o le scritture.

**Rispetto alla 3.0.**
- **È portabile.** Tutto sta nella cartella `sciame/` del progetto. Gli agenti e le skill si generano in `.claude/`.
- **Il nucleo della percezione.** Undici ruoli e sette profili: `percezione`, `movimento`, `stima`, `tracciamento`,
  `localizzazione`, `sensori`, `latenza`.
- **`convoca.py`.** Il comando `ruoli` e l'opzione `--responsabile` di `seleziona`.

**Rispetto alla v2.** I contenuti propri di un progetto sono usciti: al loro posto ci sono i principi che il contratto
di ogni convocazione dichiara. Restano i cancelli G0–G5, le corsie cieche con i canarini, i sigilli e la selezione
solo dal triage.
