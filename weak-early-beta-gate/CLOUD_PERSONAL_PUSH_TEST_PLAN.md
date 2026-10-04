# Personal-device push test plan — not executed

The user requests a real arrival test on their own device only. No other member
may receive a test. No push has been sent; no key, credential, database or extra
authentication permission has been created/configured by this task.

## Checked state and missing integration

- UI reads browser permission and member status, defaults OFF, and truthfully
  displays “通知は現在利用できません”. It does not request permission.
- Preference API, D1 migrations, fresh Whop eligibility, candidate filtering and
  dedupe/delivery-ledger dry-run contracts are implemented and locally tested.
- The checked-in Cloud configuration has no production D1 binding or Whop policy.
  Existing live bindings/credentials and exact member links remain unverified;
  there is no identity-link registration flow.
- Subscription registration/revocation, gesture-only UI, push-only service worker,
  RFC sender and internal personal dispatch helper exist and are tested locally.
  Registration/delivery flags remain off, no cron/public test-send entry exists.
  See CLOUD_DISCORD_PUSH_READINESS.md for live/schema/setup blockers.
- Existing Discord notifications are unchanged and cannot substitute for a
  browser-push arrival test. Provider acceptance alone is not arrival proof.

## Questions for the parent to resolve with the user

1. Which personal device/OS/browser will receive the test? Is Cloud a browser tab
   or installed web app, and is its notification permission granted/denied/unasked?
2. Which existing Discord account and verified existing Whop integration evidence apply?
   Keep current Discord login; require no new Cloud/Whop account or re-login.
   Never infer the link from Slack/display name/email or a role alone.
3. After sign-in and explicit device opt-in, identify one active subscription
   through the secure server flow. Do not ask for endpoints, credentials or keys
   in Slack. Do not silently select all of the user's devices.
4. Approve the named D1 binding/migrations and use/configuration of a scoped Whop
   credential. Separately approve use of an existing VAPID key or creation and
   installation of a new one if necessary. General publication is insufficient.

## Integration and controlled test sequence

Complete the access-preserving setup/checks in `CLOUD_RELEASE_READINESS.md` first.
Verify the implemented explicit opt-in/revocation and service worker, then
approve the exact sender/key configuration and a reviewed personal trigger. Derive the member from the existing session, require exact-origin
mutations, and restrict the personal-test action to that member and one selected
device. Use a labeled test event, short-lived one-use authorization and persistent
idempotency key. No browser-supplied recipient may override server ownership.
Keep general scheduling and all other members' delivery disabled.

Recheck live paid eligibility immediately before dispatch. Unknown/expired/test/
revoked/provider-error outcomes hold; no cached Discord-role grace authorizes a
send. Save the actual send receipt separately from dry-run eligibility. Confirm
arrival with the user's device/time and displayed message before calling it passed.

Run this matrix with local time-controlled fixtures, then the approved single
device. A synthetic message must say “テスト通知”, never invent a real detection.

| Case | Expected outcome |
|---|---|
| Default OFF / new-detection or reminder individually OFF | No send; suppressed receipt |
| New-detection ON and verified paid self | One labeled arrival on selected device only |
| Detection-day actual close below/equal/above cap | Below/equal qualify; above suppressed; unknown never becomes zero |
| D5/D6, holiday/year boundary | Chosen +5/+6 bank day; unchanged detector/calendar |
| 08:00 JST reminder ON | Today is confirmation day; actual price/P&L not yet known |
| Reminder OFF / different date | No reminder |
| Free/expired/test/revoked/unknown/provider failure | No send; held/denied reason |
| Concurrent/repeated same event | One successful send/arrival; persistent dedupe |
| Opt-out/revoked device before dispatch | Final check suppresses; device remains revoked |
| Browser/provider error/expired endpoint | Honest failure/held receipt; no arrival claim |

First perform one immediate labeled new-detection-style personal test. Test the
morning wording immediately as a clearly labeled test; execute a single real
08:00 JST personal reminder only after the user chooses the date/device and the
required setup is approved. No test is scheduled here. The test record must show
member/device scope, explicit opt-in, cap/endpoint/event switches, fresh eligibility,
event/dispatch times, actual receipt, dedupe outcome and user's arrival confirmation.
