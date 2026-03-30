"""
Tests for main/theorems/b_reorg.py — B-REORGANIZATION abstract theorem.

B-Reorganization (§368(a)(1)(B)):
  Acquisition by one corporation (A), solely in exchange for all or part of
  its voting stock, of stock of another corporation (C), such that immediately
  after the acquisition A controls C.

Key structural constraints:
  - A must be a CORPORATION
  - A must control C (≥80% voting + ≥80% all other) immediately after
  - A must have received stock of C (TRANS where recipient=A, obj is
    PIECE-OF a STOCK issued by C)
  - All consideration given by A to each counterparty O1 must be a piece
    of VOTING STOCK issued by A (solely-for-voting-stock requirement)

Phellis case queries (CLAUDE.md §5.5):
  - B-Reorg(NJ, DELAWARE) → fails: NJ gives assets, not NJ voting stock
  - B-Reorg(DELAWARE, NJ) → fails: DELAWARE never acquires NJ stock

Coverage:
  - Registration
  - Simple successful B-Reorg
  - Multiple counterparties each exchange for A's voting stock (success)
  - Fails when A is not a CORPORATION
  - Fails when A does not achieve ≥80% control
  - Fails when what A acquires is not stock of C (acquires C's assets)
  - Fails when no TRANS to A exists at all
  - Fails when consideration is non-voting stock of A
  - Fails when consideration includes both voting and non-voting stock of A
  - Fails when consideration is assets (not stock of A at all)
  - Fails when A gives nothing to the counterparty
  - Variable acquirer / target / time patterns
  - Deduplication: multiple CONTROL solutions yield one B-Reorg result
  - Direct DB entry bypasses theorem
  - Wrong arity yields nothing
  - Phellis-style: NJ/Delaware fails (assets as consideration)
  - Phellis-style: Delaware/NJ fails (no NJ stock acquired)
"""
import pytest

from main.database import Database
from main.theorems.base import ABSTRACT_THEOREMS, goal_abstract, assert_expand
import main.theorems.stockholder  # noqa: F401 — registers STOCKHOLDER
import main.theorems.control      # noqa: F401 — registers CONTROL (needs STOCKHOLDER)
import main.theorems.trans        # noqa: F401 — registers TRANS, SPLITPIECE
import main.theorems.b_reorg      # noqa: F401 — registers B-REORGANIZATION


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _setup_corp_stock(db: Database, corp: str, stock_sym: str, *, voting: bool = True) -> None:
    """Assert CORPORATION, ISSUE, STOCK, optionally VOTING, and COMMON."""
    db.assert_('CORPORATION', corp)
    db.assert_('ISSUE', corp, stock_sym)
    db.assert_('STOCK', stock_sym)
    if voting:
        db.assert_('VOTING', stock_sym)
    db.assert_('COMMON', stock_sym)


def _add_piece(
    db: Database,
    piece: str,
    stock_sym: str,
    n: int,
    *,
    owner: str | None = None,
    time: str | None = None,
) -> None:
    """Assert PIECE-OF, NSHARES, and optionally OWN(owner, piece, time)."""
    db.assert_('PIECE-OF', piece, stock_sym)
    db.assert_('NSHARES', piece, n)
    if owner is not None and time is not None:
        db.assert_('OWN', owner, piece, time)


def _setup_basic_b_reorg(db: Database) -> None:
    """
    Minimal successful B-Reorg:
      ACQUIRER receives 100% of TARGET's voting stock (P-C) from O1.
      ACQUIRER gives its own voting stock (P-A) to O1 in exchange.
      After T1: ACQUIRER controls TARGET (owns all of S-C).
    """
    _setup_corp_stock(db, 'ACQUIRER', 'S-A', voting=True)
    _setup_corp_stock(db, 'TARGET', 'S-C', voting=True)

    _add_piece(db, 'P-C', 'S-C', 100, owner='O1', time='T0')
    _add_piece(db, 'P-A', 'S-A', 100)  # no prior OWN — issued from treasury

    # O1 transfers P-C (TARGET stock) to ACQUIRER
    assert_expand(db, 'TRANS', 'O1', 'P-C', 'O1', 'ACQUIRER', 'T1')
    # ACQUIRER gives its own voting stock (P-A) to O1 as consideration
    assert_expand(db, 'TRANS', 'ACQUIRER', 'P-A', 'ACQUIRER', 'O1', 'T1')


@pytest.fixture
def db() -> Database:
    return Database()


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_registered(self):
        assert 'B-REORGANIZATION' in ABSTRACT_THEOREMS

    def test_callable(self):
        assert callable(ABSTRACT_THEOREMS['B-REORGANIZATION'])


# ---------------------------------------------------------------------------
# Basic success
# ---------------------------------------------------------------------------

class TestBasicSuccess:
    def test_succeeds_with_full_acquisition(self, db):
        _setup_basic_b_reorg(db)
        results = list(goal_abstract(db, 'B-REORGANIZATION', 'ACQUIRER', 'TARGET', 'T1'))
        assert len(results) == 1

    def test_ground_args_yield_empty_binding(self, db):
        _setup_basic_b_reorg(db)
        results = list(goal_abstract(db, 'B-REORGANIZATION', 'ACQUIRER', 'TARGET', 'T1'))
        assert results == [{}]

    def test_multiple_counterparties_all_exchange_for_voting_stock(self, db):
        """Two shareholders of TARGET each exchange C stock for A voting stock."""
        _setup_corp_stock(db, 'ACQUIRER', 'S-A', voting=True)
        _setup_corp_stock(db, 'TARGET', 'S-C', voting=True)

        # O1 holds 60 shares, O2 holds 40 shares — ACQUIRER acquires 100%
        _add_piece(db, 'P-C1', 'S-C', 60, owner='O1', time='T0')
        _add_piece(db, 'P-C2', 'S-C', 40, owner='O2', time='T0')
        _add_piece(db, 'P-A1', 'S-A', 60)
        _add_piece(db, 'P-A2', 'S-A', 40)

        assert_expand(db, 'TRANS', 'O1', 'P-C1', 'O1', 'ACQUIRER', 'T1')
        assert_expand(db, 'TRANS', 'O2', 'P-C2', 'O2', 'ACQUIRER', 'T1')
        assert_expand(db, 'TRANS', 'ACQUIRER', 'P-A1', 'ACQUIRER', 'O1', 'T1')
        assert_expand(db, 'TRANS', 'ACQUIRER', 'P-A2', 'ACQUIRER', 'O2', 'T1')

        results = list(goal_abstract(db, 'B-REORGANIZATION', 'ACQUIRER', 'TARGET', 'T1'))
        assert len(results) == 1


# ---------------------------------------------------------------------------
# Acquirer is not a Corporation
# ---------------------------------------------------------------------------

class TestNotCorporation:
    def test_fails_when_acquirer_not_corporation(self, db):
        _setup_basic_b_reorg(db)
        db.erase('CORPORATION', 'ACQUIRER')

        results = list(goal_abstract(db, 'B-REORGANIZATION', 'ACQUIRER', 'TARGET', 'T1'))
        assert results == []


# ---------------------------------------------------------------------------
# Control not achieved
# ---------------------------------------------------------------------------

class TestNoControl:
    def test_fails_when_only_50_percent_acquired(self, db):
        """ACQUIRER takes only 50% of TARGET voting stock → no control → no B-Reorg."""
        _setup_corp_stock(db, 'ACQUIRER', 'S-A', voting=True)
        _setup_corp_stock(db, 'TARGET', 'S-C', voting=True)

        _add_piece(db, 'P-C1', 'S-C', 50, owner='O1', time='T0')
        _add_piece(db, 'P-C2', 'S-C', 50, owner='O2', time='T0')  # O2 retains 50%
        _add_piece(db, 'P-A1', 'S-A', 50)

        assert_expand(db, 'TRANS', 'O1', 'P-C1', 'O1', 'ACQUIRER', 'T1')
        assert_expand(db, 'TRANS', 'ACQUIRER', 'P-A1', 'ACQUIRER', 'O1', 'T1')

        results = list(goal_abstract(db, 'B-REORGANIZATION', 'ACQUIRER', 'TARGET', 'T1'))
        assert results == []

    def test_fails_just_below_80_percent(self, db):
        """79% ownership fails the control threshold → no B-Reorg."""
        _setup_corp_stock(db, 'ACQUIRER', 'S-A', voting=True)
        _setup_corp_stock(db, 'TARGET', 'S-C', voting=True)

        _add_piece(db, 'P-C1', 'S-C', 79, owner='O1', time='T0')
        _add_piece(db, 'P-C2', 'S-C', 21, owner='O2', time='T0')
        _add_piece(db, 'P-A1', 'S-A', 79)

        assert_expand(db, 'TRANS', 'O1', 'P-C1', 'O1', 'ACQUIRER', 'T1')
        assert_expand(db, 'TRANS', 'ACQUIRER', 'P-A1', 'ACQUIRER', 'O1', 'T1')

        results = list(goal_abstract(db, 'B-REORGANIZATION', 'ACQUIRER', 'TARGET', 'T1'))
        assert results == []


# ---------------------------------------------------------------------------
# What A acquires is not stock of C
# ---------------------------------------------------------------------------

class TestAcquiredNotStockOfC:
    def test_fails_when_a_acquires_c_assets_not_stock(self, db):
        """A acquires C's operating assets (no STOCK assertion) → no B-Reorg."""
        _setup_corp_stock(db, 'ACQUIRER', 'S-A', voting=True)
        db.assert_('CORPORATION', 'TARGET')

        # TARGET's asset — note: no STOCK assertion, so _is_stock_of returns False
        db.assert_('ASSET', 'TARGET-ASSETS')
        db.assert_('PIECE-OF', 'ASSET-P', 'TARGET-ASSETS')
        db.assert_('NSHARES', 'ASSET-P', 1)
        db.assert_('OWN', 'TARGET', 'ASSET-P', 'T0')

        _add_piece(db, 'P-A', 'S-A', 100)

        assert_expand(db, 'TRANS', 'TARGET', 'ASSET-P', 'TARGET', 'ACQUIRER', 'T1')
        assert_expand(db, 'TRANS', 'ACQUIRER', 'P-A', 'ACQUIRER', 'TARGET', 'T1')

        results = list(goal_abstract(db, 'B-REORGANIZATION', 'ACQUIRER', 'TARGET', 'T1'))
        assert results == []

    def test_fails_when_no_trans_to_acquirer_exists(self, db):
        """No TRANS to ACQUIRER at all → no acquisitions found → no B-Reorg."""
        _setup_corp_stock(db, 'ACQUIRER', 'S-A', voting=True)
        _setup_corp_stock(db, 'TARGET', 'S-C', voting=True)
        _add_piece(db, 'P-C', 'S-C', 100, owner='O1', time='T0')

        # No exchange — O1 never transfers to ACQUIRER
        results = list(goal_abstract(db, 'B-REORGANIZATION', 'ACQUIRER', 'TARGET', 'T1'))
        assert results == []


# ---------------------------------------------------------------------------
# Consideration not solely voting stock of A
# ---------------------------------------------------------------------------

class TestNotSolelyVotingStock:
    def test_fails_when_consideration_is_nonvoting_stock_of_a(self, db):
        """A gives only non-voting stock → fails solely-for-voting-stock."""
        _setup_corp_stock(db, 'ACQUIRER', 'S-A-NV', voting=False)
        _setup_corp_stock(db, 'TARGET', 'S-C', voting=True)

        _add_piece(db, 'P-C', 'S-C', 100, owner='O1', time='T0')
        _add_piece(db, 'P-A-NV', 'S-A-NV', 100)

        assert_expand(db, 'TRANS', 'O1', 'P-C', 'O1', 'ACQUIRER', 'T1')
        assert_expand(db, 'TRANS', 'ACQUIRER', 'P-A-NV', 'ACQUIRER', 'O1', 'T1')

        results = list(goal_abstract(db, 'B-REORGANIZATION', 'ACQUIRER', 'TARGET', 'T1'))
        assert results == []

    def test_fails_when_consideration_includes_nonvoting_stock(self, db):
        """A gives voting + non-voting stock as consideration → mixed → fails."""
        _setup_corp_stock(db, 'ACQUIRER', 'S-A', voting=True)
        db.assert_('ISSUE', 'ACQUIRER', 'S-A-NV')
        db.assert_('STOCK', 'S-A-NV')
        db.assert_('COMMON', 'S-A-NV')
        # No VOTING assertion for S-A-NV

        _setup_corp_stock(db, 'TARGET', 'S-C', voting=True)
        _add_piece(db, 'P-C', 'S-C', 100, owner='O1', time='T0')
        _add_piece(db, 'P-A', 'S-A', 80)
        _add_piece(db, 'P-A-NV', 'S-A-NV', 20)

        assert_expand(db, 'TRANS', 'O1', 'P-C', 'O1', 'ACQUIRER', 'T1')
        assert_expand(db, 'TRANS', 'ACQUIRER', 'P-A', 'ACQUIRER', 'O1', 'T1')
        assert_expand(db, 'TRANS', 'ACQUIRER', 'P-A-NV', 'ACQUIRER', 'O1', 'T1')

        results = list(goal_abstract(db, 'B-REORGANIZATION', 'ACQUIRER', 'TARGET', 'T1'))
        assert results == []

    def test_fails_when_consideration_is_assets_not_stock(self, db):
        """A gives operating assets (not stock) as consideration → fails."""
        _setup_corp_stock(db, 'ACQUIRER', 'S-A', voting=True)
        _setup_corp_stock(db, 'TARGET', 'S-C', voting=True)
        _add_piece(db, 'P-C', 'S-C', 100, owner='O1', time='T0')

        db.assert_('ASSET', 'ACQUIRER-ASSETS')
        db.assert_('PIECE-OF', 'ASSET-P', 'ACQUIRER-ASSETS')
        db.assert_('NSHARES', 'ASSET-P', 1)

        assert_expand(db, 'TRANS', 'O1', 'P-C', 'O1', 'ACQUIRER', 'T1')
        assert_expand(db, 'TRANS', 'ACQUIRER', 'ASSET-P', 'ACQUIRER', 'O1', 'T1')

        results = list(goal_abstract(db, 'B-REORGANIZATION', 'ACQUIRER', 'TARGET', 'T1'))
        assert results == []

    def test_fails_when_no_consideration_given_to_counterparty(self, db):
        """O1 transfers C stock to A but A gives O1 nothing in return → fails."""
        _setup_corp_stock(db, 'ACQUIRER', 'S-A', voting=True)
        _setup_corp_stock(db, 'TARGET', 'S-C', voting=True)
        _add_piece(db, 'P-C', 'S-C', 100, owner='O1', time='T0')

        assert_expand(db, 'TRANS', 'O1', 'P-C', 'O1', 'ACQUIRER', 'T1')
        # No TRANS from ACQUIRER to O1

        results = list(goal_abstract(db, 'B-REORGANIZATION', 'ACQUIRER', 'TARGET', 'T1'))
        assert results == []


# ---------------------------------------------------------------------------
# Variable patterns
# ---------------------------------------------------------------------------

class TestVariablePatterns:
    def test_variable_acquirer(self, db):
        _setup_basic_b_reorg(db)
        results = list(goal_abstract(db, 'B-REORGANIZATION', '?A', 'TARGET', 'T1'))
        assert len(results) == 1
        assert results[0]['A'] == 'ACQUIRER'

    def test_variable_target(self, db):
        _setup_basic_b_reorg(db)
        results = list(goal_abstract(db, 'B-REORGANIZATION', 'ACQUIRER', '?C', 'T1'))
        assert len(results) == 1
        assert results[0]['C'] == 'TARGET'

    def test_variable_time(self, db):
        _setup_basic_b_reorg(db)
        results = list(goal_abstract(db, 'B-REORGANIZATION', 'ACQUIRER', 'TARGET', '?T'))
        assert len(results) == 1
        assert results[0]['T'] == 'T1'

    def test_all_variables(self, db):
        _setup_basic_b_reorg(db)
        results = list(goal_abstract(db, 'B-REORGANIZATION', '?A', '?C', '?T'))
        assert len(results) == 1
        r = results[0]
        assert r['A'] == 'ACQUIRER'
        assert r['C'] == 'TARGET'
        assert r['T'] == 'T1'


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

class TestDeduplication:
    def test_multiple_stock_classes_yield_one_result(self, db):
        """TARGET has two voting classes; CONTROL yields once per class via
        STOCKHOLDER, but B-REORGANIZATION must deduplicate to one result."""
        _setup_corp_stock(db, 'ACQUIRER', 'S-A', voting=True)
        _setup_corp_stock(db, 'TARGET', 'S-C1', voting=True)
        db.assert_('ISSUE', 'TARGET', 'S-C2')
        db.assert_('STOCK', 'S-C2')
        db.assert_('VOTING', 'S-C2')
        db.assert_('COMMON', 'S-C2')

        _add_piece(db, 'P-C1', 'S-C1', 100, owner='O1', time='T0')
        _add_piece(db, 'P-C2', 'S-C2', 100, owner='O1', time='T0')
        _add_piece(db, 'P-A1', 'S-A', 200)

        assert_expand(db, 'TRANS', 'O1', 'P-C1', 'O1', 'ACQUIRER', 'T1')
        assert_expand(db, 'TRANS', 'O1', 'P-C2', 'O1', 'ACQUIRER', 'T1')
        assert_expand(db, 'TRANS', 'ACQUIRER', 'P-A1', 'ACQUIRER', 'O1', 'T1')

        results = list(goal_abstract(db, 'B-REORGANIZATION', 'ACQUIRER', 'TARGET', 'T1'))
        assert len(results) == 1


# ---------------------------------------------------------------------------
# Direct DB bypass
# ---------------------------------------------------------------------------

class TestDirectDBBypass:
    def test_direct_entry_returned_without_running_theorem(self, db):
        db.assert_('B-REORGANIZATION', 'A', 'C', 'T0')
        results = list(goal_abstract(db, 'B-REORGANIZATION', 'A', 'C', 'T0'))
        assert results == [{}]

    def test_direct_entry_with_variable(self, db):
        db.assert_('B-REORGANIZATION', 'A', 'C', 'T0')
        results = list(goal_abstract(db, 'B-REORGANIZATION', '?A', 'C', 'T0'))
        assert results == [{'A': 'A'}]


# ---------------------------------------------------------------------------
# Wrong arity
# ---------------------------------------------------------------------------

class TestWrongArity:
    def test_zero_args_yields_nothing(self, db):
        assert list(ABSTRACT_THEOREMS['B-REORGANIZATION'](db)) == []

    def test_two_args_yields_nothing(self, db):
        assert list(ABSTRACT_THEOREMS['B-REORGANIZATION'](db, 'A', 'C')) == []

    def test_four_args_yields_nothing(self, db):
        assert list(ABSTRACT_THEOREMS['B-REORGANIZATION'](db, 'A', 'C', 'T', 'EXTRA')) == []


# ---------------------------------------------------------------------------
# Phellis-style cases (CLAUDE.md §5.5)
# ---------------------------------------------------------------------------

class TestPhellisStyle:
    def _setup(self, db):
        """
        Simplified Phellis reorganization:
          - DELAWARE issues all its common voting stock (DE-PIECE) to NJ.
          - NJ transfers its operating assets (NJ-ASSET-P) to DELAWARE in return.
          - After T1: NJ owns 100% of DELAWARE → NJ controls DELAWARE.
          - NJ gave *assets*, not NJ voting stock → B-Reorg(NJ, DE) fails.
          - NJ issued no stock in this scenario → B-Reorg(DE, NJ) also fails.
        """
        db.assert_('CORPORATION', 'NEW-JERSEY')
        db.assert_('CORPORATION', 'DELAWARE')

        # DELAWARE's only voting stock class
        db.assert_('ISSUE', 'DELAWARE', 'DE-COMMON')
        db.assert_('STOCK', 'DE-COMMON')
        db.assert_('VOTING', 'DE-COMMON')
        db.assert_('COMMON', 'DE-COMMON')
        db.assert_('PIECE-OF', 'DE-PIECE', 'DE-COMMON')
        db.assert_('NSHARES', 'DE-PIECE', 100)
        db.assert_('OWN', 'DELAWARE', 'DE-PIECE', 'T0')

        # NJ's operating assets — not voting stock of NJ
        db.assert_('ASSET', 'NJ-ASSETS')
        db.assert_('PIECE-OF', 'NJ-ASSET-P', 'NJ-ASSETS')
        db.assert_('NSHARES', 'NJ-ASSET-P', 1000)
        db.assert_('OWN', 'NEW-JERSEY', 'NJ-ASSET-P', 'T0')

        # DELAWARE transfers its stock to NJ (NJ acquires all DE voting stock)
        assert_expand(db, 'TRANS', 'DELAWARE', 'DE-PIECE', 'DELAWARE', 'NEW-JERSEY', 'T1')
        # NJ gives assets to DELAWARE — not NJ voting stock
        assert_expand(db, 'TRANS', 'NEW-JERSEY', 'NJ-ASSET-P', 'NEW-JERSEY', 'DELAWARE', 'T1')

    def test_nj_acquirer_delaware_target_fails_not_solely_voting_stock(self, db):
        """
        B-Reorg(NJ, DELAWARE): NJ controls DELAWARE after ✓, NJ received
        Delaware stock ✓, but NJ gave assets (not NJ voting stock) to DELAWARE ✗.
        """
        self._setup(db)
        results = list(goal_abstract(
            db, 'B-REORGANIZATION', 'NEW-JERSEY', 'DELAWARE', '?T',
        ))
        assert results == []

    def test_delaware_acquirer_nj_target_fails_no_nj_stock_acquired(self, db):
        """
        B-Reorg(DELAWARE, NJ): NJ has no stock issued, DELAWARE cannot control
        NJ → CONTROL(DELAWARE, NJ) fails → no B-Reorg.
        """
        self._setup(db)
        results = list(goal_abstract(
            db, 'B-REORGANIZATION', 'DELAWARE', 'NEW-JERSEY', '?T',
        ))
        assert results == []
