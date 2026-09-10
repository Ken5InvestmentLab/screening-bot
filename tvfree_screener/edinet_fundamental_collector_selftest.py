#!/usr/bin/env python3
"""Synthetic checks for the TEST-only EDINET fundamental collector."""
from __future__ import annotations

import io
import zipfile

import pandas as pd

import edinet_fundamental_collector as e


def make_zip(rows: list[list[str]]) -> bytes:
    cols = ["要素ID", "項目名", "コンテキストID", "相対年度", "連結・個別", "期間・時点", "ユニットID", "単位", "値"]
    df = pd.DataFrame(rows, columns=cols)
    payload = df.to_csv(index=False, sep="\t").encode("utf-16")
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("XBRL_TO_CSV/jppfs.csv", payload)
    return out.getvalue()


def main() -> None:
    try:
        e.require_api_key({})
        raise AssertionError("missing API key must fail closed")
    except RuntimeError:
        pass

    assert e.sec_code_to_symbol("72030") == "7203"
    assert e.sec_code_to_symbol("130A0") == "130A"
    assert e.sec_code_to_symbol("72031") is None

    doc = e.normalize_document(
        {
            "docID": "S100TEST",
            "secCode": "72030",
            "edinetCode": "E00000",
            "filerName": "Synthetic Corp",
            "ordinanceCode": "010",
            "formCode": "030000",
            "docTypeCode": "120",
            "docDescription": "synthetic",
            "periodStart": "2024-04-01",
            "periodEnd": "2025-03-31",
            "submitDateTime": "2025-06-20 15:12",
            "xbrlFlag": "1",
            "csvFlag": "1",
        },
        "2025-06-20",
    )
    assert doc is not None
    assert doc["symbol"] == "7203"
    assert doc["available_date"] == "2025-06-20"
    assert doc["available_at"] == "2025-06-20 15:12:00"

    rows = [
        ["jpcrp_cor:NumberOfIssuedSharesAsOfFiscalYearEndIssuedSharesTotalNumberOfSharesEtc", "shares", "CurrentYearInstant_NonConsolidatedMember", "当期", "個別", "時点", "shares", "株", "1,000"],
        ["jppfs_cor:Assets", "assets", "CurrentYearInstant", "当期", "連結", "時点", "JPY", "円", "5000000"],
        ["jppfs_cor:NetAssets", "equity", "CurrentYearInstant", "当期", "連結", "時点", "JPY", "円", "2000000"],
        ["jppfs_cor:NetSales", "sales", "CurrentYearDuration", "当期", "連結", "期間", "JPY", "円", "7000000"],
        ["jppfs_cor:OperatingIncome", "op", "CurrentYearDuration", "当期", "連結", "期間", "JPY", "円", "(300000)"],
        ["jppfs_cor:ProfitLossAttributableToOwnersOfParent", "net", "CurrentYearDuration", "当期", "連結", "期間", "JPY", "円", "200000"],
        ["jppfs_cor:NetCashProvidedByUsedInOperatingActivities", "ocf", "CurrentYearDuration", "当期", "連結", "期間", "JPY", "円", "400000"],
        ["jppfs_cor:NetSales", "old sales", "Prior1YearDuration", "前期", "連結", "期間", "JPY", "円", "999999999"],
    ]
    parsed = e.read_xbrl_csv_zip(make_zip(rows))
    facts = e.extract_standard_facts(parsed)
    assert facts["shares_outstanding"] == 1000.0
    assert facts["assets"] == 5_000_000.0
    assert facts["equity"] == 2_000_000.0
    assert facts["revenue"] == 7_000_000.0
    assert facts["operating_income"] == -300_000.0
    assert facts["net_income"] == 200_000.0
    assert facts["operating_cf"] == 400_000.0
    assert facts["revenue_status"] == "ok"

    # Two same-priority current-year values conflict -> do not guess.
    ambiguous_rows = rows + [
        ["jppfs_cor:NetSales", "sales duplicate", "CurrentYearDuration", "当期", "連結", "期間", "JPY", "円", "7100000"],
    ]
    ambiguous = e.extract_standard_facts(e.read_xbrl_csv_zip(make_zip(ambiguous_rows)))
    assert ambiguous["revenue"] is None
    assert ambiguous["revenue_status"] == "ambiguous"

    assert "<redacted>" in repr(e.EdinetClient("super-secret-test-key"))
    assert "super-secret-test-key" not in repr(e.EdinetClient("super-secret-test-key"))
    print("edinet_fundamental_collector_selftest: OK")


if __name__ == "__main__":
    main()
