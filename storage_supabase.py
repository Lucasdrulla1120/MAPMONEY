
import os, time
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
BUCKET = os.environ.get("SUPABASE_BUCKET", "comprovantes")

_supabase: Client | None = None

def _client():
    global _supabase
    if _supabase is None:
        if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
            raise RuntimeError("Defina SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY para usar o Storage.")
        _supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    return _supabase

def upload_file(file_storage, trip_id: int, user_id: int) -> str:
    data = file_storage.read()
    filename = (file_storage.filename or "arquivo").replace("/", "_")
    ts = int(time.time())
    path = f"comprovantes/{trip_id}/{user_id}-{ts}-{filename}"
    cl = _client()
    cl.storage.from_(BUCKET).upload(path, data, {"content-type": file_storage.mimetype})
    return cl.storage.from_(BUCKET).get_public_url(path)
