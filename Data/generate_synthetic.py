"""
Synthetic koi pond sensor data generator.

Produces 30 days of readings every 10 minutes, matching the Arduino
sketch output format (timestamp,temp_c,ph,turbidity), plus a labeled
event log. DATA IS SYNTHETIC. It demonstrates the pipeline, not real
pond behaviour.

Run:  python generate_synthetic.py
Out:  synthetic_readings.csv, events.csv (same folder as this script)
"""
from pathlib import Path
import numpy as np
import pandas as pd

SEED = 42
DAYS = 30
STEP_MIN = 10
START = "2026-10-01 00:00:00"

rng = np.random.default_rng(SEED)
out_dir = Path(__file__).parent

# --- time index ---
idx = pd.date_range(START, periods=DAYS * 24 * 60 // STEP_MIN, freq=f"{STEP_MIN}min")
n = len(idx)
hours = np.asarray(idx.hour + idx.minute / 60, dtype=float)

# --- baselines ---
# temp: daily cycle, warmest ~15:00, plus slow weather drift and noise
temp = 26 + 2.5 * np.sin(2 * np.pi * (hours - 9) / 24)
temp += np.cumsum(rng.normal(0, 0.01, n))
temp += rng.normal(0, 0.15, n)

# pH: slow drift around 7.4, small daily swing (photosynthesis), noise
ph = 7.4 + 0.15 * np.sin(2 * np.pi * (hours - 10) / 24)
ph += np.cumsum(rng.normal(0, 0.003, n))
ph += rng.normal(0, 0.03, n)

# turbidity (NTU-like): low baseline with noise
turb = 8 + rng.normal(0, 0.8, n)

# --- injected events (label: type, start index, duration in steps) ---
events = []

def add_event(kind, day, hour, dur_hours):
    start = int((day * 24 + hour) * 60 / STEP_MIN)
    dur = int(dur_hours * 60 / STEP_MIN)
    end = min(start + dur, n)
    t = np.arange(end - start)
    decay = np.exp(-t / (dur / 3))  # sharp onset, slow recovery
    if kind == "heavy_rain":
        turb[start:end] += 35 * decay
        ph[start:end] -= 0.5 * decay
        temp[start:end] -= 1.5 * decay
    elif kind == "water_change":
        turb[start:end] += 20 * decay
        ph[start:end] += (7.4 - ph[start:end]) * 0.5 * decay
        temp[start:end] -= 2.0 * decay
    elif kind == "overfeeding":
        turb[start:end] += 15 * (1 - np.exp(-t / (dur / 4))) * decay**0.3
        ph[start:end] -= 0.35 * (1 - np.exp(-t / (dur / 4)))
    events.append({
        "event_type": kind,
        "start": idx[start],
        "end": idx[end - 1],
    })

add_event("water_change", day=4,  hour=9,  dur_hours=6)
add_event("heavy_rain",   day=9,  hour=15, dur_hours=8)
add_event("overfeeding",  day=14, hour=12, dur_hours=10)
add_event("water_change", day=19, hour=9,  dur_hours=6)
add_event("heavy_rain",   day=23, hour=18, dur_hours=8)
add_event("overfeeding",  day=27, hour=12, dur_hours=10)

# --- clip to physical ranges ---
temp = np.clip(temp, 15, 35)
ph = np.clip(ph, 0, 14)
turb = np.clip(turb, 0, 100)

df = pd.DataFrame({
    "timestamp": idx.strftime("%Y-%m-%dT%H:%M:%S"),
    "temp_c": temp.round(2),
    "ph": ph.round(2),
    "turbidity": turb.round(2),
})

# --- sensor faults (so the cleaning step has real work to do) ---
# 1) dropped readings (missing values)
drop = rng.choice(n, size=int(0.01 * n), replace=False)
df.loc[drop, ["temp_c", "ph", "turbidity"]] = np.nan
# 2) DS18B20 disconnect glitch: -127.00 (the real sensor error value)
glitch = rng.choice(n, size=8, replace=False)
df.loc[glitch, "temp_c"] = -127.00

df.to_csv(out_dir / "synthetic_readings.csv", index=False)
pd.DataFrame(events).to_csv(out_dir / "events.csv", index=False)

print(f"Wrote {len(df)} rows -> synthetic_readings.csv")
print(f"Wrote {len(events)} events -> events.csv")
print(df.describe().round(2))
