import assert from 'node:assert/strict'
import { test } from 'node:test'
import { createRequire } from 'node:module'
import { mkdtemp, mkdir, writeFile, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

for (const app of ['frontend', 'planner', 'investigations']) {
  test(`${app}: EditorConfig and js-beautify retain glob matching with the new majors`, async () => {
    const require = createRequire(path.join(root, app, 'package.json'))
    const fromEditorconfig = createRequire(require.resolve('editorconfig'))
    const fromBeautify = createRequire(require.resolve('js-beautify'))
    const { Minimatch } = fromEditorconfig('minimatch')
    assert.equal(new Minimatch('**/*.{js,ts}').match('src/example.ts'), true)
    assert.equal(new Minimatch('**/*.{js,ts}').match('src/example.css'), false)
    const folder = await mkdtemp(path.join(tmpdir(), 'verto-glob-compat-'))
    try {
      await mkdir(path.join(folder, 'src'))
      await writeFile(path.join(folder, '.editorconfig'), 'root = true\n[*.{js,ts}]\nindent_style = space\nindent_size = 2\n[*.css]\nindent_size = 4\n')
      await writeFile(path.join(folder, 'src', 'example.ts'), 'const x = 1;')
      await writeFile(path.join(folder, 'src', 'style.css'), 'body{}')
      const { globSync } = fromBeautify('glob')
      assert.deepEqual(globSync('**/*.{js,ts}', { cwd: folder }), ['src/example.ts'])
      assert.deepEqual(globSync('**/*', { cwd: folder, ignore: ['**/*.css'], nodir: true }), ['src/example.ts'])
      const config = await require('editorconfig').parse(path.join(folder, 'src', 'example.ts'))
      assert.equal(config.indent_style, 'space')
      assert.equal(config.indent_size, 2)
      assert.equal(require('js-beautify').js('const x={a:1};', { indent_size: config.indent_size }), 'const x = {\n  a: 1\n};')
    } finally {
      await rm(folder, { recursive: true, force: true })
    }
  })
}

test('Mermaid converter retains Nano ID ESM imports and custom-length IDs', async () => {
  const require = createRequire(path.join(root, 'package.json'))
  const fromConverter = createRequire(require.resolve('@excalidraw/mermaid-to-excalidraw'))
  const { nanoid } = await import(fromConverter.resolve('nanoid'))
  const ids = Array.from({ length: 64 }, () => nanoid(32))
  assert.equal(new Set(ids).size, 64)
  assert.ok(ids.every(id => /^[A-Za-z0-9_-]{32}$/.test(id)))
})

test('Vue language tooling retains minimatch attribute matching', () => {
  const require = createRequire(path.join(root, 'frontend/package.json'))
  const fromCore = createRequire(require.resolve('@vue/language-core'))
  const { minimatch } = fromCore('minimatch')
  assert.equal(minimatch('data-project', 'data-*'), true)
  assert.equal(minimatch('aria-label', 'data-*'), false)
})
