# Observe the real owner response through Workers Logs

This candidate adds an observation at the last step of the existing normal private
response path. The browser continues to use its existing Discord session and the
same fresh-role check. Successful GET requests for the dashboard and normal access
API can emit `NEW_A_PROTECTED_OWNER_RESPONSE_V1` to the configured Worker logs.
The recovery page can return 200 while refreshing authentication. It exits before
this observation and never emits the event.

The event is available only to the existing provider-side log reader. It contains
the two fixed route names, response status, strategy, commit, prepared build-input
hash, and Worker version metadata. It does not include account identifiers,
credential headers, arbitrary response data, or stored state. For the access
API it checks a time- and size-bounded clone of the response and records only the
known safe `{authorized: true, strategy: "A_BASE"}` contract. It adds no HTTP
route, account setting, database schema change, permission, or authentication
mechanism.

## Use from an authorized operator session

1. Before promoting this candidate, establish that an authorized operator can read
   the existing `tentei-kyokuchi-cloud` Workers Logs from the Cloudflare dashboard.
   Do not assume the CLI or an existing API token can query these logs. Use the
   [Cloudflare Workers Logs documentation](https://developers.cloudflare.com/workers/observability/logs/workers-logs/)
   for the supported provider view and supported structured filters.
2. After a separately prepared and approved exact release, the owner may visit
   the usual dashboard from their own existing authenticated browser, then visit
   the normal `/api/cloud/new-a-finite/access` address on the same domain. This is
   ordinary viewing over HTTPS. Do not capture or transfer cookies, developer
   tooling network exports, tokens, or page contents.
3. In the provider's service logs, filter to `operation =
   cloud_owner_response_observed`, the current Worker version, and the observation
   window. An authorized reader needs the provider-generated enclosing event
   metadata and the safe structured fields for both successful routes. Check the
   same service, exact commit, version, and build-input hash against CI and a
   normal live-version readback. Use the log's original observation time and
   provenance. If the provider reader or either matching event is unavailable,
   owner-specific evidence remains unverified.

Provider metadata is independently required. A local stdout event, a copied JSON
object, a screenshot, and public `/healthz` are insufficient. The observation
does not establish a private pretraffic probe, traffic percentages, a final
deployed artifact hash, anonymous denials, or authenticated nonowner behavior.
The host acceptance adapter still needs trusted provider log provenance,
anonymous/direct-route observations, and any separate Worker identity,
dependency, and owner-decision requirements. This change neither installs that
adapter nor issues or applies an approval. It cannot supply retrospective events
for the current deployment before this instrumentation exists.
