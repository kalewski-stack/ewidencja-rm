import { defineConfig } from 'vite';
import preact from '@preact/preset-vite';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { readdirSync, statSync, writeFileSync } from 'node:fs';

const root = fileURLToPath(new URL('.', import.meta.url));
const repo = resolve(root, '../..');

// Po buildzie: lista plików dla service workera ekranu (ekran działa z cache po pierwszym załadowaniu).
function swManifest() {
  return {
    name: 'sw-manifest',
    closeBundle() {
      const dist = resolve(root, 'dist');
      const files: string[] = [];
      const walk = (dir: string, prefix: string) => {
        for (const f of readdirSync(dir)) {
          const p = resolve(dir, f);
          if (statSync(p).isDirectory()) walk(p, `${prefix}${f}/`);
          else files.push(`${prefix}${f}`);
        }
      };
      walk(dist, '/');
      const keep = files.filter((f) =>
        (f.startsWith('/assets/') && !/\/(ops|mod|phone|print)-/.test(f)) || f.startsWith('/static/') || f.startsWith('/theme/'));
      writeFileSync(resolve(dist, 'sw-manifest.json'), JSON.stringify({ version: Date.now().toString(36), files: ['/screen', ...keep] }));
    },
  };
}

export default defineConfig(({ mode }) => ({
  root,
  publicDir: resolve(root, 'public'),
  plugins: [preact(), swManifest()],
  resolve: { alias: { '@shared': resolve(repo, 'packages/shared'), '@content': resolve(repo, 'content') } },
  build: {
    outDir: resolve(root, 'dist'),
    emptyOutDir: true,
    sourcemap: false,
    minify: mode === 'development' ? false : 'esbuild',
    rollupOptions: {
      input: {
        phone: resolve(root, 'index.html'),
        screen: resolve(root, 'screen.html'),
        ops: resolve(root, 'ops.html'),
        mod: resolve(root, 'mod.html'),
        print: resolve(root, 'print/qr.html'),
      },
    },
  },
}));
