# FORMATI_INCROCI: i formati condivisi di sciame-incroci 1.0

Questo documento è il contratto tra incroci e chiunque lo usi (compresa la prossima estensione). §1–§6 traducono il
testo sigillato dei formati della convocazione crossroads-r2 (fetta 1); il testo che fa fede è quello inglese,
`CROSSROADS_FORMATS.md`, riportato parola per parola. I percorsi citati (`f4/…`, `work/…`) sono l'archivio di progetto
di quelle convocazioni, lasciati come furono scritti. §7 è l'interfaccia per chi consuma, §8 il glossario, §9 i corpi
dei tre record, §10 l'emendamento F, che cambia §3 dove lo dice ed è l'unico testo a farlo. Dove §1–§6 e §10 non
concordano vale §10. Il deposito è `<stato>/crossroads/` (in italiano `<stato>/incroci/`), dove `<stato>` è
`.swarmer/` del progetto (in italiano `.sciame/`); i nomi al suo interno sono canonici in ogni lingua (per esempio
`crossroads/view/graph.jsonl` è `.sciame/incroci/view/graph.jsonl` in un'installazione italiana).

## 1. Formato (a): la riga di dipendenza [=, Δ B adottato]
`DEPENDS-ON <id> <id>…` alla colonna 0 di un file designato, fuori dai blocchi ```. Alias italiano `RICHIEDE` (la modifica
f4 di B, ora vincolante per entrambi; `DIPENDE-DA` è ritirato perché `DIPENDE DA D1` rompe `jury.py count`, A-7). Una riga
può portare più id; l'arco è `depends_on` dalla decisione che possiede la riga a ogni id. Un *locatore* nudo si risolve
dentro lo stesso file.

## 2. Formato (b): gli id [Δ B: ancora della giuria]
| cosa | grammatica dell'id | esempio |
|---|---|---|
| ancora di convocazione | `<name>@<created>` (MANIFEST `name`, `created` ISO 8601 con fuso) | `crossroads@2026-11-17T08:03:16+01:00` |
| decisione di convocazione | `<ancora conv>/<relpath>#<loc>`, *locatore* `loc` = `D\d+` \| `H-\d{3}` \| `select` | `…/f2/03-triage/TRIAGE.md#H-001` |
| **ancora di giuria [Δ B, K-104, decisione dell'utente 3]** | `jury:<dir>@<sha256(jury.json)[:12]>`; `dir` = percorso POSIX della cartella della giuria relativo alla radice del progetto; dentro ogni segmento `%`, `@`, `#`, `(`, `)`, gli spazi e i controlli C0/C1 sono codificati in percentuale (`@` → `%40`) | `jury:.swarmer/j-auth@4bac0fa6380c` |
| decisione di giuria | `<ancora giuria>#<loc>` | `jury:.swarmer/j-auth@4bac0fa6380c#D1` |
| record canonico | `U-` \| `R-` \| `N-` + `sha256(byte del corpo)[:12]` (regex `^[URN]-[0-9a-f]{12}$`) | `R-c418a7941dd2` |
| opzione | `<id della decisione>(<etichetta>)`; `etichetta` = 1+ caratteri senza `(`, `)`, `\|`, controlli; spazi interni ammessi (B2), esterni tolti | `U-4fe64b59b127(a)` |
| nodi valore | `who:<ruolo>`, `concern:<nome>` (mai pendenti) | `concern:engine` |
| riferimento di evidenza | `<ancora>/<relpath>@<sha12 del file>` o qualunque id sopra | `…/TRIAGE.md@5f26f5cd7553` |
| posizione nella fonte | `<ancora>/<relpath>:<riga>` o `records/<id>.md` (campo `src`, solo per la lettura) | |
Non sono id (chiavi di sola visualizzazione, mai salvate nei record): l'*handle* `h(id)` = `sha256(id)[:HLEN]`, HLEN ≥ 12,
+2 finché non c'è collisione (`index/HLEN`); l'*indice di membro* `m<k>`; il ramo `crossroads/<h(D′)>`. Trailer:
`Crossroads-Decision`, `Crossroads-Concern`, `Crossroads-Reverts` (sintassi dei trailer di git, un valore ciascuno). Due
cartelle di giuria con jury.json identico byte per byte ora hanno due ancore, quindi DUPLICATE-ANCHOR scatta solo per lo
stesso `dir` due volte (prova: `work/a12`, entrambe le strade nel grafo).

## 3. Formato (c′): UNO sha del blocco, il record R e la sua proiezione TSV [Δ A, Δ B]
**3.1 Il diff** (entrambi i rami, ogni sha di blocco, `realize` e ogni scansione dei commit, `check-commits`, `plan`,
`--realized`). Ambiente `GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_ATTR_NOSYSTEM=1 LC_ALL=C`, e
```
git -c core.quotePath=false -c core.attributesFile=/dev/null -c diff.algorithm=myers -c diff.indentHeuristic=false
    -c diff.interHunkContext=0 -c diff.suppressBlankEmpty=false -c diff.noprefix=false -c diff.mnemonicPrefix=false
    -c diff.relative=false -c diff.external= -c diff.orderFile= -c color.ui=never -C <repo>
    diff-tree -r --root --no-commit-id <FLAGS> <commit>        # un commit contro il suo unico genitore (merge: nessuno, NONLINEAR)
    diff --cached <FLAGS>                                     # realize: indice contro HEAD (vedi §10 F-1)
FLAGS = -p --raw -z -U0 --no-renames --no-ext-diff --no-textconv --diff-algorithm=myers --no-indent-heuristic
        --inter-hunk-context=0 --src-prefix=a/ --dst-prefix=b/ --ignore-submodules=none --no-color
```
**[Δ A]** `changes()` di A usava `git log -p -U0` con `diff.algorithm`, `diff.interHunkContext`, l'euristica di rientro e
textconv del repository (K-dbg-1, correzione obbligatoria 9). **[Δ B]** I vincoli di B restano, più `-z --raw`,
`core.attributesFile`, `diff.external`, `diff.orderFile`.
**3.2 Percorso.** Il percorso è il campo terminato da NUL del record `--raw -z` (percorso dopo la modifica; con
`--no-renames` è uguale a quello prima), come byte grezzi. **Non** è mai letto dalle righe `---`/`+++`. **[Δ B]** B leggeva
`+++ b/x y.txt\t` e includeva il TAB nello sha (misurato, `out_hs_test.json` HS3: 2 blocchi su 19 differiscono, entrambi
sul percorso con uno spazio; accettazione B6). Il record grezzo *i* va con la sezione di patch *i* (vedi §10 F-2).
**3.3 hunk_sha256** = esadecimale minuscolo `sha256(P ‖ LF ‖ L₁ ‖ LF ‖ … ‖ Lₙ ‖ LF)`, dove P sono i byte del percorso e
L₁…Lₙ le righe del blocco nell'ordine di git (tutte le `-` poi tutte le `+`), ciascuna con i byte esatti che git stampa,
segno `-`/`+` compreso, senza l'LF finale (un CR resta); una riga marcatore `\` conta come i byte esatti
`\ No newline at end of file`. **[Δ A]** A scartava il marcatore (HS4: i 3 blocchi senza fine riga differiscono anche con
una configurazione pulita). Sezione binaria (`Binary files … differ`): hunk_sha256 = il letterale `BINARY`, nessuna riga.
Le modifiche del solo modo non hanno blocchi (A: MODE); un modo `160000` è UNSUPPORTED, nessun blocco. Implementazione di
riferimento: `hunksha.py` (libreria standard).
**3.4 Intestazione del blocco** `a,b c,d` = i numeri di `@@` con il conteggio omesso scritto come `1`. **3.5 Chiave del
blocco** = (percorso, intestazione, hunk_sha256). **Occorrenza del blocco** = (sha40 del commit, percorso, ordinale k in
quel percorso, intestazione, hunk_sha256). **hunk_sha256 da solo è un hash di contenuto, mai un'identità** (B7, K-403): due
decisioni che aggiungono lo stesso testo hanno lo stesso sha. Un commit *porta* un record R quando ogni chiave di blocco
di R è tra le occorrenze del commit; un R realizzato da più commit che lo portano si risolve con un'assegnazione che
preferisce il commit il cui trailer nomina la decisione di R, e TRAILER-MISMATCH si riferisce solo quando nessun commit che
lo porta la nomina (l'algoritmo è del Ramo B; questo file fissa solo le chiavi che usa). L'intreccio in A può continuare a
confrontare hunk_sha256 per contenuto.
**3.6 Atomo di riga** `LINE <percorso> +|- <sha256(byte della riga senza segno né LF)>` [=]; i marcatori non fanno atomi.
**3.7 Corpo del record R** (lo scrittore di B; una chiave per riga, chiavi in quest'ordine, chiavi multiple ordinate):
`KIND realization`, `TIME <ISO 8601 con fuso>`, `DECISION <id>`, `CONCERN <nome>`, `MODE git|nogit`,
`HUNK <qpath> <hunk_sha256|BINARY> <intestazione>`…, `LINE <qpath> +|- <sha256>`…. `qpath` = il percorso, tra virgolette
alla maniera di git (`"…"` con `\t \n \" \\` e l'ottale per gli altri controlli) quando contiene uno spazio, un TAB, `"`,
`\` o un controllo; UTF-8 grezzo altrimenti **[Δ B]** (B divideva sugli spazi, A9/B6). I blocchi `nogit` (difflib con
intestazioni alla git) si confrontano solo con blocchi `nogit`; gli atomi LINE si confrontano tra i modi [=].
**3.8 Proiezione TSV** `realized.tsv` (l'ingresso `--realized` di A), una riga per HUNK, separata da TAB, con `\t \n \\`
protetti: `decision  concern  commit|-  path  hunk_sha256  header` **[Δ A: aggiunta la colonna 6; A indicizzava le righe
per hunk_sha256 soltanto]**. `commit` è il commit assegnato che lo porta, `-` finché non ce n'è. B la scrive dal grafo
(derivata, P4); A non la scrive mai.

## 4. Formato (d): i cursori [=]
Un cursore è un id di record o un hash di istantanea `SNAPSHOT_<sha256(graph.jsonl)[:12]>` sotto
`.swarmer/crossroads/log/`, mai un offset in byte. Un cursore sconosciuto risponde «full resync» (uscita 1).

## 5. Formato (e): il grafo derivato `.swarmer/crossroads/view/graph.jsonl` [nuovo; K-404, J1]
Un oggetto JSON per nodo e per riga, UTF-8, LF, chiavi ordinate, nodi ordinati per `id`, `ensure_ascii=false`.
Sacrificabile: una funzione pura delle fonti, dei record, degli oggetti git e dell'albero (P4). Gli scalari mancanti nella
fonte sono la stringa `NR` = `"not recorded"`; **le liste mancanti sono `[]`, mai una divisione di NR** **[Δ B]** (2 nodi
portano `depends_on: ["not","recorded"]`: `H-001/01-avversario/work/b_ud3` r.4 e `00-architetto/tests/work/pa12` r.1). Tipi di
decisione: `user`, `jury`, `triage`, `selection`; contenitori: `convening`, `jury`; altri: `option`, `realization`, `note`.
Un nodo decisione è un nodo con `node_class` ∉ {container, option, record}.
| # | campo (e) | tipo | sui tipi | fonte (B) | nome f4 di A (stub, `proto/README.md` r.9–13) | letto da A in |
|---|---|---|---|---|---|---|
| e1 | `id` | str, formato (b) | tutti | id §2 | chiave di `{id: record}` | tutti |
| e2 | `kind` | enum sopra | tutti | tipo della fonte | — | radius, brief |
| e3 | `node_class` **[Δ B: era `base`]** | enum container, decided, recommended, open, not_decided, rejected, invalid, option, record (STATUS_MAP, B proto r.18) | tutti | mappa degli stati | — (il `base` di A è un commit git) | radius |
| e4 | `lifecycle` **[Δ A: era `status`]** | enum: i valori di e3 più `superseded` | tutti | sovrapposizione §3.1 | `status` | riga del membro nella sintesi |
| e5 | `depends_on` | [id], ordinata | decisioni | formato (a), U DEPENDS-ON, giuria DEPENDS | `depends_on` | radius, plan, CYCLE, bozza di D′ |
| e6 | `supersedes` | [id], ordinata | decisioni | SUPERSEDES/SOSTITUISCE, giuria `previous` | `supersedes` | Δ (S(Rad)), bozza di D′ |
| e7 | `time` | str ISO 8601 con fuso, o NR | decisioni, R, N | TIME, MANIFEST, SEALS.jsonl (giuria, K-103) | `time` | Δ |
| e8 | `impact` **[Δ A: era `area`]** | [nome di area], ordinata | decisioni | IMPACT/IMPATTO | `area` (str o lista) | brief, check-commits R2, bozza di D′ |
| e9 | `evidence` **[Δ A: era `cites`]** | [rif. di evidenza], ordinata | decisioni, opzioni | EVIDENCE/EVIDENZA | `cites` | Δ (E(D)), index |
| e10 | `options` | [etichetta] nell'ordine della fonte | decisioni | OPTIONS | `options` (A: una lista di oggetti; A unisce e10 a e12–e14 per etichetta) `options[].label` | brief |
| e11 | `chosen` | etichetta o NR | decisioni | CHOSE, opzione dell'OUTCOME | `chose` | bozza di D′ |
| e12 | `rejected` | {etichetta: ragione o NR} per ogni etichetta ≠ chosen | decisioni | REJECTED/SCARTATA | `options[].reason` | opzioni scartate nella sintesi |
| e13 | `text` **[Δ B: nuovo]** | str (il testo dell'opzione) o NR | opzioni | OPTIONS `(<etichetta>) <testo>` | `options[].text` | opzioni scartate nella sintesi |
| e14 | `evidence` dell'opzione | come e9 | opzioni | EVIDENCE `<loc>(<opz>)` | `options[].cites` | brief, index |
| e15 | `l0` **[Δ B: ora nel grafo]** | str, una riga, ≤ limite L0 in byte | decisioni | riga di `show --level 0` | `l0` | riga del membro nella sintesi |
| e16 | `l1` **[Δ B: ora nel grafo]** | str, ≤ 1200 B | decisioni | scheda di `show --level 1` | `l1` | pagina 1 della sintesi |
| e17 | `decision` | id | R | R DECISION | `realized.tsv` col 1 | `--realized` |
| e18 | `concern` | str | R | R CONCERN | `realized.tsv` col 2 | `--realized` |
| e19 | `hunks` | ["<qpath> <hunk_sha256\|BINARY> <intestazione>"] | R | R HUNK | `realized.tsv` col 4–6 | `--realized` |
| e20 | `lines` | ["<qpath> +\|- <sha256>"] | R | R LINE | — | (evidenza K-102) |
| e21 | `mode` | git \| nogit | R | R MODE | — | `--realized` (solo git) |
| e22 | `withdraws` | [id di R] | N | N WITHDRAWS | — | `--realized` scarta gli R ritirati |
Portati da B, non letti da A (elencati perché la tabella sia il nodo intero): `edges`, `rev` (coppie [arco, id], la tabella
chiusa degli archi di `f4/H-001/00-architetto/APPENDIX.md` §A), `superseded_by`, `question`, `rationale`, `by`,
`authority`, `delegated`, `source_status`, `history`, `subject`, `src`, `realization` (none, live, reverted, path-gone),
`live` (int), `label` (opzioni), `about`, `adds` (N).
**Ritirati dall'interfaccia [Δ A]:** `commits` e `concern` delle sole decisioni dello stub (i commit vengono dai trailer;
senza repository la sintesi legge i nodi R). A scrive la sua bozza di D′ (`plan.json` `dprime_draft`) con i nomi (e)
`question`, `chosen`, `rejected`, `supersedes`, `depends_on`, `impact`.

## 6. Il limite di pagina e la sua unità [Δ A, Δ B; decisione dell'utente 2]
`PAGE_MAX = 7276` **byte** di UTF-8, ogni LF compreso, per file di pagina: `p<n>.md` della sintesi di A, `PLAN.md`,
`PLAN_p<n>.md`, e ogni uscita di B che un agente è mandato a leggere per id (`show` livelli 0–1). 7276 B ≤ 4000 token al
peggior rapporto misurato di 1,819 B/token (cl100k; per Claude **non verificato**, classe 5). Anche tutti gli altri limiti
sono espressi in byte: L1 ≤ 1200 B **[Δ B: erano caratteri]**, il limite L0 in byte **[Δ B: erano «56 token» caratteri/4]**,
i limiti di riga di A già in byte. Una cifra in token può comparire solo come valore derivato con il suo rapporto. Leggere
tutto il raggio costa O(|Rad|) pagine, indipendente da N (criterio 3 del contratto). **Conseguenza per la fetta A:** i
limiti f4 (pagina 1 10428 B, pagina n 11916 B, PLAN 7820/11252 B) superano 7276 e vanno risommati; `PAGE_MAX = 12000` in
`crossroads_proto.py` r.13 è superato.

## 7. L'interfaccia per chi consuma (per la prossima estensione)
Chi consuma (l'ottimizzatore di contesto previsto, o qualunque strumento) legge incroci solo attraverso ciò che questa
sezione nomina, e scrive solo sotto la propria cartella di stato (per esempio `.sciame/context/`). Nient'altro è
un'interfaccia.
- **Id stabili:** §2. Un id non cambia mai; un handle è una chiave di visualizzazione, mai salvata.
- **Livelli:**
  - L0: una riga di `crossroads/view/INDEX.tsv`, al più 224 byte con il suo LF (campi: id, lifecycle, chosen,
    question; TAB, barra rovescia e LF protetti);
  - L1: la scheda di una decisione, al più 1200 byte con il suo LF, nel campo `l1` del suo nodo (e16), stampata anche
    da `incroci mostra ID --livello 1`;
  - L2: `incroci mostra ID --livello 2`, al più 7276 byte con il suo LF (il nodo intero è nel grafo).
- **Il registro delle modifiche:** `incroci modifiche --da-cursore SNAPSHOT_<sha12>` stampa gli id aggiunti, tolti,
  cambiati e quelli il cui stato è cambiato dopo quell'istantanea; i cursori stanno in `crossroads/log/` (restano gli
  ultimi 20). Un cursore sconosciuto esce con 1 e «full resync»: chi consuma rilegge allora `INDEX.tsv`.
- **Il grafo:** `crossroads/view/graph.jsonl`, formato (e) di §5.
- **Senza perdite, mai compressi né riscritti:** `crossroads/records/` (U, R, N) e le fonti dello sciame
  (convocazioni, giurie). Chi consuma non li modifica mai; una correzione è un nuovo record.
- **Sacrificabili e rigenerabili:** `crossroads/view/`, `crossroads/log/`, `crossroads/stage/` e ogni file derivato di
  chi consuma. `incroci deriva` li riscrive dai record, dalle fonti e da git.
- **Scritture:** chi consuma scrive solo sotto la propria cartella di stato.

## 8. Glossario (un significato per termine)
Il simbolo `R` indica solo il record di realizzazione; `D` e `D′` solo la decisione a monte e la sua inversione;
«token» solo un token di un modello; «holds» (vale) dice che una proprietà dichiarata è vera, mai che si è trovato un
difetto (quello è «difetto confermato»). `D` seguito da cifre non è mai un simbolo: compare solo dentro un id (`…#D1`) o
con un prefisso.

| # | termine | definizione |
|---|---|---|
| G1 | **D** | la decisione a monte di cui si prepara l'inversione: l'argomento di `radius`, `brief`, `plan` |
| G2 | **D′** | la nuova decisione che inverte D; sostituisce Rad(D)∖keep e dipende da depends_on(D)∖Rad |
| G3 | **Rad(D)**, il raggio | D più ogni decisione raggiungibile da D sugli archi `depends_on` rovesciati (BFS esatta) |
| G4 | **C_Rad** | i commit che realizzano membri di Rad∖keep, code delle catene di revert a profondità pari, dal più recente |
| G5 | **R**, record R | un record di realizzazione: file canonico `records/R-<hex12>.md`, tipo `realization`, §3.7 e §9 |
| G6 | **sha del blocco** (`hunk_sha256`) | l'hash di contenuto di §3.3, sotto il diff vincolato di §3.1 e §10 F-1 |
| G6b | **chiave / occorrenza del blocco** | (percorso, intestazione, sha del blocco) / lo stesso più commit e ordinale |
| G7 | **realizzata** | un commit realizza la decisione X quando il suo unico `Crossroads-Decision` è X ed è la coda di una catena di revert a profondità pari. «Ancora realizzata» significa realizzata |
| G8 | **live**, `live(X)` | presenza testuale: il numero degli atomi di riga `+` di X ancora nell'albero. Un'evidenza, e la regola solo senza git |
| G9 | **token** | un token di un modello, sotto un tokenizzatore nominato. Ogni limite è in byte; una cifra in token è derivata, con il suo rapporto |
| G10 | **voce di file** | un elemento della trama che registra la creazione o la cancellazione di un file |
| G11 | **holds** (vale) | una proprietà dichiarata del progetto è vera sull'insieme dichiarato: un invariante, un limite, una previsione detta come proprietà |
| G12 | **pagina**, **PAGE_MAX** | un file che un agente legge in una volta; al più 7276 byte di UTF-8 con ogni LF |
| G13 | **byte** | un ottetto della codifica UTF-8, LF compreso. L'unica unità di un limite di dimensione |
| G14 | **derivato** (classe di fonte) | un campo preso da un file che lo sciame già scrive. Le classi sono derivato, riga, record, NR |
| G15 | **dimensione della convocazione** | i byte dei file di una convocazione, il denominatore dei rapporti di costo |
| G16 | **decisione** | un nodo del grafo con `node_class` ∉ {container, option, record}; tipi user, jury, triage, selection |
| G17 | **record** | un file canonico immutabile `U-`/`R-`/`N-` + hex12; si corregge solo con un nuovo record che lo sostituisce o lo annota |
| G18 | **lifecycle** | lo stato derivato di un nodo (e4) |
| G19 | **evidenza** | i riferimenti su cui poggia una decisione o un'opzione (arco `rests_on`, campo e9) |
| G20 | **impatto** | le aree che una decisione tocca (e8) |
| G21 | **area** (concern) | una parte nominata del codice, definita in `crossroads/CONCERNS.md` da righe `CONCERN <nome> <glob>…` |
| G22 | **opzione scartata** | un'opzione della decisione diversa da `chosen`; la sua ragione è `rejected[etichetta]` |
| G23 | **Δ** («cambiato dopo») | i record che citano le evidenze di D o sostituiscono un membro del raggio, più tardi di D come istanti |
| G24 | **handle**, **indice di membro** | chiavi di visualizzazione nelle pagine: prefisso esadecimale `h(id)`, `m<k>`. Mai salvate come id |
| G25 | **id**, **ancora**, **locatore** | §2: il nome stabile / il prefisso del contenitore / la chiave nel file (`D\d…`, `H-\d{3}`, `select`) |
| G26 | **blocco / avviso / rilievo** | ritorno indietro: un blocco ferma plan o apply, un avviso no. derive: un rilievo è grave, di rapporto o informativo |
| G27 | **NR** | il letterale `not recorded`, per uno scalare che le fonti non danno; una lista è `[]` |
| G28 | **dimostrata / verificata / sostenuta / confutata / non risolta** | i cinque stati del preambolo dello sciame, regola 2 |
| G29 | etichette con prefisso | difetti del debugger `DBG-…`, decisioni di chiusura `CL-…`; i casi d'attacco tengono i loro nomi |

## 9. I corpi dei record
Il corpo di un record è UTF-8, LF, un `CHIAVE valore` per riga, chiavi nell'ordine qui sotto, una chiave multipla una
volta per valore con i valori ordinati; nessun CR, nessun BOM. L'id è la lettera del tipo, `-` e le prime 12 cifre
esadecimali dello sha256 dei byte del corpo; il file è `crossroads/records/<id>.md`, creato con O_EXCL e mai modificato.
- **U** (una decisione dell'utente; `incroci decidi`), chiavi in ordine: `KIND user`, `TIME <ISO 8601 con fuso>`,
  `BY <ruolo>`, `AUTHORITY owner|delegated:<rif>|…`, `QUESTION <testo>`, `OPTIONS (<etichetta>) <testo> | …`,
  `CHOSE (<etichetta>)`, `REJECTED (<etichetta>) <ragione>`… (o `REJECTED none`), `RATIONALE <testo>`,
  `IMPACT <area>…|none`, `EVIDENCE <rif>…|none`, `DEPENDS-ON <id>…|none` e, facoltativa, `SUPERSEDES <id>…`. Ogni
  chiave tranne SUPERSEDES è obbligatoria; CHOSE è una delle OPTIONS; un'etichetta di REJECTED è un'opzione non scelta.
  Multipla: REJECTED.
- **R** (una realizzazione; `incroci realizza`): `KIND realization`, `TIME`, `DECISION <id>`, `CONCERN <nome>`,
  `MODE git|nogit`, `HUNK <qpath> <hunk_sha256|BINARY> <intestazione>`…, `LINE <qpath> +|- <sha256>`… (§3.7).
  Multiple: HUNK, LINE.
- **N** (una nota; `incroci nota`): `KIND note`, `TIME`, `BY`, `ABOUT <id>`, `WITHDRAWS <id di R>`…, poi
  facoltative `QUESTION`, `REJECTED`…, `RATIONALE`, `IMPACT`, `EVIDENCE`. Multiple: WITHDRAWS, REJECTED. Una nota non
  porta né DEPENDS-ON né SUPERSEDES: una nota con l'una o l'altra è INVALID-RECORD e non aggiunge archi, così ogni arco
  del grafo che viene da un record viene dai byte di quel record. Una nota riempie solo un campo che la sua decisione
  ha lasciato NR, segnato «added later by N-…»; non sovrascrive mai un valore registrato: una correzione è un nuovo U
  che sostituisce.
Un record il cui nome di file non è lo sha256 dei suoi byte è messo in quarantena (INTEGRITY, grave); uno che viola una
regola qui sopra resta come INVALID-RECORD (di rapporto) con lifecycle invalid.

## 10. Emendamento F (2026-11-17)
Il verdetto di crossroads-r2 ha nominato sette mancanze. L'emendamento F risolve quelle di formato; ogni voce nomina la
prova di `tests/test_crossroads.py` che la controlla.
- **F-1 (K-501), il vincolo del file d'ordine.** Su git 2.53 il vincolo `-c diff.orderFile=` fa uscire con 128 `diff`,
  `log`, `show` e `fast-import` («failed to read orderfile ''»); solo `diff-tree` lo accetta. Il vincolo resta solo su
  `diff-tree`: la riga dei commit di §3.1 non cambia, byte per byte. La riga di realize diventa
  `diff --cached <FLAGS> -O/dev/null`, senza il vincolo, e `hunksha.staged()` fa lo stesso. Gli altri comandi git
  (`log`, `show`, `ls-tree`, `cat-file`, `fast-import`, `switch`) girano senza il vincolo e non stampano diff con sha.
  Prova: uscita 0, e la chiave del blocco in stage è uguale alla chiave `diff-tree` del commit fatto da quell'indice
  (`K-501`).
- **F-2 (K-502), cambio di tipo.** Un record grezzo con stato `T` è consumato con entrambe le sue sezioni di patch;
  record grezzi e sezioni di patch si accoppiano consumando le sezioni di ogni record, mai per posizione. Un cambio di
  tipo dà una voce `(percorso, "UNSUPPORTED", "UNSUPPORTED", 0)` e nessuno sha di blocco; così anche un gitlink (modo
  160000). Conseguenze: `realize` rifiuta con UNSUPPORTED (uscita 1, nulla scritto); la scansione dei commit di derive
  dà il rilievo informativo UNSUPPORTED; il piano di ritorno dà il blocco UNSUPPORTED, come prima. Prova: `K-502`.
- **F-3 (K-506), una regola degli scrittori.** Ogni dimensione di pagina conta l'LF finale. L2 accorcia le stringhe
  scalari lunghe dentro il JSON (dimezzando la più lunga) prima di accorciare mai il testo, così il recinto si chiude
  sempre (due righe di recinto). Ogni scrittore solleva un errore se una pagina supera 7276 byte. Prova: `K-506` (il
  caso da 7277 byte dà al più 7276 con due righe di recinto).
- **F-4 (K-505), il sigillo di una giuria.** L'ora di una decisione di giuria viene da una riga di SEALS.jsonl solo
  quando la riga nomina proprio il file OUTCOME (una riga relativa, contro la cartella del file SEALS) e il suo sha256 è
  lo sha256 dei byte attuali di quel file. Altrimenti l'ora è NR. Prova: `K-505` (uno sha sbagliato o una cartella con
  lo stesso nome sotto un altro genitore danno NR).
- **F-5 (K-102), «ancora realizzata».** Con git, «ancora realizzata» è G7: un commit il cui unico
  `Crossroads-Decision` è X e che è la coda di una catena di revert a profondità pari, con i revert completi
  riconosciuti come in A1 (la riga di git `This reverts commit <sha40>` o un trailer `Crossroads-Reverts`, gli stessi
  percorsi, blob o multinsiemi di righe scambiati). SUPERSEDED-STILL-REALIZED scatta su G7; `live` (G8) è stampato come
  evidenza; quando G7 e G8 non concordano su una decisione con record R, si dà il rilievo informativo LIVE-DISAGREES.
  Senza git la regola torna a G8. Costo: G7 si calcola solo per le decisioni il cui lifecycle è superseded o rejected,
  con un solo `git log` per i trailer e le righe di revert e il controllo di revert completo solo sui candidati. Prova:
  `K-102`.
- **F-6 (K-507), insiemi di archi.** CYCLE corre su `depends_on ∪ supersedes`. Il raggio corre solo su `depends_on`
  (e5); non usa mai `rests_on` né le note. Prova: `K-507`.
- **F-7, voci minori.** `stage` rifiuta ogni percorso con una componente `.git`, oltre alla radice, alla cartella di
  stato e ai percorsi fuori dalla radice. Una convocazione o una giuria trovata sotto la profondità di lettura (fino a
  tre livelli) dà il rilievo di rapporto SOURCE-SKIPPED, mai il silenzio. Prove: `B4 stage`, `F-7 SOURCE-SKIPPED`.
