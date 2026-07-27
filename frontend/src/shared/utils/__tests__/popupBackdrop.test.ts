import { describe, expect, it } from 'vitest';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const sourceRoot = join(process.cwd(), 'src');

function vueFiles(directory: string): string[] {
  return readdirSync(directory).flatMap((entry) => {
    const path = join(directory, entry);
    const stat = statSync(path);
    if (stat.isDirectory()) return vueFiles(path);
    return entry.endsWith('.vue') ? [path] : [];
  });
}

function findBackdropSelfClickHandlers() {
  const pattern = /<[^>]*class="[^"]*(?:modal|backdrop|dialog)[^"]*"[^>]*@click\.self=|<[^>]*@click\.self=[^>]*class="[^"]*(?:modal|backdrop|dialog)[^"]*"/gs;

  return vueFiles(sourceRoot).flatMap((file) => {
    const source = readFileSync(file, 'utf8');
    const matches = [...source.matchAll(pattern)];
    return matches.map((match) => ({
      file: relative(process.cwd(), file).replace(/\\/g, '/'),
      snippet: match[0].replace(/\s+/g, ' ').trim(),
    }));
  });
}

describe('popup backdrop behavior', () => {
  it('does not close modal, backdrop, or dialog overlays by clicking outside content', () => {
    expect(findBackdropSelfClickHandlers()).toEqual([]);
  });
});
