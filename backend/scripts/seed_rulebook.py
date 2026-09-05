"""Rulebook Seeding Script for ChromaDB.

Pre-loads sample government procurement rulebooks, General Financial Rules (GFR 2017),
Public Procurement Policy for MSEs, Make-in-India local content guidelines,
and GeM incident management policies into the ChromaDB vector database.
"""

import asyncio
import os
import sys
from pathlib import Path

# Ensure project root and backend paths are available for imports
_current_file = Path(__file__).resolve()
_backend_dir = _current_file.parent.parent
_root_dir = _backend_dir.parent
for _p in [str(_root_dir), str(_backend_dir), str(_current_file.parent)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from app.services.rag_service import gov_rules_collection, index_rulebook

# Comprehensive sample procurement rules for RAG initialization
SAMPLE_RULEBOOK_TEXT = """
=== GENERAL FINANCIAL RULES (GFR) 2017 - PUBLIC PROCUREMENT RULES ===

[GFR Rule 144: Fundamental Principles of Public Buying]
Every authority delegated with the financial powers of procuring goods in public interest shall have the responsibility and accountability to bring efficiency, economy, and transparency in matters relating to public procurement and for fair and equitable treatment of suppliers and promotion of competition in public procurement. The description of the subject matter of procurement to the extent practicable should be objective, functional, and generic, without any brand or trade names.

[GFR Rule 153: Mandatory Procurement from Micro and Small Enterprises (MSEs)]
Under the Public Procurement Policy for Micro and Small Enterprises (MSEs) Order, Central Ministries, Departments, and Central Public Sector Undertakings (CPSUs) shall procure a minimum of 25% of their total annual procurement value from Micro and Small Enterprises (MSEs).
1. Out of the 25% target, 4% is non-negotiably earmarked for procurement from MSEs owned by Scheduled Caste (SC) or Scheduled Tribe (ST) entrepreneurs.
2. An additional 3% is earmarked for procurement from MSEs owned by Women entrepreneurs.
3. If an MSE bidder quotes a price within the price band of L1 + 15% in any tender where L1 is a non-MSE bidder, the MSE shall be allowed to supply a portion of the requirement up to 25% of the tender value by bringing down their price to the L1 price.

[GFR Rule 170: Earnest Money Deposit (EMD) and Bid Security Exemptions]
1. Micro and Small Enterprises (MSEs) registered with the Udyam Registration portal or National Small Industries Corporation (NSIC) are 100% exempt from payment of Earnest Money Deposit (EMD) / Bid Security.
2. Startups recognized by the Department for Promotion of Industry and Internal Trade (DPIIT) are also completely exempt from Bid Security / EMD across all Central Government tenders.
3. In place of a Bid Security / EMD, MSE and Startup bidders shall submit a signed 'Bid Security Declaration' accepting suspension from bidding in government tenders if they withdraw or modify their bids during the validity period.

[GFR Rule 173: Prior Turnover and Experience Criteria Exemptions for MSEs & Startups]
To encourage participation and promote indigenous innovation, Procuring Entities shall relax condition of prior turnover and prior experience in public procurement to all Startups (recognized by DPIIT) and Micro & Small Enterprises (MSEs), subject to meeting of quality and technical specifications.
1. The procuring entity shall not insist on minimum annual financial turnover or past performance history for MSEs/Startups unless the item requires specialized critical safety standards.
2. Even in high-value tenders, relaxing prior experience by at least 50% or providing full exemption is mandatory where quality standards are certified.

[GFR Rule 171: Performance Security / Security Deposit Limits]
1. To ensure due performance of the contract, Performance Security is to be obtained from the successful bidder awarded the contract.
2. Performance Security should ordinarily range between 3% to 5% of the total value of the contract. Under revised Ministry of Finance guidelines, performance security shall not exceed 3% of the contract value.
3. Performance Security may be furnished in the form of an Account Payee Demand Draft, Fixed Deposit Receipt from a Commercial bank, Bank Guarantee, or Online payment in an acceptable form.

=== PUBLIC PROCUREMENT (PREFERENCE TO MAKE IN INDIA) ORDER (PPP-MII) ===

[Make In India - Local Content Classification & Eligibility]
1. 'Class-I Local Supplier': A supplier or service provider whose goods, services, or works offered for procurement has local content equal to or more than 50%. Class-I local suppliers are entitled to purchase preference in all government procurements.
2. 'Class-II Local Supplier': A supplier or service provider whose goods, services, or works offered for procurement has local content more than 20% but less than 50%.
3. 'Non-Local Supplier': A supplier whose local content is 20% or less. Non-local suppliers are ineligible to participate in domestic tenders where estimated value is up to INR 200 Crores (Global Tender Enquiry restriction).
4. False declarations of local content percentage constitute a fraudulent practice under the Public Procurement Order and shall result in debarment / blacklisting for up to two (2) years across all government portals.

=== GeM INCIDENT MANAGEMENT AND BLACKLISTING POLICY ===

[GeM Debarment, Incident Flagging, and Blacklisting Guidelines]
1. A bidder or vendor convicted of fraud, document forgery, submission of fabricated certificates (GST, PAN, OEM Authorizations, or Balance Sheets), or severe contract default shall be placed on the GeM Debarment / Blacklist registry.
2. Any entity currently debarred or blacklisted by any Central Ministry, State Government Department, or Central Public Sector Enterprise (CPSE) is strictly disqualified and barred from participating in any active public tender.
3. Submitting altered or expired OEM authorization letters constitutes immediate grounds for disqualification, forfeiture of security, and mandatory incident logging.
"""


async def seed_rules():
    """Seeds the default procurement rulebook into ChromaDB."""
    print("=" * 60)
    print("Starting Government Procurement Rulebook Seeding for ChromaDB")
    print("=" * 60)

    initial_count = gov_rules_collection.count()
    print(f"Current documents in 'gov_rules' collection: {initial_count}")

    print("Indexing procurement rules into vector collection...")
    await index_rulebook(SAMPLE_RULEBOOK_TEXT)

    final_count = gov_rules_collection.count()
    print(f"Updated documents in 'gov_rules' collection: {final_count}")
    print(f"Successfully added {final_count - initial_count} new rule chunks.")
    print("=" * 60)
    print("Rulebook seeding completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(seed_rules())
