# sciame-incroci 1.0: le decisioni del progetto come grafo, e la strada per tornare indietro

incroci (in inglese crossroads) è un'estensione dello sciame (5.2 o successiva). Registra le decisioni dell'utente,
dello sciame (triage, selezione) e delle giurie come un grafo navigabile, con le opzioni scartate e le ragioni, la
motivazione, l'impatto, le evidenze e le dipendenze. Lega ogni decisione ai commit che la realizzano, un'area per
commit. Quando il progetto è bloccato, trova la decisione a monte D, ne dà la sintesi in pagine limitate e pianifica
la sua inversione su un ramo nuovo, senza ricostruire il contesto. I formati sono in `FORMATI_INCROCI.md`; la skill
`sciame-incroci` dice all'agente quando usare ogni comando.

## Attivarla
`bash sciame/sciame.sh estensioni --aggiungi incroci` (in inglese `extensions --add crossroads`) scrive la chiave
`estensioni` di `.sciame/config.json` e rigenera: la skill `sciame-incroci` compare in ogni destinazione attiva e ogni
skill di strategia riceve il blocco del coordinatore qui sotto. `estensioni --togli incroci` le toglie di nuovo; il
deposito `.sciame/incroci/` resta, perché è del progetto.

## Il deposito
`.sciame/incroci/` (in inglese `.swarmer/crossroads/`):
- `records/`: i record canonici, immutabili e indirizzati dal contenuto: `U-…` (una decisione dell'utente), `R-…`
  (una realizzazione: i blocchi di modifica di una decisione in un'area), `N-…` (una nota). Mettili in un commit a parte;
- `view/`: derivata e sacrificabile: `graph.jsonl` (formato (e)), `INDEX.tsv` (una riga L0 per nodo), `REPORT.md` (una
  pagina: i rilievi gravi e di rapporto, quelli informativi contati), `REPORT.tsv` (ogni rilievo), `realized.tsv` (una riga per blocco realizzato), e i file di sintesi, piano e indice del ritorno indietro;
- `log/`: le istantanee del grafo (le ultime 20) e l'elenco di ogni record mai visto;
- `stage/`: le immagini «prima» del modo senza git;
- `CONCERNS.md`, facoltativo, scritto dal progetto: righe `CONCERN <nome> <glob>…`.
`view/`, `log/` e `stage/` sono ignorati da git grazie al `.gitignore` che incroci scrive nel deposito. I nomi interni
del deposito restano quelli canonici in ogni lingua: sono un formato di dati, come le chiavi dei record.

## I comandi
`bash sciame/sciame.sh incroci <comando>` (in inglese `crossroads`). Codici d'uscita: 0 ok, 1 errore o blocco,
2 rilievi, piano scaduto o prova a vuoto. I comandi che leggono la vista la derivano di nuovo prima, se manca o è scaduta.

| comando | inglese | fa |
|---|---|---|
| `deriva [--sorgente DIR]… [--git auto\|yes\|no] [--rigoroso] [-v]` | `derive` | scrive `view/` e `log/`; stampa l'istantanea e i rilievi che non sono informativi |
| `controlla [--inverti ID,…]` | `check` | stampa ogni rilievo, non scrive nulla |
| `decidi --domanda D --opzioni "(a) t \| (b) t" --scelta a --motivazione T [--scarta "(b) ragione"]… [--impatto "a…"] [--evidenza "id-o-rif…"] [--richiede "id…"] [--sostituisce "id…"] [--autorita owner\|delegated:<rif>]` | `decide` | scrive un record U, ne stampa l'id; `--evidenza` vuole id o riferimenti `<ancora>/<percorso>[@sha12]` separati da spazi, non testo libero (una parola semplice dà un avviso: sarebbe DANGLING) |
| `nota --riguarda ID [--motivazione T] [--scarta "(b) r"]… [--ritira R-…]…` | `note` | scrive un record N |
| `prepara FILE…` | `stage` | senza git: le immagini «prima», prima di modificare |
| `realizza ID --area C [--modo auto\|git\|nogit]` | `realize` | scrive un record R dal diff in stage (git) o dallo stage (senza git) |
| `trailer ID AREA` | `trailers` | stampa le due righe di trailer del commit; non fa mai commit |
| `mostra ID\|HANDLE [--livello 0\|1\|2]` | `show` | la riga L0, la scheda L1 o la pagina L2 di un nodo |
| `modifiche --da-cursore SNAPSHOT_<sha12>` | `changes` | ciò che è cambiato dopo un'istantanea |
| `lint FILE… [--lessico]` | `lint` | le righe di protocollo quasi giuste; FOREIGN-H in un triage o in una selezione |
| `raggio ID` | `radius` | Rad(ID) |
| `sintesi ID` | `brief` | la sintesi a pagine `view/brief/<h>/p<n>.md` (ogni pagina ≤ 7276 B) |
| `piano ID [--mantieni X…] [--margine N]` | `plan` | il piano in sola lettura `view/plan/<h>/PLAN.md` e `plan.json`, con la bozza di D′ e il comando `decidi` per registrarla |
| `applica PLAN.json --nuova ID [--prove CMD] [--esegui]` | `apply` | senza `--esegui` una prova a vuoto (uscita 2); con esso, dopo il sì dell'utente, il ramo `crossroads/<h12(D′)>` |
| `verifica PLAN.json --nuova ID [--prove CMD]` | `verify` | I1–I3 bloccanti; I4, I5 e le prove riferiti: OK, OK-BROKEN o FAILED |
| `controlla-commit INTERVALLO` | `check-commits` | le regole dei trailer: una decisione e un'area per commit, aree, revert semplici, TRAILER-MISMATCH |

## Le righe di protocollo
In un triage (`TRIAGE.md`), in una selezione (`SELEZIONE.md`, `SELECTION.md`), in una proposta di giuria
(`PROPOSTA.md`, `PROPOSAL.md`) e nel file a fianco `INCROCI.md` (in inglese `CROSSROADS.md`) accanto a un triage o a
una selezione, alla colonna 0 e fuori dai blocchi ```, scritte prima del sigillo o mai (una riga tardiva è una nota):
```
QUESTION|DOMANDA <loc> <testo>           RATIONALE|MOTIVAZIONE <loc> <testo>
REJECTED|SCARTATA <loc> (<etichetta>) <ragione>
EVIDENCE|EVIDENZA <loc>[(<etichetta>)] <rif>…   IMPACT|IMPATTO <loc> <area>…
DEPENDS-ON|RICHIEDE <loc> <id>…          SUPERSEDES|SOSTITUISCE <loc> <id>…
TRIAGE H-### TEST|REFORMULATE|OPEN|REFUTED (TESTARE/PROVA, RIFORMULARE, APERTA, SMENTITA/CONFUTATA) [testo]
loc = D<cifra>… | H-### | select
```
`DIPENDE-DA` non è mai letto. Le righe sono invisibili a `jury count`. Una riga di un triage o di una selezione che
nomina un H# di un'altra convocazione va nel file a fianco, che convoca.py non legge (altrimenti FOREIGN-H).

<!-- coordinator -->
**incroci è attivo in questo progetto** (`bash sciame/sciame.sh incroci …`, skill `sciame-incroci`).
- Nel mandato dell'arbitro del triage, dell'arbitro della selezione e del relatore di una giuria, incolla le righe di
  protocollo qui sotto e chiedi, per ogni decisione, la domanda, le opzioni scartate con le ragioni, l'impatto, le
  evidenze e ciò da cui dipende:
  `DOMANDA <loc> <testo>` · `SCARTATA <loc> (<etichetta>) <ragione>` · `MOTIVAZIONE <loc> <testo>` ·
  `IMPATTO <loc> <area>…` · `EVIDENZA <loc>[(<etichetta>)] <rif>…` · `RICHIEDE <loc> <id>…` ·
  `SOSTITUISCE <loc> <id>…` · `TRIAGE H-### TESTARE|RIFORMULARE|APERTA|SMENTITA [testo]` (`loc` = `D1…`, `H-###`,
  select; colonna 0, fuori dai blocchi di codice; un H# di un'altra convocazione va in `INCROCI.md` accanto al file).
- Prima di sigillare quei file esegui `incroci lint FILE…` e correggi ogni NEAR-MISS e FOREIGN-H.
- Dopo ogni sigillo di una fase o di un esito di giuria, e prima di rispondere all'utente, esegui `incroci deriva` e
  leggi i rilievi gravi di `view/REPORT.md`.
- Registra ogni risposta dell'utente a una domanda di decisione con `incroci decidi` (con `--sostituisce` quando
  sostituisce una scelta precedente).
<!-- /coordinator -->

## Commit per area
Un commit porta una decisione e un'area. Metti in stage le modifiche di una decisione in un'area, esegui
`realizza ID --area C`, poi `trailer ID C`, e proponi all'utente il `git commit` con quelle due righe di trailer:
l'utente lo esegue, o approva un comando esplicito. Poi `controlla-commit <intervallo>`: un commit senza trailer che
tocca solo il deposito (il commit dei record) non è segnalato; ogni altro commit senza trailer è R1. Lo sciame non fa
mai commit.

## La strada per tornare indietro
`mostra` o `view/INDEX.tsv` trova D; `raggio D` e `sintesi D` danno il raggio e la pagina 1 (la scheda L1 di D, le sue
opzioni scartate con le ragioni, ciò che è cambiato dopo, i membri); `piano D` dà i commit, i blocchi e la bozza di
D′. L'utente sceglie; `decidi … --sostituisce` registra D′; `applica plan.json --nuova D′` è una prova a vuoto, e
`--esegui` (solo dopo il sì esplicito dell'utente) scrive un commit per ogni commit di C_Rad su un ramo nuovo con un
solo `git fast-import`: HEAD, il ramo corrente e l'albero di lavoro cambiano solo alla fine (`git switch`). I commit
nuovi portano l'identità git dell'utente (`user.name`, `user.email`) e l'ora corrente; senza un'identità `applica`
rifiuta. `verifica` lo controlla: I1 protegge i file (nessun percorso fuori dai file del piano cambia), I2 le righe (ogni
file del piano è uguale alla trama, quindi le righe delle decisioni esterne nei file del raggio restano), I3 i trailer.
OK significa sicuro sui byte, OK-BROKEN che le prove falliscono.

## Limiti
- **Merge:** un merge nell'intervallo è un arresto (NONLINEAR). I commit di merge sono saltati dalla scansione dei
  commit; un blocco risolto dentro un merge è R-UNMATCHED.
- **Rinomine:** nessuna è seguita (`--no-renames`). Gli arresti sicuri sono REALIZATION-PATH-GONE, le copie con
  modifiche (RN1) e uno squash marcato con una sola decisione senza record di realizzazione (M2b).
- **Non supportati:** un cambio di tipo, un collegamento simbolico (modo 120000) o un gitlink (modo 160000) su un
  percorso del raggio è UNSUPPORTED; `realizza` li rifiuta.
- **Filesystem che non distinguono maiuscole:** CASE-COLLISION blocca due percorsi tracciati che differiscono solo per
  le maiuscole; non è verificato su APFS né su NTFS.
- **«OK» significa sicuro sui byte, non sul comportamento.** Il raggio è quello dichiarato: una dipendenza che nessuno
  ha dichiarato è colta solo dalle prove (OK-BROKEN). I4 e MISSING-DEPENDS sono euristiche.
- **Limite di pagina:** 7276 byte per pagina, che garantisce al più 7276 token. «Al più 4000 token» vale solo al
  rapporto misurato di 1,819 byte per token (cl100k) e non è verificato per Claude. La taratura del tokenizzatore di
  Claude e l'influenza delle righe sui giurati (i giurati le leggono) sono fuori ambito: richiedono il sì dell'utente
  per mandare dati a terzi.
- **Id:** gli id da 48 bit proteggono solo da modifiche accidentali. `log/` è sacrificabile, quindi RECORD-VANISHED
  richiede che `log/` sopravviva. Un TIME retrodatato non è rilevato.
- **Non costruiti:** nessuna esportazione Mermaid o HTML, nessun editor di CONCERNS, nessun motore a revert, nessuna
  modifica del motore dello sciame oltre al meccanismo delle estensioni (quella è una modifica a parte).
- **Commit:** lo sciame non fa mai commit, merge né push; `applica --esegui` crea solo un ramo, dopo un sì esplicito.
- **La prima inversione di un agente:** se un agente nuovo, con solo il testo del guasto, la skill e l'aiuto, trova D e
  pianifica l'inversione entro il limite di pagina resta non risolto finché non si fa la prova descritta da
  `--make-fixture` delle prove, con il sì dell'utente.
