## Practical Session Structure

- [X] Session 1: Database + tests. Tell Claude Code: "Implement taxman/database.py and tests/test_database.py per the spec in AGENTS.md and CLAUDE.md §2. Do not touch any other files." Validate, commit.
    - [X] Read code, updated DECISIONS.md, and unit tests, ensuring understanding and that everything makes sense
- [X] Session 2: symbols.py + prog.py + tests. Then ask Claude Code to update DECISIONS.md with any choices it made.
    - [X] Validate output (run pytest tests/ -v and confirm all pass before Session 3)
- [X] Session 3: theorems/stockholder.py + tests. (Note: no separate theorems/base.py — registries live in prog.py per DECISIONS.md)
    - [X] Validate output
- [X] Session 4: control.py + tests.
    - [] Validate output
- [X] Session 5: trans.py + distribute.py + tests.
- [X] Session 6: b_reorg.py + tests/test_b_reorg.py.
- [X] Sessions 7–8: One reorganization type per session (C, D).
- [] Session 9: Load the Phellis case (main/cases/phellis.py) and run end-to-end assertions against main/cases/phellis_expected.py