// Package the exact static tree mounted by FastAPI and validate local dependencies.
const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const source = path.resolve(__dirname, '../web');
const output = path.resolve(__dirname, '../dist/web');
const html = fs.readFileSync(path.join(source, 'index.html'), 'utf8');
for (const match of html.matchAll(/(?:href|src)="\/assets\/([^"]+)"/g)) {
  const asset = path.join(source, match[1]);
  fs.accessSync(asset);
  if (asset.endsWith('.js')) execFileSync(process.execPath, ['--check', asset]);
}
const fonts = fs.readFileSync(path.join(source, 'fonts/noto-sans-sc.css'), 'utf8');
for (const match of fonts.matchAll(/url\(['"]?([^)'"]+)['"]?\)/g)) {
  fs.accessSync(path.join(source, 'fonts', match[1]));
}
fs.rmSync(output, { recursive: true, force: true });
fs.cpSync(source, output, { recursive: true });
console.log('Packaged validated frontend assets in dist/web');
