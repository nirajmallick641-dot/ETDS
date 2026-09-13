from supabase import create_client, Client
from .config import SUPABASE_URL, SUPABASE_SECRET_KEY

if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
    supabase: Client | None = None
else:
    supabase = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)
