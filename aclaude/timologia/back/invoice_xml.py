"""
AADE myDATA Invoice XML Builder
================================
Standalone function to build myDATA-compliant invoice XML.
Adapted from the AgelClaw AADE MCP server.
"""
from datetime import date
from decimal import Decimal

from lxml import etree


# ── XML Namespaces ──
# The AADE dev API uses https:// namespace URIs for classification elements

NS_INV = "http://www.aade.gr/myDATA/invoice/v1.0"
NS_ICLS = "https://www.aade.gr/myDATA/incomeClassificaton/v1.0"
NS_ECLS = "https://www.aade.gr/myDATA/expensesClassificaton/v1.0"

NAMESPACES = {
    None: NS_INV,
    "icls": NS_ICLS,
    "ecls": NS_ECLS,
}

# ── VAT Rate Categories ──
# category -> decimal rate
VAT_RATES = {
    1: Decimal("0.24"),
    2: Decimal("0.13"),
    3: Decimal("0.06"),
    4: Decimal("0.17"),
    5: Decimal("0.09"),
    6: Decimal("0.04"),
    7: Decimal("0"),    # exempt
    8: Decimal("0"),    # exempt
}


def build_invoice_xml(
    issuer_vat: str,
    issuer_country: str,
    issuer_branch: int,
    counterpart_vat: str,
    invoice_type: str,
    series: str,
    number: int,
    items: list[dict],
    payment_method: int = 3,
    counterpart_country: str = "GR",
    counterpart_name: str = "",
    issue_date: date | None = None,
    currency: str = "EUR",
    env: str = "dev",
) -> bytes:
    """Build myDATA-compliant invoice XML.

    Args:
        issuer_vat: Issuer VAT number (AFM).
        issuer_country: Issuer country code (e.g. "GR").
        issuer_branch: Issuer branch number (0 for HQ).
        counterpart_vat: Counterpart VAT number.
        invoice_type: AADE invoice type code (e.g. "2.1", "11.1").
        series: Invoice series identifier.
        number: Invoice sequential number.
        items: List of line item dicts. Each must have:
            - net_value (required): Net amount
            - vat_category (optional, default 1): VAT rate category (1-8)
            - quantity (optional): Item quantity
            - unit_price (optional): Price per unit
            - income_classification_type (optional, default "E3_561_003")
            - income_classification_category (optional, default "category1_3")
        payment_method: AADE payment method code (default 3 = bank transfer).
        counterpart_country: Counterpart country code (default "GR").
        counterpart_name: Counterpart name (required for non-GR counterparts).
        issue_date: Invoice date (default: today).
        currency: Currency code (default "EUR").
        env: AADE environment ("dev" or "prod").

    Returns:
        bytes: UTF-8 encoded XML document.
    """
    root = etree.Element("InvoicesDoc", nsmap=NAMESPACES)
    inv = etree.SubElement(root, "invoice")

    # Issuer
    issuer = etree.SubElement(inv, "issuer")
    etree.SubElement(issuer, "vatNumber").text = issuer_vat
    etree.SubElement(issuer, "country").text = issuer_country
    etree.SubElement(issuer, "branch").text = str(issuer_branch)

    # Counterpart (omit for retail receipt types 11.x -- AADE forbids it)
    if not invoice_type.startswith("11."):
        cp = etree.SubElement(inv, "counterpart")
        etree.SubElement(cp, "vatNumber").text = counterpart_vat
        etree.SubElement(cp, "country").text = counterpart_country
        if counterpart_name and counterpart_country != "GR":
            etree.SubElement(cp, "name").text = counterpart_name
        etree.SubElement(cp, "branch").text = "0"

    # Invoice header
    header = etree.SubElement(inv, "invoiceHeader")
    etree.SubElement(header, "series").text = series
    etree.SubElement(header, "aa").text = str(number)
    etree.SubElement(header, "issueDate").text = (issue_date or date.today()).isoformat()
    etree.SubElement(header, "invoiceType").text = invoice_type
    etree.SubElement(header, "currency").text = currency

    # Payment methods
    pm = etree.SubElement(inv, "paymentMethods")
    pay = etree.SubElement(pm, "paymentMethodDetails")

    total_net = Decimal("0")
    total_vat = Decimal("0")

    # Invoice details (lines)
    for i, item in enumerate(items, 1):
        net = Decimal(str(item["net_value"])).quantize(Decimal("0.01"))
        vat_cat = int(item.get("vat_category", 1))
        vat_rate = VAT_RATES.get(vat_cat, Decimal("0.24"))
        vat_amount = (net * vat_rate).quantize(Decimal("0.01"))

        detail = etree.SubElement(inv, "invoiceDetails")
        etree.SubElement(detail, "lineNumber").text = str(i)
        if item.get("quantity"):
            etree.SubElement(detail, "quantity").text = str(item["quantity"])
        if item.get("unit_price"):
            etree.SubElement(detail, "unitPrice").text = str(item["unit_price"])
        etree.SubElement(detail, "netValue").text = str(net)
        etree.SubElement(detail, "vatCategory").text = str(vat_cat)
        etree.SubElement(detail, "vatAmount").text = str(vat_amount)

        # Income classification (must be in invoice namespace, not icls)
        icls = etree.SubElement(detail, f"{{{NS_INV}}}incomeClassification")
        etree.SubElement(icls, f"{{{NS_ICLS}}}classificationType").text = item.get(
            "income_classification_type", "E3_561_003")
        etree.SubElement(icls, f"{{{NS_ICLS}}}classificationCategory").text = item.get(
            "income_classification_category", "category1_3")
        etree.SubElement(icls, f"{{{NS_ICLS}}}amount").text = str(net)

        total_net += net
        total_vat += vat_amount

    total_gross = total_net + total_vat

    # Payment
    etree.SubElement(pay, "type").text = str(payment_method)
    etree.SubElement(pay, "amount").text = str(total_gross)

    # Summary
    summary = etree.SubElement(inv, "invoiceSummary")
    etree.SubElement(summary, "totalNetValue").text = str(total_net)
    etree.SubElement(summary, "totalVatAmount").text = str(total_vat)
    etree.SubElement(summary, "totalWithheldAmount").text = "0.00"
    etree.SubElement(summary, "totalFeesAmount").text = "0.00"
    etree.SubElement(summary, "totalStampDutyAmount").text = "0.00"
    etree.SubElement(summary, "totalOtherTaxesAmount").text = "0.00"
    etree.SubElement(summary, "totalDeductionsAmount").text = "0.00"
    etree.SubElement(summary, "totalGrossValue").text = str(total_gross)

    # Income classification summary (must be in invoice namespace)
    icls_sum = etree.SubElement(summary, f"{{{NS_INV}}}incomeClassification")
    etree.SubElement(icls_sum, f"{{{NS_ICLS}}}classificationType").text = items[0].get(
        "income_classification_type", "E3_561_003")
    etree.SubElement(icls_sum, f"{{{NS_ICLS}}}classificationCategory").text = items[0].get(
        "income_classification_category", "category1_3")
    etree.SubElement(icls_sum, f"{{{NS_ICLS}}}amount").text = str(total_net)

    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)
