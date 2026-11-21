"""An isolated database for trying historical corrections."""

from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from .ledger import Ledger


def prepare_demo(path: Path, today: date) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory() as scratch:
        sample = Ledger(Path(scratch) / "sample.sqlite3")
        sample.save(today - timedelta(days=4), {"income": "1000,00 Зареждане на касата"})
        sample.save(today - timedelta(days=3), {
            "contract": "18001", "interest": "15", "principal": "80",
            "income": "30 Каса", "cost": "10 Консумативи",
        })
        sample.save(today - timedelta(days=2), {
            "marker": "1", "contract": "19001", "interest": "40", "principal": "100",
            "gold": "5 Златен пръстен", "pledge": "19010", "pledgeAmount": "70",
        })
        sample.save(today - timedelta(days=1), {
            "contract": "20001", "interest": "12", "principal": "60",
            "income": "15", "cost": "8", "buyGold": "25", "buySilver": "12",
        })
        sample.save(today, {"income": "20", "cost": "5"})
        sample.backup(path)
