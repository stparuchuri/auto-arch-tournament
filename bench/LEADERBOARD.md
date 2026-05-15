# LLM hardware-development benchmark — leaderboard

Sorted by mean final CoreMark fitness (iter/s) across reps. Each rep is one full tournament run (`make N=… K=… TARGET=bench`) starting from the bench-fixture core.

**Outcome columns** are per-rep means: how many of a rep's iterations landed as `acc`epted improvements / `rej`ected regressions / `brk`oken (didn't compile, didn't pass formal, couldn't place on FPGA, ...). See *Failure modes* below for the broken-class breakdown.

Best LUT4 / Fmax / IPC are the FPGA-side detail of the **best rep's best entry** (the one whose fitness equals `Best`). They surface the area-vs-frequency tradeoff each model picked. Baseline for reference: LUT4 = 9563, Fmax = 127 MHz, IPC ≈ 0.79.

| Model | Reps | Fitness mean ± std | Best | LUT4 | Fmax MHz | IPC | acc | rej | brk | Iters→best | Pass-rate | $ cost | s/iter |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `gpt-5_5_xhigh` | 3/3 | 468.3 ± 52.8 | 525.0 | 5453 | 220.2 | 2.38 | 5.7 | 37.7 | 2.0 | 28.3 | 12% | $0.00 | 478 |
| `gpt-5_5_high` | 3/3 | 430.2 ± 23.0 | 461.9 | 9807 | 187.3 | 2.47 | 6.3 | 36.7 | 3.0 | 31.3 | 14% | $0.00 | 578 |
| `gpt-5_5_medium` | 3/3 | 423.5 ± 11.2 | 431.6 | 7803 | 200.6 | 2.15 | 5.3 | 32.3 | 7.7 | 36.0 | 12% | $0.00 | 513 |
| `kimi-k2_6` | 2/3 | 339.5 ± 8.3 | 347.8 | 10254 | 146.2 | 2.38 | 3.3 | 16.7 | 21.0 | 11.5 | 7% | $28.44 | 690 |
| `gemini-3_1-pro` | 3/3 | 339.4 ± 12.6 | 354.7 | 10242 | 149.7 | 2.37 | 3.0 | 12.7 | 30.3 | 21.0 | 7% | $83.53 | 492 |



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
| `hypothesis_gen_failed` | 45 |
| `formal_failed` | 8 |
| `cosim_failed` | 6 |
| `implementation_compile_failed` | 2 |
| `schema_error` | 2 |

### `gemini-3_1-pro`

| Class | Count |
|---|---|
| `hypothesis_gen_failed` | 68 |
| `sandbox_violation` | 9 |
| `formal_failed` | 6 |
| `cosim_failed` | 5 |
| `implementation_compile_failed` | 3 |

## Per-rep details

Every `(model, rep)` row from `bench/results.jsonl`, before per-model aggregation.

| Model | Rep | Status | Iters | acc | rej | brk | Baseline → Final | Δ% | Best | LUT4 | Fmax MHz | IPC | Wall (m) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `gemini-3_1-pro` | 1 | done | 46 | 2 | 13 | 31 | 282.8 → 354.7 | 25% | 354.7 | 10242 | 149.7 | 2.37 | 335.4 |
| `gemini-3_1-pro` | 2 | done | 46 | 3 | 14 | 29 | 282.8 → 339.6 | 20% | 339.6 | 11068 | 142.4 | 2.39 | 438.8 |
| `gemini-3_1-pro` | 3 | done | 46 | 4 | 11 | 31 | 282.8 → 323.9 | 15% | 323.9 | 11836 | 135.8 | 2.39 | 357.2 |
| `gpt-5_5_high` | 1 | done | 46 | 7 | 36 | 3 | 282.8 → 461.9 | 63% | 461.9 | 9807 | 187.3 | 2.47 | 279.8 |
| `gpt-5_5_high` | 2 | done | 46 | 8 | 34 | 4 | 282.8 → 420.6 | 49% | 420.6 | 11953 | 178.1 | 2.36 | 713.2 |
| `gpt-5_5_high` | 3 | done | 46 | 4 | 40 | 2 | 282.8 → 408.0 | 44% | 408.0 | 5637 | 175.8 | 2.32 | 336.4 |
| `gpt-5_5_medium` | 1 | done | 46 | 7 | 32 | 5 | 282.8 → 431.6 | 53% | 431.6 | 7803 | 200.6 | 2.15 | 346.6 |
| `gpt-5_5_medium` | 2 | done | 46 | 5 | 32 | 9 | 282.8 → 407.6 | 44% | 407.6 | 7358 | 186.9 | 2.18 | 398.0 |
| `gpt-5_5_medium` | 3 | done | 46 | 4 | 33 | 9 | 282.8 → 431.2 | 52% | 431.2 | 9997 | 193.7 | 2.23 | 434.5 |
| `gpt-5_5_xhigh` | 1 | done | 46 | 5 | 39 | 2 | 282.8 → 397.8 | 41% | 397.8 | 6052 | 182.4 | 2.18 | 421.1 |
| `gpt-5_5_xhigh` | 2 | done | 46 | 5 | 38 | 3 | 282.8 → 525.0 | 86% | 525.0 | 5453 | 220.2 | 2.38 | 384.2 |
| `gpt-5_5_xhigh` | 3 | done | 46 | 7 | 36 | 1 | 282.8 → 482.0 | 70% | 482.0 | 3164 | 216.5 | 2.23 | 292.9 |
| `kimi-k2_6` | 1 | done | 46 | 3 | 20 | 23 | 282.8 → 347.8 | 23% | 347.8 | 10254 | 146.2 | 2.38 | 542.5 |
| `kimi-k2_6` | 2 | done | 46 | 3 | 17 | 26 | 282.8 → 331.2 | 17% | 331.2 | 10038 | 140.6 | 2.36 | 515.6 |
| `kimi-k2_6` | 3 | failed | 31 | 4 | 13 | 14 | 282.8 → 396.1 | 40% | 396.1 | 9927 | 165.5 | 2.39 | 531.2 |

## Winning hypotheses

Each model's accepted-improvement entries (the hypotheses that actually moved the fitness needle), in order. Pulled from the preserved `bench/<model>/rep<N>/log.jsonl`.

### `gemini-3_1-pro` rep 1

- **1-Cycle 64-entry BTB in IF Stage with Fast Redirect** — fitness 354.7 (+25.4%) _predictor_ R5 — LUT4 10242, 149.7 MHz

### `gemini-3_1-pro` rep 2

- **16-entry BTB/BHT predictor in IF stage** — fitness 323.9 (+14.5%) _predictor_ R4 — LUT4 10334, 137.2 MHz
- **128-entry BTB + 8-entry RAS** — fitness 339.6 (+4.8%) _predictor_ R5 — LUT4 11068, 142.4 MHz

### `gemini-3_1-pro` rep 3

- **IF-stage Static BTFN and JAL Predictor** — fitness 282.9 (+0.0%) _structural_ R5 — LUT4 9995, 120.5 MHz
- **BHT and RAS for frontend branch prediction** — fitness 321.7 (+13.7%) _structural_ R9 — LUT4 10964, 134.8 MHz
- **GShare Predictor with 256-entry BHT and 8-bit GHR** — fitness 323.9 (+0.7%) _predictor_ R10 — LUT4 11836, 135.8 MHz

### `gpt-5_5_high` rep 1

- **Static backward branch predictor** — fitness 338.7 (+19.7%) _predictor_ R1 — LUT4 9995, 144.3 MHz
- **Add MEM-to-EX load forwarding** — fitness 355.3 (+4.9%) _structural_ R3 — LUT4 10183, 144.1 MHz
- **Isolate M-extension ALU mux** — fitness 366.0 (+3.0%) _micro_opt_ R8 — LUT4 10063, 148.4 MHz
- **Gate static branch target formation** — fitness 420.4 (+14.8%) _predictor_ R9 — LUT4 9895, 170.5 MHz
- **Factor forwarding matches** — fitness 437.7 (+4.1%) _micro_opt_ R12 — LUT4 10101, 177.5 MHz
- **Register memory request metadata** — fitness 461.9 (+5.5%) _structural_ R14 — LUT4 9807, 187.3 MHz

### `gpt-5_5_high` rep 2

- **Add small BTB branch predictor** — fitness 285.5 (+1.0%) _predictor_ R1 — LUT4 12128, 120.9 MHz
- **Gate false load-use stalls** — fitness 290.9 (+1.9%) _micro_opt_ R2 — LUT4 12353, 123.2 MHz
- **Optimize load byte-lane formatter** — fitness 305.2 (+4.9%) _micro_opt_ R3 — LUT4 12355, 129.2 MHz
- **Consolidate multiply datapath** — fitness 313.6 (+2.8%) _micro_opt_ R4 — LUT4 12557, 132.8 MHz
- **Trim BTB tag compare** — fitness 326.0 (+4.0%) _micro_opt_ R6 — LUT4 12046, 138.0 MHz
- **Prune dead pipeline payload** — fitness 341.8 (+4.8%) _micro_opt_ R7 — LUT4 12206, 144.7 MHz
- **Bypass ALU for LSU addresses** — fitness 420.6 (+23.1%) _structural_ R11 — LUT4 11953, 178.1 MHz

### `gpt-5_5_high` rep 3

- **Move DIV/REM off the ALU critical path** — fitness 353.0 (+24.8%) _structural_ R1 — LUT4 5472, 158.6 MHz
- **Case-based MEM byte-lane muxes** — fitness 380.4 (+7.8%) _micro_opt_ R4 — LUT4 5458, 170.9 MHz
- **Lookahead hot-branch predictor** — fitness 408.0 (+7.2%) _predictor_ R6 — LUT4 5637, 175.8 MHz

### `gpt-5_5_medium` rep 1

- **Remove regfile reset fanout** — fitness 316.2 (+11.8%) _micro_opt_ R1 — LUT4 7990, 142.0 MHz
- **Move M extension to multicycle unit** — fitness 356.9 (+12.8%) _structural_ R2 — LUT4 7480, 167.0 MHz
- **Prune dead pipeline metadata** — fitness 397.6 (+11.4%) _micro_opt_ R3 — LUT4 7727, 186.1 MHz
- **Add posted store buffer** — fitness 405.5 (+2.0%) _structural_ R5 — LUT4 7373, 188.5 MHz
- **Register final writeback data** — fitness 422.6 (+4.2%) _structural_ R9 — LUT4 7042, 196.4 MHz
- **Add narrow forwarding sideband** — fitness 431.6 (+2.1%) _structural_ R12 — LUT4 7803, 200.6 MHz

### `gpt-5_5_medium` rep 2

- **Multicycle RV32M arithmetic unit** — fitness 375.7 (+32.9%) _micro_opt_ R1 — LUT4 9711, 172.3 MHz
- **Drop regfile reset fanout** — fitness 383.0 (+1.9%) _micro_opt_ R5 — LUT4 7608, 175.6 MHz
- **Share M-unit multiplier hardware** — fitness 393.7 (+2.8%) _micro_opt_ R8 — LUT4 7548, 180.5 MHz
- **Split RVFI shadow metadata from datapath** — fitness 407.6 (+3.5%) _structural_ R9 — LUT4 7358, 186.9 MHz

### `gpt-5_5_medium` rep 3

- **Gate and share M-extension ALU hardware** — fitness 398.4 (+40.9%) _micro_opt_ R1 — LUT4 9829, 178.9 MHz
- **Precompute PC targets in decode** — fitness 412.1 (+3.4%) _structural_ R5 — LUT4 10159, 185.1 MHz
- **Retire PC-next in MEM** — fitness 431.2 (+4.7%) _structural_ R15 — LUT4 9997, 193.7 MHz

### `gpt-5_5_xhigh` rep 1

- **Decouple slow RV32M ops from EX** — fitness 368.8 (+30.4%) _structural_ R1 — LUT4 5962, 165.7 MHz
- **Retiming slow M finalization** — fitness 380.7 (+3.2%) _micro_opt_ R3 — LUT4 6010, 171.0 MHz
- **Register forwarding selects** — fitness 386.7 (+1.6%) _structural_ R4 — LUT4 6006, 173.7 MHz
- **Registered low-half MUL path** — fitness 397.8 (+2.9%) _structural_ R8 — LUT4 6052, 182.4 MHz

### `gpt-5_5_xhigh` rep 2

- **Iterative divider off ALU critical path** — fitness 400.6 (+41.6%) _micro_opt_ R1 — LUT4 5455, 179.9 MHz
- **Prune dead pipeline control bits** — fitness 427.6 (+6.7%) _micro_opt_ R6 — LUT4 5446, 192.1 MHz
- **Valid-only pipeline payload resets** — fitness 432.2 (+1.1%) _micro_opt_ R7 — LUT4 5434, 194.1 MHz
- **Tiny ifetch replay predictor** — fitness 525.0 (+21.5%) _predictor_ R10 — LUT4 5453, 220.2 MHz

### `gpt-5_5_xhigh` rep 3

- **Move DIV/REM to multicycle EX unit** — fitness 350.2 (+23.8%) _structural_ R1 — LUT4 5592, 157.3 MHz
- **Share MUL hardware in ALU** — fitness 353.5 (+0.9%) _micro_opt_ R2 — LUT4 5627, 158.8 MHz
- **Hazard-only source-use interlock** — fitness 381.0 (+7.8%) _micro_opt_ R4 — LUT4 5642, 171.1 MHz
- **Register writeback payload in MEM/WB** — fitness 407.0 (+6.8%) _structural_ R6 — LUT4 5653, 182.8 MHz
- **Remove regfile reset fanout** — fitness 413.2 (+1.5%) _micro_opt_ R9 — LUT4 3181, 185.6 MHz
- **Stage-local control bundles** — fitness 482.0 (+16.6%) _structural_ R10 — LUT4 3164, 216.5 MHz

### `kimi-k2_6` rep 1

- **Add static branch predictor (backward-taken, JAL-always-taken)** — fitness 324.1 (+14.6%) _structural_ R1 — LUT4 10189, 138.1 MHz
- **Add 32-entry 2-bit BHT for forward branch direction prediction** — fitness 347.8 (+7.3%) _predictor_ R4 — LUT4 10254, 146.2 MHz

### `kimi-k2_6` rep 2

- **IF-stage static predictor: backward branches and JAL always taken** — fitness 316.9 (+12.1%) _predictor_ R1 — LUT4 10559, 135.0 MHz
- **4-entry Return Address Stack for JALR returns** — fitness 331.2 (+4.5%) _predictor_ R3 — LUT4 10038, 140.6 MHz

### `kimi-k2_6` rep 3

- **Guard ALU multipliers off critical path for non-M ops** — fitness 315.2 (+11.5%) _micro_opt_ R1 — LUT4 10217, 141.6 MHz
- **8-entry direct-mapped instruction cache in IF to absorb imem stalls** — fitness 334.4 (+6.1%) _structural_ R5 — LUT4 9980, 139.7 MHz
- **Split ALU into fast and M-extension paths with final 2:1 mux** — fitness 396.1 (+18.5%) _micro_opt_ R8 — LUT4 9927, 165.5 MHz

Generated by `python -m tools.bench.report`. Source data: `bench/results.jsonl` + per-rep `bench/<model>/rep<N>/log.jsonl`.
