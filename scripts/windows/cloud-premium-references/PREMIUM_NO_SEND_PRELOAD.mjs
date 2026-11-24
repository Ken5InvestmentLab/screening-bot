const prior=globalThis.fetch.bind(globalThis);
globalThis.fetch=async(input,init={})=>{const method=String(init.method||'GET').toUpperCase();if(!['GET','HEAD'].includes(method))throw Error('no-send validation forbids all external writes');return prior(input,{...init,signal:init.signal||AbortSignal.timeout(20000)});};
