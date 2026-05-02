"""
Expected outcomes for the Phellis case (United States v. Phellis, 257 U.S. 156).

These constants define the ground-truth legal conclusions that the TAXMAN
system must derive from the Phellis fact database (main/cases/phellis.py).
Each constant is used directly in tests/test_phellis.py.

Sources: CLAUDE.md §5.5 (queries and expected results), §8 (case data).
"""

# ------------------------------------------------------------------
# B-Reorganization (§368(a)(1)(B))
# ------------------------------------------------------------------

# DELAWARE never acquires NJ stock in any TRANS → CONTROL(DE, NJ) cannot
# be established → B-Reorg(DE, NJ) fails immediately.
B_REORG_DELAWARE_ACQUIRES_NJ: bool = False

# NJ does acquire DE stock (PHE29, PHE31) and NJ controls DE at T1 ✓.
# However, what NJ gives DE in exchange is PHE26 (operating assets, not
# NJ voting stock) → "solely for voting stock" requirement fails.
B_REORG_NJ_ACQUIRES_DELAWARE: bool = False

# ------------------------------------------------------------------
# C-Reorganization (§368(a)(1)(C))
# ------------------------------------------------------------------

# DELAWARE acquires NJ's assets (PHE26, a non-stock property piece) and
# gives NJ solely DE voting stock (PHE29 debenture + PHE31 common, both
# stipulated VOTING) in exchange → C-Reorg(DE, NJ) succeeds.
C_REORG_ACQUIRER: str = 'DELAWARE'
C_REORG_ACQUIRED: str = 'NEW-JERSEY'

# ------------------------------------------------------------------
# D-Reorganization (§368(a)(1)(D)) — partial (no distribution check)
# ------------------------------------------------------------------

# NJ transfers its operating assets (PHE26, property) to DELAWARE (T1),
# and NJ controls DELAWARE immediately after (owns 100% of DE stock at T1)
# → D-Reorg(NJ, DE) succeeds.
D_REORG_TRANSFEROR: str = 'NEW-JERSEY'
D_REORG_TRANSFEREE: str = 'DELAWARE'

# ------------------------------------------------------------------
# Control
# ------------------------------------------------------------------

# After the reorganization events at T1 (DE issues PHE29 + PHE31 to NJ),
# NJ owns 100% of DE's voting stock → CONTROL(NJ, DE, T1) holds.
# Checked at T1, before the T2 distribution reduces NJ's DE common
# holdings to 0 shares (see DECISIONS.md for time-model rationale).
NJ_CONTROLS_DELAWARE: bool = True
NJ_CONTROLS_DELAWARE_AT: str = 'T1'

# ------------------------------------------------------------------
# Post-distribution stockholder status
# ------------------------------------------------------------------

# After the DISTRIBUTE event at T2, Phellis receives 500 shares of DE
# common (2-for-1 on his 250 NJ common shares) → Phellis is a
# stockholder of DELAWARE at T2.
PHELLIS_IS_DELAWARE_STOCKHOLDER: bool = True
PHELLIS_IS_DELAWARE_STOCKHOLDER_AT: str = 'T2'
