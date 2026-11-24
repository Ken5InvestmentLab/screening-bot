# Official disclosure inventory and publication evidence

## Checkpoint and cache integration (2026-11-16)

Official inventories, original document SHA/body, extraction records, draft fragments and validation status are retained per owner/symbol by the research commands in RECOVERY.md. They accelerate research; they do not replace the final fresh official-list and full-batch post gates. A new reader revalidates with the source, honors Retry-After, accepts304 only with an intact original and unchanged final URL, and never substitutes a cached success for retrieval failure. New200 content gets a new SHA and invalidates dependent work. Literal content/PDF resave identities and pypdf extraction are keyed by actual SHA and verifier version; metadata creation/modification values NEVER supply publication time. Keep raw PDF integrity checks and semantic body reading distinct.

The parent owns state and shared drafts. Parallel researchers use independent packets; parent audit workers share one bounded public reader. Source config/adapter changes invalidate affected symbols only; final post repairTargets automatically retain targeted repair state when an initialized research manifest is present. Unexplained owner/lock/intent conditions remain reconciliation blockers.

## Confirmed issuer-only IR policy (Ken5, 2026-11-16 22:09 JST)

This supersedes the blanket time requirement below. TDnet timely disclosures require their actual publication time. Materials published only in the official company IR library may use their verified publication date, labelled `(会社IR資料・公表日)`. Retain and read every important document. PDF CreationDate, HTTP Last-Modified and meeting times are supplementary records, NEVER publication timestamps.

Reviewed `issuerIrDateOnlyPolicies` use `issuer-ir-library-v1`: verify the issuer-hosted category marker and exact fiscal/material table row, resolve every original PDF anchor with the declared document count, and retrieve the complete same-day TDnet pagination. Verify the actual PDF against any owned TDnet originals: an identical TDnet document keeps its real time; unavailable/incomplete exchange evidence blocks classification. Save category/document SHA, actual links, date field and all exchange page evidence in `publication.issuerIrEvidence`. This is evidence-based classification, not a URL allowlist exception. Full-batch coverage, same-owner/intake, source/body checks, locks and delivery-intent protection remain mandatory. No subset posts ahead of an unfinished report.

## Publication correction (2026-11-16, supersedes older untimed examples)

All owned, unposted reports must pass together before normal delivery. Never send a valid subset ahead of an unfinished report. Keep the same owner, claims, command lock and delivery-intent protections.

Publication time is mandatory for every linked disclosure. Missing time is a retrieval/verification failure, never a publishable unknown-time label. Retry the primary source at most once, inspect its actual publication field separately from its title, and try a verified official alternate route (company IR / TDnet / JPX). Resolve the identical document and publication date; a matching title, filename, PDF date or a different same-day release is insufficient. If all routes fail, retain the claim and repair the batch; do not use a stub or partial delivery.

Timezone precedence: explicit source offset/zone, then a reviewed domestic official JST field with saved evidence, otherwise unresolved. A `zoneEvidence` with `basis: "domestic-official"` requires `country: "JP"`, the owned `symbolCode`, the actual `publicationField`, the source URL and an exact verified quote. Save issuer ownership and same-document TDnet/JPX corroboration in the owner evidence packet; do not claim an explicit timezone when the original field has none. Posted receipts retain the actual publication evidence.

XJ GetList2 uses `xj-table-v1`: publication is the first td, formal title the second, primary `PDF-GENERAL` document the third. Fiscal dates in titles are not publication metadata. Summary PDF/XBRL are attachment roles of the same record, not separately titled disclosures. `xj-json-v1` reads `publishDate`, `title` and `files` with an exact inventory count check. Both preserve all old rows and validate their actual publication fields before the 45-day relevance decision. Never discard a malformed row to get a passing inventory. A date-only first route can be repaired by a timed official route only for the same stable document identity/date/title; contradictory timed values still fail.

`eir-announcements-v1` reads the configured official JSONP envelope as JSON, never executable JavaScript, and checks issuer code and item count. It preserves legitimate `space` records without inventing a document URL. Legacy HTTP links remain recorded as unavailable direct evidence; no HTTPS alias is guessed. A required material item lacking a usable original still blocks delivery. Explicit publication fields accept complete slash-date/space-time metadata separately from titles. Domestic `00:00:00` metadata requires corroboration and is not treated as a known publication time; explicit zoned instants retain their precision. The primary field receives at most one fresh retry when time is missing. On Windows, a Node/OpenSSL DH incompatibility may use the system HTTPS reader with normal certificate verification, HTTPS-only redirects and a bounded timeout; never disable certificate validation or lower OpenSSL security.

For a genuinely date-only issuer record, its source may declare reviewed `publicationSources` with `kind: "exchange"`, the owned `symbolCode`, `format: "tdnet-table-v1"`, a verified official URL/identity marker and the actual page date. The audit reads the page's date header and that symbol's domestic TSE `kjTime` row, then compares the actual issuer and exchange PDFs. Identity requires identical raw SHA256 or the strictly limited resave-metadata normalization described below; save both raw hashes in either case. The original issuer metadata, official reference inventory, exact PDF URLs/hash and time field are retained. Similar titles, matching dates, filename IDs or different documents never suffice; conflicting exact-document times or unavailable official references fail closed. This corroboration does not replace the complete 45-day issuer-list check or permit partial delivery.

For `tdnet-table-v1` publication references and `tdnet-supplement-v1` inventory sources, use `followPagination: true` with the observed official first page `https://www.release.tdnet.info/inbs/I_list_001_YYYYMMDD.html` for the reviewed date. The audit follows the listing's actual same-day page links, checks each page's host, date, coverage and owned `kjTime` rows, and retains the page observations. This keeps the same disclosure in scope when new releases move its row to another page. Missing or inconsistent pages keep the source unverified.

This is mandatory for every future Premium report, including PM alerts appended to an AM owner. It supplements all existing official IR / IRBANK / TDnet-equivalent research, 45-day coverage, latest-material/same-time-material priority, PDF reading, quality, URL audit, BOTTOM scope and delivery deduplication. It does not authorize historical reruns, a new worker, or extra posts.

## Owner workflow

### Acquisition details verified on 2026-11-16

- Preserve issuer XML counts and issuer identity. A feed whose declared count differs from actual rows is unverified. Follow the issuer's observed alternate full-feed link, retain the failed observation, and reconcile the entire original ID set before using that complete route. Dated archive rows that reuse one landing URL retain separate internal row keys from the actual URL/date/title; these keys are not invented publisher IDs.
- EIR entries explicitly typed `calendar`/`calendar`, with a `calendar_*` ID, `space` type, no link and no attachments, are scheduled events. Preserve them and their source fields. They cannot substitute for a financial disclosure. A missing-link press/material record still blocks.
- A reviewed PDF landing-page resolution must follow an actual unique anchor on that page, retain its URL/hash, and match the retrieved document against the correct official exchange publication row.
- Exact PDF matching may normalize only identified resave metadata: XMP modification/metadata time and instance UUID, the referenced Info object's modification time, and the second XRef instance ID. The first document ID, creation dates, page content, attachments and every other byte remain significant. Such metadata NEVER supplies the publication time. Save both raw hashes and the normalized identity. The 6863 case was independently checked by matching full text and every rendered pixel of all 12 pages.
- When an issuer directly links its official video publication page, a reviewed source rule may read `playerMicroformatRenderer.publishDate` with its explicit offset. Require the exact video ID, company code in title/description, expected official channel and playable status; reject missing or conflicting fields. Convert the explicit offset to JST. For page content evidence, hash the stable title/description/publication metadata and declare that scope explicitly; client nonces are not content, and this does not mean the video itself was watched. Financial analysis must remain grounded in the separately read financial PDFs. No URL allowlist exception or unknown-time label is added.
- Validate the entire disclosure-link set before rendering. Split long link lists between complete lines into additional Discord fields, never truncate a URL. An oversized individual line, more than 25 fields or an Embed over 6,000 characters fails closed.

These adapters do not change ownership, collection dates, schedules, Discord destination, source coverage, unknown-delivery protection or the full-batch publication gate.

1. Keep the same claimId and owner-specific claimPath. Research official IR/news and the existing independent disclosure lists. Verify the company identity and that each official source belongs to the owned symbol. Do not label an aggregator as an official issuer source.
2. Prepare an owner-local official-sources JSON using the actual observed official list structure. Scan all required pages covering at least 45 days before the earliest owned receivedAt for that symbol through the current observation cutoff. Include newer visible disclosures. Complete pagination and identify every dated disclosure row; never choose a narrower scope just to omit material items. `coverageComplete` records that research duty, not a permission to assume completeness.
3. Run the supported worker command:

   `node premium_worker/worker.mjs audit-disclosures --claim-id <claimId> --input <owner-local-official-sources.json>`

   It reads official sources and writes a separate inventory per symbol/cutoff under `out/workflows/<claimId>/disclosures/`. It does not collect alerts, edit state, or send Discord messages. Read its observations. `failed`/`unverified` is a blocker, never a verified zero. HTTP 200 alone is insufficient. Unsupported markup, bad identity/scope, incomplete pagination, unknown publication date/zone, missing zero evidence, or conflicting official records fail closed. Fix only that symbol's source adapter/evidence within supported formats; do not weaken checks, invent metadata, add hardcoded URL exceptions, or use a stub to bypass a failed source.
4. Keep the existing report destination and top-level claimId. Each report adds `disclosureAuditPath` from that command and `disclosureEvidence` as shown below. Read each selected original PDF/detail body. Calculate its SHA256 from the actual downloaded bytes; preserve the source quotation and map its substance to actual analytical text. Do not infer publication dates/times from filenames, document IDs, PDF creation times, search snippets, meeting times in titles, or retrieval timestamps.
5. Use exact official inventory IDs and URLs. Newest fundamentally material disclosures and the same-publication cohort remain mandatory; routine personnel/administrative items remain governed by the existing importance rules. Analyze any additional substantively important material as before. A selected disclosure must have a verified direct link and substantive analytical reflection, not only an ID/title inventory. Do not reproduce a whole source document in the report.
6. Label each selected link using the inventory's title and official publication evidence: `YYYY-MM-DD 開示タイトル(hh:mm JST)` for an explicitly established time/zone, or `YYYY-MM-DD 開示タイトル(時刻不明)` for a date-only publication. Convert explicit UTC/offset instants to JST, including date rollover. No invented midnight, guessed timezone or inferred year. When a source shows a time without a verifiable zone, stop that symbol until the ambiguity is resolved; do not silently discard the time and pretend it was a date-only release. For same-day date-only releases the retrieval snapshot establishes visibility by the observation cutoff, not a fictitious publication time.
7. Run full dry-run on ALL owned unposted reports. Read the complete `repairTargets` list; repair only those symbols/reports while retaining other verified drafts. Rerun the full check. No good report is sent ahead of a failing report. A real post re-fetches official lists and selected content with a fresh per-pass cache immediately before sending, checks all reports again, then checks PM intake once more. A changed publication time/content or newly required disclosure blocks all sends and names the affected reports. After the check, the exact fresh inventory is saved and referenced in the posted receipt.
8. On `needsResearch`, merge newly joined PM alerts into the SAME owner, obtain their inventories/evidence, and repeat the same full checks. Never wait for future PM arrival. If PM arrives during delivery, verify its remainder before its next consolidated send, excluding confirmed/unknown deliveries as already required.

## Source config contract

Example structure only. Replace every example identity, URL, date and scope with evidence actually verified for the current owned symbol. Do not fetch example.invalid.

```json
{
  "symbols": [{
    "symbolCode": "1234",
    "sources": [{
      "kind": "issuer",
      "symbolCode": "1234",
      "url": "https://issuer.example.invalid/ir",
      "format": "html-records-v1",
      "recordTag": "tr",
      "identityMarker": "an exact official company/list identity marker",
      "scopeStart": "unique raw marker before the complete disclosure list",
      "scopeEnd": "unique raw marker after the complete disclosure list",
      "coverageComplete": true,
      "coverageFrom": "2026-01-01",
      "coverageThrough": "2026-11-13",
      "emptyMarker": "an explicit official no-disclosure message, if applicable",
      "zoneEvidence": {
        "zone": "Asia/Tokyo",
        "url": "https://issuer.example.invalid/ir",
        "quote": "exact original text establishing 日本時間 or JST"
      }
    }]
  }]
}
```

- `kind`: issuer (at least one required) or exchange (official TDnet/JPX source, if used). Every configured source is checked; a failed one is not silently dropped. Keep independent IRBANK/TDnet-equivalent checks too.
- `html-records-v1`: non-nested tr/li/article records inside the verified complete listing scope. Every anchor in a disclosure record is inventoried. Dates must include a full year outside the title, or use an explicit `time datetime` attribute. Metadata time/zone must come from the publication row or verified official timezone statement. Unknown/mixed layouts are blocked; this is not a universal scraper.
- `ys-ir-topics-v1` and `delta-ir-news-v1` read the verified issuer's complete list through the 45-day boundary, following its observed numbered pages as needed. The former resolves a current detail page's unique same-title issuer PDF. Keep separate language editions and the original publication evidence.
- `geostar-library-v1` covers the issuer's separate disclosure, financial results, briefing and statutory filing libraries. It checks the first list's date range and verifies that the displayed numbered next page contains the identical list before treating it as a duplicate. `nakabayashi-ir-archive-v1` reads the full annual IR archive's nested announcement cards and verifies coverage.
- A reviewed issuer archive configured with `archiveLegacyHttpOutsideWindow: true` retains the dates, titles and original addresses of older HTTP-only records as unavailable. A record without an HTTPS original inside the required window blocks the audit.
- The `avix-wordpress-style-placeholder-v1` evidence format handles Avix's observed WordPress stylesheet placeholder. It requires the official article identity, verified retained bytes and the original digest. After substituting the original value of that single generated placeholder, all article bytes and the cited passage must match. Normal PDF and HTML verification keeps its existing digest checks.
- `intrance-ir-archive-v1` follows the observed company IR archive pages through the date boundary and resolves each current release to its single verified issuer-hosted PDF. `beat-releases-v1` verifies the official news page's link to the full release API, the Japanese edition, and the dates and ordering of its release rows.
- The `pixta-rails-csrf-v1` evidence format verifies a Pixta news article's publication identity, live response and retained original. Every byte apart from the observed single per-response token must match, and the cited passage must be present in the current article.
- `json-records-v1`: an official JSON array, optionally selected by `recordsPath` (dot-separated property path). Default keys are id/title/url/date/time/timezone/publishedAt; `keys` may map these to the actual official schema. A recognized empty array is explicit zero evidence. HTML needs an explicit empty message; parse failure is never zero. A declared `hasMore`/next page must be resolved, not ignored.
- Publisher IDs are namespaced by official source host and symbol. If the official source provides no identifier, its canonical public document URL is the stable identity. Titles are not deduplication keys. Duplicate aliases of an identical publisher ID may merge; conflicting dates/times/titles for that ID block processing.
- Source identity, correct list scope, pagination/window completeness and company-specific importance still require the existing research review. Mechanical checks cannot certify that an arbitrary configured domain belongs to a company or that a human-selected scope contains every official disclosure. Never falsely attest them. Unsupported sites need a reviewed adapter; do not fabricate a successful inventory.
- For a verified issuer's flat JSON array using a literal dotted date field, use `json-records-v1` with `jsonPublicationDateFormat: "YYYY.MM.DD"` and map `keys.date` to that field. The adapter keeps the original record text and reads only the calendar date. The existing issuer-only date classification still requires original documents and a complete same-day exchange check.
- `issuer-atom-v1` reads the issuer's official Atom feed using the actual zoned `published` field and its alternate HTML article link. It rejects truncated/paginated feeds and feeds whose oldest entry is inside the required window. `issuer-bloglist-v1` reads the named BlogList title link and calendar date from each actual visible issuer card, and requires the oldest shown day to precede the research window.
- A separately verified JPX PR item may use `jpx-pr-publication-v1` as an exchange publication supplement. Record the date shown in the official JPX PR archive and the verified JPX document URL. The TDnet distribution source can be the Yahoo disclosure list with `prEvidence.yahooPdfUrl` or the company-specific Kabutan news list with `prEvidence.kabutanPdfUrl`. For Kabutan, verify the disclosure row with its actual `time[datetime]` offset and the matching `tdnet-pdf.kabutan.jp` document link. The adapter corroborates the title and clock with the independent IFIS listing and re-fetches all three byte-identical PDFs. The public disclosure link remains the official JPX PDF, and the current issuer list remains required.

## Per-report evidence contract

```json
{
  "disclosureAuditPath": "<absolute inventory path returned by audit-disclosures>",
  "disclosureEvidence": [{
    "id": "<exact official inventory ID>",
    "contentUrl": "<one of that ID's verified official URLs>",
    "contentRead": true,
    "contentSha256": "<64 lowercase hex digits, actual source bytes>",
    "contentEvidence": "short quotation actually read in the original body",
    "reflections": [{
      "field": "足元材料",
      "text": "exact substantive analytical passage present in this report"
    }]
  }]
}
```

For verified zero relevant disclosures, keep `disclosureEvidence: []` and retain the ordinary grounded company analysis/source requirements. Missing/unknown official evidence is not zero. HTML/text quotations are mechanically checked against current source content. For PDFs, the bytes/hash are rechecked, while body reading, quotations and semantic adequacy remain the existing researcher responsibility; a hash does not prove that an interpretation is correct. Existing narrative/importance/primary-source quality checks still apply. Required links must survive Discord field rendering without truncation.

A genuine alert-specific insufficient-source stub additionally requires `fail --claim-id <claimId> --audit <verified-inventory-path> --alert-id <alertId> --reason "insufficient verified sources"` and must be the sole remaining owned alert. It cannot send ahead of an unfinished mixed batch. An unverified official inventory or known fundamentally material disclosure blocks this substitute. Do not use fail to bypass report repair. Retain the same owner for normal close-out; when the last report was a stub, a close-out input may contain only confirmed posted alert IDs and top-level claimId, never fabricated unposted reports.

Offline tests: workflow.test.mjs, workflow-cli.test.mjs, disclosure-audit.test.mjs, disclosure-cli.test.mjs. Test send responses are intercepted in isolated temporary directories; no real network or Discord is used. These tests and code deployment do not establish live-site coverage or production delivery success.
