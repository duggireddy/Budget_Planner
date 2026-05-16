"""Budget category tree matching the 2026 Excel template."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

LineType = Literal["income", "expense", "info", "computed"]


@dataclass
class Line:
    key: str
    label_de: str
    label_en: str
    line_type: LineType = "expense"
    editable: bool = True


@dataclass
class Section:
    id: str
    title_de: str
    title_en: str
    tab: str
    lines: list[Line]
    summary_key: str | None = None
    summary_label_de: str | None = None
    summary_label_en: str | None = None


MONTH_NAMES_DE = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]
MONTH_NAMES_EN = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


def _lines(keys_labels, default_type: LineType = "expense") -> list[Line]:
    out: list[Line] = []
    for item in keys_labels:
        if len(item) == 4:
            k, de, en, lt = item
            out.append(Line(k, de, en, lt))
        else:
            k, de, en = item
            out.append(Line(k, de, en, default_type))
    return out


SECTIONS: list[Section] = [
    Section(
        id="self_employed_a",
        title_de="Selbstständig A",
        title_en="Self-employed A",
        tab="income",
        lines=_lines([
            ("sea_revenue", "Umsatz / Revenue", "Revenue / Sales", "income"),
            ("sea_taxes", "Steuern", "Taxes"),
            ("sea_social", "Sozialabgaben", "Social security contributions"),
            ("sea_operating", "Betriebsausgaben", "Operating expenses / Business expenses"),
            ("sea_trade", "Gewerbesteuer", "Trade tax"),
            ("sea_other", "Sonstige Ausgaben", "Other expenses"),
        ]),
        summary_key="sea_net",
        summary_label_de="Summe Nettoeinnahme selbstst.",
        summary_label_en="Net self-employed income",
    ),
    Section(
        id="self_employed_b",
        title_de="Selbstständig B",
        title_en="Self-employed B",
        tab="income",
        lines=_lines([
            ("seb_revenue", "Umsatz / Revenue", "Revenue / Sales", "income"),
            ("seb_taxes", "Steuern", "Taxes"),
            ("seb_social", "Sozialabgaben", "Social security contributions"),
            ("seb_operating", "Betriebsausgaben", "Operating expenses / Business expenses"),
            ("seb_trade", "Gewerbesteuer", "Trade tax"),
            ("seb_other", "Sonstige Ausgaben", "Other expenses"),
        ]),
        summary_key="seb_net",
        summary_label_de="Summe Nettoeinnahme selbstst.",
        summary_label_en="Net self-employed income",
    ),
    Section(
        id="net_a",
        title_de="Netto A",
        title_en="Net Amount A",
        tab="income",
        lines=_lines([
            ("na_gross", "Brutto", "Gross", "income"),
            ("na_net", "Netto", "Net", "income"),
            ("na_minijob", "Nebeneinkünfte (450€ Job)", "Additional income (450€ job)", "income"),
        ]),
        summary_key="na_total",
        summary_label_de="Summe Netto nichtselbstst.",
        summary_label_en="Total net non-self-employed",
    ),
    Section(
        id="net_b",
        title_de="Netto B",
        title_en="Net Amount B",
        tab="income",
        lines=_lines([
            ("nb_gross", "Brutto", "Gross", "income"),
            ("nb_net", "Netto", "Net", "income"),
            ("nb_minijob", "Nebeneinkünfte (450€ Job)", "Additional income (450€ job)", "income"),
        ]),
        summary_key="nb_total",
        summary_label_de="Summe Netto nichtselbstst.",
        summary_label_en="Total net non-self-employed",
    ),
    Section(
        id="other_income_a",
        title_de="Sonstige Einnahmen A",
        title_en="Other income A",
        tab="income",
        lines=_lines([
            ("oia_child", "Kindergeld", "Child benefit", "income"),
            ("oia_parental", "Elterngeld", "Parental allowance", "income"),
            ("oia_rental", "Mieteinnahmen", "Rental income", "income"),
            ("oia_pv", "Photovoltaik", "Photovoltaic (solar) system income", "income"),
            ("oia_alimony", "Unterhalt", "Maintenance/alimony income", "income"),
            ("oia_pension_stat", "Gesetzliche Rente", "Statutory pension income", "income"),
            ("oia_pension_t1", "Rente Stufe 1", "Pension income – Tier 1", "income"),
            ("oia_pension_t2", "Rente Stufe 2", "Pension income – Tier 2", "income"),
            ("oia_pension_t3", "Rente Stufe 3", "Pension income – Tier 3", "income"),
            ("oia_interest", "Zinsen", "Interest income", "income"),
            ("oia_dividend", "Dividenden", "Dividend income", "income"),
            ("oia_tax_refund", "Steuererstattung", "Tax refunds", "income"),
            ("oia_license", "Lizenzen/Patente", "License/patent income", "income"),
            ("oia_other", "Sonstiges", "Other", "income"),
        ]),
        summary_key="oia_total",
        summary_label_de="Summe Sonstige Einnahmen",
        summary_label_en="Total other income",
    ),
    Section(
        id="other_income_b",
        title_de="Sonstige Einnahmen B",
        title_en="Other income B",
        tab="income",
        lines=_lines([
            ("oib_child", "Kindergeld", "Child benefit", "income"),
            ("oib_parental", "Elterngeld", "Parental allowance", "income"),
            ("oib_rental", "Mieteinnahmen", "Rental income", "income"),
            ("oib_pv", "Photovoltaik", "Photovoltaic (solar) system income", "income"),
            ("oib_alimony", "Unterhalt", "Maintenance/alimony income", "income"),
            ("oib_pension_stat", "Gesetzliche Rente", "Statutory pension income", "income"),
            ("oib_pension_t1", "Rente Stufe 1", "Pension income – Tier 1", "income"),
            ("oib_pension_t2", "Rente Stufe 2", "Pension income – Tier 2", "income"),
            ("oib_pension_t3", "Rente Stufe 3", "Pension income – Tier 3", "income"),
            ("oib_interest", "Zinsen", "Interest income", "income"),
            ("oib_dividend", "Dividenden", "Dividend income", "income"),
            ("oib_tax_refund", "Steuererstattung", "Tax refunds", "income"),
            ("oib_license", "Lizenzen/Patente", "License/patent income", "income"),
            ("oib_other", "Sonstiges", "Other", "income"),
        ]),
        summary_key="oib_total",
        summary_label_de="Summe Sonstige Einnahmen",
        summary_label_en="Total other income",
    ),
    Section(
        id="living",
        title_de="Lebenshaltung",
        title_en="Living expenses",
        tab="living",
        lines=_lines([
            ("liv_clothes", "Kleidung", "Clothes"),
            ("liv_household", "Haushalt (Lebensmittel)", "Household costs (e.g. groceries)"),
            ("liv_eating_out", "Auswärts essen", "Eating out / pub / nightclub"),
            ("liv_cosmetics", "Kosmetik/Friseur", "Cosmetics / nail salon / hairdresser"),
            ("liv_hobby", "Hobby", "Hobby"),
            ("liv_pets", "Haustiere", "Pets"),
            ("liv_medication", "Medikamente", "Medication"),
            ("liv_doctors", "Ärzte/Physio", "Doctors, physiotherapy, alternative practitioner"),
            ("liv_pocket", "Taschengeld", "Pocket money"),
            ("liv_daycare", "Kita/Schule", "Daycare / school fees"),
            ("liv_care", "Pflegekosten", "Care costs / nursing care costs"),
            ("liv_vacation", "Urlaub", "Vacation / holidays"),
            ("liv_bank_fees", "Kontoführung", "Account management fees"),
            ("liv_tobacco", "Tabak", "Tobacco"),
            ("liv_gifts", "Geschenke", "Gifts"),
            ("liv_gym", "Sport/Fitness", "Gym / sports"),
            ("liv_mobile", "Mobilfunk", "Mobile phone contract"),
            ("liv_cable", "Kabel", "Cable connection"),
            ("liv_streaming", "Streaming", "Sky / Netflix / Prime / Disney+"),
            ("liv_music", "Musik-Streaming", "Apple Music / Spotify / etc."),
            ("liv_books", "Bücher", "Books"),
            ("liv_magazines", "Zeitschriften", "Magazine / newspaper subscriptions"),
            ("liv_semester", "Semesterbeitrag", "Semester fee"),
            ("liv_transport", "Bus/Bahn/Sprit", "Bus and train ticket / Petrol"),
            ("liv_alimony_pay", "Unterhaltszahlungen", "Maintenance / alimony payments"),
            ("liv_union", "Gewerkschaft", "Trade union membership"),
            ("liv_other1", "Sonstiges 1", "Other"),
            ("liv_other2", "Sonstiges 2", "Other"),
            ("liv_other3", "Sonstiges 3", "Other"),
        ]),
        summary_key="liv_total",
        summary_label_de="Summe Lebenshaltung",
        summary_label_en="Total living expenses",
    ),
    Section(
        id="housing",
        title_de="Wohnen",
        title_en="Living & Renting",
        tab="housing",
        lines=_lines([
            ("hou_rent", "Warmmiete", "Warm rent"),
            ("hou_electricity", "Strom", "Electricity"),
            ("hou_heating", "Heizung/Nebenkosten", "Heating / utility costs"),
            ("hou_gez", "Rundfunkbeitrag (GEZ)", "Broadcasting fee"),
            ("hou_property_tax", "Grundsteuer/Gebühren", "Property-related taxes and charges"),
            ("hou_internet", "Internet", "Internet access"),
            ("hou_cleaning", "Reinigung/Garten", "Cleaning service / gardener"),
            ("hou_garage", "Garage/Stellplatz", "Garage / parking space"),
            ("hou_other", "Sonstiges", "Other"),
        ]),
        summary_key="hou_total",
        summary_label_de="Summe Wohnen",
        summary_label_en="Total housing",
    ),
    Section(
        id="baufinanzierung",
        title_de="Baufinanzierung",
        title_en="Housing & Financing",
        tab="housing",
        lines=_lines([
            ("bau_re1", "Immobilienfinanzierung 1", "Real estate financing 1"),
            ("bau_re1_principal", "→ Tilgung 1", "→ Principal repayment 1"),
            ("bau_re2", "Immobilienfinanzierung 2", "Real estate financing 2"),
            ("bau_re2_principal", "→ Tilgung 2", "→ Principal repayment 2"),
            ("bau_building_loan", "Bausparloan", "Building society loan"),
            ("bau_building_principal", "→ Tilgung Bauspar", "→ Principal repayment"),
            ("bau_replace1", "Tilgungsersatz 1", "Repayment replacement investment 1"),
            ("bau_replace2", "Tilgungsersatz 2", "Repayment replacement investment 2"),
        ]),
        summary_key="bau_total",
        summary_label_de="Summe Baufinanzierung",
        summary_label_en="Total real estate financing",
    ),
    Section(
        id="health_a",
        title_de="Gesundheit A",
        title_en="Health A",
        tab="health",
        lines=_lines([
            ("ha_health", "Krankenzusatzversicherung", "Health insurance (supplementary)"),
            ("ha_care", "Pflegezusatzversicherung", "Long-term care supplementary insurance"),
            ("ha_life", "Lebensversicherung", "Life insurance"),
            ("ha_disability", "Berufsunfähigkeit", "Occupational disability insurance"),
            ("ha_asset", "→ Kapitalbildender Anteil", "→ Asset accumulation component"),
        ]),
        summary_key="ha_total",
        summary_label_de="Summe Krankenversicherung",
        summary_label_en="Total health insurance",
    ),
    Section(
        id="health_b",
        title_de="Gesundheit B",
        title_en="Health B",
        tab="health",
        lines=_lines([
            ("hb_health", "Krankenzusatzversicherung", "Health insurance (supplementary)"),
            ("hb_care", "Pflegezusatzversicherung", "Long-term care supplementary insurance"),
            ("hb_life", "Lebensversicherung", "Life insurance"),
            ("hb_disability", "Berufsunfähigkeit", "Occupational disability insurance"),
            ("hb_asset", "→ Kapitalbildender Anteil", "→ Asset accumulation component"),
        ]),
        summary_key="hb_total",
        summary_label_de="Summe Krankenversicherung",
        summary_label_en="Total health insurance",
    ),
    Section(
        id="property_insurance",
        title_de="Sachversicherungen",
        title_en="Property insurances",
        tab="insurance",
        lines=_lines([
            ("pi_vsp", "Vermögensschaden (VSP)", "Asset protection policy (VSP)"),
            ("pi_animal", "Tierhalterhaftpflicht", "Animal owner liability insurance"),
            ("pi_household", "Hausrat", "Household contents insurance"),
            ("pi_glass", "Glasbruch", "Glass breakage insurance"),
            ("pi_car", "KFZ-Versicherung", "Car insurance"),
            ("pi_accident", "Unfallversicherung", "Accident insurance"),
            ("pi_travel", "Reiseversicherung", "Travel insurance"),
            ("pi_building", "Wohngebäude", "Residential building insurance"),
            ("pi_legal", "Rechtsschutz", "Legal expenses insurance"),
            ("pi_adac", "ADAC", "ADAC membership / insurance"),
            ("pi_other", "Sonstiges", "Other"),
        ]),
        summary_key="pi_total",
        summary_label_de="Summe Sachversicherungen",
        summary_label_en="Total property insurance",
    ),
    Section(
        id="pension",
        title_de="Altersvorsorge",
        title_en="Pension scheme",
        tab="pension",
        lines=_lines([
            ("pen_ruerup1", "Rürup 1", "Rürup / basic pension"),
            ("pen_ruerup2", "Rürup 2", "Rürup / basic pension"),
            ("pen_riester1", "Riester 1", "Riester pension"),
            ("pen_riester2", "Riester 2", "Riester pension"),
            ("pen_private1", "Private Altersvorsorge 1", "Private retirement provision"),
            ("pen_private2", "Private Altersvorsorge 2", "Private retirement provision"),
        ]),
        summary_key="pen_total",
        summary_label_de="Summe Altersvorsorge",
        summary_label_en="Total retirement provision",
    ),
    Section(
        id="wealth",
        title_de="Vermögensaufbau",
        title_en="Wealth creation",
        tab="wealth",
        lines=_lines([
            ("wel_gold", "Goldsparplan", "Gold savings plan"),
            ("wel_invest1", "Investmentsparplan 1", "Investment savings plan"),
            ("wel_invest2", "Investmentsparplan 2", "Investment savings plan"),
            ("wel_savings1", "Sparvertrag 1", "Savings contracts"),
            ("wel_savings2", "Sparvertrag 2", "Savings contracts"),
            ("wel_bauspar1", "Bausparvertrag 1", "Building society savings"),
            ("wel_bauspar2", "Bausparvertrag 2", "Building society savings"),
        ]),
        summary_key="wel_total",
        summary_label_de="Summe Vermögensaufbau",
        summary_label_en="Total capital accumulation",
    ),
    Section(
        id="credit",
        title_de="Kredite",
        title_en="Credit",
        tab="wealth",
        lines=_lines([
            ("cre_loan1", "Kredit 1", "Loan 1"),
            ("cre_loan2", "Kredit 2", "Loan 2"),
            ("cre_loan3", "Kredit 3", "Loan 3"),
        ]),
        summary_key="cre_total",
        summary_label_de="Summe Verbindlichkeiten",
        summary_label_en="Total liabilities",
    ),
]

TABS = [
    {"id": "dashboard", "label_de": "Übersicht", "label_en": "Dashboard"},
    {"id": "income", "label_de": "Einnahmen", "label_en": "Income"},
    {"id": "living", "label_de": "Leben", "label_en": "Living"},
    {"id": "housing", "label_de": "Wohnen", "label_en": "Housing"},
    {"id": "health", "label_de": "Gesundheit", "label_en": "Health"},
    {"id": "insurance", "label_de": "Versicherung", "label_en": "Insurance"},
    {"id": "pension", "label_de": "Rente", "label_en": "Pension"},
    {"id": "wealth", "label_de": "Vermögen", "label_en": "Wealth"},
    {"id": "summary", "label_de": "Zusammenfassung", "label_en": "Summary"},
    {"id": "charts", "label_de": "Diagramme", "label_en": "Charts"},
]

SELF_EMPLOYED_KEYS = {
    "a": ("sea_revenue", "sea_taxes", "sea_social", "sea_operating", "sea_trade", "sea_other", "sea_net"),
    "b": ("seb_revenue", "seb_taxes", "seb_social", "seb_operating", "seb_trade", "seb_other", "seb_net"),
}

LINE_BY_KEY: dict[str, Line] = {}
SECTION_BY_ID: dict[str, Section] = {s.id: s for s in SECTIONS}
ALL_EDITABLE_KEYS: list[str] = []

for section in SECTIONS:
    for line in section.lines:
        LINE_BY_KEY[line.key] = line
        if line.editable:
            ALL_EDITABLE_KEYS.append(line.key)


def sections_for_tab(tab_id: str) -> list[Section]:
    if tab_id in ("dashboard", "summary", "charts"):
        return []
    return [s for s in SECTIONS if s.tab == tab_id]


def label_for_key(key: str, lang: str = "both") -> str:
    line = LINE_BY_KEY.get(key)
    if not line:
        return key
    if lang == "de":
        return line.label_de
    if lang == "en":
        return line.label_en
    return f"{line.label_de} · {line.label_en}"
