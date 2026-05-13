"""Unit tests for the bench matrix runner.

Pure-function tests on enumeration, key validation, log parsing, and
summarization. The actual subprocess-driven `run_one_job` path is
exercised by test_smoke.py (slow, opt-in).
"""
from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from tools.bench.runner import (
    JobSpec,
    ModelEntry,
    enumerate_jobs,
    load_done_set,
    load_keyfile,
    load_models,
    parse_codex_cost_from_log,
    parse_opencode_cost_from_log,
    summarize_run,
    validate_keys,
)


# ---- model loading -----------------------------------------------------


def _write_models_yaml(p: Path, n: int) -> None:
    lines = ["models:"]
    for i in range(n):
        lines.append(f"  - name: m{i}")
        lines.append(f"    model: prov{i}/m{i}")
        lines.append(f"    key_env: KEY{i}")
    p.write_text("\n".join(lines) + "\n")


def test_load_models_round_trip(tmp_path: Path):
    p = tmp_path / "models.yaml"
    _write_models_yaml(p, 3)
    out = load_models(p)
    assert len(out) == 3
    assert out[0].name == "m0"
    assert out[0].model == "prov0/m0"
    assert out[0].key_env == "KEY0"


def test_load_models_empty_raises(tmp_path: Path):
    p = tmp_path / "models.yaml"
    p.write_text("models: []\n")
    with pytest.raises(ValueError):
        load_models(p)


# ---- done-set + enumeration -------------------------------------------


def test_load_done_set_skips_partial(tmp_path: Path):
    p = tmp_path / "results.jsonl"
    p.write_text(
        json.dumps({"model": "a", "rep": 1, "status": "done"}) + "\n"
        + json.dumps({"model": "a", "rep": 2, "status": "running"}) + "\n"
        + json.dumps({"model": "b", "rep": 1, "status": "timed_out"}) + "\n"
        + json.dumps({"model": "b", "rep": 2, "status": "failed"}) + "\n"
    )
    done = load_done_set(p)
    # done + timed_out + failed all count as terminal (don't retry)
    assert ("a", 1) in done
    assert ("b", 1) in done
    assert ("b", 2) in done
    # running is not terminal — retry it
    assert ("a", 2) not in done


def test_load_done_set_missing_file(tmp_path: Path):
    assert load_done_set(tmp_path / "absent.jsonl") == set()


def test_enumerate_jobs_skips_done():
    models = [
        ModelEntry(name="a", model="x/a", key_env="K"),
        ModelEntry(name="b", model="x/b", key_env="K"),
    ]
    done = {("a", 1), ("a", 2)}
    jobs = enumerate_jobs(models, reps=2, done=done)
    assert len(jobs) == 2
    assert {(j.model.name, j.rep) for j in jobs} == {("b", 1), ("b", 2)}


def test_enumerate_jobs_only_filter():
    models = [
        ModelEntry(name="a", model="x/a", key_env="K"),
        ModelEntry(name="b", model="x/b", key_env="K"),
    ]
    jobs = enumerate_jobs(models, reps=1, done=set(), only_models=["b"])
    assert len(jobs) == 1
    assert jobs[0].model.name == "b"


# ---- key validation ----------------------------------------------------


def test_validate_keys_finds_missing():
    jobs = [
        JobSpec(ModelEntry(name="a", model="x/a", key_env="HAS_KEY"), 1),
        JobSpec(ModelEntry(name="b", model="x/b", key_env="MISSING_KEY"), 1),
    ]
    env = {"HAS_KEY": "yes"}
    missing = validate_keys(jobs, env)
    assert missing == ["MISSING_KEY"]


def test_validate_keys_all_present():
    jobs = [JobSpec(ModelEntry(name="a", model="x/a", key_env="K"), 1)]
    env = {"K": "v"}
    assert validate_keys(jobs, env) == []


def test_validate_keys_skips_oauth_models():
    jobs = [
        JobSpec(ModelEntry(name="a", model="gpt-5.5",
                           key_env="", oauth=True, provider="codex"), 1),
        JobSpec(ModelEntry(name="b", model="anthropic/c", key_env="K"), 1),
    ]
    env = {"K": "v"}
    # OAuth model contributes nothing to needed-keys.
    assert validate_keys(jobs, env) == []
    # Missing the API key for the non-OAuth model still flagged.
    assert validate_keys(jobs, {}) == ["K"]


def test_load_keyfile_parses_simple(tmp_path: Path):
    f = tmp_path / "keys.env"
    f.write_text(textwrap.dedent("""
        # comment line
        ANTHROPIC_API_KEY=sk-ant-test
        OPENAI_API_KEY = "sk-openai-test"
        OPENROUTER_API_KEY='sk-or-test'

        # blank line above
    """).strip() + "\n")
    out = load_keyfile(f)
    assert out["ANTHROPIC_API_KEY"] == "sk-ant-test"
    assert out["OPENAI_API_KEY"] == "sk-openai-test"
    assert out["OPENROUTER_API_KEY"] == "sk-or-test"


def test_load_keyfile_missing_returns_empty(tmp_path: Path):
    assert load_keyfile(tmp_path / "absent") == {}


# ---- codex cost parsing -----------------------------------------------


def test_parse_codex_cost_sums_turn_completed(tmp_path: Path):
    """Sum input_tokens (gross) + output_tokens + reasoning_output_tokens."""
    p = tmp_path / "agent.log"
    p.write_text(
        json.dumps({"type": "turn.completed",
                    "usage": {"input_tokens": 1000, "cached_input_tokens": 800,
                              "output_tokens": 200,
                              "reasoning_output_tokens": 50}}) + "\n"
        + json.dumps({"type": "command_execution"}) + "\n"
        + json.dumps({"type": "turn.completed",
                      "usage": {"input_tokens": 500, "cached_input_tokens": 400,
                                "output_tokens": 100,
                                "reasoning_output_tokens": 25}}) + "\n"
    )
    toks_in, toks_out, cost = parse_codex_cost_from_log(p)
    assert toks_in == 1500   # gross input (cache included)
    assert toks_out == 375   # 200+50 + 100+25
    assert cost == 0.0       # OAuth — no per-call billing


def test_parse_codex_cost_handles_missing_file(tmp_path: Path):
    assert parse_codex_cost_from_log(tmp_path / "absent") == (0, 0, 0.0)


def test_parse_codex_cost_dedups_repeated_lines(tmp_path: Path):
    """collect_agent_logs can concatenate the same hypothesis log twice;
    the parser must dedup by line content."""
    p = tmp_path / "agent.log"
    line = json.dumps({"type": "turn.completed",
                       "usage": {"input_tokens": 1000, "output_tokens": 100,
                                 "reasoning_output_tokens": 0}})
    p.write_text(line + "\n" + line + "\n" + line + "\n")
    toks_in, _toks_out, _cost = parse_codex_cost_from_log(p)
    assert toks_in == 1000  # counted once, not three times


# ---- opencode cost parsing --------------------------------------------


def test_parse_opencode_cost_includes_cache_and_reasoning(tmp_path: Path):
    """Gross input = tokens.input + cache.read + cache.write.
    Output = tokens.output + tokens.reasoning."""
    p = tmp_path / "agent.log"
    p.write_text(
        json.dumps({"type": "step_finish",
                    "part": {"tokens": {"input": 100, "output": 50,
                                         "reasoning": 200,
                                         "cache": {"read": 800, "write": 0}},
                              "cost": 0}}) + "\n"
    )
    toks_in, toks_out, cost = parse_opencode_cost_from_log(p)
    assert toks_in == 900    # 100 + 800 + 0
    assert toks_out == 250   # 50 + 200
    assert cost == 0.0


def test_parse_opencode_cost_handles_missing_file(tmp_path: Path):
    assert parse_opencode_cost_from_log(tmp_path / "absent") == (0, 0, 0.0)


# ---- summarize_run -----------------------------------------------------


def test_summarize_run_reads_run_summary_json(tmp_path: Path):
    """summarize_run loads the orchestrator-emitted run_summary.json
    verbatim and folds in token counts from agent.log."""
    log = tmp_path / "log.jsonl"
    log.write_text("")  # not consulted under the new contract
    (tmp_path / "run_summary.json").write_text(json.dumps({
        "iterations":      4,
        "accepted":        2,
        "rejected":        1,
        "broken":          1,
        "broken_by_class": {"formal_failed": 1},
        "baseline_fitness": 300.0,
        "final_fitness":    320.0,
        "best_fitness":     320.0,
        "best_round":       4,
        "delta_pct":        (20.0 / 300.0 * 100),
    }))
    agent = tmp_path / "agent.log"
    agent.write_text(
        json.dumps({"type": "turn.completed",
                    "usage": {"input_tokens": 1000, "output_tokens": 200,
                              "reasoning_output_tokens": 0}}) + "\n"
    )
    summary = summarize_run(log, agent, provider="codex")
    assert summary["iterations"] == 4
    assert summary["accepted"] == 2
    assert summary["rejected"] == 1
    assert summary["broken"] == 1
    assert summary["broken_by_class"] == {"formal_failed": 1}
    assert summary["final_fitness"] == 320.0
    assert summary["best_fitness"] == 320.0
    assert summary["best_round"] == 4
    assert summary["baseline_fitness"] == 300.0
    assert summary["delta_pct"] is not None
    assert abs(summary["delta_pct"] - (20.0 / 300.0 * 100)) < 1e-6
    # Token counts always come from agent.log (provider-specific cost
    # parsing); not in scope of run_summary.json.
    assert summary["total_tokens_in"] == 1000
    assert summary["total_tokens_out"] == 200


def test_summarize_run_missing_summary_flags_row(tmp_path: Path):
    """If run_summary.json is absent (orchestrator crashed before its
    first emit, or pre-Phase-2 orchestrator), the row carries
    summary_missing=True instead of silently scoring 0/0/0 from a
    log.jsonl fallback we used to have."""
    summary = summarize_run(tmp_path / "absent.jsonl", tmp_path / "absent.log")
    assert summary["iterations"] == 0
    assert summary["accepted"] == 0
    assert summary["final_fitness"] is None
    assert summary["best_fitness"] is None
    assert summary.get("summary_missing") is True


def test_summarize_run_malformed_json_flags_row(tmp_path: Path):
    """Mid-write or corrupt run_summary.json behaves like an absent file."""
    log = tmp_path / "log.jsonl"
    log.write_text("")
    (tmp_path / "run_summary.json").write_text("not json {")
    agent = tmp_path / "agent.log"
    agent.write_text("")
    summary = summarize_run(log, agent, provider="codex")
    assert summary.get("summary_missing") is True
    assert summary["iterations"] == 0


def test_summarize_run_carries_best_fpga_fields(tmp_path: Path):
    """LUT4/FF/Fmax/IPC of the best-fitness entry propagate from
    run_summary.json into the per-rep results.jsonl row, so downstream
    consumers (LEADERBOARD, plots, postmortems) don't have to join from
    log.jsonl."""
    log = tmp_path / "log.jsonl"
    log.write_text("")
    (tmp_path / "run_summary.json").write_text(json.dumps({
        "iterations": 16, "accepted": 5, "rejected": 10, "broken": 1,
        "broken_by_class": {"cosim_failed": 1},
        "baseline_fitness": 282.82, "final_fitness": 525.04,
        "best_fitness": 525.04, "best_round": 10, "delta_pct": 85.6,
        "best_lut4": 5453, "best_ff": 2138, "best_fmax_mhz": 220.22,
        "best_iterations": 10, "best_cycles": 4194377,
        "best_ipc_coremark": 2e-06,
    }))
    agent = tmp_path / "agent.log"
    agent.write_text("")
    summary = summarize_run(log, agent, provider="codex")
    assert summary["best_lut4"] == 5453
    assert summary["best_ff"] == 2138
    assert summary["best_fmax_mhz"] == 220.22
    assert summary["best_iterations"] == 10
    assert summary["best_cycles"] == 4194377
    assert summary["best_ipc_coremark"] == 2e-06


def test_summarize_run_missing_summary_includes_best_fpga_fields_none(tmp_path: Path):
    """The summary_missing row must still carry the FPGA-field keys (as None)
    so the results.jsonl schema is uniform across done/broken/missing rows."""
    summary = summarize_run(tmp_path / "absent.jsonl", tmp_path / "absent.log")
    assert summary.get("summary_missing") is True
    for k in ("best_lut4", "best_ff", "best_fmax_mhz",
              "best_iterations", "best_cycles", "best_ipc_coremark"):
        assert k in summary, f"missing key {k!r} in summary_missing row"
        assert summary[k] is None
