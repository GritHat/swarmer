#!/usr/bin/env python3
"""swarmer: prepares the skeleton of a convening (single, fan-out, classic or full) and checks its gates. Jury
and plenary are counted with jury.py.

It is the general form of the convening as a graph. It keeps:
- the blind lanes, with the canaries and the map known only to the coordinator;
- the snapshot of the reads;
- the seals;
- the gates bound with sha256;
- the selection only from the triage;
- the early closure of the branches.

It launches no agent and approves nothing by itself. Standard library only, no network.

Dialects (C.4): a convening with MANIFEST.json is English (CONTRACT.md, DELIVERABLE.md, SEALS.jsonl …); one with
the 4.0 manifest keeps the 4.0 names and keys (compat.CONVENE_FILES). A new convening is born in the language of the installation; an
existing one is read in either dialect and rewritten in its own. The briefs are written in the language of the
installation.

Commands (the paths become absolute):
  roles     [--question TEXT]     the roles and the profiles; with the question, the roles whose keywords appear in it
  prepare   --name N --strategy single|fan-out|classic|full --profile P --question TEXT [--roles a,b] [--dest D]
            [--seed S] [--n N --form slices|race|mixed --rule first|ranking|best]   (fan-out)
  snapshot  C                     as soon as the lanes have delivered, before reading them
  gate      C PHASE --notes TEXT [--not-delivered ROLE,…] [--verify] [--rules 1|2|3]
            PHASE = f0, A1 (the amendment AMENDMENT_1.md or AMENDMENT_A1.md), f1, f2, f3/H-001, f4/H-001, f5
            (f4/H-001 is the branch's latest round, f5 the latest closure or the next one: see the rounds below)
  seal      C FILE…               time and sha256 in SEALS.jsonl
  contradiction C FILE… --question TEXT   allocates the next K# of the convening in CONTRADICTIONS.jsonl
  select    C H-001 [H-002 H-003] [--radical H-00x] [--owner ID]   (once: a second select is refused)
  fund      C H-00x [--owner ID]  briefs the radical branch (gate rules 2: select does not brief it)
  close-branch C H-00x --reason TEXT [--deciding-test TEXT]   (on a closure of 5.0 without a test: adds the test)
  repin     C H-00x [--owner ID]  opens the next round of the f4 of a branch, on a revised pin, in f4_<n>/H-00x/
  status    C

The rules of the gates have a version (the manifest key gate_rules; a missing key means 1). A new convening is born
with the rules 3; a gate is always recomputed under the rules it was approved with, so upgrading the engine never
invalidates an approved gate. `gate --rules 2` (or 3) applies those rules to one new gate of an older convening.

The rounds (5.3). A branch re-pinned with `repin` has a round 2 of f4 in f4_2/<H#>/ (then f4_3/ …), with its own
briefs, dossier and gate GATE_f4_2_<H#>.json; its G4 runs under the rules 3 and binds only the round's own files, and
the branch's state is its latest round. After a G5 that holds and records «not closed», `fund`, `close-branch` and
`repin` act again and brief the next closure in f5_2/ (then f5_3/ …); once that folder exists `gate f5` checks it and
approves it into GATE_f5_2.json, created exclusively: GATE_f5.json and every file it binds stay as they are. The
latest G5 is the one of the highest ordinal in its file name. Rounds are read from the folders and gate files, so the
manifest keeps the keys of 5.2.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import random
import re
import secrets
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import aliases as A  # noqa: E402
import compat as C  # noqa: E402
import paths as S  # noqa: E402

BASE = HERE.parent if HERE.name in ("engine", C.OLD_TREE["engine"]) else HERE   # the swarm folder, with catalog.json
STRATEGIES = ("single", "fan-out", "classic", "full")
FORMS = ("slices", "race", "mixed")
RULES = ("first", "ranking", "best")
CONTRACT_FIELDS = tuple(C.CONVENE_LINES["contract_fields"])   # canonical (English) headings
TO_FILL = tuple(C.CONVENE_LINES["to_fill_in"].values())
ID = re.compile(r"\bH-?0*(\d{1,3})\b")
# A K# of the registry: K-001, as the allocator writes it, or K-01 and K-1 (ENG-15); not K-001-3, a K# numbered by its
# branch, which is a token of its own (KTOKEN) and never names K-001.
KID = re.compile(r"\bK-0*(\d{1,3})\b(?!-\d)")
KTOKEN = re.compile(r"\bK-\d+(?:-\d+)*\b")
LIMIT_F1 = 40   # minutes for a brief of f1
LIMIT_BRANCH = 60
GATE_RULES = 3   # the rules of the gates a new convening is born with
FILES_PER_FOLDER = 200   # a folder with more regular files than this is bound as one tree entry
PROVEN = ("proven", "verified")   # the Correctness values that count as «proven»
# Folders that do not belong to the convening's own files: the declared workspace of a role, the state folder of a
# nested installation, a nested convening, git.
WORK_NAMES = ("work", C.CONVENE_FILES["work"])
STATE_DIRS = (".swarmer", C.FILE_NAMES["it"][".swarmer"])
MANIFESTS = ("MANIFEST.json", C.CONVENE_FILES["MANIFEST.json"])
SKIP_DIRS = (".git", "__pycache__")
STATUS_NAMES = ("status.md", C.CONVENE_FILES["status.md"])
SENTINEL_DIRS = ("00-sentinel", C.CONVENE_FILES["00-sentinel"])
SENTINEL_NAMES = ("SENTINEL.md", C.CONVENE_FILES["SENTINEL.md"])
PHASE_SENTINELS = ("f2", "f3", "f4")   # the phases with a sentinel of their own under the rules 3 (ENG-17)
HIDDEN_NAMES = ("HIDDEN_ASSUMPTIONS.md", C.CONVENE_FILES["HIDDEN_ASSUMPTIONS.md"])
AMENDMENT_RE = re.compile("|".join(f"(?:{p[0]})|(?:{p[2]})" for p in C.CONVENE_PATTERNS if p[1].startswith("AMENDMENT")))
# The output of each briefed folder NN-<role> of a round of f4, by its two digits (select and repin write them so):
# what the predictions of that folder are ordered against under the rules 3 (ENG-19).
F4_OUTPUTS = {"00": "REVISION.md", "01": "COUNTERCHECKS.md", "02": "DEFECTS.md", "08": "HIDDEN_ASSUMPTIONS.md",
              "09": "VERDICT.md"}
F4_MEASUREMENTS = "MEASUREMENTS.md"   # the output of the other folders (03-07)
# A round after the first (5.3): f4_<n>/<H#> of a branch, f5_<n> of the closure; n in ASCII digits, never U+0663.
ROUND_RE = re.compile(r"(f[45])_([1-9][0-9]*)(/H-[0-9]{3})?", re.ASCII)
G5_LATER = re.compile(r"GATE_f5_([0-9]+)\.json", re.ASCII)


class Error(C.Error):
    pass


class _Keep(dict):
    def __missing__(self, k):
        return "{" + k + "}"


def language() -> str:
    """The language of the swarm (LANGUAGE, then SWARMER_LANGUAGE): the briefs and the contract are written in it."""
    return C.language(BASE)


def texts() -> dict:
    out = {}
    for l in dict.fromkeys(("en", language())):
        p = BASE / "i18n" / f"{l}.json"
        if not p.is_file():
            continue
        try:
            t = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for k, v in t.items():
            out[k] = {**out[k], **v} if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def T(key: str, **kw) -> str:
    """A text of the section "convene" of i18n (a missing key gives the key itself)."""
    v = texts().get("convene", {}).get(key, key)
    try:
        return str(v).format_map(_Keep(kw))
    except (ValueError, IndexError):
        return str(v)


def mission(key: str, **kw) -> str:
    v = texts().get("missions", {}).get(key, key)
    try:
        return str(v).format_map(_Keep(kw))
    except (ValueError, IndexError):
        return str(v)


def swarmer_version() -> str:
    """The version of swarmer (ENG-14): the first word of the swarm's VERSION, which install and regenerate write from
    engine/generate.py, the one place the version is written; in a source tree, which has no VERSION, that module's.
    The manifest key «version» is this stamp, the swarmer that prepared the convening: no engine reads it, and it is
    not a format version (the dialect is told by the file names and keys, the gates by gate_rules)."""
    p = BASE / "VERSION"
    words = p.read_text(encoding="utf-8", errors="replace").split() if p.is_file() else []
    if words and re.fullmatch(r"\d+\.\d+", words[0]):
        return words[0]
    import generate as G
    return G.VERSION


def now() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def norm_id(s: str) -> str:
    m = re.fullmatch(r"H-?0*(\d{1,3})", s.strip(), re.I)
    if not m:
        raise Error(f"malformed ID: {s} (the form is H-001)")
    return f"H-{int(m.group(1)):03d}"


def catalog() -> dict:
    """The roles and the profiles: the catalog of the swarm folder, written by regenerate."""
    p = BASE / "catalog.json"
    if not p.exists():
        if (BASE / C.STATE_NAMES["catalog.json"]).exists():
            raise Error(f"{BASE} has only the catalog of the 4.0: bash swarmer.sh update")
        raise Error(f"{p} not found: bash swarmer/swarmer.sh regenerate writes it")
    return json.loads(p.read_text(encoding="utf-8"))


def root_dir() -> Path:
    v = C.env("SWARMER_ROOT")
    if v:
        return Path(v)
    for n in ("ROOT", C.STATE_NAMES["ROOT"]):
        p = BASE / n
        if p.is_file():
            return (BASE / p.read_text(encoding="utf-8").strip()).resolve()
    return BASE.parent


def prefix() -> str:
    try:
        return catalog().get("prefix") or C.AGENT_PREFIXES[0]
    except (Error, OSError, json.JSONDecodeError):
        return C.AGENT_PREFIXES[0]


def shown(cat: str, v: str) -> str:
    """A controlled value in the language of the installation (for the texts, not for the data)."""
    lang = language()
    return v if lang == "en" else C.VALUES.get(cat, {}).get(v, v)


# --- a convening and its dialect ---

class Convening:
    def __init__(self, folder: Path, lang: str | None = None, m: dict | None = None):
        self.folder = Path(folder)
        self.lang = lang or C.convene_dialect(self.folder)
        self.m = m

    @classmethod
    def load(cls, folder) -> "Convening":
        folder = Path(folder)
        try:
            lang = C.convene_dialect(folder)
        except C.Error as e:
            raise Error(f"{folder} is not a convening ({e})")
        c = cls(folder, lang)
        p = c.file("MANIFEST.json")
        c.m = C.to_canonical(json.loads(p.read_text(encoding="utf-8")), C.MANIFEST_SCHEMA, p.name)
        c.m.setdefault("selected", [])
        c.m.setdefault("radical", None)
        return c

    def save(self) -> None:
        out = C.to_dialect(self.m, C.MANIFEST_SCHEMA, self.lang)
        write_whole(self.file("MANIFEST.json"), json_bytes(out, 1) + b"\n")

    def name(self, canonical: str) -> str:
        return C.localize_path(canonical, self.lang, "convene")

    def file(self, canonical: str) -> Path:
        return self.folder / self.name(canonical)

    def read_json(self, p: Path, kind: str) -> dict:
        return C.to_canonical(json.loads(p.read_text(encoding="utf-8")), C.CONVENE_KEYS[kind], p.name)

    def write_json(self, p: Path, data: dict, kind: str, indent=1) -> None:
        """A JSON file of the convening (a gate, the snapshot, the map, an early closure), written whole or not at
        all (ENG-13)."""
        write_whole(p, json_bytes(C.to_dialect(data, C.CONVENE_KEYS[kind], self.lang), indent))

    def create_json(self, p: Path, data: dict, kind: str, indent=1) -> None:
        """A file that must not exist yet (the gate of a new closure): created exclusively, never over another one.
        The bytes are made first, and a write that fails removes the file it created, so none is left half written."""
        raw = json_bytes(C.to_dialect(data, C.CONVENE_KEYS[kind], self.lang), indent)
        with open(p, "xb") as f:
            try:
                f.write(raw)
                f.flush()
            except BaseException:
                f.close()
                os.unlink(p)
                raise


SURROGATE = re.compile("[\ud800-\udfff]")


def json_bytes(data, indent=1) -> bytes:
    """The UTF-8 bytes of a JSON file of the convening (ENG-13). A file name that is not UTF-8 reaches the engine with
    its bytes as lone surrogates (surrogateescape); each is written as its JSON escape (\\udcff), the form
    ensure_ascii writes, so the file stays UTF-8 and json.loads gives back the same name. Everything else is written
    as before, byte for byte."""
    text = json.dumps(data, ensure_ascii=False, indent=indent)
    return SURROGATE.sub(lambda mt: f"\\u{ord(mt.group()):04x}", text).encode("utf-8")


def write_whole(p: Path, raw: bytes) -> None:
    """Writes `p` whole or not at all: a temporary file beside it, then os.replace. A write that fails leaves the
    old file as it was and no temporary file (ENG-13: a failed approval left a gate file of 0 bytes, which no reader
    can read)."""
    tmp = p.with_name(f".{p.name}.{secrets.token_hex(4)}.tmp")
    try:
        with open(tmp, "xb") as f:
            f.write(raw)
        os.replace(tmp, p)
    except BaseException:
        if os.path.lexists(tmp):
            os.unlink(tmp)
        raise


def brief(conv: Convening, folder: Path, role: str, phase: str, output: str, text: str, inputs: list[Path],
          *, canary: str | None = None, minutes: int = LIMIT_F1, h: str | None = None,
          output_path: Path | None = None) -> Path:
    """TASK.md of an agent, in the language of the installation; the files keep the names of the dialect."""
    folder.mkdir(parents=True, exist_ok=True)
    out = folder / conv.name("TASK.md")
    out.write_text(brief_text(conv, folder, role, phase, output, text, inputs, canary=canary, minutes=minutes, h=h,
                              output_path=output_path), encoding="utf-8")
    BRIEFED.append(role)
    return out


def brief_text(conv: Convening, folder: Path, role: str, phase: str, output: str, text: str, inputs: list[Path],
               *, canary: str | None = None, minutes: int = LIMIT_F1, h: str | None = None,
               output_path: Path | None = None) -> str:
    """The text of a TASK.md, written by nothing: `brief` writes it, `close_branch` compares it."""
    m = conv.m
    lang = language()
    lines = []
    if canary:
        lines += [f"{C.CONVENE_LINES['canary'].get(lang, C.CONVENE_LINES['canary']['en'])} {canary}", "",
                  T("canary"), ""]
    lines += [
        f"# {T('brief')}: {role}, {T('phase')} {phase}" + (f", {h}" if h else ""),
        "",
        f"- **{T('agent')}:** `{prefix()}-{role}`",
        f"- **{T('convening')}:** {m['name']} ({T('strategy')} {shown('strategy', m['strategy'])}, {T('profile')} "
        f"{shown('profile', m['profile'])})",
        f"- **{T('question')}:** {m['question']}",
        f"- **{T('inputs')}**",
        *[f"  - `{p}`" for p in inputs],
        f"- **{T('output')}:** `{output_path or folder / conv.name(output)}`, {T('output_tail')}",
        f"- **{T('time')}:** {T('at_most')} {minutes} {T('time_tail')}",
        f"- **{T('write')}** `{folder}`. {T('write_tail')}",
        f"- **{T('forbidden')}** {T('forbidden_tail')}",
        f"- **{T('criterion')}** {T('criterion_tail')}",
        f"- **{T('outcome')}** {T('outcome_tail')}",
        "",
        f"## {T('what')}",
        "",
        text,
        "",
    ]
    return "\n".join(lines)


BRIEFED: list[str] = []   # the roles that received a brief in this run


def translation_notice(cat: dict, roles_: list[str]) -> str | None:
    """The roles of a convening whose agent was generated from the English text, waiting for the translation into the
    language of the installation (K.2): the coordinator translates them before launching them (K.3)."""
    pending = [r for r in dict.fromkeys(roles_) if r in set(cat.get("translation_pending", []))]
    if not pending:
        return None
    lang = language()
    sec = A.per_language(BASE).get(lang, {}) if lang != "en" else {}
    command = (sec.get("commands", {}).get("translate") or ["translate"])[0]
    script = S.localized_name(BASE, "swarmer.sh", lang)
    if not (BASE / script).is_file():
        script = "swarmer.sh"
    try:
        folder = BASE.resolve().relative_to(root_dir().resolve()).as_posix()
    except ValueError:
        folder = BASE.name
    return T("translation_pending", language=cat.get("language", lang), roles=", ".join(f"{prefix()}-{r}" for r in pending),
             command=f"bash {folder}/{script} {command} <id> <file.json>")


def contract(m: dict, lang: str) -> str:
    title = (lambda f: f) if lang == "en" else (lambda f: C.CONVENE_LINES["contract_fields"][f])
    lines = [f"# {T('contract')} {m['name']}", "",
             f"{T('strategy').capitalize()}: {shown('strategy', m['strategy'])}. {T('created')}: {m['created']}.", ""]
    values = {"Question": m["question"], "Profile": m["profile"]}
    fill = C.CONVENE_LINES["to_fill_in"].get(lang, C.CONVENE_LINES["to_fill_in"]["en"])
    for f in CONTRACT_FIELDS:
        lines += [f"## {title(f)}", "", values.get(f, fill), ""]
    lines += [f"## {T('principles')}", "", T("principles_text"), ""]
    return "\n".join(lines)


def keyword_hits(role: dict, text: str) -> list[str]:
    """The keywords of a role found whole in a text, in any case: what `roles --question` shows, and what makes a
    role fit for the draw of a sentinel (ENG-16)."""
    t = text.lower()
    return list(dict.fromkeys(p.lower() for p in role.get("keywords", [])
                              if re.search(rf"(?<!\w){re.escape(p.lower())}(?!\w)", t)))


def roles(ns) -> None:
    """The roles, and the profiles. With a question, only the roles one of whose keywords appears in the text, whole."""
    cat = catalog()
    pre = cat.get("prefix") or prefix()
    cores = {n["id"]: n["name"].lower() for n in cat["cores"]}
    text = (ns.question or "").lower()
    found = 0
    for r in cat["roles"]:
        words = keyword_hits(r, text) if text else []
        if text and not words:
            continue
        found += 1
        print(T("roles_line", agent=f"{pre}-{r['id']}", name=r["name"], core=cores.get(r["core"], r["core"]),
                words=T("roles_words", words=", ".join(words)) if words else ""))
    if text and not found:
        print(T("roles_none"))
    print(T("profiles"))
    for name, p in cat["profiles"].items():
        print(T("profile_line", profile=name, **{"for": p["for"]}, roles=", ".join(p["A"])))


def prepare(ns) -> None:
    cat = catalog()
    al = A.load(BASE)
    ids = {r["id"] for r in cat["roles"]}
    profile = A.value(al, "profile", ns.profile)
    if profile not in cat["profiles"]:
        raise Error(f"unknown profile: {ns.profile} (they are: {', '.join(cat['profiles'])})")
    strategy = A.value(al, "strategy", ns.strategy)
    if strategy not in STRATEGIES:
        raise Error(f"strategy {ns.strategy}: one of {', '.join(STRATEGIES)}")
    form = A.value(al, "form", ns.form)
    rule = A.value(al, "rule", ns.rule)
    extra = [_role_id(r) for r in (ns.roles or "").split(",") if r.strip()]
    for r in extra:
        if r not in ids:
            raise Error(f"unknown role: {r}")
    prof = cat["profiles"][profile]
    seed = ns.seed if ns.seed is not None else secrets.randbelow(10**9)
    random.Random(seed)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
    name = re.sub(r"[^A-Za-z0-9_-]+", "-", ns.name).strip("-")[:40] or "convening"
    dest = Path(ns.dest).resolve() if ns.dest else S.state_dir(root_dir(), language()).resolve()
    lang = language()
    if strategy == "fan-out":
        if not ns.n or ns.n < 2 or ns.n > 16:
            raise Error("the fan-out wants --n between 2 and 16")
        if form not in FORMS or (form != "slices" and rule not in RULES):
            raise Error("the fan-out wants --form slices|race|mixed and, for race and mixed, --rule first|ranking|best")
    c = dest / f"{stamp}-{name}"
    if c.exists():
        raise Error(f"{c} already exists")
    c.mkdir(parents=True)
    conv = Convening(c, lang)
    m = {"version": swarmer_version(), "name": name, "strategy": strategy, "profile": profile, "question": ns.question,
         "seed": seed, "created": now(), "f1": {}, "selected": [], "radical": None, "gate_rules": GATE_RULES}
    conv.m = m
    conv.file("CONTRACT.md").write_text(contract(m, lang), encoding="utf-8")
    (c / "f0").mkdir()
    inputs = [conv.file("CONTRACT.md")]
    lane_map = {}
    deliverable = "DELIVERABLE.md"
    if strategy == "fan-out":
        m["fan_out"] = {"n": ns.n, "form": form, "rule": rule}
        roles_v = extra or prof["A"][:1]
        token = C.CONVENE_LINES["canary_token"].get(lang, C.CONVENE_LINES["canary_token"]["en"])
        for k in range(1, ns.n + 1):
            role = roles_v[(k - 1) % len(roles_v)]
            folder = c / "f1" / conv.name(f"agent-{k}")
            # ENG-12: in a race (and in a mixed fan-out, whose racing slices the engine cannot tell) every arm has a
            # canary of its own, in the map, which G1 checks as it checks the lanes of a classic. Slices are
            # different parts, with nothing to keep blind: no canary, as before.
            canary = f"{token}{secrets.token_hex(8)}" if form in ("race", "mixed") else None
            brief(conv, folder, role, "f1", deliverable, mission("race" if form == "race" else "fan_out_slice")
                  + ("" if form == "race" else "\n\n" + T("slice", k=k, n=ns.n)), inputs, canary=canary)
            m["f1"][f"agent-{k}"] = {"folder": str(folder), "lane": form, "role": role}
            if canary:
                lane_map[f"agent-{k}"] = {"folder": str(folder), "lane": form, "canary": canary}
    elif strategy == "single":
        role = extra[0] if extra else prof["A"][0]
        brief(conv, c / "f1" / role, role, "f1", deliverable, mission("single"), inputs)
        m["f1"][role] = {"folder": str(c / "f1" / role), "lane": "single"}
    else:
        if strategy == "classic":
            lanes = {"A": list(dict.fromkeys(prof["A"] + [r for r in extra if r not in prof["B"]])), "B": prof["B"]}
        else:
            # The global round is of the professionals; the sub-professionals enter only if named.
            lanes = {"all": [r["id"] for r in cat["roles"] if r["id"] != C.ROLES["arbiter"]
                             and (r.get("type", "professional") == "professional" or r["id"] in extra)]}
        canaries = {}
        token = C.CONVENE_LINES["canary_token"].get(lang, C.CONVENE_LINES["canary_token"]["en"])
        missions = {"A": "lane_a", "B": "lane_b", "all": "global_round"}
        for lane, rs in lanes.items():
            for role in rs:
                folder = c / "f1" / secrets.token_hex(6)
                # In the classic a canary per lane, in the full one per role: each is blind to the others.
                key = lane if strategy == "classic" else role
                canaries.setdefault(key, f"{token}{secrets.token_hex(8)}")
                brief(conv, folder, role, "f1", deliverable, mission(missions[lane]), inputs, canary=canaries[key])
                lane_map[role] = {"folder": str(folder), "lane": lane, "canary": canaries[key]}
                m["f1"][role] = {"folder": str(folder), "lane": lane}
        if strategy == "full":
            brief(conv, c / "f1c" / C.ROLES["arbiter"], C.ROLES["arbiter"], "f1c", "CONSOLIDATION.md",
                  mission("consolidation") + " " + k_note(conv),
                  inputs + [Path(v["folder"]) / conv.name(deliverable) for v in lane_map.values()], minutes=60)
        f1_out = [Path(v["folder"]) / conv.name(deliverable) for v in m["f1"].values()]
        if strategy == "full":
            f1_out = [c / "f1c" / C.ROLES["arbiter"] / conv.name("CONSOLIDATION.md")]
        translator = next((r for r in prof["translates"] + [C.ROLES["formalist"], C.ROLES["logician"]] if r not in m["f1"]), C.ROLES["logician"])
        f2 = c / "f2"
        n = conv.name
        brief(conv, f2 / n("01-translation"), translator, "f2", "CARDS.md", mission("cards"), inputs + f1_out, minutes=40)
        (f2 / n("02-signatures")).mkdir(parents=True)
        (f2 / n("02-signatures") / n("README.md")).write_text(T("signatures_readme") + "\n", encoding="utf-8")
        brief(conv, f2 / n("03-triage"), C.ROLES["arbiter"], "f2", "TRIAGE.md", mission("triage"),
              inputs + [f2 / n("01-translation") / n("CARDS.md"), f2 / n("02-signatures")], minutes=30)
        brief(conv, f2 / n("04-tournament"), C.ROLES["adversary"], "f2", "TOURNAMENT.md", mission("tournament"),
              inputs + [f2 / n("03-triage") / n("TRIAGE.md"), f2 / n("01-translation") / n("CARDS.md")], minutes=40)
        brief(conv, f2 / n("05-selection"), C.ROLES["arbiter"], "f2", "SELECTION.md", mission("selection"),
              inputs + [f2 / n("03-triage") / n("TRIAGE.md"), f2 / n("04-tournament") / n("TOURNAMENT.md")], minutes=20)
        # ENG-17: the sentinel of f2, in every classic and full (the branches are not known before the selection; the
        # cards and the triage are what every branch inherits), drawn by fitness and recorded (ENG-16); it delivers
        # before G2, which binds its folder with the rest of f2.
        _phase_sentinel(conv, cat, "f2", inputs + f1_out + [
            f2 / n("01-translation") / n("CARDS.md"), f2 / n("02-signatures"), f2 / n("03-triage") / n("TRIAGE.md"),
            f2 / n("04-tournament") / n("TOURNAMENT.md")])
    (c / "f5").mkdir()
    if lane_map:
        hidden = dest / conv.name(f".{c.name}.lanes")
        hidden.mkdir(mode=0o700)
        mp = hidden / conv.name("MAP.json")
        conv.write_json(mp, lane_map, "map")
        m["map"] = str(mp)
    conv.save()
    print(T("prepared", path=c))
    print(T("prepared_summary", strategy=shown("strategy", strategy), profile=shown("profile", profile), seed=seed))
    print(T("prepared_next", contract=conv.name("CONTRACT.md")))
    print(T("prepared_briefs"))
    for role, v in m["f1"].items():
        print(T("prepared_brief_line", role=conv.name(role) if role.startswith("agent-") else role,
                lane=shown("lane", v["lane"]), path=f"{v['folder']}/{conv.name('TASK.md')}"))
    if lane_map:
        print(T("prepared_map", path=m["map"]))
    notice = translation_notice(cat, BRIEFED)
    if notice:
        print(notice)


def _role_id(r: str) -> str:
    r = r.strip()
    for p in C.AGENT_PREFIXES:
        if r.startswith(p + "-"):
            return r[len(p) + 1:]
    return r


def snapshot(ns) -> None:
    conv = Convening.load(Path(ns.C).resolve())
    shot = {"time": now(), "file": {}}
    for v in conv.m["f1"].values():
        for p in sorted(Path(v["folder"]).rglob("*")):
            if p.is_file():
                s = p.stat()
                shot["file"][str(p)] = {"mtime": s.st_mtime, "read_after": s.st_atime > s.st_mtime}
    conv.write_json(conv.file("SNAPSHOT.json"), shot, "snapshot")
    task = conv.name("TASK.md")
    read = [p for p, v in shot["file"].items() if v["read_after"] and not p.endswith(task)]
    print(T("snapshot", n=len(shot["file"]), read=len(read)))
    for p in read:
        print(f"  {p}")


def seal(ns) -> None:
    conv = Convening.load(Path(ns.C).resolve())
    with conv.file("SEALS.jsonl").open("a", encoding="utf-8") as f:
        for name in ns.file:
            p = Path(name).resolve()
            if not p.is_file():
                raise Error(f"{p} does not exist")
            row = C.to_dialect({"time": now(), "file": str(p), "sha256": sha(p), "bytes": p.stat().st_size},
                               C.CONVENE_KEYS["seal"], conv.lang)
            f.write(json.dumps(row) + "\n")
            print(T("sealed", path=p))


def contradiction(ns) -> None:
    """Allocates the next K# of the convening (ENG-15): K-001, K-002 … in CONTRADICTIONS.jsonl at its root, one
    numbering for the whole convening, with the binary question and the files that hold its two sides. The engine
    reads it back: status lists the K#, and under the rules 3 G4 warns on a K# cited and never allocated, and G5 wants
    every allocated K# named in the closure. One writer at a time, as for SEALS.jsonl: the coordinator."""
    conv = Convening.load(Path(ns.C).resolve())
    files = []
    for name in ns.file:
        q = Path(name).resolve()
        if not q.is_file():
            raise Error(f"{q} does not exist")
        files.append(str(q))
    question = " ".join((ns.question or "").split())
    if not question:
        raise Error("--question TEXT: the binary question of the contradiction")
    known = contradictions(conv)
    n = max([int(x[2:]) for x in known] + [0]) + 1
    if n > 999:
        raise Error(f"{conv.name('CONTRADICTIONS.jsonl')} already holds K-999: no K# is left")
    k = f"K-{n:03d}"
    row = C.to_dialect({"id": k, "time": now(), "question": question, "files": files},
                       C.CONVENE_KEYS["contradiction"], conv.lang)
    p = conv.file("CONTRADICTIONS.jsonl")
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    print(T("contradiction_allocated", id=k, path=p, question=question))


def seals(conv: Convening) -> dict[str, dict]:
    p = conv.file("SEALS.jsonl")
    found = {}
    for line in p.read_text(encoding="utf-8").splitlines() if p.exists() else []:
        s = C.to_canonical(json.loads(line), C.CONVENE_KEYS["seal"], p.name)
        found.setdefault(s["file"], s)
    return found


def seal_rows(conv: Convening) -> dict[str, list[dict]]:
    """Every seal of each file, in the order of SEALS.jsonl: the rules 3 read them all (the first seal and the seal
    of each block appended later), where `seals` keeps only the first."""
    p = conv.file("SEALS.jsonl")
    found: dict[str, list[dict]] = {}
    for line in p.read_text(encoding="utf-8").splitlines() if p.exists() else []:
        s = C.to_canonical(json.loads(line), C.CONVENE_KEYS["seal"], p.name)
        found.setdefault(s["file"], []).append(s)
    return found


def ids_in(p: Path) -> list[str]:
    if not p.exists():
        return []
    return list(dict.fromkeys(f"H-{int(n):03d}" for n in ID.findall(p.read_text(encoding="utf-8"))))


def k_ids_in(text: str) -> list[str]:
    """The K# a text cites (K-1, K-01 and K-001 are one), in the form the allocator writes."""
    return list(dict.fromkeys(f"K-{int(x):03d}" for x in KID.findall(text)))


def contradictions(conv: Convening) -> dict[str, dict]:
    """The K# of the convening-wide registry CONTRADICTIONS.jsonl (ENG-15), by id, in the order allocated. A line
    that is not a K# record, or a K# written twice, stops every reader with exit 1: none guesses which K# is meant."""
    p = conv.file("CONTRADICTIONS.jsonl")
    out: dict[str, dict] = {}
    if not p.is_file():
        return out
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            r = C.to_canonical(json.loads(line), C.CONVENE_KEYS["contradiction"], p.name)
        except (ValueError, C.Error) as e:
            raise Error(f"{p.name} l.{i} cannot be read ({e})")
        k = r.get("id") if isinstance(r, dict) else None
        if not isinstance(k, str) or not re.fullmatch(r"K-[0-9]{3}", k):
            raise Error(f"{p.name} l.{i}: not a K# record (its id is K-001, K-002 …)")
        if k in out:
            raise Error(f"{p.name} l.{i}: {k} is written twice: the K# of the convening cannot be told apart")
        out[k] = r
    return out


def _unallocated(conv: Convening, files: list[Path]) -> list[str]:
    """The warnings for the K# that `files` cite and the registry does not hold (under the rules 3): a K# numbered by
    hand, per branch, is how two contradictions got one number (ENG-15)."""
    known = contradictions(conv)
    out = []
    for p in files:
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        missing = [t for t in dict.fromkeys(KTOKEN.findall(text)) if (k_ids_in(t) or [None])[0] not in known]
        if missing:
            out.append(f"{', '.join(missing)} cited in {p.relative_to(conv.folder)} and not allocated in "
                       f"{conv.name('CONTRADICTIONS.jsonl')}: contradiction C FILE… --question TEXT allocates a K#")
    return out


_PH = "|".join(re.escape(x) for x in TO_FILL)
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
CODE_SPAN = re.compile(r"(`+)(?!`).*?(?<!`)\1(?!`)")
# The placeholder alone on a line (after the marks of a list or a quote), or as the whole value of a field: «Results:
# <to fill in>», «**Results:** <to fill in>», «Slice 1 of 14: <to fill in>»; or a whole table cell. A closing
# punctuation mark adds nothing to the slot: «Goal: <to fill in>.» is still unfilled.
_END = r"[.,;:!?…]*\s*"
PLACEHOLDER = re.compile(rf"^\s*(?:(?:[-*+]|\d+[.)])\s+|>\s*)*(?:[^:|`]*:\**\s+)?(?:{_PH}){_END}$")
PLACEHOLDER_CELL = re.compile(rf"^\s*\|(?:.*\|)?\s*(?:{_PH}){_END}(?:\||$)")
LIST_ITEM = re.compile(r"^( *)(?:[-*+]|\d+[.)])( +|$)")


def unfilled(text: str) -> bool:
    """Whether a text keeps the placeholder of a field left to fill in (ENG-25): alone on a line, as the whole value
    of a field or as a whole table cell, outside the code blocks and the code spans. A text that only quotes it (in
    a code span, a code block or a sentence) is filled. Under every rule of the gates: it is a relaxation."""
    if not any(x in text for x in TO_FILL):   # the common case, as fast as the substring test of 5.2
        return False
    fence = None
    base = 0             # the content column of the list item the lines belong to (0: none)
    opens = True         # whether an indented line here starts an indented code block (CommonMark: not inside a paragraph)
    for line in text.splitlines():
        mt = FENCE.match(line)
        if fence:
            if mt and mt.group(1)[0] == fence[0] and len(mt.group(1)) >= len(fence) and not mt.group(2).strip():
                fence = None
            continue
        if mt and not (mt.group(1)[0] == "`" and "`" in mt.group(2)):
            fence = mt.group(1)
            continue
        expanded = line.expandtabs(4)
        if not expanded.strip():
            opens = True
            continue
        indent = len(expanded) - len(expanded.lstrip(" "))
        if opens and indent - base >= 4:   # an indented code block: a quote, as a fenced one
            continue
        item = LIST_ITEM.match(expanded)
        if item:
            base = len(item.group(0)) if item.group(2) else len(item.group(1)) + 2
        elif indent < base:
            base = 0
        opens = expanded.lstrip().startswith("#")   # a heading is no paragraph: code may follow it at once
        line = CODE_SPAN.sub("", line)
        if PLACEHOLDER.match(line) or PLACEHOLDER_CELL.match(line):
            return True
    return False


def full(p: Path) -> bool:
    text = p.read_text(encoding="utf-8", errors="replace") if p.is_file() else ""
    return p.is_file() and p.stat().st_size > 0 and not unfilled(text)


def level(conv: Convening) -> int:
    """The rules of the gates of a convening: the manifest key gate_rules, 1 when it is missing (4.0, 5.0)."""
    try:
        return int(conv.m.get("gate_rules") or 1)
    except (TypeError, ValueError):
        return 1


def funded(conv: Convening) -> bool:
    """Whether the radical branch has its briefs: always under the rules 1, after `fund` under the rules 2."""
    if not conv.m.get("radical"):
        return False
    return level(conv) < 2 or bool(conv.m.get("radical_funded"))


def branches(conv: Convening) -> list[str]:
    """The funded branches: the selected H#, plus the radical one once it is funded."""
    return list(conv.m["selected"]) + ([conv.m["radical"]] if funded(conv) else [])


def all_branches(conv: Convening) -> list[str]:
    return list(conv.m["selected"]) + ([conv.m["radical"]] if conv.m.get("radical") else [])


def amendments(conv: Convening, clashes: list[str] | None = None) -> dict[str, Path]:
    """The amendments of the contract at the root of the convening, by gate phase: AMENDMENT_1.md and AMENDMENT_A1.md
    (EMENDAMENTO_… in Italian) are both the phase A1. Two files for one phase are an error; with `clashes` they are
    reported there instead, and the first one is kept."""
    out = {}
    for p in sorted(conv.folder.iterdir()) if conv.folder.is_dir() else []:
        mt = AMENDMENT_RE.fullmatch(p.name)
        if not mt or not p.is_file():
            continue
        phase = "A" + str(int(next(g for g in mt.groups() if g).lstrip("A")))
        if phase in out:
            text = f"two amendments for the gate {phase}: {out[phase].name} and {p.name}"
            if clashes is None:
                raise Error(text)
            clashes.append(text)
            continue
        out[phase] = p
    return out


def amendment_phases(conv: Convening, clashes: list[str] | None = None) -> list[str]:
    """The phases of the amendments: those with a file, and those with a gate whose amendment is gone."""
    gated = [q.name[5:-5] for q in conv.folder.glob("GATE_A*.json") if re.fullmatch(r"GATE_A\d+\.json", q.name)]
    return sorted(set(amendments(conv, clashes)) | set(gated), key=lambda a: int(a[1:]))


def gated_amendments(conv: Convening) -> list[Path]:
    """The amendments bound by a valid gate: what the briefs read."""
    clashes = [] if level(conv) < 2 else None
    return [p for a, p in amendments(conv, clashes).items() if valid(conv, a)]


def _role_folder(d: Path) -> bool:
    """A folder f3/<H#>/NN-<role>, f4/<H#>/NN-<role> or f4_<n>/<H#>/NN-<role> (a briefed role): always the
    convening's own."""
    return bool(re.match(r"\d+-", d.name) and ID.fullmatch(d.parent.name)
                and (d.parent.parent.name in ("f3", "f4") or split_label(f"{d.parent.parent.name}/H-000")[1] > 1))


def _is_manifest(p: Path) -> bool:
    """A manifest of a convening (5.0 or 4.0): a JSON object with the strategy and the lanes of f1."""
    if not p.is_file():
        return False
    try:
        m = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(m, dict) and any(k in m for k in ("strategy", "strategia")) and isinstance(m.get("f1"), dict)


def _foreign(d: Path) -> bool:
    """A folder whose files are not the convening's own: a role's workspace, a state folder, a nested convening (a
    folder with a manifest of a convening). The folder of a briefed role never is (ENG-3)."""
    if _role_folder(d):
        return False
    return d.name in WORK_NAMES + STATE_DIRS or any(_is_manifest(d / x) for x in MANIFESTS)


def _own_files(base: Path):
    """Every file under `base`, without the foreign folders, git and __pycache__."""
    if not base.is_dir():
        return
    for root, dirs, files in os.walk(base):
        r = Path(root)
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not _foreign(r / d))
        for f in sorted(files):
            yield r / f


def _own(base: Path, *names: str) -> list[Path]:
    """The files named one of `names` under `base`, without those of the foreign folders (ENG-3)."""
    return [p for p in _own_files(base) if p.name in names]


def phase_folders(conv: Convening, phase: str) -> list[Path]:
    c, m = conv.folder, conv.m
    if phase == "f0":
        return [c / "f0"]
    if phase == "f1":
        return [Path(v["folder"]) for v in m["f1"].values()] + ([c / "f1c"] if m["strategy"] == "full" else [])
    return [c / phase]


def fingerprints_v1(conv: Convening, phase: str) -> dict[str, str]:
    """The fingerprints of the rules 1 (5.0), unchanged: the .md of the phase, and the .json of f3 and f4."""
    c = conv.folder
    files = [conv.file("CONTRACT.md")] if phase == "f0" else []
    folder = c
    for folder in phase_folders(conv, phase):
        files += sorted(p for p in folder.rglob("*.md") if p.is_file())
    if split_label(phase)[0][:3] in ("f3/", "f4/"):
        files += sorted(p for p in folder.rglob("*.json") if p.is_file() and not p.name.startswith("GATE_"))
    return {str(p): sha(p) for p in files}


def _link(p: Path, exclude: set[str], seen: frozenset) -> str:
    """A symbolic link, bound by its target: the sha256 of the file, or the tree of the folder, it points to."""
    target = os.readlink(p)
    try:
        real = p.resolve(strict=True)
    except (OSError, RuntimeError):
        return "link:" + target
    if real.is_dir():
        if str(real) in seen:
            return f"link:{target} -> loop"
        return f"link:{target} -> " + _tree(real, exclude, seen)
    if real.is_file():
        return f"link:{target} -> " + sha(real)
    return "link:" + target


def _entry(p: Path, exclude: set[str], seen: frozenset = frozenset()) -> str | None:
    if p.is_symlink():
        return _link(p, exclude, seen)
    if p.is_file():
        return sha(p)
    return None


def _crowded(d: Path) -> bool:
    """More than FILES_PER_FOLDER files in the subtree of `d`, without the foreign folders (bound on their own)."""
    n, stack = 0, [d]
    while stack:
        try:
            entries = list(os.scandir(stack.pop()))
        except OSError:
            continue
        for e in entries:
            if e.is_dir(follow_symlinks=False):
                if e.name not in SKIP_DIRS and not _foreign(Path(e.path)):
                    stack.append(Path(e.path))
                continue
            n += 1
            if n > FILES_PER_FOLDER:
                return True
    return False


def _aggregated(d: Path, walked: bool = False) -> bool:
    """A folder bound as one tree entry: a workspace, a nested convening or state folder, or a crowded folder. The
    folder of a phase and the NN-<role> folders in it (`walked`) are crowded only with more than FILES_PER_FOLDER
    files of their own; any other folder with more than FILES_PER_FOLDER files in its whole subtree (ENG-4)."""
    if _foreign(d):
        return True
    if not walked:
        return _crowded(d)
    try:
        return sum(1 for x in os.scandir(d) if x.is_file(follow_symlinks=False)) > FILES_PER_FOLDER
    except OSError:
        return False


def _tree(d: Path, exclude: set[str], seen: frozenset = frozenset()) -> str:
    lines = []
    try:
        seen = seen | {str(d.resolve())}
    except (OSError, RuntimeError):
        pass
    for root, dirs, files in os.walk(d):
        r = Path(root)
        keep = []
        for x in sorted(dirs):
            if x in SKIP_DIRS:
                continue
            if (r / x).is_symlink():
                lines.append(f"{(r / x).relative_to(d).as_posix()}\0{_link(r / x, exclude, seen)}\n")
                continue
            keep.append(x)
        dirs[:] = keep
        for f in files:
            p = r / f
            if f.endswith(".pyc") or str(p) in exclude:
                continue
            e = _entry(p, exclude, seen)
            if e is not None:
                lines.append(f"{p.relative_to(d).as_posix()}\0{e}\n")
    # A name that is not UTF-8 (ENG-13) is hashed by its own bytes, which surrogateescape gives back; a UTF-8 name as
    # before, so every tree entry approved before keeps its fingerprint.
    return "tree:" + hashlib.sha256("".join(sorted(lines)).encode("utf-8", "surrogateescape")).hexdigest()


def _bind(top: Path, out: dict, exclude: set[str]) -> None:
    if not top.is_dir():
        return
    if _aggregated(top, walked=True):
        out[str(top) + "/"] = _tree(top, exclude)
        return
    for root, dirs, files in os.walk(top):
        r = Path(root)
        keep = []
        for x in sorted(dirs):
            p = r / x
            if x in SKIP_DIRS:
                continue
            if p.is_symlink():
                out[str(p)] = _link(p, exclude, frozenset())
            elif _aggregated(p, walked=r == top and bool(re.match(r"\d+-", x))):
                out[str(p) + "/"] = _tree(p, exclude)
            else:
                keep.append(x)
        dirs[:] = keep
        for f in sorted(files):
            p = r / f
            if f.startswith("GATE_") or f.endswith(".pyc") or str(p) in exclude:
                continue
            e = _entry(p, exclude)
            if e is not None:
                out[str(p)] = e


def dossier_of(conv: Convening, h: str, k: int = 1) -> Path:
    """The dossier of `h`: f3/<H#>/<H#>.md, which the first round completes; a later round has its own, in its folder
    (repin never touches the first)."""
    return conv.folder / "f3" / h / f"{h}.md" if k == 1 else f4_dir(conv, h, k) / f"{h}.md"


def fingerprints_v2(conv: Convening, phase: str) -> dict[str, str]:
    """The fingerprints of the rules 2: every file of the phase (code, raw outputs, archives too), a workspace, a
    nested convening or a folder of more than FILES_PER_FOLDER files as one tree entry; the dossier of an H# is bound
    at G4, where the arbiter completes it, not at G3."""
    out = {}
    exclude = set()
    h = phase[3:] if phase[:3] in ("f3/", "f4/") else None
    if phase == "f0":
        out[str(conv.file("CONTRACT.md"))] = sha(conv.file("CONTRACT.md"))
    if phase.startswith("f3/"):
        exclude.add(str(dossier_of(conv, h)))
    for folder in phase_folders(conv, phase):
        _bind(folder, out, exclude)
    if phase.startswith("f4/") and dossier_of(conv, h).is_file():
        out[str(dossier_of(conv, h))] = sha(dossier_of(conv, h))
    return out


_FP: dict = {}


def fingerprints(conv: Convening, phase: str, rules: int = 1) -> dict[str, str]:
    key = (str(conv.folder), phase, rules)
    if key not in _FP:
        if re.fullmatch(r"A\d+", phase):
            p = amendments(conv, []).get(phase)
            _FP[key] = {str(p): sha(p)} if p else {}
        else:
            fp = (fingerprints_v2 if rules >= 2 else fingerprints_v1)(conv, phase)
            if rules >= 3 and phase == "f5":
                # ENG-17: the first G5 of the rules 3 also binds the folders of the sentinels of f3 and f4, which no
                # gate of a branch binds (they are convening-wide); a later closure binds its own folder alone.
                for ph in ("f3", "f4"):
                    for d in SENTINEL_DIRS:
                        _bind(conv.folder / ph / d, fp, set())
            _FP[key] = fp
    return dict(_FP[key])


def gate_file(conv: Convening, phase: str) -> Path:
    return conv.folder / f"GATE_{phase.replace('/', '_')}.json"


def read_gate(conv: Convening, phase: str) -> dict | None:
    p = gate_file(conv, phase)
    return conv.read_json(p, "gate") if p.exists() else None


def gate_rules(g: dict) -> int:
    try:
        return int(g.get("rules") or 1)
    except (TypeError, ValueError):
        return 1


def valid(conv: Convening, phase: str, drop=()) -> bool:
    """Whether the gate of `phase` still holds, recomputed under the rules it was approved with; `drop` leaves some
    files out of the comparison (a dossier bound by a G3 of the rules 1, which a G4 of the rules 2 binds instead)."""
    g = read_gate(conv, phase)
    if g is None:
        return False
    old = g.get("fingerprints") or {}
    new = fingerprints(conv, phase, gate_rules(g))
    if drop:
        drop = {str(x) for x in drop}
        old = {k: v for k, v in old.items() if k not in drop}
        new = {k: v for k, v in new.items() if k not in drop}
    return old == new


def g3_holds(conv: Convening, h: str, lvl: int) -> bool:
    """G3 of `h` as a prerequisite: under the rules 2 a G3 of the rules 1 holds without its dossier (ENG-1)."""
    if valid(conv, f"f3/{h}"):
        return True
    g = read_gate(conv, f"f3/{h}")
    return lvl >= 2 and g is not None and gate_rules(g) < 2 and valid(conv, f"f3/{h}", drop={dossier_of(conv, h)})


# --- the rounds (5.3): the f4 of a re-pinned branch, the closures after a G5 «not closed» ---

def round_label(phase: str, k: int) -> str:
    """The label of round k of a phase: the phase itself for the first round, f4_<k>/<H#> and f5_<k> after it. The
    label is the folder of the round and, with «_» for «/», the name of its gate file (GATE_f4_2_H-001.json)."""
    if k == 1:
        return phase
    return f"f4_{k}/{phase[3:]}" if phase.startswith("f4/") else f"f5_{k}"


def split_label(label: str) -> tuple[str, int]:
    """The phase and the round of a label: f4_2/H-001 → (f4/H-001, 2), f5_3 → (f5, 3), anything else → (label, 1)."""
    mt = ROUND_RE.fullmatch(label)
    if not mt or int(mt.group(2)) < 2 or (mt.group(1) == "f4") != bool(mt.group(3)):
        return label, 1
    return mt.group(1) + (mt.group(3) or ""), int(mt.group(2))


def f4_rounds(conv: Convening, h: str) -> list[int]:
    """The rounds of the f4 of `h`: 1 (f4/<H#>/) and each f4_<n>/<H#>/ that repin opened. They are read from the
    folders, so that the manifest keeps the keys of 5.2 and an engine of 5.2 still loads the convening."""
    out = [1]
    for d in conv.folder.iterdir() if conv.folder.is_dir() else []:
        k = split_label(f"{d.name}/{h}")[1]
        if k > 1 and (d / h).is_dir():
            out.append(k)
    return sorted(out)


def f4_round(conv: Convening, h: str) -> int:
    """The latest round of the f4 of `h`: the one that the branch's state, its G4 and G5 read."""
    return f4_rounds(conv, h)[-1]


def f4_dir(conv: Convening, h: str, k: int | None = None) -> Path:
    return conv.folder / round_label(f"f4/{h}", f4_round(conv, h) if k is None else k)


def g4_label(conv: Convening, h: str) -> str:
    """The G4 of `h` that counts: the one of its latest round."""
    return round_label(f"f4/{h}", f4_round(conv, h))


def _round_dirs(conv: Convening) -> list[Path]:
    """The folders of the rounds of f4 after the first, f4_<n>/."""
    return sorted(d for d in conv.folder.iterdir() if d.is_dir() and split_label(f"{d.name}/H-000")[1] > 1
                  and d.name.startswith("f4_")) if conv.folder.is_dir() else []


def f5_dir(conv: Convening, k: int) -> Path:
    """The folder of the k-th closure: f5/ for the first, f5_<k>/ for each later one, beside f5/ and never inside it,
    since the first G5 binds every file under f5/."""
    return conv.folder / round_label("f5", k)


def g5_ordinals(conv: Convening) -> list[int]:
    """The G5s by ordinal: GATE_f5.json is 1, each later one GATE_f5_<n>.json with n ≥ 2 in ASCII digits read as an
    integer; never ordered by an mtime, which a copy moves, by the gate's time, which is to the second, or by the
    sorted names, which put 10 before 2. A name that gives an ordinal below 2, or one already given, stops every
    reader: none guesses which of two gates is the latest."""
    found = {1: "GATE_f5.json"} if gate_file(conv, "f5").exists() else {}
    for p in sorted(conv.folder.iterdir()) if conv.folder.is_dir() else []:
        mt = G5_LATER.fullmatch(p.name)
        if not mt:
            continue
        k = int(mt.group(1))
        if k < 2 or mt.group(1) != str(k) or k in found:
            raise Error(f"{p.name}: a later gate f5 is GATE_f5_<n>.json, with n from 2 and no leading zero; the "
                        f"latest gate f5 cannot be told")
        found[k] = p.name
    return sorted(found)


def latest_g5(conv: Convening) -> tuple[int, dict] | None:
    """The latest G5, the one of the highest ordinal, and its record. A gate file that cannot be read (empty, with a
    BOM, not UTF-8, not JSON) stops every reader with exit 1: nothing is funded, closed or re-pinned on a guess."""
    ks = g5_ordinals(conv)
    if not ks:
        return None
    label = round_label("f5", ks[-1])
    try:
        g = read_gate(conv, label)
    except ValueError as e:
        raise Error(f"{gate_file(conv, label).name} cannot be read ({e}): it is the latest gate f5")
    if not isinstance(g, dict):
        raise Error(f"{gate_file(conv, label).name} is not a gate: it is the latest gate f5")
    return ks[-1], g


def g5_open(conv: Convening, k: int, g: dict) -> bool:
    """Whether the G5 `k` lets the convening go on: it holds, and it records a non-closure: «closed» false under the
    rules ≥ 2; under the rules 1, which record no «closed», a closure that says «not closed»."""
    if not valid(conv, round_label("f5", k)):
        return False
    if gate_rules(g) >= 2:
        return g.get("closed") is False
    return outcome_of(conv, k) == "not closed"


def f5_open(conv: Convening, act: str) -> int:
    """The closure that the briefs of select, fund, close-branch and repin go to: the first before any G5; after a
    G5 that holds and records a non-closure, the next one, in its own folder. After any other G5 (closed, or no longer
    holding) nothing is `act`: the lock of 5.2, which shut after any G5."""
    last = latest_g5(conv)
    if last is None:
        return 1
    k, g = last
    if g5_open(conv, k, g):
        return k + 1
    label = round_label("f5", k)
    why = "no longer holds" if not valid(conv, label) else "closes it"
    raise Error(f"the convening has its gate {label} ({gate_file(conv, label).name}), which {why}: no branch is {act} "
                f"after it")


def f5_gate_round(conv: Convening, verify: bool = False) -> tuple[int, bool]:
    """The closure that a gate f5 checks, and whether its gate file is new: the first before any G5. After a G5 that
    holds and records a non-closure, the next one once its folder f5_<k+1>/ exists (fund, close-branch and repin
    brief it), into a new gate file; until then --verify checks that G5 again, as 5.2 did, and a gate that would
    write is refused. After any other G5, the latest again, in place as in 5.2, unless it records a non-closure:
    that record is never written over."""
    last = latest_g5(conv)
    if last is None:
        return 1, True
    k, g = last
    label = round_label("f5", k)
    if g5_open(conv, k, g):
        if f5_dir(conv, k + 1).exists():
            return k + 1, True
        if verify:
            return k, False
        raise Error(f"{gate_file(conv, label).name} records a non-closure, never written over: the next closure goes "
                    f"in {round_label('f5', k + 1)}/, which fund C, close-branch C and repin C brief")
    if g.get("closed") is False:
        raise Error(f"{gate_file(conv, label).name} records a non-closure and no longer holds (files of {label}/ "
                    f"changed): its record is never written over; restore {label}/")
    return k, False


def _section(text: str, field: str):
    for title in (field, C.CONVENE_LINES["contract_fields"][field]):
        s = re.search(rf"^## {re.escape(title)}\n(.*?)(?=^## |\Z)", text, re.S | re.M)
        if s:
            return s
    return None


def _early(conv: Convening, h: str) -> bool:
    return (conv.folder / "f3" / h / conv.name("EARLY_CLOSURE.json")).exists()


def _early_data(conv: Convening, h: str) -> dict:
    p = conv.folder / "f3" / h / conv.name("EARLY_CLOSURE.json")
    return conv.read_json(p, "early_closure") if p.exists() else {}


def _blocks(text: str) -> list[list[str]]:
    """The fields of a dossier: a line «- …» and the blank or indented lines after it."""
    out, cur = [], None
    for line in text.splitlines():
        if line.startswith("- "):
            cur = [line]
            out.append(cur)
        elif cur is not None and (not line.strip() or line[:1] in (" ", "\t")):
            cur.append(line)
        else:
            cur = None
    return out


def _flat(block: list[str]) -> str:
    return " ".join(" ".join(block).split())


def _empty_fields(text: str, template: str | None, lvl: int = 2) -> list[str]:
    """The empty fields of a dossier (ENG-2): a field «- X:» with nothing on its line nor on the indented lines after
    it; under the rules 2 also a field left exactly as in the template, when the template has a line ending in «:»
    in it (the table and the fields of two lines)."""
    untouched = set()
    if template and lvl >= 2:
        untouched = {_flat(b) for b in _blocks(template) if any(x.rstrip().endswith(":") for x in b)}
    out = []
    for b in _blocks(text):
        rest = [x for x in b[1:] if x.strip()]
        if (re.match(r"^- [^|]*:\s*$", b[0]) and not rest) or _flat(b) in untouched:
            out.append(b[0])
    return out


def _correctness_in(p: Path) -> str | None:
    if not p.is_file():
        return None
    mt = re.search(C.CONVENE_LINES["correctness_re"], p.read_text(encoding="utf-8", errors="replace"), re.M | re.I)
    if not mt:
        return None
    v = " ".join(mt.group(1).lower().split())
    return C.LINE_VALUES["correctness"].get(v, v)


def arbiter_verdict(conv: Convening, h: str, d: Path | None = None) -> Path:
    """The verdict of the arbiter of `h`: NN-arbitro/VERDICT.md in the folder of its latest round (or of the round
    folder `d`), the folder that select and repin brief (09-arbitro)."""
    d = f4_dir(conv, h) if d is None else d
    folders = [x for x in sorted(d.iterdir()) if x.is_dir() and re.match(r"\d+-", x.name)
               and _role_of(x.name) == C.ROLES["arbiter"]] if d.is_dir() else []
    for x in folders:
        if (x / conv.name("VERDICT.md")).is_file():
            return x / conv.name("VERDICT.md")
    return d / f"09-{C.ROLES['arbiter']}" / conv.name("VERDICT.md")


def _correctness(conv: Convening, h: str, d: Path | None = None) -> str | None:
    """The canonical value of the line «Correctness: …» of the arbiter's verdict of `h` (of its latest round, or of
    the round folder `d`), or None: no other VERDICT.md of the branch counts."""
    return _correctness_in(arbiter_verdict(conv, h, d))


def _stray_correctness(conv: Convening, h: str, d: Path | None = None) -> list[Path]:
    """The VERDICT.md files of the round, other than the arbiter's, that carry a Correctness line."""
    own = arbiter_verdict(conv, h, d)
    return [p for p in _own(f4_dir(conv, h) if d is None else d, conv.name("VERDICT.md"))
            if p != own and _correctness_in(p)]


def proven(conv: Convening, h: str, warnings: list[str] | None = None, lvl: int = 1) -> bool:
    """`h` is proven: a valid G4 and an arbiter's verdict with Correctness proven or verified. Under the rules 1 a G4
    of the rules 1 whose verdict has no Correctness line keeps the old rule (a valid G4), with a warning; under the
    rules 2 (`lvl`, the rules of the G5) it is not proven (ENG-6). The G4 is the one of the branch's latest round."""
    label = g4_label(conv, h)
    g = read_gate(conv, label)
    if g is None or not valid(conv, label):
        return False
    v = _correctness(conv, h)
    if v is None:
        if gate_rules(g) >= 2 or lvl >= 2:
            return False
        if warnings is not None:
            warnings.append(f"{h}: «proven» taken from a G4 of the rules 1 (its verdict has no line "
                            f"{C.CONVENE_LINES['correctness'][conv.lang]}; a G5 with --rules 2 does not take it)")
        return True
    return v in PROVEN


def _role_of(folder_name: str) -> str:
    return re.sub(r"^\d+-", "", folder_name)


def team(conv: Convening, h: str) -> set[str]:
    """The roles of the f3 team of `h` (its folders NN-<role>)."""
    d = conv.folder / "f3" / h
    return {_role_of(x.name) for x in d.iterdir() if x.is_dir() and re.match(r"\d+-", x.name)} if d.is_dir() else set()


def sentinel_required(conv: Convening) -> bool:
    """A classic or a full with at least two branches that have a G3 or are not closed early (PIPELINE, the
    sentinel)."""
    if conv.m["strategy"] not in ("classic", "full"):
        return False
    return len([h for h in branches(conv) if valid(conv, f"f3/{h}") or not _early(conv, h)]) >= 2


def sentinel_found(conv: Convening, k: int = 1, phase: str | None = None) -> bool:
    """The sentinel's deliverable beside the k-th closure, f5/00-sentinel/SENTINEL.md (f5_<k>/00-sentinel/ for a later
    one): f5 is bound by G5 alone, so writing it invalidates no earlier gate. With `phase` f2, f3 or f4, the
    deliverable of the sentinel of that phase (ENG-17), <phase>/00-sentinel/SENTINEL.md."""
    where = conv.folder / phase if phase in PHASE_SENTINELS else f5_dir(conv, k)
    return any(full(where / d / n) for d in SENTINEL_DIRS for n in SENTINEL_NAMES)


def sentinel_task(conv: Convening, phase: str) -> Path | None:
    """The brief of the sentinel of f2, f3 or f4, if the engine wrote one (prepare, select, fund under the rules 3)."""
    for d in SENTINEL_DIRS:
        p = conv.folder / phase / d / conv.name("TASK.md")
        if p.is_file():
            return p
    return None


def brief_agent(task: Path) -> str | None:
    """The role of a brief, from its agent line `<prefix>-<role>`."""
    agents = tuple(f"{p}-" for p in dict.fromkeys((prefix(), *C.AGENT_PREFIXES)))
    try:
        text = task.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    return next((_role_id(x) for x in re.findall(r"`([^`/\s]+)`", text) if x.startswith(agents)), None)


def outcome_of(conv: Convening, k: int = 1) -> str | None:
    """The canonical outcome of the k-th closure, f5/CLOSURE.md (f5_<k>/CLOSURE.md), «closed» or «not closed», or
    None."""
    closure = f5_dir(conv, k) / conv.name("CLOSURE.md")
    if not closure.is_file():
        return None
    mt = re.search(C.CONVENE_LINES["outcome_re"], closure.read_text(encoding="utf-8", errors="replace"), re.M)
    return C.LINE_VALUES["outcome"][mt.group(1) or mt.group(2)] if mt else None


def _not_delivered(conv: Convening, role: str, nd: set[str]) -> bool:
    return role in nd or conv.name(role) in nd or f"{prefix()}-{role}" in nd


def conditions(conv: Convening, phase: str, not_delivered: set[str], lvl: int = 1) -> tuple[list[str], dict]:
    """The errors of a gate, and what the gate records besides (the warnings; for f5 whether it closes). `phase` is a
    gate label: f4_2/H-001 is round 2 of the f4 of H-001, f5_2 the second closure."""
    c, m, n = conv.folder, conv.m, conv.name
    errors = []
    info = {"warnings": []}
    warnings = info["warnings"]
    label = phase
    phase, k = split_label(label)
    amend = re.fullmatch(r"A\d+", phase)
    before = {"f1": "f0", "f2": "f1", "f5": "f2"}.get(phase)
    if amend:
        before = "f0"
    if phase.startswith("f3/"):
        before = "f2"
    elif phase.startswith("f4/"):
        before = "f3/" + phase[3:]
    if m["strategy"] in ("single", "fan-out") and phase == "f5":
        before = "f1"
    if before and before.startswith("f3/"):
        if not g3_holds(conv, before[3:], lvl):
            errors.append(f"the gate {before} is not approved or no longer valid")
    elif before and not valid(conv, before):
        errors.append(f"the gate {before} is not approved or no longer valid")
    # ENG-26: under the rules 3 every gate checks G0 again, not only the gate just before it, so a contract or a file
    # of f0/ changed after G1 stops every later gate; and an amendment gate checks the other gated amendments again,
    # as every other gate does from the rules 2 (an amendment without its gate is not waited for: two amendments
    # gated in turn would wait for each other).
    if lvl >= 3 and phase != "f0" and before != "f0" and not valid(conv, "f0"):
        errors.append("the gate f0 is not approved or no longer valid (under the rules 3 every gate checks it again)")
    if lvl >= 3 and amend:
        found = amendments(conv)
        for a in amendment_phases(conv):
            if a == phase or not gate_file(conv, a).exists():
                continue
            if a not in found:
                errors.append(f"the gate {a} binds an amendment that is no longer there ({n('AMENDMENT_' + a[1:] + '.md')})")
            elif not valid(conv, a):
                errors.append(f"the amendment {found[a].name} changed after its gate {a}: under the rules 3 every "
                              f"gate checks the gated amendments again")
    if lvl >= 2 and phase != "f0" and not amend:
        found = amendments(conv)
        for a in amendment_phases(conv):
            if a not in found:
                errors.append(f"the gate {a} binds an amendment that is no longer there ({n('AMENDMENT_' + a[1:] + '.md')})")
            elif not valid(conv, a):
                errors.append(f"the amendment {found[a].name} is not bound by a valid gate {a}: gate C {a}")
    if amend:
        p = amendments(conv).get(phase)
        if p is None:
            errors.append(f"no amendment for the gate {phase} ({n('AMENDMENT_' + phase + '.md')})")
        elif not full(p):
            errors.append(f"{p.name} is empty or to fill in")
        else:
            s = seals(conv).get(str(p))
            if not s:
                errors.append(f"{p.name} is not sealed: seal C {p}")
            elif s["sha256"] != sha(p):
                errors.append(f"{p.name} changed after the seal")
            mt = re.search(C.CONVENE_LINES["amends_re"], p.read_text(encoding="utf-8"), re.M)
            known = {f.lower(): f for f in CONTRACT_FIELDS} | {v.lower(): k for k, v in
                                                              C.CONVENE_LINES["contract_fields"].items()}
            named = [x.strip().strip(".").lower() for x in re.split(r"[,;]", mt.group(1))] if mt else []
            if not mt or not named or any(x not in known for x in named):
                text = (f"{p.name}: the line {C.CONVENE_LINES['amends'][conv.lang]} is missing or names no field of "
                        f"the contract ({', '.join(CONTRACT_FIELDS)})")
                # Under the rules 1 (an amendment written before the line existed, ENG-10) it is only a warning.
                (errors if lvl >= 2 else warnings).append(text)
    elif phase == "f0":
        text = conv.file("CONTRACT.md").read_text(encoding="utf-8")
        for field in CONTRACT_FIELDS:
            s = _section(text, field)
            if not s or not s.group(1).strip() or unfilled(s.group(1)):
                errors.append(f"{n('CONTRACT.md')}: «{field}» to fill in")
    elif phase == "f1":
        lane_map = {}
        if m.get("map"):
            lane_map = conv.read_json(Path(m["map"]), "map")
        last = 0.0
        canary_words = tuple(C.CONVENE_LINES["canary"].values())
        for role, v in m["f1"].items():
            out = Path(v["folder"]) / n("DELIVERABLE.md")
            if role in not_delivered or conv.name(role) in not_delivered:
                continue
            if not full(out):
                errors.append(f"{role}: the deliverable {out} is missing")
                continue
            last = max(last, out.stat().st_mtime)
            text = out.read_text(encoding="utf-8", errors="replace")
            if role in lane_map:
                own = lane_map[role]["canary"]
                if not any(text.lstrip().startswith(f"{w} {own}") for w in canary_words):
                    errors.append(f"{role}: the deliverable does not start with its canary")
                others = {v2["canary"] for r2, v2 in lane_map.items() if v2["canary"] != own}
                if any(a in text for a in others):
                    errors.append(f"{role}: the deliverable contains the canary of another lane (contamination)")
        if lane_map:
            shot = conv.file("SNAPSHOT.json")
            if not shot.exists():
                errors.append("the snapshot of the reads is missing: snapshot C, before reading")
            elif _iso(conv.read_json(shot, "snapshot")["time"]) < last - 1:
                errors.append("the snapshot is older than the last deliverable: take it again")
        if m["strategy"] == "full" and not full(c / "f1c" / C.ROLES["arbiter"] / n("CONSOLIDATION.md")):
            errors.append(f"the consolidation of the arbiter is missing (f1c/{C.ROLES['arbiter']}/{n('CONSOLIDATION.md')})")
    elif phase == "f2":
        f2 = c / "f2"
        triage = f2 / n("03-triage") / n("TRIAGE.md")
        tournament = f2 / n("04-tournament") / n("TOURNAMENT.md")
        selection = f2 / n("05-selection") / n("SELECTION.md")
        for p in (f2 / n("01-translation") / n("CARDS.md"), triage, tournament, selection):
            if not full(p):
                errors.append(f"{p.relative_to(c)} is missing")
        signs = [p for p in (f2 / n("02-signatures")).glob("*.md") if p.name != n("README.md")]
        if not signs:
            errors.append(f"no signature of the authors in f2/{n('02-signatures')}")
        s = seals(conv).get(str(triage))
        if triage.exists():
            if not s:
                errors.append(f"the triage is not sealed: seal C {triage.relative_to(c)}")
            else:
                if s["sha256"] != sha(triage):
                    errors.append("the triage changed after the seal")
                if any(p.stat().st_mtime > _iso(s["time"]) + 1 for p in signs):
                    errors.append("a signature arrived after the seal of the triage")
                if tournament.exists() and tournament.stat().st_mtime < _iso(s["time"]):
                    errors.append("the tournament is older than the seal of the triage")
        if selection.exists():
            out = set(ids_in(selection)) - set(ids_in(triage))
            if out:
                errors.append(f"the selection names H# the triage does not have: {', '.join(sorted(out))}")
            stext = selection.read_text(encoding="utf-8")
            if not any(x in stext for x in C.CONVENE_LINES["countersign"].values()):
                errors.append(f"the selection does not have the line «{C.CONVENE_LINES['countersign'][conv.lang]}»")
        # ENG-17: the sentinel of f2 that prepare briefed delivers before G2, which binds every file of f2: one
        # delivered after G2 would invalidate it. Under the rules 3, its deliverable or its «not delivered».
        task = sentinel_task(conv, "f2") if lvl >= 3 else None
        if task:
            role = brief_agent(task) or "?"
            if not _not_delivered(conv, role, not_delivered) and not sentinel_found(conv, phase="f2"):
                errors.append(f"f2/{task.parent.name}: no {n('SENTINEL.md')} of the sentinel {role}: G2 binds it, so "
                              f"it delivers before G2 (or --not-delivered {role})")
    elif phase.startswith("f3/") or phase.startswith("f4/"):
        h = phase[3:]
        if h not in all_branches(conv):
            errors.append(f"{h} is not selected")
        elif h not in branches(conv):
            errors.append(f"radical not funded: fund C {h}")
        if _early(conv, h):
            errors.append(f"the branch {h} is closed early: no G3 nor G4")
        if k > 1 and lvl < 3:
            errors.append(f"{label} is a round opened by repin: its G4 runs under the rules 3 "
                          f"(gate C {phase} --rules 3)")
        folder = c / label
        # ENG-17: the sentinel of the phase, convening-wide, is not waited for by a branch's gate: a warning, and G5
        # requires it.
        ph = phase[:2]
        task = sentinel_task(conv, ph) if lvl >= 3 and k == 1 else None
        if task and not sentinel_found(conv, phase=ph):
            warnings.append(f"no sentinel of {ph} yet ({ph}/{task.parent.name}/{n('SENTINEL.md')}): G5 will require "
                            f"it")
        if phase.startswith("f3/"):
            for name in ("SOLUTION.md", "VERIFICATION.md", "MEASUREMENT_PLAN.md", "ATTACK.md", "PREDICTIONS.md"):
                if not any(full(p) for p in _own(folder, n(name))):
                    errors.append(f"{phase}: {n(name)} is missing")
            for p in _own(folder, n("PREDICTIONS.md")):
                if not re.search(C.CONVENE_LINES["decides_re"], p.read_text(encoding="utf-8"), re.M):
                    errors.append(f"{p.relative_to(c)}: the line {C.CONVENE_LINES['decides'][conv.lang]} is missing")
        else:
            for name in ("COUNTERCHECKS.md", "VERDICT.md"):
                if not any(full(p) for p in _own(folder, n(name))):
                    errors.append(f"{label}: {n(name)} is missing")
            if lvl >= 3:
                errors += _order_rules3(conv, folder)
                warnings += _unallocated(conv, [p for p in _own_files(folder) if p.suffix == ".md"])
            else:
                sig = seals(conv)
                checks = _own(folder, n("COUNTERCHECKS.md"))
                for p in _own(folder, n("PREDICTIONS.md")):
                    s = sig.get(str(p))
                    if not s:
                        errors.append(f"{p.relative_to(c)} born in f4 is not sealed")
                    elif sha(p) != s["sha256"] and not _tail_only(p, s):
                        errors.append(f"{p.relative_to(c)} changed after the seal, not only at the end")
                    elif any(q.stat().st_mtime < _iso(s["time"]) for q in checks):
                        errors.append(f"{p.relative_to(c)} is sealed after the counterchecks")
            dossier = dossier_of(conv, h, k)
            if dossier.exists():
                try:
                    template = hypothesis_card().replace("H-000", h)
                except (Error, OSError):
                    template = None
                empty = _empty_fields(dossier.read_text(encoding="utf-8"), template, lvl)
                if empty:
                    errors.append(f"the dossier {h} has {len(empty)} empty fields (one writes «missing»)")
            else:
                errors.append(f"the dossier {dossier.relative_to(c)} is missing")
            if lvl >= 2:
                errors += _g4_rules2(conv, h, folder, not_delivered, warnings)
    elif phase == "f5":
        closure = f5_dir(conv, k) / n("CLOSURE.md")
        outcome = None
        if not full(closure):
            errors.append(f"{label}/{n('CLOSURE.md')} of the arbiter is missing")
        else:
            outcome = outcome_of(conv, k)
            if outcome is None:
                errors.append(f"{n('CLOSURE.md')} without the line {C.CONVENE_LINES['outcome'][conv.lang]}")
        info["closed"] = outcome == "closed"
        if m["strategy"] not in ("single", "fan-out"):
            bs = branches(conv)
            proven_ = [h for h in bs if proven(conv, h, warnings, lvl)]
            open_ = [h for h in bs if not valid(conv, g4_label(conv, h)) and not _early(conv, h)]
            r = m.get("radical")
            if lvl >= 2 and r and r not in bs and not _early(conv, r):
                open_.append(r)   # a radical recorded and never funded nor closed (ENG-8)
            if outcome == "not closed":
                unnamed = [h for h in open_ if h not in ids_in(closure)]
                if unnamed:
                    errors.append(f"branches without a valid G4 nor an early closure, not named in "
                                  f"{n('CLOSURE.md')}: {', '.join(unnamed)}")
            else:
                if open_:
                    errors.append(f"branches without a valid G4 nor an early closure: {', '.join(open_)}")
                if bs and not proven_:
                    errors.append("Outcome: closed but no H# proven by its verdict (Correctness proven or verified): "
                                  "the cycle does not close; a recorded non-closure has the other line of "
                                  f"{C.CONVENE_LINES['outcome'][conv.lang]}")
                    if lvl >= 2:
                        for h in bs:
                            g = read_gate(conv, g4_label(conv, h))
                            g4 = g4_label(conv, h)
                            if g and gate_rules(g) < 2 and valid(conv, g4) and _correctness(conv, h) is None:
                                errors.append(f"{h}: the verdict of its G4 of the rules 1 has no line "
                                              f"{C.CONVENE_LINES['correctness'][conv.lang]}: add it to "
                                              f"{arbiter_verdict(conv, h).relative_to(c)} and gate f4/{h} --rules 2")
            if lvl >= 2:
                text = closure.read_text(encoding="utf-8") if closure.is_file() else ""
                declared = re.search(C.CONVENE_LINES["declared_missing_re"], text, re.M | re.I)
                if sentinel_required(conv) and not sentinel_found(conv, k) and not declared:
                    errors.append(f"the sentinel is missing: {label}/{n('00-sentinel')}/{n('SENTINEL.md')}, or the "
                                  f"line {C.CONVENE_LINES['declared_missing'][conv.lang]} in {n('CLOSURE.md')}")
                # ENG-17: under the rules 3 the first closure also wants the sentinels of f3 and f4 that select or
                # fund briefed (a later closure has its own sentinel, beside it).
                for ph in ("f3", "f4") if lvl >= 3 and k == 1 else ():
                    task = sentinel_task(conv, ph)
                    if task and sentinel_required(conv) and not sentinel_found(conv, phase=ph) and not declared:
                        errors.append(f"the sentinel of {ph} is missing: {ph}/{task.parent.name}/{n('SENTINEL.md')}, "
                                      f"or the line {C.CONVENE_LINES['declared_missing'][conv.lang]} in "
                                      f"{n('CLOSURE.md')}")
                for h in all_branches(conv):
                    e = _early_data(conv, h)
                    if e.get("status") == "declared unresolved" and not (e.get("deciding_test") or "").strip():
                        errors.append(f"{h}: declared unresolved without the test that would decide it "
                                      f"({n('EARLY_CLOSURE.json')}): close-branch C {h} --reason … --deciding-test "
                                      f"TEXT adds it")
        if lvl >= 3:
            # ENG-15: every K# allocated in the convening's registry is accounted for by the closure, resolved or open.
            ctext = closure.read_text(encoding="utf-8", errors="replace") if closure.is_file() else ""
            named = set(k_ids_in(ctext))
            unnamed = [x for x in contradictions(conv) if x not in named]
            if unnamed:
                errors.append(f"K# allocated in {n('CONTRADICTIONS.jsonl')} and not named in {label}/"
                              f"{n('CLOSURE.md')}: {', '.join(unnamed)} (each resolved or open)")
            if closure.is_file():
                warnings += _unallocated(conv, [closure])
    return errors, info


def _g4_rules2(conv: Convening, h: str, folder: Path, nd: set[str], warnings: list[str]) -> list[str]:
    """The conditions of a G4 under the rules 2: the Correctness line (ENG-6), every briefed role delivered (ENG-7a),
    V2 by a role outside the f3 team on a proven result (ENG-7b); a warning without the sentinel (ENG-5)."""
    n = conv.name
    errors = []
    v = _correctness(conv, h, folder)
    if v is None:
        errors.append(f"{arbiter_verdict(conv, h, folder).relative_to(conv.folder)} without the line "
                      f"{C.CONVENE_LINES['correctness'][conv.lang]}")
    for p in _stray_correctness(conv, h, folder):
        errors.append(f"{p.relative_to(conv.folder)}: only the arbiter's verdict carries the line "
                      f"{C.CONVENE_LINES['correctness'][conv.lang]}")
    is_proven = v in PROVEN
    skip = {n("TASK.md"), *STATUS_NAMES}
    for d in sorted(folder.iterdir()) if folder.is_dir() else []:
        if not d.is_dir() or not re.match(r"\d\d-", d.name) or not (d / n("TASK.md")).is_file():
            continue
        role = _role_of(d.name)
        if _not_delivered(conv, role, nd) or (d.name.startswith("08-") and not is_proven):
            continue
        if not any(full(p) for p in _own_files(d) if p.suffix == ".md" and p.name not in skip):
            errors.append(f"{d.relative_to(conv.folder)}: no deliverable of {role} (or --not-delivered {role})")
    if is_proven:
        f3_team = team(conv, h)
        audits = [p for p in _own(folder, *HIDDEN_NAMES) if full(p) and len(p.relative_to(folder).parts) >= 2
                  and re.match(r"\d+-", p.relative_to(folder).parts[0])
                  and _role_of(p.relative_to(folder).parts[0]) not in f3_team]
        if not audits:
            errors.append(f"V2 missing on a proven result: {n('HIDDEN_ASSUMPTIONS.md')} under f4/{h}, by a role "
                          f"outside the f3 team ({', '.join(sorted(f3_team))})")
    k = _f5_now(conv)
    if sentinel_required(conv) and not sentinel_found(conv, k):
        where = f"{round_label('f5', k)}/{n('00-sentinel')}/{n('SENTINEL.md')}"
        warnings.append(f"no sentinel yet ({where}): G5 will require it" if level(conv) >= 2 else
                        f"no sentinel yet ({where}): a G5 under the rules 2 (--rules 2) would require it")
    return errors


def _f5_now(conv: Convening) -> int:
    """The closure that a gate f5 would check now, for a warning: the first when the gates f5 cannot be read."""
    try:
        return f5_gate_round(conv, verify=True)[0]
    except (Error, OSError, ValueError):
        return 1


def _first_seal(rows: dict, p: Path) -> float | None:
    """The time of the earliest seal of `p`: the first moment it is known to have existed."""
    times = [_iso(s["time"]) for s in rows.get(str(p), [])]
    return min(times) if times else None


def _whole_seal(rows: dict, p: Path) -> tuple[float | None, str | None]:
    """The time of the earliest seal that covers every byte of the PREDICTIONS.md `p`, or what is wrong: every seal of
    it is a prefix of it (it was only appended to), and the last block appended has a seal of its own (ENG-19)."""
    mine = rows.get(str(p), [])
    if not mine:
        return None, "born in f4 is not sealed"
    data = p.read_bytes()
    whole = []
    for s in mine:
        size = s.get("bytes")
        if size is None:   # a seal without its size covers the file only whole
            size = len(data) if s["sha256"] == hashlib.sha256(data).hexdigest() else -1
        if not 0 <= size <= len(data) or hashlib.sha256(data[:size]).hexdigest() != s["sha256"]:
            return None, "changed after the seal, not only at the end"
        if size == len(data):
            whole.append(_iso(s["time"]))
    if not whole:
        return None, ("has a block added after its last seal with no seal of its own: under the rules 3 every block "
                      "of a PREDICTIONS.md is sealed before the test it decides")
    return min(whole), None


def _order_rules3(conv: Convening, folder: Path) -> list[str]:
    """The order of a round of f4 under the rules 3 (ENG-19, ENG-21), read from the seal times of SEALS.jsonl and
    never from an mtime, which a copy or a touch moves:
    - a PREDICTIONS.md of the counterchecks' folder (01-), or outside any role folder, is a prediction before the
      counterchecks: sealed, whole, before every COUNTERCHECKS.md of the round is first sealed;
    - one of any other role folder is a post-countercheck prediction, of a role that works after the counterchecks
      (the owner's revision, the debugger, the measurements, V2, the arbiter): sealed, whole, before that role's own
      output is first sealed, whatever the seal of the counterchecks;
    - each REVISION.md is first sealed after every COUNTERCHECKS.md and DEFECTS.md of the round is.
    An output that something is ordered against must be sealed itself; the times are compared strictly, so two
    seals in the same second show no order."""
    c, n = conv.folder, conv.name
    rows = seal_rows(conv)
    errors: list[str] = []
    missing: set[Path] = set()

    def first(o: Path, who: str) -> float | None:
        t = _first_seal(rows, o)
        if t is None and o not in missing:
            missing.add(o)
            errors.append(f"{o.relative_to(c)} is not sealed: under the rules 3 {who} is ordered against it by the "
                          f"seals (seal C {o.relative_to(c)})")
        return t

    checks = _own(folder, n("COUNTERCHECKS.md"))
    defects = _own(folder, n("DEFECTS.md"))
    for p in _own(folder, n("PREDICTIONS.md")):
        t, wrong = _whole_seal(rows, p)
        if wrong:
            errors.append(f"{p.relative_to(c)} {wrong}")
            continue
        parts = p.relative_to(folder).parts
        role = folder / parts[0] if len(parts) > 1 and re.match(r"\d\d-", parts[0]) else None
        if role is None or f4_output(role.name) == "COUNTERCHECKS.md":
            targets, kind = checks, "a prediction before the counterchecks"
        else:
            own = role / n(f4_output(role.name))
            targets, kind = [own] if own.is_file() else [], "a post-countercheck prediction, against its own output"
        for o in targets:
            to = first(o, str(p.relative_to(c)))
            if to is not None and t >= to:
                when = "in the same second as" if t == to else "after"
                errors.append(f"{p.relative_to(c)} is sealed {when} {o.relative_to(c)}, which it must precede ({kind}; "
                              f"the seal times of {n('SEALS.jsonl')})")
    for r in _own(folder, n("REVISION.md")):
        tr = _first_seal(rows, r)
        if tr is None:
            if r not in missing:
                missing.add(r)
                errors.append(f"{r.relative_to(c)} is not sealed: under the rules 3 the revision is ordered after the "
                              f"counterchecks and the defects by the seals (seal C {r.relative_to(c)})")
            continue
        for o in checks + defects:
            to = first(o, str(r.relative_to(c)))
            if to is not None and tr <= to:
                errors.append(f"{r.relative_to(c)} is not sealed after {o.relative_to(c)}: the revision answers the "
                              f"counterchecks and the defects (the seal times of {n('SEALS.jsonl')})")
    return errors


def f4_output(folder_name: str) -> str:
    """The output of a briefed folder NN-<role> of f4, by its two digits (the canonical name)."""
    return F4_OUTPUTS.get(folder_name[:2], F4_MEASUREMENTS)


def _iso(s: str) -> float:
    return datetime.datetime.fromisoformat(s).timestamp()


def _tail_only(p: Path, s: dict) -> bool:
    """The seal still holds if the file was only appended to: the first bytes are the sealed ones."""
    data = p.read_bytes()
    n = s.get("bytes")
    return n is not None and len(data) >= n and hashlib.sha256(data[:n]).hexdigest() == s["sha256"]


def gate(ns) -> None:
    conv = Convening.load(Path(ns.C).resolve())
    phase = ns.phase
    mt = re.fullmatch(r"[Aa]?(\d+)", phase)
    if mt:
        phase = f"A{int(mt.group(1))}"
    if not re.fullmatch(r"f[0125]|f[34]/H-\d{3}|A\d+", phase):
        raise Error(f"unknown phase: {phase}")
    lvl = max(level(conv), ns.rules or 1)
    # f4/<H#> is the branch's latest round; f5 the closure that is open (5.3): the label names its folder and gate.
    label, new = phase, False
    if phase.startswith("f4/"):
        label = g4_label(conv, phase[3:])
    elif phase == "f5":
        k, new = f5_gate_round(conv, verify=ns.verify)
        label = round_label("f5", k)
    nd = {r.strip() for r in (ns.not_delivered or "").split(",") if r.strip()}
    errors, info = conditions(conv, label, nd, lvl)
    if errors:
        print(T("gate_refused", phase=label))
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    for w in info["warnings"]:
        print(T("gate_warning", text=w))
    if ns.verify:
        print(T("gate_holds", phase=label))
        return
    g = {"phase": label, "time": now(), "notes": ns.notes, "not_delivered": sorted(nd),
         "fingerprints": fingerprints(conv, label, lvl)}
    if lvl >= 2:   # a gate of the rules 1 keeps the keys of 5.0, so that an engine of 5.x still reads it
        g["rules"] = lvl
        if phase == "f5":
            g["closed"] = info.get("closed", False)
        if info["warnings"]:
            g["warnings"] = info["warnings"]
    if new:   # a G5 of a new closure never goes over a gate file, the record of a non-closure least of all
        conv.create_json(gate_file(conv, label), g, "gate")
    else:
        conv.write_json(gate_file(conv, label), g, "gate")
    if phase == "f5" and not info.get("closed", False):
        print(T("gate_approved_not_closed", phase=label, n=len(g["fingerprints"])))
    else:
        print(T("gate_approved", phase=label, n=len(g["fingerprints"])))


def hypothesis_card() -> str:
    for l in dict.fromkeys((language(), "en", "it")):
        p = BASE / S.localized_name(BASE, "HYPOTHESIS_CARD.md", l)
        if p.is_file():
            return p.read_text(encoding="utf-8")
    raise Error(f"the hypothesis card is missing in {BASE}: bash swarmer/swarmer.sh regenerate")


def base_inputs(conv: Convening) -> list[Path]:
    """The inputs every brief of a branch reads: the contract, its gated amendments, the cards, the triage, the
    tournament."""
    c, n = conv.folder, conv.name
    return ([conv.file("CONTRACT.md")] + gated_amendments(conv)
            + [c / "f2" / n("01-translation") / n("CARDS.md"), c / "f2" / n("03-triage") / n("TRIAGE.md"),
               c / "f2" / n("04-tournament") / n("TOURNAMENT.md")])


def owner_of(conv: Convening, h: str, prof: dict) -> str:
    """The owner of a branch: the role of its folder f3/<H>/01-<role>, otherwise the first f3 role of the profile."""
    d = conv.folder / "f3" / h
    found = sorted(x.name[3:] for x in d.iterdir() if x.is_dir() and x.name.startswith("01-")) if d.is_dir() else []
    return found[0] if found else prof["f3"][0]


def _branch_briefs(conv: Convening, h: str, owner_id: str | None, prof: dict, write: bool = True, k: int = 1,
                   rules: int | None = None) -> dict[Path, str]:
    """The dossier and the briefs of the branch `h`: f3 and the first round of f4 (select, fund), or round k of f4
    alone (repin), in f4_<k>/<H#>/ with a dossier of its own; written, or only returned (TASK path → text). `rules`
    are the rules the briefs are written for (those of the convening; 3 for a round after the first)."""
    c, n = conv.folder, conv.name
    rules = level(conv) if rules is None else rules
    base_in = base_inputs(conv)
    f3, f4 = c / "f3" / h, c / round_label(f"f4/{h}", k)
    prev = [] if k == 1 else [c / round_label(f"f4/{h}", k - 1)]
    dossier = dossier_of(conv, h, k)
    if write:
        (f3 if k == 1 else f4).mkdir(parents=True, exist_ok=k == 1)
        dossier.write_text(hypothesis_card().replace("H-000", h), encoding="utf-8")
    owner = owner_id or prof["f3"][0]
    check = next((r for r in prof["f3"][1:] if r not in (C.ROLES["adversary"], C.ROLES["metrologist"], owner)), C.ROLES["logician"])
    adv, dbg, arb = C.ROLES["adversary"], C.ROLES["debugger"], C.ROLES["arbiter"]
    inv = C.ROLES["inverter"]
    sol = f3 / f"01-{owner}" / n("SOLUTION.md")
    checks = f4 / f"01-{adv}" / n("COUNTERCHECKS.md")
    defects = f4 / "02-debugger" / n("DEFECTS.md")
    auditor = inv if inv not in (owner, check, C.ROLES["metrologist"], adv) else dbg
    f3_ = [f3] + prev   # what every brief of f4 reads of the branch: f3, and the previous round
    # ENG-20: G3 wants the line «decides: yes|no» in every PREDICTIONS.md of f3, so every f3 brief asks for it, the
    # companions' as the owner's (whose mission already says so).
    decides = " " + mission("f3_predictions")
    plan = [
        (f3 / f"01-{owner}", owner, "f3", "SOLUTION.md", mission("owner_solution", h=h), base_in, LIMIT_BRANCH),
        (f3 / f"02-{check}", check, "f3", "VERIFICATION.md", mission("proof", h=h) + decides, base_in + [sol],
         LIMIT_BRANCH),
        (f3 / f"03-{C.ROLES['metrologist']}", C.ROLES["metrologist"], "f3", "MEASUREMENT_PLAN.md",
         mission("measurement_plan", h=h) + decides, base_in + [sol], 30),
        (f3 / f"04-{adv}", adv, "f3", "ATTACK.md", mission("attack", h=h) + decides, base_in + [sol], 30),
    ] if k == 1 else []
    plan += [
        (f4 / f"00-{owner}", owner, "f4", F4_OUTPUTS["00"], mission("owner_revision", h=h),
         base_in + f3_ + [f4 / f"01-{adv}", f4 / "02-debugger"], LIMIT_BRANCH),
        (f4 / f"01-{adv}", adv, "f4", F4_OUTPUTS["01"], mission("counterchecks", h=h), base_in + f3_, LIMIT_BRANCH),
        (f4 / "02-debugger", dbg, "f4", F4_OUTPUTS["02"], mission("defects", h=h), base_in + f3_ + [f4 / f"01-{adv}"],
         LIMIT_F1),
    ]
    for i, role in enumerate([r for r in prof["f4"] if r not in (adv, dbg)], start=3):
        plan.append((f4 / f"{i:02d}-{role}", role, "f4", F4_MEASUREMENTS, mission("proof_contribution", h=h),
                     base_in + f3_ + [f4 / f"01-{adv}"], LIMIT_F1))
    plan += [
        (f4 / f"08-{auditor}", auditor, "f4", F4_OUTPUTS["08"], mission("hidden_assumption_audit", h=h),
         base_in + f3_ + [checks, defects], 30),
        (f4 / f"09-{arb}", arb, "f4", F4_OUTPUTS["09"], mission("verdict", h=h, dossier=dossier),
         base_in + f3_ + [f4], 30),
    ]
    out = {}
    for folder, role, phase, output, text, inputs, minutes in plan:
        if phase == "f4":
            text += _f4_notes(conv, h, k, f4, prev, output, rules)
        if write:
            brief(conv, folder, role, phase, output, text, inputs, minutes=minutes, h=h)
        out[folder / n("TASK.md")] = brief_text(conv, folder, role, phase, output, text, inputs, minutes=minutes, h=h)
    return out


def _f4_notes(conv: Convening, h: str, k: int, folder: Path, prev: list[Path], output: str, rules: int) -> str:
    """What a brief of f4 says besides its mission: the round, for a round after the first; where the predictions of
    its role go and what they are ordered against (COORD-1). Under the rules 3, the category of its folder: before
    the counterchecks for the counterchecks' own, against its own output for every role that works after them (and
    the revision after the counterchecks and the defects, COORD-2). Under the older rules, which order every
    PREDICTIONS.md of f4 before the counterchecks, a role that works after them is asked for none."""
    notes = []
    if k > 1:
        notes.append(mission("f4_round", k=k, h=h, previous=prev[0], folder=folder))
    if rules >= 3:
        notes.append(mission("predictions_before" if output == F4_OUTPUTS["01"] else "predictions_after",
                             output=conv.name(output)))
        if output == F4_OUTPUTS["00"]:
            notes.append(mission("revision_order"))
        if output == F4_OUTPUTS["09"]:   # the arbiter assigns the final K#: from the registry (ENG-15)
            notes.append(k_note(conv))
    elif output != F4_OUTPUTS["01"]:
        notes.append(mission("predictions_after_old", rules=rules, output=conv.name(output)))
    return "".join(" " + x for x in notes)


def k_note(conv: Convening) -> str:
    """What a brief of the rules 3 says of the K# (ENG-15): the coordinator allocates them in the registry."""
    return mission("k_registry", registry=f"`{conv.file('CONTRADICTIONS.jsonl')}`")


def _convened(conv: Convening, cat: dict, skip: Path | None = None) -> set[str]:
    """What a sentinel of the rules 3 is none of: every role that a brief of the convening names in its agent line
    (the lanes, f2, the teams of every round, the closures, the other sentinels; not the brief in `skip`, which is
    being rewritten), the folders NN-<role> of every branch, the fixed roles of the branches and every role of the
    profile, so that no later brief convenes it either."""
    c, m = conv.folder, conv.m
    used = set(m["f1"]) | {v["role"] for v in m["f1"].values() if v.get("role")}
    used |= {C.ROLES[x] for x in ("arbiter", "adversary", "debugger", "metrologist", "inverter")}
    prof = cat.get("profiles", {}).get(m["profile"], {})
    for key in ("A", "B", "translates", "f3", "f4"):
        used |= set(prof.get(key, []))
    for task in _own(c, conv.name("TASK.md")):
        if skip is None or task.parent != skip:
            used |= {brief_agent(task)} - {None}
    for h in all_branches(conv):
        for f in [c / "f3" / h] + [f4_dir(conv, h, j) for j in f4_rounds(conv, h)]:
            if f.is_dir():
                used |= {_role_of(x.name) for x in f.iterdir() if x.is_dir() and re.match(r"\d+-", x.name)}
    return used


def _draw_sentinel(conv: Convening, cat: dict, skip: Path | None = None) -> tuple[str, str]:
    """A sentinel of the rules 3 (ENG-16), and the record of its draw for its brief: drawn with the convening's seed
    among the free roles (those `_convened` does not hold) fit for the question, a keyword of their own in it, as
    `roles --question` finds them, the professionals first; among all the free roles when none is fit; the logician
    when none is free."""
    m = conv.m
    used = _convened(conv, cat, skip)
    free = [r for r in cat["roles"] if r["id"] not in used]
    hits = {r["id"]: keyword_hits(r, m.get("question") or "") for r in free}
    fit = [r for r in free if hits[r["id"]]]

    def pool_of(rs):
        return sorted(r["id"] for r in ([r for r in rs if r.get("type", "professional") == "professional"] or rs))

    seed = m.get("seed")
    if fit:
        pool = pool_of(fit)
        role = random.Random(seed).choice(pool)
        return role, mission("sentinel_draw", seed=seed, n=len(pool), pool=", ".join(pool), words=", ".join(hits[role]))
    if free:
        pool = pool_of(free)
        return random.Random(seed).choice(pool), mission("sentinel_draw_unfit", seed=seed, n=len(pool))
    return C.ROLES["logician"], mission("sentinel_draw_none", role=C.ROLES["logician"])


def _phase_sentinel(conv: Convening, cat: dict, phase: str, inputs: list[Path]) -> Path | None:
    """The brief of the sentinel of f2, f3 or f4 (ENG-17), in <phase>/00-sentinel/, written once: a brief already
    there is never rewritten, so its draw stays as recorded and the gate that binds its folder holds."""
    if sentinel_task(conv, phase):
        return None
    role, record = _draw_sentinel(conv, cat)
    text = " ".join([mission(f"sentinel_{phase}"), record, k_note(conv)])
    return brief(conv, conv.folder / phase / conv.name("00-sentinel"), role, phase, "SENTINEL.md", text, inputs,
                 minutes=20)


def _phase_sentinels(conv: Convening, cat: dict, f5k: int) -> None:
    """The sentinels of f3 and f4 (ENG-17), briefed by select or fund under the rules 3 in a classic or a full with at
    least two funded branches, before any G5: the first G5 binds their folders, so none is written after it (a later
    closure has its own sentinel). A round opened by repin has none of its own: the next closure's sentinel reads it."""
    c, m, n = conv.folder, conv.m, conv.name
    if level(conv) < 3 or f5k > 1 or m["strategy"] not in ("classic", "full") or len(branches(conv)) < 2:
        return
    base = [conv.file("CONTRACT.md")] + gated_amendments(conv) + [c / "f2" / n("05-selection") / n("SELECTION.md")]
    _phase_sentinel(conv, cat, "f3", base + [c / "f3"])
    _phase_sentinel(conv, cat, "f4", base + [c / "f3", c / "f4"])


def _sentinel_roles(conv: Convening) -> set[str]:
    """The roles of the sentinels briefed by the engine: those of f3 and f4, and those of every closure."""
    out = {brief_agent(t) for t in (sentinel_task(conv, ph) for ph in ("f3", "f4")) if t}
    for d in conv.folder.iterdir() if conv.folder.is_dir() else []:
        if d.is_dir() and split_label(d.name)[0] == "f5":
            out |= {brief_agent(d / x / conv.name("TASK.md")) for x in SENTINEL_DIRS
                    if (d / x / conv.name("TASK.md")).is_file()}
    return out - {None}


def _no_sentinel_owner(conv: Convening, owner_id: str | None) -> None:
    """Under the rules 3 a sentinel stays a role that was not convened: fund and repin refuse it as an owner."""
    if owner_id and level(conv) >= 3 and owner_id in _sentinel_roles(conv):
        raise Error(f"{owner_id} is a sentinel of this convening: a sentinel is a role that was not convened, so it "
                    f"owns no branch (choose another --owner)")


def _sentinel_brief(conv: Convening, cat: dict, k: int = 1) -> Path | None:
    """The brief of the sentinel (ENG-5) beside the k-th closure, in a classic or a full with at least two funded
    branches: a role drawn with the seed among those in no lane of f1, in no branch team of any round and not the
    sentinel of an earlier closure. Under the rules 3 the draw of `_draw_sentinel`, recorded in the brief."""
    c, m, n = conv.folder, conv.m, conv.name
    bs = branches(conv)
    if m["strategy"] not in ("classic", "full") or len(bs) < 2:
        return None
    inputs = ([conv.file("CONTRACT.md")] + gated_amendments(conv)
              + [c / "f2" / n("05-selection") / n("SELECTION.md"), c / "f3", c / "f4"] + _round_dirs(conv))
    if level(conv) >= 3:
        folder = f5_dir(conv, k) / n("00-sentinel")
        role, record = _draw_sentinel(conv, cat, skip=folder)
        return brief(conv, folder, role, "f5", "SENTINEL.md", " ".join([mission("sentinel"), record, k_note(conv)]),
                     inputs, minutes=20)
    used = set(m["f1"]) | {C.ROLES["arbiter"]}
    for h in bs:
        for f in [c / "f3" / h] + [f4_dir(conv, h, j) for j in f4_rounds(conv, h)]:
            if f.is_dir():
                used |= {_role_of(x.name) for x in f.iterdir() if x.is_dir() and re.match(r"\d+-", x.name)}
    agents = tuple(f"{p}-" for p in dict.fromkeys((prefix(), *C.AGENT_PREFIXES)))
    for j in range(1, k):
        task = f5_dir(conv, j) / n("00-sentinel") / n("TASK.md")
        if task.is_file():
            text = task.read_text(encoding="utf-8", errors="replace")
            used |= {_role_id(x) for x in re.findall(r"`([^`/\s]+)`", text) if x.startswith(agents)}
    free = [r for r in cat["roles"] if r["id"] not in used]
    pool = sorted(r["id"] for r in free if r.get("type", "professional") == "professional") or sorted(
        r["id"] for r in free) or [C.ROLES["logician"]]
    role = random.Random(m["seed"]).choice(pool)
    return brief(conv, f5_dir(conv, k) / n("00-sentinel"), role, "f5", "SENTINEL.md", mission("sentinel"), inputs,
                 minutes=20)


def _closure_brief(conv: Convening, k: int = 1) -> Path:
    """The brief of the k-th closure (ENG-9): every input the arbiter needs, and the output where G5 looks for it;
    a later closure goes beside the first, in f5_<k>/, and reads the earlier ones."""
    c, m, n = conv.folder, conv.m, conv.name
    try:
        prof = catalog()["profiles"].get(m["profile"], {"f3": [C.ROLES["logician"]]})
    except (Error, OSError, ValueError):
        prof = {"f3": [C.ROLES["logician"]]}
    inputs = [conv.file("CONTRACT.md")] + gated_amendments(conv) + [
        c / "f2" / n("05-selection") / n("SELECTION.md")] + [f5_dir(conv, j) / n("CLOSURE.md") for j in range(1, k)]
    for h in all_branches(conv):
        if _early(conv, h):
            inputs.append(c / "f3" / h / n("EARLY_CLOSURE.json"))
        elif h in branches(conv):
            # The revision and the sentinel only where they were briefed (a convening of 5.0 has neither); the
            # dossier, the revision and the verdict of the branch's latest round.
            revision = f4_dir(conv, h) / f"00-{owner_of(conv, h, prof)}"
            inputs += [dossier_of(conv, h, f4_round(conv, h))] + (
                [revision / n("REVISION.md")] if (revision / n("TASK.md")).is_file() else []
            ) + [arbiter_verdict(conv, h)]
    # The sentinels of f2, f3 and f4 where the engine briefed them (ENG-17), then the closure's own.
    inputs += [t.parent / n("SENTINEL.md") for t in (sentinel_task(conv, ph) for ph in PHASE_SENTINELS) if t]
    sentinel = f5_dir(conv, k) / n("00-sentinel")
    if m["strategy"] in ("classic", "full") and len(branches(conv)) >= 2 and (sentinel / n("TASK.md")).is_file():
        inputs.append(sentinel / n("SENTINEL.md"))
    inputs += [c / "GATE_*.json", c / "f3", c / "f4"] + _round_dirs(conv)
    closure = f5_dir(conv, k) / n("CLOSURE.md")
    # ENG-23: what G5 checks for a non-closure, and the branches it checks it on: every funded branch not closed
    # early, and a radical neither funded nor closed (each, unless its G4 holds by the closure).
    listed = [h for h in branches(conv) if not _early(conv, h)]
    r = m.get("radical")
    if r and r not in branches(conv) and not _early(conv, r):
        listed.append(mission("closure_radical", h=r))
    text = mission("closure", closure_file=closure,
                   open=mission("closure_open", branches=", ".join(listed) or mission("closure_none")))
    if level(conv) >= 3:
        text += " " + k_note(conv) + " " + mission("k_closure", registry=f"`{conv.file('CONTRADICTIONS.jsonl')}`",
                                                   closure_file=f"`{closure}`")
    return brief(conv, f5_dir(conv, k) / f"01-{C.ROLES['arbiter']}", C.ROLES["arbiter"], "f5", "CLOSURE.md",
                 text, inputs, minutes=30, output_path=closure)


def select(ns) -> None:
    conv = Convening.load(Path(ns.C).resolve())
    c, m, n = conv.folder, conv.m, conv.name
    if m["strategy"] in ("single", "fan-out"):
        raise Error("in the single and in the fan-out there are no hypotheses to select")
    if not valid(conv, "f2"):
        raise Error("the gate f2 is not approved or no longer valid")
    chosen = [norm_id(h) for h in ns.hypotheses]
    radical = norm_id(ns.radical) if ns.radical else None
    # Once (ENG-22): a second select would write the empty card over a completed dossier and the briefs over the
    # branches' work, and would replace the recorded selection.
    there = [h for h in chosen + ([radical] if radical else []) if (c / "f3" / h).exists()]
    if m["selected"] or m.get("radical") or there:
        raise Error(f"the convening already has its selection ({', '.join(all_branches(conv) or there)}): select runs "
                    f"once; fund C H-00x briefs the radical, repin C H-00x opens a new round of a branch")
    if len(chosen) > 3:
        raise Error("at most three H# plus a radical one")
    allowed = set(ids_in(c / "f2" / n("03-triage") / n("TRIAGE.md"))) & set(
        ids_in(c / "f2" / n("05-selection") / n("SELECTION.md")))
    for h in chosen + ([radical] if radical else []):
        if h not in allowed:
            raise Error(f"{h} is not in the triage and in the countersigned selection")
    cat = catalog()
    prof = cat["profiles"][m["profile"]]
    owner_id = _role_id(ns.owner) if ns.owner else None
    if owner_id and owner_id not in {r["id"] for r in cat["roles"]}:
        raise Error(f"unknown role: {ns.owner}")
    hypothesis_card()
    f5k = f5_open(conv, "selected")
    lvl = level(conv)
    # Under the rules 2 the radical is only recorded: `fund` briefs it (ENG-8).
    for h in chosen + ([radical] if radical and lvl < 2 else []):
        _branch_briefs(conv, h, owner_id, prof)
    m["selected"], m["radical"] = chosen, radical
    if lvl >= 2:
        if radical:
            m["radical_funded"] = False
        else:
            m.pop("radical_funded", None)
    conv.save()
    _phase_sentinels(conv, cat, f5k)
    _sentinel_brief(conv, cat, f5k)
    _closure_brief(conv, f5k)
    print(T("branches_open", ids=", ".join(branches(conv))))
    if radical and not funded(conv):
        print(T("radical_recorded", h=radical))


def fund(ns) -> None:
    """Briefs the radical branch, recorded by select under the rules 2 (ENG-8)."""
    conv = Convening.load(Path(ns.C).resolve())
    m = conv.m
    h = norm_id(ns.hypothesis)
    if m["strategy"] in ("single", "fan-out"):
        raise Error("in the single and in the fan-out there are no branches to fund")
    if not valid(conv, "f2"):
        raise Error("the gate f2 is not approved or no longer valid")
    if h != m.get("radical"):
        raise Error(f"{h} is not the radical branch of the selection")
    f5k = f5_open(conv, "funded")   # after a G5 «not closed» that holds, the next closure (5.3)
    if funded(conv):
        raise Error(f"{h} is already funded")
    if _early(conv, h):
        raise Error(f"{h} is already closed")
    cat = catalog()
    prof = cat["profiles"][m["profile"]]
    owner_id = _role_id(ns.owner) if ns.owner else None
    if owner_id and owner_id not in {r["id"] for r in cat["roles"]}:
        raise Error(f"unknown role: {ns.owner}")
    _no_sentinel_owner(conv, owner_id)
    _branch_briefs(conv, h, owner_id, prof)
    m["radical_funded"] = True
    conv.save()
    _phase_sentinels(conv, cat, f5k)
    _sentinel_brief(conv, cat, f5k)
    _closure_brief(conv, f5k)
    print(T("branch_funded", h=h))
    notice = translation_notice(cat, BRIEFED)
    if notice:
        print(notice)


def _remove_unused_briefs(conv: Convening, h: str) -> None:
    """After an early closure, the f3/f4 folders of `h` that hold only the TASK.md the engine wrote, unchanged."""
    try:
        prof = catalog()["profiles"][conv.m["profile"]]
    except (Error, OSError, KeyError, ValueError):
        return
    expected = _branch_briefs(conv, h, owner_of(conv, h, prof), prof, write=False)
    for task, text in expected.items():
        d = task.parent
        if not d.is_dir() or d.is_symlink():
            continue
        files = [p for p in d.rglob("*") if not p.is_dir()]
        if files == [task] and task.read_text(encoding="utf-8", errors="replace") == text:
            shutil.rmtree(d)
    f4 = conv.folder / "f4" / h
    if f4.is_dir() and not any(f4.iterdir()):
        f4.rmdir()


def close_branch(ns) -> None:
    conv = Convening.load(Path(ns.C).resolve())
    m = conv.m
    h = norm_id(ns.hypothesis)
    if h not in all_branches(conv):
        raise Error(f"{h} is not selected")
    f5k = f5_open(conv, "closed")   # after a G5 «not closed» that holds, the next closure (5.3)
    p = conv.folder / "f3" / h / conv.name("EARLY_CLOSURE.json")
    test = (ns.deciding_test or "").strip()
    if p.exists():
        # A closure declared unresolved before --deciding-test existed (5.0) gets its test, and nothing else changes.
        data = _early_data(conv, h)
        if data.get("status") == "declared unresolved" and not (data.get("deciding_test") or "").strip() and test:
            data["deciding_test"] = test
            conv.write_json(p, data, "early_closure")
            print(T("deciding_test_added", h=h))
            if m["strategy"] in ("classic", "full"):
                _closure_brief(conv, f5k)
            return
        raise Error(f"{h} is already closed")
    if valid(conv, f"f3/{h}"):
        raise Error(f"{h} already has a G3: the early closure holds only before")
    data = {"time": now(), "hypothesis": h, "reason": ns.reason}
    if h not in branches(conv):
        p.parent.mkdir(parents=True, exist_ok=True)
        data["status"] = "not funded"
        conv.write_json(p, data, "early_closure")
        print(T("branch_not_funded", h=h))
    else:
        if level(conv) >= 2 and not test:
            raise Error(f"{h} is funded: under the rules 2 it closes early only with --deciding-test TEXT, the test "
                        f"that would decide it")
        data["status"] = "declared unresolved"
        if test:
            data["deciding_test"] = test
        conv.write_json(p, data, "early_closure")
        if level(conv) >= 2:   # under the rules 1 the briefs stay, as in 5.0
            _remove_unused_briefs(conv, h)
        print(T("branch_closed", h=h))
    if m["strategy"] in ("classic", "full"):
        _closure_brief(conv, f5k)


def repin(ns) -> None:
    """Opens the next round of the f4 of a branch, on a revised pin (ENG-18): f4_<n>/<H#>/ with every brief of f4
    and the dossier of the round, from the card. The earlier rounds, the f3 dossier, the seals and the gates are not
    touched; the G4 of the round runs under the rules 3 and binds and counts only the round's own files."""
    conv = Convening.load(Path(ns.C).resolve())
    m = conv.m
    h = norm_id(ns.hypothesis)
    if m["strategy"] in ("single", "fan-out"):
        raise Error("in the single and in the fan-out there are no branches to re-pin")
    if not valid(conv, "f2"):
        raise Error("the gate f2 is not approved or no longer valid")
    if h not in branches(conv):
        raise Error(f"{h} is not a funded branch" + (f": fund C {h} first" if h == m.get("radical") else ""))
    if _early(conv, h):
        raise Error(f"{h} is closed early: it has no new round")
    f5k = f5_open(conv, "re-pinned")
    cat = catalog()
    prof = cat["profiles"][m["profile"]]
    owner_id = _role_id(ns.owner) if ns.owner else None
    if owner_id and owner_id not in {r["id"] for r in cat["roles"]}:
        raise Error(f"unknown role: {ns.owner}")
    _no_sentinel_owner(conv, owner_id)
    hypothesis_card()
    k = f4_round(conv, h) + 1
    folder = f4_dir(conv, h, k)
    if folder.exists():
        raise Error(f"{folder} already exists")
    _branch_briefs(conv, h, owner_id or owner_of(conv, h, prof), prof, k=k, rules=max(3, level(conv)))
    _sentinel_brief(conv, cat, f5k)
    _closure_brief(conv, f5k)
    print(T("repinned", h=h, k=k, path=folder))
    notice = translation_notice(cat, BRIEFED)
    if notice:
        print(notice)


def status(ns) -> None:
    conv = Convening.load(Path(ns.C).resolve())
    m = conv.m
    lvl = level(conv)
    print(T("status_head", name=m["name"], strategy=shown("strategy", m["strategy"]),
            profile=shown("profile", m["profile"])))
    phases = ["f0"]
    clashes = []
    phases += [a for a in amendment_phases(conv, clashes) if lvl >= 2 or gate_file(conv, a).exists()]
    for x in clashes:
        print(T("status_clash", text=x))
    phases += ["f1"] + ([] if m["strategy"] in ("single", "fan-out") else ["f2"])
    for h in all_branches(conv):
        phases += [f"f3/{h}"] + ([round_label(f"f4/{h}", k) for k in f4_rounds(conv, h)] if h in branches(conv)
                                 else [])
    if m["strategy"] not in ("single", "fan-out"):
        # Every G5 by ordinal, and the closure that a G5 «not closed» opened, still to approve.
        phases += [round_label("f5", k) for k in g5_ordinals(conv)] or ["f5"]
        last = latest_g5(conv)
        if last and g5_open(conv, *last) and f5_dir(conv, last[0] + 1).exists():
            phases.append(round_label("f5", last[0] + 1))
    for label in phases:
        phase, k = split_label(label)
        if phase.startswith("f3/") and _early(conv, phase[3:]):
            print(T("status_early", phase=phase))
            continue
        if phase.startswith("f3/") and phase[3:] not in branches(conv):
            print(T("status_not_funded", phase=phase, h=phase[3:]))
            continue
        g = read_gate(conv, label)
        if g is None:
            print(T("status_pending", phase=label))
            continue
        if phase.startswith("f3/"):
            # A G3 of the rules 1 holds without its dossier once a G4 of the branch was approved under the rules 2.
            g4s = [read_gate(conv, round_label("f4/" + phase[3:], j)) for j in f4_rounds(conv, phase[3:])]
            ok = g3_holds(conv, phase[3:], max([lvl] + [gate_rules(x) for x in g4s if x]))
        else:
            ok = valid(conv, label)
        closed = g.get("closed")
        if closed is None and phase == "f5" and gate_rules(g) < 2:
            closed = outcome_of(conv, k) != "not closed"   # a G5 of the rules 1 records no «closed»
        if ok and phase == "f5" and closed is False:
            print(T("status_not_closed", phase=label))
        else:
            print(T("status_approved" if ok else "status_invalid", phase=label))
    ks = contradictions(conv)   # ENG-15: the K# of the convening, when it has any
    if ks:
        print(T("status_contradictions", ids=", ".join(ks), path=conv.file("CONTRADICTIONS.jsonl").name))


def build_parser(al: dict) -> argparse.ArgumentParser:
    p = A.parser(prog="convene", description=__doc__.replace("swarmer:", f"swarmer {swarmer_version()}:", 1),
                 formatter_class=argparse.RawDescriptionHelpFormatter)
    add = A.subparsers(p, al)
    q = add("roles")
    A.arg(q, al, "--question")
    q = add("prepare")
    A.arg(q, al, "--name", required=True)
    A.arg(q, al, "--strategy", required=True)
    A.arg(q, al, "--profile", required=True)
    A.arg(q, al, "--question", required=True)
    A.arg(q, al, "--roles")
    A.arg(q, al, "--dest")
    A.arg(q, al, "--seed", type=int)
    A.arg(q, al, "--n", type=int, help="fan-out: the total number of agents, from 2 to 16")
    A.arg(q, al, "--form", help="fan-out: slices, race or mixed")
    A.arg(q, al, "--rule", help="fan-out, race or mixed: the choice rule declared first")
    q = add("snapshot")
    q.add_argument("C")
    q = add("gate")
    q.add_argument("C")
    q.add_argument("phase")
    A.arg(q, al, "--notes", required=True)
    A.arg(q, al, "--not-delivered")
    A.arg(q, al, "--verify", action="store_true")
    A.arg(q, al, "--rules", type=int, choices=(1, 2, 3),
          help="the rules of this gate, when higher than the convening's (gate_rules in the manifest)")
    q = add("seal")
    q.add_argument("C")
    q.add_argument("file", nargs="+")
    q = add("contradiction")
    q.add_argument("C")
    q.add_argument("file", nargs="+")
    A.arg(q, al, "--question", required=True, help="the binary question of the contradiction")
    q = add("select")
    q.add_argument("C")
    q.add_argument("hypotheses", nargs="+")
    A.arg(q, al, "--radical")
    A.arg(q, al, "--owner", metavar="ID")
    q = add("fund")
    q.add_argument("C")
    q.add_argument("hypothesis")
    A.arg(q, al, "--owner", metavar="ID")
    q = add("close-branch")
    q.add_argument("C")
    q.add_argument("hypothesis")
    A.arg(q, al, "--reason", required=True)
    A.arg(q, al, "--deciding-test", help="the test that would decide the branch (required under the rules 2 for a "
                                         "funded branch)")
    q = add("repin")
    q.add_argument("C")
    q.add_argument("hypothesis")
    A.arg(q, al, "--owner", metavar="ID")
    q = add("status")
    q.add_argument("C")
    return p


def main(argv=None) -> None:
    al = A.load(BASE)
    ns = build_parser(al).parse_args(sys.argv[1:] if argv is None else argv)
    commands = {"roles": roles, "prepare": prepare, "snapshot": snapshot, "gate": gate, "seal": seal,
                "contradiction": contradiction, "select": select, "fund": fund, "close-branch": close_branch,
                "repin": repin, "status": status}
    try:
        commands[ns.command](ns)
    except (C.Error, OSError, ValueError) as e:
        print(f"convene: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
