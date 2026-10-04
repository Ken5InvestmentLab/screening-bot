// Model DO routing/storage across independently loaded Worker modules. All data
// and credentials are synthetic; the real authority class performs the decision.
exports.runtime = { DurableObject: class { constructor(ctx, env) { this.ctx=ctx; this.env=env; } } };
exports.namespace = function(Class, env, records = new Map()) {
  const instances = new Map();
  return { records, instances, idFromName: name => name, get(name) {
    if(!instances.has(name)) {
      if(!records.has(name)) records.set(name,new Map()); const values=records.get(name);
      const ctx={blockConcurrencyWhile:callback=>callback(),storage:{
        get:async key=>values.get(key),put:async(key,value)=>{values.set(key,structuredClone(value));},delete:async key=>values.delete(key),
      }};
      instances.set(name,new Class(ctx,env));
    }
    return {fetch:async(input,init)=>instances.get(name).fetch(input instanceof Request?input:new Request(input,init))};
  }};
};
