"""
TAXMAN Theorem registries — goal_abstract and assert_expand entry points.

Theorems are named rules that define one concept in terms of others.
There are two directions:

Abstract (bottom-up): given low-level facts, derive a high-level conclusion.
    STOCKHOLDER(O, C) is derived by chaining ISSUE → STOCK → PIECE-OF → OWN.
    Called via goal_abstract(db, 'STOCKHOLDER', owner, corp).

Expand (top-down): given a high-level assertion, generate the low-level facts
    that instantiate it. TRANS(S, X, O, R, T) expands by erasing OWN(O, X, T0)
    and asserting OWN(R, X, T1). Called via assert_expand(db, 'TRANS', ...).

Theorem modules register themselves in ABSTRACT_THEOREMS or EXPAND_THEOREMS
on import. Tests that need a theorem must import its module explicitly:

    import main.theorems.stockholder   # registers STOCKHOLDER
    import main.theorems.control       # registers CONTROL

goal_abstract checks the DB for a direct assertion first; only on a miss does
it call the registered theorem. This mirrors the original micro-Planner
behavior where assert_() of a computed result short-circuits future derivation.
"""

from typing import Iterator

from main.database import Database

# Theorem registries.  Each theorem module imports one of these dicts and
# inserts its handler on import, e.g.:
#   ABSTRACT_THEOREMS['STOCKHOLDER'] = stockholder_fn
ABSTRACT_THEOREMS: dict[str, callable] = {}
EXPAND_THEOREMS: dict[str, callable] = {}


def goal_abstract(db: Database, concept: str, *args) -> Iterator[dict]:
    """Query for *concept* with pattern *args*.

    Tries a direct DB lookup first.  Falls back to a registered abstract
    theorem if the DB returns nothing.
    """
    results = list(db.query(concept, *args))
    if results:
        yield from results
        return

    if concept in ABSTRACT_THEOREMS:
        yield from ABSTRACT_THEOREMS[concept](db, *args)


def assert_expand(db: Database, concept: str, *args) -> None:
    """Assert *concept* via its registered expand theorem, or directly.

    If no theorem is registered the proposition is stored as-is.
    """
    if concept in EXPAND_THEOREMS:
        EXPAND_THEOREMS[concept](db, *args)
    else:
        db.assert_(concept, *args)
