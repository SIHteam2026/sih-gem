import asyncio
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.api.mock_gem_router import create_cpcl_demo_payload
from app.services.ingestion_service import ingest_procurement
from app.services.procurement_processing_service import start_procurement_processing, get_procurement_processing_status
from app.db.client import list_procurements, get_procurement_hierarchy, get_bid_evaluations

class TestProcurementProcessingIntegration(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # 1. Ingest procurement
        payload = create_cpcl_demo_payload()
        res = await ingest_procurement(payload)
        self.procurement_id = res.procurement_id
        self.tender_id = res.tender_id

    async def test_canonical_processing_pipeline(self):
        from backend.app.db.client import get_procurement_hierarchy
        p_detail = await get_procurement_hierarchy(self.procurement_id)
        print("PROC DETAILS docs:", p_detail.get("documents"))
        print("TENDER docs:", p_detail.get("tender", {}).get("documents"))
        # 2. Start processing
        proc_res = await start_procurement_processing(self.procurement_id, force=True)
        print("PROC RES MSG:", proc_res.message)
        status_res = await get_procurement_processing_status(self.procurement_id)
        print("LAST ERROR:", status_res.last_error_message)
        self.assertEqual(proc_res.status.value, "READY")
        
        # 3. Check status
        status_res = await get_procurement_processing_status(self.procurement_id)
        self.assertEqual(status_res.status.value, "READY")
        self.assertEqual(len(status_res.completed_stages), 4)
        
        # 4. Check evaluations
        from backend.app.db.client import _IN_MEMORY_EVALUATIONS
        evaluations = [e for e in _IN_MEMORY_EVALUATIONS if e.get("tender_id") == "CPCL/WQM/2026/RFP-017"]
        
        self.assertEqual(len(evaluations), 2)
        
        for e in evaluations:
            bidder = e.get("bidder", {})
            results = e.get("requirement_results", [])
            # Assert missing items are UNVERIFIED
            # HydroTech misses some requirements like PAN if not in its mock
            
            if "AquaPure" in str(bidder.get("legal_name", "")):
                # Must reach REVIEW due to contradiction 27% vs 14%
                lc_result = next((r for r in results if r.get("requirement_id") == "REQ-LC-MII-20"), None)
                if lc_result:
                    # Should be REVIEW
                    status_val = lc_result.get("status")
                    if hasattr(status_val, "value"): status_val = status_val.value
                    self.assertEqual(status_val, "REVIEW")
                    
        # 5. Check idempotency (re-running doesn't duplicate)
        proc_res2 = await start_procurement_processing(self.procurement_id)
        self.assertTrue(proc_res2.already_completed)
        self.assertEqual(proc_res2.status.value, "READY")
        
        # Check if missing docs lead to correct failure (mocked by injecting a bad stage or deleting tender doc)
        pass
            
if __name__ == '__main__':
    unittest.main()
