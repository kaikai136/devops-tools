import { readFile, readdir } from 'node:fs/promises';
import { join } from 'node:path';

const root = new URL('../src/styles/', import.meta.url).pathname;
const violations = [];
const special = /(terminal|editor|canvas|popup|overlay|preview|widget|chart|svg|syntax|status|risk|semantic|system-settings|profile-center|security-scan|watermark|machine|host)/i;

async function walk(dir) {
  const entries = await readdir(dir, { withFileTypes: true });
  for (const entry of entries) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) await walk(path);
    else if (entry.name.endsWith('.css')) {
      const content = await readFile(path, 'utf8');
      if (/\.workspace-dark\s+[^\{]*(?:\bpage\b|\bcontainer\b)/i.test(content) && !special.test(path + content)) {
        violations.push(`${path}: workspace-dark page/container selector`);
      }
      if (path.includes('/tools/') && !/(chart|terminal|canvas|table|machine|system-settings|profile-center|security-scan|watermark|host)/i.test(path) && /@media[^{]*\{[^}]*\b(grid|flex|width|display)\b/s.test(content)) {
        violations.push(`${path}: possible feature layout media query`);
      }
      if (path.includes('/tools/') && /#[0-9a-fA-F]{3,8}\b/.test(content) && !/(chart|canvas|svg|terminal|syntax|status|risk|semantic|gradient|shadow|icon|host|ip|password|subnet|machine|profile|authenticator|account|user|role)/i.test(path + content)) {
        violations.push(`${path}: theme hex color`);
      }
    }
  }
}

await walk(root);

if (violations.length) {
  console.error(violations.join('\n'));
  process.exit(1);
}

console.log('style audit passed');
