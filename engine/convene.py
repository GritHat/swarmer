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
  gate      C PHASE --notes TEXT [--not-delivered ROLE,…] [--verify]
            PHASE = f0, f1, f2, f3/H-001, f4/H-001, f5
  seal      C FILE…               time and sha256 in SEALS.jsonl
  select    C H-001 [H-002 H-003] [--radical H-00x] [--owner ID]
  close-branch C H-00x --reason TEXT
  status    C
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import random
import re
import secrets
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
          *, canary: str | None = None, minutes: int = LIMIT_F1, h: str | None = None) -> Path:
    """TASK.md of an agent, in the language of the installation; the files keep the names of the dialect."""
    folder.mkdir(parents=True, exist_ok=True)
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
        f"- **{T('output')}:** `{folder / conv.name(output)}`, {T('output_tail')}",
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
    out = folder / conv.name("TASK.md")
    out.write_text("\n".join(lines), encoding="utf-8")
    BRIEFED.append(role)
    return out


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
         "seed": seed, "created": now(), "f1": {}, "selected": [], "radical": None}
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


def phase_folders(conv: Convening, phase: str) -> list[Path]:
    c, m = conv.folder, conv.m
    if phase == "f0":
        return [c / "f0"]
    if phase == "f1":
        return [Path(v["folder"]) for v in m["f1"].values()] + ([c / "f1c"] if m["strategy"] == "full" else [])
    return [c / phase]


def fingerprints(conv: Convening, phase: str) -> dict[str, str]:
    c = conv.folder
    files = [conv.file("CONTRACT.md")] if phase == "f0" else []
    folder = c
    for folder in phase_folders(conv, phase):
        files += sorted(p for p in folder.rglob("*.md") if p.is_file())
    if phase.startswith("f3/") or phase.startswith("f4/"):
        files += sorted(p for p in folder.rglob("*.json") if p.is_file() and not p.name.startswith("GATE_"))
    return {str(p): sha(p) for p in files}


def gate_file(conv: Convening, phase: str) -> Path:
    return conv.folder / f"GATE_{phase.replace('/', '_')}.json"


def valid(conv: Convening, phase: str) -> bool:
    p = gate_file(conv, phase)
    if not p.exists():
        return False
    g = conv.read_json(p, "gate")
    return g.get("fingerprints") == fingerprints(conv, phase)


def _section(text: str, field: str):
    for title in (field, C.CONVENE_LINES["contract_fields"][field]):
        s = re.search(rf"^## {re.escape(title)}\n(.*?)(?=^## |\Z)", text, re.S | re.M)
        if s:
            return s
    return None


def _early(conv: Convening, h: str) -> bool:
    return (conv.folder / "f3" / h / conv.name("EARLY_CLOSURE.json")).exists()


def conditions(conv: Convening, phase: str, not_delivered: set[str]) -> list[str]:
    c, m, n = conv.folder, conv.m, conv.name
    errors = []
    before = {"f1": "f0", "f2": "f1", "f5": "f2"}.get(phase)
    if phase.startswith("f3/"):
        before = "f2"
    elif phase.startswith("f4/"):
        before = "f3/" + phase[3:]
    if m["strategy"] in ("single", "fan-out") and phase == "f5":
        before = "f1"
    if before and not valid(conv, before):
        errors.append(f"the gate {before} is not approved or no longer valid")
    if phase == "f0":
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
        if h not in m["selected"] + ([m["radical"]] if m["radical"] else []):
            errors.append(f"{h} is not selected")
        if _early(conv, h):
            errors.append(f"the branch {h} is closed early: no G3 nor G4")
        folder = c / phase
        if phase.startswith("f3/"):
            for name in ("SOLUTION.md", "VERIFICATION.md", "MEASUREMENT_PLAN.md", "ATTACK.md", "PREDICTIONS.md"):
                if not any(full(p) for p in folder.rglob(n(name))):
                    errors.append(f"{phase}: {n(name)} is missing")
            for p in folder.rglob(n("PREDICTIONS.md")):
                if not re.search(C.CONVENE_LINES["decides_re"], p.read_text(encoding="utf-8"), re.M):
                    errors.append(f"{p.relative_to(c)}: the line {C.CONVENE_LINES['decides'][conv.lang]} is missing")
        else:
            for name in ("COUNTERCHECKS.md", "VERDICT.md"):
                if not any(full(p) for p in folder.rglob(n(name))):
                    errors.append(f"{phase}: {n(name)} is missing")
            sig = seals(conv)
            checks = list(folder.rglob(n("COUNTERCHECKS.md")))
            for p in folder.rglob(n("PREDICTIONS.md")):
                s = sig.get(str(p))
                if not s:
                    errors.append(f"{p.relative_to(c)} born in f4 is not sealed")
                elif sha(p) != s["sha256"] and not _tail_only(p, s):
                    errors.append(f"{p.relative_to(c)} changed after the seal, not only at the end")
                elif any(q.stat().st_mtime < _iso(s["time"]) for q in checks):
                    errors.append(f"{p.relative_to(c)} is sealed after the counterchecks")
            dossier = c / "f3" / h / f"{h}.md"
            if dossier.exists():
                empty = [r for r in dossier.read_text(encoding="utf-8").splitlines() if re.match(r"^- [^|]*:\s*$", r)]
                if empty:
                    errors.append(f"the dossier {h} has {len(empty)} empty fields (one writes «missing»)")
            else:
                errors.append(f"the dossier {dossier.relative_to(c)} is missing")
    elif phase == "f5":
        closure = c / "f5" / n("CLOSURE.md")
        if not full(closure):
            errors.append(f"f5/{n('CLOSURE.md')} of the arbiter is missing")
        elif not re.search(C.CONVENE_LINES["outcome_re"], closure.read_text(encoding="utf-8"), re.M):
            errors.append(f"{n('CLOSURE.md')} without the line {C.CONVENE_LINES['outcome'][conv.lang]}")
        if m["strategy"] not in ("single", "fan-out"):
            branches = m["selected"] + ([m["radical"]] if m["radical"] else [])
            proven = [h for h in branches if valid(conv, f"f4/{h}")]
            open_ = [h for h in branches if h not in proven and not _early(conv, h)]
            if open_:
                errors.append(f"branches without a valid G4 nor an early closure: {', '.join(open_)}")
            if branches and not proven:
                errors.append("no H# proven: the cycle does not close with a G5")
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
    if not re.fullmatch(r"f[0125]|f[34]/H-\d{3}", phase):
        raise Error(f"unknown phase: {phase}")
    nd = {r.strip() for r in (ns.not_delivered or "").split(",") if r.strip()}
    errors = conditions(conv, phase, nd)
    if errors:
        print(T("gate_refused", phase=phase))
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    if ns.verify:
        print(T("gate_holds", phase=phase))
        return
    g = {"phase": phase, "time": now(), "notes": ns.notes, "not_delivered": sorted(nd),
         "fingerprints": fingerprints(conv, phase)}
    conv.write_json(gate_file(conv, phase), g, "gate")
    print(T("gate_approved", phase=phase, n=len(g["fingerprints"])))


def hypothesis_card() -> str:
    for l in dict.fromkeys((language(), "en", "it")):
        p = BASE / S.localized_name(BASE, "HYPOTHESIS_CARD.md", l)
        if p.is_file():
            return p.read_text(encoding="utf-8")
    raise Error(f"the hypothesis card is missing in {BASE}: bash swarmer/swarmer.sh regenerate")


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
    template = hypothesis_card()
    base_in = [conv.file("CONTRACT.md"), c / "f2" / n("01-translation") / n("CARDS.md"),
               c / "f2" / n("03-triage") / n("TRIAGE.md"), c / "f2" / n("04-tournament") / n("TOURNAMENT.md")]
    for h in chosen + ([radical] if radical else []):
        f3, f4 = c / "f3" / h, c / "f4" / h
        f3.mkdir(parents=True, exist_ok=True)
        (f3 / f"{h}.md").write_text(template.replace("H-000", h), encoding="utf-8")
        owner = owner_id or prof["f3"][0]
        check = next((r for r in prof["f3"][1:] if r not in (C.ROLES["adversary"], C.ROLES["metrologist"], owner)), C.ROLES["logician"])
        sol = f3 / f"01-{owner}" / n("SOLUTION.md")
        brief(conv, f3 / f"01-{owner}", owner, "f3", "SOLUTION.md", mission("owner_solution", h=h), base_in,
              minutes=LIMIT_BRANCH, h=h)
        brief(conv, f3 / f"02-{check}", check, "f3", "VERIFICATION.md", mission("proof", h=h), base_in + [sol],
              minutes=LIMIT_BRANCH, h=h)
        brief(conv, f3 / f"03-{C.ROLES['metrologist']}", C.ROLES["metrologist"], "f3", "MEASUREMENT_PLAN.md", mission("measurement_plan", h=h),
              base_in + [sol], minutes=30, h=h)
        brief(conv, f3 / f"04-{C.ROLES['adversary']}", C.ROLES["adversary"], "f3", "ATTACK.md", mission("attack", h=h), base_in + [sol],
              minutes=30, h=h)
        brief(conv, f4 / f"01-{C.ROLES['adversary']}", C.ROLES["adversary"], "f4", "COUNTERCHECKS.md", mission("counterchecks", h=h),
              base_in + [f3], minutes=LIMIT_BRANCH, h=h)
        brief(conv, f4 / "02-debugger", C.ROLES["debugger"], "f4", "DEFECTS.md", mission("defects", h=h),
              base_in + [f3, f4 / f"01-{C.ROLES['adversary']}"], h=h)
        for i, role in enumerate([r for r in prof["f4"] if r not in (C.ROLES["adversary"], C.ROLES["debugger"])], start=3):
            brief(conv, f4 / f"{i:02d}-{role}", role, "f4", "MEASUREMENTS.md", mission("proof_contribution", h=h),
                  base_in + [f3, f4 / f"01-{C.ROLES['adversary']}"], h=h)
        brief(conv, f4 / f"09-{C.ROLES['arbiter']}", C.ROLES["arbiter"], "f4", "VERDICT.md", mission("verdict", h=h, dossier=f3 / f"{h}.md"),
              base_in + [f3, f4], minutes=30, h=h)
    m["selected"], m["radical"] = chosen, radical
    conv.save()
    brief(conv, c / "f5" / f"01-{C.ROLES['arbiter']}", C.ROLES["arbiter"], "f5", "CLOSURE.md",
          mission("closure", closure_file=c / "f5" / n("CLOSURE.md")), [conv.file("CONTRACT.md"), c / "f3", c / "f4"],
          minutes=30)
    print(T("branches_open", ids=", ".join(chosen + ([radical] if radical else []))))


def close_branch(ns) -> None:
    conv = Convening.load(Path(ns.C).resolve())
    m = conv.m
    h = norm_id(ns.hypothesis)
    if h not in m["selected"] + ([m["radical"]] if m["radical"] else []):
        raise Error(f"{h} is not selected")
    if valid(conv, f"f3/{h}"):
        raise Error(f"{h} already has a G3: the early closure holds only before")
    p = conv.folder / "f3" / h / conv.name("EARLY_CLOSURE.json")
    if p.exists():
        raise Error(f"{h} is already closed")
    conv.write_json(p, {"time": now(), "hypothesis": h, "reason": ns.reason, "status": "declared unresolved"},
                    "early_closure")
    print(T("branch_closed", h=h))


def status(ns) -> None:
    conv = Convening.load(Path(ns.C).resolve())
    m = conv.m
    print(T("status_head", name=m["name"], strategy=shown("strategy", m["strategy"]),
            profile=shown("profile", m["profile"])))
    phases = ["f0", "f1"] + ([] if m["strategy"] in ("single", "fan-out") else ["f2"])
    for h in m["selected"] + ([m["radical"]] if m["radical"] else []):
        phases += [f"f3/{h}", f"f4/{h}"]
    if m["strategy"] not in ("single", "fan-out"):
        phases.append("f5")
    for phase in phases:
        if phase.startswith("f3/") and _early(conv, phase[3:]):
            print(T("status_early", phase=phase))
            continue
        if not gate_file(conv, phase).exists():
            print(T("status_pending", phase=phase))
        else:
            print(T("status_approved" if valid(conv, phase) else "status_invalid", phase=phase))


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
    q = add("seal")
    q.add_argument("C")
    q.add_argument("file", nargs="+")
    q = add("select")
    q.add_argument("C")
    q.add_argument("hypotheses", nargs="+")
    A.arg(q, al, "--radical")
    A.arg(q, al, "--owner", metavar="ID")
    q = add("close-branch")
    q.add_argument("C")
    q.add_argument("hypothesis")
    A.arg(q, al, "--reason", required=True)
    q = add("status")
    q.add_argument("C")
    return p


def main(argv=None) -> None:
    al = A.load(BASE)
    ns = build_parser(al).parse_args(sys.argv[1:] if argv is None else argv)
    commands = {"roles": roles, "prepare": prepare, "snapshot": snapshot, "gate": gate, "seal": seal,
                "select": select, "close-branch": close_branch, "status": status}
    try:
        commands[ns.command](ns)
    except (C.Error, OSError, ValueError) as e:
        print(f"convene: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
