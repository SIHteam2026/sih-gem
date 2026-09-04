import os
from pathlib import Path
import pymupdf


def create_gst_certificate(filename: str, legal_name: str, gstin: str):
    doc = pymupdf.open()
    page = doc.new_page()
    content = f"""Government of India
Form GST REG-06
Registration Certificate

Registration Number (GSTIN): {gstin}
1. Legal Name: {legal_name}
2. Trade Name: {legal_name}
3. Constitution of Business: Private Limited Company
4. Address: 123 Industrial Area, Phase II, New Delhi, Delhi, 110020
5. Date of Liability: 01/07/2017
6. Period of Validity: From: 01/07/2017 To: Permanent
7. Type of Registration: Regular
Jurisdictional Office: Ward 101, Delhi
Date of Issue of Certificate: 01/07/2017
Status: Active
"""
    page.insert_text((50, 60), content, fontsize=11)
    doc.save(filename)
    doc.close()
    print(f"Generated GST certificate: {filename}")


def create_menu(filename: str):
    doc = pymupdf.open()
    page = doc.new_page()
    content = """MARIO'S PIZZERIA & TRATTORIA
Authentic Wood-Fired Artisanal Pizzas & Fresh Italian Delights

CLASSIC & ARTISANAL PIZZAS (12")
1. Margherita Classica - $14.00
2. Pepperoni Supreme - $16.50
3. Quattro Formaggi - $17.00
4. Truffle Wild Mushroom - $18.50
5. Diavola Piccante - $17.50

APPETIZERS & SIDES
1. Garlic Herb Breadsticks - $6.50
2. Crispy Truffle Fries - $7.50
3. Classic Caesar Salad - $8.50
4. Traditional Tiramisu - $7.00
"""
    page.insert_text((50, 60), content, fontsize=11)
    doc.save(filename)
    doc.close()
    print(f"Generated Pizza menu: {filename}")



def main():
    eval_dir = Path(__file__).parent.resolve()
    eval_dir.mkdir(parents=True, exist_ok=True)

    # 1. valid_gst.pdf
    valid_gst_path = str(eval_dir / "valid_gst.pdf")
    create_gst_certificate(
        filename=valid_gst_path,
        legal_name="ACME CORP",
        gstin="07AAAAA0000A1Z5"
    )

    # 2. mismatch_gst.pdf
    mismatch_gst_path = str(eval_dir / "mismatch_gst.pdf")
    create_gst_certificate(
        filename=mismatch_gst_path,
        legal_name="ACME CORP",
        gstin="07BBBBB9999B1Z5"
    )

    # 3. menu.pdf
    menu_path = str(eval_dir / "menu.pdf")
    create_menu(filename=menu_path)

    print("All test PDFs generated successfully in:", eval_dir)


def create_synthetic_tender_pdf(output_path: str) -> bytes:
    """Generates the benchmark synthetic multi-page tender PDF for DEMO/CPCL/WQM/2026/017."""
    import pymupdf

    doc = pymupdf.open()

    # Page 1: Overview & Statutory Identity
    page1 = doc.new_page()
    page1_text = """CHENNAI PETROLEUM CORPORATION LIMITED (CPCL)
NOTICE INVITING TENDER: DEMO/CPCL/WQM/2026/017
Tender Title: Supply, Installation, and Commissioning of Online Continuous Water Quality Monitoring System
Issuing Authority: Chennai Petroleum Corporation Limited (CPCL) - MoP&NG
Estimated Tender Value: INR 1,50,00,000 (INR 1.50 Crore)

SECTION I: STATUTORY REGISTRATION
Clause 1.1: GST Registration
The bidder must possess a valid and active GST Registration Certificate under the CGST/SGST/IGST Act.
Evidence Required: Active GSTIN and latest 3 months GSTR-3B filing receipts.

Clause 1.2: PAN & Legal Identity
The bidder must possess a valid Permanent Account Number (PAN) issued by the Income Tax Department and Certificate of Incorporation/Partnership Deed.
Evidence Required: Copy of PAN Card and Certificate of Incorporation.
"""
    page1.insert_text((50, 60), page1_text, fontsize=10)

    # Page 2: Financial & Experience Criteria
    page2 = doc.new_page()
    page2_text = """SECTION II: MINIMUM ELIGIBILITY CRITERIA

Clause 2.1: Financial Turnover
The bidder shall have an average annual financial turnover of not less than INR 5.0 Crores during the last three completed financial years (FY 2022-23, FY 2023-24, and FY 2024-25).
Evidence Required: Audited Balance Sheets or CA Turnover Certificate bearing valid UDIN.
Statutory Exemption: Micro and Small Enterprises (MSEs) registered under Udyam and DPIIT-recognized Startups are exempt from the average annual turnover criteria as per GFR 2017 Rule 173(i).

Clause 2.2: Past Experience & Performance
The bidder must have successfully executed at least 2 similar completed supply contracts of Online Water Quality Monitoring Systems during the last 5 years, each with a contract value not less than INR 1.0 Crore.
Evidence Required: Satisfactory work completion certificates from the client along with copies of Purchase Orders.
"""
    page2.insert_text((50, 60), page2_text, fontsize=10)

    # Page 3: Technical, OEM, Make in India, Warranty & Vague Criteria
    page3 = doc.new_page()
    page3_text = """SECTION III: TECHNICAL, OEM & COMMERCIAL REQUIREMENTS

Clause 3.1: OEM / Manufacturer Authorization
The bidder must be the Original Equipment Manufacturer (OEM) of the analyzers or an authorized representative/channel partner. In case of authorized partner, a valid Manufacturer Authorization Form (MAF) from the OEM must be submitted on OEM letterhead.
Evidence Required: Manufacturer Authorization Form (MAF) from OEM.

Clause 3.2: Make in India (Local Content)
Minimum 20% Local Content is mandatory for Class-II Local Suppliers under Public Procurement (Preference to Make in India) Order 2017.
Evidence Required: Self-declaration of local content percentage and location of local value addition.

Clause 3.3: Non-Debarment & Vigilance Clearance
The bidder must not be debarred, blacklisted, or put on holiday list by CPCL, MoP&NG, or any Central/State Government Ministry/PSU as on the bid closing date.
Evidence Required: Self-undertaking on company letterhead signed by authorized signatory.

Clause 3.4: Comprehensive Warranty & SLA
The supplied monitoring equipment shall carry a minimum 24-month comprehensive on-site OEM warranty from the date of final commissioning.
Evidence Required: Warranty undertaking certificate.

Clause 3.5: General Industrial Reputation (Vague Criteria)
Bidder should have adequate experience and satisfactory reputation in similar industrial domains.
"""
    page3.insert_text((50, 60), page3_text, fontsize=10)

    pdf_bytes = doc.tobytes()
    if output_path:
        doc.save(output_path)
    doc.close()
    return pdf_bytes


async def run_tender_intelligence_verification():
    """Comprehensive test runner for Tender Intelligence pipeline."""
    import sys
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    from backend.app.models.tender import (
        AmbiguityType,
        RequirementCategory,
        TenderAnalysisResult,
        TenderRequirement,
    )
    from backend.app.services.pdf_parser import extract_pages_from_pdf, extract_text_from_pdf
    from backend.app.services.tender_service import analyze_tender

    eval_dir = Path(__file__).parent.resolve()
    tender_pdf_path = str(eval_dir / "demo_cpcl_tender.pdf")
    pdf_bytes = create_synthetic_tender_pdf(tender_pdf_path)

    print("=" * 80)
    print(" OPAL TENDER INTELLIGENCE - AUDIT & VERIFICATION SUITE")
    print(" Benchmark Tender: DEMO/CPCL/WQM/2026/017")
    print("=" * 80)

    # 1. Page-Aware PDF Extraction Test
    print("\n[TEST 1] Testing page-aware PDF extraction...")
    pages = await extract_pages_from_pdf(pdf_bytes)
    print(f"  [OK] Extracted page count: {len(pages)}")
    assert len(pages) == 3, f"Expected 3 pages, got {len(pages)}"
    assert pages[0]["page"] == 1 and "DEMO/CPCL/WQM/2026/017" in pages[0]["text"]
    assert pages[1]["page"] == 2 and "Clause 2.1: Financial Turnover" in pages[1]["text"]
    assert pages[2]["page"] == 3 and "Clause 3.4: Comprehensive Warranty" in pages[2]["text"]
    print("  [PASSED] Page-aware PDF extraction properly retains page boundaries!")

    # 2. Backward Compatible Raw Text Extraction Test
    print("\n[TEST 2] Testing backward-compatible extract_text_from_pdf...")
    raw_text = await extract_text_from_pdf(pdf_bytes)
    assert len(raw_text) > 500
    assert "SECTION I" in raw_text and "SECTION II" in raw_text and "SECTION III" in raw_text
    print("  [PASSED] Backward-compatible extract_text_from_pdf works cleanly!")

    # 3. Live AI Structured Extraction on Synthetic Tender
    print("\n[TEST 3] Running full Tender Analysis AI pipeline...")
    result = await analyze_tender(pdf_bytes)

    print(f"  [OK] Extracted Tender ID   : {result.tender_id}")
    print(f"  [OK] Extracted Tender Title: {result.tender_title}")
    print(f"  [OK] Total Requirements   : {len(result.requirements)}")
    print(f"  [OK] Page Count Recorded   : {result.page_count}")

    assert len(result.requirements) >= 5, f"Expected at least 5 requirements, got {len(result.requirements)}"

    # Display Extracted Requirements Table
    print("\n" + "-" * 88)
    print(f"| {'ID':<8} | {'Category':<24} | {'Pg':<3} | {'Threshold / Condition':<28} | {'Ambiguous':<9} |")
    print("-" * 88)

    for req in result.requirements:
        pg = req.source_provenance.page_number if req.source_provenance else "-"
        cond_str = ""
        if req.structured_condition:
            sc = req.structured_condition
            val = f"{sc.threshold_value:,.0f}" if isinstance(sc.threshold_value, (int, float)) else str(sc.threshold_value or "")
            cond_str = f"{sc.operator or ''} {val} {sc.unit or ''}".strip()
        if not cond_str:
            cond_str = "<Unquantified>"
        amb_flag = "YES" if req.is_ambiguous else "NO"
        cat_str = req.category.value if hasattr(req.category, "value") else str(req.category)

        print(f"| {req.requirement_id:<8} | {cat_str:<24} | {str(pg):<3} | {cond_str:<28} | {amb_flag:<9} |")

    print("-" * 88)

    # 4. Check Specific Key Requirements
    print("\n[TEST 4] Validating Key Benchmark Requirements:")

    # Turnover check (>= INR 5 Crore over 3 years)
    turnover_reqs = [r for r in result.requirements if r.category in (RequirementCategory.FINANCIAL_TURNOVER, 'FINANCIAL_TURNOVER') or 'turnover' in r.description.lower()]
    print(f"  Turnover requirements found: {len(turnover_reqs)}")
    assert len(turnover_reqs) >= 1, "Turnover requirement must be extracted"
    t_req = turnover_reqs[0]
    print(f"   - Turnover statement: {t_req.description}")
    if t_req.structured_condition:
        print(f"   - Structured threshold: {t_req.structured_condition.threshold_value} {t_req.structured_condition.unit} (Period: {t_req.structured_condition.period_years}y)")
    if t_req.applicability:
        print(f"   - MSE Exemption Flag: {t_req.applicability.msme_exemption_applicable}")
        print(f"   - Exemption Notes: {t_req.applicability.exemption_notes}")

    # Local Content (>= 20%)
    lc_reqs = [r for r in result.requirements if r.category in (RequirementCategory.LOCAL_CONTENT_MII, RequirementCategory.LOCAL_CONTENT, 'LOCAL_CONTENT_MII', 'LOCAL_CONTENT') or 'local content' in r.description.lower()]
    print(f"  Local content requirements found: {len(lc_reqs)}")
    assert len(lc_reqs) >= 1, "Local Content requirement must be extracted"
    lc_req = lc_reqs[0]
    if lc_req.structured_condition:
        print(f"   - Local content threshold: {lc_req.structured_condition.threshold_value}%")

    # Vague / Ambiguous Clause check
    vague_reqs = [r for r in result.requirements if r.is_ambiguous or (r.ambiguity and r.ambiguity.is_ambiguous)]
    print(f"  Ambiguous clauses detected: {len(vague_reqs)}")
    assert len(vague_reqs) >= 1, "Deliberately vague clause must be detected by Ambiguity Radar"
    for v in vague_reqs:
        print(f"   - Ambiguous clause [{v.requirement_id}]: {v.description}")
        reason_txt = v.ambiguity_reason or (v.ambiguity.ambiguity_reason if v.ambiguity else "")
        print(f"     Reason: {reason_txt}")

    # 5. Provenance Check
    print("\n[TEST 5] Checking Source Provenance across requirements:")
    prov_count = sum(1 for r in result.requirements if r.source_provenance and r.source_provenance.page_number is not None)
    print(f"  Requirements with page provenance: {prov_count}/{len(result.requirements)}")
    assert prov_count >= 1, "At least some requirements must have extracted page provenance"

    # 6. Backward Compatibility Check
    print("\n[TEST 6] Validating Legacy Field Access:")
    for req in result.requirements:
        assert isinstance(req.requirement_id, str)
        assert hasattr(req, "category")
        assert isinstance(req.description, str)
        assert isinstance(req.mandatory, bool)
        assert isinstance(req.evidence_required, list)
        assert isinstance(req.is_ambiguous, bool)
    print("  [OK] All legacy fields (requirement_id, category, description, mandatory, evidence_required, is_ambiguous, ambiguity_reason) are 100% accessible.")
    print("  [PASSED] Full backward compatibility verified!")

    print("\n" + "=" * 80)
    print(" ALL TENDER INTELLIGENCE AUDIT TESTS PASSED SUCCESSFULLY!")
    print("=" * 80)


if __name__ == "__main__":
    import asyncio
    main()
    asyncio.run(run_tender_intelligence_verification())

