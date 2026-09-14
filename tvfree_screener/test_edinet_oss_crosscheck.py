from __future__ import annotations

import io
import zipfile

import pandas as pd

from tvfree_screener import edinet_fundamental_collector as custom
from tvfree_screener.edinet_oss_crosscheck import crosscheck_zip


COLS = [
    "要素ID", "項目名", "コンテキストID", "相対年度", "連結・個別",
    "期間・時点", "ユニットID", "単位", "値",
]


def _zip(rows: list[list[str]]) -> bytes:
    frame = pd.DataFrame(rows, columns=COLS)
    payload = frame.to_csv(index=False, sep="\t").encode("utf-16")
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("XBRL_TO_CSV/jppfs.csv", payload)
    return out.getvalue()


def _financial_rows() -> list[list[str]]:
    return [
        [
            "jppfs_cor:Assets", "assets", "CurrentYearInstant", "当期",
            "連結", "時点", "JPY", "円", "5000000",
        ],
        [
            "jppfs_cor:NetAssets", "equity", "CurrentYearInstant", "当期",
            "連結", "時点", "JPY", "円", "2000000",
        ],
        [
            "jppfs_cor:NetSales", "sales", "CurrentYearDuration", "当期",
            "連結", "期間", "JPY", "円", "7000000",
        ],
        [
            "jppfs_cor:OperatingIncome", "op", "CurrentYearDuration", "当期",
            "連結", "期間", "JPY", "円", "300000",
        ],
        [
            "jppfs_cor:ProfitLossAttributableToOwnersOfParent", "net",
            "CurrentYearDuration", "当期", "連結", "期間", "JPY", "円", "200000",
        ],
        [
            "jppfs_cor:NetCashProvidedByUsedInOperatingActivities", "ocf",
            "CurrentYearDuration", "当期", "連結", "期間", "JPY", "円", "400000",
        ],
    ]


def test_current_year_summary_shares_win_over_filing_date_fallback() -> None:
    rows = _financial_rows() + [
        [
            "jpcrp_cor:TotalNumberOfIssuedSharesSummaryOfBusinessResults",
            "issued summary", "CurrentYearInstant_NonConsolidatedMember", "当期",
            "個別", "時点", "shares", "株", "1200",
        ],
        [
            "jpcrp_cor:NumberOfIssuedSharesAsOfFiscalYearEndIssuedSharesTotalNumberOfSharesEtc",
            "issued filing", "FilingDateInstant_OrdinaryShareMember", "提出日時点",
            "個別", "時点", "shares", "株", "1100",
        ],
    ]
    parsed = custom.read_xbrl_csv_zip(_zip(rows))
    facts = custom.extract_standard_facts(parsed)

    assert facts["shares_outstanding"] == 1200.0
    assert (
        facts["shares_outstanding_element_id"]
        == "jpcrp_cor:TotalNumberOfIssuedSharesSummaryOfBusinessResults"
    )


def test_filing_date_issued_shares_is_accepted_as_explicit_fallback() -> None:
    rows = _financial_rows() + [
        [
            "jpcrp_cor:NumberOfIssuedSharesAsOfFiscalYearEndIssuedSharesTotalNumberOfSharesEtc",
            "issued filing", "FilingDateInstant_OrdinaryShareMember", "提出日時点",
            "個別", "時点", "shares", "株", "1100",
        ],
    ]
    parsed = custom.read_xbrl_csv_zip(_zip(rows))
    facts = custom.extract_standard_facts(parsed)

    assert facts["shares_outstanding"] == 1100.0
    assert facts["shares_outstanding_status"] == "ok"
    assert facts["shares_outstanding_context_id"].startswith("FilingDateInstant")


def test_edinet_tools_agrees_on_same_zip_without_strategy_outcomes() -> None:
    rows = _financial_rows() + [
        [
            "jpcrp_cor:TotalNumberOfIssuedSharesSummaryOfBusinessResults",
            "issued summary", "CurrentYearInstant_NonConsolidatedMember", "当期",
            "個別", "時点", "shares", "株", "1200",
        ],
    ]
    result = crosscheck_zip(_zip(rows), doc_id="S100SYNTH")

    assert result["outcome_data_opened"] is False
    assert result["availability_policy_changed"] is False
    assert result["comparisons"]["shares_outstanding"]["status"] == "MATCH"
    assert result["comparisons"]["shares_outstanding"]["custom_value"] == 1200.0

    # The synthetic J-GAAP facts are intentionally chosen from fields mapped by
    # both implementations, so every compared accounting fact should agree.
    assert result["all_compared_fields_agree"] is True
    assert result["mismatch_fields"] == []
