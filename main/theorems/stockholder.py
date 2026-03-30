"""
STOCKHOLDER abstract theorem (CLAUDE.md §3.2, §5).

(THEOREM ABSTRACT (O C S P)
  (STOCKHOLDER ?O ?C)
  (GOAL (ISSUE ?C ?S))
  (GOAL (STOCK ?S))
  (GOAL (PIECE-OF ?P ?S))
  (GOAL (OWN ?O ?P)))

?O owns a piece ?P of stock ?S issued by corporation ?C.

Time-indexed form: the caller may pass a time token as the third argument,
e.g. (STOCKHOLDER ?O ?C ?T).  When a time token is present the OWN lookup
is restricted to that time: (OWN ?O ?P ?T).  When absent, both time-free
and time-indexed OWN propositions are accepted (two-arity OWN first, then
three-arity OWN with a bound ?T variable).
"""
from typing import Iterator

from main.database import Database
from main.prog import prog
from main.theorems.base import ABSTRACT_THEOREMS


def _stockholder_abstract(db: Database, *args) -> Iterator[dict]:
    """Yield one binding dict per (owner, corp[, time]) match."""
    if len(args) == 2:
        owner_pat, corp_pat = args
        time_pat = None
    elif len(args) == 3:
        owner_pat, corp_pat, time_pat = args
    else:
        return  # wrong arity — yield nothing

    if time_pat is None:
        # Try time-free OWN first, then time-indexed OWN (binding any time).
        # Two separate prog() calls so results are not interleaved ambiguously.
        goals_no_time = [
            ('ISSUE', corp_pat, '?S'),
            ('STOCK', '?S'),
            ('PIECE-OF', '?P', '?S'),
            ('OWN', owner_pat, '?P'),
        ]
        yield from prog(db, goals_no_time)

        goals_with_time = [
            ('ISSUE', corp_pat, '?S'),
            ('STOCK', '?S'),
            ('PIECE-OF', '?P', '?S'),
            ('OWN', owner_pat, '?P', '?T'),
        ]
        yield from prog(db, goals_with_time)
    else:
        goals = [
            ('ISSUE', corp_pat, '?S'),
            ('STOCK', '?S'),
            ('PIECE-OF', '?P', '?S'),
            ('OWN', owner_pat, '?P', time_pat),
        ]
        yield from prog(db, goals)


ABSTRACT_THEOREMS['STOCKHOLDER'] = _stockholder_abstract
