# Local cash ledger implementation plan

**Goal**. Run the agreed cashier screen locally with SQLite persistence. The specification is the reviewed desktop mockup and the confirmed example day in this chat.

**Architecture**. Python validates a draft and saves the four blocks in one SQLite transaction. Qt Quick displays the daily snapshot in 14 aligned columns and positions independently stored records by index within each block. Money and weights use integer hundredths.

1. **Database and rules**. In `cash_ledger/ledger.py`, implement `Ledger.save(day, fields)`, `Ledger.day(day)`, `Ledger.set_opening_cash(value)` and `weight_error(fields)`. Cover the confirmed example totals, close and reopen, history, one weight per tag, and rollback when a draft is invalid.
2. **Desktop window**. In `cash_ledger/desktop.py` and `cash_ledger/Main.qml`, load and save through the database, show opening cash, preserve Enter shortcuts, warn as soon as a second weight field is filled, and display the calculated sale price under its weight. Exercise the real application window against a temporary database, including the entry and save controls.
3. **Run locally**. Install Qt in the project's virtual environment, run all tests, and start the window against a fresh local database. The Java checkout serves as a reference. Real data, hosting, and platform packaging are outside this first run.
