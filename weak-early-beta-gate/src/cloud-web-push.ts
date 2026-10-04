// RFC 8291 / 8292. No keys, recipients, or send mode are supplied by the browser.
export type PushConfig = {
  CLOUD_PUSH_REGISTRATION_ENABLED?: string;
  CLOUD_PUSH_MODE?: string;
  CLOUD_PUSH_TEST_MEMBER_ID?: string;
  CLOUD_PUSH_TEST_SUBSCRIPTION_ID?: string;
  CLOUD_PUSH_TEST_RUN_ID?: string;
  CLOUD_PUSH_ALLOWED_ORIGINS?: string;
  CLOUD_VAPID_PUBLIC_KEY?: string;
  CLOUD_VAPID_PRIVATE_KEY?: string;
  CLOUD_VAPID_SUBJECT?: string;
};
export type PushSubscription = { endpoint: string; p256dh: string; auth: string };
export function decode(value: string, length?: number): Uint8Array<ArrayBuffer> {
  if (typeof value !== "string" || !/^[A-Za-z0-9_-]+$/.test(value) || value.length > 512) throw new Error("invalid_key");
  const bytes = Uint8Array.from(atob(value.replace(/-/g, "+").replace(/_/g, "/")), c => c.charCodeAt(0));
  if ((length !== undefined && bytes.length !== length) || encode(bytes) !== value) throw new Error("invalid_key");
  return bytes;
}
export function encode(bytes: Uint8Array): string {
  return btoa(Array.from(bytes, n => String.fromCharCode(n)).join("")).replace(/=/g, "").replace(/\+/g, "-").replace(/\//g, "_");
}
const utf8 = (text: string): Uint8Array<ArrayBuffer> => Uint8Array.from(new TextEncoder().encode(text));
function join(...parts: Uint8Array[]): Uint8Array<ArrayBuffer> {
  const result = new Uint8Array(parts.reduce((total, bytes) => total + bytes.length, 0));
  let offset = 0;
  for (const bytes of parts) { result.set(bytes, offset); offset += bytes.length; }
  return result;
}
export function allowedEndpoint(endpoint: string, env: PushConfig): URL {
  if (typeof endpoint !== "string" || endpoint.length > 2048) throw new Error("invalid_endpoint");
  const url = new URL(endpoint);
  const origins = (env.CLOUD_PUSH_ALLOWED_ORIGINS ?? "").split(",").map(s => s.trim()).filter(Boolean);
  if (url.protocol !== "https:" || url.username || url.password || url.hash || url.port || !origins.includes(url.origin)) throw new Error("endpoint_not_allowed");
  return url;
}
export async function validateSubscription(value: unknown, env: PushConfig): Promise<PushSubscription> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("invalid_subscription");
  const input = value as Record<string, unknown>;
  if (Object.keys(input).some(key => !["endpoint", "expirationTime", "keys"].includes(key))) throw new Error("invalid_subscription");
  if (input.expirationTime !== null && input.expirationTime !== undefined &&
    (typeof input.expirationTime !== "number" || !Number.isFinite(input.expirationTime) || input.expirationTime <= Date.now())) throw new Error("expired_subscription");
  if (!input.keys || typeof input.keys !== "object" || Array.isArray(input.keys)) throw new Error("invalid_subscription");
  const keys = input.keys as Record<string, unknown>;
  if (Object.keys(keys).sort().join(",") !== "auth,p256dh" || typeof keys.p256dh !== "string" || typeof keys.auth !== "string") throw new Error("invalid_subscription");
  allowedEndpoint(input.endpoint as string, env);
  const point = decode(keys.p256dh, 65);
  if (point[0] !== 4) throw new Error("invalid_key");
  await crypto.subtle.importKey("raw", point, { name: "ECDH", namedCurve: "P-256" }, false, []);
  decode(keys.auth, 16);
  return { endpoint: input.endpoint as string, p256dh: keys.p256dh, auth: keys.auth };
}
export function registrationConfigured(env: PushConfig): boolean {
  try {
    if (env.CLOUD_PUSH_REGISTRATION_ENABLED !== "true" || !env.CLOUD_PUSH_ALLOWED_ORIGINS?.trim()) return false;
    return decode(env.CLOUD_VAPID_PUBLIC_KEY ?? "", 65)[0] === 4;
  } catch { return false; }
}
// Only the approved member can prepare a browser subscription before its exact
// provider origin has been observed. Preparation does not save it or send.
export function personalPreparationConfigured(env: PushConfig): boolean {
  try {
    return env.CLOUD_PUSH_MODE === "personal_test" && !!env.CLOUD_PUSH_TEST_MEMBER_ID &&
      env.CLOUD_PUSH_REGISTRATION_ENABLED === "true" && decode(env.CLOUD_VAPID_PUBLIC_KEY ?? "", 65)[0] === 4;
  } catch { return false; }
}
async function hkdf(key: Uint8Array<ArrayBuffer>, salt: Uint8Array<ArrayBuffer>, info: Uint8Array<ArrayBuffer>, bits: number): Promise<Uint8Array<ArrayBuffer>> {
  const imported = await crypto.subtle.importKey("raw", key, "HKDF", false, ["deriveBits"]);
  return new Uint8Array(new Uint8Array(await crypto.subtle.deriveBits({ name: "HKDF", hash: "SHA-256", salt, info }, imported, bits)));
}
// Test vectors can inject published ephemeral material. Runtime ephemeral keys
// are generated only after an explicitly enabled, authorized dispatch.
export async function encryptPushPayload(subscription: PushSubscription, payload: string,
  fixture?: { privateKey: CryptoKey; publicKey: Uint8Array<ArrayBuffer>; salt: Uint8Array<ArrayBuffer> }): Promise<Uint8Array<ArrayBuffer>> {
  const plaintext = utf8(payload);
  if (plaintext.length > 3000) throw new Error("payload_too_large");
  const recipientBytes = decode(subscription.p256dh, 65);
  const recipient = await crypto.subtle.importKey("raw", recipientBytes, { name: "ECDH", namedCurve: "P-256" }, false, []);
  let material = fixture;
  if (!material) {
    const pair = await crypto.subtle.generateKey({ name: "ECDH", namedCurve: "P-256" }, true, ["deriveBits"]) as CryptoKeyPair;
    material = { privateKey: pair.privateKey, publicKey: new Uint8Array(await crypto.subtle.exportKey("raw", pair.publicKey) as ArrayBuffer), salt: crypto.getRandomValues(new Uint8Array(16)) };
  }
  if (material.salt.length !== 16 || material.publicKey.length !== 65) throw new Error("invalid_material");
  // Generated Workers types spell this property $public; WebCrypto uses public.
  const algorithm = { name: "ECDH", public: recipient };
  const secret = new Uint8Array(new Uint8Array(await crypto.subtle.deriveBits(algorithm, material.privateKey, 256)));
  const ikm = await hkdf(secret, decode(subscription.auth, 16), join(utf8("WebPush: info\0"), recipientBytes, material.publicKey), 256);
  const salt = new Uint8Array(material.salt);
  const key = await hkdf(ikm, salt, utf8("Content-Encoding: aes128gcm\0"), 128);
  const nonce = await hkdf(ikm, salt, utf8("Content-Encoding: nonce\0"), 96);
  const aes = await crypto.subtle.importKey("raw", key, "AES-GCM", false, ["encrypt"]);
  const ciphertext = new Uint8Array(await crypto.subtle.encrypt({ name: "AES-GCM", iv: nonce, tagLength: 128 }, aes, join(plaintext, new Uint8Array([2]))));
  return join(material.salt, new Uint8Array([0, 0, 16, 0, 65]), material.publicKey, ciphertext);
}
export async function vapidAuthorization(endpoint: URL, env: PushConfig, now = Date.now()): Promise<string> {
  const point = decode(env.CLOUD_VAPID_PUBLIC_KEY ?? "", 65);
  const scalar = decode(env.CLOUD_VAPID_PRIVATE_KEY ?? "", 32);
  const subject = new URL(env.CLOUD_VAPID_SUBJECT ?? "");
  if (subject.protocol !== "https:" || subject.username || subject.password || subject.hash || point[0] !== 4) throw new Error("invalid_vapid_configuration");
  const publicJwk = { kty: "EC", crv: "P-256", x: encode(point.slice(1, 33)), y: encode(point.slice(33)), ext: true };
  const privateKey = await crypto.subtle.importKey("jwk", { ...publicJwk, d: encode(scalar) }, { name: "ECDSA", namedCurve: "P-256" }, false, ["sign"]);
  const publicKey = await crypto.subtle.importKey("jwk", publicJwk, { name: "ECDSA", namedCurve: "P-256" }, false, ["verify"]);
  const token = `${encode(utf8(JSON.stringify({ typ: "JWT", alg: "ES256" })))}.${encode(utf8(JSON.stringify({ aud: endpoint.origin, exp: Math.floor(now / 1000) + 3600, sub: subject.href })))}`;
  const signature = new Uint8Array(await crypto.subtle.sign({ name: "ECDSA", hash: "SHA-256" }, privateKey, utf8(token)));
  if (!await crypto.subtle.verify({ name: "ECDSA", hash: "SHA-256" }, publicKey, signature, utf8(token))) throw new Error("vapid_key_mismatch");
  return `vapid t=${token}.${encode(signature)}, k=${env.CLOUD_VAPID_PUBLIC_KEY}`;
}
export type SendResult = { status: "disabled" | "accepted" | "expired" | "rejected" | "unknown"; reason: string };
export async function sendPersonalPush(env: PushConfig, memberId: string, subscriptionId: string,
  subscription: PushSubscription, payload: string, transport: typeof fetch = fetch,
  fixture?: Parameters<typeof encryptPushPayload>[2]): Promise<SendResult> {
  // No broad-member mode exists. Even test mode requires one exact member/device.
  if (env.CLOUD_PUSH_MODE !== "personal_test" || !env.CLOUD_PUSH_TEST_MEMBER_ID || !env.CLOUD_PUSH_TEST_SUBSCRIPTION_ID ||
      env.CLOUD_PUSH_TEST_MEMBER_ID !== memberId || env.CLOUD_PUSH_TEST_SUBSCRIPTION_ID !== subscriptionId) return { status: "disabled", reason: "personal_test_not_enabled" };
  let endpoint: URL, authorization: string, body: Uint8Array<ArrayBuffer>;
  try {
    endpoint = allowedEndpoint(subscription.endpoint, env);
    authorization = await vapidAuthorization(endpoint, env);
    body = await encryptPushPayload(subscription, payload, fixture);
  } catch { return { status: "rejected", reason: "invalid_sender_configuration" }; }
  try {
    const response = await transport(endpoint.href, { method: "POST", body,
      headers: { Authorization: authorization, TTL: "300", "Content-Encoding": "aes128gcm", "Content-Type": "application/octet-stream", Urgency: "normal" },
      redirect: "error", signal: AbortSignal.timeout(8000), cache: "no-store" });
    if (response.ok) return { status: "accepted", reason: "provider_accepted_not_arrival" };
    if ([404, 410].includes(response.status)) return { status: "expired", reason: "subscription_expired" };
    return { status: "rejected", reason: "provider_rejected" };
  } catch { return { status: "unknown", reason: "delivery_outcome_unknown_no_auto_retry" }; }
}
