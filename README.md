# html-doctype-checker-cli

Check every HTML file starts with `<!DOCTYPE html>`, fail CI when one does not.

[![CI](https://github.com/haiderstudio/html-doctype-checker-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/haiderstudio/html-doctype-checker-cli/actions/workflows/ci.yml) [![Licence: MIT](https://img.shields.io/badge/Licence-MIT-yellow.svg)](LICENSE)

## What it does

`html_doctype_checker` reads HTML files and finds every file that is
missing a doctype, or carries a wrong or legacy one, and reports each
one with the file and the line number. It exits 1 when any file
fails, so it can fail a CI run. A page that starts with
`<!DOCTYPE html>` exits 0.

- Without a doctype the browser falls into quirks mode and lays the
  page out by 1990s rules — the page looks wrong for no visible
  reason. The fix is one line per file once it is found, but nothing
  stops you shipping a page without one. This catches it before the
  page ships.
- The doctype must be the first thing in the file, on line 1. Blank
  lines or comments before it are reported: a comment before the
  doctype put old versions of Internet Explorer into quirks mode,
  and a doctype on line 2 is a sign the file was edited by hand and
  the doctype drifted. A doctype after other content — an `<html>`
  tag, say — is reported the same way.
- Legacy doctypes are named, not just flagged: HTML 4.01 Strict,
  Transitional, and Frameset, HTML 4.0, HTML 3.2, HTML 2.0, XHTML
  1.0 Strict, Transitional, and Frameset, XHTML 1.1, and XHTML
  Basic. They switch the browser into almost-standards mode rather
  than full standards mode, so they are a fail, not a warning.
- The match is case-insensitive and spacing-insensitive, so
  `<!doctype HTML>` and `<!DOCTYPE   html>` both pass, and a
  UTF-8 byte-order mark at the start of the file is fine. The
  standard `<!DOCTYPE html SYSTEM "about:legacy-compat">` form
  passes too — it is a real HTML5 doctype.
- A second doctype anywhere in the file is reported: a document has
  one doctype only. A doctype written inside an HTML comment does
  not count — it is not a doctype, it is a comment.
- A file given directly on the command line is always checked,
  whatever its name. A folder is walked for `.html` and `.htm`
  files, recursively by default (`--no-recursive` stops at the top
  level). `.git` folders are never walked, and directory links are
  never followed.
- `--json` prints the result as JSON, and `--stdin` checks one HTML
  document read from standard input. A file that cannot be read as
  UTF-8 is reported as a problem, not skipped silently.
- Report-only: it never edits a file, never fetches a URL, and only
  reads the files and folders you point it at.

## What it does NOT do

- It checks the doctype only. It does not check anything else in the
  page: titles are [html-title-checker-cli](https://github.com/haiderstudio/html-title-checker-cli)'s
  job, `lang` attributes are html-lang-checker-cli's job, and image
  `alt` text is image-alt-checker-cli's job. It does not check
  whether the HTML is valid, whether links work, or whether a
  stylesheet exists — each of those is a different tool's job.
- It does not fix anything. When it reports a missing doctype, you
  add `<!DOCTYPE html>` as the first line yourself.
- It does not judge the page's content. A page with the right
  doctype and broken markup still passes — that is the markup
  checker's job, not this one.

## Who it is for

Anyone who ships HTML pages — a personal site, a client site, a
documentation folder — and wants a gate that stops a page without
a doctype reaching production. One missing doctype is one page
rendered in quirks mode, and it is a one-line fix once found.

## Install

No install step and no dependencies — Python 3.8 or newer, standard
library only. Clone the repo and run it:

```sh
git clone https://github.com/haiderstudio/html-doctype-checker-cli.git
cd html-doctype-checker-cli
```

## Usage

Check one file:

```sh
python3 src/html_doctype_checker.py examples/good.html
```

```
OK — 1 file(s) checked, every file starts with <!DOCTYPE html>.
```

Check a file with no doctype:

```sh
python3 src/html_doctype_checker.py examples/bad.html
```

```
FAIL examples/bad.html: missing doctype — add <!DOCTYPE html> as the first line (line 1)
Checked 1 file(s), 1 problem(s) in 1 file(s).
```

Check a whole folder (exit code 1, because three of the four example files fail):

```sh
python3 src/html_doctype_checker.py examples/
```

```
FAIL examples/bad.html: missing doctype — add <!DOCTYPE html> as the first line (line 1)
FAIL examples/edge.html: doctype is on line 4, not line 1 (comment(s) before it) (line 4)
FAIL examples/legacy.html: legacy doctype HTML 4.01 Transitional — replace it with <!DOCTYPE html> (line 1)
Checked 4 file(s), 3 problem(s) in 3 file(s).
```

Check one document from standard input:

```sh
python3 src/html_doctype_checker.py --stdin < examples/good.html
```

```
OK — 1 file(s) checked, every file starts with <!DOCTYPE html>.
```

Machine-readable output for CI:

```sh
python3 src/html_doctype_checker.py --json examples/bad.html
```

```json
{
  "files_checked": 1,
  "problems": [
    {
      "file": "examples/bad.html",
      "line": 1,
      "kind": "missing",
      "message": "missing doctype — add <!DOCTYPE html> as the first line"
    }
  ],
  "ok": false
}
```

Exit codes: 0 means every file passed, 1 means at least one file
failed, 2 means a usage error (no paths given, a path that does not
exist, or no HTML files found).

## Examples

### A legacy doctype, named

`examples/legacy.html` carries an HTML 4.01 Transitional doctype:

```sh
python3 src/html_doctype_checker.py examples/legacy.html
```

```
FAIL examples/legacy.html: legacy doctype HTML 4.01 Transitional — replace it with <!DOCTYPE html> (line 1)
Checked 1 file(s), 1 problem(s) in 1 file(s).
```

### The right doctype, in the wrong place

`examples/edge.html` has the right doctype, but blank lines and a
comment come first, so it sits on line 4:

```sh
python3 src/html_doctype_checker.py examples/edge.html
```

```
FAIL examples/edge.html: doctype is on line 4, not line 1 (comment(s) before it) (line 4)
Checked 1 file(s), 1 problem(s) in 1 file(s).
```

### A folder, with one file excluded

```sh
python3 src/html_doctype_checker.py --exclude legacy examples/
```

```
FAIL examples/bad.html: missing doctype — add <!DOCTYPE html> as the first line (line 1)
FAIL examples/edge.html: doctype is on line 4, not line 1 (comment(s) before it) (line 4)
Checked 3 file(s), 2 problem(s) in 2 file(s).
```

The full example run, with the output it produces, is in
[`examples/sample-output.md`](examples/sample-output.md) — run it
yourself with `sh examples/run-example.sh`.

## How it is tested

```sh
python3 tests/test_html_doctype_checker.py
```

The suite is standard-library `unittest` only — no pytest, no
third-party imports. It covers the correct doctype and its case and
spacing variants, missing doctypes, legacy doctypes (HTML 4.01
Strict, Transitional, and Frameset, HTML 4.0, HTML 3.2, XHTML 1.0
and 1.1), wrong doctypes, doctypes on line 2 or later, blank lines
and comments before the doctype, a byte-order mark, multiple
doctypes, a doctype inside a comment, folder walking (`.htm`
included, `.git` skipped, `--no-recursive`, `--exclude`), `--json`
and `--stdin` output, exit codes 0, 1, and 2, and the repo hygiene
rules (no placeholder text, no absolute paths, no secrets, standard
library only, `.env` first in `.gitignore`, CI runs this test file).
Every CLI run in the tests uses absolute paths, and the suite passes
from the repo root, from `/tmp`, and under a fake home folder.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Small, focused improvements
are welcome — open an issue first for anything larger than a typo.

## Licence

MIT — see [LICENSE](LICENSE).

## Original work

This tool was written from scratch for this repo. The doctype rules
it checks come from the HTML standard's definition of the doctype
and from the W3C's published legacy doctype declarations, named in
the messages the tool prints. No code was copied from another tool.
