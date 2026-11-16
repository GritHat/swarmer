---
name: sciame-installa
description: "Installs (or updates) the sciame agent swarm into the current project: role agents, the convening skills and the swarm documents. Use it only when the user asks to install, update or set up the swarm. / Installa o aggiorna lo sciame di agenti nel progetto corrente."
argument-hint: "[it|en] [--istruzioni] [--cartella DIR --locale DIR --gestiti-dal-progetto]"
disable-model-invocation: true
---

# Install the swarm / Installare lo sciame

1. The plugin folder is `${CLAUDE_PLUGIN_ROOT}` (the folder that holds `skills/` and `sciame.sh`).
2. Read the arguments: a bare `it` or `en` is the language (default: the language of the conversation); the other
   options are passed as they are. Then, in the project root, run (each argument quoted on its own):

   ```
   bash "${CLAUDE_PLUGIN_ROOT}/sciame.sh" -C "$PWD" installa --lingua "<it|en>" [the other options]
   ```

   If the project already has a `sciame/` folder that is not this swarm, the installer refuses and changes nothing:
   tell the user, and suggest `--cartella sciame/skill --locale sciame --gestiti-dal-progetto`, which installs the
   swarm next to it and takes the project's cards as local overrides.
3. Run `bash <folder>/sciame.sh controlla` and report the result. Tell the user that the new agents and skills become
   visible after reopening the Claude Code session, and that `bash <folder>/sciame.sh aiuto` lists every command.

Never commit, never publish, and never touch files of the project outside what the installer writes.
