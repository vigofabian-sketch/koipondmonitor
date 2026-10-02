# koipondmonitor

Pond water-quality monitoring pipeline: simulated Arduino sensor circuit, SQL feature engineering, anomaly detection, and a dashboard.

> **Hardware is simulated (Wokwi). Data is synthetic. Not deployed.**
> This repo demonstrates a working pipeline. It does not claim results on a real pond.

## Why
My family keeps koi and an orchard. Water quality (temperature, pH, turbidity) drives fish health. I wanted to design the full monitoring chain, from sensor to alert, before building it for real.

## Pipeline
```
Arduino sensors (simulated) -> CSV -> SQLite -> SQL features -> anomaly detection -> dashboard
```

| Step | File |
|---|---|
| Sensor circuit + logging sketch (Wokwi) | `Hardware/` |
| Synthetic data + event log | `Data/generate_synthetic.py` |
| Cleaning + feature engineering (SQL window functions) | `SQL/features.sql`, `build_features.py` |
| Isolation Forest vs threshold baseline | `anomaly_detection.py` |
| Dashboard | `dashboard.py` |

## Hardware (simulated)
- Arduino Uno, DS18B20 temperature sensor (4.7k pull-up), DS1307 RTC
- Two potentiometers stand in for the pH and turbidity probes (analog, A0 and A1)
- Sketch prints `timestamp,temp_c,ph,turbidity` rows
- Real deployment would swap in an analog pH probe and a turbidity sensor, plus an SD card module

## Data
- `generate_synthetic.py` makes 30 days of readings every 10 minutes (seed 42)
- 6 injected, labeled events: 2 water changes, 2 heavy rains, 2 overfeedings
- Built-in faults: ~1% missing readings and 8 `-127.00` DS18B20 disconnect glitches

## Features (SQL)
Cleaning view, then 1h and 24h rolling means, reading-to-reading change, daily min/max, and deviation from the 24h mean, all with SQLite window functions. Events are joined as a label **for scoring only**, never as a model input.

## Results (synthetic data)
| Method | Precision | Recall | F1 | Events detected |
|---|---|---|---|---|
| Threshold baseline | 0.63 | 0.27 | 0.38 | 6/6 |
| Isolation Forest | 0.69 | 0.73 | 0.71 | 6/6 |

![Anomaly plot](Images/anomaly_plot.png)

Both methods detect every event at least once. Isolation Forest flags far more of each event's duration at similar precision.

## Limitations
- **Synthetic data.** The model finds anomalies I injected. This shows the pipeline works, not that it works on a real pond.
- **False positives early on.** The first days are flagged because the generator's pH drifts high there. The model flags "unusual", not "bad".
- **Contamination is set to 0.07**, close to the true event rate (~6.6%). That is prior knowledge a real deployment would not have.
- **Baseline thresholds were chosen by hand**, so the comparison depends on them.
- Rolling windows are short at the start of the series.

## Run it
```
pip install -r requirements.txt
python Data/generate_synthetic.py
python build_features.py
python anomaly_detection.py
streamlit run dashboard.py
```

## Next steps
- Validate on a public aquaculture water quality dataset
- Build the real hardware (pH probe calibration, SD logging, waterproof enclosure) and collect real pond data
- Add alert rules and a notification path
