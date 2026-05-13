# LLM hardware-development benchmark — leaderboard

Sorted by mean final CoreMark fitness (iter/s) across reps. Each rep is one full tournament run (`make N=… K=… TARGET=bench`) starting from the bench-fixture core.

**Outcome columns** are per-rep means: how many of a rep's iterations landed as `acc`epted improvements / `rej`ected regressions / `brk`oken (didn't compile, didn't pass formal, couldn't place on FPGA, ...). See *Failure modes* below for the broken-class breakdown.

| Model | Reps | Fitness mean ± std | Best | acc | rej | brk | Iters→best | Pass-rate | $ cost | s/iter |
|---|---|---|---|---|---|---|---|---|---|---|
| `gpt-5_5_xhigh` | 3/3 | 468.3 ± 52.8 | 525.0 | 5.7 | 37.7 | 2.0 | 28.3 | 12% | $0.00 | 478 |
| `gpt-5_5_high` | 3/3 | 430.2 ± 23.0 | 461.9 | 6.3 | 36.7 | 3.0 | 31.3 | 14% | $0.00 | 578 |
| `gpt-5_5_medium` | 3/3 | 423.5 ± 11.2 | 431.6 | 5.3 | 32.3 | 7.7 | 36.0 | 12% | $0.00 | 513 |
| `kimi-k2_6` | 1/1 | 282.8 ± 0.0 | 282.8 | 1.0 | 0.0 | 3.0 | 1.0 | 25% | $0.42 | 759 |



## Failure modes

Counts each model's broken iterations grouped by the orchestrator's broken-class label. `formal_failed` = RTL compiled but didn't pass riscv-formal (the suffix is the first failing check). `implementation_compile_failed` = RTL didn't pass Verilator lint. `hypothesis_gen_failed` = agent didn't write the expected YAML at the slot's pre-allocated path. `placement_failed` = nextpnr couldn't place the design on the target FPGA. `make_failed_during_execution` = formal/run_all.sh's `*.sby` glob found zero tasks at tally time (usually an agent wiped the checks dir mid-run; the PID-suffix fix in `formal/run_all.sh` removes the race but the class is still emitted if anything else corrupts the checks dir).

### `gpt-5_5_xhigh`

| Class | Count |
|---|---|
| `cosim_failed` | 5 |
| `formal_failed` | 1 |

### `gpt-5_5_high`

| Class | Count |
|---|---|
| `cosim_failed` | 5 |
| `formal_failed` | 3 |
| `implementation_compile_failed` | 1 |

### `gpt-5_5_medium`

| Class | Count |
|---|---|
| `cosim_failed` | 12 |
| `formal_failed` | 11 |

### `kimi-k2_6`

| Class | Count |
|---|---|
| `formal_failed` | 2 |
| `sandbox_violation` | 1 |

## Per-rep details

Every `(model, rep)` row from `bench/results.jsonl`, before per-model aggregation.

| Model | Rep | Status | Iters | acc | rej | brk | Baseline → Final | Δ% | Best | Wall (m) |
|---|---|---|---|---|---|---|---|---|---|---|
| `gpt-5_5_high` | 1 | done | 46 | 7 | 36 | 3 | 282.8 → 461.9 | 63% | 461.9 | 279.8 |
| `gpt-5_5_high` | 2 | done | 46 | 8 | 34 | 4 | 282.8 → 420.6 | 49% | 420.6 | 713.2 |
| `gpt-5_5_high` | 3 | done | 46 | 4 | 40 | 2 | 282.8 → 408.0 | 44% | 408.0 | 336.4 |
| `gpt-5_5_medium` | 1 | done | 46 | 7 | 32 | 5 | 282.8 → 431.6 | 53% | 431.6 | 346.6 |
| `gpt-5_5_medium` | 2 | done | 46 | 5 | 32 | 9 | 282.8 → 407.6 | 44% | 407.6 | 398.0 |
| `gpt-5_5_medium` | 3 | done | 46 | 4 | 33 | 9 | 282.8 → 431.2 | 52% | 431.2 | 434.5 |
| `gpt-5_5_xhigh` | 1 | done | 46 | 5 | 39 | 2 | 282.8 → 397.8 | 41% | 397.8 | 421.1 |
| `gpt-5_5_xhigh` | 2 | done | 46 | 5 | 38 | 3 | 282.8 → 525.0 | 86% | 525.0 | 384.2 |
| `gpt-5_5_xhigh` | 3 | done | 46 | 7 | 36 | 1 | 282.8 → 482.0 | 70% | 482.0 | 292.9 |
| `kimi-k2_6` | 1 | done | 4 | 1 | 0 | 3 | 282.8 → 282.8 | 0% | 282.8 | 50.6 |

## Winning hypotheses

Each model's accepted-improvement entries (the hypotheses that actually moved the fitness needle), in order. Pulled from the preserved `bench/<model>/rep<N>/log.jsonl`.

### `gpt-5_5_high` rep 1

- **Static backward branch predictor** — fitness 338.7 (+19.7%) _predictor_ R1
- **Add MEM-to-EX load forwarding** — fitness 355.3 (+4.9%) _structural_ R3
- **Isolate M-extension ALU mux** — fitness 366.0 (+3.0%) _micro_opt_ R8
- **Gate static branch target formation** — fitness 420.4 (+14.8%) _predictor_ R9
- **Factor forwarding matches** — fitness 437.7 (+4.1%) _micro_opt_ R12
- **Register memory request metadata** — fitness 461.9 (+5.5%) _structural_ R14

### `gpt-5_5_high` rep 2

- **Add small BTB branch predictor** — fitness 285.5 (+1.0%) _predictor_ R1
- **Gate false load-use stalls** — fitness 290.9 (+1.9%) _micro_opt_ R2
- **Optimize load byte-lane formatter** — fitness 305.2 (+4.9%) _micro_opt_ R3
- **Consolidate multiply datapath** — fitness 313.6 (+2.8%) _micro_opt_ R4
- **Trim BTB tag compare** — fitness 326.0 (+4.0%) _micro_opt_ R6
- **Prune dead pipeline payload** — fitness 341.8 (+4.8%) _micro_opt_ R7
- **Bypass ALU for LSU addresses** — fitness 420.6 (+23.1%) _structural_ R11

### `gpt-5_5_high` rep 3

- **Move DIV/REM off the ALU critical path** — fitness 353.0 (+24.8%) _structural_ R1
- **Case-based MEM byte-lane muxes** — fitness 380.4 (+7.8%) _micro_opt_ R4
- **Lookahead hot-branch predictor** — fitness 408.0 (+7.2%) _predictor_ R6

### `gpt-5_5_medium` rep 1

- **Remove regfile reset fanout** — fitness 316.2 (+11.8%) _micro_opt_ R1
- **Move M extension to multicycle unit** — fitness 356.9 (+12.8%) _structural_ R2
- **Prune dead pipeline metadata** — fitness 397.6 (+11.4%) _micro_opt_ R3
- **Add posted store buffer** — fitness 405.5 (+2.0%) _structural_ R5
- **Register final writeback data** — fitness 422.6 (+4.2%) _structural_ R9
- **Add narrow forwarding sideband** — fitness 431.6 (+2.1%) _structural_ R12

### `gpt-5_5_medium` rep 2

- **Multicycle RV32M arithmetic unit** — fitness 375.7 (+32.9%) _micro_opt_ R1
- **Drop regfile reset fanout** — fitness 383.0 (+1.9%) _micro_opt_ R5
- **Share M-unit multiplier hardware** — fitness 393.7 (+2.8%) _micro_opt_ R8
- **Split RVFI shadow metadata from datapath** — fitness 407.6 (+3.5%) _structural_ R9

### `gpt-5_5_medium` rep 3

- **Gate and share M-extension ALU hardware** — fitness 398.4 (+40.9%) _micro_opt_ R1
- **Precompute PC targets in decode** — fitness 412.1 (+3.4%) _structural_ R5
- **Retire PC-next in MEM** — fitness 431.2 (+4.7%) _structural_ R15

### `gpt-5_5_xhigh` rep 1

- **Decouple slow RV32M ops from EX** — fitness 368.8 (+30.4%) _structural_ R1
- **Retiming slow M finalization** — fitness 380.7 (+3.2%) _micro_opt_ R3
- **Register forwarding selects** — fitness 386.7 (+1.6%) _structural_ R4
- **Registered low-half MUL path** — fitness 397.8 (+2.9%) _structural_ R8

### `gpt-5_5_xhigh` rep 2

- **Iterative divider off ALU critical path** — fitness 400.6 (+41.6%) _micro_opt_ R1
- **Prune dead pipeline control bits** — fitness 427.6 (+6.7%) _micro_opt_ R6
- **Valid-only pipeline payload resets** — fitness 432.2 (+1.1%) _micro_opt_ R7
- **Tiny ifetch replay predictor** — fitness 525.0 (+21.5%) _predictor_ R10

### `gpt-5_5_xhigh` rep 3

- **Move DIV/REM to multicycle EX unit** — fitness 350.2 (+23.8%) _structural_ R1
- **Share MUL hardware in ALU** — fitness 353.5 (+0.9%) _micro_opt_ R2
- **Hazard-only source-use interlock** — fitness 381.0 (+7.8%) _micro_opt_ R4
- **Register writeback payload in MEM/WB** — fitness 407.0 (+6.8%) _structural_ R6
- **Remove regfile reset fanout** — fitness 413.2 (+1.5%) _micro_opt_ R9
- **Stage-local control bundles** — fitness 482.0 (+16.6%) _structural_ R10

Generated by `python -m tools.bench.report`. Source data: `bench/results.jsonl` + per-rep `bench/<model>/rep<N>/log.jsonl`.
