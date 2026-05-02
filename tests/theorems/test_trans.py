"""
Tests for main/theorems/trans.py — TRANS and SPLITPIECE expand theorems.

TRANS(subject, obj, owner, recipient, time):
  - Records TRANS proposition.
  - Erases most recent (OWN owner obj T_prev).
  - Asserts (OWN recipient obj time).

SPLITPIECE(new_piece, old_piece, time):
  - Asserts (PIECE-OF new_piece S) where S = old_piece's stock class.
  - Decrements (NSHARES old_piece) by (NSHARES new_piece).

Coverage:
  TRANS
  - Registration
  - Basic transfer: TRANS fact stored, prior OWN erased, new OWN asserted
  - Transfer with no prior ownership: new OWN asserted without error
  - Transfer with time-free prior OWN: time-free entry erased
  - Multiple prior time-indexed entries: only last one erased
  - Owner equals recipient: OWN updated to same owner at new time
  - Transfer of freshly split piece (no prior OWN): OWN created
  SPLITPIECE
  - Registration
  - Basic split: PIECE-OF propagated, NSHARES decremented
  - Missing PIECE-OF on old_piece: no-op
  - Missing NSHARES on old_piece: no-op (PIECE-OF still set)
  - Missing NSHARES on new_piece: no-op after PIECE-OF set
"""
import pytest

from main.database import Database
from main.symbols import reset_gen
from main.theorems.base import EXPAND_THEOREMS, assert_expand
import main.theorems.trans  # noqa: F401 — registers TRANS and SPLITPIECE


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


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_trans_registered(self):
        assert 'TRANS' in EXPAND_THEOREMS

    def test_splitpiece_registered(self):
        assert 'SPLITPIECE' in EXPAND_THEOREMS

    def test_trans_callable(self):
        assert callable(EXPAND_THEOREMS['TRANS'])

    def test_splitpiece_callable(self):
        assert callable(EXPAND_THEOREMS['SPLITPIECE'])


# ---------------------------------------------------------------------------
# TRANS: basic ownership transfer
# ---------------------------------------------------------------------------

class TestTransBasic:
    def test_trans_fact_stored(self, db):
        db.assert_('OWN', 'OWNER-A', 'PIECE1', 'T0')
        assert_expand(db, 'TRANS', 'SUBJECT', 'PIECE1', 'OWNER-A', 'OWNER-B', 'T1')

        trans_rows = db.query('TRANS', 'SUBJECT', 'PIECE1', 'OWNER-A', 'OWNER-B', 'T1')
        assert trans_rows == [{}]

    def test_prior_own_erased(self, db):
        db.assert_('OWN', 'OWNER-A', 'PIECE1', 'T0')
        assert_expand(db, 'TRANS', 'SUBJECT', 'PIECE1', 'OWNER-A', 'OWNER-B', 'T1')

        assert db.query('OWN', 'OWNER-A', 'PIECE1', 'T0') == []

    def test_new_own_asserted(self, db):
        db.assert_('OWN', 'OWNER-A', 'PIECE1', 'T0')
        assert_expand(db, 'TRANS', 'SUBJECT', 'PIECE1', 'OWNER-A', 'OWNER-B', 'T1')

        assert db.query('OWN', 'OWNER-B', 'PIECE1', 'T1') == [{}]

    def test_only_transferred_piece_affected(self, db):
        # An unrelated piece should be unchanged.
        db.assert_('OWN', 'OWNER-A', 'PIECE1', 'T0')
        db.assert_('OWN', 'OWNER-A', 'PIECE2', 'T0')
        assert_expand(db, 'TRANS', 'SUBJECT', 'PIECE1', 'OWNER-A', 'OWNER-B', 'T1')

        assert db.query('OWN', 'OWNER-A', 'PIECE2', 'T0') == [{}]


# ---------------------------------------------------------------------------
# TRANS: no prior ownership
# ---------------------------------------------------------------------------

class TestTransNoPrior:
    def test_new_own_asserted_when_no_prior(self, db):
        assert_expand(db, 'TRANS', 'SUBJECT', 'PIECE1', 'OWNER-A', 'OWNER-B', 'T1')

        assert db.query('OWN', 'OWNER-B', 'PIECE1', 'T1') == [{}]

    def test_no_error_when_no_prior(self, db):
        # Should not raise even if owner never owned obj.
        assert_expand(db, 'TRANS', 'SUBJECT', 'PIECE1', 'OWNER-A', 'OWNER-B', 'T1')


# ---------------------------------------------------------------------------
# TRANS: time-free prior OWN
# ---------------------------------------------------------------------------

class TestTransTimeFreePrior:
    def test_time_free_own_erased(self, db):
        db.assert_('OWN', 'OWNER-A', 'PIECE1')
        assert_expand(db, 'TRANS', 'SUBJECT', 'PIECE1', 'OWNER-A', 'OWNER-B', 'T1')

        assert db.query('OWN', 'OWNER-A', 'PIECE1') == []

    def test_new_time_indexed_own_asserted(self, db):
        db.assert_('OWN', 'OWNER-A', 'PIECE1')
        assert_expand(db, 'TRANS', 'SUBJECT', 'PIECE1', 'OWNER-A', 'OWNER-B', 'T1')

        assert db.query('OWN', 'OWNER-B', 'PIECE1', 'T1') == [{}]


# ---------------------------------------------------------------------------
# TRANS: multiple prior OWN entries
# ---------------------------------------------------------------------------

class TestTransMultiplePrior:
    def test_last_entry_erased(self, db):
        # T0 then T1 asserted — T1 is the most recent; T1 should be erased.
        db.assert_('OWN', 'OWNER-A', 'PIECE1', 'T0')
        db.assert_('OWN', 'OWNER-A', 'PIECE1', 'T1')
        assert_expand(db, 'TRANS', 'SUBJECT', 'PIECE1', 'OWNER-A', 'OWNER-B', 'T2')

        assert db.query('OWN', 'OWNER-A', 'PIECE1', 'T1') == []

    def test_earlier_entry_preserved(self, db):
        # T0 entry should remain (only T1 is erased).
        db.assert_('OWN', 'OWNER-A', 'PIECE1', 'T0')
        db.assert_('OWN', 'OWNER-A', 'PIECE1', 'T1')
        assert_expand(db, 'TRANS', 'SUBJECT', 'PIECE1', 'OWNER-A', 'OWNER-B', 'T2')

        assert db.query('OWN', 'OWNER-A', 'PIECE1', 'T0') == [{}]


# ---------------------------------------------------------------------------
# TRANS: owner equals recipient
# ---------------------------------------------------------------------------

class TestTransSameOwner:
    def test_own_updated_to_new_time(self, db):
        db.assert_('OWN', 'OWNER-A', 'PIECE1', 'T0')
        assert_expand(db, 'TRANS', 'SUBJECT', 'PIECE1', 'OWNER-A', 'OWNER-A', 'T1')

        assert db.query('OWN', 'OWNER-A', 'PIECE1', 'T0') == []
        assert db.query('OWN', 'OWNER-A', 'PIECE1', 'T1') == [{}]


# ---------------------------------------------------------------------------
# TRANS: fresh piece (created by SPLITPIECE) has no prior OWN
# ---------------------------------------------------------------------------

class TestTransFreshPiece:
    def test_own_created_for_new_piece(self, db):
        # Simulates what DISTRIBUTE does: SPLITPIECE makes a piece, TRANS assigns it.
        # No prior OWN for the new piece.
        assert_expand(db, 'TRANS', 'NJ', 'PHE-NEW', 'NJ', 'PHELLIS', 'T3')

        assert db.query('OWN', 'PHELLIS', 'PHE-NEW', 'T3') == [{}]


# ---------------------------------------------------------------------------
# SPLITPIECE: basic split
# ---------------------------------------------------------------------------

class TestSplitpieceBasic:
    def test_piece_of_propagated(self, db):
        db.assert_('PIECE-OF', 'OLD', 'STOCK-S1')
        db.assert_('NSHARES', 'OLD', 100)
        db.assert_('NSHARES', 'NEW', 30)
        assert_expand(db, 'SPLITPIECE', 'NEW', 'OLD', 'T1')

        assert db.query('PIECE-OF', 'NEW', 'STOCK-S1') == [{}]

    def test_nshares_decremented(self, db):
        db.assert_('PIECE-OF', 'OLD', 'STOCK-S1')
        db.assert_('NSHARES', 'OLD', 100)
        db.assert_('NSHARES', 'NEW', 30)
        assert_expand(db, 'SPLITPIECE', 'NEW', 'OLD', 'T1')

        result = db.query('NSHARES', 'OLD', '?N')
        assert len(result) == 1
        assert result[0]['N'] == 70

    def test_old_nshares_entry_replaced(self, db):
        db.assert_('PIECE-OF', 'OLD', 'STOCK-S1')
        db.assert_('NSHARES', 'OLD', 100)
        db.assert_('NSHARES', 'NEW', 30)
        assert_expand(db, 'SPLITPIECE', 'NEW', 'OLD', 'T1')

        assert db.query('NSHARES', 'OLD', 100) == []

    def test_new_nshares_unchanged(self, db):
        db.assert_('PIECE-OF', 'OLD', 'STOCK-S1')
        db.assert_('NSHARES', 'OLD', 100)
        db.assert_('NSHARES', 'NEW', 30)
        assert_expand(db, 'SPLITPIECE', 'NEW', 'OLD', 'T1')

        result = db.query('NSHARES', 'NEW', '?M')
        assert result[0]['M'] == 30

    def test_split_entire_piece(self, db):
        db.assert_('PIECE-OF', 'OLD', 'STOCK-S1')
        db.assert_('NSHARES', 'OLD', 50)
        db.assert_('NSHARES', 'NEW', 50)
        assert_expand(db, 'SPLITPIECE', 'NEW', 'OLD', 'T1')

        result = db.query('NSHARES', 'OLD', '?N')
        assert len(result) == 1
        assert result[0]['N'] == 0


# ---------------------------------------------------------------------------
# SPLITPIECE: missing prerequisites
# ---------------------------------------------------------------------------

class TestSplitpieceMissing:
    def test_no_piece_of_is_noop(self, db):
        # old_piece has no PIECE-OF entry — should not raise or write anything.
        db.assert_('NSHARES', 'OLD', 100)
        db.assert_('NSHARES', 'NEW', 30)
        assert_expand(db, 'SPLITPIECE', 'NEW', 'OLD', 'T1')

        assert db.query('PIECE-OF', 'NEW', '?S') == []
        # NSHARES of OLD should be unchanged.
        assert db.query('NSHARES', 'OLD', 100) == [{}]

    def test_no_old_nshares_leaves_piece_of(self, db):
        # PIECE-OF should still be set even if NSHARES of old_piece is missing.
        db.assert_('PIECE-OF', 'OLD', 'STOCK-S1')
        db.assert_('NSHARES', 'NEW', 30)
        assert_expand(db, 'SPLITPIECE', 'NEW', 'OLD', 'T1')

        assert db.query('PIECE-OF', 'NEW', 'STOCK-S1') == [{}]

    def test_no_new_nshares_leaves_piece_of(self, db):
        db.assert_('PIECE-OF', 'OLD', 'STOCK-S1')
        db.assert_('NSHARES', 'OLD', 100)
        # new_piece has no NSHARES yet — no decrement should happen.
        assert_expand(db, 'SPLITPIECE', 'NEW', 'OLD', 'T1')

        assert db.query('PIECE-OF', 'NEW', 'STOCK-S1') == [{}]
        assert db.query('NSHARES', 'OLD', 100) == [{}]
