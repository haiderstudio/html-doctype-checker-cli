Output of `sh examples/run-example.sh`, run from the repo root:

```
== examples/good.html ==
OK — 1 file(s) checked, every file starts with <!DOCTYPE html>.

== examples/bad.html ==
FAIL examples/bad.html: missing doctype — add <!DOCTYPE html> as the first line (line 1)
Checked 1 file(s), 1 problem(s) in 1 file(s).

== examples/legacy.html ==
FAIL examples/legacy.html: legacy doctype HTML 4.01 Transitional — replace it with <!DOCTYPE html> (line 1)
Checked 1 file(s), 1 problem(s) in 1 file(s).

== examples/edge.html ==
FAIL examples/edge.html: doctype is on line 4, not line 1 (comment(s) before it) (line 4)
Checked 1 file(s), 1 problem(s) in 1 file(s).

== examples/ : the whole folder ==
FAIL examples/bad.html: missing doctype — add <!DOCTYPE html> as the first line (line 1)
FAIL examples/edge.html: doctype is on line 4, not line 1 (comment(s) before it) (line 4)
FAIL examples/legacy.html: legacy doctype HTML 4.01 Transitional — replace it with <!DOCTYPE html> (line 1)
Checked 4 file(s), 3 problem(s) in 3 file(s).
```
