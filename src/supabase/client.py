"""
EvoAlpha — Supabase Client
Placeholder — your teammate will fill this in once Supabase is set up.
"""
from config.settings import SUPABASE_URL, SUPABASE_ANON_KEY


_client = None


def get_supabase_client():
    """
    Get (or create) a Supabase client instance.
    Returns None if credentials are not configured.
    """
    global _client
    if _client is not None:
        return _client

    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        print("  ⚠ Supabase not configured — using mock data")
        return None

    try:
        from supabase import create_client
        _client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        return _client
    except Exception as e:
        print(f"  ⚠ Supabase connection failed: {e}")
        return None
