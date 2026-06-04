"""VIAB-UX-005a: A/B test split utility for viability default sort.

Provides deterministic 50/50 user assignment via MD5 hash of user_id.

- Group A: data_desc (control)
- Group B: confianca (treatment)
"""

import hashlib


def get_viability_sort_group(user_id: str) -> str:
    """Deterministic 50/50 A/B split based on MD5 hash of user_id.

    The same user_id always maps to the same group.
    Expected distribution: ~50% in Group A, ~50% in Group B.

    Args:
        user_id: User UUID string. Must be non-empty.

    Returns:
        'A' for control (data_desc) or 'B' for treatment (confianca).

    Raises:
        ValueError: If user_id is empty or None.
    """
    if not user_id:
        raise ValueError("user_id must be a non-empty string")

    hash_val = hashlib.md5(user_id.encode()).digest()[0]
    return "A" if hash_val % 2 == 0 else "B"
