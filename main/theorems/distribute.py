"""
DISTRIBUTE expand theorem (CLAUDE.md §4.3).

DISTRIBUTE(subject, obj, owner, recipient_corp, time):
    Distributes shares of the piece `obj` (owned by `owner`) to stockholders
    of `recipient_corp`, according to a distribution rule stored in the DB.

    Records the DISTRIBUTE proposition in the DB, then for each eligible
    holder creates a new piece via SPLITPIECE and TRANS.

Distribution rule (must be pre-asserted before calling assert_expand):

    (DISTRIBUTION-RULE obj 'N-FOR-ONE' n source_stock)
        Each holder of source_stock at `time` receives n * their_shares
        pieces of obj.  E.g. the 2-for-1 Delaware common distribution in
        the Phellis case.

    (DISTRIBUTION-RULE obj 'PRORATA' source_stock)
        Each holder receives shares proportional to their fraction of total
        source_stock holdings.

In both cases the implementation enumerates (PIECE-OF ? source_stock) entries
directly rather than going through the STOCKHOLDER theorem, so no import side-
effect on ABSTRACT_THEOREMS is required.
"""
from main.database import Database
from main.symbols import gen
from main.theorems.base import EXPAND_THEOREMS, assert_expand


def _holders_of(db: Database, source_stock: str, time: str) -> list[tuple[str, int]]:
    """Return [(holder, n_shares), ...] for every owner of source_stock at time."""
    results = []
    for entry in db.all_entries('PIECE-OF'):
        piece, stock = entry
        if stock != source_stock:
            continue
        own_results = db.query('OWN', '?O', piece, time)
        for own_b in own_results:
            holder = own_b['O']
            n_res = db.query('NSHARES', piece, '?N')
            if n_res:
                results.append((holder, n_res[0]['N']))
    return results


def _allocations_n_for_one(
    db: Database,
    source_stock: str,
    time: str,
    n: int,
) -> list[tuple[str, int]]:
    return [(holder, n * shares) for holder, shares in _holders_of(db, source_stock, time)]


def _allocations_prorata(
    db: Database,
    obj: str,
    source_stock: str,
    time: str,
) -> list[tuple[str, int]]:
    obj_n_res = db.query('NSHARES', obj, '?N')
    if not obj_n_res:
        return []
    total_obj = obj_n_res[0]['N']

    holders = _holders_of(db, source_stock, time)
    if not holders:
        return []
    total_source = sum(shares for _, shares in holders)
    if total_source == 0:
        return []

    return [(holder, round(shares / total_source * total_obj)) for holder, shares in holders]


def _distribute_expand(
    db: Database,
    subject: str,
    obj: str,
    owner: str,
    recipient_corp: str,
    time: str,
) -> None:
    """Expand DISTRIBUTE: split obj and transfer pieces to eligible holders."""
    db.assert_('DISTRIBUTE', subject, obj, owner, recipient_corp, time)

    nfor1 = db.query('DISTRIBUTION-RULE', obj, 'N-FOR-ONE', '?N', '?SRC')
    prorata = db.query('DISTRIBUTION-RULE', obj, 'PRORATA', '?SRC')

    if nfor1:
        n = nfor1[0]['N']
        source_stock = nfor1[0]['SRC']
        allocations = _allocations_n_for_one(db, source_stock, time, n)
    elif prorata:
        source_stock = prorata[0]['SRC']
        allocations = _allocations_prorata(db, obj, source_stock, time)
    else:
        return

    for holder, allocation in allocations:
        if allocation <= 0:
            continue
        p = gen()
        db.assert_('NSHARES', p, allocation)
        assert_expand(db, 'SPLITPIECE', p, obj, time)
        assert_expand(db, 'TRANS', subject, p, owner, holder, time)


EXPAND_THEOREMS['DISTRIBUTE'] = _distribute_expand
