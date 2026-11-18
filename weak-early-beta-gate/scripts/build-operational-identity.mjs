// Nonsecret build provenance. This describes prepared inputs, never final Worker bytes.
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const gate=fileURLToPath(new URL('../',import.meta.url));
const repo=path.dirname(gate.replace(/[\\/]$/,''));
const generated=path.join(gate,'src/operational-build.generated.ts');
const hash=createHash('sha256');
function visit(name){const file=path.join(gate,name);if(file===generated)return;const stat=fs.lstatSync(file);if(stat.isSymbolicLink())throw Error('Unexpected build symlink');if(stat.isDirectory()){for(const leaf of fs.readdirSync(file).sort())visit(path.join(name,leaf));}else if(stat.isFile()){hash.update(name.split(path.sep).join('/'));hash.update('\0');hash.update(fs.readFileSync(file));hash.update('\0');}}
for(const name of ['src','public','wrangler.jsonc','package.json','package-lock.json'])visit(name);
const source_commit=execFileSync('git',['--no-optional-locks','rev-parse','HEAD'],{cwd:repo,encoding:'utf8',windowsHide:true}).trim();
if(!/^[a-f0-9]{40}$/.test(source_commit))throw Error('Full build source required');
const build={schema:'NEW_A_OPERATIONAL_BUILD_V1',source_commit,build_input_sha256:hash.digest('hex'),target:{worker:'tentei-kyokuchi-cloud',database:'tentei-cloud-settings'}};
fs.writeFileSync(generated,'// Generated nonsecret prepared-input identity.\nexport const operationalBuild = '+JSON.stringify(build)+' as const;\n');
console.log(JSON.stringify({operationalBuild:build}));
