"""
D-REORGANIZATION abstract theorem (CLAUDE.md §5.4).

Statute (§368(a)(1)(D)):
  Transfer of assets by one corporation (A) to another corporation (C),
  such that immediately after the transfer, A (or A's shareholders) controls C.

Algorithm (partial — distribution requirement omitted per CLAUDE.md §9):
  1. Scan TRANS entries for transfers where owner=A, recipient=C, and the
     transferred object is a property (PIECE-OF a class without a STOCK
     assertion) — i.e. not a stock piece.
  2. A must be a CORPORATION.
  3. A must control C immediately after the transfer:
     CONTROL(A, C, T) via goal_abstract.
  4. "Distribution requirement" (§354/355/356) is NOT checked — the full
     D-Reorg requires a qualifying plan of reorganization plus a distribution
     of C stock to A's shareholders, but TAXMAN implements only the structural
     core (asset transfer + post-transfer control).

On success, yield a binding dict for any variable args in the pattern.
"""
from typing import Iterator

from main.database import Database
from main.theorems.base import ABSTRACT_THEOREMS, goal_abstract


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _is_var(val) -> bool:
    return isinstance(val, str) and val.startswith('?')


def _matches_pat(pat, val) -> bool:
    """Return True if pat is a variable or equals val."""
    return _is_var(pat) or pat == val


def _is_property_of(db: Database, piece: str) -> bool:
    """Return True iff *piece* is a PIECE-OF a class that has no STOCK assertion.

    A "property" piece is any piece whose parent class is not a stock — it
    represents operating assets, bonds, or other non-equity interests.
    """
    for poc in db.query('PIECE-OF', piece, '?S'):
        cls = poc['S']
        if not db.query('STOCK', cls):
            return True
    return False


# ---------------------------------------------------------------------------
# Theorem body
# ---------------------------------------------------------------------------

def _d_reorg_abstract(db: Database, *args) -> Iterator[dict]:
    """Yield one binding dict per (transferor, transferee, time) satisfying D-Reorg."""
    if len(args) != 3:
        return

    transferor_pat, transferee_pat, time_pat = args

    seen: set[tuple] = set()

    for entry in db.all_entries('TRANS'):
        if len(entry) != 5:
            continue
        _subj, X, owner, recip, T = entry

        # Property filter: the transferred object must be a non-stock asset.
        if not _is_property_of(db, X):
            continue

        A = owner  # transferor — the entity that owned and transferred the property
        C = recip  # transferee — the entity that receives the property

        # Apply pattern filters before any further work.
        if not _matches_pat(transferor_pat, A):
            continue
        if not _matches_pat(transferee_pat, C):
            continue
        if not _matches_pat(time_pat, T):
            continue

        triple = (A, C, T)
        if triple in seen:
            continue

        # Constraint 1: transferor must be a registered corporation.
        if not db.query('CORPORATION', A):
            continue

        # Constraint 2: A must control C immediately after the transfer.
        if not list(goal_abstract(db, 'CONTROL', A, C, T)):
            continue

        seen.add(triple)
        binding: dict = {}
        for pat, val in [(transferor_pat, A), (transferee_pat, C), (time_pat, T)]:
            if _is_var(pat) and len(pat) > 1:
                binding[pat[1:]] = val
        yield binding


ABSTRACT_THEOREMS['D-REORGANIZATION'] = _d_reorg_abstract
