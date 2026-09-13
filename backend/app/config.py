import os
from dotenv import load_dotenv

load_dotenv()

APP_ENV = os.getenv('APP_ENV', 'production')
SUPABASE_URL = os.getenv('SUPABASE_URL', '').strip().rstrip('/')
SUPABASE_SECRET_KEY = os.getenv('SUPABASE_SECRET_KEY', '').strip()
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '').strip()
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-5.6-luna').strip()
DEVICE_API_KEY = os.getenv('DEVICE_API_KEY', '').strip()
CORS_ORIGINS = [x.strip() for x in os.getenv('CORS_ORIGINS', '*').split(',') if x.strip()]
DETECTION_IMBALANCE_WARN_PCT = float(os.getenv('DETECTION_IMBALANCE_WARN_PCT', '8'))
DETECTION_IMBALANCE_CRITICAL_PCT = float(os.getenv('DETECTION_IMBALANCE_CRITICAL_PCT', '15'))
DETECTION_ANOMALY_WARN_SCORE = float(os.getenv('DETECTION_ANOMALY_WARN_SCORE', '0.65'))
DETECTION_ANOMALY_CRITICAL_SCORE = float(os.getenv('DETECTION_ANOMALY_CRITICAL_SCORE', '0.82'))
