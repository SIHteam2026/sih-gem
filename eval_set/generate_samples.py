"""Script to generate synthetic test PDFs for the evaluation set."""

from pathlib import Path
import pymupdf


def generate_sample_pdfs(output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)

    # Sample 1: Standard Active Tax Invoice
    doc1 = pymupdf.open()
    page1 = doc1.new_page()
    content1 = """TAX INVOICE / GST VERIFICATION SLIP

Seller Details:
Legal Business Name: TATA CONSULTANCY SERVICES LIMITED
Trade Name: TCS
GSTIN / UIN: 27AABCU9603R1ZN
Registration Status: Active
Address: TCS House, Raveline Street, Fort, Mumbai, Maharashtra 400001

Invoice No: INV-2026-0891
Date of Invoice: 15-08-2026

Particulars:
1. Enterprise Cloud Consulting Services - HSN 998313
   Taxable Value: Rs. 100,000.00
   CGST (9%): Rs. 9,000.00
   SGST (9%): Rs. 9,000.00

Total Invoice Amount: 118000.00
Amount in words: One Lakh Eighteen Thousand Rupees Only
Status: Active
"""
    page1.insert_text((40, 60), content1, fontsize=11)
    doc1.save(output_dir / "sample_gst_invoice_1.pdf")
    doc1.close()

    # Sample 2: Another Active Invoice
    doc2 = pymupdf.open()
    page2 = doc2.new_page()
    content2 = """TAX INVOICE

Billed From:
INFOSYS LIMITED
Electronics City, Hosur Road, Bangalore, Karnataka - 560100
GSTIN: 29AAACI4818K1ZW
Filing Status: Active

Invoice #: INF-99214
Invoice Date: 20/08/2026

Description of Services:
Software Engineering Support & AI Architecture Deployment
Sub Total: 50,000.00
IGST (18%): 9,000.00
Grand Total: 59000.00

Authorized Signatory for INFOSYS LIMITED
Registration State: Karnataka (29)
Current Taxpayer Status: Active
"""
    page2.insert_text((40, 60), content2, fontsize=11)
    doc2.save(output_dir / "sample_gst_invoice_2.pdf")
    doc2.close()

    # Sample 3: Cancelled / Non-compliant GST
    doc3 = pymupdf.open()
    page3 = doc3.new_page()
    content3 = """GST REGISTRATION SUSPENSION & CLAIM NOTICE

Entity Information:
Legal Entity: RELIANCE RETAIL LIMITED
GSTIN Number: 27AABCR0216R1Z9
Taxpayer Registration Status: Cancelled
Reason for Cancellation: Suo Moto Cancellation by Tax Officer

Disputed Input Tax Credit Claim:
Disputed Invoice Value: 25000.00
Eligible ITC: 0.00
Status: Cancelled
"""
    page3.insert_text((40, 60), content3, fontsize=11)
    doc3.save(output_dir / "sample_gst_status_3.pdf")
    doc3.close()

    print(f"Generated sample PDFs in: {output_dir}")


if __name__ == "__main__":
    generate_sample_pdfs(Path(__file__).parent)
