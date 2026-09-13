from __future__ import annotations
from dataclasses import dataclass
from math import isfinite
from typing import Any
from .config import (
    DETECTION_IMBALANCE_WARN_PCT,
    DETECTION_IMBALANCE_CRITICAL_PCT,
    DETECTION_ANOMALY_WARN_SCORE,
    DETECTION_ANOMALY_CRITICAL_SCORE,
)

@dataclass
class DetectionResult:
    status: str
    severity: str | None
    is_theft: bool
    anomaly_score: float
    imbalance_pct: float | None
    reasons: list[str]


def num(value: Any) -> float | None:
    try:
        n = float(value)
        return n if isfinite(n) else None
    except (TypeError, ValueError):
        return None


def detect(payload: dict[str, Any]) -> DetectionResult:
    reasons: list[str] = []
    tamper = bool(payload.get('tamper', False) or payload.get('tamper_detected', False))
    source_power = num(payload.get('source_power_kw') or payload.get('feeder_power_kw') or payload.get('input_power_kw'))
    load_power = num(payload.get('load_power_kw') or payload.get('meter_power_kw') or payload.get('output_power_kw') or payload.get('power_kw'))

    imbalance_pct = None
    if source_power is not None and load_power is not None and source_power > 0:
        imbalance_pct = max(0.0, ((source_power - load_power) / source_power) * 100.0)
        if imbalance_pct >= DETECTION_IMBALANCE_CRITICAL_PCT:
            reasons.append(f'power imbalance {imbalance_pct:.1f}%')
        elif imbalance_pct >= DETECTION_IMBALANCE_WARN_PCT:
            reasons.append(f'elevated power imbalance {imbalance_pct:.1f}%')

    voltage = num(payload.get('voltage'))
    current = num(payload.get('current'))
    if voltage is not None and (voltage < 200 or voltage > 260):
        reasons.append(f'voltage out of expected range ({voltage:.1f} V)')
    if current is not None and current < 0:
        reasons.append('invalid negative current')

    supplied_score = num(payload.get('anomaly_score'))
    score = supplied_score if supplied_score is not None else 0.0
    if imbalance_pct is not None:
        score = max(score, min(1.0, imbalance_pct / 100.0))
    if tamper:
        score = max(score, 0.98)
        reasons.insert(0, 'tamper signal active')

    # Theft requires a direct tamper signal or a material feeder/load mismatch.
    is_theft = tamper or (imbalance_pct is not None and imbalance_pct >= DETECTION_IMBALANCE_CRITICAL_PCT)

    if is_theft:
        return DetectionResult('critical', 'critical', True, min(1.0, score), imbalance_pct, reasons)
    if score >= DETECTION_ANOMALY_CRITICAL_SCORE:
        return DetectionResult('critical', 'critical', False, min(1.0, score), imbalance_pct, reasons or ['high anomaly score'])
    if score >= DETECTION_ANOMALY_WARN_SCORE or (imbalance_pct is not None and imbalance_pct >= DETECTION_IMBALANCE_WARN_PCT):
        return DetectionResult('warning', 'warning', False, min(1.0, score), imbalance_pct, reasons or ['anomalous telemetry pattern'])
    return DetectionResult('normal', None, False, min(1.0, score), imbalance_pct, [])
