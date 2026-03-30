"""
TRANS expand theorem (CLAUDE.md §4.1) and SPLITPIECE (§4.2).

TRANS(subject, obj, owner, recipient, time):
    Records the TRANS proposition in the DB.
    Erases the most recently asserted (OWN owner obj T_prev) entry.
    Asserts (OWN recipient obj time).

    The "last known state" heuristic (T0=(LAST STATE) in the paper) is
    implemented by taking the last entry in insertion order from the OWN
    query results.  Since case descriptions assert ownership events
    chronologically, this picks the most recent time token.

SPLITPIECE(new_piece, old_piece, time):
    new_piece must already have (NSHARES new_piece n) asserted before calling.
    Asserts (PIECE-OF new_piece S) where S is the stock class of old_piece.
    Decrements (NSHARES old_piece) by (NSHARES new_piece).
"""
from main.database import Database
from main.theorems.base import EXPAND_THEOREMS


def _trans_expand(
    db: Database,
    subject: str,
    obj: str,
    owner: str,
    recipient: str,
    time: str,
) -> None:
    """Expand TRANS: record the transaction and update ownership."""
    db.assert_('TRANS', subject, obj, owner, recipient, time)

    # Erase the most recently asserted time-indexed OWN for (owner, obj).
    prior_timed = db.query('OWN', owner, obj, '?T')
    if prior_timed:
        db.erase('OWN', owner, obj, prior_timed[-1]['T'])
    elif db.query('OWN', owner, obj):
        # Fall back to time-free OWN if no time-indexed entry exists.
        db.erase('OWN', owner, obj)

    db.assert_('OWN', recipient, obj, time)


def _splitpiece_expand(
    db: Database,
    new_piece: str,
    old_piece: str,
    time: str,
) -> None:
    """Expand SPLITPIECE: carve new_piece out of old_piece.

    Precondition: (NSHARES new_piece n) already asserted.
    """
    poc = db.query('PIECE-OF', old_piece, '?S')
    if not poc:
        return
    stock = poc[0]['S']

    db.assert_('PIECE-OF', new_piece, stock)

    old_n_res = db.query('NSHARES', old_piece, '?N')
    new_n_res = db.query('NSHARES', new_piece, '?M')
    if not old_n_res or not new_n_res:
        return

    old_n = old_n_res[0]['N']
    new_n = new_n_res[0]['M']
    # TODO is this properly deleting old stuff?
    db.erase('NSHARES', old_piece, old_n)
    # TODO where should we enforce old_n - new_n >= 0?
    db.assert_('NSHARES', old_piece, max(old_n - new_n, 0))
        


EXPAND_THEOREMS['TRANS'] = _trans_expand
EXPAND_THEOREMS['SPLITPIECE'] = _splitpiece_expand
