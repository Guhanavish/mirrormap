#!/usr/bin/env node
import { createHash } from 'node:crypto';
import { mkdtemp, writeFile, rm, chmod } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';

const base = 'https://github.com/Guhanavish/mirrormap/releases/download/installer-preview-1/';
const supported = {
  'win32-x64': 'mirrormap-windows-x64.exe',
  'linux-x64': 'mirrormap-linux-x64',
  'darwin-x64': 'mirrormap-macos-x64',
  'darwin-arm64': 'mirrormap-macos-arm64',
};
const filename = supported[process.platform + '-' + process.arch];
const args = process.argv.slice(2);
if (!filename) {
  console.error('No standalone build for this platform. Use the Python wheel or skill-only mode.');
  process.exit(2);
}
if (args.includes('--help') || args.includes('-h')) {
  console.log('mirrormap-bootstrap setup --agent codex --project . [--apply]\nDownloads a checksum-verified native engine; preview unless --apply.');
  process.exit(0);
}
if (!args.length || !['setup','repair','update','uninstall','installation-doctor'].includes(args[0])) {
  console.error('Specify setup, repair, update, uninstall or installation-doctor.');
  process.exit(2);
}
const dir = await mkdtemp(join(tmpdir(), 'mirrormap-'));
try {
  async function download(name, limit) {
    const res = await fetch(base + name, { signal: AbortSignal.timeout(180000) });
    if (!res.ok) throw new Error('Release asset unavailable (' + res.status + '): ' + name);
    const reader = res.body.getReader();
    let size = 0;
    const chunks = [];
    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > limit) { await reader.cancel(); throw new Error('Release asset too large'); }
      chunks.push(Buffer.from(value));
    }
    return Buffer.concat(chunks);
  }
  const sums = (await download('SHA256SUMS.txt', 100000)).toString('utf8');
  const expected = sums.split(/\r?\n/).map(x=>x.match(/^([a-f0-9]{64})\s+\*?(\S+)$/i)).filter(Boolean).filter(x=>x[2]===filename);
  if (expected.length !== 1) throw new Error('Missing or ambiguous release checksum');
  const data = await download(filename, 200000000);
  if (createHash('sha256').update(data).digest('hex') !== expected[0][1].toLowerCase()) throw new Error('Checksum verification failed');
  const executable = join(dir, filename);
  await writeFile(executable, data, {mode: 0o700, flag:'wx'});
  await chmod(executable, 0o700);
  const child = spawnSync(executable, args, {stdio:'inherit',shell:false});
  if (child.error) throw child.error;
  process.exitCode = child.status ?? 2;
} catch (err) {
  console.error('MirrorMap setup: ' + err.message);
  console.error('No fallback bypasses a failed download or checksum. Use a verified manual installation.');
  process.exitCode = 2;
} finally {
  await rm(dir, {recursive:true,force:true});
}
