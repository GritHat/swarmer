# sciame — uno sciame di agenti per Claude Code

*[English](README.md)*

**sciame** è una squadra di agenti specialistici per Claude Code che un coordinatore convoca per una richiesta, con
una di otto strategie. I ruoli sono **professionisti** (le competenze generali) e **sottoprofessionisti** (le loro
specializzazioni), in un database unico in tutte le lingue della skill. Tutta la skill (documenti, database e
motore) sta in un file solo, `sciame.sh`, con la sola bash e la libreria standard di Python.

## Installare

```
# un file solo, in qualunque progetto
curl -fsSLO https://raw.githubusercontent.com/GritHat/swarmer/main/sciame.sh
bash sciame.sh installa --lingua it          # oppure --lingua en

# oppure come plugin di Claude Code
/plugin marketplace add GritHat/swarmer
/plugin install sciame
/sciame-installa it
```

Poi riapri la sessione di Claude Code e convoca lo sciame:

| strategia | skill | per | agenti |
|---|---|---|---|
| singolo | `/sciame-singolo` | una domanda chiara di un campo | 1 |
| ventaglio | `/sciame-ventaglio` | un lavoro divisibile in fette parallele, o una gara con la regola di scelta dichiarata prima | 2–16 |
| classica | `/sciame-classica` | decidere, progettare, correggere, dimostrare, misurare: corsie cieche, triage, torneo dei falsificatori, rami, verdetti | 6–15 |
| giuria | `/sciame-giuria` | decidere una proposta istruita: il consenso approva, la maggioranza rivede (al più 3 giri, senza regressioni), la minoranza respinge | 7–11 |
| giuria leggera | `/sciame-giuria-leggera` | decisioni piccole e poco influenti, o dove una prova veloce scopre l'errore: tre giurati, prova prima del voto, un giro, poi la giuria ordinaria | 5 |
| completa | `/sciame-completa` | domande strategiche o aperte: tutti i professionisti, ciechi, senza voto, poi una classica | tutti + classica |
| plenaria | `/sciame-plenaria` | passaggi di fase e scelte enormemente importanti: completa, convocazione usuale, passata critica, due arbitri, voto finale | 60–80 e oltre |
| esperto | `/sciame-esperto` | una competenza che manca: scheda provvisoria, richiesta registrata, ruolo creato alla soglia | 1 |
| auto | `/sciame` | sceglie il coordinatore la strategia più economica che basta, e lo dice | — |

Dalla shell: `bash sciame/sciame.sh <strategia> "richiesta"`; `bash sciame/sciame.sh aiuto` elenca tutti i comandi.

## Che cosa la distingue

- **Ogni consegna basta da sola**: scopo e criterio di fatto, ingressi, spazio di scrittura e spazio vietato, la
  verifica da eseguire, e una risposta che comincia con FATTO, PROBLEMI o BLOCCATO. I rapporti degli agenti sono
  evidenze, non prove: il coordinatore riesegue i controlli promessi sul risultato integrato.
- **Le decisioni sono verificabili**: i voti delle giurie sono sigillati (sha256), ciechi, ricontati dai file da
  `giuria.py`, con una clausola dell'obiettivo (bersaglio, catena, controfattuale, costo) che ogni proposta deve
  passare.
- **Lo sciame cresce quando serve**: le competenze mancanti si chiedono con un motivo; tre richiedenti in una
  convocazione, o tre richieste in due convocazioni, fanno un professionista nuovo, che entra nel database, negli
  agenti e in `sciame.sh`.
- **Gli override locali**: le schede proprie di un progetto stanno in `sciame/locale/`, hanno sempre la priorità sui
  ruoli generici, possono contenere i dettagli privati del progetto e non si pubblicano mai.
- **Onesto sull'ambiente**: senza sottoagenti, shell o scritture, il coordinatore tiene le fasi e dice che cosa si è
  ridotto (`AMBIENTE.md`).

## Lingue

Italiano e inglese. Si cambia con `bash sciame/sciame.sh lingua it` (agenti, skill e documenti si rigenerano), o per
una convocazione con `lingua=it`. Le lingue nuove si propongono con una pull request: vedi
[CONTRIBUTING.it.md](CONTRIBUTING.it.md).

## Proporre un professionista nuovo

Apri una pull request che aggiunge una voce a `db/professionisti.json`, con i testi in tutte le lingue del repository
(modello: `.github/PULL_REQUEST_TEMPLATE/nuovo_professionista.md`), oppure da un progetto con lo sciame installato:
`bash sciame/sciame.sh approva scheda.json` e poi `bash sciame/sciame.sh proponi <sigla> --invia`.

Licenza: MIT.
