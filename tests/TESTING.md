# Testing Strategy

Tests are organized bottom-up by layer. Each layer must pass completely before
building the next. Run all tests with:

```bash
pytest tests/ -v
```

---

## Layer 1 — Database primitives (`test_database.py`)

- Assert and retrieve a proposition
- Erase removes exactly the right tuple
- Query with all variables ground (verification — returns `[{}]` on match)
- Query with one unbound variable (search — returns one binding dict per match)
- Query with multiple unbound variables (enumerate)
- Arity mismatch never matches (`OWN(A, B)` does not match `OWN(A, B, T)`)
- No match returns empty list, not an error
- `assert_` is idempotent — duplicate assertions do not create duplicate entries

## Layer 2 — Prog (`test_prog.py`)

- Single-goal prog behaves like a direct query
- Two-goal prog shares bindings correctly across goals
- Backtracking: if goal 2 fails, prog retries goal 1 with the next match
- A prog that cannot be satisfied yields nothing (does not raise)
- `apply_bindings` substitutes bound variables and leaves unbound ones as-is

## Layer 3 — Stockholder theorem (`test_stockholder.py`)

- Set up the Phellis initial network from `CLAUDE.md` §8
- `goal_abstract(db, 'STOCKHOLDER', 'PHELLIS', 'NEW-JERSEY')` returns one result
- `goal_abstract(db, 'STOCKHOLDER', '?O', 'NEW-JERSEY')` returns all holders
- A non-holder returns no results (does not raise)

## Layer 4 — Control theorem (`test_control.py`)

- Build a two-corp network where X owns 85% of Y's voting stock
- `CONTROL(X, Y, T)` succeeds
- Change to 75% — `CONTROL` fails
- Non-voting shares alone do not satisfy the voting test
- Both the voting test and the non-voting test must pass for control

## Layer 5 — Trans expand theorem (`test_trans.py`)

- `assert_expand(db, 'TRANS', ...)` erases the prior `OWN` and asserts a new one
- The `TRANS` proposition itself is recorded in the DB
- Partial transfer (Splitpiece): two resulting pieces sum to the original share count

## Layer 6 — Distribute expand theorem (`test_distribute.py`)

- Each recipient in the target class receives a new piece
- Share counts follow the distribution rule (N-for-1 or pro-rata)
- The source piece is split and transferred correctly

## Layer 7 — B-Reorganization (`test_b_reorg.py`)

- Load the Phellis case
- B-Reorg with Delaware as acquirer fails — Delaware never acquires NJ stock
  (failure point: `CONTROL(Delaware, New-Jersey, T)` finds no match)
- B-Reorg with NJ as acquirer fails — PHE26 is an asset, not voting stock
  ("solely for voting stock" constraint violated)

## Layer 8 — C/D-Reorganization (`test_c_reorg.py`, `test_d_reorg.py`)

- C-Reorg with Delaware as acquirer succeeds (PHE26 = substantially all NJ properties;
  PHE31 = Delaware common stock, stipulated voting)
- D-Reorg (partial) finds the asset transfer and subsequent NJ control of Delaware

## Layer 9 — Phellis end-to-end (`test_phellis.py`)

- Load `main/cases/phellis.py` in full
- Assert results against `main/cases/phellis_expected.json`
- Covers all four queries from `CLAUDE.md` §5.5
