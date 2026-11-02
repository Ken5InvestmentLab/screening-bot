const test = require('node:test'), assert = require('node:assert/strict');
const { modules } = require('./helpers/cloud-worker-modules.cjs');
const adapter = modules().load('./cloud-whop-adapter');
const NOW = Date.parse('2026-10-04T08:00:00Z');
function fixture() {
  return {
    link: { member_id:'internal', discord_user_id:'discord-fixture', whop_user_id:'user_1', membership_id:'mem_1', payment_id:'pay_1', environment:'live', verification_method:'verified_operator', evidence_reference:'fixture-evidence', verified_at:'2026-09-01T00:00:00Z', revoked_at:null },
    policy: { account_id:'biz_1', product_ids:['prod_1'], paid_plan_ids:['plan_1'], one_time_plan_ids:[] },
    membership: { id:'mem_1', company:{id:'biz_1'}, user:{id:'user_1'}, product:{id:'prod_1'}, plan:{id:'plan_1'}, status:'active', currency:'jpy', payment_collection_paused:false, cancel_at_period_end:false, renewal_period_start:'2026-10-01T00:00:00Z', renewal_period_end:'2026-11-01T00:00:00Z' },
    payment: { id:'pay_1', company:{id:'biz_1'}, user:{id:'user_1'}, membership:{id:'mem_1'}, product:{id:'prod_1'}, plan:{id:'plan_1'}, status:'paid', substatus:'succeeded', currency:'jpy', total:1000, refunded_amount:0, paid_at:'2026-10-01T00:00:00Z' },
  };
}
const decide = (f, now=NOW) => adapter.evaluateNestedMembership(f.membership,f.payment,f.link,f.policy,now);
test('documented nested fields are normalized only with exact operator evidence',()=>{
 const f=fixture();assert.equal(decide(f).status,'paid');f.membership.cancel_at_period_end=true;assert.equal(decide(f).status,'paid');assert.notEqual(decide(f,Date.parse('2026-11-01T00:00:00Z')).status,'paid');
});
for(const [label,change] of [
 ['mixed alias',f=>f.membership.user_id='user_other'],['mixed payment',f=>f.payment.account_id='biz_1'],
 ['foreign company',f=>f.payment.company.id='biz_other'],['foreign owner',f=>f.payment.user.id='user_other'],
 ['foreign membership',f=>f.payment.membership.id='mem_other'],['foreign product',f=>f.payment.product.id='prod_other'],['foreign plan',f=>f.payment.plan.id='plan_other'],
 ['paused collection',f=>f.membership.payment_collection_paused=true],['trial',f=>f.membership.status='trialing'],['revoked',f=>f.membership.status='revoked'],
 ['full refund',f=>f.payment.refunded_amount=1000],['partial refund',f=>f.payment.refunded_amount=1],['unknown refund',f=>f.payment.refunded_amount=null],
 ['dispute',f=>f.payment.substatus='open_dispute'],['unknown substatus',f=>delete f.payment.substatus],['string amount',f=>f.payment.total='1000'],
 ['missing currency',f=>delete f.payment.currency],['wrong currency',f=>f.payment.currency='usd'],['free grant',f=>f.payment.total=0],
 ['prior payment',f=>f.payment.paid_at='2026-09-01T00:00:00Z'],['timezone missing',f=>f.membership.renewal_period_end='2026-11-01'],
 ['missing period',f=>delete f.membership.renewal_period_end],['unverified identity',f=>f.link.evidence_reference=''],['test link',f=>f.link.environment='test'],
]) test('nested provider '+label+' fails closed',()=>{const f=fixture();change(f);assert.notEqual(decide(f).status,'paid');});
test('nested runtime reads only exact verified membership and payment; no broad payment query',async()=>{
 const f=fixture(),reads=[];const m=modules({clock:{now:NOW},fetchMock:async(url,init)=>{reads.push(String(url));assert.equal(init.cache,'no-store');assert.equal(init.redirect,'error');return Response.json(String(url).includes('/memberships/')?f.membership:f.payment);}});
 const db={prepare(){return {bind(){return this;},async first(){return f.link;}};}};
 const result=await m.load('./cloud-api').currentMembership({CLOUD_DB:db,WHOP_API_KEY:'fixture-only',WHOP_ACCOUNT_ID:'biz_1',WHOP_PRODUCT_IDS:'prod_1',WHOP_PAID_PLAN_IDS:'plan_1',WHOP_RESPONSE_SCHEMA:'nested_v1'},'discord-fixture');
 assert.equal(result.status,'paid');assert.deepEqual(reads,['https://api.whop.com/api/v1/memberships/mem_1','https://api.whop.com/api/v1/payments/pay_1']);
 assert.doesNotMatch(JSON.stringify(result),/fixture-only|user_1|pay_1|mem_1/);
});
