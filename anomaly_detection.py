"""
Anomaly detection on SQL-engineered features: Isolation Forest vs a
simple threshold baseline.

Run from repo root (after build_features.py):  python anomaly_detection.py
Outputs: Images/anomaly_plot.png, Data/predictions.csv, metrics printed.

NOTE: data is SYNTHETIC. event_label is used ONLY to score results,
never as a model input. Results show the pipeline works, not that the
model works on real ponds.
"""
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import precision_score, recall_score, f1_score

ROOT = Path(__file__).parent
df = pd.read_csv(ROOT / "Data" / "features.csv", parse_dates=["ts"])

# ground truth (evaluation only)
y_true = (df["event_label"] != "none").astype(int)

# --- baseline: fixed threshold rules, set from general pond knowledge ---
baseline = (
    (df["turbidity"] > 20)
    | (df["ph"] < 6.9)
    | (df["ph"] > 8.2)
    | (df["temp_c"] < 20)
    | (df["temp_c"] > 30)
).astype(int)

# --- Isolation Forest on engineered features ---
FEATURES = [
    "temp_c", "ph", "turbidity",
    "temp_roll_1h", "ph_roll_1h", "turb_roll_1h",
    "temp_delta", "ph_delta", "turb_delta",
    "turb_dev_24h", "ph_dev_24h",
]
X = df[FEATURES].fillna(0)  # first row has no delta
X = StandardScaler().fit_transform(X)
iso = IsolationForest(n_estimators=200, contamination=0.07, random_state=42)
iforest = (iso.fit_predict(X) == -1).astype(int)

df["baseline_flag"] = baseline
df["iforest_flag"] = iforest

def report(name, y_pred):
    return {
        "method": name,
        "flagged": int(y_pred.sum()),
        "precision": round(precision_score(y_true, y_pred), 3),
        "recall": round(recall_score(y_true, y_pred), 3),
        "f1": round(f1_score(y_true, y_pred), 3),
    }

# event-level: was each injected event detected at least once?
df["event_id"] = (df["event_label"] != df["event_label"].shift()).cumsum()
ev = df[df["event_label"] != "none"]
def event_recall(col):
    return round(ev.groupby("event_id")[col].max().mean(), 3)

res = pd.DataFrame([report("threshold baseline", baseline),
                    report("isolation forest", iforest)])
res["event_level_recall"] = [event_recall("baseline_flag"), event_recall("iforest_flag")]
print(res.to_string(index=False))

df.to_csv(ROOT / "Data" / "predictions.csv", index=False)

# --- plot ---
fig, axes = plt.subplots(3, 1, figsize=(12, 8), sharex=True)
for ax, col, lab in zip(axes, ["temp_c", "ph", "turbidity"],
                        ["Temp (C)", "pH", "Turbidity"]):
    ax.plot(df["ts"], df[col], lw=0.6, color="steelblue")
    ax.scatter(df.loc[df["iforest_flag"] == 1, "ts"],
               df.loc[df["iforest_flag"] == 1, col],
               s=6, color="red", label="Isolation Forest flag")
    for _, g in ev.groupby("event_id"):
        ax.axvspan(g["ts"].min(), g["ts"].max(), color="orange", alpha=0.2)
    ax.set_ylabel(lab)
axes[0].legend(loc="upper right")
axes[0].set_title("Synthetic pond data: flags (red) vs injected events (orange)")
plt.tight_layout()
(ROOT / "Images").mkdir(exist_ok=True)
plt.savefig(ROOT / "Images" / "anomaly_plot.png", dpi=130)
print("saved Images/anomaly_plot.png")
