# TAXMAN

A Python reimplementation of McCarty's 1976 AI system for legal reasoning about US corporate
reorganization tax law.

> McCarty, L. Thorne. "Reflections on TAXMAN: An Experiment in Artificial Intelligence and
> Legal Reasoning." *Datenverarbeitung im Recht* Band 5, Heft 4/1976.
> Original language: micro-Planner (Lisp). Original source is not publicly available.

---

## What It Does

Given a structured description of a corporate transaction — who transferred what to whom and
when — TAXMAN determines whether the transaction qualifies as a **Type B**, **Type C**, or
**Type D** tax-free reorganization under IRC §368.

It works by pattern-matching a factual network of propositions against hierarchical legal concept
definitions, reasoning upward from raw facts (stock transfers, asset transfers) through
intermediate concepts (stockholder, control) to conclusory legal labels. This is not a rules
engine or a decision tree. It is a semantic network with a deductive theorem prover operating
over a time-indexed database of propositions.

---

## Status

The system is under active development. Completed layers:

| Layer | Module | Status |
|---|---|---|
| Database (assert/erase/query) | `main/database.py` | Done |
| Symbol generation, timeline | `main/symbols.py` | Done |
| Chained goals with backtracking | `main/prog.py` | Done |
| STOCKHOLDER theorem | `main/theorems/stockholder.py` | Done |
| CONTROL theorem | `main/theorems/control.py` | Done |
| TRANS expand theorem | `main/theorems/trans.py` | Done |
| DISTRIBUTE expand theorem | `main/theorems/distribute.py` | Done |
| B-REORGANIZATION theorem | `main/theorems/b_reorg.py` | Done |
| C-REORGANIZATION theorem | `main/theorems/c_reorg.py` | In progress |
| D-REORGANIZATION theorem | `main/theorems/d_reorg.py` | In progress |
| Phellis case end-to-end | `main/cases/phellis.py` | Not started |

See `SESSIONS.md` for the development plan.

---

## Requirements

- Python 3.10+
- No external runtime dependencies
- `pytest` for running tests: `pip install pytest`

---

## Setup

```bash
git clone <repo>
cd taxman
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install pytest
```

---

## Running Tests

```bash
pytest tests/ -v
```

Tests are organized bottom-up by layer. All passing tests represent fully implemented and
verified behavior.

---

## Using the System

Interact with TAXMAN through its database and theorem layers. The entry point is
`goal_abstract`, which derives legal conclusions from facts.

### 1. Build a fact database

```python
from main.database import Database
from main.symbols import gen, Timeline
from main.theorems.base import assert_expand, goal_abstract
import main.theorems.stockholder
import main.theorems.control

db = Database()

# Declare corporations
db.assert_('CORPORATION', 'ACME')
db.assert_('CORPORATION', 'TARGET')

# TARGET issues common voting stock
db.assert_('ISSUE', 'TARGET', 'TARGET-COMMON')
db.assert_('STOCK', 'TARGET-COMMON')
db.assert_('COMMON', 'TARGET-COMMON')
db.assert_('VOTING', 'TARGET-COMMON')

# Alice owns 90 shares out of 100 total
alice_piece = gen()
db.assert_('PIECE-OF', alice_piece, 'TARGET-COMMON')
db.assert_('NSHARES', alice_piece, 90)
db.assert_('OWN', 'ALICE', alice_piece, 'T0')

other_piece = gen()
db.assert_('PIECE-OF', other_piece, 'TARGET-COMMON')
db.assert_('NSHARES', other_piece, 10)
db.assert_('OWN', 'OTHER', other_piece, 'T0')
```

### 2. Query for legal conclusions

```python
# Does Alice control TARGET?
results = list(goal_abstract(db, 'CONTROL', 'ALICE', 'TARGET', 'T0'))
print(results)  # [{'X': 'ALICE', 'C': 'TARGET', 'T': 'T0'}] — yes

# Who are the stockholders of TARGET?
for r in goal_abstract(db, 'STOCKHOLDER', '?O', 'TARGET'):
    print(r['O'])  # ALICE, OTHER
```

### 3. Record a transaction

```python
tl = Timeline()
t1 = tl.advance()

# Transfer Alice's piece to ACME
assert_expand(db, 'TRANS', 'ALICE', alice_piece, 'ALICE', 'ACME', t1)

# Verify ownership changed
print(db.query('OWN', 'ACME', alice_piece, t1))  # [{}] — yes
print(db.query('OWN', 'ALICE', alice_piece, 'T0'))  # [] — erased
```

### 4. Check for a reorganization

Once B/C/D reorganization theorems are complete (see status table above):

```python
import main.theorems.b_reorg

for r in goal_abstract(db, 'B-REORGANIZATION', '?A', '?C', '?T'):
    print(f"B-Reorg: acquirer={r['A']}, acquired={r['C']}, time={r['T']}")
```

---

## Conventions

- All predicates and entity names: uppercase strings (`'CORPORATION'`, `'NEW-JERSEY'`)
- Query variables: strings prefixed with `?` (`'?X'`, `'?CORP'`)
- Time tokens: strings prefixed with `T` (`'T0'`, `'T1'`)
- Fresh symbols from `gen()`: prefixed `PHE` (`'PHE1'`, `'PHE2'`, ...)
- `NSHARES` values: Python `int`, not `str`
- `ISSUE` is always 2-argument `(issuer, stock)` — no time token

---

## Key Concepts

### The Database

A set of propositions of the form `(predicate, arg1, arg2, ...)`. Adding a proposition
makes it true; removing it makes it false. Time is handled by appending a time token as
the last argument.

### Goals

A query against the database. Variables unify with any matching value and bind across a
chain of goals (`prog`). If a later goal in a chain fails, the system backtracks and tries
the next match from an earlier goal — identical to Prolog resolution.

### Theorems

Named rules that define one concept in terms of others. **Abstract** theorems reason
bottom-up from facts to conclusions (e.g. `STOCKHOLDER` from `ISSUE/STOCK/PIECE-OF/OWN`).
**Expand** theorems reason top-down, generating DB updates from a high-level event
(e.g. `TRANS` updates `OWN` records). Theorem modules register themselves on import.

---

## Known Gaps

The original paper is explicit about what TAXMAN does not handle.
See `CLAUDE.md` §9 for the full discussion.

| Capability | Status |
|---|---|
| Classify B, C, D reorganizations | In progress |
| Continuity-of-interest doctrine | Not implemented |
| Business purpose doctrine | Not implemented |
| Step transaction doctrine | Not implemented |
| Nonrecognition rules (§354/361) | Not implemented |
| Basis rules (§358/362) | Not implemented |
| Distribution rules (§354/355) | Not implemented |
| "Substantially all properties" test | Partial only |
| Creeping acquisitions (time-bounded) | Incorrect per paper |
| Natural language I/O | Not implemented |

---

## Reference

- Full technical spec (data model, theorem definitions, the Phellis case): `CLAUDE.md`
- Architecture and coding conventions: `AGENTS.md`
- Design decisions log: `DECISIONS.md`
- Layer-by-layer testing strategy: `tests/TESTING.md`
- Source paper: McCarty (1976), see `resources/`
- IRC §368: https://www.law.cornell.edu/uscode/text/26/368
