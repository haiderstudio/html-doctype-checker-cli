#!/usr/bin/env python3
"""Tests for html_doctype_checker — stdlib unittest only."""

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import html_doctype_checker as checker

REPO = Path(__file__).resolve().parent.parent
GOOD = "<!DOCTYPE html>\n<html><head><title>t</title></head><body></body></html>\n"


def run_cli(argv, stdin_text=None):
    """Run main(argv), capture stdout/stderr, return (code, out, err)."""
    out = io.StringIO()
    err = io.StringIO()
    old_stdin = sys.stdin
    if stdin_text is not None:
        sys.stdin = io.StringIO(stdin_text)
    try:
        with redirect_stdout(out), redirect_stderr(err):
            try:
                code = checker.main(argv)
            except SystemExit as exc:
                code = exc.code
    finally:
        sys.stdin = old_stdin
    return code, out.getvalue(), err.getvalue()


def write(tmp, name, text, encoding="utf-8"):
    path = Path(tmp) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(text, bytes):
        path.write_bytes(text)
    else:
        path.write_text(text, encoding=encoding)
    return str(path)


def kinds(problems):
    return [p["kind"] for p in problems]


class TestClassifyDoctype(unittest.TestCase):
    def test_html5_lowercase_ok(self):
        self.assertEqual(checker._classify_doctype("<!DOCTYPE html>"), ("ok", None))

    def test_html5_uppercase_ok(self):
        self.assertEqual(checker._classify_doctype("<!DOCTYPE HTML>"), ("ok", None))

    def test_html5_mixed_case_ok(self):
        self.assertEqual(checker._classify_doctype("<!DoCtYpE hTmL>"), ("ok", None))

    def test_html5_extra_spacing_ok(self):
        self.assertEqual(checker._classify_doctype("<!DOCTYPE    html   >"), ("ok", None))

    def test_html5_newline_inside_ok(self):
        self.assertEqual(checker._classify_doctype("<!DOCTYPE\nhtml>"), ("ok", None))

    def test_legacy_compat_system_ok(self):
        kind, _ = checker._classify_doctype(
            '<!DOCTYPE html SYSTEM "about:legacy-compat">')
        self.assertEqual(kind, "ok")

    def test_html401_strict_legacy(self):
        kind, label = checker._classify_doctype(
            '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" '
            '"http://www.w3.org/TR/html4/strict.dtd">')
        self.assertEqual(kind, "legacy")
        self.assertEqual(label, "HTML 4.01 Strict")

    def test_html401_transitional_legacy(self):
        kind, label = checker._classify_doctype(
            '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" '
            '"http://www.w3.org/TR/html4/loose.dtd">')
        self.assertEqual(kind, "legacy")
        self.assertEqual(label, "HTML 4.01 Transitional")

    def test_html401_frameset_legacy(self):
        kind, label = checker._classify_doctype(
            '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Frameset//EN" '
            '"http://www.w3.org/TR/html4/frameset.dtd">')
        self.assertEqual(kind, "legacy")
        self.assertEqual(label, "HTML 4.01 Frameset")

    def test_html401_no_variant_legacy(self):
        kind, label = checker._classify_doctype(
            '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN">')
        self.assertEqual(kind, "legacy")
        self.assertEqual(label, "HTML 4.01")

    def test_html32_legacy(self):
        kind, label = checker._classify_doctype(
            '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">')
        self.assertEqual(kind, "legacy")
        self.assertEqual(label, "HTML 3.2")

    def test_xhtml10_strict_legacy(self):
        kind, label = checker._classify_doctype(
            '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" '
            '"http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">')
        self.assertEqual(kind, "legacy")
        self.assertEqual(label, "XHTML 1.0 Strict")

    def test_xhtml10_transitional_legacy(self):
        kind, label = checker._classify_doctype(
            '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" '
            '"http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">')
        self.assertEqual(kind, "legacy")
        self.assertEqual(label, "XHTML 1.0 Transitional")

    def test_xhtml11_legacy(self):
        kind, label = checker._classify_doctype(
            '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" '
            '"http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">')
        self.assertEqual(kind, "legacy")
        self.assertEqual(label, "XHTML 1.1")

    def test_html40_legacy(self):
        kind, label = checker._classify_doctype(
            '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0 Transitional//EN" '
            '"http://www.w3.org/TR/html4/loose.dtd">')
        self.assertEqual(kind, "legacy")
        self.assertEqual(label, "HTML 4.0 Transitional")

    def test_wrong_doctype(self):
        kind, _ = checker._classify_doctype("<!DOCTYPE foo>")
        self.assertEqual(kind, "wrong")

    def test_wrong_doctype_with_public(self):
        kind, _ = checker._classify_doctype(
            '<!DOCTYPE html PUBLIC "-//EXAMPLE//DTD Something//EN">')
        self.assertEqual(kind, "wrong")

    def test_wrong_doctype_svg(self):
        kind, _ = checker._classify_doctype(
            '<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" '
            '"http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">')
        self.assertEqual(kind, "wrong")


class TestCheckDocument(unittest.TestCase):
    def check(self, text):
        return checker.check_document(text, "page.html")

    def test_correct_doctype_no_problems(self):
        self.assertEqual(self.check(GOOD), [])

    def test_correct_doctype_case_insensitive(self):
        self.assertEqual(self.check("<!doctype HTML>\n<html></html>"), [])

    def test_correct_doctype_extra_spaces(self):
        self.assertEqual(self.check("<!DOCTYPE   html  >\n<html></html>"), [])

    def test_missing_doctype(self):
        problems = self.check("<html><head></head><body></body></html>")
        self.assertEqual(kinds(problems), ["missing"])
        self.assertEqual(problems[0]["line"], 1)
        self.assertIn("missing doctype", problems[0]["message"])

    def test_empty_document_missing(self):
        self.assertEqual(kinds(self.check("")), ["missing"])

    def test_whitespace_only_missing(self):
        self.assertEqual(kinds(self.check("   \n\n  ")), ["missing"])

    def test_comment_only_missing(self):
        self.assertEqual(kinds(self.check("<!-- nothing here -->\n")), ["missing"])

    def test_legacy_reported_with_name(self):
        problems = self.check(
            '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" '
            '"http://www.w3.org/TR/html4/loose.dtd">\n<html></html>')
        self.assertEqual(kinds(problems), ["legacy"])
        self.assertIn("HTML 4.01 Transitional", problems[0]["message"])
        self.assertEqual(problems[0]["line"], 1)

    def test_xhtml_reported_with_name(self):
        problems = self.check(
            '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" '
            '"http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">\n<html></html>')
        self.assertEqual(kinds(problems), ["legacy"])
        self.assertIn("XHTML 1.0 Strict", problems[0]["message"])

    def test_wrong_doctype_reported(self):
        problems = self.check("<!DOCTYPE foo>\n<html></html>")
        self.assertEqual(kinds(problems), ["wrong"])
        self.assertIn("foo", problems[0]["message"])

    def test_blank_lines_before_doctype(self):
        problems = self.check("\n\n<!DOCTYPE html>\n<html></html>")
        self.assertEqual(kinds(problems), ["not-first"])
        self.assertEqual(problems[0]["line"], 3)
        self.assertIn("blank lines", problems[0]["message"])

    def test_comment_before_doctype(self):
        problems = self.check("<!-- hi -->\n<!DOCTYPE html>\n<html></html>")
        self.assertEqual(kinds(problems), ["not-first"])
        self.assertEqual(problems[0]["line"], 2)
        self.assertIn("comment", problems[0]["message"])

    def test_doctype_after_html_tag(self):
        problems = self.check("<html>\n<!DOCTYPE html>\n</html>")
        self.assertEqual(kinds(problems), ["not-first"])
        self.assertEqual(problems[0]["line"], 2)
        self.assertIn("other content", problems[0]["message"])

    def test_doctype_on_line_2_after_text(self):
        problems = self.check("hello\n<!DOCTYPE html>\n<html></html>")
        self.assertEqual(kinds(problems), ["not-first"])
        self.assertEqual(problems[0]["line"], 2)

    def test_bom_before_doctype_ok(self):
        self.assertEqual(self.check("\ufeff<!DOCTYPE html>\n<html></html>"), [])

    def test_leading_spaces_before_doctype_on_line_1(self):
        self.assertEqual(self.check("   <!DOCTYPE html>\n<html></html>"), [])

    def test_multiple_doctypes(self):
        problems = self.check(
            "<!DOCTYPE html>\n<html></html>\n<!DOCTYPE html>\n")
        self.assertEqual(kinds(problems), ["multiple"])
        self.assertEqual(problems[0]["line"], 3)

    def test_multiple_doctypes_after_legacy(self):
        problems = self.check(
            '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" '
            '"http://www.w3.org/TR/html4/strict.dtd">\n<html></html>\n'
            '<!DOCTYPE html>\n')
        self.assertEqual(kinds(problems), ["legacy", "multiple"])

    def test_doctype_inside_comment_does_not_count(self):
        problems = self.check(
            "<!-- <!DOCTYPE html> -->\n<html></html>")
        self.assertEqual(kinds(problems), ["missing"])

    def test_doctype_inside_comment_then_real_one(self):
        problems = self.check(
            "<!-- <!DOCTYPE html> -->\n<!DOCTYPE html>\n<html></html>")
        self.assertEqual(kinds(problems), ["not-first"])
        self.assertEqual(problems[0]["line"], 2)

    def test_doctype_after_multiline_comment(self):
        problems = self.check(
            "<!--\nline two\n-->\n<!DOCTYPE html>\n<html></html>")
        self.assertEqual(kinds(problems), ["not-first"])
        self.assertEqual(problems[0]["line"], 4)

    def test_legacy_on_line_2_reports_both(self):
        problems = self.check(
            "\n<!DOCTYPE HTML PUBLIC \"-//W3C//DTD HTML 4.01//EN\" "
            "\"http://www.w3.org/TR/html4/strict.dtd\">\n<html></html>")
        self.assertEqual(kinds(problems), ["legacy", "not-first"])

    def test_wrong_doctype_on_line_2_reports_both(self):
        problems = self.check("\n<!DOCTYPE foo>\n<html></html>")
        self.assertEqual(kinds(problems), ["wrong", "not-first"])

    def test_problem_carries_file_name(self):
        problems = checker.check_document("<html></html>", "some/page.html")
        self.assertEqual(problems[0]["file"], "some/page.html")

    def test_doctype_without_closing_bracket_missing(self):
        problems = self.check("<!DOCTYPE html\n<html></html>")
        self.assertEqual(kinds(problems), ["missing"])


class TestCheckFile(unittest.TestCase):
    def test_clean_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "good.html", GOOD)
            self.assertEqual(checker.check_file(path), [])

    def test_bad_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.html", "<html></html>")
            problems = checker.check_file(path)
            self.assertEqual(kinds(problems), ["missing"])
            self.assertTrue(problems[0]["file"].endswith("bad.html"))

    def test_missing_file_reports_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            problems = checker.check_file(os.path.join(tmp, "nope.html"))
            self.assertEqual(kinds(problems), ["unreadable"])

    def test_non_utf8_file_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.html",
                         b"<!DOCTYPE html>\n<html>\xff\xfe</html>")
            problems = checker.check_file(path)
            self.assertEqual(kinds(problems), ["unreadable"])
            self.assertIn("UTF-8", problems[0]["message"])

    def test_bom_file_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bom.html",
                         b"\xef\xbb\xbf<!DOCTYPE html>\n<html></html>")
            self.assertEqual(checker.check_file(path), [])

    def test_input_file_left_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.html", "<html></html>")
            before = Path(path).read_bytes()
            checker.check_file(path)
            self.assertEqual(Path(path).read_bytes(), before)


class TestCollectFiles(unittest.TestCase):
    def test_direct_file_any_name_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "weird.txt", GOOD)
            self.assertEqual(checker.collect_files([path]), [path])

    def test_folder_walk_finds_html_and_htm_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = write(tmp, "a.html", GOOD)
            b = write(tmp, "sub/b.htm", GOOD)
            write(tmp, "c.txt", GOOD)
            write(tmp, "d.css", "body {}")
            found = checker.collect_files([tmp])
            self.assertEqual(found, sorted([a, b]))

    def test_folder_walk_is_recursive(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = write(tmp, "a.html", GOOD)
            b = write(tmp, "deep/deeper/c.html", GOOD)
            self.assertEqual(checker.collect_files([tmp]), sorted([a, b]))

    def test_git_folder_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = write(tmp, "a.html", GOOD)
            write(tmp, ".git/hooks/sample.html", GOOD)
            self.assertEqual(checker.collect_files([tmp]), [a])

    def test_no_recursive(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = write(tmp, "a.html", GOOD)
            write(tmp, "sub/b.html", GOOD)
            self.assertEqual(checker.collect_files([tmp], recursive=False), [a])

    def test_exclude_pattern(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = write(tmp, "a.html", GOOD)
            write(tmp, "vendor/b.html", GOOD)
            found = checker.collect_files([tmp], exclude=["vendor"])
            self.assertEqual(found, [a])

    def test_missing_path_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                checker.collect_files([os.path.join(tmp, "nope")])

    def test_uppercase_extension_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = write(tmp, "UP.HTML", GOOD)
            self.assertEqual(checker.collect_files([tmp]), [a])


class TestMain(unittest.TestCase):
    def test_clean_run_exit_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "good.html", GOOD)
            code, out, _ = run_cli([path])
            self.assertEqual(code, 0)
            self.assertIn("OK", out)

    def test_dirty_run_exit_1_and_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.html", "<html></html>")
            code, out, _ = run_cli([path])
            self.assertEqual(code, 1)
            self.assertIn("FAIL", out)
            self.assertIn("bad.html", out)
            self.assertIn("line 1", out)

    def test_folder_summary_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "a.html", GOOD)
            write(tmp, "b.html", "<html></html>")
            write(tmp, "c.html", "<!DOCTYPE foo>\n<html></html>")
            code, out, _ = run_cli([tmp])
            self.assertEqual(code, 1)
            self.assertIn("Checked 3 file(s), 2 problem(s) in 2 file(s).", out)

    def test_json_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.html", "<html></html>")
            code, out, _ = run_cli(["--json", path])
            self.assertEqual(code, 1)
            data = json.loads(out)
            self.assertFalse(data["ok"])
            self.assertEqual(data["files_checked"], 1)
            self.assertEqual(len(data["problems"]), 1)
            self.assertEqual(data["problems"][0]["kind"], "missing")
            self.assertTrue(data["problems"][0]["file"].endswith("bad.html"))

    def test_json_output_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "good.html", GOOD)
            code, out, _ = run_cli(["--json", path])
            self.assertEqual(code, 0)
            data = json.loads(out)
            self.assertTrue(data["ok"])
            self.assertEqual(data["problems"], [])

    def test_stdin_clean(self):
        code, out, _ = run_cli(["--stdin"], stdin_text=GOOD)
        self.assertEqual(code, 0)
        self.assertIn("OK", out)

    def test_stdin_dirty(self):
        code, out, _ = run_cli(["--stdin"], stdin_text="<html></html>")
        self.assertEqual(code, 1)
        self.assertIn("missing doctype", out)

    def test_stdin_with_paths_is_usage_error(self):
        code, _, err = run_cli(["--stdin", "x.html"])
        self.assertEqual(code, 2)
        self.assertIn("usage", err.lower())

    def test_no_paths_is_usage_error(self):
        code, _, err = run_cli([])
        self.assertEqual(code, 2)
        self.assertIn("usage", err.lower())

    def test_missing_path_exit_2(self):
        code, _, err = run_cli(["/nonexistent/page.html"])
        self.assertEqual(code, 2)
        self.assertIn("no such file", err.lower())

    def test_empty_folder_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _, err = run_cli([tmp])
            self.assertEqual(code, 2)
            self.assertIn("no HTML files", err)

    def test_bad_flag_exit_2(self):
        code, _, _ = run_cli(["--nope"])
        self.assertEqual(code, 2)

    def test_version(self):
        code, out, _ = run_cli(["--version"])
        self.assertEqual(code, 0)
        self.assertIn("html_doctype_checker", out)

    def test_non_utf8_file_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.html", b"<html>\xff</html>")
            code, out, _ = run_cli([path])
            self.assertEqual(code, 1)
            self.assertIn("UTF-8", out)

    def test_cli_runs_from_another_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "good.html", GOOD)
            result = subprocess.run(
                [sys.executable, str(REPO / "src" / "html_doctype_checker.py"), path],
                capture_output=True, text=True, cwd="/tmp",
                env={**os.environ, "HOME": "/tmp/fakehome"},
            )
            self.assertEqual(result.returncode, 0)
            self.assertIn("OK", result.stdout)

    def test_run_example_output_matches_sample(self):
        result = subprocess.run(
            ["sh", str(REPO / "examples" / "run-example.sh")],
            capture_output=True, text=True, cwd=str(REPO),
        )
        sample = (REPO / "examples" / "sample-output.md").read_text()
        self.assertIn(result.stdout.strip(), sample)

    def test_readme_quotes_match_real_runs(self):
        readme = (REPO / "README.md").read_text()
        good = subprocess.run(
            [sys.executable, "src/html_doctype_checker.py",
             "examples/good.html"],
            capture_output=True, text=True, cwd=str(REPO),
        )
        self.assertEqual(good.returncode, 0)
        self.assertIn(good.stdout.strip(), readme)
        bad = subprocess.run(
            [sys.executable, "src/html_doctype_checker.py",
             "examples/bad.html"],
            capture_output=True, text=True, cwd=str(REPO),
        )
        self.assertEqual(bad.returncode, 1)
        self.assertIn(bad.stdout.strip(), readme)
        legacy = subprocess.run(
            [sys.executable, "src/html_doctype_checker.py",
             "examples/legacy.html"],
            capture_output=True, text=True, cwd=str(REPO),
        )
        self.assertEqual(legacy.returncode, 1)
        self.assertIn(legacy.stdout.strip(), readme)
        edge = subprocess.run(
            [sys.executable, "src/html_doctype_checker.py",
             "examples/edge.html"],
            capture_output=True, text=True, cwd=str(REPO),
        )
        self.assertEqual(edge.returncode, 1)
        self.assertIn(edge.stdout.strip(), readme)
        folder = subprocess.run(
            [sys.executable, "src/html_doctype_checker.py", "examples/"],
            capture_output=True, text=True, cwd=str(REPO),
        )
        self.assertEqual(folder.returncode, 1)
        self.assertIn(folder.stdout.strip(), readme)
        self.assertIn("Checked 4 file(s), 3 problem(s) in 3 file(s).",
                      folder.stdout)
        self.assertIn("Checked 4 file(s), 3 problem(s) in 3 file(s).",
                      readme)
        js = subprocess.run(
            [sys.executable, "src/html_doctype_checker.py",
             "--json", "examples/bad.html"],
            capture_output=True, text=True, cwd=str(REPO),
        )
        self.assertEqual(js.returncode, 1)
        self.assertIn(js.stdout.strip(), readme)
        nested = subprocess.run(
            [sys.executable, str(REPO / "src" / "html_doctype_checker.py"),
             str(REPO / "examples" / "good.html")],
            capture_output=True, text=True, cwd="/tmp",
        )
        self.assertEqual(nested.returncode, 0)


class TestRepoHygiene(unittest.TestCase):
    def _repo_files(self):
        files = []
        for root, dirs, filenames in os.walk(REPO):
            dirs[:] = [d for d in dirs
                       if d not in (".git", "__pycache__", "tests")]
            for name in filenames:
                files.append(Path(root) / name)
        return files

    def test_no_placeholder_text(self):
        banned = ["TODO", "FIXME", "coming soon", "lorem", "XXX"]
        for path in self._repo_files():
            text = path.read_text(errors="ignore")
            for word in banned:
                self.assertNotIn(word, text, "%s contains %r" % (path, word))

    def test_no_absolute_paths(self):
        for path in self._repo_files():
            text = path.read_text(errors="ignore")
            self.assertNotIn("/home/hatch", text, str(path))
            self.assertNotIn("/Users/", text, str(path))

    def test_no_secrets(self):
        for path in self._repo_files():
            text = path.read_text(errors="ignore").lower()
            for word in ["api_key", "password =", "secret =", "token ="]:
                self.assertNotIn(word, text, "%s contains %r" % (path, word))

    def test_stdlib_imports_only(self):
        import ast
        allowed = {"argparse", "json", "os", "re", "sys"}
        tree = ast.parse((REPO / "src" / "html_doctype_checker.py").read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertIn(alias.name.split(".")[0], allowed)
            elif isinstance(node, ast.ImportFrom):
                self.assertIn(node.module.split(".")[0], allowed)

    def test_no_network_use_in_src(self):
        src = (REPO / "src" / "html_doctype_checker.py").read_text()
        for word in ["urllib", "requests", "socket", "http.client", "urlopen"]:
            self.assertNotIn(word, src)

    def test_gitignore_lists_env_first(self):
        lines = (REPO / ".gitignore").read_text().splitlines()
        self.assertEqual(lines[0], ".env")

    def test_ci_runs_this_test_file(self):
        ci = (REPO / ".github" / "workflows" / "ci.yml").read_text()
        self.assertIn("actions/checkout", ci)
        self.assertIn("setup-python", ci)
        self.assertIn("tests/test_html_doctype_checker.py", ci)
        self.assertIn("push", ci)
        self.assertIn("pull_request", ci)
        self.assertIn("3.12", ci)

    def test_licence_present(self):
        self.assertTrue((REPO / "LICENSE").exists())
        self.assertIn("MIT License", (REPO / "LICENSE").read_text())

    def test_readme_says_doctype_only(self):
        readme = (REPO / "README.md").read_text()
        self.assertIn("doctype only", readme.lower())
        self.assertIn("html-title-checker-cli", readme)


if __name__ == "__main__":
    unittest.main(verbosity=2)
