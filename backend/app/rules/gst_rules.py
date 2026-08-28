"""GST Rules Evaluation Engine Stub."""


def evaluate_gst(extracted_data: dict, gov_data: dict):
    return {
        "status": "✅ VERIFIED",
        "errors": [],
        "confidence_metrics": {"name_match_score": 1.0},
    }
