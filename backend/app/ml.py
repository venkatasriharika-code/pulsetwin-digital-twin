from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score, mean_absolute_error, mean_squared_error, precision_score, r2_score, recall_score
from sklearn.model_selection import train_test_split

DATASET_PATH = Path(os.getenv("PULSETWIN_ML_DATASET", Path(__file__).resolve().parent.parent / "data" / "cms_timely_effective_care_hospital.csv"))
MODEL_DIR = Path(os.getenv("PULSETWIN_MODEL_DIR", Path(__file__).resolve().parent.parent / "models"))
META_PATH = MODEL_DIR / "latest.json"
FEATURES = ["ed_volume", "left_before_seen_pct", "head_ct_score"]


def _number(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.astype(str).str.replace(",", "", regex=False).str.extract(r"(-?\d+(?:\.\d+)?)")[0], errors="coerce")


def _dataset_frame() -> pd.DataFrame:
    if not DATASET_PATH.exists():
        raise FileNotFoundError(f"No healthcare benchmark found at {DATASET_PATH}. Download CMS Timely and Effective Care — Hospital or set PULSETWIN_ML_DATASET.")
    raw = pd.read_csv(DATASET_PATH, low_memory=False)
    required = {"Facility ID", "Condition", "Measure ID", "Score"}
    missing = required - set(raw.columns)
    if missing: raise ValueError(f"Dataset is missing required CMS columns: {sorted(missing)}")
    ed = raw[raw["Condition"].astype(str).str.lower().eq("emergency department")].copy()
    ed["ScoreNumeric"] = _number(ed["Score"])
    pivot = ed.pivot_table(index="Facility ID", columns="Measure ID", values="ScoreNumeric", aggfunc="first")
    volume_map = {"low": 1.0, "medium": 2.0, "high": 3.0, "very high": 4.0}
    volume = ed[ed["Measure ID"].eq("EDV")].set_index("Facility ID")["Score"].astype(str).str.lower().map(volume_map)
    pivot["EDV"] = volume
    renamed = pivot.rename(columns={"EDV":"ed_volume", "OP_22":"left_before_seen_pct", "OP_23":"head_ct_score", "OP_18a":"wait_time_minutes"})
    frame = renamed[FEATURES + ["wait_time_minutes"]].dropna().reset_index()
    if len(frame) < 30: raise ValueError(f"Only {len(frame)} usable hospital ED rows were found; at least 30 are required for a meaningful benchmark split.")
    return frame


def train_models(seed: int = 42) -> dict[str, Any]:
    frame = _dataset_frame(); X = frame[FEATURES]; y = frame["wait_time_minutes"]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=.2, random_state=seed)
    reg = RandomForestRegressor(n_estimators=120, min_samples_leaf=3, random_state=seed, n_jobs=-1).fit(X_train, y_train)
    pred = reg.predict(X_test)
    threshold = float(y_train.quantile(.75)); classifier = RandomForestClassifier(n_estimators=120, min_samples_leaf=3, class_weight="balanced", random_state=seed, n_jobs=-1).fit(X_train, (y_train >= threshold).astype(int)); cp = classifier.predict(X_test); actual = (y_test >= threshold).astype(int)
    MODEL_DIR.mkdir(parents=True, exist_ok=True); joblib.dump(reg, MODEL_DIR / "wait_time.joblib"); joblib.dump(classifier, MODEL_DIR / "bottleneck.joblib")
    result = {"modelVersion": f"ed-ops-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}", "status":"validated", "dataset":{"name":"CMS Timely and Effective Care - Hospital", "source":"Centers for Medicare & Medicaid Services", "sourceUrl":"https://data.cms.gov/provider-data/dataset/yv7e-xc69", "rows":len(frame), "features":FEATURES, "target":"OP_18a median ED time"}, "trainedRows":len(X_train), "testRows":len(X_test), "waitTime":{"maeMinutes":round(mean_absolute_error(y_test, pred),2),"rmseMinutes":round(mean_squared_error(y_test, pred)**.5,2),"r2":round(r2_score(y_test, pred),3)}, "bottleneck":{"thresholdMinutes":round(threshold,2),"accuracy":round(accuracy_score(actual, cp)*100,2),"balancedAccuracy":round(balanced_accuracy_score(actual, cp)*100,2),"precision":round(precision_score(actual, cp, zero_division=0)*100,2),"recall":round(recall_score(actual, cp, zero_division=0)*100,2),"f1":round(f1_score(actual, cp, zero_division=0)*100,2)}, "trainedAt":datetime.now(timezone.utc).isoformat()}
    META_PATH.write_text(json.dumps(result, indent=2)); return result


def latest() -> dict[str, Any] | None:
    return json.loads(META_PATH.read_text()) if META_PATH.exists() else None


def predict(features: dict[str, float]) -> dict[str, Any]:
    if not (MODEL_DIR / "wait_time.joblib").exists(): raise FileNotFoundError("Train the ED models before requesting predictions")
    values = pd.DataFrame([[float(features[name]) for name in FEATURES]], columns=FEATURES); reg = joblib.load(MODEL_DIR / "wait_time.joblib"); classifier = joblib.load(MODEL_DIR / "bottleneck.joblib"); wait = float(reg.predict(values)[0]); bottleneck = int(classifier.predict(values)[0])
    metadata = latest() or {}; return {"predictedWaitMinutes":round(wait,1),"bottleneckRisk":"high" if bottleneck else "normal","modelVersion":metadata.get("modelVersion"),"features":features}
