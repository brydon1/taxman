"""
Tests for main/theorems/distribute.py — DISTRIBUTE expand theorem.

DISTRIBUTE(subject, obj, owner, recipient_corp, time):
  Distributes shares of piece `obj` to holders of source_stock, according
  to a pre-asserted DISTRIBUTION-RULE proposition.

  N-FOR-ONE: (DISTRIBUTION-RULE obj 'N-FOR-ONE' n source_stock)
  PRORATA:   (DISTRIBUTION-RULE obj 'PRORATA' source_stock)

Coverage:
  - Registration
  - DISTRIBUTE proposition stored in DB
  - N-FOR-ONE: single holder receives n * their_shares
  - N-FOR-ONE: multiple holders each receive correct allocation
  - N-FOR-ONE: NSHARES of obj decremented by total distributed
  - N-FOR-ONE: new pieces belong to same stock class as obj
  - N-FOR-ONE: recipients own new pieces at correct time
  - PRORATA: single holder receives all shares
  - PRORATA: two holders receive proportional shares
  - PRORATA: NSHARES of obj goes to zero after full distribution
  - No rule in DB: no-op (no new OWN entries created)
  - Zero-share holder skipped (allocation = 0)
  - Phellis-style scenario: 2-for-1 Delaware common to NJ common holders
"""
import pytest

from main.database import Database
from main.symbols import reset_gen, gen
from main.theorems.base import EXPAND_THEOREMS, assert_expand, goal_abstract
import main.theorems.stockholder # noqa: F401 — registers STOCKHOLDER
import main.theorems.trans       # noqa: F401 — registers TRANS, SPLITPIECE
import main.theorems.distribute  # noqa: F401 — registers DISTRIBUTE


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_gen():
    reset_gen()
    yield


@pytest.fixture
def db():
    return Database()


def _setup_stock_class(db, corp, stock_sym, *, voting=True):
    db.assert_('ISSUE', corp, stock_sym)
    db.assert_('STOCK', stock_sym)
    if voting:
        db.assert_('VOTING', stock_sym)
    db.assert_('COMMON', stock_sym)


def _add_piece_owned(db, piece, stock, n, owner, time):
    db.assert_('PIECE-OF', piece, stock)
    db.assert_('NSHARES', piece, n)
    db.assert_('OWN', owner, piece, time)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_distribute_registered(self):
        assert 'DISTRIBUTE' in EXPAND_THEOREMS

    def test_distribute_callable(self):
        assert callable(EXPAND_THEOREMS['DISTRIBUTE'])


# ---------------------------------------------------------------------------
# DISTRIBUTE proposition stored
# ---------------------------------------------------------------------------

class TestDistributePropositionStored:
    def test_distribute_fact_in_db(self, db):
        db.assert_('DISTRIBUTION-RULE', 'OBJ', 'N-FOR-ONE', 2, 'SRC-STOCK')
        _add_piece_owned(db, 'P-SRC', 'SRC-STOCK', 10, 'HOLDER-A', 'T1')
        _add_piece_owned(db, 'OBJ', 'DIST-STOCK', 100, 'NJ', 'T1')

        assert_expand(db, 'DISTRIBUTE', 'NJ', 'OBJ', 'NJ', 'CORP', 'T1')

        rows = db.query('DISTRIBUTE', 'NJ', 'OBJ', 'NJ', 'CORP', 'T1')
        assert rows == [{}]


# ---------------------------------------------------------------------------
# N-FOR-ONE distribution
# ---------------------------------------------------------------------------

class TestNForOne:
    def _setup(self, db, time='T1'):
        # Source stock class: holders will be measured against this.
        _setup_stock_class(db, 'NJ', 'SRC-STOCK')
        _add_piece_owned(db, 'P-HOLDER-A', 'SRC-STOCK', 10, 'HOLDER-A', time)
        _add_piece_owned(db, 'P-HOLDER-B', 'SRC-STOCK', 20, 'HOLDER-B', time)

        # Object being distributed.
        _setup_stock_class(db, 'DE', 'DIST-STOCK')
        _add_piece_owned(db, 'OBJ-PIECE', 'DIST-STOCK', 60, 'NJ', time)

        # Distribution rule: 2 shares per 1 held.
        db.assert_('DISTRIBUTION-RULE', 'OBJ-PIECE', 'N-FOR-ONE', 2, 'SRC-STOCK')

    # TODO if the events do not share time, then this fails
    def test_single_holder_receives_allocation(self, db):
        holder_A = 'HOLDER-A'
        company_NJ = 'NJ'
        company_DE = 'DE'
        src_stock = 'SRC-STOCK'
        dist_stock = 'DIST-STOCK'
        time_1 = 'T1'
        piece_to_dist = 'OBJ-PIECE'
        _setup_stock_class(db, company_NJ, src_stock)
        _add_piece_owned(db, 'P-HOLDER-A', src_stock, 10, holder_A, time_1)

        _setup_stock_class(db, company_DE, dist_stock)
        _add_piece_owned(db, piece_to_dist, dist_stock, 20, company_NJ, time_1)

        stockholder_results_before = list(goal_abstract(db,'STOCKHOLDER', holder_A, company_DE, '?T'))
        assert len(stockholder_results_before) == 0

        assert_expand(db,'DISTRIBUTION-RULE', piece_to_dist, 'N-FOR-ONE', 2, src_stock)

        assert_expand(db, 'DISTRIBUTE', company_NJ, piece_to_dist, company_NJ, 'CORP', time_1)

        # HOLDER-A should now own a new piece of DIST-STOCK.
        stockholder_results_after = list(goal_abstract(db,'STOCKHOLDER', holder_A, company_DE, time_1))
        assert len(stockholder_results_after) == 1
        # The new piece of DIST-STOCK has 20 shares
        new_piece = stockholder_results_after[0]['P']
        nshares = db.query('NSHARES', new_piece, '?N')
        assert nshares[0]['N'] == 20  # 2 * 10

    def test_two_holders_get_correct_allocations(self, db):
        self._setup(db)
        assert_expand(db, 'DISTRIBUTE', 'NJ', 'OBJ-PIECE', 'NJ', 'CORP', 'T1')

        # HOLDER-A: 2*10 = 20 shares
        holder_A_stockholder_of_DE = list(goal_abstract(db,'STOCKHOLDER', 'HOLDER-A', 'DE', 'T1'))
        assert len(holder_A_stockholder_of_DE) == 1
        nshares_A = db.query('NSHARES', holder_A_stockholder_of_DE[0]['P'], '?N')
        assert len(nshares_A) == 1
        assert nshares_A[0]['N'] == 20  # 2 * 10

        # HOLDER-B: 2*20 = 40 shares
        holder_B_stockholder_of_DE = list(goal_abstract(db,'STOCKHOLDER', 'HOLDER-B', 'DE', 'T1'))
        assert len(holder_B_stockholder_of_DE) == 1
        assert db.query('NSHARES', holder_B_stockholder_of_DE[0]['P'], '?N')[0]['N'] == 40

    def test_obj_nshares_decremented(self, db):
        self._setup(db)
        assert_expand(db, 'DISTRIBUTE', 'NJ', 'OBJ-PIECE', 'NJ', 'CORP', 'T1')

        # 20 + 40 = 60 distributed; OBJ-PIECE started at 60 → 0 remaining.
        remaining = db.query('NSHARES', 'OBJ-PIECE', '?N')
        assert remaining[0]['N'] == 0

    def test_new_pieces_belong_to_dist_stock(self, db):
        self._setup(db)
        assert_expand(db, 'DISTRIBUTE', 'NJ', 'OBJ-PIECE', 'NJ', 'CORP', 'T1')

        for holder in ('HOLDER-A', 'HOLDER-B'):
            stockholder = list(goal_abstract(db,'STOCKHOLDER', holder, 'DE', 'T1'))
            piece = stockholder[0]['P']
            assert db.query('PIECE-OF', piece, 'DIST-STOCK') == [{}]

    def test_three_for_one(self, db):
        _setup_stock_class(db, 'NJ', 'SRC-STOCK')
        _add_piece_owned(db, 'P-H', 'SRC-STOCK', 5, 'HOLDER', 'T1')
        _setup_stock_class(db, 'DE', 'DIST-STOCK')
        _add_piece_owned(db, 'OBJ-PIECE', 'DIST-STOCK', 100, 'NJ', 'T1')
        db.assert_('DISTRIBUTION-RULE', 'OBJ-PIECE', 'N-FOR-ONE', 3, 'SRC-STOCK')

        assert_expand(db, 'DISTRIBUTE', 'NJ', 'OBJ-PIECE', 'NJ', 'CORP', 'T1')

        stockholder = list(goal_abstract(db,'STOCKHOLDER', 'HOLDER', 'DE', 'T1'))
        assert db.query('NSHARES', stockholder[0]['P'], '?N')[0]['N'] == 15  # 3 * 5


# ---------------------------------------------------------------------------
# PRORATA distribution
# ---------------------------------------------------------------------------

class TestProrata:
    def test_single_holder_gets_all(self, db):
        _setup_stock_class(db, 'NJ', 'SRC-STOCK')
        _add_piece_owned(db, 'P-H', 'SRC-STOCK', 100, 'HOLDER-A', 'T1')
        _setup_stock_class(db, 'DE', 'DIST-STOCK')
        _add_piece_owned(db, 'OBJ', 'DIST-STOCK', 500, 'NJ', 'T1')
        db.assert_('DISTRIBUTION-RULE', 'OBJ', 'PRORATA', 'SRC-STOCK')

        assert_expand(db, 'DISTRIBUTE', 'NJ', 'OBJ', 'NJ', 'CORP', 'T1')

        stockholder = list(goal_abstract(db,'STOCKHOLDER', 'HOLDER-A', 'DE', 'T1'))
        assert len(stockholder) == 1
        assert db.query('NSHARES', stockholder[0]['P'], '?N')[0]['N'] == 500

    def test_two_equal_holders_split_evenly(self, db):
        _setup_stock_class(db, 'NJ', 'SRC-STOCK')
        _add_piece_owned(db, 'P-A', 'SRC-STOCK', 50, 'HOLDER-A', 'T1')
        _add_piece_owned(db, 'P-B', 'SRC-STOCK', 50, 'HOLDER-B', 'T1')
        _setup_stock_class(db, 'DE', 'DIST-STOCK')
        _add_piece_owned(db, 'OBJ', 'DIST-STOCK', 200, 'NJ', 'T1')
        db.assert_('DISTRIBUTION-RULE', 'OBJ', 'PRORATA', 'SRC-STOCK')

        assert_expand(db, 'DISTRIBUTE', 'NJ', 'OBJ', 'NJ', 'CORP', 'T1')

        stockholder_a = list(goal_abstract(db,'STOCKHOLDER', 'HOLDER-A', 'DE', 'T1'))
        stockholder_b = list(goal_abstract(db,'STOCKHOLDER', 'HOLDER-B', 'DE', 'T1'))
        n_a = db.query('NSHARES', stockholder_a[0]['P'], '?N')[0]['N']
        n_b = db.query('NSHARES', stockholder_b[0]['P'], '?N')[0]['N']
        assert n_a == 100
        assert n_b == 100

    def test_proportional_allocation(self, db):
        # A holds 1/4, B holds 3/4; distribute 400 shares.
        _setup_stock_class(db, 'NJ', 'SRC-STOCK')
        _add_piece_owned(db, 'P-A', 'SRC-STOCK', 25, 'HOLDER-A', 'T1')
        _add_piece_owned(db, 'P-B', 'SRC-STOCK', 75, 'HOLDER-B', 'T1')
        _setup_stock_class(db, 'DE', 'DIST-STOCK')
        _add_piece_owned(db, 'OBJ', 'DIST-STOCK', 400, 'NJ', 'T1')
        db.assert_('DISTRIBUTION-RULE', 'OBJ', 'PRORATA', 'SRC-STOCK')

        assert_expand(db, 'DISTRIBUTE', 'NJ', 'OBJ', 'NJ', 'CORP', 'T1')

        stockholder_a = list(goal_abstract(db,'STOCKHOLDER', 'HOLDER-A', 'DE', 'T1'))
        stockholder_b = list(goal_abstract(db,'STOCKHOLDER', 'HOLDER-B', 'DE', 'T1'))
        n_a = db.query('NSHARES', stockholder_a[0]['P'], '?N')[0]['N']
        n_b = db.query('NSHARES', stockholder_b[0]['P'], '?N')[0]['N']
        assert n_a == 100   # 1/4 * 400
        assert n_b == 300   # 3/4 * 400

    def test_obj_fully_distributed(self, db):
        _setup_stock_class(db, 'NJ', 'SRC-STOCK')
        _add_piece_owned(db, 'P-A', 'SRC-STOCK', 1, 'HOLDER-A', 'T1')
        _setup_stock_class(db, 'DE', 'DIST-STOCK')
        _add_piece_owned(db, 'OBJ', 'DIST-STOCK', 100, 'NJ', 'T1')
        db.assert_('DISTRIBUTION-RULE', 'OBJ', 'PRORATA', 'SRC-STOCK')

        assert_expand(db, 'DISTRIBUTE', 'NJ', 'OBJ', 'NJ', 'CORP', 'T1')

        remaining = db.query('NSHARES', 'OBJ', '?N')
        assert remaining[0]['N'] == 0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestDistributeEdgeCases:
    def test_no_rule_is_noop(self, db):
        _setup_stock_class(db, 'NJ', 'SRC-STOCK')
        _add_piece_owned(db, 'P-H', 'SRC-STOCK', 10, 'HOLDER-A', 'T1')
        _setup_stock_class(db, 'DE', 'DIST-STOCK')
        _add_piece_owned(db, 'OBJ', 'DIST-STOCK', 100, 'NJ', 'T1')
        # No DISTRIBUTION-RULE asserted.

        assert_expand(db, 'DISTRIBUTE', 'NJ', 'OBJ', 'NJ', 'CORP', 'T1')

        # No new OWN entries should exist for HOLDER-A.
        assert list(goal_abstract(db,'STOCKHOLDER', 'HOLDER-A', 'DE', 'T1')) == []

    def test_zero_share_holder_skipped(self, db):
        _setup_stock_class(db, 'NJ', 'SRC-STOCK')
        _add_piece_owned(db, 'P-A', 'SRC-STOCK', 0, 'HOLDER-A', 'T1')
        _add_piece_owned(db, 'P-B', 'SRC-STOCK', 10, 'HOLDER-B', 'T1')
        _setup_stock_class(db, 'DE', 'DIST-STOCK')
        _add_piece_owned(db, 'OBJ', 'DIST-STOCK', 20, 'NJ', 'T1')
        db.assert_('DISTRIBUTION-RULE', 'OBJ', 'N-FOR-ONE', 2, 'SRC-STOCK')

        assert_expand(db, 'DISTRIBUTE', 'NJ', 'OBJ', 'NJ', 'CORP', 'T1')

        # HOLDER-A (0 shares) gets nothing.
        assert list(goal_abstract(db,'STOCKHOLDER', 'HOLDER-A', 'DE', 'T1')) == []
        # HOLDER-B (10 shares) gets 2*10=20.
        stockholder_b = list(goal_abstract(db,'STOCKHOLDER', 'HOLDER-B', 'DE', 'T1'))
        assert len(stockholder_b) == 1


# ---------------------------------------------------------------------------
# Phellis-style scenario
# ---------------------------------------------------------------------------

class TestPhellisStyle:
    """2-for-1 Delaware common distribution to NJ common holders.

    NJ holds 500 shares of Delaware common (PHE31-PIECE).
    Phellis holds 250 NJ common shares; another holder holds 250.
    Rule: 2 Delaware shares per 1 NJ common share held.
    After distribution:
      - Phellis receives 500 shares of Delaware common.
      - Other holder receives 500 shares of Delaware common.
      - PHE31-PIECE NSHARES goes from 1000 to 0.
    """

    def test_phellis_2_for_1_distribution(self, db):
        # NJ common stock class.
        _setup_stock_class(db, 'NEW-JERSEY', 'NJ-COMMON')

        # Phellis holds 250 NJ common at T2.
        _add_piece_owned(db, 'PHELLIS-NJ', 'NJ-COMMON', 250, 'PHELLIS', 'T2')
        # Another holder also has 250 NJ common.
        _add_piece_owned(db, 'OTHER-NJ', 'NJ-COMMON', 250, 'OTHER', 'T2')

        # Delaware common stock class.
        _setup_stock_class(db, 'DELAWARE', 'DE-COMMON')

        # NJ holds 1000 shares of Delaware common as PHE31-PIECE.
        _add_piece_owned(db, 'PHE31-PIECE', 'DE-COMMON', 1000, 'NEW-JERSEY', 'T2')

        # Distribution rule: 2 Delaware shares per 1 NJ common share.
        db.assert_('DISTRIBUTION-RULE', 'PHE31-PIECE', 'N-FOR-ONE', 2, 'NJ-COMMON')

        assert_expand(
            db, 'DISTRIBUTE',
            'NEW-JERSEY', 'PHE31-PIECE', 'NEW-JERSEY', 'NEW-JERSEY', 'T2',
        )

        # Phellis should own 500 shares of Delaware common.
        phellis_stockholder_b = list(goal_abstract(db,'STOCKHOLDER', 'PHELLIS', 'DELAWARE', 'T2'))
        assert len(phellis_stockholder_b) == 1
        phellis_piece = phellis_stockholder_b[0]['P']
        assert db.query('NSHARES', phellis_piece, '?N')[0]['N'] == 500
        assert db.query('PIECE-OF', phellis_piece, 'DE-COMMON') == [{}]

        # Other holder also gets 500 shares.
        phellis_stockholder_b = list(goal_abstract(db,'STOCKHOLDER', 'OTHER', 'DELAWARE', 'T2'))
        assert len(phellis_stockholder_b) == 1
        other_piece = phellis_stockholder_b[0]['P']
        assert db.query('NSHARES', other_piece, '?N')[0]['N'] == 500

        # PHE31-PIECE fully distributed: 0 shares remaining.
        remaining = db.query('NSHARES', 'PHE31-PIECE', '?N')
        assert remaining[0]['N'] == 0
