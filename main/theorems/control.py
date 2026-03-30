"""
CONTROL abstract theorem (CLAUDE.md §5.1).

Statutory definition: X controls Y at T iff X owns
  ≥ 80 % of every class of voting stock issued by Y, AND
  ≥ 80 % of every class of non-voting stock issued by Y.

If Y has issued no voting stock at all, control cannot be established.
Non-voting stock classes are vacuously satisfied when none exist.

(THEOREM ABSTRACT (X Y T)
  (CONTROL ?X ?Y ?T)
  (Goal (STOCKHOLDER ?X ?Y ?T) Abstract)     ; must own some stock
  ; find all stock classes issued by Y
  ; partition into voting / non-voting
  ; for each class sum total shares and X's shares
  ; verify owned/total >= 0.80 for each class)

ISSUE, STOCK, VOTING, PIECE-OF, NSHARES are queried time-free (structural
facts in the Phellis network per DECISIONS.md).  OWN is queried with the
concrete time token (ownership changes via Trans expand theorems).
"""
from typing import Iterator

from main.database import Database
from main.theorems.base import ABSTRACT_THEOREMS, goal_abstract


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _is_var(val) -> bool:
    return isinstance(val, str) and val.startswith('?')


def _resolve(pat, binding: dict):
    """Return the concrete value for *pat* given *binding*, or *pat* if unbound."""
    if _is_var(pat) and len(pat) > 1:
        return binding.get(pat[1:], pat)
    return pat


def _check_control(db: Database, owner: str, corp: str, time: str) -> bool:
    """Return True iff *owner* controls *corp* at *time* under §368(c).

    Two aggregate tests, both required:
      (1) owner's combined voting power / total voting power of corp  ≥ 0.80
      (2) owner's combined non-voting shares / total non-voting shares ≥ 0.80
          (vacuously satisfied when corp has issued no non-voting stock)

    Each test aggregates across all classes in its category rather than
    checking each class independently.  At least one voting class must exist.
    """
    voting: list[str] = []
    nonvoting: list[str] = []

    for entry in db.all_entries('ISSUE'):
        if len(entry) != 2:
            continue
        issuer, stock_sym = entry
        if issuer != corp:
            continue
        if not db.query('STOCK', stock_sym):
            continue
        if db.query('VOTING', stock_sym):
            voting.append(stock_sym)
        else:
            nonvoting.append(stock_sym)

    if not voting:
        return False

    def _tally(symbols: list[str]) -> tuple[int, int]:
        """Return (owner_shares, total_shares) aggregated across all classes in *symbols*."""
        owned = 0
        total = 0
        for stock_sym in symbols:
            for piece_binding in db.query('PIECE-OF', '?P', stock_sym):
                piece = piece_binding.get('P')
                if piece is None:
                    continue
                n_results = db.query('NSHARES', piece, '?N')
                if not n_results:
                    continue
                n = n_results[0].get('N', 0)
                total += n
                if db.query('OWN', owner, piece, time):
                    owned += n
        return owned, total

    voting_x, voting_total = _tally(voting)
    if voting_total == 0 or voting_x / voting_total < 0.80:
        return False

    nonvoting_x, nonvoting_total = _tally(nonvoting)
    if nonvoting_total > 0 and nonvoting_x / nonvoting_total < 0.80:
        return False

    return True


# ---------------------------------------------------------------------------
# Theorem body
# ---------------------------------------------------------------------------

def _control_abstract(db: Database, *args) -> Iterator[dict]:
    """Yield one binding dict per (owner, corp, time) triple that satisfies control."""
    if len(args) != 3:
        return

    owner_pat, corp_pat, time_pat = args

    # Use STOCKHOLDER to enumerate candidate triples — handles variable patterns
    # and ensures at least one OWN link exists before the expensive ratio check.
    seen: set[tuple] = set()
    for sh_binding in goal_abstract(db, 'STOCKHOLDER', owner_pat, corp_pat, time_pat):
        owner = _resolve(owner_pat, sh_binding)
        corp = _resolve(corp_pat, sh_binding)
        time = _resolve(time_pat, sh_binding)

        if _is_var(owner) or _is_var(corp) or _is_var(time):
            continue  # cannot do arithmetic on unresolved variables

        triple = (owner, corp, time)
        if triple in seen:
            continue
        seen.add(triple)

        if _check_control(db, owner, corp, time):
            binding: dict = {}
            for pat, val in [(owner_pat, owner), (corp_pat, corp), (time_pat, time)]:
                if _is_var(pat) and len(pat) > 1:
                    binding[pat[1:]] = val
            yield binding


ABSTRACT_THEOREMS['CONTROL'] = _control_abstract
