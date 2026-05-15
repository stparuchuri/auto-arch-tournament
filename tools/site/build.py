"""HWE Bench site builder.

Reads bench/results.jsonl + per-rep log.jsonl and renders the static site.
Single-file Python — no Jinja2 / no node / no jekyll. Run after a bench
update; commit the generated HTML.

Usage:
    python -m tools.site.build
    python -m tools.site.build --out site/

The generator is intentionally simple: f-string templates, no template
engine. If you want to change copy, edit this file. If you want to
change layout, edit the HTML / CSS in site/. Tokens live in
site/css/tokens.css; STYLE.md (.design/branding/hwe-bench/patterns/)
is the canonical style guide.
"""
from __future__ import annotations

import argparse
import json
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

HERE = Path(__file__).parent
REPO = HERE.parent.parent
DEFAULT_RESULTS = REPO / "bench" / "results.jsonl"
DEFAULT_OUT = REPO / "site"

BASELINE_FITNESS = 282.82
SITE_VERSION = "v1 · 2026-05"


@dataclass
class Rep:
    model: str
    rep: int
    status: str
    final_fitness: Optional[float]
    best_fitness: Optional[float]
    baseline_fitness: Optional[float]
    delta_pct: Optional[float]
    iterations: int
    accepted: int
    rejected: int
    broken: int
    broken_by_class: dict
    wall_clock_sec: int
    total_cost_usd: float
    total_tokens_in: int
    total_tokens_out: int
    best_lut4: Optional[int]
    best_ff: Optional[int]
    best_fmax_mhz: Optional[float]
    best_iterations: Optional[int]
    best_cycles: Optional[int]
    best_ipc_coremark: Optional[float]
    winners: list = field(default_factory=list)  # list[dict] from log.jsonl

    @property
    def delta(self) -> float:
        return self.delta_pct or 0.0

    @property
    def is_complete(self) -> bool:
        return self.status == "done"


def load_reps(results_path: Path, repo: Path) -> list[Rep]:
    """Load rows from results.jsonl and enrich each with its winners list."""
    reps: list[Rep] = []
    for raw in results_path.read_text().splitlines():
        if not raw.strip():
            continue
        d = json.loads(raw)
        reps.append(Rep(
            model=d.get("model", "?"),
            rep=int(d.get("rep", 0)),
            status=d.get("status", "?"),
            final_fitness=d.get("final_fitness"),
            best_fitness=d.get("best_fitness"),
            baseline_fitness=d.get("baseline_fitness"),
            delta_pct=d.get("delta_pct"),
            iterations=int(d.get("iterations") or 0),
            accepted=int(d.get("accepted") or 0),
            rejected=int(d.get("rejected") or 0),
            broken=int(d.get("broken") or 0),
            broken_by_class=dict(d.get("broken_by_class") or {}),
            wall_clock_sec=int(d.get("wall_clock_sec") or 0),
            total_cost_usd=float(d.get("total_cost_usd") or 0.0),
            total_tokens_in=int(d.get("total_tokens_in") or 0),
            total_tokens_out=int(d.get("total_tokens_out") or 0),
            best_lut4=d.get("best_lut4"),
            best_ff=d.get("best_ff"),
            best_fmax_mhz=d.get("best_fmax_mhz"),
            best_iterations=d.get("best_iterations"),
            best_cycles=d.get("best_cycles"),
            best_ipc_coremark=d.get("best_ipc_coremark"),
        ))
    # Enrich with per-rep winners
    for rep in reps:
        log = repo / "bench" / rep.model / f"rep{rep.rep}" / "log.jsonl"
        if not log.is_file():
            continue
        rep.winners = _winners_from_log(log)
    return reps


def _winners_from_log(log_path: Path) -> list[dict]:
    """Return ordered list of accepted-improvement entries (excluding baseline)."""
    wins: list[dict] = []
    for raw in log_path.read_text().splitlines():
        if not raw.strip():
            continue
        try:
            e = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if e.get("outcome") in ("improvement", "accepted") and e.get("round_id", 0) != 0:
            wins.append(e)
    return wins


@dataclass
class ModelAgg:
    model: str
    reps: list[Rep]
    n_done: int
    n_total: int
    fitness_mean: Optional[float]
    fitness_median: Optional[float]
    fitness_std: Optional[float]
    fitness_best: Optional[float]
    delta_mean: Optional[float]
    delta_best: Optional[float]
    total_cost_usd: float
    broken_by_class_total: dict
    best_rep: Optional[Rep]  # the rep that produced fitness_best


def aggregate(reps: list[Rep]) -> list[ModelAgg]:
    by_model: dict[str, list[Rep]] = {}
    for r in reps:
        by_model.setdefault(r.model, []).append(r)

    out: list[ModelAgg] = []
    for model, group in by_model.items():
        done = [r for r in group if r.is_complete and r.final_fitness is not None]
        # Include failed-but-with-data reps in the "best" tally so the leaderboard
        # surfaces a model's reachable peak even when one rep crashed mid-run.
        with_data = [r for r in group if r.best_fitness is not None]
        fits_done = [r.final_fitness for r in done if r.final_fitness is not None]
        deltas_done = [r.delta_pct for r in done if r.delta_pct is not None]
        best_rep = max(with_data, key=lambda r: r.best_fitness or -1) if with_data else None
        broken_classes: dict[str, int] = {}
        for r in group:
            for cls, n in r.broken_by_class.items():
                broken_classes[cls] = broken_classes.get(cls, 0) + int(n)
        out.append(ModelAgg(
            model=model,
            reps=sorted(group, key=lambda r: r.rep),
            n_done=len(done),
            n_total=len(group),
            fitness_mean=statistics.fmean(fits_done) if fits_done else None,
            fitness_median=statistics.median(fits_done) if fits_done else None,
            fitness_std=(statistics.pstdev(fits_done) if len(fits_done) > 1
                         else (0.0 if fits_done else None)),
            fitness_best=best_rep.best_fitness if best_rep else None,
            delta_mean=statistics.fmean(deltas_done) if deltas_done else None,
            delta_best=best_rep.delta if best_rep else None,
            total_cost_usd=sum(r.total_cost_usd for r in group),
            broken_by_class_total=broken_classes,
            best_rep=best_rep,
        ))
    out.sort(key=lambda a: -(a.fitness_best or 0))
    return out


# ── formatting helpers ─────────────────────────────────────────────

def fnum(x, fmt=".2f"):
    return "—" if x is None else format(x, fmt)

def fpct(x, fmt="+.1f"):
    return "—" if x is None else f"{format(x, fmt)}%"

def fmoney(x):
    return "—" if x is None else f"${x:.2f}"

def fhours(sec):
    if not sec:
        return "—"
    return f"{sec/3600:.1f}h"

def fcompact(n):
    if n is None: return "—"
    if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
    if n >= 1_000: return f"{n/1_000:.1f}k"
    return f"{n}"


# ── shared HTML fragments ──────────────────────────────────────────

def head(title: str, current: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="HWE Bench is an unbounded benchmark for LLM-generated RISC-V CPU designs, measured by Fmax × IPC on a real FPGA under formal-verification correctness gates.">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:ital,wght@0,400;0,500;1,400&display=swap">
<link rel="stylesheet" href="css/style.css">
<link rel="stylesheet" href="css/print.css">
</head>
<body>
<div class="page">

<nav class="top">
  <a href="index.html" class="wordmark">HWE <span class="alt">Bench</span></a>
  <ul>
    <li><a href="index.html"{' aria-current="page"' if current=='index' else ''}>Leaderboard</a></li>
    <li><a href="methodology.html"{' aria-current="page"' if current=='methodology' else ''}>Methodology</a></li>
    <li><a href="models.html"{' aria-current="page"' if current=='models' else ''}>Models</a></li>
    <li><a href="data.html"{' aria-current="page"' if current=='data' else ''}>Data</a></li>
  </ul>
  <span class="version">{SITE_VERSION}</span>
</nav>
"""

FOOTER = """
<footer class="bot">
  <div>HWE Bench · methodology v1 · <a href="https://github.com/FeSens/auto-arch-tournament" class="ext">source on GitHub</a></div>
  <div class="manifesto">a benchmark that respects how far a frontier model still has to go.</div>
</footer>

</div>
</body>
</html>
"""


# ── page renderers ─────────────────────────────────────────────────

def render_index(aggs: list[ModelAgg], reps: list[Rep]) -> str:
    leader = aggs[0] if aggs else None
    top_rep = leader.best_rep if leader else None
    top_winner = top_rep.winners[-1] if top_rep and top_rep.winners else None

    # stat block from the current top
    if top_rep:
        stat_fit = fnum(top_rep.best_fitness)
        stat_delta = fpct(top_rep.delta_pct)
        stat_lut = fcompact(top_rep.best_lut4)
        stat_fmax = f"{top_rep.best_fmax_mhz:.0f} MHz" if top_rep.best_fmax_mhz else "—"
        stat_model = top_rep.model
    else:
        stat_fit = stat_delta = stat_lut = stat_fmax = stat_model = "—"

    # leaderboard rows (one per model, sorted by peak)
    rows = []
    for i, a in enumerate(aggs, 1):
        rep = a.best_rep
        winner_title = (rep.winners[-1].get("title", "—")[:60] if rep and rep.winners else "—")
        rows.append(f"""
    <tr>
      <td class="num">{i}</td>
      <td><span class="model-name">{a.model}</span></td>
      <td class="num">{a.n_done}/{a.n_total}</td>
      <td class="num">{fnum(a.fitness_best, '.2f')}</td>
      <td class="num">{fpct(a.delta_best)}</td>
      <td class="num">{fnum(a.fitness_mean, '.1f')}{f' ± {a.fitness_std:.1f}' if a.fitness_std else ''}</td>
      <td class="num">{fcompact(rep.best_lut4) if rep else '—'}</td>
      <td class="num">{f'{rep.best_fmax_mhz:.0f}' if rep and rep.best_fmax_mhz else '—'}</td>
      <td class="num">{fmoney(a.total_cost_usd)}</td>
    </tr>""")
    leaderboard_html = "".join(rows)

    return head("HWE Bench — RISC-V CPU design benchmark for LLMs", "index") + f"""
<section class="hero-block">
  <div class="hero-eyebrow">RISC-V · RV32IM · single-issue · FPGA-grounded</div>
  <h1 class="hero">HWE Bench</h1>
  <p class="hero-lede">
    An unbounded benchmark for LLM hardware development.
    Models compete to design RISC-V CPU microarchitectures, measured by CoreMark
    fitness (Fmax × IPC) on a real Tang Nano 20K FPGA, gated by riscv-formal
    correctness and Python-ISS cosim.
  </p>
  <div class="hero-thesis">
    <span class="label">Thesis</span>
    SWE-bench tops out at 100%. HWE Bench doesn't have a top.<br>
    The fitness number reflects an actual microarchitecture, and microarchitecture
    has room to grow as long as models keep finding it.
  </div>
</section>

<section class="section">
  <div class="eyebrow">Current frontier</div>
  <h2>The top design so far</h2>
  <div class="stats">
    <div class="stat"><div class="label">Best fitness</div><div class="value">{stat_fit}</div><div class="sub">{stat_delta} over baseline</div></div>
    <div class="stat"><div class="label">Best Fmax</div><div class="value">{stat_fmax}</div><div class="sub">baseline 127 MHz</div></div>
    <div class="stat"><div class="label">Best LUT4</div><div class="value">{stat_lut}</div><div class="sub">baseline 9.6k</div></div>
    <div class="stat"><div class="label">By model</div><div class="value mono">{stat_model.replace('_', '⋅') if stat_model != '—' else '—'}</div><div class="sub">{top_winner.get('title', '—') if top_winner else '—'}</div></div>
  </div>
  <p class="prose">
    The current peak of <strong>{stat_fit}</strong> iter/s came from one of fifteen completed reps
    across five model configurations. The curve has not plateaued. Each new model release adds
    new strategies — branch predictors, ALU bypasses, M-extension hoists, return-address stacks
    — and the best design changes hands.
  </p>
</section>

<section class="section">
  <div class="eyebrow">Leaderboard</div>
  <h2>Models by peak fitness</h2>
  <div class="wide">
  <table class="bench">
    <caption>Sorted by best single-rep peak fitness · {sum(a.n_total for a in aggs)} reps total</caption>
    <thead>
      <tr>
        <th class="num">#</th>
        <th>Model</th>
        <th class="num">Reps</th>
        <th class="num">Best</th>
        <th class="num">Δ%</th>
        <th class="num">Mean ± std</th>
        <th class="num">Best LUT4</th>
        <th class="num">Best Fmax</th>
        <th class="num">$ cost</th>
      </tr>
    </thead>
    <tbody>{leaderboard_html}
    </tbody>
  </table>
  </div>
  <p class="prose">
    Peak fitness includes reps that finalized with a <code>failed</code> status if their data was
    captured before the failure — fitness 396.13 from <code>kimi-k2_6</code> rep3 is included
    despite the rep crashing on its way out. The mean column excludes failed reps.
    Methodology details on <a href="methodology.html">the methodology page</a>.
  </p>
</section>

<section class="section">
  <div class="eyebrow">Why unbounded</div>
  <h2>SWE-bench saturates. HWE Bench doesn't.</h2>
  <div class="prose">
  <p>
    Most LLM benchmarks have a fixed ceiling. SWE-bench tops out at 100% issue-resolution.
    Multiple-choice evals approach 99%. Once a model lands at the ceiling, every subsequent
    model gets the same score, and the benchmark stops being useful for tracking capability.
  </p>
  <p>
    HWE Bench has no ceiling. The fitness score is <span class="mono">Fmax × IPC</span> —
    operating frequency times instructions-per-cycle — measured on a real FPGA. There is
    no theoretical maximum; better microarchitecture always scores higher. As long as models
    can find new tricks (deeper pipelines, smarter predictors, restructured ALUs), the
    leaderboard keeps moving.
  </p>
  <p>
    Empirically: the current best is <strong>{stat_fit}</strong>
    iter/s, <strong>{stat_delta}</strong> over the V0 baseline core. Each successive batch of
    reps has produced at least one design that beats the prior record. The curve has not
    plateaued.
  </p>
  </div>
</section>

{FOOTER}
"""


def render_methodology() -> str:
    return head("HWE Bench — Methodology", "methodology") + """
<section class="hero-block">
  <div class="hero-eyebrow">Methodology · v1</div>
  <h1>What HWE Bench measures, and how.</h1>
  <p class="hero-lede">
    Each iteration is one hypothesis → one RTL implementation → 45+ formal checks
    → cosim against a Python ISS → 3-seed FPGA placement → CoreMark on Verilator.
    A single failed gate marks the iteration as <em>broken</em>. No surface-metric gaming.
  </p>
</section>

<section class="section">
  <div class="eyebrow">Score</div>
  <h2>Fitness = Fmax × IPC</h2>
  <div class="prose">
  <p>
    The fitness score is <span class="mono">Fmax × IPC</span> measured on the same CoreMark
    workload, in <span class="mono">iter/s</span>.
  </p>
  <ul>
    <li><strong>Fmax</strong> — median operating frequency from 3 nextpnr seeds, placed on a
        Tang Nano 20K (Gowin GW2A-LV18QN88C8/I7).</li>
    <li><strong>IPC</strong> — instructions-per-cycle on CoreMark 2K with iStall+dStall
        backpressure, measured between <span class="mono">start_time</span> and
        <span class="mono">stop_time</span> markers.</li>
  </ul>
  <p>
    The baseline V0 core scores <span class="mono">282.82 iter/s</span> (Fmax = 127 MHz,
    LUT4 = 9,563). Every fitness number on the site is reported against this anchor.
  </p>
  </div>
</section>

<section class="section">
  <div class="eyebrow">Correctness gates</div>
  <h2>Three gates per iteration</h2>
  <dl class="defs">
    <dt>1. Verilator lint</dt>
    <dd>RTL must pass <span class="mono">verilator --lint-only -Wall</span>.
        Caught early; cheap.</dd>

    <dt>2. riscv-formal</dt>
    <dd>45+ <span class="mono">.sby</span> bounded model checks via SymbiYosys + bitwuzla,
        covering RV32IM instruction semantics, register-file forwarding, PC propagation,
        retirement uniqueness, liveness, and traps. The single-issue variant runs against
        <span class="mono">formal/wrapper_si.sv</span>; dual-issue cores run against
        <span class="mono">formal/wrapper.sv</span>. A single failed check fails the iteration.</dd>

    <dt>3. Python ISS cosim</dt>
    <dd>Every retirement of <span class="mono">selftest.elf</span> is diffed field-by-field
        against a Python instruction-set simulator that implements RV32IM by spec. Any
        divergence — wrong register write, missing trap, wrong PC — fails the iteration.
        CoreMark is checked separately via UART-CRC validation (CRCs match the canonical
        EEMBC values).</dd>
  </dl>
  <p class="prose">
    If any gate fails, the iteration is marked <code>broken</code> and counted on the
    leaderboard under <code>broken_by_class</code>. No score is awarded. The model gets a
    new slot on the next round.
  </p>
</section>

<section class="section">
  <div class="eyebrow">Tournament</div>
  <h2>How a single rep runs</h2>
  <div class="prose">
  <p>
    A <em>rep</em> is one independent tournament run with parameters
    <span class="mono">N=15</span> (rounds) and <span class="mono">K=3</span> (slots per round).
    Each round, the model produces 3 hypothesis YAMLs (in parallel, separate agent
    invocations); each hypothesis is independently implemented as RTL, evaluated through the
    three gates above, scored, and committed to the rep's <code>log.jsonl</code>. The
    best-fitness implementation across all 3 slots becomes the new baseline for the next
    round.
  </p>
  <p>
    Three reps per model are run independently. They share no state. Each rep's final fitness
    is published; the model's reported peak is the maximum across reps, and the mean is
    averaged across <em>completed</em> reps (status = <code>done</code>).
  </p>
  </div>
</section>

<section class="section">
  <div class="eyebrow">Reproducibility</div>
  <h2>Re-run the whole bench from a fresh clone</h2>
  <div class="prose">
  <p>
    The benchmark is reproducible from the <a href="https://github.com/FeSens/auto-arch-tournament" class="ext">source repository</a>.
    Every per-iteration artifact is preserved:
  </p>
  <ul>
    <li><code>bench/results.jsonl</code> — one row per rep, structured.</li>
    <li><code>bench/&lt;model&gt;/rep&lt;N&gt;/log.jsonl</code> — per-iteration journal with
        fitness, LUT4, FF, Fmax, IPC, cycles, outcome class, and timestamp.</li>
    <li><code>bench/&lt;model&gt;/rep&lt;N&gt;/agent.log</code> — full model transcript.
        Every <code>read</code>, <code>edit</code>, <code>bash</code>, <code>write</code>
        tool call the agent made.</li>
    <li><code>bench/&lt;model&gt;/rep&lt;N&gt;/summary.json</code> — rolled-up summary with
        cost, wall-clock, and the best-fitness entry's microarch metadata.</li>
  </ul>
  <p>
    The hypothesis-implementation contract is in <code>CLAUDE.md</code> at the repo root.
    The eval contract — wrapper.sv, checks.cfg, the Python ISS, the cosim harness — is in
    <code>formal/</code>, <code>fpga/</code>, and <code>test/cosim/</code>. None of these
    are modifiable by the agent; sandbox rolls back any iteration that touches them.
  </p>
  </div>
</section>

""" + FOOTER


def render_models(aggs: list[ModelAgg]) -> str:
    sections = []
    for a in aggs:
        # Per-rep table
        rep_rows = []
        for r in a.reps:
            status_str = r.status
            if r.status == "failed":
                status_str = '<span class="mono" title="orchestrator exited non-zero; data preserved">failed ⚠</span>'
            rep_rows.append(f"""
      <tr>
        <td>rep{r.rep}</td>
        <td>{status_str}</td>
        <td class="num">{fnum(r.best_fitness, '.2f')}</td>
        <td class="num">{fpct(r.delta_pct)}</td>
        <td class="num">{fcompact(r.best_lut4)}</td>
        <td class="num">{f'{r.best_fmax_mhz:.0f}' if r.best_fmax_mhz else '—'}</td>
        <td class="num">{r.accepted}</td>
        <td class="num">{r.broken}</td>
        <td class="num">{fhours(r.wall_clock_sec)}</td>
        <td class="num">{fmoney(r.total_cost_usd)}</td>
      </tr>""")
        rep_rows_html = "".join(rep_rows)

        # Winners list (across all reps)
        winners_html = []
        for r in a.reps:
            if not r.winners:
                continue
            winners_html.append(f"<h3>rep{r.rep} — winning hypotheses</h3>")
            winners_html.append('<dl class="defs">')
            for w in r.winners:
                title = w.get("title", "—")
                fit = w.get("fitness", "?")
                delta = w.get("delta_pct")
                lut = w.get("lut4")
                fmax = w.get("fmax_mhz")
                rid = w.get("round_id")
                lut_str = fcompact(lut) if lut else "—"
                fmax_str = f"{fmax:.0f} MHz" if isinstance(fmax, (int, float)) else "—"
                delta_str = f"+{delta:.1f}%" if isinstance(delta, (int, float)) else "—"
                winners_html.append(
                    f'<dt>R{rid} · {title}</dt>'
                    f'<dd>fitness <span class="mono">{fit:.2f}</span> '
                    f'(<span class="mono">{delta_str}</span>) · '
                    f'LUT4 <span class="mono">{lut_str}</span> · '
                    f'Fmax <span class="mono">{fmax_str}</span></dd>'
                )
            winners_html.append("</dl>")
        winners_str = "\n".join(winners_html) or "<p>No winning hypotheses recorded.</p>"

        # Broken classes
        broken_str = ", ".join(f'<code>{k}</code>×{v}' for k, v in
                                sorted(a.broken_by_class_total.items(),
                                       key=lambda kv: -kv[1])) or "—"

        sections.append(f"""
<section class="section" id="{a.model}">
  <div class="eyebrow">{a.model}</div>
  <h2>{a.model.replace('_', ' ').replace('-', ' ')}</h2>

  <div class="stats">
    <div class="stat"><div class="label">Best</div><div class="value">{fnum(a.fitness_best)}</div><div class="sub">{fpct(a.delta_best)} vs baseline</div></div>
    <div class="stat"><div class="label">Mean</div><div class="value">{fnum(a.fitness_mean, '.1f')}</div><div class="sub">{fpct(a.delta_mean)} mean Δ</div></div>
    <div class="stat"><div class="label">Reps</div><div class="value">{a.n_done}/{a.n_total}</div><div class="sub">completed / total</div></div>
    <div class="stat"><div class="label">Cost</div><div class="value">{fmoney(a.total_cost_usd)}</div><div class="sub">{fmoney(a.total_cost_usd/a.n_total) if a.n_total else '—'} per rep</div></div>
  </div>

  <div class="wide">
  <table class="bench">
    <caption>per-rep detail</caption>
    <thead>
      <tr>
        <th>Rep</th><th>Status</th>
        <th class="num">Best</th><th class="num">Δ%</th>
        <th class="num">LUT4</th><th class="num">Fmax</th>
        <th class="num">acc</th><th class="num">brk</th>
        <th class="num">Wall</th><th class="num">Cost</th>
      </tr>
    </thead>
    <tbody>{rep_rows_html}
    </tbody>
  </table>
  </div>

  <p class="prose"><strong>Broken classes (all reps combined):</strong> {broken_str}</p>

  <div class="prose">
  {winners_str}
  </div>
</section>
""")

    sections_html = "\n".join(sections)
    return head("HWE Bench — Models", "models") + f"""
<section class="hero-block">
  <div class="hero-eyebrow">Per-model detail</div>
  <h1>What each model actually did.</h1>
  <p class="hero-lede">
    Below: the per-rep outcomes for every model run on HWE Bench so far, plus the
    accepted-improvement hypotheses each rep produced — verbatim titles, fitness,
    LUT4, and Fmax. The hypothesis titles are exactly what the agent wrote.
  </p>
</section>
{sections_html}
""" + FOOTER


def render_data(reps: list[Rep]) -> str:
    rows = []
    for r in sorted(reps, key=lambda x: (x.model, x.rep)):
        log_link = f"https://github.com/FeSens/auto-arch-tournament/blob/main/bench/{r.model}/rep{r.rep}/log.jsonl"
        agent_link = f"https://github.com/FeSens/auto-arch-tournament/blob/main/bench/{r.model}/rep{r.rep}/agent.log"
        summary_link = f"https://github.com/FeSens/auto-arch-tournament/blob/main/bench/{r.model}/rep{r.rep}/summary.json"
        rows.append(f"""
      <tr>
        <td><span class="model-name">{r.model}</span></td>
        <td>rep{r.rep}</td>
        <td>{r.status}</td>
        <td class="num">{r.iterations}</td>
        <td class="num">{fnum(r.best_fitness)}</td>
        <td><a href="{log_link}" class="ext">log.jsonl</a></td>
        <td><a href="{agent_link}" class="ext">agent.log</a></td>
        <td><a href="{summary_link}" class="ext">summary.json</a></td>
      </tr>""")
    rows_html = "".join(rows)

    return head("HWE Bench — Data", "data") + f"""
<section class="hero-block">
  <div class="hero-eyebrow">Raw data</div>
  <h1>Every iteration, every transcript.</h1>
  <p class="hero-lede">
    The full per-iteration journal and agent transcript for every rep are committed to
    the repository. No data is summarized away. Below is the index.
  </p>
</section>

<section class="section">
  <div class="eyebrow">Downloads</div>
  <h2>Aggregate</h2>
  <ul class="prose">
    <li><a href="https://github.com/FeSens/auto-arch-tournament/blob/main/bench/results.jsonl" class="ext"><code>bench/results.jsonl</code></a> — one row per rep, structured. Schema: model, rep, status, final_fitness, best_fitness, baseline_fitness, delta_pct, iterations, accepted, rejected, broken, broken_by_class, wall_clock_sec, total_cost_usd, total_tokens_in/out, best_lut4, best_ff, best_fmax_mhz, best_iterations, best_cycles, best_ipc_coremark.</li>
    <li><a href="https://github.com/FeSens/auto-arch-tournament/blob/main/bench/leaderboard.csv" class="ext"><code>bench/leaderboard.csv</code></a> — per-model aggregate (mean fitness, best, broken counts).</li>
    <li><a href="https://github.com/FeSens/auto-arch-tournament/blob/main/bench/LEADERBOARD.md" class="ext"><code>bench/LEADERBOARD.md</code></a> — human-readable leaderboard with failure-mode breakdowns.</li>
  </ul>
</section>

<section class="section">
  <div class="eyebrow">Per-rep</div>
  <h2>Index of all reps</h2>
  <div class="wide">
  <table class="bench">
    <caption>{len(reps)} reps</caption>
    <thead>
      <tr>
        <th>Model</th><th>Rep</th><th>Status</th>
        <th class="num">Iters</th><th class="num">Best fit</th>
        <th>Log</th><th>Transcript</th><th>Summary</th>
      </tr>
    </thead>
    <tbody>{rows_html}
    </tbody>
  </table>
  </div>
  <p class="prose">
    Each <code>log.jsonl</code> is one row per iteration: hypothesis ID, title, outcome
    (<code>improvement</code> / <code>regression</code> / <code>broken</code>), fitness,
    delta vs baseline, LUT4, FF, Fmax, IPC, cycles, error class if broken, timestamp.
    Each <code>agent.log</code> is the verbatim model transcript: every bash command,
    every file read, every write.
  </p>
</section>
""" + FOOTER


# ── main ──────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    reps = load_reps(args.results, REPO)
    if not reps:
        print(f"no reps in {args.results}")
        return 1
    aggs = aggregate(reps)

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "index.html").write_text(render_index(aggs, reps))
    (args.out / "methodology.html").write_text(render_methodology())
    (args.out / "models.html").write_text(render_models(aggs))
    (args.out / "data.html").write_text(render_data(reps))

    print(f"wrote {args.out}/index.html")
    print(f"wrote {args.out}/methodology.html")
    print(f"wrote {args.out}/models.html")
    print(f"wrote {args.out}/data.html")
    print(f"  ({len(reps)} reps · {len(aggs)} models)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
