"""Central Government Debarment / Blacklist Registry Simulation.

Simulates the Central Public Procurement Portal (CPPP) and GeM
debarred/blacklisted suppliers database for verifying bidder eligibility.
"""

from typing import Set

# Simulated Central Government Debarment & Blacklist Database (PANs and GSTINs)
BLACKLISTED_ENTITIES: Set[str] = {
    # Blacklisted PAN numbers
    "ABCDE1234F",
    "BKRPN5544K",
    "XYZAB9876C",
    "FRAUD1234X",
    "DEBAR9999Z",
    # Blacklisted GSTIN numbers
    "22AAAAA0000A1Z5",
    "07BBBBB9999B1Z5",
    "29ABCDE1234F1Z5",
    "33XYZAB9876C1Z9",
}


def is_entity_blacklisted(entity_id: str) -> bool:
    """Checks whether a given PAN, GSTIN, or Entity ID is present in the central government debarment database.

    Args:
        entity_id (str): The PAN or GSTIN string to check.

    Returns:
        bool: True if the entity is blacklisted/debarred, False otherwise.
    """
    if not entity_id:
        return False

    normalized_id = str(entity_id).strip().upper()
    return normalized_id in BLACKLISTED_ENTITIES
