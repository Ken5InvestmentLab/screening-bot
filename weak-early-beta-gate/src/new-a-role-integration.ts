import { roleFacade, type RoleEnv } from './new-a-role-facade';
import { memberServices, type MemberAdapters } from './new-a-member-services';
import { reportIdentity } from './shared-report-gate';
import { cloudReportRole } from './cloud-role-authority';
import type { CloudEnv } from './cloud-api';

export function memberRouteCandidate(
  request: Request,
  env: CloudEnv & RoleEnv,
  denial: Response,
  adapters?: Omit<MemberAdapters, 'identity'>,
): Promise<Response | null> {
  if (env.CLOUD_MEMBER_VIEW_ENABLED !== 'true') return Promise.resolve(denial);
  const services = adapters && memberServices({
    ...adapters,
    identity: memberRequest => reportIdentity(memberRequest, {
      ...env,
      REPORT_ROLE_LOOKUP: (subject, token) => cloudReportRole(env, subject, token, new URL(memberRequest.url).pathname),
    }, true),
  }, env.SESSION_SECRET);
  return roleFacade(request, env, denial, services);
}
