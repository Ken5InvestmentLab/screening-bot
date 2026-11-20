import { hasMemberRoleConfiguration, isMemberViewPath, memberAudience, memberOrigin, roleFacade, type RoleEnv } from './new-a-role-facade';
import { memberServices, type MemberAdapters } from './new-a-member-services';
import { reportIdentity, reportVerifiedSessionSubject } from './shared-report-gate';
import { cloudReportRole } from './cloud-role-authority';
import type { CloudEnv } from './cloud-api';
import { createNewAMemberCurrentReader } from './new-a-member-current';
import { createNewAMemberProjectionReader } from './new-a-member-projection';
import { createMemberPersonalReader, createMemberSettings } from './new-a-member-storage';
import { memberReleaseAllows } from './new-a-member-release';
import { memberResponseObserver, OBSERVED_OWNER_MANIFEST } from './new-a-member-observation';
import type { OperationalBuild } from './operational-readback';
import { protectedReply, type TrustedOwnerContext } from './new-a-cloud';
import { FRAME_PATHS } from './research-a/frame.generated';

type MemberEnv = CloudEnv & RoleEnv & { CLOUD_MEMBER_DB?: D1Database };

function memberAdapters(env: MemberEnv): Omit<MemberAdapters, 'identity'> | undefined {
  const owner = env.CLOUD_DB;
  const member = env.CLOUD_MEMBER_DB;
  const secret = env.SESSION_SECRET;
  if (!owner || !member || owner === member || !secret
    || typeof owner.withSession !== 'function' || typeof member.withSession !== 'function') return undefined;
  const current = createNewAMemberCurrentReader(owner);
  return {
    current,
    common: createNewAMemberProjectionReader(member, current),
    preferences: (request, subject) => createMemberSettings(member.withSession('first-primary'), secret)(request, subject),
    personal: (subject, source) => createMemberPersonalReader(member.withSession('first-primary'))(subject, source),
    asset: async request => {
      const pathname = new URL(request.url).pathname;
      const asset = await env.ASSETS.fetch(new URL(pathname, 'https://assets.local').toString());
      if (!asset.ok) return new Response(null, { status: 404 });
      return new Response(asset.body, { headers: {
        'content-type': pathname.endsWith('.png') ? 'image/png' : 'application/javascript; charset=utf-8',
      } });
    },
  };
}

export function isSharedOwnerPage(path: string): boolean {
  return isMemberViewPath(path) || FRAME_PATHS.includes(path);
}

export async function sharedOwnerPage(request: Request, env: MemberEnv, ownerContext: TrustedOwnerContext,
  build: OperationalBuild): Promise<Response> {
  const { subject } = ownerContext;
  if (!ownerContext.ownerAuthorized || !subject || subject !== env.CLOUD_OWNER_DISCORD_ID?.trim())
    return protectedReply(request, 401, { error: 'owner_required' });
  if (!ownerContext.current) return protectedReply(request, 503, { error: 'authentication_unavailable' });
  if (!ownerContext.roleAuthorized) return protectedReply(request, 403, { error: 'role_required' });
  const url = new URL(request.url);
  if (!isMemberViewPath(url.pathname) && FRAME_PATHS.includes(url.pathname)) {
    const response = protectedReply(request, 302, '', false);
    response.headers.set('location', url.pathname === '/weak_early_beta_analytics_free.html'
      ? '/weak_early_beta_analytics.html' : '/weak_early_beta_latest.html');
    return response;
  }
  const denial = protectedReply(request, 403, { error: 'role_required' });
  return await routeMemberView(request, env, denial, build, undefined, subject) ?? denial;
}

export function memberRouteCandidate(
  request: Request,
  env: MemberEnv,
  denial: Response,
  build: OperationalBuild,
  ctx?: ExecutionContext,
): Promise<Response | null> {
  return routeMemberView(request, env, denial, build, ctx);
}

function routeMemberView(
  request: Request,
  env: MemberEnv,
  denial: Response,
  build: OperationalBuild,
  ctx?: ExecutionContext,
  verifiedOwner?: string,
): Promise<Response | null> {
  if (env.CLOUD_MEMBER_VIEW_ENABLED !== 'true') return Promise.resolve(denial);
  const adapters = memberAdapters(env);
  const url = new URL(request.url);
  const scope = memberOrigin(url, env);
  const audience = scope && memberAudience(env, scope);
  const observe = !verifiedOwner && adapters && scope && audience && hasMemberRoleConfiguration(env) && denial.status === 403
    ? memberResponseObserver(request, build, {
      db: env.CLOUD_MEMBER_DB, ctx, version: env.CLOUD_VERSION_METADATA, owner: env.CLOUD_OWNER_DISCORD_ID, scope, audience,
    }) : undefined;
  if (observe && url.pathname === OBSERVED_OWNER_MANIFEST) {
    observe(denial, () => reportVerifiedSessionSubject(request, env), 'not_checked');
  }
  const services = adapters && memberServices({
    ...adapters,
    identity: memberRequest => verifiedOwner
      ? Promise.resolve({ subject: verifiedOwner, discord_authorized: true })
      : reportIdentity(memberRequest, {
      ...env,
      REPORT_ROLE_LOOKUP: (subject, token) => cloudReportRole(env, subject, token, new URL(memberRequest.url).pathname),
    }, true),
  }, env.SESSION_SECRET);
  return roleFacade(request, env, denial, services,
    (subject, tier) => {
      // A freshly verified owner retains access during a public release cutover.
      if (verifiedOwner === subject && tier === 'premium') return Promise.resolve(true);
      return memberReleaseAllows(env.CLOUD_MEMBER_DB, build, env.CLOUD_VERSION_METADATA, subject, tier);
    }, observe);
}
