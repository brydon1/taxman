# AGENTS.md

## Project
TAXMAN reimplementation in Python. See CLAUDE.md for full spec, README.md for architecture.

## How to run tests
pytest tests/ -v

## Conventions
- All DB propositions: uppercase strings, e.g. 'CORPORATION', 'NEW-JERSEY'
- Variables in queries: strings prefixed with '?', e.g. '?X', '?CORP'
- Time tokens: strings prefixed with 'T', e.g. 'T0', 'T1'
- Fresh symbols: generated via gen() in symbols.py, prefixed 'PHE'
- Every theorem registers itself in ABSTRACT_THEOREMS or EXPAND_THEOREMS dicts in **theorems/base.py**
- NSHARES values must be asserted as Python int, not str — control.py does arithmetic on them
- ISSUE is always asserted as 2-arg (issuer, stock) with no time token — both STOCKHOLDER and CONTROL depend on this

## Layer dependency order
database → symbols → prog → theorems/base -> theorems (stockholder → control → trans → distribute → reorgs) → cases

## Import side-effects
Theorem modules register handlers on import. Tests that need a theorem must import its module:
  from main.theorems.base import ABSTRACT_THEOREMS, goal_abstract, assert_expand
  import main.theorems.stockholder  # registers STOCKHOLDER
  import main.theorems.control      # registers CONTROL (also requires stockholder registered first)

## Do not
- Add external dependencies (stdlib only)
- Change the Database API once test_database.py is passing
- Implement continuity-of-interest, business purpose, or step transaction doctrines (out of scope per CLAUDE.md §9)