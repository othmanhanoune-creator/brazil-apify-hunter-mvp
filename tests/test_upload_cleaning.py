from pathlib import Path


def test_upload_script_contains_prepare_leads():
    text = Path("src/supabase_client/upload_leads_to_supabase.py").read_text(encoding="utf-8")
    assert "def prepare_leads" in text
    assert "lead_id" in text
    assert "market" in text
