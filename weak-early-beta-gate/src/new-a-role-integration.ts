import { hasMemberRoleConfiguration, memberOrigin, roleFacade, type RoleEnv } from './new-a-role-facade';
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

export function memberRouteCandidate(
  request: Request,
  env: MemberEnv,
  denial: Response,
  build: OperationalBuild,
  ctx?: ExecutionContext,
): Promise<Response | null> {
  if (env.CLOUD_MEMBER_VIEW_ENABLED !== 'true') return Promise.resolve(denial);
  const adapters = memberAdapters(env);
  const url = new URL(request.url);
  const scope = memberOrigin(url, env);
  const observe = adapters && scope && hasMemberRoleConfiguration(env) && denial.status === 403
    ? memberResponseObserver(request, build, {
      db: env.CLOUD_MEMBER_DB, ctx, version: env.CLOUD_VERSION_METADATA, owner: env.CLOUD_OWNER_DISCORD_ID, scope,
    }) : undefined;
  if (observe && url.pathname === OBSERVED_OWNER_MANIFEST) {
    observe(denial, () => reportVerifiedSessionSubject(request, env), 'not_checked');
  }
  const services = adapters && memberServices({
    ...adapters,
    identity: memberRequest => reportIdentity(memberRequest, {
      ...env,
      REPORT_ROLE_LOOKUP: (subject, token) => cloudReportRole(env, subject, token, new URL(memberRequest.url).pathname),
    }, true),
  }, env.SESSION_SECRET);
  return roleFacade(request, env, denial, services,
    subject => memberReleaseAllows(env.CLOUD_MEMBER_DB, build, env.CLOUD_VERSION_METADATA, subject), observe);
}
