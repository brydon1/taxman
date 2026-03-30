# TAXMAN — Reimplementation Guide

> A 1970s AI system for legal reasoning about US corporate reorganization tax law.
> Original author: L. Thorne McCarty (Stanford/Rutgers, 1972–76).
> Original language: micro-Planner (a Lisp dialect). **Original source code is not publicly available.**
>
> This guide covers how to reimplement TAXMAN from scratch using the paper's specification.
> See `CLAUDE.md` for the full technical extraction of that specification.

---

## What TAXMAN Does

Given a structured description of a corporate transaction (who transferred what to whom and when),
TAXMAN determines whether the transaction qualifies as a **Type B**, **Type C**, or **Type D**
tax-free reorganization under the US Internal Revenue Code (§368).

It does this by pattern-matching the transaction's factual network against hierarchical legal concept
definitions — working upward from raw facts (stock transfers, asset transfers) through intermediate
concepts (stockholder, control) to conclusory legal labels (B-Reorganization, C-Reorganization, D-Reorganization).

The system is not a rules engine or a decision tree. It is a **semantic network + deductive theorem prover**
operating over a time-indexed database of propositions.

---

## Prerequisites

You do not need to know Lisp. The implementation strategy below uses **Python 3.10+**,
which maps cleanly onto TAXMAN's core abstractions. A Lisp implementation path is included
at the end for completeness.

**Required:**
- Python 3.10+ (pattern matching via `match`/`case` is useful but not mandatory)
- No external libraries are required for a core implementation

**Helpful background:**
- Basic graph data structures (nodes + labeled edges)
- Familiarity with how Prolog or SQL pattern matching works (TAXMAN's `Goal` is similar)
- The IRC §368 reorganization definitions (summarized in `CLAUDE.md` §5)

---

## Mental Model Before You Write Any Code

TAXMAN has three moving parts. Understand these before touching the data structures.

### 1. The Database

A set of **propositions** — tuples of the form `(predicate, arg1, arg2, ...)`.
Think of it as a set of rows in a table where the predicate is the table name:

```
CORPORATION(NEW-JERSEY)
CORPORATION(DELAWARE)
ISSUE(NEW-JERSEY, S1)
STOCK(S1)
COMMON(S1)
PIECE-OF(P1, S1)
NSHARES(P1, 100)
OWN(PHELLIS, P1)
```

Adding a proposition makes it "true". Removing it makes it "false". There is no third state.
Time is handled by appending a time-token as a final argument: `OWN(PHELLIS, P1, T4)`.

### 2. Goals

A query against the database. Variables (written `?X`) unify with any value:

```
Goal: OWN(?X, P1)       → matches OWN(PHELLIS, P1), binds X = PHELLIS
Goal: OWN(PHELLIS, ?X)  → matches OWN(PHELLIS, P1), binds X = P1
Goal: OWN(PHELLIS, P1)  → returns True/False (verification)
```

Chained goals (**Prog**) share variable bindings and backtrack automatically when a later
goal fails. This is identical to Prolog's resolution, or a nested loop with `continue` on miss.

### 3. Theorems

Named rules that define one concept in terms of others. Two directions:

- **Abstract** (bottom-up): given low-level facts, derive a high-level conclusion.
  `STOCKHOLDER(O, C)` is derived by chaining `ISSUE → STOCK → PIECE-OF → OWN`.
- **Expand** (top-down): given a high-level assertion, generate the low-level facts that
  instantiate it. `TRANS(S, X, O, R, T)` expands by erasing `OWN(O, X, T0)` and
  asserting `OWN(R, X, T1)`.

---

## Implementation: Python

### Step 1 — The Database

```python
from collections import defaultdict

class Database:
    def __init__(self):
        # Index by predicate for fast lookup
        self._store: dict[str, list[tuple]] = defaultdict(list)

    def assert_(self, pred: str, *args):
        entry = args
        if entry not in self._store[pred]:
            self._store[pred].append(entry)

    def erase(self, pred: str, *args):
        self._store[pred] = [e for e in self._store[pred] if e != args]

    def query(self, pred: str, *args) -> list[dict]:
        """
        Returns a list of binding dicts for each matching tuple.
        Variable slots are strings starting with '?'.
        Ground slots must match exactly.
        """
        results = []
        for entry in self._store[pred]:
            if len(entry) != len(args):
                continue
            bindings = {}
            match = True
            for pattern, value in zip(args, entry):
                if isinstance(pattern, str) and pattern.startswith('?'):
                    var = pattern[1:]         # strip '?'
                    if var in bindings and bindings[var] != value:
                        match = False; break
                    bindings[var] = value
                elif pattern != value:
                    match = False; break
            if match:
                results.append(bindings)
        return results
```

**Usage:**

```python
db = Database()
db.assert_('CORPORATION', 'NEW-JERSEY')
db.assert_('OWN', 'PHELLIS', 'P1')
db.assert_('OWN', 'PHELLIS', 'P1', 'T4')

db.query('OWN', '?O', '?X')
# → [{'O': 'PHELLIS', 'X': 'P1'}]

db.query('CORPORATION', '?X')
# → [{'X': 'NEW-JERSEY'}]
```

### Step 2 — Prog (Chained Goals with Backtracking)

This is the heart of the system. A Prog is a sequence of goals that must all succeed,
sharing variable bindings, with automatic backtracking.

```python
from typing import Iterator

def apply_bindings(args: tuple, bindings: dict) -> tuple:
    """Replace ?VAR with its bound value if known."""
    return tuple(
        bindings.get(a[1:], a) if isinstance(a, str) and a.startswith('?') else a
        for a in args
    )

def prog(db: Database, goals: list[tuple], bindings: dict = None) -> Iterator[dict]:
    """
    Yields each complete binding dict that satisfies all goals in sequence.
    goals = list of (predicate, arg1, arg2, ...) tuples.
    Backtracks automatically when a later goal fails.
    """
    if bindings is None:
        bindings = {}
    if not goals:
        yield dict(bindings)
        return

    pred, *args = goals[0]
    resolved_args = apply_bindings(tuple(args), bindings)

    for match in db.query(pred, *resolved_args):
        merged = {**bindings, **match}
        # Conflict check: if a variable is already bound to a different value, skip
        conflict = any(
            bindings.get(k) is not None and bindings[k] != v
            for k, v in match.items()
        )
        if not conflict:
            yield from prog(db, goals[1:], merged)
```

**Usage — "Phellis is a stockholder of New-Jersey":**

```python
goals = [
    ('ISSUE', 'NEW-JERSEY', '?S'),
    ('STOCK', '?S'),
    ('PIECE-OF', '?P', '?S'),
    ('OWN', 'PHELLIS', '?P'),
]
for result in prog(db, goals):
    print(result)  # → {'S': 'S1', 'P': 'P1'}
```

### Step 3 — Symbol Generation

TAXMAN frequently needs fresh unique symbols (for newly created stocks, ownership pieces, etc.):

```python
_counter = 0
def gen(prefix='PHE') -> str:
    global _counter
    _counter += 1
    return f'{prefix}{_counter}'

# Usage
s1 = gen()   # → 'PHE1'
p1 = gen()   # → 'PHE2'
```

### Step 4 — Theorem: Abstract (Deduction)

An Abstract theorem defines a concept as a Prog over lower-level facts.
Register theorems in a dict; the `goal_abstract` function checks the DB first,
then tries registered theorems.

```python
# In main/theorems/base.py:
# Theorem registry: concept_name → function(db, *args) → Iterator[dict]
# ABSTRACT_THEOREMS, EXPAND_THEOREMS, goal_abstract, assert_expand are all defined there.

from main.theorems.base import ABSTRACT_THEOREMS, goal_abstract

# Register STOCKHOLDER theorem
def stockholder_abstract(db, owner, corp):
    """Derives (STOCKHOLDER owner corp) from ISSUE/STOCK/PIECE-OF/OWN chain."""
    o = owner  # may be '?O' (variable) or a ground value
    c = corp
    goals = [
        ('ISSUE', c, '?S'),
        ('STOCK', '?S'),
        ('PIECE-OF', '?P', '?S'),
        ('OWN', o, '?P'),
    ]
    for bindings in prog(db, goals):
        yield {'O': bindings.get('O', o), 'C': bindings.get('C', c),
               'S': bindings['S'], 'P': bindings['P']}

ABSTRACT_THEOREMS['STOCKHOLDER'] = stockholder_abstract
```

### Step 5 — Theorem: Expand (State Transition)

An Expand theorem fires when you `assert_expand(concept, ...)`.
It reads the current state, then asserts/erases propositions to produce the next state.

```python
EXPAND_THEOREMS: dict[str, callable] = {}

def assert_expand(db: Database, concept: str, *args):
    if concept in EXPAND_THEOREMS:
        EXPAND_THEOREMS[concept](db, *args)
    else:
        db.assert_(concept, *args)

# Register TRANS theorem
def trans_expand(db, subject, obj, owner, recipient, time):
    """Transfer ownership of obj from owner to recipient at time."""
    db.assert_('TRANS', subject, obj, owner, recipient, time)

    # Find prior state: most recent time before `time`
    prior_owns = db.query('OWN', owner, obj, '?T0')
    if prior_owns:
        t0 = prior_owns[-1]['T0']   # last known state
        db.erase('OWN', owner, obj, t0)

    db.assert_('OWN', recipient, obj, time)

EXPAND_THEOREMS['TRANS'] = trans_expand
```

### Step 6 — Time Management

Each proposition that changes over time carries a time token as its last argument.
States are created as discrete snapshots:

```python
class Timeline:
    """Manages state tokens T0, T1, T2, ..."""
    def __init__(self):
        self._states = ['T0']

    def current(self) -> str:
        return self._states[-1]

    def advance(self) -> str:
        n = len(self._states)
        t = f'T{n}'
        self._states.append(t)
        return t

    def all_states(self) -> list[str]:
        return list(self._states)
```

### Step 7 — Control Theorem

The most complex abstract theorem. Implements the 80% voting + 80% share-count test:

```python
def control_abstract(db, x, corp, time):
    """
    Yields binding if X controls Corp at time T.
    Control = owns ≥80% of voting stock votes AND ≥80% of all other share classes.
    """
    # Confirm X has any stockholding in corp
    if not list(stockholder_abstract(db, x, corp)):
        return

    # Find all stock classes issued by corp at time
    stock_classes = db.query('ISSUE', corp, '?S')

    voting_x, voting_total = 0, 0
    nonvoting_x, nonvoting_total = 0, 0

    for sc in stock_classes:
        s = sc['S']
        if not db.query('STOCK', s):
            continue
        is_voting = bool(db.query('VOTING', s))

        # All pieces of this stock
        pieces = db.query('PIECE-OF', '?P', s)
        for piece in pieces:
            p = piece['P']
            nshares_rows = db.query('NSHARES', p, '?N')
            if not nshares_rows:
                continue
            n = int(nshares_rows[0]['N'])

            if is_voting:
                voting_total += n
                if db.query('OWN', x, p):
                    voting_x += n
            else:
                nonvoting_total += n
                if db.query('OWN', x, p):
                    nonvoting_x += n

    voting_ok = (voting_total == 0) or (voting_x / voting_total >= 0.80)
    nonvoting_ok = (nonvoting_total == 0) or (nonvoting_x / nonvoting_total >= 0.80)

    if voting_ok and nonvoting_ok:
        yield {'X': x, 'C': corp, 'T': time}

ABSTRACT_THEOREMS['CONTROL'] = control_abstract
```

### Step 8 — Loading a Case

Write case descriptions as a Python function that calls `assert_` and `assert_expand`:

```python
def load_phellis_case(db: Database, tl: Timeline):
    # --- Initial state T0 ---
    t0 = tl.current()
    db.assert_('CORPORATION', 'NEW-JERSEY')
    db.assert_('CORPORATION', 'DELAWARE')

    # NJ preferred stock
    db.assert_('ISSUE', 'NEW-JERSEY', 'NJ-PREFERRED', t0)
    db.assert_('STOCK', 'NJ-PREFERRED')
    db.assert_('PREFERRED', 'NJ-PREFERRED')

    # NJ common stock
    db.assert_('ISSUE', 'NEW-JERSEY', 'NJ-COMMON', t0)
    db.assert_('STOCK', 'NJ-COMMON')
    db.assert_('COMMON', 'NJ-COMMON')

    # Phellis owns 250 shares of NJ common
    p_phe = gen()
    db.assert_('PIECE-OF', p_phe, 'NJ-COMMON')
    db.assert_('NSHARES', p_phe, 250)
    db.assert_('OWN', 'PHELLIS', p_phe, t0)

    # --- Event 1: NJ transfers all assets to new Delaware corp ---
    t1 = tl.advance()
    nj_assets = gen()          # symbol for NJ's operating assets
    db.assert_('ASSET', nj_assets)
    assert_expand(db, 'TRANS', 'NEW-JERSEY', nj_assets, 'NEW-JERSEY', 'DELAWARE', t1)

    # --- Event 2: Delaware issues debenture + common stock to NJ ---
    t2 = tl.advance()
    de_deb = gen()             # Delaware debenture stock
    db.assert_('ISSUE', 'DELAWARE', de_deb, t2)
    db.assert_('STOCK', de_deb)
    db.assert_('DEBENTURE', de_deb)
    db.assert_('VOTING', de_deb)   # stipulated for illustration

    de_common = gen()          # Delaware common stock
    db.assert_('ISSUE', 'DELAWARE', de_common, t2)
    db.assert_('STOCK', de_common)
    db.assert_('COMMON', de_common)
    db.assert_('VOTING', de_common)

    # Delaware transfers both to NJ
    piece_deb = gen()
    db.assert_('PIECE-OF', piece_deb, de_deb)
    db.assert_('NSHARES', piece_deb, 59661700)
    assert_expand(db, 'TRANS', 'DELAWARE', piece_deb, 'DELAWARE', 'NEW-JERSEY', t2)

    piece_com = gen()
    db.assert_('PIECE-OF', piece_com, de_common)
    db.assert_('NSHARES', piece_com, 58854200)
    assert_expand(db, 'TRANS', 'DELAWARE', piece_com, 'DELAWARE', 'NEW-JERSEY', t2)

    # --- Event 3: NJ distributes Delaware common to NJ common holders (2-for-1) ---
    t3 = tl.advance()
    # Distribute: for each holder of NJ-COMMON, create a piece and transfer
    for holder_bindings in list(stockholder_abstract(db, '?O', 'NEW-JERSEY')):
        holder = holder_bindings['O']
        piece_in = holder_bindings['P']
        holder_shares = int(db.query('NSHARES', piece_in, '?N')[0]['N'])

        new_piece = gen()
        db.assert_('PIECE-OF', new_piece, de_common)
        db.assert_('NSHARES', new_piece, holder_shares * 2)  # 2-for-1
        assert_expand(db, 'TRANS', 'NEW-JERSEY', new_piece, 'NEW-JERSEY', holder, t3)
```

---

## Running Queries

Once the case is loaded, query the system using `goal_abstract`:

```python
db = Database()
tl = Timeline()
load_phellis_case(db, tl)

# Query: Is there a C-Reorganization?
# (Implement C-REORGANIZATION as an Abstract theorem following CLAUDE.md §5.3)
for result in goal_abstract(db, 'C-REORGANIZATION', '?A', '?C', '?T'):
    print("C-Reorg found:", result)
# Expected: {'A': 'DELAWARE', 'C': 'NEW-JERSEY', 'T': 'T2'}

# Query: Does New Jersey control Delaware at T2?
for result in goal_abstract(db, 'CONTROL', 'NEW-JERSEY', 'DELAWARE', 'T2'):
    print("Control established:", result)
```

---

## File Layout for a Clean Implementation

```
taxman/
├── README.md          ← this file
├── CLAUDE.md          ← full technical spec extracted from the paper
├── AGENTS.md          ← instructions for Claude Code
├── DECISIONS.md       ← architectural decisions log
├── requirements.txt   ← python package dependencies
├── main/
│   ├── __init__.py
│   ├── database.py    ← Database class (assert_, erase, query)
│   ├── prog.py        ← prog() generator, apply_bindings()
│   ├── symbols.py     ← gen(), Timeline
│   ├── theorems/
│   │   ├── __init__.py
│   │   ├── base.py          ← ABSTRACT_THEOREMS, EXPAND_THEOREMS, goal_abstract, assert_expand
│   │   ├── stockholder.py   ← STOCKHOLDER abstract theorem
│   │   ├── control.py       ← CONTROL abstract theorem
│   │   ├── trans.py         ← TRANS expand theorem
│   │   ├── distribute.py    ← DISTRIBUTE expand theorem
│   │   ├── b_reorg.py       ← B-REORGANIZATION abstract theorem
│   │   ├── c_reorg.py       ← C-REORGANIZATION abstract theorem
│   │   └── d_reorg.py       ← D-REORGANIZATION abstract theorem
│   └── cases/
│       ├── phellis.py            ← United States v. Phellis case data
        └── phellis_expected.py   ← ground truth for test assertions
└── tests/
    ├── test_database.py
    ├── test_prog.py
    ├── test_stockholder.py
    ├── test_control.py
    └── test_phellis.py
```

---

## Testing Strategy

Work bottom-up. Each layer must be solid before the next is added.

**Layer 1 — Database primitives:**
- Assert and retrieve a proposition
- Erase removes exactly the right tuple
- Query with all variables ground (verify)
- Query with one unbound variable (search)
- Query with multiple unbound variables (enumerate)
- No match returns empty list, not an error

**Layer 2 — Prog:**
- Single-goal prog behaves like a query
- Two-goal prog shares bindings correctly
- Backtracking: if goal 2 fails, prog retries goal 1 with next match
- A Prog that cannot be satisfied yields nothing (does not raise)

**Layer 3 — Stockholder theorem:**
- Set up the Phellis initial network from `CLAUDE.md` §8
- `goal_abstract(db, 'STOCKHOLDER', 'PHELLIS', 'NEW-JERSEY')` returns one result
- `goal_abstract(db, 'STOCKHOLDER', '?O', 'NEW-JERSEY')` returns all holders

**Layer 4 — Trans expand:**
- Assert a Trans; verify OWN is updated correctly in the DB
- Prior ownership is erased; new ownership is recorded at the new time token
- Partial transfer (Splitpiece) creates two pieces summing to original

**Layer 5 — Control:**
- Build a simple two-corp network where X owns 85% of Y's voting stock
- `CONTROL(X, Y, T)` succeeds
- Change to 75% ownership — `CONTROL` fails

**Layer 6 — B/C/D Reorganization:**
- Load the Phellis case
- B-Reorg with Delaware as acquirer fails (see `CLAUDE.md` §5.5)
- B-Reorg with NJ as acquirer fails (PHE26 is not voting stock)
- C-Reorg with Delaware as acquirer succeeds
- D-Reorg (partial) succeeds

---

## If You Prefer Lisp

Install **SBCL** (Steel Bank Common Lisp) — the closest modern equivalent to the
Lisp underlying micro-Planner:

```bash
# macOS
brew install sbcl

# Ubuntu/Debian
apt install sbcl

# Windows: download installer from sbcl.org
```

Start a REPL:

```bash
sbcl
```

Key Lisp syntax for this codebase:

| Concept | Lisp syntax |
|---|---|
| Define a function | `(defun name (args) body)` |
| Call a function | `(name arg1 arg2)` |
| List literal | `'(a b c)` |
| Association list (dict) | `'((key1 . val1) (key2 . val2))` |
| If expression | `(if condition then else)` |
| Loop | `(loop for x in list do ...)` |
| Print | `(format t "~A~%" value)` |

The Python implementation above maps directly to Lisp: `defaultdict` → `assoc`,
generator functions → recursive functions returning lists, classes → structures or closures.

---

## Known Gaps in the Spec

The paper is explicit about what TAXMAN does not handle. Do not attempt to implement
these without reading `CLAUDE.md` §9 and the discussion in paper §VI first:

- **Creeping acquisitions** — the current search order is incorrect per the paper itself
- **"Solely for voting stock" across time windows** — ambiguous per Treasury Reg §1.368-2(c)
- **§354/355/356 distributions** — required to complete D-Reorg; not representable in current framework
- **Business purpose / continuity of interest / step transaction doctrines** — explicitly out of scope for Part One; reserved for Part Two (which was never published)

---

## Reference

- Full implementation spec: `CLAUDE.md`
- Source paper: McCarty, L.T. (1976). *Reflections on TAXMAN: An Experiment in Artificial Intelligence and Legal Reasoning.* Datenverarbeitung im Recht 5(4).
- micro-Planner reference: Sussman, Winograd & Charniak, *Micro-Planner Reference Manual*, MIT AI Memo No. 203 (1970).
- IRC §368 text: [26 USC §368](https://www.law.cornell.edu/uscode/text/26/368)