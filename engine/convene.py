#!/usr/bin/env python3
"""swarmer 5.0: prepares the skeleton of a convening (single, fan-out, classic or full) and checks its gates. Jury
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
  gate      C PHASE --notes TEXT [--not-delivered ROLE,…] [--verify] [--rules 1|2]
            PHASE = f0, A1 (the amendment AMENDMENT_1.md or AMENDMENT_A1.md), f1, f2, f3/H-001, f4/H-001, f5
  seal      C FILE…               time and sha256 in SEALS.jsonl
  select    C H-001 [H-002 H-003] [--radical H-00x] [--owner ID]
  fund      C H-00x [--owner ID]  briefs the radical branch (gate rules 2: select does not brief it)
  close-branch C H-00x --reason TEXT [--deciding-test TEXT]   (on a closure of 5.0 without a test: adds the test)
  status    C

The rules of the gates have a version (the manifest key gate_rules; a missing key means 1). A new convening is born
with the rules 2; a gate is always recomputed under the rules it was approved with, so upgrading the engine never
invalidates an approved gate. `gate --rules 2` applies the rules 2 to one new gate of an older convening.
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
VERSION = "5.0"
STRATEGIES = ("single", "fan-out", "classic", "full")
FORMS = ("slices", "race", "mixed")
RULES = ("first", "ranking", "best")
CONTRACT_FIELDS = tuple(C.CONVENE_LINES["contract_fields"])   # canonical (English) headings
TO_FILL = tuple(C.CONVENE_LINES["to_fill_in"].values())
ID = re.compile(r"\bH-?0*(\d{1,3})\b")
LIMIT_F1 = 40   # minutes for a brief of f1
LIMIT_BRANCH = 60
GATE_RULES = 2   # the rules of the gates a new convening is born with
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
HIDDEN_NAMES = ("HIDDEN_ASSUMPTIONS.md", C.CONVENE_FILES["HIDDEN_ASSUMPTIONS.md"])
AMENDMENT_RE = re.compile("|".join(f"(?:{p[0]})|(?:{p[2]})" for p in C.CONVENE_PATTERNS if p[1].startswith("AMENDMENT")))


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
        self.file("MANIFEST.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    def name(self, canonical: str) -> str:
        return C.localize_path(canonical, self.lang, "convene")

    def file(self, canonical: str) -> Path:
        return self.folder / self.name(canonical)

    def read_json(self, p: Path, kind: str) -> dict:
        return C.to_canonical(json.loads(p.read_text(encoding="utf-8")), C.CONVENE_KEYS[kind], p.name)

    def write_json(self, p: Path, data: dict, kind: str, indent=1) -> None:
        p.write_text(json.dumps(C.to_dialect(data, C.CONVENE_KEYS[kind], self.lang), ensure_ascii=False,
                                indent=indent), encoding="utf-8")


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


def roles(ns) -> None:
    """The roles, and the profiles. With a question, only the roles one of whose keywords appears in the text, whole."""
    cat = catalog()
    pre = cat.get("prefix") or prefix()
    cores = {n["id"]: n["name"].lower() for n in cat["cores"]}
    text = (ns.question or "").lower()
    found = 0
    for r in cat["roles"]:
        words = list(dict.fromkeys(p.lower() for p in r["keywords"]
                                   if re.search(rf"(?<!\w){re.escape(p.lower())}(?!\w)", text))) if text else []
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
    m = {"version": VERSION, "name": name, "strategy": strategy, "profile": profile, "question": ns.question,
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
        for k in range(1, ns.n + 1):
            role = roles_v[(k - 1) % len(roles_v)]
            folder = c / "f1" / conv.name(f"agent-{k}")
            brief(conv, folder, role, "f1", deliverable, mission("race" if form == "race" else "fan_out_slice")
                  + ("" if form == "race" else "\n\n" + T("slice", k=k, n=ns.n)), inputs)
            m["f1"][f"agent-{k}"] = {"folder": str(folder), "lane": form, "role": role}
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
            brief(conv, c / "f1c" / C.ROLES["arbiter"], C.ROLES["arbiter"], "f1c", "CONSOLIDATION.md", mission("consolidation"),
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


def seals(conv: Convening) -> dict[str, dict]:
    p = conv.file("SEALS.jsonl")
    found = {}
    for line in p.read_text(encoding="utf-8").splitlines() if p.exists() else []:
        s = C.to_canonical(json.loads(line), C.CONVENE_KEYS["seal"], p.name)
        found.setdefault(s["file"], s)
    return found


def ids_in(p: Path) -> list[str]:
    if not p.exists():
        return []
    return list(dict.fromkeys(f"H-{int(n):03d}" for n in ID.findall(p.read_text(encoding="utf-8"))))


def full(p: Path) -> bool:
    text = p.read_text(encoding="utf-8", errors="replace") if p.is_file() else ""
    return p.is_file() and p.stat().st_size > 0 and not any(x in text for x in TO_FILL)


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
    """A folder f3/<H#>/NN-<role> or f4/<H#>/NN-<role> (a briefed role): always the convening's own."""
    return bool(re.match(r"\d+-", d.name) and ID.fullmatch(d.parent.name) and d.parent.parent.name in ("f3", "f4"))


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
    if phase.startswith("f3/") or phase.startswith("f4/"):
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
    return "tree:" + hashlib.sha256("".join(sorted(lines)).encode("utf-8")).hexdigest()


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


def dossier_of(conv: Convening, h: str) -> Path:
    return conv.folder / "f3" / h / f"{h}.md"


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
            _FP[key] = (fingerprints_v2 if rules >= 2 else fingerprints_v1)(conv, phase)
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


def arbiter_verdict(conv: Convening, h: str) -> Path:
    """The verdict of the arbiter of `h`: f4/<H#>/NN-arbitro/VERDICT.md, the folder select briefs (09-arbitro)."""
    d = conv.folder / "f4" / h
    folders = [x for x in sorted(d.iterdir()) if x.is_dir() and re.match(r"\d+-", x.name)
               and _role_of(x.name) == C.ROLES["arbiter"]] if d.is_dir() else []
    for x in folders:
        if (x / conv.name("VERDICT.md")).is_file():
            return x / conv.name("VERDICT.md")
    return d / f"09-{C.ROLES['arbiter']}" / conv.name("VERDICT.md")


def _correctness(conv: Convening, h: str) -> str | None:
    """The canonical value of the line «Correctness: …» of the arbiter's verdict of `h`, or None: no other VERDICT.md
    of the branch counts."""
    return _correctness_in(arbiter_verdict(conv, h))


def _stray_correctness(conv: Convening, h: str) -> list[Path]:
    """The VERDICT.md files of the branch, other than the arbiter's, that carry a Correctness line."""
    own = arbiter_verdict(conv, h)
    return [p for p in _own(conv.folder / "f4" / h, conv.name("VERDICT.md")) if p != own and _correctness_in(p)]


def proven(conv: Convening, h: str, warnings: list[str] | None = None, lvl: int = 1) -> bool:
    """`h` is proven: a valid G4 and an arbiter's verdict with Correctness proven or verified. Under the rules 1 a G4
    of the rules 1 whose verdict has no Correctness line keeps the old rule (a valid G4), with a warning; under the
    rules 2 (`lvl`, the rules of the G5) it is not proven (ENG-6)."""
    g = read_gate(conv, f"f4/{h}")
    if g is None or not valid(conv, f"f4/{h}"):
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


def sentinel_found(conv: Convening) -> bool:
    """The sentinel's deliverable, f5/00-sentinel/SENTINEL.md: f5 is bound by G5 alone, so writing it invalidates no
    earlier gate."""
    return any(full(conv.folder / "f5" / d / n) for d in SENTINEL_DIRS for n in SENTINEL_NAMES)


def outcome_of(conv: Convening) -> str | None:
    """The canonical outcome of f5/CLOSURE.md («closed» or «not closed»), or None."""
    closure = conv.folder / "f5" / conv.name("CLOSURE.md")
    if not closure.is_file():
        return None
    mt = re.search(C.CONVENE_LINES["outcome_re"], closure.read_text(encoding="utf-8", errors="replace"), re.M)
    return C.LINE_VALUES["outcome"][mt.group(1) or mt.group(2)] if mt else None


def _not_delivered(conv: Convening, role: str, nd: set[str]) -> bool:
    return role in nd or conv.name(role) in nd or f"{prefix()}-{role}" in nd


def conditions(conv: Convening, phase: str, not_delivered: set[str], lvl: int = 1) -> tuple[list[str], dict]:
    """The errors of a gate, and what the gate records besides (the warnings; for f5 whether it closes)."""
    c, m, n = conv.folder, conv.m, conv.name
    errors = []
    info = {"warnings": []}
    warnings = info["warnings"]
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
            if not s or not s.group(1).strip() or any(x in s.group(1) for x in TO_FILL):
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
    elif phase.startswith("f3/") or phase.startswith("f4/"):
        h = phase[3:]
        if h not in all_branches(conv):
            errors.append(f"{h} is not selected")
        elif h not in branches(conv):
            errors.append(f"radical not funded: fund C {h}")
        if _early(conv, h):
            errors.append(f"the branch {h} is closed early: no G3 nor G4")
        folder = c / phase
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
                    errors.append(f"{phase}: {n(name)} is missing")
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
            dossier = dossier_of(conv, h)
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
        closure = c / "f5" / n("CLOSURE.md")
        outcome = None
        if not full(closure):
            errors.append(f"f5/{n('CLOSURE.md')} of the arbiter is missing")
        else:
            outcome = outcome_of(conv)
            if outcome is None:
                errors.append(f"{n('CLOSURE.md')} without the line {C.CONVENE_LINES['outcome'][conv.lang]}")
        info["closed"] = outcome == "closed"
        if m["strategy"] not in ("single", "fan-out"):
            bs = branches(conv)
            proven_ = [h for h in bs if proven(conv, h, warnings, lvl)]
            open_ = [h for h in bs if not valid(conv, f"f4/{h}") and not _early(conv, h)]
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
                            g = read_gate(conv, f"f4/{h}")
                            if g and gate_rules(g) < 2 and valid(conv, f"f4/{h}") and _correctness(conv, h) is None:
                                errors.append(f"{h}: the verdict of its G4 of the rules 1 has no line "
                                              f"{C.CONVENE_LINES['correctness'][conv.lang]}: add it to "
                                              f"{arbiter_verdict(conv, h).relative_to(c)} and gate f4/{h} --rules 2")
            if lvl >= 2:
                text = closure.read_text(encoding="utf-8") if closure.is_file() else ""
                if sentinel_required(conv) and not sentinel_found(conv) and not re.search(
                        C.CONVENE_LINES["declared_missing_re"], text, re.M | re.I):
                    errors.append(f"the sentinel is missing: f5/{n('00-sentinel')}/{n('SENTINEL.md')}, or the line "
                                  f"{C.CONVENE_LINES['declared_missing'][conv.lang]} in {n('CLOSURE.md')}")
                for h in all_branches(conv):
                    e = _early_data(conv, h)
                    if e.get("status") == "declared unresolved" and not (e.get("deciding_test") or "").strip():
                        errors.append(f"{h}: declared unresolved without the test that would decide it "
                                      f"({n('EARLY_CLOSURE.json')}): close-branch C {h} --reason … --deciding-test "
                                      f"TEXT adds it")
    return errors, info


def _g4_rules2(conv: Convening, h: str, folder: Path, nd: set[str], warnings: list[str]) -> list[str]:
    """The conditions of a G4 under the rules 2: the Correctness line (ENG-6), every briefed role delivered (ENG-7a),
    V2 by a role outside the f3 team on a proven result (ENG-7b); a warning without the sentinel (ENG-5)."""
    n = conv.name
    errors = []
    v = _correctness(conv, h)
    if v is None:
        errors.append(f"{arbiter_verdict(conv, h).relative_to(conv.folder)} without the line "
                      f"{C.CONVENE_LINES['correctness'][conv.lang]}")
    for p in _stray_correctness(conv, h):
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
    if sentinel_required(conv) and not sentinel_found(conv):
        warnings.append(f"no sentinel yet (f5/{n('00-sentinel')}/{n('SENTINEL.md')}): G5 will require it" if
                        level(conv) >= 2 else f"no sentinel yet (f5/{n('00-sentinel')}/{n('SENTINEL.md')}): a G5 "
                        f"under the rules 2 (--rules 2) would require it")
    return errors


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
    nd = {r.strip() for r in (ns.not_delivered or "").split(",") if r.strip()}
    errors, info = conditions(conv, phase, nd, lvl)
    if errors:
        print(T("gate_refused", phase=phase))
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    for w in info["warnings"]:
        print(T("gate_warning", text=w))
    if ns.verify:
        print(T("gate_holds", phase=phase))
        return
    g = {"phase": phase, "time": now(), "notes": ns.notes, "not_delivered": sorted(nd),
         "fingerprints": fingerprints(conv, phase, lvl)}
    if lvl >= 2:   # a gate of the rules 1 keeps the keys of 5.0, so that an engine of 5.x still reads it
        g["rules"] = lvl
        if phase == "f5":
            g["closed"] = info.get("closed", False)
        if info["warnings"]:
            g["warnings"] = info["warnings"]
    conv.write_json(gate_file(conv, phase), g, "gate")
    if phase == "f5" and not info.get("closed", False):
        print(T("gate_approved_not_closed", phase=phase, n=len(g["fingerprints"])))
    else:
        print(T("gate_approved", phase=phase, n=len(g["fingerprints"])))


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


def _branch_briefs(conv: Convening, h: str, owner_id: str | None, prof: dict, write: bool = True) -> dict[Path, str]:
    """The dossier and the briefs of the branch `h` (f3 and f4): written, or only returned (TASK path → text)."""
    c, n = conv.folder, conv.name
    base_in = base_inputs(conv)
    f3, f4 = c / "f3" / h, c / "f4" / h
    if write:
        f3.mkdir(parents=True, exist_ok=True)
        (f3 / f"{h}.md").write_text(hypothesis_card().replace("H-000", h), encoding="utf-8")
    owner = owner_id or prof["f3"][0]
    check = next((r for r in prof["f3"][1:] if r not in (C.ROLES["adversary"], C.ROLES["metrologist"], owner)), C.ROLES["logician"])
    adv, dbg, arb = C.ROLES["adversary"], C.ROLES["debugger"], C.ROLES["arbiter"]
    inv = C.ROLES["inverter"]
    sol = f3 / f"01-{owner}" / n("SOLUTION.md")
    checks = f4 / f"01-{adv}" / n("COUNTERCHECKS.md")
    defects = f4 / "02-debugger" / n("DEFECTS.md")
    auditor = inv if inv not in (owner, check, C.ROLES["metrologist"], adv) else dbg
    plan = [
        (f3 / f"01-{owner}", owner, "f3", "SOLUTION.md", mission("owner_solution", h=h), base_in, LIMIT_BRANCH),
        (f3 / f"02-{check}", check, "f3", "VERIFICATION.md", mission("proof", h=h), base_in + [sol], LIMIT_BRANCH),
        (f3 / f"03-{C.ROLES['metrologist']}", C.ROLES["metrologist"], "f3", "MEASUREMENT_PLAN.md",
         mission("measurement_plan", h=h), base_in + [sol], 30),
        (f3 / f"04-{adv}", adv, "f3", "ATTACK.md", mission("attack", h=h), base_in + [sol], 30),
        (f4 / f"00-{owner}", owner, "f4", "REVISION.md", mission("owner_revision", h=h),
         base_in + [f3, f4 / f"01-{adv}", f4 / "02-debugger"], LIMIT_BRANCH),
        (f4 / f"01-{adv}", adv, "f4", "COUNTERCHECKS.md", mission("counterchecks", h=h), base_in + [f3], LIMIT_BRANCH),
        (f4 / "02-debugger", dbg, "f4", "DEFECTS.md", mission("defects", h=h), base_in + [f3, f4 / f"01-{adv}"],
         LIMIT_F1),
    ]
    for i, role in enumerate([r for r in prof["f4"] if r not in (adv, dbg)], start=3):
        plan.append((f4 / f"{i:02d}-{role}", role, "f4", "MEASUREMENTS.md", mission("proof_contribution", h=h),
                     base_in + [f3, f4 / f"01-{adv}"], LIMIT_F1))
    plan += [
        (f4 / f"08-{auditor}", auditor, "f4", "HIDDEN_ASSUMPTIONS.md", mission("hidden_assumption_audit", h=h),
         base_in + [f3, checks, defects], 30),
        (f4 / f"09-{arb}", arb, "f4", "VERDICT.md", mission("verdict", h=h, dossier=f3 / f"{h}.md"),
         base_in + [f3, f4], 30),
    ]
    out = {}
    for folder, role, phase, output, text, inputs, minutes in plan:
        if write:
            brief(conv, folder, role, phase, output, text, inputs, minutes=minutes, h=h)
        out[folder / n("TASK.md")] = brief_text(conv, folder, role, phase, output, text, inputs, minutes=minutes, h=h)
    return out


def _sentinel_brief(conv: Convening, cat: dict) -> Path | None:
    """The brief of the sentinel (ENG-5), in a classic or a full with at least two funded branches: a role drawn
    with the seed among those in no lane of f1 and in no branch team."""
    c, m, n = conv.folder, conv.m, conv.name
    bs = branches(conv)
    if m["strategy"] not in ("classic", "full") or len(bs) < 2:
        return None
    used = set(m["f1"]) | {C.ROLES["arbiter"]}
    for h in bs:
        for f in (c / "f3" / h, c / "f4" / h):
            if f.is_dir():
                used |= {_role_of(x.name) for x in f.iterdir() if x.is_dir() and re.match(r"\d+-", x.name)}
    free = [r for r in cat["roles"] if r["id"] not in used]
    pool = sorted(r["id"] for r in free if r.get("type", "professional") == "professional") or sorted(
        r["id"] for r in free) or [C.ROLES["logician"]]
    role = random.Random(m["seed"]).choice(pool)
    inputs = ([conv.file("CONTRACT.md")] + gated_amendments(conv)
              + [c / "f2" / n("05-selection") / n("SELECTION.md"), c / "f3", c / "f4"])
    return brief(conv, c / "f5" / n("00-sentinel"), role, "f5", "SENTINEL.md", mission("sentinel"), inputs, minutes=20)


def _closure_brief(conv: Convening) -> Path:
    """The brief of the closure (ENG-9): every input the arbiter needs, and the output where G5 looks for it."""
    c, m, n = conv.folder, conv.m, conv.name
    try:
        prof = catalog()["profiles"].get(m["profile"], {"f3": [C.ROLES["logician"]]})
    except (Error, OSError, ValueError):
        prof = {"f3": [C.ROLES["logician"]]}
    inputs = [conv.file("CONTRACT.md")] + gated_amendments(conv) + [
        c / "f2" / n("05-selection") / n("SELECTION.md")]
    for h in all_branches(conv):
        if _early(conv, h):
            inputs.append(c / "f3" / h / n("EARLY_CLOSURE.json"))
        elif h in branches(conv):
            # The revision and the sentinel only where they were briefed (a convening of 5.0 has neither).
            revision = c / "f4" / h / f"00-{owner_of(conv, h, prof)}"
            inputs += [dossier_of(conv, h)] + ([revision / n("REVISION.md")] if (revision / n("TASK.md")).is_file()
                                               else []) + [arbiter_verdict(conv, h)]
    sentinel = c / "f5" / n("00-sentinel")
    if m["strategy"] in ("classic", "full") and len(branches(conv)) >= 2 and (sentinel / n("TASK.md")).is_file():
        inputs.append(sentinel / n("SENTINEL.md"))
    inputs += [c / "GATE_*.json", c / "f3", c / "f4"]
    closure = c / "f5" / n("CLOSURE.md")
    return brief(conv, c / "f5" / f"01-{C.ROLES['arbiter']}", C.ROLES["arbiter"], "f5", "CLOSURE.md",
                 mission("closure", closure_file=closure), inputs, minutes=30, output_path=closure)


def select(ns) -> None:
    conv = Convening.load(Path(ns.C).resolve())
    c, m, n = conv.folder, conv.m, conv.name
    if m["strategy"] in ("single", "fan-out"):
        raise Error("in the single and in the fan-out there are no hypotheses to select")
    if not valid(conv, "f2"):
        raise Error("the gate f2 is not approved or no longer valid")
    chosen = [norm_id(h) for h in ns.hypotheses]
    radical = norm_id(ns.radical) if ns.radical else None
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
    _sentinel_brief(conv, cat)
    _closure_brief(conv)
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
    if read_gate(conv, "f5") is not None:
        raise Error("the convening has its gate f5: no branch is funded after it")
    if funded(conv):
        raise Error(f"{h} is already funded")
    if _early(conv, h):
        raise Error(f"{h} is already closed")
    cat = catalog()
    prof = cat["profiles"][m["profile"]]
    owner_id = _role_id(ns.owner) if ns.owner else None
    if owner_id and owner_id not in {r["id"] for r in cat["roles"]}:
        raise Error(f"unknown role: {ns.owner}")
    _branch_briefs(conv, h, owner_id, prof)
    m["radical_funded"] = True
    conv.save()
    _sentinel_brief(conv, cat)
    _closure_brief(conv)
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
    if read_gate(conv, "f5") is not None:
        raise Error("the convening has its gate f5: no branch is closed after it")
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
                _closure_brief(conv)
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
        _closure_brief(conv)


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
        phases += [f"f3/{h}"] + ([f"f4/{h}"] if h in branches(conv) else [])
    if m["strategy"] not in ("single", "fan-out"):
        phases.append("f5")
    for phase in phases:
        if phase.startswith("f3/") and _early(conv, phase[3:]):
            print(T("status_early", phase=phase))
            continue
        if phase.startswith("f3/") and phase[3:] not in branches(conv):
            print(T("status_not_funded", phase=phase, h=phase[3:]))
            continue
        g = read_gate(conv, phase)
        if g is None:
            print(T("status_pending", phase=phase))
            continue
        if phase.startswith("f3/"):
            # A G3 of the rules 1 holds without its dossier once its G4 was approved under the rules 2 (ENG-1).
            g4 = read_gate(conv, "f4/" + phase[3:])
            ok = g3_holds(conv, phase[3:], max(lvl, gate_rules(g4) if g4 else 1))
        else:
            ok = valid(conv, phase)
        closed = g.get("closed")
        if closed is None and phase == "f5" and gate_rules(g) < 2:
            closed = outcome_of(conv) != "not closed"   # a G5 of the rules 1 records no «closed»
        if ok and phase == "f5" and closed is False:
            print(T("status_not_closed", phase=phase))
        else:
            print(T("status_approved" if ok else "status_invalid", phase=phase))


def build_parser(al: dict) -> argparse.ArgumentParser:
    p = A.parser(prog="convene", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
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
    A.arg(q, al, "--rules", type=int, choices=(1, 2),
          help="the rules of this gate, when higher than the convening's (gate_rules in the manifest)")
    q = add("seal")
    q.add_argument("C")
    q.add_argument("file", nargs="+")
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
    q = add("status")
    q.add_argument("C")
    return p


def main(argv=None) -> None:
    al = A.load(BASE)
    ns = build_parser(al).parse_args(sys.argv[1:] if argv is None else argv)
    commands = {"roles": roles, "prepare": prepare, "snapshot": snapshot, "gate": gate, "seal": seal,
                "select": select, "fund": fund, "close-branch": close_branch, "status": status}
    try:
        commands[ns.command](ns)
    except (C.Error, OSError, ValueError) as e:
        print(f"convene: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
