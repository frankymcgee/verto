import { beforeAll, describe, expect, it } from 'vitest';
import { build } from 'esbuild';
import * as sass from 'sass';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
let javascript;
let stylesheet;
let manifest;

beforeAll(async () => {
  const result = await build({
    absWorkingDir: root,
    entryPoints: {
      'verto/dist/js/verto_gantt.bundle': 'verto/public/js/verto_gantt.bundle.js',
      'verto/dist/css/verto_gantt.bundle': 'verto/public/css/verto_gantt.bundle.scss',
    },
    outdir: path.join(root, 'verto/public/dist/test-output'),
    entryNames: '[dir]/[name].[hash]',
    target: 'es2017',
    bundle: true,
    minify: true,
    metafile: true,
    write: false,
    plugins: [{
      name: 'frappe-scss',
      setup(build) {
        build.onLoad({ filter: /\.scss$/ }, ({ path: file }) => ({
          contents: sass.compile(file, { loadPaths: [path.join(root, 'node_modules')] }).css,
          loader: 'css',
        }));
      },
    }],
  });
  manifest = {};
  for (const [outputPath, details] of Object.entries(result.metafile.outputs)) {
    if (!details.entryPoint) continue;
    const key = path.basename(details.entryPoint).replace(/\.scss$/, '.css');
    const output = result.outputFiles.find(file => file.path === path.resolve(root, outputPath));
    manifest[key] = output;
  }
  javascript = manifest['verto_gantt.bundle.js'];
  stylesheet = manifest['verto_gantt.bundle.css'];
});

describe('production Desk Gantt assets', () => {
  it('resolves both Desk hooks to built files with content hashes', () => {
    const hooks = readFileSync(path.join(root, 'verto/hooks.py'), 'utf8');
    const includes = {
      js: hooks.match(/app_include_js = \[([\s\S]*?)\]/)[1],
      css: hooks.match(/app_include_css = \[([\s\S]*?)\]/)[1],
    };
    for (const [kind, asset] of [['js', javascript], ['css', stylesheet]]) {
      expect(includes[kind]).toContain(`"verto_gantt.bundle.${kind}"`);
      expect(asset.path).toMatch(/verto_gantt\.bundle\.[A-Z0-9]+\.(js|css)$/);
      expect(path.extname(asset.path)).toBe(`.${kind}`);
    }
    expect(hooks).not.toContain('"/assets/verto/js/gantt_view.js"');
  });

  it('registers the real chart constructor on cold boot without a global or network assets', () => {
    const context = {
      frappe: { views: { ListView: class {} }, provide() {} },
    };
    Object.defineProperty(context, 'Gantt', {
      get() { throw new Error('The unbundled global Gantt was accessed'); },
    });
    vm.runInNewContext(javascript.text, context);
    const View = context.frappe.views.GanttView;
    const view = new View();
    expect(typeof View.Gantt).toBe('function');
    expect(Array.from(view.required_libs)).toEqual([]);
    expect(javascript.text).not.toContain('/assets/frappe/node_modules/');
  });

  it('ships chart and popup styles inline rather than leaving an external CSS import', () => {
    expect(stylesheet.text).toContain('.gantt-container');
    expect(stylesheet.text).toContain('.popup-wrapper');
    expect(stylesheet.text).not.toContain('@import');
    expect(stylesheet.text).not.toContain('/assets/frappe/node_modules/');
  });
});
