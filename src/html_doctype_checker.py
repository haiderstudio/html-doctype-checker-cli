#!/usr/bin/env python3
"""Check every HTML file starts with <!DOCTYPE html>.

Run: python3 src/html_doctype_checker.py page.html
     python3 src/html_doctype_checker.py site/
     python3 src/html_doctype_checker.py --stdin < page.html

Without a doctype the browser falls into quirks mode and lays the
page out by 1990s rules — the page looks wrong for no visible
reason. The fix is one line per file once it is found, but nothing
stops you shipping a page without one. This tool finds every HTML
file that is missing a doctype, or carries a wrong or legacy one,
and reports each one with the file and the line number. It exits 1
when any file fails, so it can fail a CI run. A page that starts
with <!DOCTYPE html> exits 0.

The doctype must be the first thing in the file, on line 1, and it
must be exactly <!DOCTYPE html> (any case, any spacing inside the
declaration). Blank lines or comments before it are reported: a
comment before the doctype put old versions of Internet Explorer
into quirks mode, and a doctype on line 2 is a sign the file was
edited by hand and the doctype drifted. Legacy doctypes — HTML
4.01, HTML 3.2, XHTML 1.0 and XHTML 1.1 — are named as legacy,
because they switch the browser into almost-standards mode rather
than full standards mode. A second doctype anywhere in the file is
reported too. Only the doctype is checked: titles, lang attributes,
and everything else in the page are other tools' jobs.

Report-only: it never edits a file, never fetches a URL, and only
reads the files and folders you point it at.
"""

import argparse
import json
import os
import re
import sys

VERSION = "1.0.0"

DOCTYPE_RE = re.compile(r"<!DOCTYPE\b[^<>]*>", re.IGNORECASE)
COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)

# Legacy doctypes, matched against the text inside the declaration.
# The first group is the name reported; the second is a variant word
# (Strict, Transitional, Frameset) looked for after it.
LEGACY_DOCTYPES = (
    ("HTML 4.01", ("Strict", "Transitional", "Frameset")),
    ("HTML 4.0", ("Strict", "Transitional", "Frameset")),
    ("HTML 3.2", ()),
    ("HTML 2.0", ()),
    ("XHTML 1.0", ("Strict", "Transitional", "Frameset")),
    ("XHTML 1.1", ()),
    ("XHTML Basic 1.0", ()),
    ("XHTML Basic 1.1", ()),
    ("XHTML Basic", ()),
)

BOM = "\ufeff"


def _line_of(text, index):
    """1-based line number of the character at index in text."""
    return text.count("\n", 0, index) + 1


def _comment_spans(text):
    """(start, end) spans of every HTML comment in text."""
    return [(m.start(), m.end()) for m in COMMENT_RE.finditer(text)]


def _inside_spans(index, spans):
    return any(start <= index < end for start, end in spans)


def _classify_doctype(raw):
    """Classify a doctype declaration.

    raw is the full declaration, e.g. "<!DOCTYPE html>".
    Returns ("ok", None) for the HTML5 doctype,
    ("legacy", "HTML 4.01 Transitional") for a known legacy one,
    ("wrong", raw) for anything else.
    """
    inner = raw[len("<!DOCTYPE"):-1].strip()
    squashed = re.sub(r"\s+", " ", inner)
    if squashed.lower() in ("html", 'html system "about:legacy-compat"'):
        return "ok", None
    lowered = squashed.lower()
    for name, variants in LEGACY_DOCTYPES:
        if name.lower() in lowered:
            label = name
            for variant in variants:
                if variant.lower() in lowered:
                    label = name + " " + variant
                    break
            return "legacy", label
    return "wrong", raw


def _describe_prefix(prefix):
    """What sits before the doctype: "blank", "comments", or "content"."""
    without_comments = COMMENT_RE.sub("", prefix)
    if without_comments.strip() == "":
        if COMMENT_RE.search(prefix):
            return "comments"
        return "blank"
    return "content"


def check_document(text, name):
    """Check one HTML document's text. Returns a list of problems.

    Each problem is a dict with file, line, kind, and message.
    kind is one of: missing, legacy, wrong, not-first, multiple.
    """
    problems = []
    if text.startswith(BOM):
        text = text[1:]
    spans = _comment_spans(text)
    matches = [
        m for m in DOCTYPE_RE.finditer(text)
        if not _inside_spans(m.start(), spans)
    ]
    if not matches:
        problems.append({
            "file": name,
            "line": 1,
            "kind": "missing",
            "message": "missing doctype — add <!DOCTYPE html> as the first line",
        })
        return problems

    first = matches[0]
    first_line = _line_of(text, first.start())
    kind, detail = _classify_doctype(first.group(0))
    if kind == "legacy":
        problems.append({
            "file": name,
            "line": first_line,
            "kind": "legacy",
            "message": "legacy doctype %s — replace it with <!DOCTYPE html>" % detail,
        })
    elif kind == "wrong":
        problems.append({
            "file": name,
            "line": first_line,
            "kind": "wrong",
            "message": "wrong doctype %s — replace it with <!DOCTYPE html>" % detail,
        })

    if first_line != 1:
        before = _describe_prefix(text[:first.start()])
        if before == "blank":
            why = "blank lines before it"
        elif before == "comments":
            why = "comment(s) before it"
        else:
            why = "other content before it"
        problems.append({
            "file": name,
            "line": first_line,
            "kind": "not-first",
            "message": "doctype is on line %d, not line 1 (%s)"
            % (first_line, why),
        })

    for extra in matches[1:]:
        problems.append({
            "file": name,
            "line": _line_of(text, extra.start()),
            "kind": "multiple",
            "message": "second doctype %s — a document has one doctype only"
            % extra.group(0),
        })
    return problems


def check_file(path):
    """Check one file on disk. Returns a list of problems."""
    try:
        raw = open(path, "rb").read()
    except OSError as exc:
        return [{
            "file": path,
            "line": 1,
            "kind": "unreadable",
            "message": "could not be read: %s" % exc.strerror,
        }]
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return [{
            "file": path,
            "line": 1,
            "kind": "unreadable",
            "message": "could not be read as UTF-8 — save the file as UTF-8 and try again",
        }]
    return check_document(text, path)


def _is_html_file(path):
    lowered = path.lower()
    return lowered.endswith(".html") or lowered.endswith(".htm")


def collect_files(paths, recursive=True, exclude=None):
    """Expand paths into a sorted list of HTML files to check.

    A path given directly is always checked, whatever its name.
    A folder is walked for .html and .htm files. .git folders are
    never walked, and directory links are never followed.
    """
    exclude = exclude or []
    found = []
    for path in paths:
        if os.path.isfile(path):
            found.append(path)
        elif os.path.isdir(path):
            if recursive:
                for root, dirs, files in os.walk(path, followlinks=False):
                    dirs[:] = sorted(
                        d for d in dirs
                        if d != ".git"
                        and not any(re.search(p, d) for p in exclude)
                    )
                    for name in sorted(files):
                        full = os.path.join(root, name)
                        if _is_html_file(full):
                            if any(re.search(p, full) for p in exclude):
                                continue
                            found.append(full)
            else:
                for name in sorted(os.listdir(path)):
                    full = os.path.join(path, name)
                    if os.path.isfile(full) and _is_html_file(full):
                        if any(re.search(p, full) for p in exclude):
                            continue
                        found.append(full)
        else:
            raise FileNotFoundError(path)
    return found


def _print_text(problems, checked):
    bad_files = sorted({p["file"] for p in problems})
    for problem in problems:
        print("FAIL %s: %s (line %d)"
              % (problem["file"], problem["message"], problem["line"]))
    if problems:
        print("Checked %d file(s), %d problem(s) in %d file(s)."
              % (checked, len(problems), len(bad_files)))
    else:
        print("OK — %d file(s) checked, every file starts with "
              "<!DOCTYPE html>." % checked)


def _print_json(problems, checked):
    print(json.dumps({
        "files_checked": checked,
        "problems": problems,
        "ok": not problems,
    }, indent=2, ensure_ascii=False))


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="html_doctype_checker",
        description="Check every HTML file starts with <!DOCTYPE html>.",
    )
    parser.add_argument("paths", nargs="*", help="HTML files or folders to check")
    parser.add_argument("--json", action="store_true",
                        help="print the result as JSON")
    parser.add_argument("--stdin", action="store_true",
                        help="check one HTML document read from standard input")
    parser.add_argument("--no-recursive", action="store_true",
                        help="do not walk subfolders")
    parser.add_argument("--exclude", action="append", default=[],
                        metavar="PATTERN",
                        help="skip files or folders whose path matches "
                             "this regular expression (repeatable)")
    parser.add_argument("--version", action="version",
                        version="html_doctype_checker " + VERSION)
    args = parser.parse_args(argv)

    if args.stdin and args.paths:
        parser.error("--stdin takes no paths")
    if not args.stdin and not args.paths:
        parser.error("give at least one file or folder, or --stdin")

    if args.stdin:
        text = sys.stdin.read()
        problems = check_document(text, "<stdin>")
        if args.json:
            _print_json(problems, 1)
        else:
            _print_text(problems, 1)
        return 0 if not problems else 1

    try:
        files = collect_files(
            args.paths,
            recursive=not args.no_recursive,
            exclude=args.exclude,
        )
    except FileNotFoundError as exc:
        print("error: no such file or folder: %s" % exc, file=sys.stderr)
        return 2
    if not files:
        print("error: no HTML files found", file=sys.stderr)
        return 2

    problems = []
    for path in files:
        problems.extend(check_file(path))

    if args.json:
        _print_json(problems, len(files))
    else:
        _print_text(problems, len(files))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
