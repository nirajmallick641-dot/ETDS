# ETDS — Real-Time Electricity Theft Detection System

This version turns the original single-file demo into a real hardware + database architecture:

**Arduino + network shield → FastAPI hardware gateway → Supabase Postgres → Supabase Realtime → ETDS dashboard**

The browser no longer generates fake sensor readings or fake theft alerts. Incidents are created from telemetry received by the backend and stored in Supabase. The dashboard subscribes to database changes in real time.

## What is working in this package

- Real Supabase Auth for operators.
- Supabase Postgres tables for meters, readings and incidents.
- Supabase Realtime subscriptions for live meter, reading and incident changes.
- Secure hardware ingestion endpoint using a server-side `DEVICE_API_KEY`.
- Server-side theft/anomaly detection with tamper and feeder/load imbalance support.
- Automatic incident open/close lifecycle based on live telemetry.
- Live meter map using Leaflet + OpenStreetMap.
- Historical incident list and operator resolve action.
- Live charts from stored telemetry.
- Real OpenAI backend assistant using the configured Responses API model.
- Browser buzzer that repeatedly beeps while an active theft incident exists and stops after the incident is resolved/normal; the operator must arm it once because browsers restrict unsolicited audio.
- Example Arduino Uno + Ethernet Shield firmware payload structure.

## 1. Supabase setup

Open the Supabase SQL Editor and run:

`supabase/schema.sql`

Then copy your **Project URL** and **Publishable key** into `config.js`.

Never put the Supabase secret/service-role key into `config.js` or any frontend file.

### First admin/operator

Supabase Auth creates the user. The schema creates a matching `profiles` row. You can promote a user to admin manually in the SQL editor if you need roles later:

```sql
update public.profiles
set role = 'admin'
where id = 'YOUR_AUTH_USER_UUID';
```

## 2. Backend setup on Render

Create a Render Web Service from this repository.

- Root directory: `backend`
- Build: `pip install -r requirements.txt`
- Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health check: `/health`

Set these environment variables from `backend/.env.example`:

```text
SUPABASE_URL
SUPABASE_SECRET_KEY
OPENAI_API_KEY
OPENAI_MODEL=gpt-5.6-luna
DEVICE_API_KEY
CORS_ORIGINS=https://YOUR-VERCEL-DOMAIN.vercel.app
```

`SUPABASE_SECRET_KEY`, `OPENAI_API_KEY`, and `DEVICE_API_KEY` are backend secrets. Do not put them in GitHub frontend code.

The AI model can be changed with `OPENAI_MODEL`; the default in this package is `gpt-5.6-luna`.

## 3. Frontend setup on Vercel / GitHub Pages

Edit `config.js`:

```js
window.ETDS_CONFIG = {
  SUPABASE_URL: 'https://YOUR_PROJECT.supabase.co',
  SUPABASE_PUBLISHABLE_KEY: 'YOUR_SB_PUBLISHABLE_KEY',
  API_BASE_URL: 'https://YOUR-RENDER-SERVICE.onrender.com'
};
```

The publishable key is designed for browser use. Never replace it with the secret/service-role key.

## 4. Hardware → ETDS

The firmware/device sends JSON to:

`POST https://YOUR-RENDER-SERVICE.onrender.com/api/hardware/telemetry`

with:

```http
Authorization: Bearer YOUR_DEVICE_API_KEY
Content-Type: application/json
```

Example:

```json
{
  "meter_id": "MTR-001",
  "voltage": 239.8,
  "current": 12.4,
  "power_kw": 2.97,
  "energy_kwh": 1824.4,
  "source_power_kw": 3.40,
  "load_power_kw": 2.97,
  "tamper": false,
  "latitude": 22.3072,
  "longitude": 73.1812,
  "signal_strength": -58,
  "relay_state": "on",
  "device_status": "online"
}
```

### Theft logic

- `tamper=true` → critical theft incident.
- `source_power_kw` vs `load_power_kw` imbalance ≥ 15% → critical theft incident.
- Imbalance ≥ 8% or anomaly score ≥ 0.65 → warning.
- When the next reading is normal, the active incident is automatically resolved with a database update.

These thresholds are environment variables so they can be tuned to your actual meter/sensor behavior.

## 5. Arduino

Open `firmware/arduino_uno_ethernet/arduino_uno_ethernet.ino`. This example targets Arduino Uno with a W5100/W5500 Ethernet Shield. Replace the example sensor functions with your exact calibrated sensors. The original repository did not contain a board model, pin map, current transformer, voltage sensor, meter protocol, or network shield, so sensor functions are intentionally placeholders.

**Security warning:** the basic Arduino EthernetClient example uses HTTP on port 80. Do not send a real device key over an untrusted network. For production, use a TLS-capable Ethernet library/module or an HTTPS gateway (for example, a local Raspberry Pi/PC gateway) and update the endpoint accordingly.

### Important hardware note

A real theft detector should ideally compare a feeder/source measurement with one or more downstream meter measurements. A single voltage/current sensor is not enough to prove theft by itself. The included backend supports `source_power_kw` and `load_power_kw` specifically for that comparison.

## 6. Real-time behavior

The dashboard subscribes to Supabase Realtime for `meters`, `readings` and `incidents`. Supabase requires the tables to be present in the `supabase_realtime` publication; the included SQL configures that.

The operator should click **Arm Buzzer** once after opening the dashboard. Thereafter, an active theft incident causes an audible browser buzzer, and the buzzer stops automatically when the active theft incident disappears/resolves.

## 7. API quick test

After Render is deployed:

```bash
curl https://YOUR-RENDER-SERVICE.onrender.com/health
```

Then send a telemetry packet:

```bash
curl -X POST https://YOUR-RENDER-SERVICE.onrender.com/api/hardware/telemetry \
  -H "Authorization: Bearer YOUR_DEVICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"meter_id":"MTR-001","voltage":239.8,"current":12.4,"power_kw":2.97,"source_power_kw":3.5,"load_power_kw":2.97,"tamper":false,"latitude":22.3072,"longitude":73.1812}'
```

That should create a reading and, because the imbalance is above the configured critical threshold, an active theft incident.

Send a normal reading next (for example matching source/load power) and the incident will auto-resolve.

## 8. Original project → production changes

The original repository was a static `index.html` using Canva Data SDK/demo simulation and browser-side generated alerts. This package removes that fake data path and replaces it with a proper backend and Supabase database.

The UI keeps the original ETDS/PPI futuristic direction while adding actual fleet state, incident lifecycle, map markers, realtime subscriptions, database-backed history, and server AI.

## License

MIT (see `LICENSE`).
