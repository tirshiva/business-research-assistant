"""Public-domain sample corpus for government / business document RAG.

Texts are original samples written for this project (CC0). They are not
copies of copyrighted reports. URLs point at public catalogs for provenance
style only.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from app.rag.models import SourceDocument

_RETRIEVED = datetime(2026, 8, 1, tzinfo=UTC)


def public_sample_corpus() -> list[SourceDocument]:
    """Return ingestible public sample reports."""
    return [
        SourceDocument(
            document_id="sample-noida-economic-brief-2024",
            title="NCR Food Services and Office Catchment Brief (sample)",
            source="India Business Research sample public corpus",
            source_url="https://data.gov.in/",
            publication_date=date(2024, 6, 15),
            retrieved_at=_RETRIEVED,
            category="economic_report",
            license="CC0-1.0",
            text=(
                "[Page 1]\n"
                "This sample public brief summarises office-worker meal demand "
                "in Noida and Greater Noida.\n"
                "Sector 62 and nearby IT parks concentrate weekday daytime "
                "workers who order lunch delivery.\n"
                "Cloud kitchens serving office catchments typically see peak "
                "demand between 12:00 and 15:00.\n"
                "\n"
                "[Page 17]\n"
                "Noida's Sector 62 office catchment supports prepared-food "
                "delivery when kitchens sit within a short drive of major "
                "software parks. Public statistical sketches (not official "
                "MOSPI tables) suggest weekday office density is the primary "
                "demand driver, not weekend walk-in traffic.\n"
                "Infrastructure notes: arterial roads and metro connectivity "
                "improve delivery reliability.\n"
            ),
        ),
        SourceDocument(
            document_id="sample-india-infra-urban-access-2023",
            title="Urban Access and Logistics Notes for Indian Cities (sample)",
            source="India Business Research sample public corpus",
            source_url="https://data.gov.in/",
            publication_date=date(2023, 11, 1),
            retrieved_at=_RETRIEVED,
            category="infrastructure_report",
            license="CC0-1.0",
            text=(
                "[Page 1]\n"
                "Sample infrastructure guidance for last-mile food delivery "
                "in Indian metropolitan areas.\n"
                "Reliable electricity, kitchen exhaust compliance, and "
                "two-wheeler access matter more than highway frontage for "
                "cloud kitchens.\n"
                "\n"
                "[Page 4]\n"
                "Parking and loading bays reduce delay at peak lunch hours. "
                "Metro-adjacent catchments in Noida, Bengaluru, and Hyderabad "
                "show stronger weekday delivery volumes in this sample.\n"
            ),
        ),
        SourceDocument(
            document_id="sample-demographic-daytime-population-2022",
            title="Daytime Worker Population Notes (sample)",
            source="India Business Research sample public corpus",
            source_url="https://censusindia.gov.in/",
            publication_date=date(2022, 3, 20),
            retrieved_at=_RETRIEVED,
            category="demographic_report",
            license="CC0-1.0",
            text="""[Page 2]
This sample demographic note discusses daytime worker populations in planned industrial
and IT townships. Office workers in Noida Sector 62 form a concentrated weekday market
for lunch and snacks, distinct from residential dinner demand.

[Page 8]
Targeting office workers implies menu and hours aligned to weekday shifts rather than
late-night residential neighbourhoods.
""",
        ),
        SourceDocument(
            document_id="sample-fssai-public-hygiene-outline-2024",
            title="Public Food-Safety Hygiene Outline for Kitchens (sample)",
            source="India Business Research sample public corpus",
            source_url="https://www.fssai.gov.in/",
            publication_date=date(2024, 1, 10),
            retrieved_at=_RETRIEVED,
            category="government_report",
            license="CC0-1.0",
            text=(
                "[Page 1]\n"
                "Sample outline of publicly discussed kitchen hygiene themes: "
                "potable water, pest control, and traceable ingredients. This "
                "is original training text, not an official FSSAI gazette.\n"
                "\n"
                "[Page 3]\n"
                "Cloud kitchens still require the same hygiene controls as "
                "restaurants even without a dining hall. Local municipal trade "
                "licenses and FSSAI registration remain relevant.\n"
            ),
        ),
    ]
