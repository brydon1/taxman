"""
B-REORGANIZATION abstract theorem (CLAUDE.md §5.2).

Statute (§368(a)(1)(B)):
  Acquisition by one corporation (A), solely in exchange for all or part of
  its voting stock, of stock of another corporation (C), such that immediately
  after the acquisition A controls C.

Algorithm — Control located first (CLAUDE.md §7.4):
  1. Find CONTROL(A, C, T_ctrl) via goal_abstract.
  2. A must be asserted as CORPORATION.
  3. Scan all TRANS entries in the DB for transfers TO A.  Keep those where
     the transferred object is a PIECE-OF a STOCK issued by C.
     If none found, fail.
  4. For each distinct counterparty O1 that transferred C stock to A, find
     all TRANS entries where A is subject, A is owner, and O1 is recipient
     (i.e. every transfer A made to O1 as consideration).  Every such object
     must be a PIECE-OF a VOTING STOCK issued by A (solely-for-voting-stock).
     If O1 received nothing from A, or received non-voting consideration, fail.
  5. On success yield a binding dict for any variable args in the pattern.
"""
from typing import Iterator

from main.database import Database
from main.theorems.base import ABSTRACT_THEOREMS, goal_abstract


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _is_var(val) -> bool:
    return isinstance(val, str) and val.startswith('?')


def _resolve(pat: str, binding: dict) -> str:
    if _is_var(pat) and len(pat) > 1:
        return binding.get(pat[1:], pat)
    return pat


def _is_stock_of(db: Database, piece: str, corp: str) -> bool:
    """Return True iff *piece* is a PIECE-OF a STOCK issued by *corp*."""
    for poc in db.query('PIECE-OF', piece, '?S'):
        stock_sym = poc['S']
        if db.query('STOCK', stock_sym) and db.query('ISSUE', corp, stock_sym):
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

def _b_reorg_abstract(db: Database, *args) -> Iterator[dict]:
    """Yield one binding dict per (acquirer, target, time) satisfying B-Reorg."""
    if len(args) != 3:
        return

    acquirer_pat, target_pat, time_pat = args

    seen: set[tuple] = set()

    for ctrl_binding in goal_abstract(db, 'CONTROL', acquirer_pat, target_pat, time_pat):
        A = _resolve(acquirer_pat, ctrl_binding)
        C = _resolve(target_pat, ctrl_binding)
        T_ctrl = _resolve(time_pat, ctrl_binding)

        if _is_var(A) or _is_var(C) or _is_var(T_ctrl):
            continue

        triple = (A, C, T_ctrl)
        if triple in seen:
            continue
        seen.add(triple)

        # Constraint 1: acquirer must be a registered corporation.
        if not db.query('CORPORATION', A):
            continue

        # Constraint 2: A must have acquired stock of C.
        # TRANS(subject, obj, owner, recipient, time) — 5 args.
        acquisitions: list[tuple[str, str, str, str]] = []  # (subj, X1, O1, T_acq)
        for entry in db.all_entries('TRANS'):
            if len(entry) != 5:
                continue
            subj, X1, O1, recip, T_acq = entry
            if recip != A:
                continue
            if _is_stock_of(db, X1, C):
                acquisitions.append((subj, X1, O1, T_acq))

        if not acquisitions:
            continue

        # Constraint 3: solely for voting stock.
        # For each distinct counterparty O1 that transferred C stock to A,
        # every TRANS from A back to O1 must be a piece of voting stock of A.
        valid = True
        seen_counterparties: set[str] = set()

        for (_, _X1, O1, _T_acq) in acquisitions:
            if O1 in seen_counterparties:
                continue
            seen_counterparties.add(O1)

            consideration = [
                entry for entry in db.all_entries('TRANS')
                if (len(entry) == 5
                    and entry[0] == A   # subject = A
                    and entry[2] == A   # owner   = A
                    and entry[3] == O1) # recipient = O1
            ]

            if not consideration:
                valid = False
                break

            for (_, X2, _, _, _T_con) in consideration:
                if not _is_voting_stock_of(db, X2, A):
                    valid = False
                    break
            if not valid:
                break

        if not valid:
            continue

        binding: dict = {}
        for pat, val in [(acquirer_pat, A), (target_pat, C), (time_pat, T_ctrl)]:
            if _is_var(pat) and len(pat) > 1:
                binding[pat[1:]] = val
        yield binding


ABSTRACT_THEOREMS['B-REORGANIZATION'] = _b_reorg_abstract
