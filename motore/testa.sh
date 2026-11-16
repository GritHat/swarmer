#!/usr/bin/env bash
#: SCIAME DI AGENTI PER CLAUDE CODE, versione 4.0 — AGENT SWARM FOR CLAUDE CODE, version 4.0
#:
#: Un file solo: i documenti, il database dei professionisti e il motore dello sciame, più i comandi per installarlo e
#: convocarlo. / One file: the swarm's documents, its database of professionals and its engine, plus the commands to
#: install and convene it.
#:
#: Serve / Needs: bash, python3 >= 3.8 (solo libreria standard / standard library only), Claude Code (`claude`).
#:
#:   bash sciame.sh installa [--lingua it|en] [--istruzioni] [--forza] [--cartella DIR] [--locale DIR]
#:   bash sciame/sciame.sh <singolo|ventaglio|classica|giuria|completa|plenaria|esperto|auto> "richiesta"
#:   bash sciame/sciame.sh aiuto            # tutti i comandi, nella lingua scelta / every command, in the chosen language
#:
#: English command names work too: install, help, language, single, fan-out, classic, jury, full, plenary, expert.

set -euo pipefail

QUESTO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)/$(basename "${BASH_SOURCE[0]}")"

errore() { printf 'sciame: %s\n' "$*" >&2; exit 1; }

serve_python() {
    command -v python3 >/dev/null 2>&1 || errore "manca python3 / python3 is missing (>= 3.8)"
    python3 -I -B -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' \
        || errore "python3 è troppo vecchio / python3 is too old: >= 3.8"
}

# I file che stanno in fondo a questo file, in una cartella. / The files at the end of this file, into a folder.
estrai() {
    # Un nome di file è relativo, senza «..», senza componenti vuoti: altrimenti l'estrazione si ferma (codice 2).
    awk -v dest="$1" '
        /^#==== sciame\.sh: file [A-Za-z0-9_.\/-]+ ====$/ {
            if (out) close(out)
            nome = $4
            if (nome ~ /^\// || nome ~ /(^|\/)\.\.(\/|$)/ || nome ~ /\/\// || (nome in visti)) { cattivo = nome; exit 2 }
            visti[nome] = 1
            out = dest "/" nome
            d = out; sub(/\/[^\/]*$/, "", d); system("mkdir -p \"" d "\"")
            printf "" > out; next }
        /^#==== sciame\.sh: fine dei file ====$/ { if (out) close(out); out = ""; next }
        out { print > out }
        END { if (cattivo != "") { print "sciame: nome di file non ammesso: " cattivo > "/dev/stderr"; exit 2 } }
    ' "$QUESTO" || errore "sciame.sh contiene un nome di file non ammesso / an unsafe file name: non lo installo"
    [ -f "$1/motore/sciame.py" ] && [ -f "$1/db/professionisti.json" ] \
        || errore "questo file è incompleto / this file is incomplete: scaricalo di nuovo / download it again"
}

# La cartella dello sciame da config.json, validata: relativa, senza «..», diversa da «.».
cartella_da_config() {
    local f="$1/.sciame/config.json"
    [ -f "$f" ] && [ ! -L "$f" ] || { printf 'sciame'; return; }
    python3 -I -B -c '
import json, os, sys
c = json.load(open(sys.argv[1])).get("cartella", "sciame")
parti = c.split("/")
if not c or os.path.isabs(c) or ".." in parti or c in (".", "./") or "" in parti:
    sys.exit("sciame: cartella non ammessa in .sciame/config.json: %r" % c)
print(c, end="")' "$f"
}

# La cartella dello sciame: quella di questo file se è una copia installata (RADICE e FABBRICA.json accanto),
# altrimenti quella di .sciame/config.json del progetto, altrimenti <progetto>/sciame.
trova() {
    local qui; qui="$(dirname "$QUESTO")"
    if [ -n "${RADICE:-}" ]; then
        RADICE="$(cd "$RADICE" && pwd -P)"
        [ -n "${CARTELLA:-}" ] || CARTELLA="$(cartella_da_config "$RADICE")" || exit 1
    elif [ -f "$qui/RADICE" ] && [ -f "$qui/FABBRICA.json" ] && [ -f "$qui/motore/sciame.py" ]; then
        RADICE="$(cd "$qui/$(cat "$qui/RADICE")" && pwd -P)"
        CARTELLA="$(python3 -I -B -c 'import os,sys; print(os.path.relpath(sys.argv[1], sys.argv[2]))' "$qui" "$RADICE")"
    else
        RADICE="$PWD"
        [ -n "${CARTELLA:-}" ] || CARTELLA="$(cartella_da_config "$RADICE")" || exit 1
    fi
}

installa() {
    serve_python
    if [ "$RADICE" = "/" ] || [ "$RADICE" = "$(cd "${HOME:-/}" && pwd -P)" ]; then
        errore "$RADICE non sembra un progetto / does not look like a project: -C CARTELLA installa"
    fi
    local args=()
    while [ $# -gt 0 ]; do
        case "$1" in
            --cartella|--folder) CARTELLA="${2%/}"; shift 2 ;;
            --lingua|--language) args+=(--lingua "$2"); shift 2 ;;
            --locale|--local) args+=(--locale "$2"); shift 2 ;;
            --istruzioni|--instructions) args+=(--istruzioni); shift ;;
            --forza|--force) args+=(--forza); shift ;;
            --gestiti-dal-progetto|--project-managed) args+=(--gestiti-dal-progetto); shift ;;
            *) errore "installa: opzione sconosciuta / unknown option: $1" ;;
        esac
    done
    SCIAME_TMP="$(mktemp -d)"
    trap 'rm -rf "${SCIAME_TMP:-}"' EXIT
    estrai "$SCIAME_TMP"
    cp "$QUESTO" "$SCIAME_TMP/sciame.sh"
    python3 -I -B "$SCIAME_TMP/motore/sciame.py" installa --da "$SCIAME_TMP" --radice "$RADICE" --cartella "$CARTELLA" ${args[@]+"${args[@]}"}
}

principale() {
    RADICE=""
    CARTELLA=""   # mai dall'ambiente: la cartella viene da --cartella, dalla copia installata o da .sciame/config.json
    if [ "${1:-}" = "-C" ]; then
        [ $# -ge 2 ] || errore "-C vuole una cartella / -C wants a folder"
        RADICE="$2"; shift 2
    fi
    local comando="${1:-aiuto}"
    [ $# -eq 0 ] || shift
    case "$comando" in
        install) comando=installa ;; help|-h|--help) comando=aiuto ;; language) comando=lingua ;;
        single) comando=singolo ;; fan-out|fanout) comando=ventaglio ;; classic) comando=classica ;;
        jury) comando=giuria ;; light-jury) comando=giuria-leggera ;; full) comando=completa ;; plenary) comando=plenaria ;; expert) comando=esperto ;;
        roles) comando=ruoli ;; professionals) comando=professionisti ;; check) comando=controlla ;;
        regenerate) comando=rigenera ;; remove) comando=rimuovi ;; instructions) comando=istruzioni ;;
        models) comando=modelli ;; requests) comando=richieste ;; count) comando=conta ;; approve) comando=approva ;;
        propose) comando=proponi ;; build) comando=costruisci ;; verify) comando=verifica ;; tests) comando=prove ;;
        update) comando=aggiorna ;; import-cards) comando=importa-schede ;;
    esac
    trova
    case "$comando" in
        aiuto)
            sed -n 's/^#: \{0,1\}//p' "$QUESTO"
            if [ -f "$RADICE/$CARTELLA/motore/sciame.py" ]; then
                local l="it"; [ -f "$RADICE/$CARTELLA/LINGUA" ] && l="$(head -c 8 "$RADICE/$CARTELLA/LINGUA" | tr -d '\n')"
                case "$l" in [a-z][a-z]) ;; *) l="it" ;; esac
                [ -f "$RADICE/$CARTELLA/documenti/$l/_AIUTO.txt" ] && cat "$RADICE/$CARTELLA/documenti/$l/_AIUTO.txt"
            fi ;;
        installa) installa "$@" ;;
        aggiorna)
            # Con i file di questo sciame.sh, senza toccare quelli modificati nel progetto (vanno accanto, .nuovo).
            installa "$@" ;;
        prove)
            serve_python
            [ -f "$RADICE/$CARTELLA/motore/sciame.py" ] || errore "sciame non installato / not installed"
            local rc=0
            for p in "$RADICE/$CARTELLA"/prove/prova_*.py; do python3 -I -B "$p" || rc=1; done
            exit "$rc" ;;
        *)
            serve_python
            [ -f "$RADICE/$CARTELLA/motore/sciame.py" ] \
                || errore "in $RADICE lo sciame non c'è ancora / is not installed yet: bash sciame.sh installa"
            exec python3 -I -B "$RADICE/$CARTELLA/motore/sciame.py" --sciame "$RADICE/$CARTELLA" "$comando" "$@" ;;
    esac
}

principale "$@"
