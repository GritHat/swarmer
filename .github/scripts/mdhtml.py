#!/usr/bin/env python3
"""A small Markdown-to-HTML converter for the documentation pages of GitHub Pages (agensi.py --api). Standard library.

It covers what the repository's documents use: ATX headings (with anchors), paragraphs, bullet and numbered lists
(nested by indentation, with continuation lines), fenced code blocks, inline code, pipe tables (with \\| inside cells),
links, bold and italic, horizontal rules and block quotes. Every other character is escaped: raw HTML in the source is
shown as text, and HTML comments are dropped.

    to_html(markdown, link=lambda url: url) -> (body_html, [(level, text, anchor), ...])
"""
from __future__ import annotations

import html
import re
from typing import Callable

LIST = re.compile(r"^( *)([-*+]|\d{1,9}[.)]) +(.*)$")
FENCE = re.compile(r"^( *)(`{3,}|~{3,})\s*([\w+-]*)")
HEADING = re.compile(r"^ {0,3}(#{1,6}) +(.*?)(?: +#+)? *$")
RULE = re.compile(r"^ {0,3}([-*_])(?: *\1){2,} *$")
TABLE_SEP = re.compile(r"^ *\|? *:?-{2,}:? *(\| *:?-{2,}:? *)*\|? *$")
SAFE_URL = re.compile(r"^(https?:|mailto:|#|\.{0,2}/|[\w.-]+(?:/|$|#|\.))", re.I)


def slug(text: str) -> str:
    s = re.sub(r"<[^>]+>", "", text)
    s = html.unescape(s).lower()
    s = re.sub(r"[^\w\- ]+", "", s, flags=re.UNICODE).strip()
    return re.sub(r"[\s]+", "-", s) or "section"


def plain(md: str) -> str:
    """The text of an inline Markdown fragment, without markup (for titles and anchors)."""
    s = re.sub(r"`([^`]*)`", r"\1", md)
    s = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", s)
    return re.sub(r"(\*\*|__|\*)", "", s).strip()


def inline(text: str, link: Callable[[str], str]) -> str:
    out = []
    pos = 0
    for m in re.finditer(r"(`+)(.+?)(?<!`)\1(?!`)", text):
        out.append(_text(text[pos:m.start()], link))
        out.append(f"<code>{html.escape(m.group(2).strip() if m.group(2).strip() else m.group(2))}</code>")
        pos = m.end()
    out.append(_text(text[pos:], link))
    return "".join(out)


def _text(t: str, link: Callable[[str], str]) -> str:
    t = html.escape(t, quote=False)

    def a(m: re.Match) -> str:
        label, url = m.group(1), html.unescape(m.group(2).strip().split(" ")[0])
        url = link(url)
        if not SAFE_URL.match(url):
            return label
        return f'<a href="{html.escape(url)}">{label}</a>'

    t = re.sub(r"!?\[([^\]]+)\]\(([^)\s]+(?: &quot;[^)]*&quot;)?)\)", a, t)
    t = re.sub(r"(?<![\"'=>/\w])(https?://[^\s<>()\"']+[^\s<>().,;:!?'\"])",
               lambda m: f'<a href="{html.escape(html.unescape(m.group(1)))}">{m.group(1)}</a>', t)
    t = re.sub(r"\*\*(?=\S)(.+?)(?<=\S)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![\w*])\*(?=[^\s*])(.+?)(?<=[^\s*])\*(?![\w*])", r"<em>\1</em>", t)
    return t


def cells(row: str) -> list[str]:
    row = row.strip()
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|") and not row.endswith("\\|"):
        row = row[:-1]
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", row)]


def to_html(md: str, link: Callable[[str], str] = lambda u: u) -> tuple[str, list[tuple[int, str, str]]]:
    md = re.sub(r"<!--.*?-->", "", md, flags=re.S)
    lines = md.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    toc: list[tuple[int, str, str]] = []
    used: dict[str, int] = {}
    para: list[str] = []
    stack: list[tuple[int, str]] = []   # open lists: (indent, tag)
    item_open = [False]

    def flush_para() -> None:
        if para:
            text = inline(" ".join(p.strip() for p in para), link)
            out.append(f"<p>{text}</p>" if not stack else text)
            para.clear()

    def close_lists(indent: int = -1) -> None:
        flush_para()
        while stack and stack[-1][0] > indent:
            out.append(f"</li></{stack.pop()[1]}>")

    i = 0
    while i < len(lines):
        line = lines[i]
        fm = FENCE.match(line)
        if fm:
            flush_para()
            pad, fence, lang = len(fm.group(1)), fm.group(2), fm.group(3)
            if stack and not pad:
                close_lists()
            body = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith(fence[0] * len(fence)):
                body.append(lines[i][pad:] if lines[i][:pad].strip() == "" else lines[i])
                i += 1
            cls = f' class="language-{html.escape(lang)}"' if lang else ""
            out.append(f"<pre><code{cls}>{html.escape(chr(10).join(body))}</code></pre>")
            i += 1
            continue
        if not line.strip():
            flush_para()
            # a blank line ends the lists unless the next line continues them
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if stack and (j >= len(lines) or not (LIST.match(lines[j]) or lines[j].startswith("  "))):
                close_lists()
            i += 1
            continue
        hm = HEADING.match(line)
        if hm:
            close_lists()
            level, text = len(hm.group(1)), hm.group(2)
            base = slug(inline(text, link))
            n = used.get(base, 0)
            used[base] = n + 1
            anchor = base if not n else f"{base}-{n}"
            toc.append((level, plain(text), anchor))
            out.append(f'<h{level} id="{anchor}"><a class="anchor" href="#{anchor}" aria-hidden="true">#</a>'
                       f'{inline(text, link)}</h{level}>')
            i += 1
            continue
        if RULE.match(line) and not para:
            close_lists()
            out.append("<hr>")
            i += 1
            continue
        if "|" in line and i + 1 < len(lines) and TABLE_SEP.match(lines[i + 1]) and lines[i + 1].count("-") >= 3:
            close_lists()
            head = cells(line)
            aligns = []
            for c in cells(lines[i + 1]):
                aligns.append("center" if c.startswith(":") and c.endswith(":") else
                              "right" if c.endswith(":") else "left" if c.startswith(":") else "")
            rows = []
            i += 2
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                rows.append(cells(lines[i]))
                i += 1

            def td(tag: str, k: int, c: str) -> str:
                al = aligns[k] if k < len(aligns) and aligns[k] else ""
                return f'<{tag}{f" style={chr(34)}text-align:{al}{chr(34)}" if al else ""}>{inline(c, link)}</{tag}>'

            out.append('<div class="table"><table><thead><tr>' + "".join(td("th", k, c) for k, c in enumerate(head))
                       + "</tr></thead><tbody>"
                       + "".join("<tr>" + "".join(td("td", k, c) for k, c in enumerate(r[:len(head)]))
                                 + "".join("<td></td>" for _ in range(len(head) - len(r))) + "</tr>" for r in rows)
                       + "</tbody></table></div>")
            continue
        if line.lstrip().startswith(">") and not stack:
            flush_para()
            quote = []
            while i < len(lines) and lines[i].lstrip().startswith(">"):
                quote.append(re.sub(r"^\s*> ?", "", lines[i]))
                i += 1
            body, sub = to_html("\n".join(quote), link)
            out.append(f"<blockquote>{body}</blockquote>")
            continue
        lm = LIST.match(line)
        if lm:
            flush_para()
            indent, marker, text = len(lm.group(1)), lm.group(2), lm.group(3)
            tag = "ul" if marker in "-*+" else "ol"
            if stack and indent > stack[-1][0]:
                out.append(f"<{tag}><li>")
                stack.append((indent, tag))
            else:
                while stack and stack[-1][0] > indent:
                    out.append(f"</li></{stack.pop()[1]}>")
                if stack and stack[-1][1] == tag:
                    out.append("</li><li>")
                else:
                    if stack:
                        out.append(f"</li></{stack.pop()[1]}>")
                    start = f' start="{int(marker[:-1])}"' if tag == "ol" and int(marker[:-1]) != 1 else ""
                    out.append(f"<{tag}{start}><li>")
                    stack.append((indent, tag))
            para.append(text)
            i += 1
            continue
        if stack and not line.startswith(" ") and not para:
            close_lists()
        para.append(line)
        i += 1
    close_lists()
    return "\n".join(out) + "\n", toc
