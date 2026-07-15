# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

See `PRD.md` in this directory for the full functional spec (state machine, formulas, menu structure) — it is the primary reference for this project, more so than usual, since this is a from-scratch build against a written spec rather than reverse-engineered from existing code.

## Status

Planned, not yet implemented — see `PLAN.md` for the full design (this section will move to "Implemented" once the code lands). This is the final integrated system (Python), built by porting the patterns proven in the four sibling PoC projects (`ConsoleMVC`, `DataPersistence`, `DataMonitor`, `DummyDataGenerator`) rather than importing them directly — this is a separate repo.

## Commands (per PLAN.md, not yet verified against real code)

Run from this directory (`SampleOrderSystem/`):

- Install dev dependency: `pip install -r requirements-dev.txt` (only `pytest`; runtime has no dependencies)
- Run the app: `python -m sampleordersystem`
- Run all tests: `pytest` (from this directory)

## Architecture (target)

- **MVC layering** per `ConsoleMVC`: Model (Sample, Order entities + state machine), Controller (menu actions, approval/rejection logic, production-queue processing), View (console menus/tables). Keep the order state-transition rules (see `PRD.md` state machine) inside the Model/domain layer, not the Controller, so they can be unit-tested without console I/O.
- **Persistence** per `DataPersistence`: JSON-file-backed repositories for samples and orders, restart-safe.
- **Production queue**: FIFO. The shortfall/yield/time formulas in `PRD.md` (`실 생산량 = ceil(부족분 / 수율)`, `총 생산 시간 = 평균 생산시간 × 실 생산량`) are the parts most worth unit-testing directly, since they're easy to get subtly wrong (rounding direction, which quantity yield applies to).
- **REJECTED is excluded from monitoring** — a rule easy to silently violate when writing the status-count aggregation; the PRD calls it out explicitly.

## When extending

- See `PLAN.md` for the full package layout (`src/sampleordersystem/{model,view,controller,persistence}`) and test plan before adding files, so new code lands in the right layer.
