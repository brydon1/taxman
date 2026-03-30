# DECISIONS.md

## 2026-03-19: Database indexing by predicate
Store propositions as `dict[str, list[tuple]]` keyed by predicate name.
Alternative considered: flat list of all propositions. Rejected because Control
theorem requires enumerating all stock classes for a corp — predicate-indexed
makes this O(n_stocks) not O(n_all_facts).

## 2026-03-19: prog() as a generator
Returns Iterator[dict] rather than list[dict]. Allows early exit once first
match is found (important for verification queries). Backtracking is implicit
in the recursive yield-from structure.

## 2026-03-19: assert_ is idempotent (no duplicates)
Duplicate detection uses a linear scan (`entry not in self._store[pred]`).
Alternative considered: using a set for O(1) deduplication, rejected because
tuples containing mutable values (not the case here, but future-proofing)
and because insertion order is preserved in list — tests assert result ordering
matches assertion order, which sets do not guarantee. For the scale of TAXMAN
(~50 symbols, ~200 propositions) the linear scan is negligible.

## 2026-03-19: query arity must match exactly
A query `('OWN', '?O', '?X')` (2 args) will never match `('OWN', 'PHELLIS', 'P1', 'T4')`
(3 args). This means callers must know the arity they want. This is intentional:
it matches how micro-Planner pattern lists work (fixed-length), and it means
time-indexed and time-free propositions of the same predicate coexist without
collision. The prog() layer is responsible for expanding time-variables when
needed.

## 2026-03-19: Anonymous variable '?' produces no binding key
When pattern element is exactly `'?'`, the arg matches but no key is added to
the binding dict. This avoids polluting bindings with an empty-string key `''`
that could silently break variable-conflict checks in prog(). Callers that only
care about existence (not the matched value) use `'?'`; callers that need the
value use a named variable like `'?S'`.

## 2026-03-19: Time-indexed propositions handled at proposition level only
The Database stores `('OWN', 'PHELLIS', 'P1', 'T0')` as just another 3-arg
proposition under predicate `'OWN'`. No special time-period lists or temporal
index exists at this layer. Time management (advancing state, erasing old
ownership, asserting new) is the responsibility of Expand theorems (trans.py).
This keeps the Database layer minimal and matches the paper's description of
Assert/Erase operating on the raw list set.

## 2026-03-19: all_entries() and all_predicates() as introspection helpers
Not part of the original TAXMAN spec but added to Database because:
1. The Control theorem needs to enumerate all stock classes for a given corp
   — `all_entries('ISSUE')` is cleaner than a wildcard query.
2. Tests need to assert idempotency of assert_ without going through query().
These methods return copies (list()) to prevent callers from mutating internal
state. If the API must be frozen after test_database.py passes (per AGENTS.md),
these are included because the Control theorem will need them.

## 2026-03-20: Theorem registries and routing live in theorems/base.py
ABSTRACT_THEOREMS, EXPAND_THEOREMS, goal_abstract, and assert_expand are defined
in theorems/base.py. prog.py retains only apply_bindings and prog() — the pure
pattern-matching primitives that have no dependency on the theorem layer.

This separation reflects the two distinct abstraction levels:
- prog.py: low-level DB iteration (no knowledge of theorems exist)
- theorems/base.py: theorem routing (reads registries, calls theorems)

Import chain: database ← prog ← theorems/base ← individual theorem modules.
No circular imports: theorems/base.py imports only Database; theorem modules
import from theorems/base and prog as needed.

## 2026-03-19: goal_abstract short-circuits on DB hit — does not merge DB + theorem results
If db.query() returns any results, goal_abstract yields them and returns immediately.
The registered theorem is never called. This means:
1. Asserting CONTROL directly into the DB bypasses the ratio check.
2. Tests can pre-assert conclusions to isolate higher layers.
3. The caching pattern from CLAUDE.md §3.2 ("first searches DB for a direct assertion")
   is faithfully reproduced.
Alternative considered: always running the theorem and merging. Rejected because
it would make direct assertions ambiguous and double-count results.

## 2026-03-19: assert_expand falls back to direct store when no theorem registered
If no expand theorem is registered for a concept, assert_expand(db, concept, *args)
stores (concept, *args) directly in the DB. This allows incremental implementation:
TRANS can be expand-registered in session 5 without breaking earlier sessions that
might assert it directly. The fallback matches micro-Planner's behavior when no
theorem is bound to a pattern.

## 2026-03-19: apply_bindings skips anonymous variable via len(a) > 1 guard
In apply_bindings, the condition `len(a) > 1` before substitution means '?' (length 1
after '?' prefix) is never looked up in bindings and is passed through unchanged.
db.query then receives '?' and treats it as a wildcard. If the guard were absent,
bindings.get('', '?') would return '?' anyway ('' key never set), so the behavior
would be identical — but the guard makes the intent explicit and avoids dict lookup.

## 2026-03-19: reset_gen() added to symbols.py for test isolation
The _counter in symbols.py is module-level global. Without reset, test execution
order affects which symbol names are produced. Tests that assert specific symbol
names (e.g., 'PHE1') call reset_gen() in setUp/autouse fixtures. Tests that only
care about uniqueness do not need to reset. The function is intentionally not
called automatically on Database construction — the counter is not tied to any DB.

## 2026-03-19: gen() counter is global across all prefixes
gen('A') and gen('B') both increment the same counter: gen('A') → 'A1', gen('B') → 'B2'.
Alternative: per-prefix counters. Rejected because uniqueness across all generated
symbols is the requirement (any two symbols must be distinguishable); per-prefix
counters would allow 'A1' and 'B1' to coexist in the same DB, creating confusion
in assertions that compare symbol names without knowing their prefix.

## 2026-03-19: NSHARES values stored as int (not str)
The Database layer is untyped — it stores whatever is passed. control.py does
`total += n` where n comes from a NSHARES query result. This requires n to be int.
Convention: always assert NSHARES with an int literal. Strings like '100' will cause
a TypeError at runtime in the Control theorem. No type enforcement at the DB layer —
the cost of adding it (complicates Database API) exceeds the benefit for this scale.

## 2026-03-19: ISSUE always asserted as 2-arg (issuer, stock) — no time token
Both the STOCKHOLDER and CONTROL theorems query ISSUE as a 2-arg proposition.
CONTROL._check_control explicitly skips ISSUE entries with len != 2. This means
ISSUE is treated as a structural/static fact rather than a time-varying one, which
matches the paper's model: a stock class once issued remains a class of the corporation
even if no shares are currently outstanding. Time-variation in ownership is captured
entirely via OWN propositions with time tokens, not via ISSUE.

## 2026-03-20: TRANS expand erases last OWN by insertion order, not by time-token sort
TRANS finds prior ownership via `db.query('OWN', owner, obj, '?T')` and erases
`prior[-1]` (the last entry in insertion order).  The assumption is that case
descriptions assert ownership events chronologically, so insertion order matches
temporal order.  A sort on the numeric suffix of the time token was rejected
because: (1) time tokens are convention not a contract — future cases may use
non-numeric suffixes; (2) it adds complexity for no benefit at this scale.
If ownership is asserted out of chronological order the caller is responsible for
consistency, not trans.py.

## 2026-03-20: TRANS also handles time-free OWN as a fallback
If no time-indexed (OWN owner obj ?T) entry exists, TRANS checks for a time-free
(OWN owner obj) entry and erases it.  This lets initial-state assertions that omit
time tokens (e.g. in simple test setups) work correctly with TRANS expand.
The time-free check is a fallback — time-indexed OWN is always tried first.

## 2026-03-20: SPLITPIECE registered in trans.py, not in a separate file
SPLITPIECE is a lower-level piece-manipulation primitive used by DISTRIBUTE.
It is registered in trans.py rather than a dedicated file because:
(1) It shares no logic with DISTRIBUTE; (2) the layer order is
trans → distribute → reorgs (AGENTS.md), so trans.py is the right home;
(3) keeping it with TRANS keeps the file cohesive (both are ownership-change
primitives that operate on pieces).

## 2026-03-20: DISTRIBUTE distribution rule stored as DB proposition, not a direct arg
DISTRIBUTE(subject, obj, owner, recipient_corp, time) reads the rule from:
  (DISTRIBUTION-RULE obj 'N-FOR-ONE' n source_stock)
  (DISTRIBUTION-RULE obj 'PRORATA' source_stock)
Alternatives considered: pass n and source_stock as direct args to assert_expand.
Rejected because the paper stores distribution rules as explicit propositions in the
semantic network, and this keeps the DISTRIBUTE call site clean.  The rule must be
pre-asserted before calling assert_expand(db, 'DISTRIBUTE', ...).

## 2026-03-20: DISTRIBUTE enumerates PIECE-OF directly, not via STOCKHOLDER theorem
To find holders of source_stock, distribute.py iterates db.all_entries('PIECE-OF')
and filters by stock == source_stock, then queries OWN for each piece.
Alternative: use goal_abstract(db, 'STOCKHOLDER', ...) which yields richer bindings.
Rejected because: (1) the STOCKHOLDER theorem bindings include S and P via internal
variable names that callers should not depend on; (2) STOCKHOLDER requires both ISSUE
and STOCK to be asserted for the corporation, but DISTRIBUTE only needs to know who
holds a particular stock class, not the full corporate-issuance chain; (3) this
approach is more direct and testable without importing ABSTRACT_THEOREMS side-effects.

## 2026-03-19: phellis_expected.py contains JSON despite .py extension
The file at main/cases/phellis_expected.py is a JSON object, not Python source.
The README.md file layout section names it phellis_expected.json (the intended name).
Load it with open() + json.load(), not by importing. The extension mismatch is a
naming error; do not rename without updating any test that references the path.
README.md's code sample for db.query() at lines 146-148 also contains a related
error: it shows a 2-arg OWN query returning both 2-arg and 3-arg results. The actual
implementation enforces arity-matching — a 2-arg query never matches a 3-arg entry.
Do not copy that example verbatim when writing test_phellis.py.

## 2026-03-29: CONTROL uses aggregate-within-category thresholds, not per-class
§368(c) requires 80% of "total combined voting power" and 80% of "total number of
shares of all other classes" — both are aggregate figures, not per-class tests.
_check_control now tallies owner_shares and total_shares across all voting classes
combined (one ratio check), then does the same for all non-voting classes combined
(one ratio check). A prior per-class implementation was stricter: a class where the
owner held 75% would fail even if the owner's aggregate exceeded 80%. The test
test_nonvoting_threshold_checked_in_aggregate captures the case that was incorrectly
failing under the old code (85% of NV1 + 75% of NV2 = 80% aggregate → control).
