"""Seed default client and sample budget."""

from __future__ import annotations

from app.database import (
    bulk_upsert,
    create_client,
    get_or_create_budget,
    init_db,
    list_clients,
    load_entries,
)

SAMPLE_LINES: list[tuple[str, float]] = [
    ("na_net", 1987.0),
    ("liv_clothes", 20.0),
    ("liv_household", 400.0),
    ("liv_eating_out", 100.0),
    ("liv_cosmetics", 25.0),
    ("liv_gifts", 10.0),
    ("liv_gym", 25.0),
    ("liv_mobile", 10.0),
    ("liv_cable", 50.0),
    ("liv_transport", 120.0),
    ("hou_rent", 853.0),
    ("hou_electricity", 52.0),
    ("hou_gez", 19.0),
    ("hou_internet", 50.0),
    ("hou_cleaning", 10.0),
    ("pi_animal", 9.0),
    ("pi_car", 180.0),
    ("pi_legal", 32.0),
    ("cre_loan1", 520.0),
]


def ensure_sample_client() -> int:
    """Create sample client with Jul–Dec data if database is empty."""
    init_db()
    clients = list_clients()
    if clients:
        client_id = int(clients[0]["id"])
    else:
        client = create_client(
            {
                "name": "Sample Client",
                "company_name": "Muster GmbH",
                "contact_person": "Max Mustermann",
                "email": "sample@example.com",
                "phone": "+49 30 123456",
                "street": "Musterstraße 1",
                "postal_code": "10115",
                "city": "Berlin",
                "country": "Germany",
                "tax_id": "12/345/67890",
                "vat_id": "DE123456789",
                "iban": "DE89370400440532013000",
                "notes": "Demo client with Jul–Dec budget data",
            }
        )
        client_id = int(client["id"])

    budget_id = get_or_create_budget(client_id, 2026)
    entries = load_entries(budget_id)
    has_data = any(sum(vals) > 0 for vals in entries.values())
    if has_data:
        return client_id

    for line_key, amount in SAMPLE_LINES:
        bulk_upsert(budget_id, line_key, 7, 12, amount)
    return client_id


if __name__ == "__main__":
    cid = ensure_sample_client()
    print(f"Seeded client id={cid}")
