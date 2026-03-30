---
name: project_taxman_state
description: Current implementation state of the TAXMAN reimplementation in Python — what's done, what's next, and known doc inconsistencies
type: project
---

## Completed layers (as of 2026-03-20)

- database.py — Database class (assert_, erase, query, all_entries, all_predicates)
- symbols.py — gen(), reset_gen(), Timeline
- prog.py — prog() generator, apply_bindings()
- theorems/base.py — ABSTRACT_THEOREMS, EXPAND_THEOREMS, goal_abstract, assert_expand
- theorems/stockholder.py — STOCKHOLDER abstract theorem
- theorems/control.py — CONTROL abstract theorem (≥80% voting + non-voting)
- theorems/trans.py — TRANS and SPLITPIECE expand theorems
- theorems/distribute.py — DISTRIBUTE expand theorem (N-FOR-ONE and PRORATA rules)

## Next up

- Session 6: b_reorg.py (B-REORGANIZATION abstract theorem)
- Session 7: c_reorg.py (C-REORGANIZATION abstract theorem)
- Session 8: d_reorg.py (D-REORGANIZATION abstract theorem, partial per §9 of spec)
- Session 9: main/cases/phellis.py + end-to-end test_phellis.py

## Known doc inconsistencies

- phellis_expected.py has .py extension but is JSON — load with json.load(), not import
- README.md lines 146-148 show a 2-arg OWN query returning mixed-arity results — wrong, arity matching is strict
- SESSIONS.md Session 3 says "no separate theorems/base.py — registries live in prog.py" — this is outdated; base.py was created in Session 3/4

## Key conventions (from AGENTS.md + DECISIONS.md)

- ISSUE always 2-arg (issuer, stock) — no time token
- NSHARES values must be Python int (control.py does arithmetic)
- Distribution rule pre-asserted as (DISTRIBUTION-RULE obj 'N-FOR-ONE' n source_stock) or (DISTRIBUTION-RULE obj 'PRORATA' source_stock) before calling DISTRIBUTE
- SPLITPIECE requires (NSHARES new_piece n) to be pre-asserted before calling
