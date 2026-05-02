"""
C-REORGANIZATION abstract theorem (CLAUDE.md §5.3).

Statute (§368(a)(1)(C)):
  Acquisition by one corporation (A) of substantially all the properties of
  another corporation (C), in exchange solely for all or part of A's voting
  stock.

Algorithm:
  1. Scan TRANS entries for transfers where owner=C, recipient=A, and the
     transferred object is a property (PIECE-OF a class without a STOCK
     assertion) — i.e. not stock of C.
  2. A must be a CORPORATION.
  3. For each such property transfer, verify that A gave C solely voting
     stock of A as consideration: every TRANS(A, X2, A, C, *) must have
     X2 be a PIECE-OF a VOTING STOCK issued by A, and at least one such
     TRANS must exist.
  4. "Substantially all properties" test is partial (CLAUDE.md §9):
     the system verifies that A received at least one property of C but
     does not check whether C retained significant assets after the transfer.
"""
from typing import Iterator

from main.database import Database
from main.theorems.base import ABSTRACT_THEOREMS


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


def _is_voting_stock_of(db: Database, piece: str, corp: str) -> bool:
    """Return True iff *piece* is a PIECE-OF a VOTING STOCK issued by *corp*."""
    for poc in db.query('PIECE-OF', piece, '?S'):
        stock_sym = poc['S']
        if (db.query('STOCK', stock_sym)
                and db.query('VOTING', stock_sym)
                and db.query('ISSUE', corp, stock_sym)):
            return True
    return False


# ---------------------------------------------------------------------------
# Theorem body
# ---------------------------------------------------------------------------

def _c_reorg_abstract(db: Database, *args) -> Iterator[dict]:
    """Yield one binding dict per (acquirer, target, time) satisfying C-Reorg."""
    if len(args) != 3:
        return

    acquirer_pat, target_pat, time_pat = args

    seen: set[tuple] = set()

    for entry in db.all_entries('TRANS'):
        if len(entry) != 5:
            continue
        _subj, X1, O1, recip, T = entry

        # Property transfer: C=O1 owned X1 and transferred it to A=recip.
        # X1 must be a property (PIECE-OF a non-STOCK class), not stock of C.
        if not _is_property_of(db, X1):
            continue

        A = recip
        C = O1

        # Apply pattern filters before any further work.
        if not _matches_pat(acquirer_pat, A):
            continue
        if not _matches_pat(target_pat, C):
            continue
        if not _matches_pat(time_pat, T):
            continue

        triple = (A, C, T)
        if triple in seen:
            continue

        # Constraint 1: acquirer must be a registered corporation.
        if not db.query('CORPORATION', A):
            continue

        # Constraint 2: solely for voting stock.
        # Every TRANS from A (as subject and owner) to C must be a piece of
        # voting stock issued by A.  At least one such TRANS must exist.
        consideration = [
            e for e in db.all_entries('TRANS')
            if len(e) == 5 and e[0] == A and e[2] == A and e[3] == C
        ]

        if not consideration:
            continue

        if not all(_is_voting_stock_of(db, e[1], A) for e in consideration):
            continue

        seen.add(triple)
        binding: dict = {}
        for pat, val in [(acquirer_pat, A), (target_pat, C), (time_pat, T)]:
            if _is_var(pat) and len(pat) > 1:
                binding[pat[1:]] = val
        yield binding


ABSTRACT_THEOREMS['C-REORGANIZATION'] = _c_reorg_abstract
