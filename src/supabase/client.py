"""
EvoAlpha — Supabase Client
Connects to Supabase for data loading.
"""
from config.settings import SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY


_client = None


def get_supabase_client():
    """
    Get (or create) a Supabase client instance.
    Prefers service role key (full access), falls back to anon key.
    Returns None if credentials are not configured.
    """
    global _client
    if _client is not None:
        return _client

    if not SUPABASE_URL:
        print("  ⚠ Supabase URL not configured")
        return None

    # Prefer service role key (server-side, full access), fall back to anon key
    key = SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY
    if not key:
        print("  ⚠ No Supabase key configured")
        return None

    try:
        from supabase import create_client
        _client = create_client(SUPABASE_URL, key)
        return _client
    except Exception as e:
        print(f"  ⚠ Supabase connection failed: {e}")
        return None
