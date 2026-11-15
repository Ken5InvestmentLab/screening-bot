// Data-free new-A assets only. No legacy HTML, ledger, price JSON or private inputs are read; only pinned code/assets.
import fs from 'node:fs/promises';import path from 'node:path';import {fileURLToPath} from 'node:url';import './build-new-a-frame.mjs';
const gate=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),publicDir=path.join(gate,'public');
const {ownerFrame}=await import('../.cache/new-a/frame.generated.mjs');
const context={ownerAuthorized:true,roleAuthorized:true,current:true};
for(const page of ['latest','analytics','guide','silence','dive','shadow','fusion','balance'])for(const suffix of ['', '_free'])await fs.writeFile(path.join(publicDir,`weak_early_beta_${page}${suffix}.html`),ownerFrame(`/weak_early_beta_${page}${suffix}.html`,context));
// Only known old generated artifacts are removed; unknown files make validation fail.
for(const name of await fs.readdir(publicDir))if(/^weak_early_beta_data_.*\.json$/.test(name)||/^weak-early-beta-(interactions|scenarios|theme-init)\.js$/.test(name)||/^report-(interactions|theme-init)\.js$/.test(name))await fs.unlink(path.join(publicDir,name));
const oldAssets=path.join(publicDir,'report-assets');try{for(const name of await fs.readdir(oldAssets))if(/^(cloud-logo|discord|coconala|x)-(dark|light)\.png$/.test(name))await fs.unlink(path.join(oldAssets,name));}catch(e){if(e.code!=='ENOENT')throw e;}
console.log(JSON.stringify({newADataFreeSync:true,privateInputsRead:0,legacyBundlesCopied:0}));
