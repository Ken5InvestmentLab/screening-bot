"""Read-only review of the exact Git-tree delta for the member-only rollout."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

from . import continuing_acceptance as acceptance
from .approval_git import approval_git


CONFIG = "weak-early-beta-gate/wrangler.jsonc"
ENTRY = "weak-early-beta-gate/src/index.ts"
PRESENTATION = "weak-early-beta-gate/scripts/new-a-ui-source/assets/member-presentation.js"
INITIAL_REVIEW_SCHEMA = "NEW_A_MEMBER_RELEASE_SOURCE_REVIEW_V1"
PRESENTATION_REVIEW_SCHEMA = "NEW_A_MEMBER_PRESENTATION_SUCCESSOR_SOURCE_REVIEW_V1"
COMPLETED_TIMING_REVIEW_SCHEMA = "NEW_A_MEMBER_COMPLETED_TIMING_SUCCESSOR_SOURCE_REVIEW_V1"
FUNDAMENTAL_REVIEW_SCHEMA = "NEW_A_MEMBER_FUNDAMENTAL_SUCCESSOR_SOURCE_REVIEW_V1"
ROLE_ONLY_REVIEW_SCHEMA = "NEW_A_MEMBER_ROLE_ONLY_SUCCESSOR_SOURCE_REVIEW_V1"
JOURNAL_REVIEW_SCHEMA = "NEW_A_MEMBER_JOURNAL_SUCCESSOR_SOURCE_REVIEW_V1"
FUNDAMENTAL_POPUP_REVIEW_SCHEMA = "NEW_A_MEMBER_FUNDAMENTAL_POPUP_SUCCESSOR_SOURCE_REVIEW_V1"
FUNDAMENTAL_IMPACT_REVIEW_SCHEMA = "NEW_A_MEMBER_FUNDAMENTAL_IMPACT_SUCCESSOR_SOURCE_REVIEW_V1"
CLOUD_UI_REVIEW_SCHEMA = "NEW_A_MEMBER_CLOUD_UI_SUCCESSOR_SOURCE_REVIEW_V1"
CLOUD_UI_POLISH_REVIEW_SCHEMA = "NEW_A_MEMBER_CLOUD_UI_POLISH_SUCCESSOR_SOURCE_REVIEW_V1"
CLOUD_OWNER_REFERENCE_REVIEW_SCHEMA = "NEW_A_MEMBER_CLOUD_OWNER_REFERENCE_SUCCESSOR_SOURCE_REVIEW_V1"
FUNDAMENTAL_INLINE_LINKS_REVIEW_SCHEMA = "NEW_A_MEMBER_FUNDAMENTAL_INLINE_LINKS_SUCCESSOR_SOURCE_REVIEW_V1"
UNIFIED_MEMBER_UI_REVIEW_SCHEMA = "NEW_A_MEMBER_UNIFIED_UI_SUCCESSOR_SOURCE_REVIEW_V1"
LOADING_AND_ZERO_REVIEW_SCHEMA = "NEW_A_MEMBER_LOADING_AND_ZERO_SUCCESSOR_SOURCE_REVIEW_V1"
SHARED_DEFAULTS_REVIEW_SCHEMA = "NEW_A_MEMBER_SHARED_DEFAULTS_SUCCESSOR_SOURCE_REVIEW_V1"
ENTRY_NOTICE_REVIEW_SCHEMA = "NEW_A_MEMBER_ENTRY_NOTICE_SUCCESSOR_SOURCE_REVIEW_V1"
FIXED_TRIAL_FEE_REVIEW_SCHEMA = "NEW_A_MEMBER_FIXED_TRIAL_FEE_SUCCESSOR_SOURCE_REVIEW_V1"
FREE_COMPLETED_ANALYTICS_REVIEW_SCHEMA = "NEW_A_MEMBER_FREE_COMPLETED_ANALYTICS_SUCCESSOR_SOURCE_REVIEW_V1"
SETTLED_PRICE_REVIEW_SCHEMA = "NEW_A_MEMBER_SETTLED_PRICE_SUCCESSOR_SOURCE_REVIEW_V1"
APPROVAL_TIMEOUT_REVIEW_SCHEMA = "NEW_A_MEMBER_APPROVAL_TIMEOUT_SUCCESSOR_SOURCE_REVIEW_V1"
PREMIUM_LEGACY_REVIEW_SCHEMA = "NEW_A_MEMBER_PREMIUM_LEGACY_SUCCESSOR_SOURCE_REVIEW_V1"
FUNDAMENTAL_RETENTION_REVIEW_SCHEMA = "NEW_A_MEMBER_FUNDAMENTAL_RETENTION_SUCCESSOR_SOURCE_REVIEW_V1"
PREMIUM_RUNTIME_REVIEW_SCHEMA = "NEW_A_MEMBER_PREMIUM_RUNTIME_SUCCESSOR_SOURCE_REVIEW_V1"
CARD_DISPLAY_REVIEW_SCHEMA = "NEW_A_MEMBER_CARD_DISPLAY_SUCCESSOR_SOURCE_REVIEW_V1"
PUBLICATION_RECOVERY_REVIEW_SCHEMA = "NEW_A_MEMBER_PUBLICATION_RECOVERY_SUCCESSOR_SOURCE_REVIEW_V1"
CARD_EDITORIAL_REVIEW_SCHEMA = "NEW_A_MEMBER_CARD_EDITORIAL_SUCCESSOR_SOURCE_REVIEW_V1"
HOLD_HEADING_REVIEW_SCHEMA = "NEW_A_MEMBER_HOLD_HEADING_SUCCESSOR_SOURCE_REVIEW_V1"
MEMBER_READY_REVIEW_SCHEMA = "NEW_A_MEMBER_PUBLISHED_GENERATION_SUCCESSOR_SOURCE_REVIEW_V1"
FUNDAMENTAL_BATCH_REVIEW_SCHEMA = "NEW_A_MEMBER_FUNDAMENTAL_BATCH_SUCCESSOR_SOURCE_REVIEW_V1"
HELP_TERMS_REVIEW_SCHEMA = "NEW_A_MEMBER_HELP_TERMS_SUCCESSOR_SOURCE_REVIEW_V1"
HELP_LABEL_REVIEW_SCHEMA = "NEW_A_MEMBER_HELP_LABEL_SUCCESSOR_SOURCE_REVIEW_V1"
PUBLICATION_FIRST_REVIEW_SCHEMA = "NEW_A_MEMBER_PUBLICATION_FIRST_SUCCESSOR_SOURCE_REVIEW_V1"
SOURCE_BASELINE_REVIEW_SCHEMA = "NEW_A_MEMBER_SOURCE_BASELINE_SUCCESSOR_SOURCE_REVIEW_V1"
SETTLED_HISTORY_REVIEW_SCHEMA = "NEW_A_MEMBER_SETTLED_HISTORY_SUCCESSOR_SOURCE_REVIEW_V1"
TIERED_SUCCESSOR_SCHEMAS = frozenset({
    HELP_TERMS_REVIEW_SCHEMA,
    HELP_LABEL_REVIEW_SCHEMA,
    PUBLICATION_FIRST_REVIEW_SCHEMA,
    FUNDAMENTAL_BATCH_REVIEW_SCHEMA,
    MEMBER_READY_REVIEW_SCHEMA,
    HOLD_HEADING_REVIEW_SCHEMA,
    SOURCE_BASELINE_REVIEW_SCHEMA,
    SETTLED_HISTORY_REVIEW_SCHEMA,
    CARD_EDITORIAL_REVIEW_SCHEMA,
    PUBLICATION_RECOVERY_REVIEW_SCHEMA,
    CARD_DISPLAY_REVIEW_SCHEMA,
    FUNDAMENTAL_RETENTION_REVIEW_SCHEMA,
    PREMIUM_RUNTIME_REVIEW_SCHEMA,
    PREMIUM_LEGACY_REVIEW_SCHEMA,
    FREE_COMPLETED_ANALYTICS_REVIEW_SCHEMA, SETTLED_PRICE_REVIEW_SCHEMA, APPROVAL_TIMEOUT_REVIEW_SCHEMA,
})
_PURCHASE_LABEL = '<a class="member-purchase" href="/purchase">Premiumのアクセス権を購入する</a>'.encode()
_NEW_PURCHASE_LABEL = '<a class="member-purchase" href="/purchase">Premiumアクセス権を購入する</a>'.encode()
_SUCCESSOR_REVIEW_PATHS = frozenset({
    "weak_early_beta/new_a/member_release_source_review.py",
    "weak_early_beta/new_a/member_ordinary_acceptance.py",
    "tests/test_new_a_member_release_source_review.py",
    "tests/test_new_a_member_ordinary_acceptance.py",
})
_PRESENTATION_SUCCESSOR_PATHS = _SUCCESSOR_REVIEW_PATHS | {PRESENTATION}
_COMPLETED_TIMING_DELTAS = {
    "weak-early-beta-gate/scripts/prepare-new-a-member-projection.cjs": (
        (b"date <= terminal && terminal < asOf", b"date <= terminal && terminal <= asOf"),
        (b"terminal < closed && closed < asOf", b"terminal < closed && closed <= asOf"),
    ),
    "weak-early-beta-gate/src/new-a-member-projection.ts": (
        (b"row.completed_on >= row.date && row.completed_on < through",
         b"row.completed_on >= row.date && row.completed_on <= through"),
    ),
    "weak_early_beta/new_a/member_publisher.py": (
        (b'row["date"] <= row["completed_on"] < as_of', b'row["date"] <= row["completed_on"] <= as_of'),
    ),
}
_TIMING_GUIDE = "weak-early-beta-gate/AGENTS.md"
_TIMING_GUIDE_DELTA = (
    b"Build and paginate that view on the server from verified prior-session monitoring closures and settled virtual "
    b"positions. The current session's activity and active monitoring are Premium only, including their API and pagination metadata.",
    b"Build and paginate that view on the server from verified monitoring closures and settled virtual positions "
    b"completed on or before the latest published session. The current session's action cards and active "
    b"monitoring are Premium only, including their API and pagination metadata.",
)
_MEMBER_DASHBOARD_PATHS = {
    PRESENTATION,
    "weak-early-beta-gate/scripts/build-new-a-member-frame.mjs",
    "weak-early-beta-gate/scripts/new-a-ui-source/assets/member-loader.js",
    "tests/new_a_role_presentation_candidate.test.cjs",
}
_TIMING_SUCCESSOR_PATHS = _SUCCESSOR_REVIEW_PATHS | set(_COMPLETED_TIMING_DELTAS) | _MEMBER_DASHBOARD_PATHS | {
    _TIMING_GUIDE,
    "tests/new_a_member_projection_preparation.test.cjs",
    "tests/new_a_member_projection.test.cjs",
    "tests/test_new_a_member_publisher.py",
}
_FUNDAMENTAL_BASELINE = "161016a13ca09c310fd8d24687743ad90831a8a9"
_FUNDAMENTAL_MIGRATION = "weak-early-beta-gate/member-migrations/0005_new_a_member_fundamental_reports.sql"
_FUNDAMENTAL_PRODUCT_PATHS = frozenset({
    _FUNDAMENTAL_MIGRATION,
    PRESENTATION,
    "weak-early-beta-gate/scripts/new-a-ui-source/assets/member-loader.js",
    "weak-early-beta-gate/scripts/prepare-new-a-member-projection.cjs",
    "weak-early-beta-gate/src/new-a-member-projection.ts",
    "weak-early-beta-gate/src/new-a-member-services.ts",
    "weak-early-beta-gate/src/new-a-role-facade.ts",
    "weak_early_beta/new_a/fundamentals.py",
    "weak_early_beta/new_a/member_publisher.py",
    "tests/new_a_member_consistency.test.cjs",
    "tests/new_a_member_projection_preparation.test.cjs",
    "tests/new_a_member_worker.test.cjs",
    "tests/new_a_role_presentation_candidate.test.cjs",
    "tests/test_new_a_fundamentals.py",
    "tests/test_new_a_member_publisher.py",
})
# Exact product blobs reviewed from 94d7474 (server), 23dc91c (daily) and ea85b3a (UI).
# Include the full migration bytes; earlier member migrations may not change.
_FUNDAMENTAL_PRODUCT_SHA256 = "0fa5bc7d4f39a024b0031fdb0613d4630c7082d60f718ec82e8b1a2a94cd2800"
_ROLE_ONLY_BASELINE = "df7210db699677669e0b5c6d3fc2ea941bd37b96"
_ROLE_ONLY_CONFIG_LINE = b'    "CLOUD_MEMBER_VIEW_ENABLED": "true",\n'
_ROLE_ONLY_AUDIENCE_LINE = b'    "CLOUD_MEMBER_AUDIENCE": "role_only",\n'
_TIERED_AUDIENCE_LINE = b'    "CLOUD_MEMBER_AUDIENCE": "tiered",\n'
_ROLE_ONLY_MIGRATION = "weak-early-beta-gate/member-migrations/0006_new_a_role_only_response_observations.sql"
_ROLE_ONLY_PRODUCT_PATHS = frozenset({
    _ROLE_ONLY_MIGRATION,
    "weak-early-beta-gate/AGENTS.md",
    "weak-early-beta-gate/scripts/prepare-new-a-member-stage.mjs",
    "weak-early-beta-gate/scripts/verify-release-config.mjs",
    "weak-early-beta-gate/src/new-a-member-observation.ts",
    "weak-early-beta-gate/src/new-a-role-facade.ts",
    "weak-early-beta-gate/src/new-a-role-integration.ts",
    "weak_early_beta/new_a/member_observation_host.py",
    "weak_early_beta/new_a/member_rollout.py",
})
_ROLE_ONLY_TEST_PATHS = frozenset({
    "tests/cloud_release_config.test.cjs",
    "tests/new_a_member_stage_config.test.mjs",
    "tests/new_a_member_worker.test.cjs",
    "tests/new_a_role_facade_candidate.test.cjs",
    "tests/test_new_a_member_observation_host.py",
    "tests/test_new_a_member_rollout.py",
})
_ROLE_ONLY_PRODUCT_SHA256 = "1b64c36fd3f8dca56e204fa3d115219b19bcd3db6060db7053388e481c7bce63"
_JOURNAL_BASELINE = "70d475ad9980bc8d116525c0717e948590624f89"
_JOURNAL_REVIEWED_RUNNER = "853832eabd6a289761080ae0bc54e142d3d8f65f"
_JOURNAL_PRODUCT_PATHS = frozenset({
    "scripts/windows/weak-early-beta-daily-runner.mjs",
    "scripts/windows/weak-early-beta-run-journal.mjs",
    "scripts/windows/test-weak-early-beta-daily-runner.mjs",
})
_JOURNAL_PRODUCT_SHA256 = "e7c7307d629e08e67aaca69d2c6b8784c21f87e36ae45225ef39d95ee7861159"
_FUNDAMENTAL_POPUP_BASELINE = "00fab418f14488b3fa2f347213e52d0e8e5e1853"
_FUNDAMENTAL_POPUP_REVIEWED_PATHS = frozenset({
    PRESENTATION,
    "weak-early-beta-gate/scripts/new-a-ui-source/presentation-adapter.cjs",
    "weak-early-beta-gate/scripts/new-a-ui-source/frame.html",
    "weak-early-beta-gate/scripts/new-a-ui-source/assets/browser-transport.js",
    "weak-early-beta-gate/scripts/new-a-ui-source/assets/finite-dom.js",
    "weak-early-beta-gate/scripts/new-a-ui-source/assets/owner-loader.js",
    "tests/new_a_analytics_presets.test.cjs",
    "tests/new_a_dashboard_details.test.cjs",
    "tests/new_a_role_presentation_candidate.test.cjs",
})
_FUNDAMENTAL_POPUP_REVIEWED_SHA256 = "d9053b478b5c7b4ce7fbebadcaa338caf142a8b4b1996c7f6a68125508f3a87e"
_FUNDAMENTAL_IMPACT_BASELINE = "c8d76064fa236e2c79801484394ca032c01c994b"
_FUNDAMENTAL_IMPACT_REVIEWED_PATHS = frozenset({
    PRESENTATION,
    "weak-early-beta-gate/scripts/new-a-ui-source/presentation-adapter.cjs",
    "tests/new_a_dashboard_details.test.cjs",
    "tests/new_a_role_presentation_candidate.test.cjs",
})
_FUNDAMENTAL_IMPACT_REVIEWED_SHA256 = "e1a500af4f1160265639f5b86a911c1fc3cd19383bd1d08f5fea0e51dcba3904"
_CLOUD_UI_BASELINE = "e063e97722eaa1edc5fdbe7bdb12d079e29603b1"
_CLOUD_UI_ADDITIONS = frozenset({
    "weak-early-beta-gate/scripts/new-a-ui-source/assets/owner-settings.js",
    "weak-early-beta-gate/scripts/new-a-ui-source/settings-dialog.js",
})
_CLOUD_UI_PRODUCT_PATHS = _CLOUD_UI_ADDITIONS | frozenset({
    "tests/cloud_bundle_sync.test.cjs",
    "tests/new_a_analytics_presets.test.cjs",
    "tests/new_a_dashboard_details.test.cjs",
    "tests/new_a_member_consistency.test.cjs",
    "tests/new_a_owner_connection.test.cjs",
    "tests/new_a_role_presentation_candidate.test.cjs",
    "tests/new_a_role_settings_candidate.test.cjs",
    "weak-early-beta-gate/scripts/build-new-a-frame.mjs",
    "weak-early-beta-gate/scripts/build-new-a-member-frame.mjs",
    "weak-early-beta-gate/scripts/new-a-ui-source/assets/browser-transport.js",
    "weak-early-beta-gate/scripts/new-a-ui-source/assets/finite-controller.js",
    "weak-early-beta-gate/scripts/new-a-ui-source/assets/finite-dom.js",
    "weak-early-beta-gate/scripts/new-a-ui-source/assets/member-loader.js",
    "weak-early-beta-gate/scripts/new-a-ui-source/assets/member-presentation.js",
    "weak-early-beta-gate/scripts/new-a-ui-source/assets/member-settings.js",
    "weak-early-beta-gate/scripts/new-a-ui-source/assets/owner-loader.js",
    "weak-early-beta-gate/scripts/new-a-ui-source/frame.html",
    "weak-early-beta-gate/scripts/new-a-ui-source/history-body.html",
    "weak-early-beta-gate/scripts/new-a-ui-source/patch-legacy-interactions.mjs",
    "weak-early-beta-gate/scripts/new-a-ui-source/settings-body.html",
})
_CLOUD_UI_PRODUCT_SHA256 = "5915482eefe7eaa5be1240fc42735e747777323462c5ed83635239e9dee3d957"
_CLOUD_UI_POLISH_BASELINE = "17730c08d10455f02c0da57071fec67a1d8eaf92"
_CLOUD_UI_POLISH_PRODUCT_PATHS = frozenset({
    ENTRY,
    PRESENTATION,
    "tests/cloud_bundle_sync.test.cjs",
    "tests/new_a_member_worker.test.cjs",
    "tests/new_a_role_presentation_candidate.test.cjs",
    "tests/new_a_role_settings_candidate.test.cjs",
    "weak-early-beta-gate/scripts/build-new-a-frame.mjs",
    "weak-early-beta-gate/scripts/build-new-a-member-frame.mjs",
    "weak-early-beta-gate/scripts/new-a-ui-source/assets/member-loader.js",
    "weak-early-beta-gate/scripts/new-a-ui-source/assets/member-settings.js",
    "weak-early-beta-gate/scripts/new-a-ui-source/assets/owner-loader.js",
    "weak-early-beta-gate/scripts/new-a-ui-source/frame.html",
    "weak-early-beta-gate/scripts/new-a-ui-source/guide-body.html",
    "weak-early-beta-gate/scripts/new-a-ui-source/settings-dialog.js",
    "weak-early-beta-gate/src/new-a-member-services.ts",
    "weak-early-beta-gate/src/new-a-role-facade.ts",
    "weak-early-beta-gate/src/new-a-role-integration.ts",
})
# The entrypoint binds the shared page to the verified owner after the existing owner gate.
_CLOUD_UI_POLISH_ENTRY_SHA256 = "7b467a73aa92f487c4020715b773e35b955d31f51a0dc903ab187590557b9391"
_CLOUD_UI_POLISH_PRODUCT_SHA256 = "c6714194ec123f2f6c262d5638de25d04ce3ea34ec95a10c136ffbbc7f76c479"
_CLOUD_OWNER_REFERENCE_BASELINE = "0c3643c5b3ae513c95818fabc418affd56937d72"
_CLOUD_OWNER_REFERENCE_ADDITIONS = frozenset({
    "weak-early-beta-gate/scripts/new-a-ui-source/assets/reference-analytics.js",
    "weak-early-beta-gate/scripts/new-a-ui-source/reference-analytics.cjs",
    "weak-early-beta-gate/scripts/new-a-ui-source/reference-history.cjs",
    "weak-early-beta-gate/scripts/prepare-new-a-reference-view.cjs",
    "weak-early-beta-gate/src/new-a-member-reference.ts",
    "weak_early_beta/new_a/member_reference_publication.py",
})
_CLOUD_OWNER_REFERENCE_PRODUCT_PATHS = _CLOUD_OWNER_REFERENCE_ADDITIONS | {
    "tests/cloud_bundle_sync.test.cjs",
    "tests/new_a_dashboard_details.test.cjs",
    "tests/new_a_member_consistency.test.cjs",
    "tests/new_a_member_stage_config.test.mjs",
    "tests/new_a_member_worker.test.cjs",
    "tests/new_a_role_presentation_candidate.test.cjs",
    "tests/test_new_a_member_publisher.py",
    "weak-early-beta-gate/scripts/build-new-a-frame.mjs",
    "weak-early-beta-gate/scripts/build-new-a-member-frame.mjs",
    "weak-early-beta-gate/scripts/new-a-ui-source/assets/finite-controller.js",
    "weak-early-beta-gate/scripts/new-a-ui-source/assets/finite-dom.js",
    "weak-early-beta-gate/scripts/new-a-ui-source/assets/member-loader.js",
    "weak-early-beta-gate/scripts/new-a-ui-source/assets/member-presentation.js",
    "weak-early-beta-gate/scripts/new-a-ui-source/assets/owner-loader.js",
    "weak-early-beta-gate/scripts/new-a-ui-source/frame.html",
    "weak-early-beta-gate/scripts/prepare-new-a-member-projection.cjs",
    "weak-early-beta-gate/scripts/prepare-new-a-member-stage.mjs",
    "weak-early-beta-gate/src/index.ts",
    "weak-early-beta-gate/src/new-a-cloud.ts",
    "weak-early-beta-gate/src/new-a-member-services.ts",
    "weak-early-beta-gate/src/new-a-role-facade.ts",
    "weak-early-beta-gate/src/new-a-role-integration.ts",
    "weak_early_beta/new_a/member_publication.py",
}
_CLOUD_OWNER_REFERENCE_REVIEW_PATHS = frozenset({
    "weak_early_beta/new_a/member_ordinary_acceptance.py",
    "weak_early_beta/new_a/member_release_source_review.py",
})
_CLOUD_OWNER_REFERENCE_AUTH_SHA256 = {
    "weak-early-beta-gate/src/index.ts": "feea298e2a0d58ccfdb771ee56ca2980e3cded6a728cc93243bbe570c1cbf8e4",
    "weak-early-beta-gate/src/new-a-cloud.ts": "a75dae1a95b9d1544bf60fb80a237a496d902ad1cf8c3be18102b3fe6defad96",
}
_CLOUD_OWNER_REFERENCE_PRODUCT_SHA256 = "47a5ca746658c3e299642dc8ec4548fa0ab9ce165d350644b35dfa9179e5b284"
_FUNDAMENTAL_INLINE_LINKS_BASELINE = "c6d818555a8124771a08ee71f47ee50a25a4eb9c"
_FUNDAMENTAL_INLINE_LINKS_ADDITIONS = frozenset({"weak-early-beta-gate/scripts/new-a-ui-source/fundamental-text.cjs"})
_FUNDAMENTAL_INLINE_LINKS_PRODUCT_PATHS = _FUNDAMENTAL_INLINE_LINKS_ADDITIONS | {
    "tests/new_a_analytics_presets.test.cjs",
    "tests/new_a_dashboard_details.test.cjs",
    "tests/new_a_member_consistency.test.cjs",
    "tests/new_a_role_presentation_candidate.test.cjs",
    "tests/test_new_a_wrangler_response.py",
    "weak-early-beta-gate/scripts/build-new-a-frame.mjs",
    "weak-early-beta-gate/scripts/new-a-ui-source/assets/finite-dom.js",
    "weak-early-beta-gate/scripts/new-a-ui-source/assets/member-presentation.js",
    "weak-early-beta-gate/scripts/new-a-ui-source/assets/reference-analytics.js",
    "weak-early-beta-gate/scripts/new-a-ui-source/presentation-adapter.cjs",
    "weak_early_beta/new_a/publisher.py",
}
_FUNDAMENTAL_INLINE_LINKS_PRODUCT_SHA256 = "19dfb11e8f65675fefa6292204b44d7e8f63aab6042bed01d71dcdafcfb45045"
_UNIFIED_MEMBER_UI_BASELINE = "fca0cde2c46411e82a5f0d12064be19396c43432"
_UNIFIED_MEMBER_UI_PRODUCT_PATHS = frozenset({ENTRY, "tests/new_a_member_worker.test.cjs", "weak-early-beta-gate/AGENTS.md"})
_UNIFIED_MEMBER_UI_PRODUCT_SHA256 = "8b644e26f6109a99dc6334065fe054b3313aa6a24857b370825ed8bf2f773cfa"
_UNIFIED_MEMBER_UI_ENTRY_SHA256 = "20b368723cae0de43ce19e4fda894c1e19a037e5d0537aaa520205ff42808d5f"
_LOADING_AND_ZERO_BASELINE = "be45d0fc3fb499af5fc2958295c13ce18f056ad7"
_LOADING_AND_ZERO_PRODUCT_PATHS = frozenset({
    "tests/new_a_analytics_presets.test.cjs",
    "tests/new_a_member_consistency.test.cjs",
    "tests/new_a_member_worker.test.cjs",
    "tests/new_a_role_presentation_candidate.test.cjs",
    "weak-early-beta-gate/scripts/new-a-ui-source/assets/member-loader.js",
    "weak-early-beta-gate/scripts/new-a-ui-source/assets/member-presentation.js",
    "weak-early-beta-gate/scripts/new-a-ui-source/assets/reference-analytics.js",
    "weak-early-beta-gate/scripts/new-a-ui-source/frame.html",
    "weak-early-beta-gate/src/new-a-member-reference.ts",
    "weak-early-beta-gate/src/new-a-member-services.ts",
})
_LOADING_AND_ZERO_PRODUCT_SHA256 = "0a8c28e426a5f20324ae7daf8de4e6ab8757569c0aa54139dffae2076fd9ef42"
_SHARED_DEFAULTS_BASELINE = "7c05fb73f3169822746fbc39a27e987393d4927e"
_SHARED_DEFAULTS_PRODUCT_PATHS = frozenset({
    "tests/cloud_bundle_sync.test.cjs",
    "tests/new_a_member_consistency.test.cjs",
    "tests/new_a_member_worker.test.cjs",
    "tests/new_a_role_settings_candidate.test.cjs",
    "tests/test_new_a_member_publisher.py",
    "weak-early-beta-gate/scripts/new-a-ui-source/assets/member-loader.js",
    "weak-early-beta-gate/scripts/new-a-ui-source/assets/member-settings.js",
    "weak-early-beta-gate/scripts/new-a-ui-source/frame.html",
    "weak-early-beta-gate/scripts/new-a-ui-source/guide-body.html",
    "weak-early-beta-gate/scripts/prepare-new-a-member-projection.cjs",
    "weak-early-beta-gate/scripts/prepare-new-a-reference-view.cjs",
    "weak-early-beta-gate/src/new-a-member-projection.ts",
    "weak-early-beta-gate/src/new-a-member-reference.ts",
    "weak-early-beta-gate/src/new-a-member-services.ts",
    "weak-early-beta-gate/src/new-a-member-storage.ts",
    "weak-early-beta-gate/src/new-a-preferences.ts",
    "weak_early_beta/new_a/member_reference_publication.py",
})
_SHARED_DEFAULTS_PRODUCT_SHA256 = "08dd9366f491e0ba40a907799261b6e43e88e8414e2cc0366932670e3a9ea856"
_ENTRY_NOTICE_BASELINE = "ce6251769a756c3c8903bc1975ca1eea4c98fa84"
_ENTRY_NOTICE_PRODUCT_PATHS = frozenset({
    "tests/test_new_a_connection.py",
    "weak_early_beta/new_a/notifications.py",
})
_ENTRY_NOTICE_PRODUCT_SHA256 = "83013b29f8bb050eed03cae127be2f6ba31b22af4ae963019efbe88575fb17a8"
_FIXED_TRIAL_FEE_PRODUCT_PATHS = _ENTRY_NOTICE_PRODUCT_PATHS | {
    "tests/cloud_bundle_sync.test.cjs",
    "tests/new_a_member_storage.test.cjs",
    "tests/new_a_owner_connection.test.cjs",
    "tests/new_a_role_settings_candidate.test.cjs",
    "tests/test_new_a_member_ordinary_acceptance.py",
    "tests/test_new_a_member_release_source_review.py",
    "tests/test_new_a_release_maintenance.py",
    "weak-early-beta-gate/scripts/new-a-ui-source/assets/finite-controller.js",
    "weak-early-beta-gate/scripts/new-a-ui-source/assets/member-settings.js",
    "weak-early-beta-gate/src/new-a-member-storage.ts",
    "weak-early-beta-gate/scripts/new-a-ui-source/guide-body.html",
    "weak-early-beta-gate/src/new-a-preferences.ts",
    "weak_early_beta/new_a/member_ordinary_acceptance.py",
    "weak_early_beta/new_a/release_maintenance.py",
}
_FIXED_TRIAL_FEE_PRODUCT_SHA256 = "8abcbd6154c76dcd8d34fb683a1aec67d8aa0fcb2bb24105bfde8dd6c2a0d443"
_FIXED_TRIAL_FEE_AUDIT_REPAIR_PATHS = _FIXED_TRIAL_FEE_PRODUCT_PATHS | {
    "tests/test_new_a_continuing_acceptance.py",
    "weak_early_beta/new_a/continuing_acceptance.py",
}
_FIXED_TRIAL_FEE_AUDIT_REPAIR_SHA256 = "3670ea456b0a53c4a9c5d2c9f76844ae4d9d4427e9cba411371ec02dad4bea93"
_FREE_COMPLETED_ANALYTICS_BASELINE = "717eb480e19ad82ed9ca2ae41e6c866a7f418255"
_FREE_COMPLETED_ANALYTICS_CALENDAR = "weak-early-beta-gate/src/new-a-market-calendar.ts"
_FREE_COMPLETED_ANALYTICS_PRODUCT_PATHS = _MEMBER_DASHBOARD_PATHS | {
    _FREE_COMPLETED_ANALYTICS_CALENDAR,
    "weak-early-beta-gate/AGENTS.md",
    "weak-early-beta-gate/src/new-a-role-facade.ts",
    "weak-early-beta-gate/src/new-a-member-services.ts",
    "weak-early-beta-gate/src/new-a-member-storage.ts",
    "weak-early-beta-gate/src/new-a-role-integration.ts",
    "weak-early-beta-gate/src/new-a-member-reference.ts",
    "weak-early-beta-gate/scripts/new-a-ui-source/assets/reference-analytics.js",
    "weak-early-beta-gate/scripts/new-a-ui-source/assets/member-settings.js",
    "weak-early-beta-gate/scripts/new-a-ui-source/frame.html",
    "weak-early-beta-gate/scripts/new-a-ui-source/guide-body.html",
    "weak-early-beta-gate/scripts/verify-release-config.mjs",
    "tests/cloud_bundle_sync.test.cjs",
    "tests/cloud_release_config.test.cjs",
    "tests/new_a_member_consistency.test.cjs",
    "tests/new_a_member_storage.test.cjs",
    "tests/new_a_member_worker.test.cjs",
    "tests/new_a_role_facade_candidate.test.cjs",
    "tests/new_a_role_settings_candidate.test.cjs",
    "tests/new_a_analytics_presets.test.cjs",
}
_FREE_COMPLETED_ANALYTICS_PRODUCT_SHA256 = "0d7bb3d19dcc41f06d0f2c0dff9797607f8690cad188a9cbac706c3096ef7d74"
_SETTLED_PRICE_BASELINE = "ff41f59ee2ad4fcd41c5b0244fe3461164bfbf31"
_SETTLED_PRICE_ADDITIONS = frozenset({
    "tests/test_new_a_missing_quote_decisions.py",
    "tests/test_new_a_settlement_recovery.py",
    "weak_early_beta/new_a/settlement_recovery.py",
})
_SETTLED_PRICE_PRODUCT_PATHS = _SETTLED_PRICE_ADDITIONS | {
    "tests/new_a_analytics_presets.test.cjs",
    "tests/new_a_member_projection_preparation.test.cjs",
    "weak-early-beta-gate/scripts/new-a-ui-source/engine/dataset-runtime.cjs",
    "weak-early-beta-gate/scripts/new-a-ui-source/engine/finite-engine.cjs",
    "weak-early-beta-gate/scripts/new-a-ui-source/engine/worker-entry.js",
    "weak-early-beta-gate/scripts/prepare-new-a-member-projection.cjs",
    "weak_early_beta/new_a/bundle.py",
    "weak_early_beta/new_a/packet.py",
    "weak_early_beta/new_a/pipeline.py",
    "weak_early_beta/new_a/run.py",
}
_SETTLED_PRICE_PRODUCT_SHA256 = "5d8c394367851f43b35dfc8818ee221843c518a8e94a5ac0cbcd535546807b42"
_APPROVAL_TIMEOUT_BASELINE = "0b756dba967e3a9b96543268a91013d8bcc5f9ff"
_APPROVAL_TIMEOUT_ADDITIONS = frozenset({
    "scripts/windows/cloud-premium-disclosure-audit.mjs",
    "scripts/windows/cloud-premium-references/.gitattributes",
    "scripts/windows/cloud-premium-references/AUTOMATION_PROMPT.md",
    "scripts/windows/cloud-premium-references/DISCLOSURE_AUDIT.md",
    "scripts/windows/cloud-premium-references/FUNDAMENTAL_EXAMPLES.md",
    "scripts/windows/cloud-premium-references/PREMIUM_PM_SAVED_PROMPT.txt",
    "scripts/windows/cloud-premium-references/report_quality.md",
    "scripts/windows/premium-disclosure-research/atomic-json.mjs",
    "scripts/windows/premium-disclosure-research/disclosure-audit.mjs",
    "scripts/windows/premium-disclosure-research/disclosure-title.mjs",
    "scripts/windows/premium-disclosure-research/evidence-cache.mjs",
    "scripts/windows/premium-disclosure-research/http-pdf-content-compare.py",
    "scripts/windows/premium-disclosure-research/http-pdf-content-review.mjs",
    "scripts/windows/premium-disclosure-research/issuer-beat-releases.mjs",
    "scripts/windows/premium-disclosure-research/issuer-feed-rows.mjs",
    "scripts/windows/premium-disclosure-research/issuer-http-discovery.mjs",
    "scripts/windows/premium-disclosure-research/issuer-intrance-archive.mjs",
    "scripts/windows/premium-disclosure-research/issuer-ir-record.mjs",
    "scripts/windows/premium-disclosure-research/issuer-nakabayashi-list.mjs",
    "scripts/windows/premium-disclosure-research/issuer-paginated-archives.mjs",
    "scripts/windows/premium-disclosure-research/issuer-softbank-list.mjs",
    "scripts/windows/premium-disclosure-research/pdf-evidence.py",
    "scripts/windows/premium-disclosure-research/research-document.mjs",
    "scripts/windows/test-cloud-premium-disclosure-audit.mjs",
    "tests/test_new_a_approval_git.py",
    "weak_early_beta/new_a/approval_git.py",
})
_APPROVAL_TIMEOUT_PRODUCT_PATHS = _APPROVAL_TIMEOUT_ADDITIONS | {
    "scripts/windows/new-a-fundamental-stage.mjs",
    "scripts/windows/preflight-reconciliation.mjs",
    "scripts/windows/test-new-a-fundamental-stage.mjs",
    "scripts/windows/test-new-a-runner.mjs",
    "scripts/windows/test-preflight-reconciliation.mjs",
    "scripts/windows/test-weak-early-beta-point-in-time-post.mjs",
    "scripts/windows/weak-early-beta-daily-runner.mjs",
    "weak_early_beta/new_a/continuing_acceptance.py",
    "weak_early_beta/new_a/continuing_transition.py",
    "weak_early_beta/new_a/execution_identity.py",
    "weak_early_beta/scripts/post_historical_snapshot.mjs",
}
_APPROVAL_TIMEOUT_PRODUCT_SHA256 = "557a13502c3d74831c4d47c20bd51a597f3100e276a14daa5d387383ff8277b5"
_PREMIUM_LEGACY_BASELINE = "1d3033f6b4b4ceeb6443d9a4ebef71974524d9cb"
_PREMIUM_LEGACY_ADDITIONS = frozenset({
    "scripts/windows/cloud-premium-references/PREMIUM_LEGACY_WORKER.mjs",
    "scripts/windows/cloud-premium-references/PREMIUM_NO_SEND_PRELOAD.mjs",
    "scripts/windows/cloud-premium-references/AGENTS.md",
})
_PREMIUM_LEGACY_PRODUCT_PATHS = _PREMIUM_LEGACY_ADDITIONS | {
    "weak_early_beta/new_a/AGENTS.md",
    "scripts/windows/weak-early-beta-fundamental-runner.mjs",
    "weak_early_beta/new_a/fundamentals.py",
    "tests/test_new_a_fundamentals.py",
    "scripts/windows/cloud-premium-references/AUTOMATION_PROMPT.md",
    "scripts/windows/cloud-premium-references/FUNDAMENTAL_EXAMPLES.md",
    "scripts/windows/cloud-premium-references/PREMIUM_PM_SAVED_PROMPT.txt",
    "scripts/windows/new-a-fundamental-stage.mjs",
    "scripts/windows/test-new-a-fundamental-stage.mjs",
    "scripts/windows/weak-early-beta-daily-runner.mjs",
    "scripts/windows/test-new-a-runner.mjs",
    "scripts/windows/preflight-reconciliation.mjs",
    "scripts/windows/test-preflight-reconciliation.mjs",
}
_PREMIUM_LEGACY_PRODUCT_SHA256 = "c6e04f5287968184ccd3d25f737d14ce3265542dbfdc1efc12ae1169a11a08f3"
_FUNDAMENTAL_RETENTION_BASELINE = "65ec8d382cc2b200a18a81d2f70130fa277f4b18"
_FUNDAMENTAL_RETENTION_PRODUCT_PATHS = frozenset({
    "weak_early_beta/new_a/fundamentals.py", "weak_early_beta/new_a/cli.py",
    "weak_early_beta/new_a/AGENTS.md", "tests/test_new_a_fundamentals.py",
    "weak-early-beta-gate/scripts/new-a-ui-source/assets/owner-loader.js",
    "weak-early-beta-gate/scripts/new-a-ui-source/assets/member-loader.js", PRESENTATION,
    "weak-early-beta-gate/scripts/new-a-ui-source/frame.html",
    "tests/new_a_dashboard_details.test.cjs", "tests/new_a_role_presentation_candidate.test.cjs",
    "weak_early_beta/new_a/notifications.py", "tests/test_new_a_connection.py",
})
_FUNDAMENTAL_RETENTION_PRODUCT_SHA256 = "8cb6a0394a599d8906b533f436b4ea34893c23829cb8bc4e2e6d3908356c1fed"
_PREMIUM_RUNTIME_BASELINE = "ba88d386c111422ae09e203e4f3a6f53dd8806c1"
_PREMIUM_RUNTIME_ADDITIONS = frozenset({
    "scripts/windows/new-a-completed-fundamental-recovery.mjs",
    "scripts/windows/test-new-a-completed-fundamental-recovery.mjs",
    "scripts/windows/cloud-premium-references/PREMIUM_CLOUD_WORKER.mjs",
    "scripts/windows/cloud-premium-references/SOURCE_COMPANION_REVIEW.md",
})
_PREMIUM_RUNTIME_PRODUCT_PATHS = _PREMIUM_RUNTIME_ADDITIONS | {
    "scripts/windows/new-a-fundamental-stage.mjs", "scripts/windows/test-new-a-fundamental-stage.mjs",
    "weak_early_beta/new_a/fundamentals.py", "tests/test_new_a_fundamentals.py", "weak_early_beta/new_a/AGENTS.md",
    "weak_early_beta/new_a/notifications.py", "tests/test_new_a_connection.py",
    "scripts/windows/cloud-premium-references/AGENTS.md",
}
_PREMIUM_RUNTIME_PRODUCT_SHA256 = "deeb6ebf5181f49948917450a2d24dc854408a176f05e62896eb71268c03f646"
_CARD_DISPLAY_BASELINE = "7bb9daec4cf5a5697045854ee840bb5a48eb7db2"
_CARD_DISPLAY_PRODUCT_PATHS = frozenset({
    PRESENTATION, "weak-early-beta-gate/scripts/new-a-ui-source/assets/member-loader.js",
    "weak-early-beta-gate/scripts/new-a-ui-source/frame.html", "weak-early-beta-gate/AGENTS.md",
    "tests/new_a_role_presentation_candidate.test.cjs",
})
_CARD_DISPLAY_PRODUCT_SHA256 = "89ca8793f2d15c701e33899267dbdb2b7193e9bba9a76b59e8aab3329a2eb5dd"
_PUBLICATION_RECOVERY_BASELINE = "1d9803f7169a1e82529a13677a72ea0599dd42af"
_PUBLICATION_RECOVERY_PRODUCT_PATHS = frozenset({
    "weak-early-beta-gate/scripts/new-a-ui-source/assets/member-loader.js",
    "weak-early-beta-gate/AGENTS.md", "tests/new_a_member_consistency.test.cjs",
    "weak_early_beta/new_a/publisher.py", "weak_early_beta/new_a/member_publisher.py",
    "weak_early_beta/new_a/notifications.py", "weak_early_beta/new_a/AGENTS.md",
    "tests/test_new_a_wrangler_response.py", "tests/test_new_a_member_publisher.py", "tests/test_new_a_connection.py",
})
_PUBLICATION_RECOVERY_PRODUCT_SHA256 = "2dfb9b1255e243b0281e405d0ad80d935b0f1b5eaa8626901561384c766069fe"
_HOLD_HEADING_BASELINE = "a3762af0017eb9ee03c95d53a21fc5e60a44f728"
_MEMBER_READY_BASELINE = "3c589967ae782a9834f992fb2dd041307f37e156"
_MEMBER_READY_PRODUCT_PATHS = frozenset({
    'weak-early-beta-gate/AGENTS.md',
    'weak-early-beta-gate/src/new-a-member-current.ts',
    'weak-early-beta-gate/src/new-a-member-projection.ts',
    'weak-early-beta-gate/src/new-a-role-integration.ts',
    'weak_early_beta/new_a/member_publisher.py',
    'tests/new_a_member_current.test.cjs',
    'tests/new_a_member_worker.test.cjs',
})
_MEMBER_READY_PRODUCT_SHA256 = '2fb177b5c12055f3975fcc2d45318ec23f63df033376e8b19d1e2812d87f440d'
_HELP_TERMS_BASELINE = "b8757da8834b5aef7769511a8f485a231ba0279f"
_HELP_TERMS_PRODUCT_PATHS = frozenset({'tests/cloud_bundle_sync.test.cjs', 'weak-early-beta-gate/scripts/new-a-ui-source/guide-body.html'})
_HELP_TERMS_PRODUCT_SHA256 = "dc2f97a79ef5df40c6b7b6d17e6296e1ae269e8a5a43b7648de05ea4fe9b74ac"
_HELP_LABEL_BASELINE = "94b3b19fb952d054b9caa0a783f0b268dde3aff0"
_HELP_LABEL_PRODUCT_PATHS = frozenset({'weak-early-beta-gate/scripts/new-a-ui-source/guide-body.html'})
_HELP_LABEL_PRODUCT_SHA256 = "8cdc15f3bcd36285c7b90dd7ca50de81766a4849608b3d42191bfd700262ba88"
_PUBLICATION_FIRST_BASELINE = "a993db6d5cab8f9f907a36fdf0767d9fa8189602"
_PUBLICATION_FIRST_PRODUCT_PATHS = frozenset({
    "scripts/windows/weak-early-beta-daily-runner.mjs",
    "scripts/windows/test-new-a-runner.mjs",
    "scripts/windows/AGENTS.md",
})
_PUBLICATION_FIRST_PRODUCT_SHA256 = "d199ea8c8a3eddbb245b611a210993371c954ea12180fe99fe76a98d2b5326f4"
_FUNDAMENTAL_BATCH_BASELINE = "a3a3896e11152e3d07555df8e5eef29c8231ce21"
_FUNDAMENTAL_BATCH_PRODUCT_PATHS = frozenset({
    "scripts/windows/cloud-premium-references/AGENTS.md",
    "scripts/windows/cloud-premium-references/AUTOMATION_PROMPT.md",
    "scripts/windows/cloud-premium-references/COPY_MANIFEST.json",
    "scripts/windows/cloud-premium-references/PREMIUM_CLOUD_WORKER.mjs",
    "scripts/windows/cloud-premium-references/SOURCE_COMPANION_REVIEW.md",
    "scripts/windows/new-a-fundamental-stage.mjs",
    "scripts/windows/test-new-a-fundamental-stage.mjs",
})
_FUNDAMENTAL_BATCH_PRODUCT_SHA256 = "080d5a4790e0dff34eaef7554400d75497ec43112d8e028f8f53da5c44232ba3"
_FUNDAMENTAL_BATCH_ENTRY_PRODUCT_PATHS = _FUNDAMENTAL_BATCH_PRODUCT_PATHS | frozenset({
    'weak-early-beta-gate/package.json',
    'weak-early-beta-gate/scripts/new-a-ui-source/engine/finite-engine.cjs',
    'weak-early-beta-gate/scripts/new-a-ui-source/assets/owner-loader.js',
    'weak-early-beta-gate/scripts/new-a-ui-source/assets/member-presentation.js',
    'weak-early-beta-gate/scripts/prepare-new-a-reference-view.cjs',
    'weak-early-beta-gate/scripts/prepare-new-a-entry-plan.cjs',
    'weak_early_beta/new_a/notifications.py',
    'weak_early_beta/new_a/AGENTS.md',
    'tests/new_a_entry_plan.test.cjs',
    'tests/new_a_dashboard_details.test.cjs',
    'tests/test_new_a_connection.py',
})
_FUNDAMENTAL_BATCH_ENTRY_ADDITIONS = frozenset({
    'weak-early-beta-gate/scripts/prepare-new-a-entry-plan.cjs', 'tests/new_a_entry_plan.test.cjs',
})
_FUNDAMENTAL_BATCH_ENTRY_PRODUCT_SHA256 = 'd2cba522ed2166dbef632d0bd3d467ad211338db5610d1d0d56f5249b8d3a5a1'
_HOLD_HEADING_PRODUCT_PATHS = frozenset({'weak-early-beta-gate/scripts/new-a-ui-source/assets/member-loader.js', 'tests/new_a_member_consistency.test.cjs'})
_HOLD_HEADING_PRODUCT_SHA256 = '39b00c7ae2e494eb76dcbb00d10f44435bb213737b517d2a9909666c9c79707a'
_SOURCE_BASELINE_BASELINE = "c88e8b0a67ac53579fbac54de8c7778f92467cd8"
_SOURCE_BASELINE_PRODUCT_PATHS = frozenset({'weak_early_beta/restrictions.py', 'weak_early_beta/new_a/source_baseline.py', 'weak_early_beta/new_a/AGENTS.md', 'weak-early-beta-gate/scripts/new-a-ui-source/guide-body.html', 'weak-early-beta-gate/scripts/new-a-ui-source/assets/owner-loader.js', 'tests/cloud_bundle_sync.test.cjs', 'tests/new_a_owner_connection.test.cjs', 'weak_early_beta/new_a/bundle.py', 'weak-early-beta-gate/scripts/new-a-ui-source/engine/finite-engine.cjs', 'weak_early_beta/new_a/run.py', 'weak-early-beta-gate/scripts/new-a-ui-source/engine/dataset-runtime.cjs', 'weak-early-beta-gate/scripts/new-a-ui-source/reference-history.cjs', 'weak-early-beta-gate/scripts/new-a-ui-source/assets/member-presentation.js', 'weak_early_beta/new_a/cli.py', 'tests/test_new_a_source_baseline.py', 'tests/new_a_analytics_presets.test.cjs', 'weak_early_beta/new_a/source.py', 'weak-early-beta-gate/scripts/new-a-ui-source/frame.html', '.github/workflows/weak-early-beta-reliability.yml', 'weak_early_beta/new_a/restriction_exits.py', 'weak_early_beta/new_a/packet.py', 'weak-early-beta-gate/scripts/new-a-ui-source/assets/member-loader.js'})
_SOURCE_BASELINE_ADDITIONS = frozenset({"tests/test_new_a_source_baseline.py","weak_early_beta/new_a/source_baseline.py","weak_early_beta/new_a/restriction_exits.py"})
_SOURCE_BASELINE_PRODUCT_SHA256 = '67fac1a01609bd435c335d8abe75ea6945da51369d4cdaca3f36d50ad43d76eb'
_SETTLED_HISTORY_BASELINE = "64133edb54590309e20a964dc58dbb48d35a6ac3"
_SETTLED_HISTORY_PRODUCT_PATHS = frozenset({'weak-early-beta-gate/scripts/new-a-ui-source/assets/member-loader.js', 'tests/new_a_member_consistency.test.cjs', 'tests/new_a_role_presentation_candidate.test.cjs', 'weak-early-beta-gate/AGENTS.md', 'weak-early-beta-gate/scripts/new-a-ui-source/assets/member-presentation.js'})
_SETTLED_HISTORY_PRODUCT_SHA256 = "b7e740cd566ec540b083d6d8d8203e9781db797a8293c5d586889ea2f9bd01a2"
_CARD_EDITORIAL_BASELINE = "c1cf2ec7f9067d765a0377bcde7eead02499456a"
_CARD_EDITORIAL_PRODUCT_PATHS = frozenset({
    'scripts/windows/cloud-premium-references/AGENTS.md',
    'scripts/windows/cloud-premium-references/AUTOMATION_PROMPT.md',
    'scripts/windows/cloud-premium-references/COPY_MANIFEST.json',
    'scripts/windows/cloud-premium-references/PREMIUM_CLOUD_WORKER.mjs',
    'scripts/windows/cloud-premium-references/PREMIUM_PM_SAVED_PROMPT.txt',
    'scripts/windows/cloud-premium-references/SOURCE_COMPANION_REVIEW.md',
    'scripts/windows/cloud-premium-references/verified-untimed-disclosures.json',
    'scripts/windows/new-a-fundamental-stage.mjs',
    'scripts/windows/test-new-a-fundamental-stage.mjs',
    'tests/new_a_role_presentation_candidate.test.cjs',
    'tests/test_new_a_fundamental_corrections.py',
    'weak-early-beta-gate/AGENTS.md',
    'weak-early-beta-gate/scripts/new-a-ui-source/assets/member-loader.js',
    'weak-early-beta-gate/scripts/new-a-ui-source/assets/member-presentation.js',
    'weak_early_beta/new_a/AGENTS.md',
    'weak_early_beta/new_a/cli.py',
    'weak_early_beta/new_a/fundamental_corrections.py',
    'weak_early_beta/new_a/fundamentals.py',
})
_CARD_EDITORIAL_ADDITIONS = frozenset({
    'scripts/windows/cloud-premium-references/COPY_MANIFEST.json',
    'scripts/windows/cloud-premium-references/verified-untimed-disclosures.json',
    'tests/test_new_a_fundamental_corrections.py',
    'weak_early_beta/new_a/fundamental_corrections.py',
})
_CARD_EDITORIAL_PRODUCT_SHA256 = "a1a6b7db1faa1ecf32fe0dac541aecd932e9cea1fd39b96b4d3a29780423523a"
_ROLE_ONLY_SUCCESSOR_SCHEMAS = frozenset({
    CLOUD_UI_REVIEW_SCHEMA, CLOUD_UI_POLISH_REVIEW_SCHEMA, CLOUD_OWNER_REFERENCE_REVIEW_SCHEMA,
    FUNDAMENTAL_INLINE_LINKS_REVIEW_SCHEMA, UNIFIED_MEMBER_UI_REVIEW_SCHEMA, LOADING_AND_ZERO_REVIEW_SCHEMA,
    SHARED_DEFAULTS_REVIEW_SCHEMA, ENTRY_NOTICE_REVIEW_SCHEMA, FIXED_TRIAL_FEE_REVIEW_SCHEMA,
    ROLE_ONLY_REVIEW_SCHEMA, JOURNAL_REVIEW_SCHEMA, FUNDAMENTAL_POPUP_REVIEW_SCHEMA, FUNDAMENTAL_IMPACT_REVIEW_SCHEMA,
})
MEMBER_BINDING = {
    "binding": "CLOUD_MEMBER_DB",
    "database_name": "tentei-cloud-member-view",
    "database_id": "72edf9bf-b033-463b-a053-ff259db17cb5",
    "remote": False,
    "migrations_dir": "member-migrations",
}


def git(repo, *args):
    return approval_git(repo, *args)


def unique_replace(data, old, new):
    if data.count(old) != 1:
        raise ValueError("Accepted owner entrypoint contract differs")
    return data.replace(old, new)


def _successor_paths(repo, baseline, candidate, *, allowed_additions=()):
    raw = git(repo, "diff", "--raw", "--no-abbrev", "--no-renames", "-z", baseline, candidate, "--")
    records = raw.split(b"\0")[:-1]
    paths = set()
    for metadata, path in zip(records[::2], records[1::2], strict=True):
        name = path.decode("utf-8")
        fields = metadata.split()
        if len(fields) != 5:
            raise ValueError("Member successor changes an existing file mode or inventory")
        regular_edit = fields[:2] == [b":100644", b"100644"] and fields[-1] == b"M"
        approved_addition = (name in allowed_additions and fields[:2] == [b":000000", b"100644"]
                             and fields[2] == b"0" * 40 and fields[-1] == b"A")
        if not regular_edit and not approved_addition:
            raise ValueError("Member successor changes an existing file mode or inventory")
        paths.add(name)
    return paths


def _check_presentation_successor(repo, baseline, candidate, paths):
    if not paths <= _PRESENTATION_SUCCESSOR_PATHS:
        raise ValueError("Presentation successor changes paths outside the purchase-label scope")

    former = git(repo, "show", f"{baseline}:{PRESENTATION}")
    proposed = git(repo, "show", f"{candidate}:{PRESENTATION}")
    if former.count(_PURCHASE_LABEL) != 1 or proposed != former.replace(_PURCHASE_LABEL, _NEW_PURCHASE_LABEL):
        raise ValueError("Presentation successor changes more than the approved purchase label")


def _check_completed_timing_successor(repo, baseline, candidate, paths):
    if not _COMPLETED_TIMING_DELTAS.keys() <= paths or not paths <= _TIMING_SUCCESSOR_PATHS:
        raise ValueError("Completed-history successor differs from the approved source scope")
    if git(repo, "show", f"{baseline}:{PRESENTATION}").count(_NEW_PURCHASE_LABEL) != 1:
        raise ValueError("Completed-history successor requires the approved member purchase label")
    if PRESENTATION in paths and git(repo, "show", f"{candidate}:{PRESENTATION}").count(_NEW_PURCHASE_LABEL) != 1:
        raise ValueError("Member dashboard changes the approved purchase link or label")
    deltas = dict(_COMPLETED_TIMING_DELTAS)
    if _TIMING_GUIDE in paths:
        deltas[_TIMING_GUIDE] = (_TIMING_GUIDE_DELTA,)
    for path, replacements in deltas.items():
        expected = git(repo, "show", f"{baseline}:{path}")
        for former, inclusive in replacements:
            if expected.count(former) != 1:
                raise ValueError("Approved completed-history cutoff contract differs")
            expected = expected.replace(former, inclusive)
        if git(repo, "show", f"{candidate}:{path}") != expected:
            raise ValueError("Completed-history successor changes more than the inclusive cutoff")


def _check_fundamental_successor(repo, candidate, paths):
    if paths != _FUNDAMENTAL_PRODUCT_PATHS | _SUCCESSOR_REVIEW_PATHS:
        raise ValueError("Fundamental successor differs from the exact reviewed source scope")
    if _product_digest(repo, candidate, _FUNDAMENTAL_PRODUCT_PATHS) != _FUNDAMENTAL_PRODUCT_SHA256:
        raise ValueError("Fundamental successor differs from the reviewed product or migration bytes")


def _product_digest(repo, candidate, paths):
    checked = hashlib.sha256()
    for path in sorted(paths):
        checked.update(path.encode() + b"\0")
        checked.update(hashlib.sha256(git(repo, "show", f"{candidate}:{path}")).digest())
    return checked.hexdigest()


def _check_role_only_successor(repo, candidate, paths):
    required = _ROLE_ONLY_PRODUCT_PATHS | {CONFIG}
    if not required <= paths or not paths <= required | _ROLE_ONLY_TEST_PATHS | _SUCCESSOR_REVIEW_PATHS:
        raise ValueError("Role-only successor differs from the exact reviewed source scope")
    if _product_digest(repo, candidate, _ROLE_ONLY_PRODUCT_PATHS) != _ROLE_ONLY_PRODUCT_SHA256:
        raise ValueError("Role-only successor differs from the reviewed access or observation bytes")


def _member_successor(repo, baseline, candidate):
    if baseline == _HELP_TERMS_BASELINE:
        paths = _successor_paths(repo, baseline, candidate)
        if paths != _HELP_TERMS_PRODUCT_PATHS | _SUCCESSOR_REVIEW_PATHS:
            raise ValueError("Cloud help-terms successor differs from the exact reviewed source scope")
        if _product_digest(repo, candidate, _HELP_TERMS_PRODUCT_PATHS) != _HELP_TERMS_PRODUCT_SHA256:
            raise ValueError("Cloud help-terms successor differs from the reviewed bytes")
        schema = HELP_TERMS_REVIEW_SCHEMA
    elif baseline == _HELP_LABEL_BASELINE:
        paths = _successor_paths(repo, baseline, candidate)
        if paths != _HELP_LABEL_PRODUCT_PATHS | _SUCCESSOR_REVIEW_PATHS:
            raise ValueError("Cloud help-label successor differs from the exact reviewed source scope")
        if _product_digest(repo, candidate, _HELP_LABEL_PRODUCT_PATHS) != _HELP_LABEL_PRODUCT_SHA256:
            raise ValueError("Cloud help-label successor differs from the reviewed bytes")
        schema = HELP_LABEL_REVIEW_SCHEMA
    elif baseline == _PUBLICATION_FIRST_BASELINE:
        paths = _successor_paths(repo, baseline, candidate)
        if paths != _PUBLICATION_FIRST_PRODUCT_PATHS | _SUCCESSOR_REVIEW_PATHS:
            raise ValueError("Cloud publication-first successor differs from the exact reviewed source scope")
        if _product_digest(repo, candidate, _PUBLICATION_FIRST_PRODUCT_PATHS) != _PUBLICATION_FIRST_PRODUCT_SHA256:
            raise ValueError("Cloud publication-first successor differs from the reviewed bytes")
        schema = PUBLICATION_FIRST_REVIEW_SCHEMA
    elif baseline == _FUNDAMENTAL_BATCH_BASELINE:
        paths = _successor_paths(repo, baseline, candidate, allowed_additions=_FUNDAMENTAL_BATCH_ENTRY_ADDITIONS)
        if paths == _FUNDAMENTAL_BATCH_ENTRY_PRODUCT_PATHS | _SUCCESSOR_REVIEW_PATHS:
            product_paths, product_sha = _FUNDAMENTAL_BATCH_ENTRY_PRODUCT_PATHS, _FUNDAMENTAL_BATCH_ENTRY_PRODUCT_SHA256
        elif paths == _FUNDAMENTAL_BATCH_PRODUCT_PATHS | _SUCCESSOR_REVIEW_PATHS:
            product_paths, product_sha = _FUNDAMENTAL_BATCH_PRODUCT_PATHS, _FUNDAMENTAL_BATCH_PRODUCT_SHA256
        else:
            raise ValueError("Cloud fundamental batch successor differs from the exact reviewed source scope")
        if _product_digest(repo, candidate, product_paths) != product_sha:
            raise ValueError("Cloud fundamental batch successor differs from the reviewed bytes")
        schema = FUNDAMENTAL_BATCH_REVIEW_SCHEMA
    elif baseline == _MEMBER_READY_BASELINE:
        paths = _successor_paths(repo, baseline, candidate)
        if paths != _MEMBER_READY_PRODUCT_PATHS | _SUCCESSOR_REVIEW_PATHS:
            raise ValueError("Cloud published generation successor differs from the exact reviewed source scope")
        if _product_digest(repo, candidate, _MEMBER_READY_PRODUCT_PATHS) != _MEMBER_READY_PRODUCT_SHA256:
            raise ValueError("Cloud published generation successor differs from the reviewed bytes")
        schema = MEMBER_READY_REVIEW_SCHEMA
    elif baseline == _HOLD_HEADING_BASELINE:
        paths = _successor_paths(repo, baseline, candidate)
        if paths != _HOLD_HEADING_PRODUCT_PATHS | _SUCCESSOR_REVIEW_PATHS:
            raise ValueError("Cloud hold heading successor differs from the exact reviewed source scope")
        if _product_digest(repo, candidate, _HOLD_HEADING_PRODUCT_PATHS) != _HOLD_HEADING_PRODUCT_SHA256:
            raise ValueError("Cloud hold heading successor differs from the reviewed bytes")
        schema = HOLD_HEADING_REVIEW_SCHEMA
    elif baseline == _SOURCE_BASELINE_BASELINE:
        paths = _successor_paths(repo, baseline, candidate, allowed_additions=_SOURCE_BASELINE_ADDITIONS)
        if paths != _SOURCE_BASELINE_PRODUCT_PATHS | _SUCCESSOR_REVIEW_PATHS:
            raise ValueError("Cloud source baseline successor differs from the exact reviewed source scope")
        if _product_digest(repo, candidate, _SOURCE_BASELINE_PRODUCT_PATHS) != _SOURCE_BASELINE_PRODUCT_SHA256:
            raise ValueError("Cloud source baseline successor differs from the reviewed bytes")
        schema = SOURCE_BASELINE_REVIEW_SCHEMA
    elif baseline == _SETTLED_HISTORY_BASELINE:
        paths = _successor_paths(repo, baseline, candidate)
        if paths != _SETTLED_HISTORY_PRODUCT_PATHS | _SUCCESSOR_REVIEW_PATHS:
            raise ValueError("Cloud settled history successor differs from the exact reviewed source scope")
        if _product_digest(repo, candidate, _SETTLED_HISTORY_PRODUCT_PATHS) != _SETTLED_HISTORY_PRODUCT_SHA256:
            raise ValueError("Cloud settled history successor differs from the reviewed bytes")
        schema = SETTLED_HISTORY_REVIEW_SCHEMA
    elif baseline == _CARD_EDITORIAL_BASELINE:
        paths = _successor_paths(repo, baseline, candidate, allowed_additions=_CARD_EDITORIAL_ADDITIONS)
        if paths != _CARD_EDITORIAL_PRODUCT_PATHS | _SUCCESSOR_REVIEW_PATHS:
            raise ValueError("Cloud card editorial successor differs from the exact reviewed source scope")
        if _product_digest(repo, candidate, _CARD_EDITORIAL_PRODUCT_PATHS) != _CARD_EDITORIAL_PRODUCT_SHA256:
            raise ValueError("Cloud card editorial successor differs from the reviewed bytes")
        schema = CARD_EDITORIAL_REVIEW_SCHEMA
    elif baseline == _PUBLICATION_RECOVERY_BASELINE:
        paths = _successor_paths(repo, baseline, candidate)
        if paths != _PUBLICATION_RECOVERY_PRODUCT_PATHS | _SUCCESSOR_REVIEW_PATHS:
            raise ValueError("Cloud member publication recovery successor differs from the exact reviewed source scope")
        if _product_digest(repo, candidate, _PUBLICATION_RECOVERY_PRODUCT_PATHS) != _PUBLICATION_RECOVERY_PRODUCT_SHA256:
            raise ValueError("Cloud member publication recovery successor differs from the reviewed bytes")
        schema = PUBLICATION_RECOVERY_REVIEW_SCHEMA
    elif baseline == _CARD_DISPLAY_BASELINE:
        paths = _successor_paths(repo, baseline, candidate)
        if paths != _CARD_DISPLAY_PRODUCT_PATHS | _SUCCESSOR_REVIEW_PATHS:
            raise ValueError("Cloud card display successor differs from the exact reviewed source scope")
        if _product_digest(repo, candidate, _CARD_DISPLAY_PRODUCT_PATHS) != _CARD_DISPLAY_PRODUCT_SHA256:
            raise ValueError("Cloud card display successor differs from the reviewed bytes")
        schema = CARD_DISPLAY_REVIEW_SCHEMA
    elif baseline == _PREMIUM_RUNTIME_BASELINE:
        paths = _successor_paths(repo, baseline, candidate, allowed_additions=_PREMIUM_RUNTIME_ADDITIONS)
        if paths != _PREMIUM_RUNTIME_PRODUCT_PATHS | _SUCCESSOR_REVIEW_PATHS:
            raise ValueError("Cloud Premium runtime successor differs from the exact reviewed source scope")
        if _product_digest(repo, candidate, _PREMIUM_RUNTIME_PRODUCT_PATHS) != _PREMIUM_RUNTIME_PRODUCT_SHA256:
            raise ValueError("Cloud Premium runtime successor differs from the reviewed bytes")
        schema = PREMIUM_RUNTIME_REVIEW_SCHEMA
    elif baseline == _FUNDAMENTAL_RETENTION_BASELINE:
        paths = _successor_paths(repo, baseline, candidate)
        if paths != _FUNDAMENTAL_RETENTION_PRODUCT_PATHS | _SUCCESSOR_REVIEW_PATHS:
            raise ValueError("Cloud fundamental retention successor differs from the exact reviewed source scope")
        if _product_digest(repo, candidate, _FUNDAMENTAL_RETENTION_PRODUCT_PATHS) != _FUNDAMENTAL_RETENTION_PRODUCT_SHA256:
            raise ValueError("Cloud fundamental retention successor differs from the reviewed bytes")
        schema = FUNDAMENTAL_RETENTION_REVIEW_SCHEMA
    elif baseline == _PREMIUM_LEGACY_BASELINE:
        paths = _successor_paths(repo, baseline, candidate, allowed_additions=_PREMIUM_LEGACY_ADDITIONS)
        if paths != _PREMIUM_LEGACY_PRODUCT_PATHS | _SUCCESSOR_REVIEW_PATHS:
            raise ValueError("Cloud Premium legacy successor differs from the exact reviewed source scope")
        if _product_digest(repo, candidate, _PREMIUM_LEGACY_PRODUCT_PATHS) != _PREMIUM_LEGACY_PRODUCT_SHA256:
            raise ValueError("Cloud Premium legacy successor differs from the reviewed bytes")
        schema = PREMIUM_LEGACY_REVIEW_SCHEMA
    elif baseline == _APPROVAL_TIMEOUT_BASELINE:
        paths = _successor_paths(repo, baseline, candidate, allowed_additions=_APPROVAL_TIMEOUT_ADDITIONS)
        if paths != _APPROVAL_TIMEOUT_PRODUCT_PATHS | _SUCCESSOR_REVIEW_PATHS:
            raise ValueError("Cloud approval-timeout successor differs from the exact reviewed source scope")
        if _product_digest(repo, candidate, _APPROVAL_TIMEOUT_PRODUCT_PATHS) != _APPROVAL_TIMEOUT_PRODUCT_SHA256:
            raise ValueError("Cloud approval-timeout successor differs from the reviewed bytes")
        schema = APPROVAL_TIMEOUT_REVIEW_SCHEMA
    elif baseline == _SETTLED_PRICE_BASELINE:
        paths = _successor_paths(repo, baseline, candidate, allowed_additions=_SETTLED_PRICE_ADDITIONS)
        if paths != _SETTLED_PRICE_PRODUCT_PATHS | _SUCCESSOR_REVIEW_PATHS:
            raise ValueError("Cloud settled-price successor differs from the exact reviewed source scope")
        if _product_digest(repo, candidate, _SETTLED_PRICE_PRODUCT_PATHS) != _SETTLED_PRICE_PRODUCT_SHA256:
            raise ValueError("Cloud settled-price successor differs from the reviewed bytes")
        schema = SETTLED_PRICE_REVIEW_SCHEMA
    elif baseline == _FREE_COMPLETED_ANALYTICS_BASELINE:
        paths = _successor_paths(repo, baseline, candidate, allowed_additions=(_FREE_COMPLETED_ANALYTICS_CALENDAR,))
        if paths != _FREE_COMPLETED_ANALYTICS_PRODUCT_PATHS | _SUCCESSOR_REVIEW_PATHS | {CONFIG}:
            raise ValueError("Free completed history and analytics differ from the reviewed source scope")
        if _product_digest(repo, candidate, _FREE_COMPLETED_ANALYTICS_PRODUCT_PATHS) != _FREE_COMPLETED_ANALYTICS_PRODUCT_SHA256:
            raise ValueError("Free completed history and analytics differ from the reviewed bytes")
        schema = FREE_COMPLETED_ANALYTICS_REVIEW_SCHEMA
    elif baseline == _ENTRY_NOTICE_BASELINE:
        paths = _successor_paths(repo, baseline, candidate)
        if paths == _ENTRY_NOTICE_PRODUCT_PATHS | _CLOUD_OWNER_REFERENCE_REVIEW_PATHS:
            if _product_digest(repo, candidate, _ENTRY_NOTICE_PRODUCT_PATHS) != _ENTRY_NOTICE_PRODUCT_SHA256:
                raise ValueError("Cloud entry notice successor differs from the reviewed bytes")
            schema = ENTRY_NOTICE_REVIEW_SCHEMA
        elif paths == _FIXED_TRIAL_FEE_PRODUCT_PATHS | _CLOUD_OWNER_REFERENCE_REVIEW_PATHS:
            if _product_digest(repo, candidate, _FIXED_TRIAL_FEE_PRODUCT_PATHS) != _FIXED_TRIAL_FEE_PRODUCT_SHA256:
                raise ValueError("Fixed Cloud trial fee successor differs from the reviewed bytes")
            schema = FIXED_TRIAL_FEE_REVIEW_SCHEMA
        elif paths == _FIXED_TRIAL_FEE_AUDIT_REPAIR_PATHS | _CLOUD_OWNER_REFERENCE_REVIEW_PATHS:
            if _product_digest(repo, candidate, _FIXED_TRIAL_FEE_AUDIT_REPAIR_PATHS) != _FIXED_TRIAL_FEE_AUDIT_REPAIR_SHA256:
                raise ValueError("Fixed Cloud trial fee acceptance audit repair differs from the reviewed bytes")
            schema = FIXED_TRIAL_FEE_REVIEW_SCHEMA
        else:
            raise ValueError("Cloud entry notice or fixed trial fee successor differs from the reviewed scope")
    elif baseline == _SHARED_DEFAULTS_BASELINE:
        paths = _successor_paths(repo, baseline, candidate)
        if paths != _SHARED_DEFAULTS_PRODUCT_PATHS | _CLOUD_OWNER_REFERENCE_REVIEW_PATHS:
            raise ValueError("Shared Cloud defaults successor differs from the reviewed scope")
        if _product_digest(repo, candidate, _SHARED_DEFAULTS_PRODUCT_PATHS) != _SHARED_DEFAULTS_PRODUCT_SHA256:
            raise ValueError("Shared Cloud defaults successor differs from the reviewed bytes")
        schema = SHARED_DEFAULTS_REVIEW_SCHEMA
    elif baseline == _LOADING_AND_ZERO_BASELINE:
        paths = _successor_paths(repo, baseline, candidate)
        if paths != _LOADING_AND_ZERO_PRODUCT_PATHS | _CLOUD_OWNER_REFERENCE_REVIEW_PATHS:
            raise ValueError("Cloud loading and zero-line successor differs from the reviewed scope")
        if _product_digest(repo, candidate, _LOADING_AND_ZERO_PRODUCT_PATHS) != _LOADING_AND_ZERO_PRODUCT_SHA256:
            raise ValueError("Cloud loading and zero-line successor differs from the reviewed bytes")
        schema = LOADING_AND_ZERO_REVIEW_SCHEMA
    elif baseline == _UNIFIED_MEMBER_UI_BASELINE:
        paths = _successor_paths(repo, baseline, candidate)
        if paths != _UNIFIED_MEMBER_UI_PRODUCT_PATHS | _CLOUD_OWNER_REFERENCE_REVIEW_PATHS:
            raise ValueError("Unified member UI successor differs from the reviewed scope")
        if _product_digest(repo, candidate, _UNIFIED_MEMBER_UI_PRODUCT_PATHS) != _UNIFIED_MEMBER_UI_PRODUCT_SHA256:
            raise ValueError("Unified member UI successor differs from the reviewed bytes")
        schema = UNIFIED_MEMBER_UI_REVIEW_SCHEMA
    elif baseline == _FUNDAMENTAL_INLINE_LINKS_BASELINE:
        paths = _successor_paths(repo, baseline, candidate, allowed_additions=_FUNDAMENTAL_INLINE_LINKS_ADDITIONS)
        if paths != _FUNDAMENTAL_INLINE_LINKS_PRODUCT_PATHS | _CLOUD_OWNER_REFERENCE_REVIEW_PATHS:
            raise ValueError("Fundamental link successor differs from the reviewed product and test scope")
        if _product_digest(repo, candidate, _FUNDAMENTAL_INLINE_LINKS_PRODUCT_PATHS) != _FUNDAMENTAL_INLINE_LINKS_PRODUCT_SHA256:
            raise ValueError("Fundamental link successor differs from the reviewed product and test bytes")
        schema = FUNDAMENTAL_INLINE_LINKS_REVIEW_SCHEMA
    elif baseline == _CLOUD_OWNER_REFERENCE_BASELINE:
        paths = _successor_paths(repo, baseline, candidate, allowed_additions=_CLOUD_OWNER_REFERENCE_ADDITIONS)
        if paths != _CLOUD_OWNER_REFERENCE_PRODUCT_PATHS | _CLOUD_OWNER_REFERENCE_REVIEW_PATHS:
            raise ValueError("Cloud owner reference successor differs from the reviewed product or test scope")
        if _product_digest(repo, candidate, _CLOUD_OWNER_REFERENCE_PRODUCT_PATHS) != _CLOUD_OWNER_REFERENCE_PRODUCT_SHA256:
            raise ValueError("Cloud owner reference successor differs from the reviewed product or test bytes")
        schema = CLOUD_OWNER_REFERENCE_REVIEW_SCHEMA
    elif baseline == _CLOUD_UI_POLISH_BASELINE:
        paths = _successor_paths(repo, baseline, candidate)
        if paths != _CLOUD_UI_POLISH_PRODUCT_PATHS | _SUCCESSOR_REVIEW_PATHS:
            raise ValueError("Cloud UI polish successor differs from the reviewed product or test scope")
        if _product_digest(repo, candidate, _CLOUD_UI_POLISH_PRODUCT_PATHS) != _CLOUD_UI_POLISH_PRODUCT_SHA256:
            raise ValueError("Cloud UI polish successor differs from the reviewed product or test bytes")
        schema = CLOUD_UI_POLISH_REVIEW_SCHEMA
    elif baseline == _CLOUD_UI_BASELINE:
        paths = _successor_paths(repo, baseline, candidate, allowed_additions=_CLOUD_UI_ADDITIONS)
        if paths != _CLOUD_UI_PRODUCT_PATHS | _SUCCESSOR_REVIEW_PATHS:
            raise ValueError("Cloud UI successor differs from the reviewed frontend or test scope")
        if _product_digest(repo, candidate, _CLOUD_UI_PRODUCT_PATHS) != _CLOUD_UI_PRODUCT_SHA256:
            raise ValueError("Cloud UI successor differs from the reviewed frontend or test bytes")
        schema = CLOUD_UI_REVIEW_SCHEMA
    elif baseline == _FUNDAMENTAL_IMPACT_BASELINE:
        paths = _successor_paths(repo, baseline, candidate)
        if paths != _FUNDAMENTAL_IMPACT_REVIEWED_PATHS | _SUCCESSOR_REVIEW_PATHS:
            raise ValueError("Fundamental impact successor differs from the reviewed frontend or test scope")
        if _product_digest(repo, candidate, _FUNDAMENTAL_IMPACT_REVIEWED_PATHS) != _FUNDAMENTAL_IMPACT_REVIEWED_SHA256:
            raise ValueError("Fundamental impact successor differs from the reviewed frontend or test bytes")
        schema = FUNDAMENTAL_IMPACT_REVIEW_SCHEMA
    elif baseline == _FUNDAMENTAL_POPUP_BASELINE:
        paths = _successor_paths(repo, baseline, candidate)
        if paths != _FUNDAMENTAL_POPUP_REVIEWED_PATHS | _SUCCESSOR_REVIEW_PATHS:
            raise ValueError("Fundamental popup successor differs from the reviewed frontend or test scope")
        if _product_digest(repo, candidate, _FUNDAMENTAL_POPUP_REVIEWED_PATHS) != _FUNDAMENTAL_POPUP_REVIEWED_SHA256:
            raise ValueError("Fundamental popup successor differs from the reviewed frontend or test bytes")
        schema = FUNDAMENTAL_POPUP_REVIEW_SCHEMA
    elif baseline == _JOURNAL_BASELINE:
        paths = _successor_paths(repo, baseline, candidate)
        parents = git(repo, "show", "-s", "--format=%P", candidate).decode().split()
        if parents != [_JOURNAL_REVIEWED_RUNNER] or paths != _JOURNAL_PRODUCT_PATHS | _SUCCESSOR_REVIEW_PATHS:
            raise ValueError("Journal successor differs from the exact reviewed runner or release scope")
        if _product_digest(repo, candidate, _JOURNAL_PRODUCT_PATHS) != _JOURNAL_PRODUCT_SHA256:
            raise ValueError("Journal successor differs from the reviewed runner bytes")
        schema = JOURNAL_REVIEW_SCHEMA
    elif baseline == _ROLE_ONLY_BASELINE:
        paths = _successor_paths(repo, baseline, candidate, allowed_additions=(_ROLE_ONLY_MIGRATION,))
        _check_role_only_successor(repo, candidate, paths)
        schema = ROLE_ONLY_REVIEW_SCHEMA
    elif baseline == _FUNDAMENTAL_BASELINE:
        paths = _successor_paths(repo, baseline, candidate, allowed_additions=(_FUNDAMENTAL_MIGRATION,))
        _check_fundamental_successor(repo, candidate, paths)
        schema = FUNDAMENTAL_REVIEW_SCHEMA
    else:
        paths = _successor_paths(repo, baseline, candidate)
        if PRESENTATION in paths and not _COMPLETED_TIMING_DELTAS.keys() & paths:
            _check_presentation_successor(repo, baseline, candidate, paths)
            schema = PRESENTATION_REVIEW_SCHEMA
        else:
            _check_completed_timing_successor(repo, baseline, candidate, paths)
            schema = COMPLETED_TIMING_REVIEW_SCHEMA
    # Keep the full-index diff format of the already-issued presentation approval.
    delta = git(repo, "diff", "--binary", "--full-index", "--no-renames", "--no-ext-diff", "--no-textconv",
                "--no-color", "--src-prefix=a/", "--dst-prefix=b/", "--unified=3", "--diff-algorithm=myers",
                "--no-indent-heuristic", baseline, candidate, "--")
    return {
        "schema": schema,
        "accepted_owner_source": baseline,
        "candidate_source": candidate,
        "reviewed_diff_sha256": hashlib.sha256(delta).hexdigest(),
        "member_database_id": MEMBER_BINDING["database_id"],
        "member_support_configured": True,
        "owner_only_gate_preserved": True,
        **({"member_audience": "role_only"} if schema in _ROLE_ONLY_SUCCESSOR_SCHEMAS else {}),
        **({"member_audience": "tiered"} if schema in TIERED_SUCCESSOR_SCHEMAS else {}),
        **({"reviewed_runner_commit": _JOURNAL_REVIEWED_RUNNER} if schema == JOURNAL_REVIEW_SCHEMA else {}),
    }


def review_member_release_source(repo, baseline, candidate):
    """Review initial member support or one exact successor."""
    repo = Path(repo).resolve()
    if not all(re.fullmatch(r"[a-f0-9]{40}", value) for value in (baseline, candidate)) or baseline == candidate:
        raise ValueError("Distinct full commits required for member source review")
    if git(repo, "merge-base", baseline, candidate).decode().strip() != baseline:
        raise ValueError("Member source is not a descendant of the accepted owner source")

    before = {name: git(repo, "show", f"{baseline}:{name}") for name in sorted(acceptance.AUTH_FILES)}
    after = {name: git(repo, "show", f"{candidate}:{name}") for name in sorted(acceptance.AUTH_FILES)}
    changed = [name for name in before if before[name] != after[name]]
    baseline_config_bytes = git(repo, "show", f"{baseline}:{CONFIG}")
    candidate_config_bytes = git(repo, "show", f"{candidate}:{CONFIG}")
    common_config = json.loads(baseline_config_bytes)
    prior_members = [db for db in common_config["d1_databases"] if db.get("binding") == "CLOUD_MEMBER_DB"]
    if prior_members or "CLOUD_MEMBER_VIEW_ENABLED" in common_config["vars"]:
        exact_shared_owner_entry = (baseline == _CLOUD_UI_POLISH_BASELINE and changed == [ENTRY]
                                    and hashlib.sha256(after[ENTRY]).hexdigest() == _CLOUD_UI_POLISH_ENTRY_SHA256)
        exact_owner_reference_auth = (
            baseline == _CLOUD_OWNER_REFERENCE_BASELINE
            and {name: hashlib.sha256(after[name]).hexdigest() for name in changed} == _CLOUD_OWNER_REFERENCE_AUTH_SHA256
        )
        exact_unified_member_ui_entry = (baseline == _UNIFIED_MEMBER_UI_BASELINE and changed == [ENTRY]
                                         and hashlib.sha256(after[ENTRY]).hexdigest() == _UNIFIED_MEMBER_UI_ENTRY_SHA256)
        if changed and not (exact_shared_owner_entry or exact_owner_reference_auth or exact_unified_member_ui_entry):
            raise ValueError("Member successor changes existing Discord or owner authorization source")
        expected_config = baseline_config_bytes
        if baseline == _ROLE_ONLY_BASELINE:
            expected_config = unique_replace(expected_config, _ROLE_ONLY_CONFIG_LINE,
                                             _ROLE_ONLY_CONFIG_LINE + _ROLE_ONLY_AUDIENCE_LINE)
        elif baseline == _FREE_COMPLETED_ANALYTICS_BASELINE:
            expected_config = unique_replace(expected_config, _ROLE_ONLY_AUDIENCE_LINE, _TIERED_AUDIENCE_LINE)
        if (expected_config != candidate_config_bytes or common_config.get("name") != acceptance.SERVICE
                or common_config["vars"].get("CLOUD_MEMBER_VIEW_ENABLED") != "true" or prior_members != [MEMBER_BINDING]):
            raise ValueError("Member successor changes the approved Worker configuration or member D1")
        if (baseline in {_JOURNAL_BASELINE, _FUNDAMENTAL_POPUP_BASELINE, _FUNDAMENTAL_IMPACT_BASELINE,
                         _CLOUD_UI_BASELINE, _CLOUD_UI_POLISH_BASELINE, _CLOUD_OWNER_REFERENCE_BASELINE,
                         _FUNDAMENTAL_INLINE_LINKS_BASELINE, _UNIFIED_MEMBER_UI_BASELINE, _LOADING_AND_ZERO_BASELINE,
                         _SHARED_DEFAULTS_BASELINE, _ENTRY_NOTICE_BASELINE}
                and common_config["vars"].get("CLOUD_MEMBER_AUDIENCE") != "role_only"):
            raise ValueError("Version-bound member successor requires the existing role-only audience")
        if (baseline in {_SETTLED_PRICE_BASELINE, _APPROVAL_TIMEOUT_BASELINE, _PREMIUM_LEGACY_BASELINE,
                         _FUNDAMENTAL_RETENTION_BASELINE, _PREMIUM_RUNTIME_BASELINE, _CARD_DISPLAY_BASELINE,
                         _PUBLICATION_RECOVERY_BASELINE, _CARD_EDITORIAL_BASELINE, _SETTLED_HISTORY_BASELINE, _SOURCE_BASELINE_BASELINE, _HOLD_HEADING_BASELINE, _MEMBER_READY_BASELINE, _FUNDAMENTAL_BATCH_BASELINE, _PUBLICATION_FIRST_BASELINE, _HELP_LABEL_BASELINE, _HELP_TERMS_BASELINE}
                and common_config["vars"].get("CLOUD_MEMBER_AUDIENCE") != "tiered"):
            raise ValueError("Cloud successor requires the existing tiered audience")
        return _member_successor(repo, baseline, candidate)

    if changed != [ENTRY]:
        raise ValueError("Existing Discord or owner authorization code changed beyond the member fallback")
    expected = unique_replace(before[ENTRY], b"import { passiveObservationSink", (
        b"import {memberRouteCandidate} from './new-a-role-integration';\n"
        b"import { passiveObservationSink"
    ))
    expected = unique_replace(expected, b"    if (denied) return denied;", (
        b"    if (denied) return (await memberRouteCandidate(request, env, denied, operationalBuild)) ?? denied;"
    ))
    with_observer = unique_replace(expected, b"env, denied, operationalBuild))", b"env, denied, operationalBuild, ctx))")
    purchase_anchor = (
        b"    const denied = await ownerOnlyGate(request, env);\n"
        b"    if (denied) return (await memberRouteCandidate(request, env, denied, operationalBuild, ctx)) ?? denied;\n"
        b"    const pathname = new URL(request.url).pathname;"
    )
    variants = [expected, with_observer]
    if with_observer.count(purchase_anchor) == 1:
        variants.append(unique_replace(with_observer, purchase_anchor, (
            b"    const pathname = new URL(request.url).pathname;\n"
            b"    if (env.CLOUD_MEMBER_VIEW_ENABLED === 'true' && pathname === '/purchase' && ['GET', 'HEAD'].includes(request.method)) return sharedGate.fetch(request, env);\n"
            b"    const denied = await ownerOnlyGate(request, env);\n"
            b"    if (denied) return (await memberRouteCandidate(request, env, denied, operationalBuild, ctx)) ?? denied;"
        )))
    if after[ENTRY] not in variants:
        raise ValueError("Member fallback changes more than the existing owner-denial branch")

    candidate_config = json.loads(candidate_config_bytes)
    mode = candidate_config["vars"].pop("CLOUD_MEMBER_VIEW_ENABLED", None)
    databases = candidate_config["d1_databases"]
    member = [database for database in databases if database.get("binding") == "CLOUD_MEMBER_DB"]
    if mode not in ("true", "false") or member != [MEMBER_BINDING]:
        raise ValueError("Member mode or dedicated production D1 binding differs")
    candidate_config["d1_databases"] = [database for database in databases if database not in member]
    if candidate_config != common_config:
        raise ValueError("Candidate changes an existing production or preview binding or setting")

    paths = [*sorted(acceptance.AUTH_FILES), CONFIG, "weak-early-beta-gate/src/new-a-member-release.ts",
             "weak-early-beta-gate/src/new-a-role-facade.ts", "weak-early-beta-gate/src/new-a-role-integration.ts",
             "weak-early-beta-gate/src/new-a-member-services.ts", "weak-early-beta-gate/src/new-a-member-projection.ts",
             "weak-early-beta-gate/scripts/prepare-new-a-member-projection.cjs", "weak_early_beta/new_a/member_publisher.py",
             "weak-early-beta-gate/src/new-a-member-observation.ts",
             "weak-early-beta-gate/member-migrations/0003_new_a_member_response_observations.sql",
             "weak-early-beta-gate/member-migrations/0004_new_a_member_access_tiers.sql"]
    delta = git(repo, "diff", "--binary", baseline, candidate, "--", *paths)
    return {
        "schema": INITIAL_REVIEW_SCHEMA,
        "accepted_owner_source": baseline,
        "candidate_source": candidate,
        "reviewed_diff_sha256": hashlib.sha256(delta).hexdigest(),
        "member_database_id": member[0]["database_id"],
        "member_support_configured": mode == "true",
        "owner_only_gate_preserved": True,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)
    args = parser.parse_args()
    print(json.dumps(review_member_release_source(Path.cwd(), args.baseline, args.candidate)))
