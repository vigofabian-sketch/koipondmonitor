"""
Load synthetic readings + events into SQLite, run SQL/features.sql,
export Data/features.csv.

Run from the repo root:  python build_features.py
"""
import sqlite3
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).parent
DB = ROOT / "Data" / "koi.db"

readings = pd.read_csv(ROOT / "Data" / "synthetic_readings.csv")
events = pd.read_csv(ROOT / "Data" / "events.csv")

con = sqlite3.connect(DB)
readings.to_sql("readings", con, if_exists="replace", index=False)
events.to_sql("events", con, if_exists="replace", index=False)

con.executescript((ROOT / "SQL" / "features.sql").read_text())

feats = pd.read_sql("SELECT * FROM features ORDER BY ts", con)
feats.to_csv(ROOT / "Data" / "features.csv", index=False)
con.close()

print(f"raw rows:      {len(readings)}")
print(f"clean rows:    {len(feats)}  (dropped {len(readings) - len(feats)} faulty/missing)")
print("\nrows per event label:")
print(feats["event_label"].value_counts().to_string())
print("\nfeature columns:")
print(", ".join(feats.columns))
