"""The ONE hunk-sha definition of crossroads (CROSSROADS_FORMATS.md §3), standard library only.

Sealed reference: crossroads-r2 slice 1, sha256 a3f17dfea781346a67d0a5bf27af0711c5dabeb8c9e14c9b9a55e7a26b9fa71b.
This file is that reference with amendment F (CROSSROADS_FORMATS.md §10) applied:
- F-1: the pin `-c diff.orderFile=` is passed to `diff-tree` only (the sealed line, byte for byte); git 2.53 refuses it
  in porcelain `diff`, `log`, `show` and `fast-import`. The realize line is `diff --cached <FLAGS> -O/dev/null`.
- F-2: raw records and patch sections are paired by consuming the sections of each record (a typechange `T` has two);
  a typechange or a gitlink (160000) yields one entry (path, "UNSUPPORTED", "UNSUPPORTED", 0) and no hunk sha.
Every hunk sha, header, path and ordinal of the other vectors is unchanged.

hunks(repo, commit) -> [(path, header 'a,b c,d', hunk_sha256 | BINARY | UNSUPPORTED, ordinal)];
staged(repo, *pathspec) does the same for the index against HEAD.
"""
import hashlib, os, re, subprocess

PIN_C = ["-c", "core.quotePath=false", "-c", "core.attributesFile=/dev/null", "-c", "diff.algorithm=myers",
         "-c", "diff.indentHeuristic=false", "-c", "diff.interHunkContext=0", "-c", "diff.suppressBlankEmpty=false",
         "-c", "diff.noprefix=false", "-c", "diff.mnemonicPrefix=false", "-c", "diff.relative=false",
         "-c", "diff.external=", "-c", "diff.orderFile=", "-c", "color.ui=never"]
# F-1: every command but diff-tree runs without the empty order file pin
PIN_C_OTHER = [x for i, x in enumerate(PIN_C)
               if x != "diff.orderFile=" and not (x == "-c" and i + 1 < len(PIN_C) and PIN_C[i + 1] == "diff.orderFile=")]
PIN_F = ["-p", "--raw", "-z", "-U0", "--no-renames", "--no-ext-diff", "--no-textconv", "--diff-algorithm=myers",
         "--no-indent-heuristic", "--inter-hunk-context=0", "--src-prefix=a/", "--dst-prefix=b/", "--ignore-submodules=none",
         "--no-color"]
REALIZE_TAIL = ["-O/dev/null"]   # F-1: the empty order of the realize line
ENV = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null", "LC_ALL": "C", "GIT_ATTR_NOSYSTEM": "1"}
MARKER = b"\\ No newline at end of file"
HDR = re.compile(rb"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
UNSUPPORTED = "UNSUPPORTED"


def _git(repo, *a):
    pins = PIN_C if a[:1] == ("diff-tree",) else PIN_C_OTHER
    return subprocess.run(["git", *pins, "-C", repo, *a], capture_output=True, check=True,
                          env={**os.environ, **ENV}).stdout


def records(raw):
    """(raw records [(old mode, new mode, status letter, path bytes)], patch sections [bytes], pairing) of a
    `-p --raw -z` output. pairing[i] = the sections of record i (F-2: two for a typechange that has both)."""
    head, sep, patch = raw.partition(b"\0\0diff --git ") if b"\0\0diff --git " in raw else (raw, b"", b"")
    f = head.split(b"\0")
    recs, i = [], 0
    while i < len(f):
        if f[i].startswith(b":"):
            m = f[i][1:].split(b" ")
            recs.append((m[0], m[1], m[4][:1], f[i + 1]))
            i += 2
        else:
            i += 1
    secs = [] if not sep else [b"diff --git " + s for s in patch.split(b"\ndiff --git ")]
    pairing, j = [], 0
    for n, (om, nm, st, path) in enumerate(recs):
        take = 2 if st == b"T" and len(secs) - j > len(recs) - n else 1
        pairing.append(secs[j:j + take])
        j += take
    if j != len(secs):
        raise RuntimeError("raw/patch mismatch %d %d" % (len(recs), len(secs)))
    return recs, secs, pairing


def parse(raw):
    recs, _secs, pairing = records(raw)
    out = []
    for (om, nm, st, path), ss in zip(recs, pairing):
        p = path.decode("utf-8", "surrogateescape")
        if st == b"T" or b"160000" in (om, nm):        # F-2: typechange or submodule: UNSUPPORTED, no hunk
            out.append((p, UNSUPPORTED, UNSUPPORTED, 0))
            continue
        s = ss[0] if ss else b""
        L = s.split(b"\n"); cur = None; hs = []
        for l in L:
            m = HDR.match(l)
            if m:
                cur = [b"%s,%s %s,%s" % (m[1], m[2] or b"1", m[3], m[4] or b"1"), []]; hs.append(cur)
            elif l.startswith(b"Binary files ") and cur is None:
                hs.append([b"BINARY", None])
            elif cur is not None and l[:1] in (b"+", b"-"): cur[1].append(l)
            elif cur is not None and l[:1] == b"\\": cur[1].append(MARKER)
        for k, (hdr, ls) in enumerate(hs):
            if ls is None: out.append((p, "BINARY", "BINARY", k)); continue
            b = path + b"\n" + b"".join(x + b"\n" for x in ls)
            out.append((p, hdr.decode(), hashlib.sha256(b).hexdigest(), k))
    return out


def hunks(repo, commit):
    return parse(_git(repo, "diff-tree", "-r", "--root", "--no-commit-id", *PIN_F, commit))


def staged(repo, *pathspec):
    return parse(_git(repo, "diff", "--cached", *PIN_F, *REALIZE_TAIL, *(("--",) + pathspec if pathspec else ())))
