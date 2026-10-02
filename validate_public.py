"""
Run the same pipeline on REAL pond sensor data (KU-MWQ dataset).

Dataset: Nahid et al., "KU-MWQ: A Dataset for Monitoring Water Quality
Using Digital Sensors", Mendeley Data, DOI 10.17632/34rczh25kc.4
Real Arduino sensors in a fish pond, Khulna University, Jan 2020.
File used: Data/public/Sensor data for 30 cm.xlsx

The dataset has NO anomaly labels, so there is no precision/recall here.
We check: what gets flagged, do methods agree, do flags look physical.

Run from repo root:  python validate_public.py
"""
import sqlite3
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).parent
SRC = ROOT / "Data" / "Public" / "Sensor data for 30 cm.xlsx"
DB = ROOT / "Data" / "koi_public.db"

# --- 1) load + clean ---
raw = pd.read_excel(SRC)
raw.columns = ["timestamp", "temp_c", "ph", "turbidity"]
raw["timestamp"] = pd.to_datetime(raw["timestamp"])
raw = raw.sort_values("timestamp").drop_duplicates("timestamp")  # 2 rows were out of order

# --- 2) resample ~1/min readings to 10-min medians ---
# so the SAME SQL (6 rows = 1h, 144 rows = 24h) works unchanged
res = (raw.set_index("timestamp")
          .resample("10min").median()
          .reset_index())
res["timestamp"] = res["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%S")
n_empty = int(res[["temp_c", "ph", "turbidity"]].isna().any(axis=1).sum())

# --- 3) reuse SQL/features.sql unchanged (events table left empty: no labels) ---
con = sqlite3.connect(DB)
res.to_sql("readings", con, if_exists="replace", index=False)
pd.DataFrame(columns=["event_type", "start", "end"]).to_sql(
    "events", con, if_exists="replace", index=False)
con.executescript((ROOT / "SQL" / "features.sql").read_text())
df = pd.read_sql("SELECT * FROM features ORDER BY ts", con, parse_dates=["ts"])
con.close()

# --- 4) detectors ---
# baseline: global z-score. (Fixed pond thresholds were unusable: turbidity
# here is 194-249 NTU, so any 'turbidity > 20' rule flags every reading.)
z = (df[["temp_c", "ph", "turbidity"]] - df[["temp_c", "ph", "turbidity"]].mean()) \
    / df[["temp_c", "ph", "turbidity"]].std()
df["baseline_flag"] = (z.abs() > 3).any(axis=1).astype(int)

FEATURES = ["temp_c", "ph", "turbidity",
            "temp_roll_1h", "ph_roll_1h", "turb_roll_1h",
            "temp_delta", "ph_delta", "turb_delta",
            "turb_dev_24h", "ph_dev_24h"]
X = StandardScaler().fit_transform(df[FEATURES].fillna(0))
# contamination is an operating choice on unlabeled data: flag the top 1%
iso = IsolationForest(n_estimators=200, contamination=0.01, random_state=42)
df["iforest_flag"] = (iso.fit_predict(X) == -1).astype(int)

# --- 5) summary ---
both = int(((df.baseline_flag == 1) & (df.iforest_flag == 1)).sum())
either = int(((df.baseline_flag == 1) | (df.iforest_flag == 1)).sum())
print(f"raw rows: {len(raw)}  ->  10-min rows: {len(res)} "
      f"({n_empty} empty bins dropped by SQL)  ->  feature rows: {len(df)}")
print(f"time span: {df.ts.min()}  to  {df.ts.max()}")
print(f"z-score baseline flags:   {int(df.baseline_flag.sum())}")
print(f"isolation forest flags:   {int(df.iforest_flag.sum())}")
print(f"flagged by both: {both}   overlap (Jaccard): {both / max(either, 1):.2f}")
print("\nIsolation Forest flags by hour of day:")
print(df[df.iforest_flag == 1].ts.dt.hour.value_counts().sort_index().to_string())
print("\nIsolation Forest flags by day:")
print(df[df.iforest_flag == 1].ts.dt.date.value_counts().sort_index().to_string())
df.to_csv(ROOT / "Data" / "predictions_public.csv", index=False)

# --- 6) plot ---
fig, axes = plt.subplots(3, 1, figsize=(12, 8), sharex=True)
for ax, col, lab in zip(axes, ["temp_c", "ph", "turbidity"],
                        ["Temp (C)", "pH", "Turbidity (NTU)"]):
    ax.plot(df["ts"], df[col], lw=0.7, color="steelblue")
    f = df[df.iforest_flag == 1]
    ax.scatter(f["ts"], f[col], s=14, color="red", label="Isolation Forest flag")
    b = df[df.baseline_flag == 1]
    ax.scatter(b["ts"], b[col], s=28, facecolors="none", edgecolors="green",
               label="z-score baseline flag")
    ax.set_ylabel(lab)
axes[0].legend(loc="upper right")
axes[0].set_title("REAL pond data (KU-MWQ, 30 cm sensors): flagged readings")
plt.tight_layout()
(ROOT / "Images").mkdir(exist_ok=True)
plt.savefig(ROOT / "Images" / "public_validation.png", dpi=130)
print("\nsaved Images/public_validation.png")
