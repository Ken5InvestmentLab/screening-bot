import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

export function atomicJson(file, value, {
  fileSystem = fs, platform = process.platform, maxRenameAttempts = 10,
  sleepSync = ms => Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms)
} = {}) {
  if (!Number.isInteger(maxRenameAttempts) || maxRenameAttempts < 1 || maxRenameAttempts > 10) throw new Error('invalid atomic rename retry bound');
  fileSystem.mkdirSync(path.dirname(file), { recursive: true });
  const temp = `${file}.tmp-${process.pid}-${crypto.randomUUID()}`;
  let fd, completeTemp = false, renamed = false;
  try {
    fd = fileSystem.openSync(temp, 'wx', 0o600);
    fileSystem.writeFileSync(fd, `${JSON.stringify(value, null, 2)}\n`); fileSystem.fsyncSync(fd);
    completeTemp = true;
    fileSystem.closeSync(fd); fd = undefined;
    // Windows readers, antivirus and sync clients can briefly deny replacement.
    // Retry only the atomic rename of these same durable bytes, never unlink the
    // destination or rewrite it in place. Ten attempts wait at most 3.25 seconds.
    for (let attempt = 0; ; attempt++) {
      try { fileSystem.renameSync(temp, file); renamed = true; break; }
      catch (error) {
        if (platform !== 'win32' || !['EPERM', 'EBUSY', 'EACCES'].includes(error.code)
          || error.syscall !== 'rename' || attempt + 1 >= maxRenameAttempts) {
          error.atomicTempPath = temp;
          throw error;
        }
        sleepSync(Math.min(50 * 2 ** attempt, 500));
      }
    }
  } finally {
    if (fd !== undefined) fileSystem.closeSync(fd);
    // Retain complete evidence bytes for explicit reconciliation after a failed replacement.
    if ((!completeTemp || renamed) && fileSystem.existsSync(temp)) fileSystem.unlinkSync(temp);
  }
}
