# Registro delle modifiche

*[English](CHANGELOG.md)*

## 5.3.0

Compatibile all'indietro: ogni cancello si ricalcola con le regole con cui è stato approvato, così ogni cancello
approvato prima resta valido. Le regole 3 dei cancelli valgono solo per una convocazione nuova e per un cancello dato
con `--regole 3`. La chiave `hooks` non fa parte della 5.3.

### Le regole 3 dei cancelli: l'ordine di f4 letto dai sigilli (ENG-19, COORD-1, ENG-21, COORD-2)
- Una convocazione nuova nasce con `regole_cancelli` 3; `cancello C FASE --regole 3` le applica a un cancello di una
  convocazione più vecchia.
- Con le regole 3, il G4 ordina f4 con le ore dei sigilli di `SIGILLI.jsonl`, mai con un mtime, che una copia o un
  touch spostano:
  - un `PREVISIONI.md` della cartella delle controprove (`01-`) si sigilla prima che `CONTROPROVE.md` sia sigillato la
    prima volta;
  - quello di un ruolo che lavora dopo le controprove (la revisione del responsabile, il debugger, le misure, V2,
    l'arbitro) si sigilla prima che l'uscita di quel ruolo sia sigillata la prima volta;
  - ogni blocco di un `PREVISIONI.md` ha un sigillo suo, le uscite rispetto a cui si ordina sono sigillate, e due
    sigilli nello stesso secondo non mostrano un ordine.
- Con le regole 3, il G4 rifiuta una `REVISIONE.md` che non è sigillata la prima volta dopo ogni `CONTROPROVE.md` e
  `DIFETTI.md` del suo giro.
- Le consegne di f4 nominano il tipo delle previsioni di ogni ruolo. Con le regole 1 e 2, che ordinano ogni
  `PREVISIONI.md` di f4 prima delle controprove, ai ruoli che lavorano dopo di esse si chiedono le previsioni in cima
  alla loro uscita, e la consegna del responsabile non chiede più un `PREVISIONI.md` che non potrebbe sigillare.

### I giri di un ramo (ENG-18, ENG-22)
- `rifissa C H-00x [--responsabile SIGLA]` (in inglese `repin`) apre il giro 2, poi 3, …, della f4 di un ramo
  finanziato, in `f4_2/<H#>/`. Scrive di nuovo ogni consegna di f4, con il giro precedente fra gli ingressi, e un
  dossier suo. Non cambia nessun file di un giro precedente, né `f3/<H#>/<H#>.md`, né un sigillo o un cancello.
- `cancello C f4/H-00x` è allora il G4 dell'ultimo giro del ramo, `GATE_f4_2_<H#>.json`. Segue solo le regole 3, e lega
  e conta solo i file del giro. Il G5 e `stato` leggono l'ultimo giro.
- Una seconda `seleziona` si rifiuta: scriveva la scheda vuota su un dossier completato e sostituiva la selezione
  registrata.

### Una chiusura successiva dopo un G5 «non chiuso» (E12)
- Dopo un G5 che regge e registra una non chiusura, `finanzia`, `chiudi-ramo` e `rifissa` agiscono di nuovo. Una non
  chiusura è «chiuso» falso con le regole 2 e 3, o una chiusura che dice «non chiuso» con le regole 1.
- Danno le consegne della chiusura successiva accanto alla prima, in `f5_2/` (poi `f5_3/`, …). Quando quella cartella
  esiste, `cancello C f5` controlla `f5_2/CHIUSURA.md` e la sua sentinella `f5_2/00-sentinella/SENTINELLA.md`, lega
  ogni file di `f5_2/`, e scrive `GATE_f5_2.json`, creato in esclusiva. `GATE_f5.json` e ogni file che lega restano
  identici byte per byte, e il primo G5 regge ancora.
- L'ultimo G5 è quello con l'ordinale più alto nel nome del file, cifre ASCII lette come intero; mai l'mtime più
  recente, l'ora del cancello o l'ultimo dei nomi ordinati.
- Ogni lettore del G5 legge l'ultimo: `finanzia`, `chiudi-ramo`, `rifissa`, `seleziona`, `stato` e `cancello f5`. Il
  blocco si apre solo su un ultimo G5 che regge e registra una non chiusura.
- Un file di cancello di f5 vuoto, che comincia con un BOM, non UTF-8 o non JSON ferma ogni lettore con uscita 1 e
  niente scritto. Così anche un secondo nome per un ordinale (`GATE_f5_02.json`).
- Prima che la chiusura successiva abbia le sue consegne, `cancello C f5 --verifica` controlla di nuovo l'ultimo G5,
  come nella 5.2, e un cancello f5 che scriverebbe sopra una non chiusura registrata si rifiuta.

### La catena fino al contratto (ENG-26)
- Con le regole 3 ogni cancello ricontrolla G0, non solo il cancello subito prima: un contratto o un file di `f0/`
  cambiato dopo G1 fa rifiutare ogni cancello successivo. Il cancello di un emendamento ricontrolla gli altri
  emendamenti approvati, come ogni altro cancello faceva già con le regole 2; un emendamento senza cancello non si
  aspetta.
- Con le regole 1 e 2 un cancello ricontrolla solo il cancello subito prima, come nella 5.2. `--regole` alza soltanto
  le regole di un cancello, mai sotto quelle della sua convocazione.

### Robustezza (ENG-13, ENG-24, ENG-25)
- Un nome di file che non è UTF-8 si lega con i suoi byte, come file di una fase e dentro uno spazio di lavoro, dove
  `_tree`, `_bind` e il JSON del cancello si fermavano con un UnicodeEncodeError. I file JSON di una convocazione
  scrivono un nome così come il suo escape JSON (`\udcff`), così restano UTF-8; ogni altro byte si scrive come prima,
  e ogni voce d'albero di un nome UTF-8 tiene la sua impronta.
- I cancelli, la foto, la mappa, una chiusura anticipata e il manifesto si scrivono in un file temporaneo accanto e poi
  si spostano al loro posto, così una scrittura che fallisce lascia il file vecchio com'era, mai un cancello di 0 byte.
  Un cancello f5 successivo, creato in esclusiva, si toglie se la sua scrittura fallisce.
- `giuria.py conta .` (o `..`) legge le giurie precedenti accanto alla cartella della giuria, non dentro: la cartella
  si rende assoluta prima di prenderne la madre. Una cartella assoluta le legge dove le leggeva.
- Una consegna, una chiusura o un contratto che si limita a citare il segnaposto `<da compilare>` (in un frammento di
  codice, in un blocco di codice recintato o rientrato o in una frase) è compilato. Il segnaposto da solo su una riga,
  come valore intero di un campo (`- Risultati: <da compilare>`, `Fetta 1 di 14: <da compilare>`) o come cella intera
  di una tabella lo lascia ancora da compilare, anche seguito da un segno di punteggiatura (`- Obiettivo: <da
  compilare>.`) e quando è rientrato come contenuto di una voce di elenco. È un allentamento, quindi vale con ogni
  regola.

### La versione (ENG-14)
- La versione dello sciame è scritta in un posto solo, `engine/generate.py` (5.3); il `VERSION` dello sciame, il
  catalogo, il manifesto di una convocazione nuova e `convoca --help` la leggono da lì. `plugin.json`, da cui il
  plugin di Claude Code e il pacchetto Agensi prendono la loro, è 5.3.0. Gli involucri, gli alias e le docstring del
  motore non dichiarano più una versione, e `tests/test_robustness.py` controlla che ogni documento che ne dichiara una
  sia d'accordo.
- La `versione` del manifesto non è una versione del formato: nessun motore la legge. Registra lo sciame che ha
  preparato la convocazione; la 5.0, la 5.1 e la 5.2 vi scrivevano tutte 5.0, e la 5.3 scrive 5.3.

### Le sentinelle di f2, f3 e f4, e la loro estrazione (ENG-17, ENG-16)
- Scelto con le prove: la PIPELINE resta, e il motore scrive le consegne delle sentinelle che descrive, invece di
  ridurre la PIPELINE alla f5. Quattro convocazioni classiche del laboratorio hanno fatto lavorare a mano sentinelle di
  f2, f3 e f4, in `<fase>/00-sentinel/` (convocazioni inglesi) senza consegna su disco (così la loro estrazione non si
  poteva verificare), e la sentinella di f4 di una di loro ha smentito i suoi tre G4 così com'erano.
- `prepara` scrive la consegna della sentinella di f2 in ogni classica e completa, `f2/00-sentinella/TASK.md`: i rami
  non si conoscono prima della selezione, e le schede e il triage sono ciò che ogni ramo eredita. Con le regole 3, il G2
  vuole la sua `SENTINELLA.md`, oppure `--non-consegnati <ruolo>`: il G2 lega ogni file di f2, quindi una sentinella
  consegnata dopo lo invaliderebbe.
- Con le regole 3, con almeno due rami finanziati, `seleziona` e `finanzia` scrivono le consegne delle sentinelle di f3
  e f4, `f3/00-sentinella/` e `f4/00-sentinella/`, una volta e prima di ogni G5. Il G3 e il G4 avvisano finché manca la
  loro. Il primo G5 le vuole entrambe, oppure «Dichiarato mancante: sentinella: <motivo>», e ne lega le cartelle, che
  nessun cancello di un ramo lega. Una chiusura successiva, e un giro aperto da `rifissa`, non hanno una sentinella di
  fase nuova: le legge la sentinella della chiusura. `sentinel_found` accetta la sentinella di una fase, e la consegna
  della chiusura elenca le loro consegne.
- Con le regole 3 ogni sentinella (di f2, f3, f4 e di ogni chiusura) si estrae con il seme della convocazione fra i
  ruoli liberi: nominati da nessuna consegna della convocazione e non convocati dal suo profilo. Fra questi vengono
  prima i ruoli adatti alla domanda (una loro parola chiave in essa, come la trova `ruoli --domanda`), i professionisti
  prima dei sottoprofessionisti; tutti i ruoli liberi quando nessuno è adatto. La consegna registra l'estrazione: il
  seme, l'insieme e le parole chiave del ruolo estratto, oppure che nessun ruolo libero era adatto. `finanzia` e
  `rifissa` rifiutano una sentinella come `--responsabile`. Con le regole 1 e 2 la sentinella della chiusura si estrae
  come nella 5.2.

### Le K# di una convocazione (ENG-15)
- `contraddizione C FILE… --domanda TESTO` (in inglese `contradiction … --question`) assegna la K# successiva della
  convocazione, `K-001`, `K-002`, …, in `CONTRADDIZIONI.jsonl` alla sua radice (`CONTRADICTIONS.jsonl` in una
  inglese), con la domanda binaria e i file dei suoi due lati. La numerazione è una sola per tutti i rami, dove la
  numerazione per verdetto di ramo aveva dato una K# sola a due domande. Uno scrittore alla volta, come per
  `SIGILLI.jsonl`: il coordinatore.
- Il motore lo legge. `stato` elenca le K#. Una riga che non è una K#, o una K# scritta due volte, ferma ogni lettore
  con uscita 1. Con le regole 3, il G5 vuole ogni K# assegnata nominata nella chiusura, risolta o aperta, e il G4 e il
  G5 avvisano di una K# citata e mai assegnata; le consegne del verdetto, della chiusura, del consolidamento e delle
  sentinelle nominano il registro.

### Le consegne (ENG-20, ENG-23, ENG-12)
- Ogni consegna di f3 chiede la riga «decide: sì|no» che il G3 vuole in ogni `PREVISIONI.md` di f3: quelle dei
  compagni (prova, piano delle misure, attacco) come quella del responsabile. Una classica i cui ruoli di f3 seguono le
  loro consegne passa il G3 senza righe aggiunte dopo.
- La consegna della chiusura dice che cosa controlla il G5 di una non chiusura: ogni ramo senza un G4 valido del suo
  ultimo giro né una chiusura anticipata, e una radicale mai finanziata né chiusa. Nomina i rami su cui lo controlla,
  dove prima diceva «ogni ramo senza verdetto» e non ne nominava nessuno.
- In un ventaglio a gara, e in uno misto, la consegna di ogni braccio comincia con un canarino suo, registrato nella
  mappa delle corsie. Il G1 lo controlla come controlla le corsie di una classica: una consegna senza il suo canarino o
  con quello di un altro braccio si rifiuta, e serve la fotografia delle letture. Un ventaglio a fette non ne ha, come
  prima. La mappa di una convocazione italiana scrive `agente-<k>`, come il suo manifesto.

### Che cosa vede un motore 5.2
- I giri si leggono dalle cartelle e dai file dei cancelli, e il manifesto tiene le chiavi della 5.2, così un motore
  5.2 carica ancora una convocazione della 5.3.
- Legge il G5 solo da `GATE_f5.json`. Una convocazione chiusa di nuovo da una chiusura successiva per lui è ancora «non
  chiusa», e `finanzia` e `chiudi-ramo` restano rifiutati. Un ramo chiuso dopo il primo G5 gli appare chiuso in
  anticipo, e ignora `f5_<n>/` e `f4_<n>/`, quindi un ramo rifissato gli mostra il suo giro 1.
- La 5.3 apre il blocco dopo un G5 delle regole 1 la cui chiusura dice «non chiuso», dove la 5.2 rifiuta dopo ogni G5.
- Su una convocazione nata con le regole 3, un motore 5.2 controlla un cancello con le condizioni delle regole 2 ma vi
  registra `regole` 3, e la 5.3 legge poi quel cancello come approvato. Una convocazione così si approva solo con la
  5.3.
- La 5.2 legge un file di cancello che la 5.3 ha scritto su un nome non UTF-8 legato come file, e lo tiene valido;
  uno spazio di lavoro che contiene un nome così ferma ancora la 5.2 con uscita 1, come prima. La 5.2 rifiuta ancora
  una consegna che si limita a citare il segnaposto, e da un cancello successivo non ricontrolla G0.
- Ignora le sentinelle di f3 e f4 e il registro delle K#, e non ha `contraddizione`; il suo G2 lega la cartella della
  sentinella di f2 senza richiederla. Un G5 che la 5.2 approva su una convocazione nata con le regole 3 lega solo f5,
  quindi la 5.3 lo legge come non più valido appena esistono le sentinelle di f3 e f4 (letto dal codice, non eseguito).
- Controlla il canarino di ogni braccio di una gara in una convocazione inglese, dalla mappa delle corsie. In una
  italiana non rilegge le chiavi `agente-<k>` della mappa, quindi controlla solo la fotografia delle letture (letto dal
  codice, non eseguito).
