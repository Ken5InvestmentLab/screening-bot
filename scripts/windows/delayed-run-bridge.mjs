import { execFileSync } from 'node:child_process';
export function delayedBridge(config, command, record, extra=[]) {
  return JSON.parse(execFileSync(config.pythonPath, ['-B','-m','weak_early_beta.new_a.delayed_recovery',command,'--record',record,...extra], {cwd:config.repoPath,encoding:'utf8',windowsHide:true,timeout:300000}));
}
