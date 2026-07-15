# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

See `PRD.md` in this directory for the full functional spec (state machine, formulas, menu structure) — it is the primary reference for this project, more so than usual, since this is a from-scratch build against a written spec rather than reverse-engineered from existing code.

## Status

Implemented (all 8 phases of `PLAN.md`): sample management, order intake/approval/rejection, the FIFO production queue with real-time-gated automatic completion, shipping, and monitoring are all in place under `src/sampleordersystem/{model,view,controller,persistence}`, backed by a full pytest suite. Built by porting the patterns proven in the four sibling PoC projects (`ConsoleMVC`, `DataPersistence`, `DataMonitor`, `DummyDataGenerator`) rather than importing them directly — this is a separate repo (verified standalone: no cross-project imports).

## Commands

Run from this directory (`SampleOrderSystem/`):

- Install dev dependency: `pip install -r requirements-dev.txt` (only `pytest`; runtime has no dependencies)
- Run the app: `PYTHONPATH=src PYTHONIOENCODING=utf-8 python -m sampleordersystem` (bash) or `$env:PYTHONPATH="src"; $env:PYTHONIOENCODING="utf-8"; python -m sampleordersystem` (PowerShell) — `pyproject.toml`'s `pythonpath` setting only applies to `pytest`, not to running the module directly.
- Run all tests: `pytest` (from this directory — no manual `PYTHONPATH` needed for tests, per `pyproject.toml`)

## Architecture

- **MVC layering** per `ConsoleMVC`: Model (`Sample`/`Order` entities + state machine + `ProductionQueue`), Controller (`sample_controller`/`order_controller`/`production_controller`/`shipping_controller`/`monitoring_controller`), View (`menus.py`/`tables.py`, pure string rendering). Order state-transition rules live in `model/order.py`, not the controllers, so they're unit-tested without console I/O.
- **Persistence** per `DataPersistence`: JSON-file-backed `JsonRepository` for samples and orders, restart-safe (`data/samples.json`/`data/orders.json`, auto-created on first write).
- **Production queue**: FIFO, single production line (only the front item's timer is running at any moment). The shortfall/yield/time formulas (`실 생산량 = ceil(부족분 / 수율)`, `총 생산 시간 = 평균 생산시간 × 실 생산량`) live in `model/production_queue.py`. Completion is real-time-gated using wall-clock time (`time.time`, not `time.monotonic`, specifically so a production item's progress survives a process restart) and happens automatically (`ProductionController.drain_ready_items()`, called both at the top of its own menu loop and at the top of `__main__.py`'s main loop — there's no background thread, so completion only fires when control returns to one of these two poll points). `rebuild_production_queue()` reconstructs the in-memory queue from any orders persisted as `PRODUCING` at startup, using each order's persisted `production_started_at` timestamp when present (best-effort fallback to "start now" for legacy records without it).
- **REJECTED is excluded from monitoring** — the status-count screen only iterates a fixed `RESERVED`/`CONFIRMED`/`PRODUCING`/`RELEASED` tuple, so REJECTED can never appear there regardless of what the underlying data contains.
- Console UX: every submenu's "back" option reads "뒤로가기" (returns to the main menu); only the main menu itself has a "종료" option that exits the whole application. `EOFError` (stdin exhausted) is caught once at the top of `__main__.py`'s main loop for a clean shutdown instead of a raw traceback.

## When extending

- See `PLAN.md` for the full package layout (`src/sampleordersystem/{model,view,controller,persistence}`) and test plan before adding files, so new code lands in the right layer.
