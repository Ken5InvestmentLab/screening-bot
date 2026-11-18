// Standard CI deployment -> actual normal-origin response. No session or override.
import fs from'node:fs';import{randomBytes}from'node:crypto';
const receipt=JSON.parse(fs.readFileSync('../.cache/weak_early_beta/cloud-deploy-recovery.json','utf8'));
if(receipt.ok!==true||receipt.headSha!==process.env.GITHUB_SHA||!receipt.versionId||receipt.operationalBuild?.source_commit!==receipt.headSha)throw Error('Exact successful CI release unavailable');
const nonce=randomBytes(32).toString('hex'),url='https://tentei-kyokuchi-cloud.ipo-ken5-5489.workers.dev/healthz?new_a_probe='+nonce;
const response=await fetch(url,{redirect:'error',headers:{'Cache-Control':'no-cache'},signal:AbortSignal.timeout(30000)});
if(response.status!==200||response.url!==url||!response.headers.get('cache-control')?.includes('no-store'))throw Error('Normal operational response unavailable');
const actual=await response.json();
if(actual.schema!=='NEW_A_OPERATIONAL_READBACK_V1'||actual.nonce!==nonce||actual.source_commit!==receipt.headSha||actual.version?.id!==receipt.versionId||actual.version?.tag!==receipt.headSha||actual.build_input_sha256!==receipt.operationalBuild.build_input_sha256||actual.owner_http_observed!==false||actual.authentication_probe!==false||actual.d1_writes!==0)throw Error('Normal operational version readback mismatch');
console.log(JSON.stringify({identity:'NEW_A_CI_NORMAL_VERSION_READBACK_V1',source_commit:receipt.headSha,version_id:receipt.versionId,build_input_sha256:actual.build_input_sha256,owner_http_observed:false,management_deployment_observed:false}));
