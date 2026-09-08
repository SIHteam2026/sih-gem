import sys

with open('backend/app/db/client.py', 'r', encoding='utf-8') as f:
    text = f.read()

content = '''
async def insert_officer_observation_db(observation_data: Dict[str, Any]) -> Dict[str, Any]:
    from fastapi.encoders import jsonable_encoder
    import uuid
    from datetime import datetime, timezone
    entry = jsonable_encoder(observation_data)
    entry.setdefault("observation_id", str(uuid.uuid4()))
    entry.setdefault("created_at", datetime.now(timezone.utc).isoformat())
    _IN_MEMORY_OBSERVATIONS.append(entry)
    _save_local_store()
    try:
        db_client = get_supabase_client()
        await asyncio.to_thread(
            lambda: db_client.table("officer_observations").insert(entry).execute()
        )
    except Exception as exc:
        pass
    return entry

async def list_officer_observations_db(procurement_id: str) -> List[Dict[str, Any]]:
    results = [obs for obs in _IN_MEMORY_OBSERVATIONS if obs.get("procurement_id") == procurement_id]
    try:
        db_client = get_supabase_client()
        response = await asyncio.to_thread(
            lambda: db_client.table("officer_observations").select("*").eq("procurement_id", procurement_id).order("created_at", desc=False).execute()
        )
        if response and hasattr(response, "data") and response.data:
            results = response.data
    except Exception:
        pass
    return results
'''

text = text.replace('_IN_MEMORY_AUDIT_LOGS: List[Dict[str, Any]] = []', '_IN_MEMORY_AUDIT_LOGS: List[Dict[str, Any]] = []\n_IN_MEMORY_OBSERVATIONS: List[Dict[str, Any]] = []')

loadStoreStr = '            _IN_MEMORY_AUDIT_LOGS.extend(data.get("audit_logs", []))'
loadStoreReplace = '            _IN_MEMORY_AUDIT_LOGS.extend(data.get("audit_logs", []))\n            _IN_MEMORY_OBSERVATIONS.clear()\n            _IN_MEMORY_OBSERVATIONS.extend(data.get("observations", []))'
text = text.replace(loadStoreStr, loadStoreReplace)

saveStoreStr = '            "audit_logs": _IN_MEMORY_AUDIT_LOGS[-500:],'
saveStoreReplace = '            "audit_logs": _IN_MEMORY_AUDIT_LOGS[-500:],\n            "observations": _IN_MEMORY_OBSERVATIONS,'
text = text.replace(saveStoreStr, saveStoreReplace)

text += '\n' + content

with open('backend/app/db/client.py', 'w', encoding='utf-8') as f:
    f.write(text)
print('Applied changes!')
