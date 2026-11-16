---
name: sciame-installa
description: "Installa (o aggiorna) lo sciame di agenti (swarmer) nel progetto corrente, per Claude Code, Codex, Antigravity, Gemini CLI o ogni strumento che legge AGENTS.md e le Agent Skills: gli agenti dei ruoli, le skill di convocazione e i documenti dello sciame. Aggiorna sul posto anche un'installazione 4.0. Usala solo quando l'utente chiede di installare, aggiornare o predisporre lo sciame. Alias italiano di swarmer-install."
argument-hint: "[it|en] [--destinazioni claude,codex,antigravity,gemini,agents] [--istruzioni] [--cartella DIR --locale DIR --gestiti-dal-progetto]"
disable-model-invocation: true
---

# Installare lo sciame

1. `<repo>` è la cartella che contiene `skills/` e `swarmer.sh`: in Claude Code, come plugin, `${CLAUDE_PLUGIN_ROOT}`;
   in un altro strumento, la cartella due livelli sopra questo `SKILL.md`. Se manca, scarica il file unico:
   `curl -fsSLO https://raw.githubusercontent.com/GritHat/swarmer/main/sciame.sh` e usa `bash sciame.sh`.
2. Leggi gli argomenti: un `it` o un `en` da solo è la lingua; le altre opzioni si passano così come sono. Senza
   `--destinazioni` un'installazione nuova genera per gli strumenti che trova nel progetto (`.claude/`, `.codex/`,
   `.gemini/`, `.agents/`, `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`), più lo standard aperto; se l'utente nomina lo
   strumento in uso, passalo (`--destinazioni codex`, …).
3. Cerca un'installazione già presente alla radice del progetto: una cartella (di solito `sciame/` o `swarmer/`, oppure
   quella indicata in `.sciame/config.json` o `.swarmer/config.json`) che contiene `FABBRICA.json` o `FACTORY.json`.
   - **Nessuna:** lancia, alla radice del progetto (ogni argomento fra virgolette a sé; la lingua, se manca, è `it`):

     ```
     bash "<repo>/swarmer.sh" -C "$PWD" installa --lingua "<it|en>" [le altre opzioni]
     ```

   - **Una trovata** (anche un'installazione 4.0, che si migra): lancia `aggiorna` al posto di `installa`, e passa
     `--lingua` solo se l'utente ne ha data una, così l'installazione tiene la sua:

     ```
     bash "<repo>/swarmer.sh" -C "$PWD" aggiorna [--lingua "<it|en>"] [le altre opzioni]
     ```

     Riferisci i file che l'aggiornamento elenca come lasciati al loro posto perché modificati nel progetto, e la sua
     nota su `CLAUDE.md`; il ritorno alla 4.0 non è supportato.

   Se il progetto ha già una cartella `sciame/` che non è questo sciame, l'installatore rifiuta e non cambia niente:
   dillo all'utente, e suggerisci `--cartella sciame/skill --locale sciame --gestiti-dal-progetto`, che installa lo
   sciame accanto e prende le schede del progetto come override locali.
4. Lancia `bash <cartella>/swarmer.sh controlla` e riferisci l'esito. Se elenca traduzioni in attesa (ruoli del
   database pubblico senza la lingua dell'installazione, generati dall'inglese con il segno `translation-pending`), di'
   che il coordinatore traduce ciascuno la prima volta che lo convoca; adesso non serve fare niente. Riferisci le destinazioni che elenca. Di' all'utente che gli
   agenti e le skill nuovi si vedono dopo aver riaperto la sessione dell'agente di programmazione, che
   `bash <cartella>/swarmer.sh destinazioni` mostra e cambia gli strumenti, e che `bash <cartella>/swarmer.sh aiuto` elenca tutti i comandi
   (in un'installazione italiana vale anche `sciame.sh`).

Non fare commit, non pubblicare niente e non toccare file del progetto oltre a quelli che scrive l'installatore.
