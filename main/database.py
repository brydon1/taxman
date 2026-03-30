"""
TAXMAN Database — proposition store.

Every fact in TAXMAN is a parenthesized list: (PREDICATE ARG1 ARG2 ...).
Here that becomes a Python tuple stored under the predicate key.

Adding a proposition makes it "true". Removing it makes it "false".
There is no third state: truth equals presence in the DB.

Time is handled by appending a time token as the last argument:

    OWN(PHELLIS, P1, T4)   — Phellis owns P1 at time T4
    OWN(PHELLIS, P1)       — Phellis owns P1 at all times in scope

The Database layer applies no special handling to time tokens; they are
just ordinary arguments. Time-aware semantics live in the theorem layer.

Whenever a concept must be treated as an object (to hang further predicates
on it), a fresh internal symbol is generated and two propositions are
asserted — one naming the symbol, one attaching an attribute:

    ISSUE(NEW-JERSEY, S1)   — NJ has issued something called S1
    STOCK(S1)               — S1 is a stock

This is the "nominalization convention" from the original micro-Planner
implementation and is why gen() exists in symbols.py.
"""

from collections import defaultdict


class Database:
    """
    Proposition database indexed by predicate.

    Propositions are stored as tuples of arguments under their predicate key.
    The same tuple may not be stored twice (assert_ is idempotent).
    Time-indexed propositions are ordinary propositions whose last argument
    is a time token; the Database layer applies no special handling to them.
    """

    def __init__(self):
        self._store: dict[str, list[tuple]] = defaultdict(list)

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def assert_(self, pred: str, *args) -> None:
        """Store (pred, *args) if not already present."""
        entry = args
        if entry not in self._store[pred]:
            self._store[pred].append(entry)

    def erase(self, pred: str, *args) -> None:
        """Remove exactly the tuple (pred, *args). No-op if absent."""
        self._store[pred] = [e for e in self._store[pred] if e != args]

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def query(self, pred: str, *args) -> list[dict]:
        """
        Return one binding-dict per DB entry that matches the pattern.

        Pattern rules:
        - A string beginning with '?' is a variable.
          '?' alone is an anonymous variable: it matches any value but
          produces no binding.  '?NAME' binds NAME to the matched value.
          If the same NAME appears more than once, both occurrences must
          unify to the same value.
        - Any other value is ground and must equal the corresponding
          DB argument exactly.
        - The pattern arity (number of args) must equal the entry arity;
          propositions with different arities never match each other.
        """
        results = []
        for entry in self._store[pred]:
            if len(entry) != len(args):
                continue
            bindings: dict = {}
            matched = True
            for pattern, value in zip(args, entry):
                if isinstance(pattern, str) and pattern.startswith('?'):
                    var = pattern[1:]   # empty string for anonymous '?'
                    if not var:
                        # anonymous variable — match but do not bind
                        continue
                    if var in bindings:
                        if bindings[var] != value:
                            matched = False
                            break
                    else:
                        bindings[var] = value
                elif pattern != value:
                    matched = False
                    break
            if matched:
                results.append(bindings)
        return results

    # ------------------------------------------------------------------
    # Introspection (useful for theorems and tests)
    # ------------------------------------------------------------------

    def all_predicates(self) -> list[str]:
        """Return every predicate that has at least one entry."""
        return [p for p, entries in self._store.items() if entries]

    def all_entries(self, pred: str) -> list[tuple]:
        """Return all raw argument-tuples stored under pred."""
        return list(self._store[pred])
