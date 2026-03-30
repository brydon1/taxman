"""
TAXMAN Prog — chained goals with backtracking.

A Goal is a query against the database. Variables (strings starting with '?')
unify with any matching value and are bound for subsequent goals in the chain:

    Goal: OWN(?X, P1)       → matches OWN(PHELLIS, P1), binds X = PHELLIS
    Goal: OWN(PHELLIS, ?X)  → matches OWN(PHELLIS, P1), binds X = P1
    Goal: OWN(PHELLIS, P1)  → returns True/False (ground verification)

A Prog is a sequence of goals that all must succeed, sharing variable bindings.
Backtracking is implicit: when a later goal finds no matches the generator
exhausts, the caller gets the next match from the earlier goal automatically,
and the sequence retries. This is identical to Prolog resolution, or a set
of nested loops where the inner loop failure causes the outer loop to advance.

Example — "Phellis is a stockholder of New-Jersey":

    goals = [
        ('ISSUE', 'NEW-JERSEY', '?S'),   # bind S ← S1
        ('STOCK', '?S'),                  # verify S1 is a stock
        ('PIECE-OF', '?P', '?S'),         # bind P ← P1
        ('OWN', 'PHELLIS', '?P'),         # verify Phellis owns P1
    ]
    # → succeeds: {'S': 'S1', 'P': 'P1'}
"""

from typing import Iterator

from main.database import Database


def apply_bindings(args: tuple, bindings: dict) -> tuple:
    """Replace ?VAR slots with their bound value; leave ground values alone.

    Anonymous variable '?' has an empty name after stripping '?', so
    bindings.get('', '?') returns '?' when '' is absent — it stays anonymous
    and db.query will treat it as a wildcard.
    """
    return tuple(
        bindings.get(a[1:], a) if isinstance(a, str) and a.startswith('?') and len(a) > 1 else a
        for a in args
    )


def prog(
    db: Database,
    goals: list[tuple],
    bindings: dict | None = None,
) -> Iterator[dict]:
    """Yield each complete binding dict that satisfies all goals in sequence.

    ``goals`` is a list of ``(predicate, arg1, arg2, ...)`` tuples.
    Backtracking is implicit: when a later goal finds no matches the generator
    simply exhausts and the caller continues with the next match from an
    earlier goal.
    """
    if bindings is None:
        bindings = {}
    if not goals:
        yield dict(bindings)
        return

    pred, *args = goals[0]
    resolved_args = apply_bindings(tuple(args), bindings)

    for match in db.query(pred, *resolved_args):
        # Guard: skip if this match would rebind an already-bound variable to a
        # different value.  (apply_bindings substitutes known bindings first, so
        # this fires only for variables that appear in multiple goals and were
        # *not* yet bound at the time the earlier goal ran.)
        conflict = any(
            k in bindings and bindings[k] != v
            for k, v in match.items()
        )
        if conflict:
            continue
        merged = {**bindings, **match}
        yield from prog(db, goals[1:], merged)
