"""Regression: _write_md must write to its `path` argument.

Found during the local-model arm fold-in: `--out-tag -local` wrote
evals/results-local.json correctly but clobbered evals/results.md, because
_write_md hardcoded the module-level RESULTS_MD constant.
"""


def test_write_md_honors_explicit_path(tmp_path):
    from smelt_rs.evals import _write_md

    results = [{
        "function": "f", "category": "int", "status": "accepted", "attempts": 1,
        "oracle_cases": 2, "speedup": 2.0, "speedup_lb": 1.8, "reason": "ok",
    }]
    summary = {"provider": "file", "model": None, "tasks": 1, "completed": 1,
               "accepted": 1, "rejected": 0, "errors": 0, "provider_calls": {},
               "max_calls": 1}
    out = tmp_path / "results-x.md"
    _write_md(results, summary, str(out))
    assert out.exists(), "output must land at the given path"
    text = out.read_text()
    assert "`f`" in text and "# smelt eval results" in text
