---
name: swarmer-install
description: "Installs (or updates) the swarmer agent swarm into the current project: role agents, the convening skills and the swarm documents. Also updates a 4.0 installation (sciame) in place. Use it only when the user asks to install, update or set up the swarm."
argument-hint: "[en|it] [--instructions] [--folder DIR --local DIR --project-managed]"
disable-model-invocation: true
---

# Install the swarm

1. The plugin folder is `${CLAUDE_PLUGIN_ROOT}` (the folder that holds `skills/` and `swarmer.sh`).
2. Read the arguments: a bare `en` or `it` is the language; the other options are passed as they are.
3. Look for an existing installation in the project root: a folder (by default `swarmer/` or `sciame/`, or the one
   named in `.swarmer/config.json` or `.sciame/config.json`) that holds `FACTORY.json` or `FABBRICA.json`.
   - **None:** run, in the project root (each argument quoted on its own; the language defaults to `en`):

     ```
     bash "${CLAUDE_PLUGIN_ROOT}/swarmer.sh" -C "$PWD" install --language "<en|it>" [the other options]
     ```

   - **One found** (also a 4.0 installation, which is migrated): run `update` instead of `install`, and pass
     `--language` only if the user gave a language, so that the installation keeps its own:

     ```
     bash "${CLAUDE_PLUGIN_ROOT}/swarmer.sh" -C "$PWD" update [--language "<en|it>"] [the other options]
     ```

     Report the files the updater lists as left in place because modified in the project, and its note on
     `CLAUDE.md`; going back to 4.0 is not supported.

   If the project already has a `swarmer/` folder that is not this swarm, the installer refuses and changes nothing:
   tell the user, and suggest `--folder swarmer/skill --local swarmer --project-managed`, which installs the swarm
   next to it and takes the project's cards as local overrides.
4. Run `bash <folder>/swarmer.sh check` and report the result. If it lists translations pending (roles of the public
   database without the language of the installation, generated from English with the mark `translation-pending`),
   say that the coordinator translates each of them the first time it convenes it; nothing has to be done now. Tell the user that the new agents and skills become
   visible after reopening the Claude Code session, and that `bash <folder>/swarmer.sh help` lists every command.

Never commit, never publish, and never touch files of the project outside what the installer writes.
