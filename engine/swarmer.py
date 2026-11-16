#!/usr/bin/env python3
"""swarmer 5.1: the command line. Usually run as `bash swarmer/swarmer.sh <command>`; `help` says everything.

Standard library only. It launches no agent: it starts the coding agent of the project (Claude Code, Codex,
Antigravity or Gemini CLI) with the skill of the strategy, or prepares,
counts and checks. Actions towards the outside (a pull request) happen only on an explicit, confirmed command, and
never with the local files. No write follows a symbolic link, and no file of the project that is not the swarm's is
overwritten (paths.py). Commands, options and values have aliases in every language of i18n/ (aliases.py).
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent          # <swarm>/engine
SWARM = HERE.parent                             # the swarm folder in the project (or the repository)
sys.path.insert(0, str(HERE))
import aliases as A  # noqa: E402
import compat as C  # noqa: E402
import generate as G  # noqa: E402
import paths as S  # noqa: E402
import professionals as P  # noqa: E402

DISTRIBUTED = ("engine", "db", "docs", "i18n", "wrappers", "tests")   # what swarmer.sh carries
NOT_DISTRIBUTED = ("tests/fixtures/",)
ID_ARG = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
ROOT_WRAPPERS = {"convene.py": "wrappers/convene.py", "jury.py": "wrappers/jury.py",
                 "generate_agents.py": "engine/generate_agents.py"}
HEAD = "engine/head.sh"
BLOCK_BEGIN, BLOCK_END = "# @aliases-begin\n", "# @aliases-end\n"
BASH_COMMANDS = ("install", "update", "help", "tests")
INSTALL_OPTIONS = ("--folder", "--language", "--local", "--instructions", "--force", "--project-managed", "--targets")
STATE = tuple(C.STATE_NAMES)   # ROOT, LANGUAGE, FACTORY.json, VERSION, catalog.json
# What an installation writes at the root of a project: never part of the repository (verify --publication, .gitignore).
TARGET_TREES = (".claude", ".codex", ".agents", ".gemini", "AGENTS.md", "GEMINI.md", "CLAUDE.md")


class Error(C.Error):
    pass


def not_published() -> tuple:
    """What is never published, and whose presence prevents publishing (verify --publication): en and it names."""
    out = []
    for n in ("_work", "_v31", "local", "proposals", "EXPERT_REQUESTS.md", ".swarmer"):
        out += S.all_names(SWARM, n)
    return tuple(dict.fromkeys(out))


# --- the project and the internal state ---

def state_file(swarm: Path, canonical: str) -> Path:
    """An internal state file (A.2): the new name; if it is missing, the 4.0 one."""
    p = Path(swarm) / canonical
    if p.exists():
        return p
    old = Path(swarm) / C.STATE_NAMES.get(canonical, canonical)
    return old if old.exists() else p


def root_of(swarm: Path) -> Path:
    """The project root: from the ROOT file (the relative path, written at installation), otherwise the folder that
    contains the swarm folder."""
    p = state_file(swarm, "ROOT")
    if p.is_file():
        return (Path(swarm) / p.read_text(encoding="utf-8").strip()).resolve()
    return Path(swarm).parent


def installed(swarm: Path) -> bool:
    return state_file(swarm, "ROOT").is_file() and state_file(swarm, "FACTORY.json").is_file()


def require_installed(swarm: Path) -> None:
    if not installed(swarm):
        raise Error(msg(swarm, "cli_not_installed", root=swarm, path=swarm))


def language(swarm: Path) -> str:
    return C.language(swarm)


def msg(swarm: Path, key: str, **kw) -> str:
    t = G.i18n(swarm, language(swarm))
    default = {"cli_prefix": "swarmer: "}.get(key, key)
    return G.fmt(t.get(key, default), **kw)


def read_factory(swarm: Path) -> dict:
    """FACTORY.json and its 4.0 name joined (the new one wins)."""
    out = {}
    for n in (C.STATE_NAMES["FACTORY.json"], "FACTORY.json"):
        p = Path(swarm) / n
        if p.is_file():
            out.update(json.loads(p.read_text(encoding="utf-8")))
    return out


def factory_text(fab: dict) -> str:
    return json.dumps(fab, indent=1, sort_keys=True) + "\n"


def sha_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def factory_files(src: Path) -> list[str]:
    """The distributed files of a source: the DISTRIBUTED folders, without __pycache__, .new and hidden files, nor
    tests/fixtures/. A symbolic link or a file name outside the allowed form (spaces, newlines, «..») stops all."""
    out = []
    suffixes = tuple(S.all_names(src, ".new"))
    for name in DISTRIBUTED:
        base = src / name
        if base.is_symlink():
            raise Error(f"{base} is a symbolic link: not distributing it")
        if base.is_dir():
            S.check_no_links(base)
            for q in sorted(base.rglob("*")):
                if not q.is_file() or "__pycache__" in q.parts or q.name.endswith(suffixes) or q.name.startswith("."):
                    continue
                rel = q.relative_to(src).as_posix()
                if rel.startswith(NOT_DISTRIBUTED):
                    continue
                if not S.FILE_NAME.match(rel):
                    raise Error(f"file name not allowed in a source to distribute: {rel!r}")
                out.append(rel)
    return out


def files_to_distribute(swarm: Path) -> list[str]:
    """In the repository, every distributed file. In an installed swarm, only the factory ones (FACTORY.json): a
    file added by the project under docs/, tests/ or engine/ does not go out."""
    every = factory_files(swarm)
    if not installed(swarm):
        return every
    fab = read_factory(swarm)
    return [r for r in every if r in fab]


def originals(swarm: Path) -> dict[str, str]:
    """The factory files as they are in the installed swarmer.sh (and in the 4.0 script, if it is a full copy with the
    markers): the source of the version to distribute of a file the project changed."""
    out = {}
    for n in (C.OLD_MARKS["script"], "swarmer.sh"):
        sh = Path(swarm) / n
        if not sh.is_file():
            continue
        text = sh.read_text(encoding="utf-8", errors="replace")
        if not any(m + " file " in text for m in S.FILE_MARKS):
            continue
        name, buf = None, []
        for line in text.splitlines(keepends=True):
            mark = next((m for m in S.FILE_MARKS if line.startswith(m + " file ")), None)
            if mark and line.rstrip("\n").endswith(" ===="):
                if name:
                    out[name] = "".join(buf)
                name, buf = line[len(mark + " file "):].rstrip("\n")[:-len(" ====")], []
            elif any(line.startswith(f"{m} {e}") for m, e in ((S.FILE_MARK, S.END_OF_FILES_LINE),
                                                                (C.OLD_MARKS["file_mark"],
                                                                 C.OLD_MARKS["end_of_files_line"]))):
                if name:
                    out[name] = "".join(buf)
                name = None
            elif name:
                buf.append(line)
    return out


def distributed_content(swarm: Path, rel: str, cache: dict) -> str:
    """The text with which a file goes out: the one on disk if it is identical to the factory (or if this is not an
    installation), otherwise the factory version from the installed swarmer.sh. A file the project changed never
    goes out."""
    text = (Path(swarm) / rel).read_text(encoding="utf-8")
    if not installed(swarm):
        return text
    fab = cache.setdefault("fab", read_factory(swarm))
    if hashlib.sha256(text.encode("utf-8")).hexdigest() == fab.get(rel):
        return text
    orig = cache.setdefault("orig", originals(swarm)).get(rel)
    if orig is None or hashlib.sha256(orig.encode("utf-8")).hexdigest() != fab.get(rel):
        raise Error(f"{rel} was changed in the project and its factory version cannot be found: restore it or build "
                    "from the repository")
    return orig


# --- generation ---

def regenerate(swarm: Path, replaceable=frozenset(), lang: str | None = None, clean=()) -> tuple[dict, list[str]]:
    """Generates again. `clean`: targets removed explicitly, whose generated files go; the other inactive targets are
    neither touched nor examined."""
    require_installed(swarm)
    root = root_of(swarm)
    data = G.catalog(swarm, root, lang or language(swarm))
    check_collisions(data)
    out = G.write(swarm, root, data, replaceable, clean)
    warn_reserved(swarm, data)
    return data, out


def check_collisions(data: dict) -> None:
    """An agent <prefix>-<id> with the same name as a skill <prefix>-<strategy> in the language in use is an error."""
    skills = set(G.skill_names(data["language"], data["prefix"]).values())
    bad = sorted(r["id"] for r in data["roles"] if f"{data['prefix']}-{r['id']}" in skills)
    if bad:
        raise Error("the agents " + ", ".join(f"{data['prefix']}-{x}" for x in bad) + " would have the name of a skill: "
                    "rename the local cards")


def warn_reserved(swarm: Path, data: dict) -> None:
    ids = sorted(r["id"] for r in data["roles"] if r["id"] in P.RESERVED)
    if ids:
        print(msg(swarm, "cli_reserved_warning", ids=", ".join(ids), n=len(ids)))


def check(swarm: Path) -> int:
    require_installed(swarm)
    root = root_of(swarm)
    print(f"python3: {sys.version.split()[0]}")
    try:
        targets = G.targets_of(root)
    except C.Error as e:
        print(f"{msg(swarm, 'cli_prefix')}{e}")
        return 1
    print(msg(swarm, "cli_targets", targets=", ".join(targets)))
    if "claude" in targets:
        if shutil.which("claude"):
            r = subprocess.run(["claude", "--version"], capture_output=True, text=True, stdin=subprocess.DEVNULL)
            print("claude: " + ((r.stdout.strip().splitlines() or ["?"])[0]))
        else:
            print("claude: " + msg(swarm, "cli_missing_claude"))
    for cli, tg in G.CLIS.items():   # the other tools are only looked for, never started
        if tg in targets and cli != "claude":
            print(f"{cli}: " + (msg(swarm, "cli_found") if shutil.which(cli) else
                                msg(swarm, "cli_missing_cli", cli=cli, clis=", ".join(G.CLIS))))
    try:
        data = G.catalog(swarm, root, language(swarm))
        check_collisions(data)
        different = G.check(swarm, root, data)
        known_roles_ok()
    except C.Error as e:
        print(f"{msg(swarm, 'cli_prefix')}{e}")
        return 1
    pending_translations(swarm, data)
    for line in G.override_notes(root, data):
        print(line)
    if different:
        print("\n".join(different))
        print(msg(swarm, "cli_not_aligned"))
        return 1
    print(msg(swarm, "cli_aligned", roles=len(data["roles"]), profiles=len(data["profiles"])))
    return 0


def pending_translations(swarm: Path, data: dict) -> None:
    """The roles generated from the English text, waiting for their translation (K.2): listed, never a failure."""
    pending = data.get("translation_pending", [])
    if pending:
        print(msg(swarm, "cli_translation_pending", language=data["language"], n=len(pending), ids=", ".join(pending),
                  command=command_line(swarm, "translate", "<id>", "<file.json>")))


def command_line(swarm: Path, command: str, *args: str) -> str:
    """A command of swarmer.sh as the user of this installation writes it: the names of its language."""
    lang = language(swarm)
    sec = A.per_language(swarm).get(lang, {}) if lang != "en" else {}

    def local(kind, x):
        names = sec.get(kind, {}).get(x, [])
        return names[0] if names else x
    script = S.localized_name(swarm, "swarmer.sh", lang)
    if not (Path(swarm) / script).is_file():
        script = "swarmer.sh"
    try:
        folder = Path(swarm).resolve().relative_to(root_of(swarm).resolve()).as_posix()
    except ValueError:
        folder = Path(swarm).name
    words = [local("options", a) if a.startswith("--") else a for a in args]
    return " ".join([f"bash {folder}/{script}", local("commands", command), *words])


def known_roles_ok() -> None:
    """The same id with agents of the two prefixes and different bodies is an error (C.8)."""
    import jury
    if jury.agents_dirs():
        jury.known_roles()


# --- installation and update, with the protected files ---

def alias_stub(alias: str, target: str) -> bytes:
    if alias.endswith(".sh"):
        return (f"#!/usr/bin/env bash\n# swarmer 5.0: an alias of {target}.\n"
                f'exec bash "$(dirname "$0")/{target}" "$@"\n').encode()
    return (f'#!/usr/bin/env python3\n"""swarmer 5.0: an alias of {target}."""\nimport runpy\nimport sys\n'
            f"from pathlib import Path\n\nm = Path(__file__).resolve().parent / \"{target}\"\nsys.argv[0] = str(m)\n"
            f"runpy.run_path(str(m), run_name=\"__main__\")\n").encode()


def detect_folder(root: Path, lang: str | None = None) -> str:
    """The swarm folder of a project (E): config.json (folder), otherwise swarmer/ if installed, otherwise its 4.0 name if
    it has a factory, otherwise the default of the language."""
    cfg = S.config(root)
    if cfg.get("folder"):
        return str(cfg["folder"])
    for f in S.all_names(None, "swarmer"):
        if (Path(root) / f / "FACTORY.json").is_file() or (Path(root) / f / C.STATE_NAMES["FACTORY.json"]).is_file():
            return f
    return S.localized_name(None, "swarmer", lang or "en")


def merge_db(local: dict, new: dict) -> dict:
    """Joins the database of the project with the new factory one: the new factory entries are added, those added
    in the project stay; for an id in both, the project's version stays, and a new factory language is added. Both
    arguments in format 2 (entries files)."""
    a = {"format": 2, "entries": [dict(v) for v in local.get("entries", [])]}
    ids = {v["id"] for v in a["entries"]}
    for v in new.get("entries", []):
        if v["id"] not in ids:
            a["entries"].append(v)
            ids.add(v["id"])
        else:
            old = next(x for x in a["entries"] if x["id"] == v["id"])
            for l, t in v.get("texts", {}).items():
                old.setdefault("texts", {}).setdefault(l, t)
    return a


def _load_entries(p: Path) -> dict:
    d = json.loads(p.read_text(encoding="utf-8"))
    return C.db_from_v1(d) if C.is_v1(d) else d


def install(src: Path, root: Path, folder: str | None, lang_arg: str | None, force: bool, local: str | None,
            managed: bool, targets_arg: str | None = None) -> Path:
    """Copies the factory files from `src` into <root>/<folder>, and migrates a 4.0 installation (E).
    - A folder that exists and is not a swarm (neither a factory nor a 3.x VERSION) is refused, unless --force, which
      first makes a backup copy.
    - A file that exists and differs from the registered factory one, or that is not registered, is not
      overwritten: the new version goes next to it with the suffix .new (localized), except the database, which is
      merged.
    - No write follows a symbolic link.
    - The targets (5.1): --targets, otherwise the key of config.json; a new installation without either gets the
      targets detected in the project (auto); an existing one without either stays Claude Code only."""
    root = root.resolve()
    S.config(root)   # before any write (E): a configuration that cannot be read stops here, with the tree untouched
    wanted = G.parse_targets(targets_arg) if targets_arg else False   # False: not given; None: auto
    detected = G.detect_targets(root)   # before the installation writes anything in the project
    folder = folder or detect_folder(root, lang_arg)
    swarm = S.valid_folder(root, folder)
    folder = swarm.relative_to(root).as_posix()   # the normalized form, the one head.sh reads
    if local:
        lp = Path(local)
        if lp.is_absolute() or ".." in lp.parts:
            raise Error(f"--local «{local}»: a relative path inside the project is needed")
    version_p = state_file(swarm, "VERSION")
    version_text = version_p.read_text(encoding="utf-8") if version_p.is_file() else ""
    is31 = version_text.startswith("3.")
    old_fab = swarm / C.STATE_NAMES["FACTORY.json"]
    known = (swarm / "FACTORY.json").is_file() or old_fab.is_file() or is31
    if swarm.exists() and any(swarm.iterdir()) and not known and not force:
        raise Error(f"{swarm} exists and is not a swarm: not touching it. Choose another --folder (for instance "
                    f"{folder}/skill, with --local {folder} if it holds its own cards) or use --force, which first "
                    "makes a backup copy")
    # every check before the first write: the targets it will write (and those removed explicitly), the links
    if wanted is not False:
        final = detected if wanted is None else wanted
    elif not known and S.config(root).get("targets") is None:
        final = detected
    else:
        final = G.targets_of(root)
    clean = [x for x in G.targets_of(root) if x not in final] if known and wanted is not False else []
    S.no_links(root, swarm)
    for rel in factory_files(src) + list(ROOT_WRAPPERS) + list(C.ALIAS_STUBS) + ["swarmer.sh", "UPSTREAM"] \
            + list(STATE) + list(C.STATE_NAMES.values()):
        S.no_links(swarm, swarm / rel)
    try:
        G.preflight(root, final, clean)
    except C.Error as e:
        raise Error(str(e))
    if swarm.exists() and any(swarm.iterdir()) and ((force and not known) or is31):
        copy = root / f"{folder.replace('/', '_')}.before-{datetime.datetime.now():%Y%m%d-%H%M%S}"
        shutil.copytree(swarm, copy, symlinks=True)
        print(f"backup: {copy}")
    replaceable = G.replaceable_31(swarm, root) if is31 else frozenset()
    swarm.mkdir(parents=True, exist_ok=True)
    S.no_links(root, swarm)
    marker = swarm / C.MIGRATING
    from40 = old_fab.is_file() or (marker.is_file() and marker.read_text(encoding="utf-8").startswith("4."))
    migrating = from40 or marker.is_file() or any((swarm / o).exists() for o in C.STATE_NAMES.values())
    if migrating:
        S.write(swarm, marker, "4.0\n" if from40 else "\n")
    # the language: the option, then LANGUAGE (or its 4.0 name), it for a 4.0, en
    lang = lang_arg
    if not lang:
        p = state_file(swarm, "LANGUAGE")
        lang = (p.read_text(encoding="utf-8").strip() if p.is_file() else "") or ("it" if from40 else "en")
    if lang not in G.available_languages(src):
        raise Error(msg(src, "cli_language_unknown", language=lang, languages=", ".join(G.available_languages(src))))
    # 1. the old factory and the new one
    old = read_factory(swarm)
    sources = [(rel, (src / rel).read_bytes()) for rel in factory_files(src)]
    sources += [(n, (src / s).read_bytes()) for n, s in ROOT_WRAPPERS.items() if (src / s).is_file()]
    if lang == "it" or from40 or any(n in old for n in C.ALIAS_STUBS):
        sources += [(a, alias_stub(a, t)) for a, t in C.ALIAS_STUBS.items()]
    for n in ("swarmer.sh", "UPSTREAM"):
        if (src / n).is_file():
            sources.append((n, (src / n).read_bytes()))
    fab = {}
    suffix = S.localized_name(src, ".new", lang)
    protected, written = [], 0
    db_rel = f"db/{P.DB_FILE}"
    old_db = swarm / "db" / C.OLD_DB[P.DB_FILE]
    # 2. every factory file of 5.0
    for rel, data in sources:
        dst = swarm / rel
        S.no_links(swarm, dst)
        h = hashlib.sha256(data).hexdigest()
        if rel == db_rel and (dst.is_file() or old_db.is_file()):
            # the database is always merged: the entries approved in the project stay, the new factory ones enter
            local_db = {"format": 2, "entries": []}
            for p in (old_db, dst):
                if p.is_file():
                    local_db = merge_db(local_db, _load_entries(p))
            merged = merge_db(local_db, _load_entries_bytes(data))
            text = json.dumps(merged, ensure_ascii=False, indent=1) + "\n"
            if not dst.is_file() or dst.read_text(encoding="utf-8") != text:
                S.write(swarm, dst, text)
            fab[rel] = sha_file(dst)
            continue
        if dst.is_file():
            current = sha_file(dst)
            if current == h:
                fab[rel] = h
                continue
            v31 = is31 and f"@swarm/{rel}" in replaceable
            changed = rel not in old or current != old[rel]
            if changed and not v31 and not (force and not known):
                S.write(swarm, dst.parent / (dst.name + suffix), data)
                fab[rel] = h      # the new factory is the one of the new swarmer.sh: the file stays the project's
                protected.append(rel)
                continue
        S.write(swarm, dst, data, 0o755 if rel.endswith(".sh") else None)
        fab[rel] = h
        written += 1
    # 3. the old factory files that 5.0 no longer has
    left = []
    for rel, h in sorted(old.items()):
        if rel in fab:
            continue
        p = swarm / rel
        if p.is_symlink() or not p.is_file():
            continue
        S.no_links(swarm, p)
        if rel == f"db/{C.OLD_DB[P.DB_FILE]}" or sha_file(p) == h or S.is_generated(p):
            S.remove_file(swarm, p)
            _prune(swarm, p.parent)
        else:
            left.append(rel)
    if old_db.is_file() and db_rel in fab:
        S.remove_file(swarm, old_db)
    # the files of the project, created only if no language's name exists (A.4)
    reg = S.find_project_file(swarm, "EXPERT_REQUESTS.md", lang, src)
    tpl = src / "docs" / lang / "_EXPERT_REQUESTS.md"
    if not reg.exists() and tpl.is_file():
        S.write(swarm, reg, tpl.read_bytes())
    loc = S.fixed_local(swarm, lang)
    readme = S.find_project_file(loc, "LOCAL_README.md", lang, src)
    tpl = src / "docs" / lang / "_LOCAL.md"
    if not readme.exists() and tpl.is_file():
        S.write(swarm, readme, tpl.read_bytes())
    forb = S.find_project_file(loc, "FORBIDDEN.txt", lang, src)
    if not forb.exists():
        S.write(swarm, forb, C.FORBIDDEN_HEAD.get(lang, C.FORBIDDEN_HEAD["en"]))
    # 6 (first half). the new internal state
    S.write(swarm, swarm / "FACTORY.json", factory_text(fab))
    S.write(swarm, swarm / "ROOT", os.path.relpath(root, swarm) + "\n")
    S.write(swarm, swarm / "LANGUAGE", lang + "\n")
    # the configuration: written only if a command changes it (C.2)
    cfg = S.config(root)
    new = dict(cfg)
    if local:
        new["local"] = local
    if managed:
        new["project_managed"] = True
    if "folder" in cfg or detect_folder(root, lang) != folder:
        new["folder"] = folder
    if wanted is not False or (not known and cfg.get("targets") is None):
        new["targets"] = final   # chosen, or a new installation: the targets of the project
    S.write_config(root, new, lang)
    # 5. regenerate
    data, done = regenerate(swarm, replaceable, lang, clean)
    # 6 (second half). the old internal state goes, then the marker
    for canon, o in C.STATE_NAMES.items():
        p = swarm / o
        if p.is_file() and not p.is_symlink() and (swarm / canon).is_file():
            S.remove_file(swarm, p)
    if marker.is_file():
        S.remove_file(swarm, marker)
    skipped = [f for f in done if f.startswith("skipped")]
    print(msg(swarm, "cli_installed", version=G.VERSION, root=root, language=data["language"],
              agents=len({Path(f).stem for f in done if any(f.startswith(d + "/") for d, _e in G.agent_dirs())}),
              skills=len({Path(f).parent.name for f in done if any(f.startswith(d + "/") for d in G.skill_dirs())})))
    print(msg(swarm, "cli_targets", targets=", ".join(data["targets"])))
    if skipped:
        print(msg(swarm, "cli_skipped", n=len(skipped)))
    pending_translations(swarm, data)
    if protected:
        print(msg(swarm, "cli_updated", n=written, protected=", ".join(protected)))
    if left:
        print(msg(swarm, "cli_left_modified", n=len(left), files=", ".join(left), protected=", ".join(left)))
    if migrating:
        claude = root / "CLAUDE.md"
        old_par = claude.is_file() and C.CLAUDE_MARKS["it"][2] in claude.read_text(encoding="utf-8")
        print(msg(swarm, "cli_migrated", version=G.VERSION, command=command_line(swarm, "instructions"),
                  path=claude if old_par else ""))
    return swarm


def _load_entries_bytes(b: bytes) -> dict:
    d = json.loads(b.decode("utf-8"))
    return C.db_from_v1(d) if C.is_v1(d) else d


def _prune(swarm: Path, d: Path) -> None:
    """Removes the empty folders from `d` up to the swarm folder (excluded)."""
    swarm = Path(swarm)
    while d != swarm and swarm in d.parents and d.is_dir() and not d.is_symlink() and not any(d.iterdir()):
        d.rmdir()
        d = d.parent


def ensure_alias_stubs(swarm: Path) -> None:
    """The Italian aliases of the factory (A.3), for `language it`: written if missing or equal to the registered
    ones; registered in FACTORY.json."""
    fab = read_factory(swarm)
    changed = False
    for a, t in C.ALIAS_STUBS.items():
        p = swarm / a
        data = alias_stub(a, t)
        if p.is_file() and (sha_file(p) == hashlib.sha256(data).hexdigest() or (a in fab and sha_file(p) != fab[a])):
            continue
        S.write(swarm, p, data, 0o755 if a.endswith(".sh") else None)
        fab[a] = hashlib.sha256(data).hexdigest()
        changed = True
    if changed:
        S.write(swarm, swarm / "FACTORY.json", factory_text(fab))


# --- starting a convening ---

def launch(swarm: Path, strategy: str, ns) -> None:
    require_installed(swarm)
    al = A.load(swarm)
    request = ns.request or ""
    if ns.from_file:
        request = Path(ns.from_file).read_text(encoding="utf-8")
    if not request.strip():
        raise Error(msg(swarm, "cli_missing_request", strategy=G.strategy_name(strategy, language(swarm))))
    cat = json.loads(state_file(swarm, "catalog.json").read_text(encoding="utf-8"))
    profile = A.value(al, "profile", ns.profile)
    if profile and profile not in cat["profiles"]:
        raise Error(msg(swarm, "cli_unknown_profile", profile=ns.profile, profiles=", ".join(cat["profiles"])))
    ids = {r["id"] for r in cat["roles"]}
    roles = []
    for r in (ns.roles or "").split(","):
        r = r.strip()
        for p in C.AGENT_PREFIXES:
            if r.startswith(p + "-"):
                r = r[len(p) + 1:]
        if r:
            roles.append(r)
    for r in roles:
        if r not in ids:
            raise Error(msg(swarm, "cli_unknown_role", role=r))
    pending = sorted(set(roles) & set(cat.get("translation_pending", [])))
    if pending:
        print(msg(swarm, "cli_translation_pending", language=cat.get("language", ""), n=len(pending),
                  ids=", ".join(pending), command=command_line(swarm, "translate", "<id>", "<file.json>")),
              file=sys.stderr)
    langs = G.available_languages(swarm)
    if ns.language and ns.language not in langs:
        raise Error(msg(swarm, "cli_language_unknown", language=ns.language, languages=", ".join(langs)))
    lang = language(swarm)
    root = root_of(swarm)
    cli = choose_cli(swarm, root, ns.cli)
    target = G.CLIS[cli]
    if target not in G.targets_of(root):
        raise Error(msg(swarm, "cli_target_inactive", cli=cli, target=target,
                        command=command_line(swarm, "targets", "--add", target)))
    skill = G.skill_names(lang, G.prefix_of(root, lang))[strategy]
    skill_file = f"{G.TARGETS[target]['skills']}/{skill}/SKILL.md"
    if not (root / skill_file).is_file():
        raise Error(f"the skill {skill} is missing: bash {swarm.name}/swarmer.sh regenerate")
    args = (f"profile={profile} " if profile else "") + (f"roles={','.join(roles)} " if roles else "") \
        + (f"language={ns.language} " if ns.language else "")
    command = launch_command(swarm, cli, skill, skill_file, args + request, ns)
    if ns.show:
        print(f"cd {shlex.quote(str(root))} && " + " ".join(shlex.quote(x) for x in command))
        return
    if not shutil.which(cli):
        raise Error(msg(swarm, "cli_missing_claude") if cli == "claude" else
                    msg(swarm, "cli_missing_cli", cli=cli, clis=", ".join(G.CLIS)))
    os.chdir(root)
    os.execvp(cli, command)


def choose_cli(swarm: Path, root: Path, given: str | None) -> str:
    """The tool that `start` opens: --cli, otherwise the key «cli» of config.json, otherwise the first of claude,
    codex, agy, gemini whose target is active and that is found in the PATH, otherwise the first whose target is
    active (claude if none: the generic target alone has no tool)."""
    cli = given or S.config(root).get("cli")
    if not cli:
        active = G.targets_of(root)
        usable = [c for c in G.CLIS if G.CLIS[c] in active]
        cli = next((c for c in usable if shutil.which(c)), usable[0] if usable else "claude")
    if cli not in G.CLIS:
        raise Error(msg(swarm, "cli_unknown_cli", cli=cli, clis=", ".join(G.CLIS)))
    return cli


def launch_command(swarm: Path, cli: str, skill: str, skill_file: str, request: str, ns) -> list[str]:
    """The command line that opens the tool with the skill and the request: interactive, or with --print without
    interaction. Claude Code receives the skill as a slash command; the other tools a prompt that names the skill and
    its file (they find it in .agents/skills)."""
    if cli == "claude":
        return (["claude"] + (["--model", ns.model] if ns.model else []) + (["-p"] if ns.print else [])
                + [f"/{skill} {request}"] + ns.rest)
    prompt = G.fmt(G.i18n(swarm, language(swarm)).get("launch_prompt", "{skill} {request}"), skill=skill,
                   path=skill_file, request=request)
    if cli == "codex":
        return ["codex"] + (["exec"] if ns.print else []) + (["--model", ns.model] if ns.model else []) + [prompt] + ns.rest
    if cli == "gemini":
        return ["gemini"] + (["--model", ns.model] if ns.model else []) + (["-p"] if ns.print else ["-i"]) + [prompt] \
            + ns.rest
    if ns.model:   # agy: the model of the session is chosen in Antigravity
        raise Error(msg(swarm, "cli_option_unsupported", option="--model", cli=cli))
    return ["agy"] + (["-p"] if ns.print else ["-i"]) + [prompt] + ns.rest


# --- new professionals: approval and proposal to the repository ---

def forbidden(swarm: Path) -> list[str]:
    return S.forbidden(root_of(swarm), swarm)[0]


def local_ids(swarm: Path) -> set[str]:
    root = root_of(swarm)
    return set(P.local_cards(S.local_agents_file(root, swarm))) if installed(swarm) else set()


def require_forbidden(swarm: Path) -> list[str]:
    """In a project with local overrides, before producing public material a FORBIDDEN.txt is needed (even empty, as
    long as it exists): it is the declaration that the project thought about what must not go out."""
    root = root_of(swarm)
    words, _ = S.forbidden(root, swarm)
    loc = S.local_folder(root, swarm)
    found = any((loc / n).is_file() for n in S.all_names(swarm, "FORBIDDEN.txt"))
    if installed(swarm) and S.has_override(root, swarm) and not found:
        raise Error(f"the project has local overrides but no FORBIDDEN.txt in {loc}: write it before approving, "
                    "proposing or building")
    return words


def git_identity() -> tuple[str, str]:
    """The identity with which propose signs the commit: the global one, read outside every repository; the commit
    uses it with -c, so the local configuration of the project does not count."""
    with tempfile.TemporaryDirectory() as empty:
        def read(k):
            return subprocess.run(["git", "config", "--global", "--get", k], capture_output=True, text=True,
                                  cwd=empty, stdin=subprocess.DEVNULL).stdout.strip()
        return read("user.name"), read("user.email")


def public_tree(base: Path) -> list[str]:
    """The files the repository would publish. With .git: `git ls-files -co --exclude-standard` (the full rules of
    .gitignore and the files already tracked). Without: the DISTRIBUTED folders entirely (except __pycache__, .pyc,
    .new) and the rest minus what .gitignore excludes by name. A symbolic link among the published files stops all."""
    base = Path(base)
    suffixes = tuple(S.all_names(base, ".new"))
    if (base / ".git").exists():
        p = subprocess.run(["git", "-C", str(base), "ls-files", "-co", "--exclude-standard", "-z"], capture_output=True,
                           stdin=subprocess.DEVNULL, check=True)
        rels = {r for r in p.stdout.decode("utf-8").split("\0") if r}
        # what build distributes is examined and copied anyway, even if .gitignore excludes it
        rels |= set(factory_files(base)) | {x for x in ("UPSTREAM", "swarmer.sh", C.OLD_MARKS["script"])
                                            if (base / x).is_file()}
        rels = sorted(rels)
    else:
        npub = not_published()
        ign = {".git", "__pycache__"} | set(npub) | ignored(base)
        ign_file = {".git", "__pycache__"} | set(npub) | ignored(base, files_only=True)
        rels = []
        for top, dirs, files in os.walk(base, followlinks=False):
            d = Path(top)
            inside = d != base and d.relative_to(base).parts[0] in DISTRIBUTED
            for c in list(dirs):
                if (d / c).is_symlink():
                    raise Error(f"{(d / c).relative_to(base)} is a symbolic link: not publishing it")
            dirs[:] = [c for c in dirs if c not in ("__pycache__", ".git")
                       and (inside or (d == base and c in DISTRIBUTED) or c not in ign)]
            for n in files:
                if n.endswith((".pyc",) + suffixes) or (not inside and n in ign_file):
                    continue
                rels.append((d / n).relative_to(base).as_posix())
        rels.sort()
    for r in rels:
        S.no_links(base, base / r)
    return rels


def ignored(base: Path, files_only: bool = False) -> set[str]:
    """The folders and files that .gitignore excludes by name (without «*»): they are not published, so not
    examined."""
    gi = Path(base) / ".gitignore"
    if not gi.is_file():
        return set()
    lines = [r.rstrip() for r in gi.read_text(encoding="utf-8").splitlines()
             if r.strip() and not r.startswith(("#", " ", "\t"))]   # a leading space is part of the name
    if any(r.startswith("!") for r in lines):
        raise Error(".gitignore has a negation «!»: without .git I do not know what is published; git init and repeat")
    # only the simple names (with at most a trailing «/»): an anchor, a path or a pattern do not apply, so that more is
    # examined, never less
    names = [r for r in lines if not any(c in r.rstrip("/") for c in "/*?[\\")]
    return {r.rstrip("/") for r in names if not (files_only and r.endswith("/"))}


def name_problems(rel: str, words: list[str]) -> list[str]:
    """The path of a file, as it is and with «-», «_», «.», «/» as spaces (for the entries of several words)."""
    return sorted(set(S.public_problems(rel, words) + S.public_problems(re.sub(r"[-_./]", " ", rel), words)))


def strings(x) -> list[str]:
    """Every string of an entry, at every depth, keys included."""
    if isinstance(x, str):
        return [x]
    if isinstance(x, dict):
        return [s for k, v in x.items() for s in strings(k) + strings(v)]
    if isinstance(x, list):
        return [s for v in x for s in strings(v)]
    return []


def phrases(text: str, n: int = 10) -> set[str]:
    words = re.findall(r"\w+", S.normalize(text))
    return {" ".join(words[i:i + n]) for i in range(max(0, len(words) - n + 1))}


def local_phrases(swarm: Path) -> set[str]:
    """The sequences of ten words of the files of the local folder: a public text must contain none of them."""
    root = root_of(swarm)
    out = set()
    loc = S.local_folder(root, swarm)
    files = [S.local_agents_file(root, swarm)] + (sorted(loc.glob("*.md")) if loc.is_dir() else [])
    for f in dict.fromkeys(files):
        if f.is_file():
            out |= phrases(f.read_text(encoding="utf-8"))
    return out


def proposals_dir(swarm: Path) -> Path:
    return S.find_project_file(swarm, "proposals", language(swarm), swarm)


def approve(swarm: Path, file: Path, rebuild: bool = True, generic_of_local: bool = False) -> str:
    """Adds new entries to the database (after the approval). Everything is first tried in a copy: if a check fails,
    the database, the agents and swarmer.sh stay as they were. The file is in format 1 or 2."""
    require_installed(swarm)
    raw = json.loads(Path(file).read_text(encoding="utf-8"))
    entries = [P.entry_v2(e) for e in (raw if isinstance(raw, list) else [raw])]
    d = P.load(swarm / "db")
    langs = G.available_languages(swarm)
    before = [v["id"] for v in d["entries"]]
    ids = set(before)
    words = require_forbidden(swarm)
    locals_ = local_ids(swarm)
    root = root_of(swarm)
    pre = G.prefix_of(root, language(swarm))
    for v in entries:
        if not isinstance(v, dict) or not ID_ARG.match(str(v.get("id", ""))):
            raise Error("an entry without a valid id")
        v.setdefault("version", G.VERSION)
        v.setdefault("status", "active")
        v.setdefault("parent", None)
        if v["id"] in ids:
            raise Error(f"{pre}-{v['id']} is already in the database")
        if v["id"] in P.RESERVED:
            raise Error(f"{pre}-{v['id']}: the id is reserved to a strategy")
        if v["id"] in locals_ and not generic_of_local:
            raise Error(f"{pre}-{v['id']} is a local card: only a generic version of it, without details of the project, "
                        "enters the public database, with --generic-from-local")
        prob = S.public_problems(json.dumps(v, ensure_ascii=False), words)
        common = phrases(" ".join(strings(v))) & local_phrases(swarm)
        if common:
            prob.append(f"{len(common)} sequences of ten words in common with the local cards (for instance "
                        f"«{sorted(common)[0]}»)")
        if prob:
            raise Error(f"{pre}-{v['id']}: cannot go into the public database: " + "; ".join(prob))
        d["entries"].append(v)
        ids.add(v["id"])
    # English is mandatory only in the public database (K.1): locally an entry may have only the language of the
    # installation, and stays local (propose refuses it) until it has the English texts
    errors = P.validate(d, langs, existing=before, required=())
    for v in entries:
        if not P.english_problems(v):
            continue
        if language(swarm) not in v.get("texts", {}):
            errors.append(f"{v['id']}: the texts are needed in English (or at least in «{language(swarm)}», the "
                          "language of the installation, until the English translation)")
    if errors:
        raise Error("the entry is not valid:\n  " + "\n  ".join(errors[:20]))
    local_only = [v["id"] for v in entries if P.english_problems(v)]
    cfg = S.config(root)
    copies = []
    for c in cfg.get("swarmer_sh_copies", []) if rebuild else []:
        if Path(c).is_absolute() or ".." in Path(c).parts:
            raise Error(f"swarmer_sh_copies: «{c}» is not a relative path inside the project")
        copies.append(S.no_links(root, root / c))
    rep = cfg.get("local_repository") if rebuild else None
    if rep:
        rep = Path(rep) if Path(rep).is_absolute() else root / rep
        dr = P.load(rep / "db")
        new_rep = [v for v in entries if v["id"] not in {x["id"] for x in dr["entries"]} and v["id"] not in local_only]
        dr["entries"] += new_rep
        err = P.validate(dr, G.available_languages(rep), existing=[x["id"] for x in dr["entries"] if x not in new_rep])
        if err:
            raise Error(f"{rep}: the entry is not valid in the repository: " + "; ".join(err[:5]))
    S.check_no_links(swarm)
    db_text = P.db_text(d)
    with tempfile.TemporaryDirectory() as tmp:   # the trial in a copy of everything that will be written, true root
        trial = Path(tmp) / "s"
        shutil.copytree(swarm, trial, symlinks=False,
                        ignore=shutil.ignore_patterns("__pycache__", *[f"*{s}" for s in S.all_names(swarm, ".new")]))
        for o in (C.STATE_NAMES["ROOT"],):
            if (trial / o).exists():
                (trial / o).unlink()
        (trial / "ROOT").write_text(str(root) + "\n", encoding="utf-8")
        (trial / "db" / P.DB_FILE).write_text(db_text, encoding="utf-8")
        fab_t = read_factory(trial)
        fab_t[f"db/{P.DB_FILE}"] = hashlib.sha256(db_text.encode("utf-8")).hexdigest()
        (trial / "FACTORY.json").write_text(json.dumps(fab_t), encoding="utf-8")
        G.catalog(trial, root, language(swarm))
        if rebuild:
            build(trial, Path(tmp) / "swarmer.sh")
        if rep:
            trial_rep = Path(tmp) / "r"
            for r_ in public_tree(rep):   # the copy of what is published, file by file, without links
                (trial_rep / r_).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(rep / r_, trial_rep / r_, follow_symlinks=False)
            P.save(dr, trial_rep / "db")
            build(trial_rep, Path(tmp) / "rep.sh", extra_words=words)
    S.write(swarm, swarm / "db" / P.DB_FILE, db_text)
    regenerate(swarm)
    props = proposals_dir(swarm)
    for v in entries:
        S.write(swarm, props / f"{v['id']}.json", json.dumps(v, ensure_ascii=False, indent=1) + "\n")
        close_requests(swarm, v["id"], d)
    out = "—"
    fab = read_factory(swarm)
    fab[f"db/{P.DB_FILE}"] = sha_file(swarm / "db" / P.DB_FILE)   # changed by approval
    S.write(swarm, swarm / "FACTORY.json", factory_text(fab))      # before building: the db goes out
    if rebuild:
        out = str(build(swarm, swarm / "swarmer.sh"))
        fab["swarmer.sh"] = sha_file(swarm / "swarmer.sh")
        for dest in copies:
            S.write(root, dest, (swarm / "swarmer.sh").read_bytes(), 0o755)
            out += f", {dest}"
        if rep:
            S.write(rep, rep / "db" / P.DB_FILE, P.db_text(dr))
            build(rep, rep / "swarmer.sh", extra_words=words)
            out += f", {rep / 'swarmer.sh'} (+{len(new_rep)} entries in the local repository)"
    S.write(swarm, swarm / "FACTORY.json", factory_text(fab))
    ids_text = ",".join(v["id"] for v in entries)
    kind = entries[0]["type"]
    kind = kind if language(swarm) == "en" else C.VALUES["entry_type"].get(kind, kind)
    done = msg(swarm, "cli_approved", ids=ids_text, id=ids_text, type=kind, script=out, swarmer_sh=out,
               path=props, proposal=props, prefix=pre)
    if local_only:
        done += "\n" + msg(swarm, "cli_local_until_english", ids=", ".join(local_only),
                           command=command_line(swarm, "translate", local_only[0], "<file.json>", "--language", "en"))
    return done


def translate(swarm: Path, rid: str, file: Path, lang: str | None = None) -> str:
    """Registers the translation of an entry of the database (K.3), made by the model that convenes it: the texts
    (name, short, keywords, body) in a JSON object, in either dialect. They are validated like the cards and with the
    public checks of the forbidden words. Into the language of the installation (or another one, not English) they go
    into the local overlay <swarm>/local/translations/<lang>/<id>.json, never distributed nor published, which
    survives the updates; the fingerprint of the texts is recorded, so that a public translation arriving later wins
    only if the local one was not modified by hand. Into English (a local entry approved without it) they go into
    the database and into the proposal: then propose accepts the entry. Agents, skills and catalog are regenerated."""
    require_installed(swarm)
    ilang = language(swarm)
    lang = lang or ilang
    langs = G.available_languages(swarm)
    if lang not in langs:
        raise Error(msg(swarm, "cli_language_unknown", language=lang, languages=", ".join(langs)))
    if not ID_ARG.match(rid):
        raise Error(f"invalid id: {rid}")
    d = P.load(swarm / "db")
    entry = next((v for v in d["entries"] if v.get("id") == rid), None)
    if entry is None:
        raise Error(msg(swarm, "cli_unknown_role", role=rid))
    raw = json.loads(Path(file).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise Error(f"{file}: an object with name, short, keywords and body is needed")
    obj = C.to_canonical(raw, C.TRANSLATION_SCHEMA, str(file))
    if obj.get("id") not in (None, rid):
        raise Error(f"{file}: the id is «{obj['id']}», not «{rid}»")
    if obj.get("language") not in (None, lang):
        raise Error(f"{file}: the language is «{obj['language']}», not «{lang}»")
    texts = {k: obj.get(k) for k in P.TEXT_FIELDS}
    if isinstance(texts["body"], str) and texts["body"] and not texts["body"].endswith("\n"):
        texts["body"] += "\n"
    errors = P.text_problems(texts, rid, lang)
    if errors:
        raise Error("the translation is not valid:\n  " + "\n  ".join(errors[:20]))
    words = require_forbidden(swarm)
    prob = S.public_problems(json.dumps(texts, ensure_ascii=False), words)
    common = phrases(" ".join(strings(texts))) & local_phrases(swarm)
    if common:
        prob.append(f"{len(common)} sequences of ten words in common with the local cards")
    if prob:
        raise Error(f"{rid}: " + "; ".join(prob))
    if lang in entry.get("texts", {}):
        raise Error(msg(swarm, "cli_translation_exists", id=rid, language=lang))
    if lang == "en":
        entry.setdefault("texts", {})["en"] = texts
        errors = P.validate(d, langs, existing=[v.get("id") for v in d["entries"]], required=())
        if errors:
            raise Error("the entry is not valid:\n  " + "\n  ".join(errors[:20]))
        S.write(swarm, swarm / "db" / P.DB_FILE, P.db_text(d))
        prop = proposals_dir(swarm) / f"{rid}.json"
        if prop.is_file():
            pv = P.entry_v2(json.loads(prop.read_text(encoding="utf-8")))
            pv.setdefault("texts", {})["en"] = texts
            S.write(swarm, prop, json.dumps(pv, ensure_ascii=False, indent=1) + "\n")
        fab = read_factory(swarm)
        fab[f"db/{P.DB_FILE}"] = sha_file(swarm / "db" / P.DB_FILE)
        S.write(swarm, swarm / "FACTORY.json", factory_text(fab))
        regenerate(swarm)
        return msg(swarm, "cli_translated_english", id=rid, language=lang, path=swarm / "db" / P.DB_FILE)
    dest = G.translations_dir(swarm, lang) / f"{rid}.json"
    dialect = ilang
    if dest.is_file():
        dialect = C.dialect_of(json.loads(dest.read_text(encoding="utf-8")), C.TRANSLATION_SCHEMA, ilang)
    out = {"id": rid, "language": lang, **texts, "written_sha256": G.translation_sha(texts)}
    S.write(swarm, dest, json.dumps(C.to_dialect(out, C.TRANSLATION_SCHEMA, dialect), ensure_ascii=False, indent=1)
            + "\n")
    regenerate(swarm)
    return msg(swarm, "cli_translated", id=rid, language=lang, path=dest)


def close_requests(swarm: Path, rid: str, d: dict) -> None:
    p = S.find_project_file(swarm, "EXPERT_REQUESTS.md", language(swarm), swarm)
    if not p.is_file():
        return
    t = p.read_text(encoding="utf-8")
    dialect = "en" if p.name == "EXPERT_REQUESTS.md" else "it"
    number = next((v["number"] for v in P.ordered(d) if v["id"] == rid), "?")
    line = C.REGISTER_CLOSED[dialect].format(id=rid, n=number, date=datetime.date.today().isoformat())
    if not any(f"- `{rid}`: {w}" in t for w in C.REGISTER_WORDS["created"]):
        S.write(swarm, p, t.rstrip("\n") + "\n" + line + "\n")


def propose(swarm: Path, ids: list[str], send: bool, yes: bool, lang: str | None = None) -> str:
    """Prepares the pull request of the approved entries to the public repository (UPSTREAM). With --send and --yes it
    opens it: clones UPSTREAM, adds the entries to its database, rebuilds swarmer.sh with the LOCAL engine (not with
    the downloaded code), verifies the clone with the forbidden words of the project, makes the fork, the push and the
    pull request. The public database is English (K.1): an entry without complete English texts is refused, and the
    title, the body, the branch and the commit message are always in English, whatever the language of the
    installation (`lang`, the --language option, is accepted and does not change them); the messages to the user are
    in the language of the installation."""
    require_installed(swarm)
    up = swarm / "UPSTREAM"
    upstream = (up.read_text(encoding="utf-8").splitlines() or [""])[0].strip() if up.is_file() else ""
    lang = "en"
    t = G.i18n(swarm, lang)
    ui = G.i18n(swarm, language(swarm))
    entries = []
    props = proposals_dir(swarm)
    for s in ids:
        if not ID_ARG.match(s):
            raise Error(f"invalid id: {s}")
        p = props / f"{s}.json"
        if not p.is_file():
            raise Error(f"{p} is missing: first {command_line(swarm, 'approve', '<card>')}")
        entries.append(P.entry_v2(json.loads(p.read_text(encoding="utf-8"))))
    for v in entries:
        if P.english_problems(v):
            raise Error(msg(swarm, "cli_needs_english", id=v["id"],
                            command=command_line(swarm, "translate", v["id"], "<file.json>", "--language", "en")))
    words = require_forbidden(swarm)
    for v in entries:
        prob = S.public_problems(json.dumps(v, ensure_ascii=False), words)
        if prob:
            raise Error(f"{v['id']}: " + "; ".join(prob))
    pre = C.AGENT_PREFIXES[0]
    tpl = swarm / "docs" / lang / "_PR_PROPOSAL.md"
    listing = "\n".join(f"- `{pre}-{v['id']}` ({v['type']}{', ' + v['parent'] if v.get('parent') else ''}): "
                        f"{P.text(v, lang)['name']}" for v in entries)
    body = tpl.read_text(encoding="utf-8") if tpl.is_file() else "{entries}"
    body = body.replace("{entries}", listing).replace(C.OLD_PR_PLACEHOLDER, listing)
    out = props / f"PR-{'-'.join(ids)[:60]}.md"
    title = G.fmt(t.get("pr_title", "swarmer: {ids}"), ids=", ".join(ids))
    commit = G.fmt(t.get("commit_message", "swarmer: {ids}"), ids=", ".join(ids))
    for what, text in (("body", body), ("title", title), ("commit message", commit)):
        prob = S.public_problems(text, words)
        if prob:
            raise Error(f"the {what} of the proposal: " + "; ".join(prob))
    S.write(swarm, out, body)
    summary = G.fmt(ui.get("pr_summary", "pr_summary"), upstream=upstream or "<owner>/<repository>", n=len(entries),
                    ids=", ".join(f"{pre}-{v['id']}" for v in entries), path=out)
    if not send:
        return summary + "\n" + msg(swarm, "cli_proposal_written", path=out,
                                    command=command_line(swarm, "propose", *ids, "--send", "--yes"))
    name, mail = git_identity()
    if not yes:
        return summary + "\n" + G.fmt(ui.get("pr_not_sent", "pr_not_sent"), name=name or "?", mail=mail or "?",
                                      identity=f"{name or '?'} <{mail or '?'}>")
    if not shutil.which("gh") or not re.match(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", upstream):
        raise Error(f"sending needs an authenticated gh and {swarm.name}/UPSTREAM in the form <owner>/<repository>")
    with tempfile.TemporaryDirectory() as tmp:
        r = Path(tmp) / "r"
        subprocess.run(["gh", "auth", "status"], check=True, stdin=subprocess.DEVNULL)
        subprocess.run(["gh", "repo", "clone", upstream, str(r)], check=True, stdin=subprocess.DEVNULL)
        S.check_no_links(r)
        branch = f"proposal-{'-'.join(ids)[:40]}"
        subprocess.run(["git", "-C", str(r), "checkout", "-b", branch], check=True)
        d = P.load(r / "db")
        before = [x["id"] for x in d["entries"]]
        d["entries"] += [v for v in entries if v["id"] not in set(before)]
        err = P.validate(d, G.available_languages(r), existing=before)
        if err:
            raise Error("the entries are not valid in the repository: " + "; ".join(err[:5]))
        P.save(d, r / "db")
        build(r, r / "swarmer.sh", extra_words=words)
        errors = verify(r, extra_words=words)
        if errors:
            raise Error("the clone does not pass the verification: " + "; ".join(errors[:5]))
        if not name or not mail:
            raise Error("a global git identity is needed (user.name and user.email): it is the one the commit publishes")
        add = [f"db/{P.DB_FILE}", "swarmer.sh"] + ([C.OLD_MARKS["script"]] if (r / C.OLD_MARKS["script"]).is_file()
                                                    else [])
        subprocess.run(["git", "-C", str(r), "add", *add], check=True)
        diff = subprocess.run(["git", "-C", str(r), "diff", "--cached", "--stat"], capture_output=True, text=True).stdout
        print(f"Sending to {upstream} as «{name} <{mail}>»:\n{diff}")
        who = {"GIT_AUTHOR_NAME": name, "GIT_AUTHOR_EMAIL": mail, "GIT_COMMITTER_NAME": name, "GIT_COMMITTER_EMAIL": mail}
        subprocess.run(["git", "-C", str(r), "commit", "-m", commit], check=True, env=dict(os.environ, **who))
        signed = subprocess.run(["git", "-C", str(r), "log", "-1", "--format=%an <%ae>|%cn <%ce>"], capture_output=True,
                                text=True, check=True).stdout.strip()
        if signed != f"{name} <{mail}>|{name} <{mail}>":
            raise Error(f"the commit is signed «{signed}», not «{name} <{mail}>»: not sending it")
        subprocess.run(["gh", "repo", "fork", "--remote", "--remote-name", "fork"], check=True, cwd=r,
                       stdin=subprocess.DEVNULL)
        subprocess.run(["git", "-C", str(r), "push", "-u", "fork", branch], check=True)
        subprocess.run(["gh", "pr", "create", "--repo", upstream, "--title", title, "--body-file", str(out)], check=True,
                       cwd=r, stdin=subprocess.DEVNULL)
    return f"pull request opened on {upstream}"


# --- swarmer.sh, a single file ---

def _q(s: str) -> str:
    return "'" + str(s).replace("'", "'\\''") + "'"


def head_block(swarm: Path) -> str:
    """The block of head.sh between # @aliases-begin and # @aliases-end, generated from the sections of i18n and from
    compat.py: the aliases of the commands bash handles and of the options of install, the messages of bash by
    language, the 4.0 names that head.sh has to recognise."""
    al = A.load(swarm)
    lines = [BLOCK_BEGIN.rstrip("\n"),
             "# Generated by «build» from i18n/*.json and engine/compat.py: do not edit by hand."]

    def case_fn(name, pairs):
        out = [f"{name}() {{", '    case "$1" in']
        for canon, names in pairs:
            alts = "|".join(_q(x) for x in dict.fromkeys([canon] + names))
            out.append(f"        {alts}) printf '%s' {_q(canon)} ;;")
        out += ["        *) printf '%s' \"$1\" ;;", "    esac", "}"]
        return out
    lines += case_fn("canonical_command", [(c, al["commands"].get(c, [])) for c in BASH_COMMANDS])
    lines += case_fn("canonical_option", [(o, al["options"].get(o, [])) for o in INSTALL_OPTIONS])
    langs = sorted(set(G.available_languages(swarm)) | {"en"})
    for l in langs:
        t = G.i18n(swarm, l)
        lines += [f"msg_{l}() {{", '    case "$1" in']
        for k in sorted(k for k in t if (k.startswith("sh_") or k == "cli_prefix") and isinstance(t[k], str)):
            lines.append(f"        {k}) printf '%s' {_q(t[k])} ;;")
        lines += ["        *) printf '%s' \"$1\" ;;", "    esac", "}"]
    lines += ["default_folder() {", '    case "$1" in']
    for l in langs:
        if l != "en":
            lines.append(f"        {l}) printf '%s' {_q(S.localized_name(swarm, 'swarmer', l))} ;;")
    lines += ["        *) printf '%s' 'swarmer' ;;", "    esac", "}"]
    lines += [f"LANGUAGES=({' '.join(_q(l) for l in langs)})",
              f"SWARM_FOLDERS=({' '.join(_q(x) for x in S.all_names(swarm, 'swarmer'))})",
              f"STATE_DIRS=({' '.join(_q(x) for x in S.all_names(swarm, '.swarmer'))})",
              f"FOLDER_KEYS=({_q('folder')} {_q(C.CONFIG_SCHEMA.fields[('folder',)][1])})",
              f"ROOT_FILES=({_q('ROOT')} {_q(C.STATE_NAMES['ROOT'])})",
              f"FACTORY_FILES=({_q('FACTORY.json')} {_q(C.STATE_NAMES['FACTORY.json'])})",
              f"LANGUAGE_FILES=({_q('LANGUAGE')} {_q(C.STATE_NAMES['LANGUAGE'])})",
              f"ENGINES=({_q('engine/swarmer.py')} {_q(C.OLD_ENGINE)})",
              f"LANGUAGE_ENVS=({_q('SWARMER_LANGUAGE')} {_q(C.ENV_ALIASES['SWARMER_LANGUAGE'])})",
              BLOCK_END.rstrip("\n")]
    return "\n".join(lines) + "\n"


def with_block(text: str, block: str) -> str:
    i, j = text.find(BLOCK_BEGIN), text.find(BLOCK_END)
    if i < 0 or j < i:
        raise Error(f"{HEAD}: the markers {BLOCK_BEGIN.strip()} and {BLOCK_END.strip()} are missing or damaged")
    return text[:i] + block + text[j + len(BLOCK_END):]


def build(swarm: Path, output: Path, extra_words: list[str] | None = None, update_head: bool = True) -> Path:
    """Rebuilds swarmer.sh: the head (engine/head.sh, with the generated block) and the distributed files, in clear
    after the «exit» line. First it checks every file: no secrets, e-mails, machine paths, forbidden words, markers
    of swarmer.sh. In the repository it also refreshes the block of engine/head.sh and writes the 4.0 script name, a
    byte copy of swarmer.sh (for the old address)."""
    cache = {}
    head_src = distributed_content(swarm, HEAD, cache)
    # in an installation the head goes out as the factory has it: its block is never rebuilt from the i18n on disk
    head = head_src if installed(swarm) else with_block(head_src, head_block(swarm))
    if not installed(swarm) and update_head and head != head_src:
        S.write(swarm, swarm / HEAD, head)
        head_src = head
    parts = [head.rstrip("\n") + "\n", "exit\n",
             "# From here on are the files of the swarm, which «install» writes into the swarm folder. Bash never gets "
             "past «exit».\n",
             f": <<'{S.END_OF_FILES}'\n"]
    if installed(swarm):
        words = require_forbidden(swarm)
    else:
        words = S.forbidden(swarm, swarm)[0]
    words = words + list(extra_words or [])
    prob = S.public_problems(head, words)
    if prob or any(S.is_mark_line(r) for r in head.splitlines()):
        raise Error(f"{HEAD} (the head of swarmer.sh): " + "; ".join(prob or ["contains a marker line of swarmer.sh"]))
    distributed = files_to_distribute(swarm) + (["UPSTREAM"] if (swarm / "UPSTREAM").is_file() else [])
    for rel in distributed:
        S.no_links(swarm, swarm / rel)
        text = head_src if rel == HEAD else distributed_content(swarm, rel, cache)
        prob = name_problems(rel, words) + S.public_problems(text, words)
        if prob:
            raise Error(f"{rel}: " + "; ".join(prob))
        if any(S.is_mark_line(r) for r in text.splitlines()):
            raise Error(f"{rel}: contains a marker line of swarmer.sh")
        parts.append(f"{S.FILE_MARK} file {rel} ====\n" + text + ("" if text.endswith("\n") else "\n"))
    parts.append(f"{S.FILE_MARK} {S.END_OF_FILES_LINE} ====\n{S.END_OF_FILES}\n")
    output = Path(output)
    body = "".join(parts)
    S.write(output.parent, output, body, 0o755)
    if not installed(swarm) and output.name == "swarmer.sh":
        S.write(output.parent, output.parent / C.OLD_MARKS["script"], body, 0o755)
    return output


def build_check(swarm: Path, output: Path) -> int:
    """`build --check`: the block of engine/head.sh, swarmer.sh and (in the repository) its 4.0-named copy are up
    to date."""
    ok = True
    if not installed(swarm):
        h = swarm / HEAD
        fresh = with_block(h.read_text(encoding="utf-8"), head_block(swarm))
        same = fresh == h.read_text(encoding="utf-8")
        print(msg(swarm, "build_up_to_date" if same else "build_not_up_to_date", path=h))
        ok = ok and same
    with tempfile.TemporaryDirectory() as tmp:
        if not installed(swarm):
            # build from a copy of the head with a fresh block, without touching the tree
            fresh_out = Path(tmp) / "swarmer.sh"
            build(swarm, fresh_out, update_head=False)
            new = _fresh_with_block(swarm, fresh_out.read_bytes())
        else:
            new = build(swarm, Path(tmp) / "swarmer.sh", update_head=False).read_bytes()
    targets = [Path(output)]
    if not installed(swarm) and Path(output).name == "swarmer.sh":
        targets.append(Path(output).parent / C.OLD_MARKS["script"])
    for t in targets:
        same = t.is_file() and t.read_bytes() == new
        print(msg(swarm, "build_up_to_date" if same else "build_not_up_to_date", path=t))
        ok = ok and same
    return 0 if ok else 1


def _fresh_with_block(swarm: Path, data: bytes) -> bytes:
    """swarmer.sh as build would write it after refreshing engine/head.sh (the embedded copy too)."""
    h = (swarm / HEAD).read_text(encoding="utf-8")
    fresh = with_block(h, head_block(swarm))
    if fresh == h:
        return data
    text = data.decode("utf-8")
    mark = f"{S.FILE_MARK} file {HEAD} ====\n"
    i = text.find(mark)
    if i >= 0 and text[i + len(mark):].startswith(h):
        text = text[:i + len(mark)] + fresh + text[i + len(mark) + len(h):]
    return text.encode("utf-8")


def _placeholders(s: str) -> set[str]:
    return set(re.findall(r"\{([a-z_]+)\}", s))


def _compare_i18n(a, b, where: str, out: list[str], alias_section: bool = False) -> None:
    if isinstance(a, dict) and isinstance(b, dict):
        if not alias_section and set(a) != set(b):
            out.append(f"{where}: keys different from en.json: "
                       + ", ".join(sorted(set(a) ^ set(b))[:8]))
        for k in set(a) & set(b):
            _compare_i18n(a[k], b[k], f"{where}.{k}", out, alias_section)
    elif isinstance(a, str) and isinstance(b, str) and not alias_section:
        if _placeholders(a) != _placeholders(b):
            out.append(f"{where}: placeholders different from en.json")


def cli_namespaces() -> dict:
    """The namespaces of the command line (B): the commands of each parser, the options of each command, the values
    of each option."""
    empty = {"commands": {}, "options": {}, "values": {c: {} for c in A.VALUE_CATEGORIES}}
    out = {}
    import convene
    import jury
    parsers = {"swarmer": build_parser(empty), "convene": convene.build_parser(empty)}
    for pname, p in parsers.items():
        sub = next(a for a in p._actions if isinstance(a, argparse._SubParsersAction))
        out[pname] = {"commands": list(sub.choices)}
        for cname, q in sub.choices.items():
            opts = [o for a in q._actions for o in a.option_strings if o.startswith("--")]
            out[f"{pname} {cname}"] = {"options": opts}
    out["jury"] = {"commands": ["count", "requests"]}
    out["generate_agents"] = {"options": ["--check", "--install", "--instructions", "--remove-instructions",
                                          "--remove", "--list"]}
    for cat in A.VALUE_CATEGORIES:
        out[f"values {cat}"] = {f"values:{cat}": list(C.VALUES.get(cat, {}))}
    return out


def alias_collisions(swarm: Path) -> list[str]:
    """The alias collisions of every language and of their union (B): checked before the parser is built, which
    would stop on them with a traceback."""
    per_lang = A.per_language(swarm)
    union = {"commands": {}, "options": {}, "values": {}}
    for sec in per_lang.values():
        for k in ("commands", "options"):
            for c, names in sec[k].items():
                union[k].setdefault(c, [])
                union[k][c] += [x for x in names if x not in union[k][c]]
        for cat, m in sec["values"].items():
            for c, names in m.items():
                lst = union["values"].setdefault(cat, {}).setdefault(c, [])
                lst += [x for x in names if x not in lst]
    return A.collisions({**per_lang, "all": union}, cli_namespaces())


def verify(swarm: Path, publication: bool = False, extra_words: list[str] | None = None) -> list[str]:
    """The checks before publishing: database valid in every language, documents with the same blocks in every
    language, i18n keys and placeholders equal to en.json, no alias collision, every command in every help, no
    secret, e-mail, machine path, forbidden word or marker of swarmer.sh in all the public material (also README,
    CONTRIBUTING, .github, skills, .claude-plugin), swarmer.sh up to date; with --publication, no work folder in the
    tree."""
    errors = []
    d = P.load(swarm / "db")
    langs = G.available_languages(swarm)
    errors += P.validate(d, langs)
    blocks = {}
    for l in langs:
        for n in G.DOCUMENTS:
            p = swarm / "docs" / l / n
            if not p.is_file():
                errors.append(f"docs/{l}/{n} is missing")
                continue
            blocks.setdefault(n, {})[l] = set(G.blocks(p.read_text(encoding="utf-8")))
    for n, per in blocks.items():
        if len({frozenset(b) for b in per.values()}) > 1:
            errors.append(f"{n}: the blocks differ between the languages: " + "; ".join(f"{l}={sorted(b)}"
                                                                                       for l, b in per.items()))
    en_p = swarm / "i18n" / "en.json"
    en = json.loads(en_p.read_text(encoding="utf-8")) if en_p.is_file() else {}
    for l in langs:
        if l == "en":
            continue
        t = json.loads((swarm / "i18n" / f"{l}.json").read_text(encoding="utf-8"))
        if set(t) != set(en):
            errors.append(f"i18n/{l}.json: keys different from en.json: " + ", ".join(sorted(set(t) ^ set(en))[:8]))
        for k in set(t) & set(en):
            _compare_i18n(en[k], t[k], f"i18n/{l}.json:{k}", errors,
                          alias_section=k in ("commands", "options", "values", "files"))
    errors += alias_collisions(swarm)
    for l in langs:
        h = swarm / "docs" / l / "_HELP.txt"
        text = h.read_text(encoding="utf-8") if h.is_file() else ""
        for c in cli_namespaces()["swarmer"]["commands"]:
            if not re.search(rf"(?<![\w-]){re.escape(c)}(?![\w-])", text):
                errors.append(f"docs/{l}/_HELP.txt: no line for the command «{c}»")
    words = (forbidden(swarm) if installed(swarm) else S.forbidden(swarm, swarm)[0]) + list(extra_words or [])
    to_check = list(files_to_distribute(swarm))
    npub = not_published()
    scripts = ("swarmer.sh", C.OLD_MARKS["script"])
    if not installed(swarm):
        # the whole tree git would publish: every file, hidden ones too, except .git, the work folders and what
        # .gitignore excludes by folder or file name
        try:
            public = public_tree(swarm)
        except (C.Error, subprocess.CalledProcessError) as e:
            errors.append(str(e))
            public = []
        for rel in public:
            if rel in to_check or rel in scripts:
                continue
            if Path(rel).parts[0] in npub:
                errors.append(f"{rel}: a work folder that must not be published")
            if not S.FILE_NAME.match(rel):
                errors.append(f"file name not allowed: {rel!r}")
                continue
            to_check.append(rel)
    for rel in to_check:
        try:
            text = (swarm / rel).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append(f"{rel}: not text")
            continue
        prob = name_problems(rel, words) + S.public_problems(text, words)
        if rel.startswith(NOT_DISTRIBUTED):   # the fixtures of the tests carry the 4.0 markers on purpose
            prob = [x for x in prob if "marker" not in x]
        errors += [f"{rel}: {x}" for x in prob]
    with tempfile.TemporaryDirectory() as tmp:
        for l in langs:
            try:
                G.catalog(swarm, Path(tmp), l)
            except C.Error as e:
                errors.append(f"language {l}: {e}")
        if not installed(swarm) and (swarm / "swarmer.sh").is_file():
            try:
                new = _fresh_with_block(swarm, build(swarm, Path(tmp) / "swarmer.sh", extra_words=extra_words,
                                                     update_head=False).read_bytes())
                for n in scripts:
                    if (swarm / n).is_file() and new != (swarm / n).read_bytes():
                        errors.append(f"{n} is not up to date: build --output swarmer.sh")
                fresh = with_block((swarm / HEAD).read_text(encoding="utf-8"), head_block(swarm))
                if fresh != (swarm / HEAD).read_text(encoding="utf-8"):
                    errors.append(f"{HEAD}: the generated block is not up to date: build")
            except (C.Error, OSError) as e:
                errors.append(f"swarmer.sh: {e}")
    if publication:
        for name in npub + ("engine/__pycache__", "tests/__pycache__"):
            if (swarm / name).exists():
                errors.append(f"{name}: must not be in the tree to publish")
        if not installed(swarm):   # the repository: what an installation writes in a project is never published
            for name in TARGET_TREES:
                if (swarm / name).exists() or (swarm / name).is_symlink():
                    errors.append(f"{name}: a file of a target (agents, skills, instructions) must not be published")
    return errors


# --- the paragraph for the instruction files (CLAUDE.md, AGENTS.md, GEMINI.md) ---

def instructions(swarm: Path, file: Path, remove: bool = False) -> str:
    root = root_of(swarm)
    t = file.read_text(encoding="utf-8") if file.is_file() else ""
    found = []
    for l, (begin, end, begin_prefix) in C.CLAUDE_MARKS.items():
        i, j = t.find(begin_prefix), t.find(end)
        if i >= 0 or j >= 0:
            found.append((l, i, j, begin, end))
    if len(found) > 1:
        raise Error(f"{file}: two paragraphs of the swarm, in two dialects: fix them by hand")
    lang = language(swarm)
    if found:
        dl, i, j, begin, end = found[0]
    else:
        dl, i, j = lang, -1, -1
        begin, end, _ = C.CLAUDE_MARKS.get(lang, C.CLAUDE_MARKS["en"])
    if (i < 0) != (j < 0) or (i >= 0 and j < i):
        raise Error(f"{file}: the markers of the paragraph of the swarm are damaged, fix them by hand")
    if i < 0 and remove:
        return "not there"
    if remove:
        t = t[:i].rstrip("\n") + ("\n" if t[:i].strip() else "") + t[j + len(end):].lstrip("\n")
        if not t.strip():   # only the paragraph of the swarm was there: the file goes
            S.remove_file(root, file)
        else:
            S.write(root, file, t)
        return "removed"
    par = (swarm / "docs" / lang / "_CLAUDE.md").read_text(encoding="utf-8")
    par = G.adapt({"names": {"swarm": S.localized_name(swarm, "swarmer", lang),
                             "local": S.localized_name(swarm, "local", lang),
                             "agents": S.localized_name(swarm, "AGENTS.md", lang)},
                   "folder": swarm.resolve().relative_to(root.resolve()).as_posix(),
                   "local_folder": S.local_folder(root, swarm).resolve().relative_to(root.resolve()).as_posix(),
                   "local_file": S.local_agents_file(root, swarm).resolve().relative_to(root.resolve()).as_posix()},
                  par) if _inside(swarm, root) else par
    if i >= 0:   # in place, with the markers it had
        S.write(root, file, t[:i] + begin + "\n" + par.strip() + "\n" + end + t[j + len(end):])
        return "written"
    S.write(root, file, (t.rstrip("\n") + "\n\n" if t.strip() else "") + begin + "\n" + par.strip() + "\n" + end + "\n")
    return "written"


def instruction_files(swarm: Path, targets: list[str] | None = None) -> list[Path]:
    """The instruction files of the targets (CLAUDE.md, AGENTS.md, GEMINI.md), each once."""
    root = root_of(swarm)
    targets = G.targets_of(root) if targets is None else targets
    return [root / n for n in dict.fromkeys(G.TARGETS[tg]["instructions"] for tg in targets)]


def all_instructions(swarm: Path, remove: bool = False) -> None:
    """The paragraph in the instruction file of every active target; with remove, out of every file that has it."""
    files = instruction_files(swarm, list(G.TARGETS) if remove else None)
    for f in files:
        if remove and not f.is_file():
            continue
        print(f"{f.name}: {instructions(swarm, f, remove)}")


def change_targets(swarm: Path, new: list[str], named=()) -> list[str]:
    """Writes the targets in config.json and regenerates: the generated files of a target removed go (only those
    with the note), and so does the paragraph of its instruction file, if no active target still reads that file.
    `named`: the targets the user removes by name, active or not (their generated files go too). Every folder is
    checked before the first write."""
    root = root_of(swarm)
    old = G.targets_of(root)
    clean = [x for x in G.TARGETS if (x in old or x in named) and x not in new]
    try:
        G.preflight(root, new, clean)
    except C.Error as e:
        raise Error(str(e))
    cfg = S.config(root)
    S.write_config(root, dict(cfg, targets=new), language(swarm))
    regenerate(swarm, clean=clean)
    keep = {f.name for f in instruction_files(swarm, new)}
    for f in instruction_files(swarm, old):
        if f.name not in keep and f.is_file():
            instructions(swarm, f, remove=True)
    return new


def _inside(swarm: Path, root: Path) -> bool:
    try:
        swarm.resolve().relative_to(root.resolve())
        S.local_folder(root, swarm).resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


# --- the command line ---

def build_parser(al: dict) -> argparse.ArgumentParser:
    p = A.parser(prog="swarmer", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument(*A.option_strings(al, "--swarm"), dest="swarm", type=Path, default=SWARM, help=argparse.SUPPRESS)
    add = A.subparsers(p, al)
    for c in ("install", "update"):
        q = add(c)
        A.arg(q, al, "--from", dest="src", type=Path, required=True)
        A.arg(q, al, "--root", type=Path, required=True)
        A.arg(q, al, "--folder")
        A.arg(q, al, "--language")
        A.arg(q, al, "--force", action="store_true")
        A.arg(q, al, "--instructions", action="store_true")
        A.arg(q, al, "--local", help="the folder (or the AGENTS.md file) of the local overrides, relative to the root")
        A.arg(q, al, "--project-managed", action="store_true",
              help="the agents of the overrides are generated by the project: the swarm does not write them")
        A.arg(q, al, "--targets", help="claude,codex,antigravity,gemini,agents or auto")
    for s in G.STRATEGIES:
        q = add(s)
        q.add_argument("request", nargs="?")
        A.arg(q, al, "--profile")
        A.arg(q, al, "--roles")
        A.arg(q, al, "--from-file")
        A.arg(q, al, "--model")
        A.arg(q, al, "--language")
        A.arg(q, al, "--print", action="store_true")
        A.arg(q, al, "--show", action="store_true")
        A.arg(q, al, "--cli", help="claude, codex, agy or gemini")
        q.set_defaults(rest=[])   # what follows «--» goes to the tool (split_rest)
    add("help")
    q = add("language")
    q.add_argument("code", nargs="?")
    q = add("roles")
    q.add_argument("question", nargs="?")
    add("professionals")
    add("check")
    q = add("regenerate")
    A.arg(q, al, "--targets", help="claude,codex,antigravity,gemini,agents or auto")
    add("remove")
    q = add("targets")
    q.add_argument("value", nargs="?", help="the list of the targets, comma-separated, or auto")
    A.arg(q, al, "--add")
    A.arg(q, al, "--remove")
    q = add("instructions")
    A.arg(q, al, "--remove", action="store_true")
    q = add("models")
    q.add_argument("assignments", nargs="*")
    A.arg(q, al, "--all")
    add("requests")
    q = add("count")
    q.add_argument("folder")
    q.add_argument("round")
    q = add("approve")
    q.add_argument("file", type=Path)
    A.arg(q, al, "--without-script", action="store_true")
    A.arg(q, al, "--generic-from-local", action="store_true",
          help="the entry is the generic version, without details of the project, of a local card")
    q = add("propose")
    q.add_argument("ids", nargs="+")
    A.arg(q, al, "--send", action="store_true")
    A.arg(q, al, "--yes", action="store_true", help="confirms the sending of the pull request")
    A.arg(q, al, "--language")
    q = add("build")
    A.arg(q, al, "--output", type=Path)
    A.arg(q, al, "--check", action="store_true", help="exits with 1 if swarmer.sh is not up to date")
    q = add("verify")
    A.arg(q, al, "--publication", action="store_true", help="also: no work folder in the tree")
    add("tests")
    q = add("import-cards")
    q.add_argument("file", type=Path)
    q = add("translate")
    q.add_argument("id")
    q.add_argument("file", type=Path)
    A.arg(q, al, "--language")
    return p


def _swarm_from_argv(argv: list[str]) -> Path:
    al = A.load(SWARM)
    names = A.option_strings(al, "--swarm")
    for i, a in enumerate(argv):
        if a in names and i + 1 < len(argv):
            return Path(argv[i + 1])
        for n in names:
            if a.startswith(n + "="):
                return Path(a[len(n) + 1:])
    return SWARM


def split_rest(argv: list[str], al: dict) -> tuple[list[str], list[str]]:
    """For a strategy: the options of the swarm may come before or after the request; only what follows the first
    «--» after the command goes to the tool. Any other command: argv as it is."""
    names = A.option_strings(al, "--swarm")
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in names:
            i += 2
            continue
        if any(a.startswith(n + "=") for n in names):
            i += 1
            continue
        break
    if i >= len(argv):
        return argv, []
    strategies = set(G.STRATEGIES) | {x for s in G.STRATEGIES for x in A.command_aliases(al, s)}
    if argv[i] not in strategies or "--" not in argv[i + 1:]:
        return argv, []
    j = argv.index("--", i + 1)
    return argv[:j], argv[j + 1:]


def main(argv=None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    pre = _swarm_from_argv(argv).resolve()
    pre = pre if (pre / "i18n").is_dir() else SWARM
    bad = alias_collisions(pre)
    if bad:
        print(msg(pre, "cli_prefix") + "\n".join(bad), file=sys.stderr)
        sys.exit(1)
    al = A.load(pre)
    argv, rest = split_rest(argv, al)
    ns = build_parser(al).parse_args(argv)
    if getattr(ns, "command", None) in G.STRATEGIES:
        ns.rest = rest
    swarm = ns.swarm.resolve()
    try:
        c = ns.command
        if c in ("install", "update"):
            s = install(ns.src.resolve(), ns.root.resolve(), ns.folder, ns.language, ns.force, ns.local,
                        ns.project_managed, ns.targets)
            if ns.instructions:
                all_instructions(s)
        elif c in G.STRATEGIES:
            launch(swarm, c, ns)
        elif c == "help":
            lang = language(swarm)
            for l in dict.fromkeys((lang, "en")):
                h = swarm / "docs" / l / "_HELP.txt"
                if h.is_file():
                    print(h.read_text(encoding="utf-8"), end="")
                    break
        elif c == "language":
            langs = G.available_languages(swarm)
            if not ns.code:
                print(msg(swarm, "cli_language_current", language=language(swarm), languages=", ".join(langs)))
            else:
                if ns.code not in langs:
                    raise Error(msg(swarm, "cli_language_unknown", language=ns.code, languages=", ".join(langs)))
                require_installed(swarm)
                S.write(swarm, swarm / "LANGUAGE", ns.code + "\n")
                old = swarm / C.STATE_NAMES["LANGUAGE"]
                if old.is_file():
                    S.remove_file(swarm, old)
                if ns.code == "it":
                    ensure_alias_stubs(swarm)
                regenerate(swarm)
                print(msg(swarm, "cli_language_changed", language=ns.code))
        elif c == "roles":
            import convene
            convene.main(["roles"] + (["--question", ns.question] if ns.question else []))
        elif c == "professionals":
            d = P.load(swarm / "db")
            l = language(swarm)
            pre_ = G.prefix_of(root_of(swarm), l) if installed(swarm) else C.AGENT_PREFIXES[0]
            for v in P.ordered(d):
                indent = "    " if v["type"] == "subprofessional" else ""
                print(f"{indent}{v['number']}. {pre_}-{v['id']}: {P.text(v, l)['name']}")
        elif c == "check":
            sys.exit(check(swarm))
        elif c == "regenerate":
            clean = []
            if ns.targets:
                require_installed(swarm)
                root = root_of(swarm)
                wanted = G.parse_targets(ns.targets)
                new = G.detect_targets(root) if wanted is None else wanted
                clean = [x for x in G.targets_of(root) if x not in new]
                try:
                    G.preflight(root, new, clean)
                except C.Error as e:
                    raise Error(str(e))
                S.write_config(root, dict(S.config(root), targets=new), language(swarm))
            data, done = regenerate(swarm, clean=clean)
            print(msg(swarm, "cli_aligned", roles=len(data["roles"]), profiles=len(data["profiles"])))
            pending_translations(swarm, data)
            skipped = [f for f in done if f.startswith("skipped")]
            if skipped:
                print(msg(swarm, "cli_skipped", n=len(skipped)))
        elif c == "remove":
            require_installed(swarm)
            for f in instruction_files(swarm, list(G.TARGETS)):
                S.no_links(root_of(swarm), f)
            removed = G.remove(root_of(swarm))
            for f in instruction_files(swarm, list(G.TARGETS)):
                if f.is_file():
                    instructions(swarm, f, remove=True)
            print(msg(swarm, "cli_removed", n=len(removed), path=swarm,
                      state=S.state_dir(root_of(swarm), language(swarm)).name))
        elif c == "instructions":
            require_installed(swarm)
            all_instructions(swarm, ns.remove)
        elif c == "targets":
            require_installed(swarm)
            root = root_of(swarm)
            now = G.targets_of(root)
            if ns.value or ns.add or ns.remove:
                if ns.value:
                    wanted = G.parse_targets(ns.value)
                    new = G.detect_targets(root) if wanted is None else wanted
                else:
                    new = list(now)
                if ns.add:
                    added = G.parse_targets(ns.add)
                    new = G.parse_targets(sorted(set(new) | set(G.detect_targets(root) if added is None else added)))
                gone = set()
                if ns.remove:
                    named = G.parse_targets(ns.remove)
                    if named is None:
                        raise Error(msg(swarm, "cli_targets_remove_auto"))
                    gone = set(named)
                    new = [x for x in new if x not in gone]
                if not new:
                    raise Error(msg(swarm, "cli_targets_empty"))
                if new != now or gone:
                    change_targets(swarm, new, sorted(gone))
                print(msg(swarm, "cli_targets_changed", targets=", ".join(new)))
            else:
                print(msg(swarm, "cli_targets", targets=", ".join(now)))
                print(msg(swarm, "cli_targets_detected", targets=", ".join(G.detect_targets(root)),
                          all=", ".join(G.TARGETS)))
        elif c == "models":
            require_installed(swarm)
            root = root_of(swarm)
            cfg = S.config(root)
            m = dict(cfg.get("models", {}))
            assignments = list(ns.assignments) + ([f"*={ns.all}"] if ns.all else [])
            for a in assignments:
                who, _, val = a.partition("=")
                if not val or not G.MODEL_RE.match(val) or not re.match(r"^[a-z0-9*][a-z0-9-]*$", who):
                    raise Error(f"form: role=model, core=model or --all model, with simple names ({a})")
                m[who] = val
            if assignments:
                S.write_config(root, dict(cfg, models=m), language(swarm))
                regenerate(swarm)
            print(json.dumps(m, ensure_ascii=False, indent=1) if m else msg(swarm, "cli_models_none"))
        elif c in ("requests", "count"):
            import jury
            jury.main(["requests", str(S.find_project_file(swarm, "EXPERT_REQUESTS.md", language(swarm), swarm))]
                      if c == "requests" else ["count", ns.folder, ns.round])
        elif c == "approve":
            print(approve(swarm, ns.file, not ns.without_script, ns.generic_from_local))
        elif c == "propose":
            print(propose(swarm, ns.ids, ns.send, ns.yes, ns.language))
        elif c == "translate":
            print(translate(swarm, ns.id, ns.file, ns.language))
        elif c == "build":
            output = ns.output or swarm / "swarmer.sh"
            if ns.check:
                sys.exit(build_check(swarm, output))
            print(build(swarm, output))
        elif c == "verify":
            errors = verify(swarm, ns.publication)
            print("\n".join(errors) if errors else msg(swarm, "verify_clean"))
            sys.exit(1 if errors else 0)
        elif c == "tests":
            rc = 0
            for t in sorted((swarm / "tests").glob("test_*.py")):
                rc = subprocess.run([sys.executable, "-I", "-B", str(t)]).returncode or rc
            sys.exit(1 if rc else 0)
        elif c == "import-cards":
            # The cards of a 3.x AGENTS.md that the database does not have belong to the project: they go into the
            # local overrides, never into the public database.
            require_installed(swarm)
            root = root_of(swarm)
            d = P.load(swarm / "db")
            known = {v["id"] for v in d["entries"]}
            dest = S.local_agents_file(root, swarm)
            already = P.local_cards(dest)
            new = [s for s in P.local_cards(ns.file).values() if s["id"] not in known and s["id"] not in already]
            bad = [s["id"] for s in new if s["id"] in P.RESERVED]
            if bad:
                raise Error("reserved ids, rename the cards: " + ", ".join(bad))
            if new:
                pre_ = G.prefix_of(root, language(swarm))
                cards = [re.sub(r"— `(?:" + P.PREFIX_ALT + r")-", f"— `{pre_}-", s["card"], count=1) for s in new]
                text = dest.read_text(encoding="utf-8") if dest.is_file() else "# Local cards\n"
                text = text.rstrip("\n") + "\n\n" + "\n\n".join(cards) + "\n"
                S.write(root, dest, text)
                regenerate(swarm)
            print(msg(swarm, "cli_cards_imported", n=len(new), path=dest))
    except (C.Error, OSError, json.JSONDecodeError, subprocess.CalledProcessError) as e:
        lang = _target_language(ns) if ns.command in ("install", "update") else None
        prefix = G.fmt(G.i18n(swarm, lang).get("cli_prefix", "swarmer: ")) if lang else msg(swarm, "cli_prefix")
        print(f"{prefix}{e}", file=sys.stderr)
        sys.exit(1)


def _target_language(ns) -> str | None:
    """The language of the installation that install/update writes (the option, its LANGUAGE, it for a 4.0): the
    swarm that runs is the extracted source, which has none."""
    if ns.language:
        return ns.language
    try:
        t = S.valid_folder(ns.root.resolve(), ns.folder or detect_folder(ns.root.resolve()))
    except (C.Error, OSError, ValueError):
        return None
    if any((t / n).is_file() for n in ("LANGUAGE", C.STATE_NAMES["LANGUAGE"])):
        return C.language(t)
    return "it" if (t / C.STATE_NAMES["FACTORY.json"]).is_file() else None


if __name__ == "__main__":
    main()
