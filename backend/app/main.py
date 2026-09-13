from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
import hashlib
import hmac

from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .config import CORS_ORIGINS, DEVICE_API_KEY
from .db import supabase
from .detection import detect
from .ai import ask_ai

app = FastAPI(title='ETDS API', version='2.0.0')
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS if CORS_ORIGINS != ['*'] else ['*'],
    allow_credentials=False,
    allow_methods=['*'],
    allow_headers=['*'],
)

class TelemetryIn(BaseModel):
    meter_id: str = Field(min_length=1, max_length=100)
    voltage: float | None = None
    current: float | None = None
    power_kw: float | None = None
    energy_kwh: float | None = None
    source_power_kw: float | None = None
    load_power_kw: float | None = None
    feeder_power_kw: float | None = None
    tamper: bool = False
    latitude: float | None = None
    longitude: float | None = None
    signal_strength: int | None = None
    relay_state: str | None = None
    measured_at: datetime | None = None
    device_status: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

class AIRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)

class ResolveRequest(BaseModel):
    resolved_by: str | None = None
    resolution_note: str | None = None


def require_db():
    if supabase is None:
        raise HTTPException(status_code=500, detail='Supabase is not configured on the backend.')
    return supabase


def require_device(x_device_key: str | None = Header(default=None), authorization: str | None = Header(default=None)):
    supplied = x_device_key or ''
    if authorization and authorization.lower().startswith('bearer '):
        supplied = authorization[7:].strip()
    if not DEVICE_API_KEY:
        raise HTTPException(status_code=503, detail='DEVICE_API_KEY is not configured.')
    if not supplied or not hmac.compare_digest(supplied, DEVICE_API_KEY):
        raise HTTPException(status_code=401, detail='Invalid device credentials.')


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@app.get('/')
def root():
    return {'service': 'ETDS API', 'status': 'ok', 'version': '2.0.0'}


@app.get('/health')
def health():
    return {'status': 'ok', 'service': 'etds-api', 'supabase_configured': supabase is not None}


@app.get('/api/meters')
def meters(db=Depends(require_db)):
    return db.table('meters').select('*').order('updated_at', desc=True).execute().data


@app.get('/api/incidents')
def incidents(db=Depends(require_db)):
    return db.table('incidents').select('*').order('detected_at', desc=True).limit(200).execute().data


@app.get('/api/readings/latest')
def latest_readings(db=Depends(require_db)):
    rows = db.table('readings').select('*').order('measured_at', desc=True).limit(500).execute().data
    latest: dict[str, Any] = {}
    for row in rows:
        latest.setdefault(row['meter_id'], row)
    return list(latest.values())


@app.post('/api/hardware/telemetry', dependencies=[Depends(require_device)])
def ingest_telemetry(payload: TelemetryIn, db=Depends(require_db)):
    detection = detect(payload.model_dump())
    measured_at = payload.measured_at or datetime.now(timezone.utc)
    base = payload.model_dump()
    base['measured_at'] = measured_at.isoformat()
    base['status'] = detection.status
    base['severity'] = detection.severity
    base['is_theft'] = detection.is_theft
    base['anomaly_score'] = detection.anomaly_score
    base['imbalance_pct'] = detection.imbalance_pct
    base.pop('metadata', None)

    # Upsert meter live location/state.
    meter_row = {
        'meter_id': payload.meter_id,
        'status': detection.status,
        'last_seen_at': measured_at.isoformat(),
        'latitude': payload.latitude,
        'longitude': payload.longitude,
        'voltage': payload.voltage,
        'current': payload.current,
        'power_kw': payload.power_kw,
        'energy_kwh': payload.energy_kwh,
        'tamper': payload.tamper,
        'signal_strength': payload.signal_strength,
        'relay_state': payload.relay_state,
        'device_status': payload.device_status or 'online',
    }
    db.table('meters').upsert(meter_row, on_conflict='meter_id').execute()
    reading = db.table('readings').insert(base).execute().data[0]

    active = db.table('incidents').select('*').eq('meter_id', payload.meter_id).eq('status', 'active').order('detected_at', desc=True).limit(1).execute().data
    active_incident = active[0] if active else None

    if detection.status != 'normal':
        if active_incident:
            db.table('incidents').update({
                'last_seen_at': measured_at.isoformat(),
                'severity': detection.severity,
                'is_theft': detection.is_theft,
                'anomaly_score': detection.anomaly_score,
                'imbalance_pct': detection.imbalance_pct,
                'reasons': detection.reasons,
            }).eq('id', active_incident['id']).execute()
        else:
            db.table('incidents').insert({
                'meter_id': payload.meter_id,
                'status': 'active',
                'severity': detection.severity,
                'is_theft': detection.is_theft,
                'detected_at': measured_at.isoformat(),
                'last_seen_at': measured_at.isoformat(),
                'anomaly_score': detection.anomaly_score,
                'imbalance_pct': detection.imbalance_pct,
                'reasons': detection.reasons,
                'snapshot': {
                    'voltage': payload.voltage,
                    'current': payload.current,
                    'power_kw': payload.power_kw,
                    'energy_kwh': payload.energy_kwh,
                    'source_power_kw': payload.source_power_kw or payload.feeder_power_kw,
                    'load_power_kw': payload.load_power_kw,
                },
            }).execute()
    elif active_incident:
        db.table('incidents').update({
            'status': 'resolved',
            'resolved_at': measured_at.isoformat(),
            'last_seen_at': measured_at.isoformat(),
            'resolution_note': 'Telemetry returned to normal automatically.',
        }).eq('id', active_incident['id']).execute()

    return {
        'ok': True,
        'reading_id': reading['id'],
        'status': detection.status,
        'is_theft': detection.is_theft,
        'severity': detection.severity,
        'anomaly_score': detection.anomaly_score,
        'imbalance_pct': detection.imbalance_pct,
        'reasons': detection.reasons,
    }


@app.post('/api/incidents/{incident_id}/resolve')
def resolve_incident(incident_id: str, body: ResolveRequest, db=Depends(require_db)):
    result = db.table('incidents').update({
        'status': 'resolved',
        'resolved_at': now_iso(),
        'resolution_note': body.resolution_note or 'Resolved by operator.',
        'resolved_by': body.resolved_by,
    }).eq('id', incident_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail='Incident not found.')
    return result.data[0]


@app.post('/api/ai')
def ai(req: AIRequest, db=Depends(require_db)):
    meters_data = db.table('meters').select('*').order('updated_at', desc=True).limit(100).execute().data
    incidents_data = db.table('incidents').select('*').order('detected_at', desc=True).limit(50).execute().data
    context = {
        'current_meters': meters_data,
        'recent_incidents': incidents_data,
        'server_time': now_iso(),
    }
    try:
        answer = ask_ai(req.question, context)
        return {'answer': answer, 'model': 'configured backend model'}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
