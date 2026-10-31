import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createHash } from 'node:crypto';
import { spawn } from 'node:child_process';

const tool = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(tool, '../..');
const assets = path.join(root, 'docs/diagrams');
const work = path.join(root, 'build/docs-diagrams');
const manifestPath = path.join(assets, 'manifest.json');
const command = process.argv[2];
const read = (filename) => fs.readFile(filename, 'utf8');
const sha = (value) => createHash('sha256').update(value.replace(/\r\n/g, '\n')).digest('hex');
const relative = (filename) => path.relative(root, filename).split(path.sep).join('/');

async function inventory() {
  const entries = JSON.parse(await read(path.join(tool, 'diagrams.json')));
  if (entries.length !== 7 || new Set(entries.map((e) => e.id)).size !== 7) {
    throw new Error('Expected seven unique diagram entries.');
  }
  for (const e of entries) {
    if (!/^[a-z][a-z0-9-]+$/.test(e.id) || !e.document.startsWith('docs/') ||
        e.document.includes('..') || !e.title || !e.description) {
      throw new Error('Invalid diagram inventory entry.');
    }
    const source = await read(path.join(assets, 'sources', `${e.id}.mmd`));
    if (/<\/?b\b/i.test(source)) throw new Error(`${e.id}: HTML bold tags are not supported.`);
    if (!source.includes(`accTitle: ${e.title}`) || !source.includes(`accDescr: ${e.description}`)) {
      throw new Error(`${e.id}: accessibility metadata differs from the inventory.`);
    }
    const doc = await read(path.join(root, e.document));
    if (!doc.includes(`<!-- diagram-start: ${e.id} -->`) ||
        !doc.includes(`<!-- diagram-end: ${e.id} -->`)) {
      throw new Error(`${e.id}: missing managed image/reference section.`);
    }
  }
  const expected = entries.map((e) => `${e.id}.mmd`).sort();
  const actual = (await fs.readdir(path.join(assets, 'sources'))).filter((f) => f.endsWith('.mmd')).sort();
  if (JSON.stringify(expected) !== JSON.stringify(actual)) throw new Error('Unregistered Mermaid sources.');
  return entries;
}

const escapeHtml = (value) => value.replaceAll('&', '&amp;').replaceAll('"', '&quot;')
  .replaceAll('<', '&lt;').replaceAll('>', '&gt;');

function sectionPattern(entry) {
  return new RegExp(`<!-- diagram-start: ${entry.id} -->[\\s\\S]*?<!-- diagram-end: ${entry.id} -->`, 'g');
}

async function diagramSection(entry, svg) {
  const box = svg.match(/\bviewBox="([^"]+)"/)[1].split(/[ ,]+/).map(Number);
  const width = Math.ceil(box[2]);
  const prefix = path.posix.relative(path.posix.dirname(entry.document), 'docs/diagrams');
  const source = (await read(path.join(assets, 'sources', `${entry.id}.mmd`))).replace(/\r\n/g, '\n').trimEnd();
  return `<!-- diagram-start: ${entry.id} -->\n` +
    `<p><a href="${prefix}/${entry.id}.svg">` +
    `<img src="${prefix}/${entry.id}.svg" alt="${escapeHtml(entry.title)}" ` +
    `width="${width}" style="width: ${width}px; max-width: 100%; height: auto;">` +
    `</a></p>\n\n<details>\n<summary>Editable Mermaid source</summary>\n\n` +
    `<!-- diagram: ${entry.id} -->\n\x60\x60\x60mermaid\n${source}\n\x60\x60\x60\n\n` +
    `[Source file](${prefix}/sources/${entry.id}.mmd)\n\n</details>\n` +
    `<!-- diagram-end: ${entry.id} -->`;
}

async function boundedSvg(page, text) {
  await page.goto('about:blank');
  return page.evaluate((xml) => {
    const doc = new DOMParser().parseFromString(xml, 'image/svg+xml');
    if (doc.querySelector('parsererror')) throw new Error('Malformed SVG');
    const svg = doc.documentElement;
    const box = svg.getAttribute('viewBox').split(/[ ,]+/).map(Number);
    svg.setAttribute('width', String(Math.ceil(box[2])));
    svg.setAttribute('height', String(Math.ceil(box[3])));
    return new XMLSerializer().serializeToString(svg);
  }, text);
}

async function inputs(entries) {
  const files = ['package.json', 'package-lock.json', 'diagrams.mjs', 'diagrams.json',
    'mermaid.json', 'labels.css', '.puppeteerrc.cjs'].map((f) => path.join(tool, f));
  files.push(...entries.map((e) => path.join(assets, 'sources', `${e.id}.mmd`)));
  const hashes = {};
  for (const filename of files.sort()) hashes[relative(filename)] = sha(await read(filename));
  return hashes;
}

async function browser() {
  process.env.PUPPETEER_CACHE_DIR = path.join(work, 'browser');
  const { default: puppeteer } = await import('puppeteer');
  return puppeteer.launch({ headless: true });
}

async function validateSvg(page, text, entry) {
  // A previous preview may have navigated this page to a standalone SVG document.
  await page.goto('about:blank');
  const source = await read(path.join(assets, 'sources', `${entry.id}.mmd`));
  const components = [
    ...source.matchAll(/\*\*([A-Z][A-Z0-9 /_-]+)\*\*/g),
    ...source.matchAll(/participant \w+ as ([A-Z][A-Z0-9 /_-]+)/g),
    ...source.matchAll(/state "([A-Z][A-Z0-9 _-]+)" as/g),
  ].map((match) => match[1]);
  if (!components.length) throw new Error(`${entry.id}: no component labels to validate.`);
  const result = await page.evaluate(({ xml, components }) => {
    const doc = new DOMParser().parseFromString(xml, 'image/svg+xml');
    if (doc.querySelector('parsererror')) return { error: 'Malformed SVG XML' };
    const svg = doc.documentElement;
    if (svg.localName !== 'svg' || svg.namespaceURI !== 'http://www.w3.org/2000/svg') {
      return { error: 'Expected SVG root' };
    }
    const box = (svg.getAttribute('viewBox') || '').trim().split(/[ ,]+/).map(Number);
    if (box.length !== 4 || !box.every(Number.isFinite) || box[2] <= 0 || box[3] <= 0) {
      return { error: 'Missing or invalid viewBox' };
    }
    if (Number(svg.getAttribute('width')) !== Math.ceil(box[2]) ||
        Number(svg.getAttribute('height')) !== Math.ceil(box[3])) {
      return { error: 'SVG must have explicit native pixel dimensions' };
    }
    if (doc.querySelector('script, foreignObject, image, iframe, object, embed, link')) {
      return { error: 'Nonportable or executable SVG element' };
    }
    for (const element of doc.querySelectorAll('*')) {
      for (const attr of element.attributes) {
        if (/^on/i.test(attr.name)) return { error: 'Executable attribute' };
        if (attr.localName === 'href' && !attr.value.startsWith('#')) return { error: 'External reference' };
        if (/url\(\s*['"]?(?!#)/i.test(attr.value)) return { error: 'External URL in attribute' };
      }
    }
    const css = [...doc.querySelectorAll('style')].map((e) => e.textContent).join('\n');
    if (/@import|@font-face|url\(\s*['"]?(?!#)/i.test(css)) return { error: 'External CSS resource' };
    const visible = [...doc.querySelectorAll('text')].map((e) => e.textContent).join(' ');
    if (/<\/?(?:b|br)\b/i.test(visible)) return { error: 'Literal HTML tags in labels' };
    if (!visible.trim()) return { error: 'Diagram has no native SVG text' };
    document.body.replaceChildren(document.importNode(svg, true));
    const leaves = [...document.querySelectorAll('text, tspan')].filter((e) => !e.querySelector('tspan'));
    const bold = leaves.filter((e) => Number.parseInt(getComputedStyle(e).fontWeight, 10) >= 700)
      .map((e) => e.textContent).join('').replace(/\s+/g, '');
    const missing = components.filter((label) => !bold.includes(label.replace(/\s+/g, '')));
    if (missing.length) return { error: `Component labels are not bold: ${missing.join(', ')}` };
    return { title: doc.querySelector('title')?.textContent,
      description: doc.querySelector('desc')?.textContent, box };
  }, { xml: text, components });
  if (result.error) throw new Error(`${entry.id}: ${result.error}`);
  if (result.title !== entry.title || result.description !== entry.description) {
    throw new Error(`${entry.id}: missing or incorrect SVG title/description.`);
  }
  return result.box;
}

async function runCli(args) {
  const cli = path.join(path.dirname(fileURLToPath(import.meta.resolve('@mermaid-js/mermaid-cli'))), 'cli.js');
  await new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [cli, ...args], { cwd: tool, windowsHide: true,
      env: { ...process.env, PUPPETEER_CACHE_DIR: path.join(work, 'browser') }, stdio: 'inherit' });
    child.on('error', reject);
    child.on('exit', (code) => code === 0 ? resolve() : reject(new Error(`Mermaid CLI exited ${code}.`)));
  });
}

async function build(entries) {
  await fs.mkdir(work, { recursive: true });
  const staging = await fs.mkdtemp(path.join(work, 'export-'));
  const renderer = JSON.parse(await read(path.join(tool, 'mermaid.json')));
  const b = await browser();
  try {
    const page = await b.newPage();
    for (const e of entries) {
      const config = path.join(staging, `${e.id}.json`);
      await fs.writeFile(config, JSON.stringify({ ...renderer, deterministicIDSeed: e.id }));
      await runCli(['--input', path.join(assets, 'sources', `${e.id}.mmd`),
        '--output', path.join(staging, `${e.id}.svg`), '--configFile', config,
        '--cssFile', path.join(tool, 'labels.css'), '--backgroundColor', 'white', '--width', '1800']);
      const stagedSvg = path.join(staging, `${e.id}.svg`);
      await fs.writeFile(stagedSvg, await boundedSvg(page, await read(stagedSvg)));
      await validateSvg(page, await read(path.join(staging, `${e.id}.svg`)), e);
      console.log(`Validated ${e.id}`);
    }
    // Publish only after every render and SVG validation succeeds.
    const documents = new Map();
    for (const e of entries) {
      const text = documents.get(e.document) ?? await read(path.join(root, e.document));
      const matches = [...text.matchAll(sectionPattern(e))];
      if (matches.length !== 1) throw new Error(`${e.id}: expected exactly one managed section.`);
      documents.set(e.document, text.replace(sectionPattern(e), () =>
        // Replacement text is assembled below before any files are published.
        `<!-- staged: ${e.id} -->`));
    }
    for (const e of entries) {
      const section = await diagramSection(e, await read(path.join(staging, `${e.id}.svg`)));
      documents.set(e.document, documents.get(e.document).replace(`<!-- staged: ${e.id} -->`, () => section));
    }
    const outputs = {};
    for (const e of entries) {
      const name = `${e.id}.svg`;
      const svg = await read(path.join(staging, name));
      await fs.writeFile(path.join(assets, name), svg);
      outputs[name] = sha(svg);
    }
    for (const [filename, text] of documents) await fs.writeFile(path.join(root, filename), text);
    const manifest = { formatVersion: 1, inputs: await inputs(entries), outputs };
    await fs.writeFile(manifestPath, JSON.stringify(manifest, null, 2) + '\n');
    console.log('Published seven bounded SVGs, synchronized Markdown references and freshness manifest.');
  } finally { await b.close(); }
}

async function check(entries) {
  const manifest = JSON.parse(await read(manifestPath));
  if (manifest.formatVersion !== 1 || JSON.stringify(manifest.inputs) !== JSON.stringify(await inputs(entries))) {
    throw new Error('Diagram sources/tooling changed. Run diagrams:build and review the SVGs.');
  }
  const expected = entries.map((e) => `${e.id}.svg`).sort();
  const actual = (await fs.readdir(assets)).filter((f) => f.endsWith('.svg')).sort();
  if (JSON.stringify(expected) !== JSON.stringify(actual) ||
      JSON.stringify(Object.keys(manifest.outputs).sort()) !== JSON.stringify(expected)) {
    throw new Error('Missing or unregistered SVG outputs.');
  }
  const b = await browser();
  try {
    const page = await b.newPage();
    for (const e of entries) {
      const name = `${e.id}.svg`;
      const svg = await read(path.join(assets, name));
      if (sha(svg) !== manifest.outputs[name]) throw new Error(`${name}: modified or stale output.`);
      const document = (await read(path.join(root, e.document))).replace(/\r\n/g, '\n');
      const sections = [...document.matchAll(sectionPattern(e))];
      if (sections.length !== 1 || sections[0][0] !== await diagramSection(e, svg)) {
        throw new Error(`${e.id}: Markdown image/reference differs from its source. Run diagrams:build.`);
      }
      await validateSvg(page, svg, e);
    }
  } finally { await b.close(); }
  console.log('PASS: seven sources, Markdown embeds, input/output hashes and self-contained accessible SVGs.');
}

async function preview(entries) {
  const directory = path.join(work, 'preview');
  await fs.mkdir(directory, { recursive: true });
  const b = await browser();
  try {
    const page = await b.newPage();
    for (const e of entries) {
      const filename = path.join(assets, `${e.id}.svg`);
      const box = await validateSvg(page, await read(filename), e);
      const width = Math.min(2200, Math.ceil(box[2]) + 32);
      const height = Math.min(2200, Math.ceil(box[3]) + 32);
      await page.setViewport({ width, height, deviceScaleFactor: 1 });
      await page.goto(pathToFileURL(filename).href);
      await page.screenshot({ path: path.join(directory, `${e.id}.png`), fullPage: true });
      console.log(`Preview ${e.id}: ${box[2]} x ${box[3]}`);
    }
    const figures = (await Promise.all(entries.map(async (e) => {
      const document = await read(path.join(root, e.document));
      let section = [...document.matchAll(sectionPattern(e))][0][0];
      section = section.replace(/(src|href)="([^"]+)"/g, (_, attr, target) =>
        `${attr}="${new URL(target, pathToFileURL(path.join(root, e.document))).href}"`);
      section = section.replace(/```mermaid\r?\n([\s\S]*?)```/g,
        (_, source) => `<pre class="mermaid">${escapeHtml(source)}</pre>`);
      section = section.replace(/\[Source file\]\(([^)]+)\)/g, (_, target) =>
        `<a href="${new URL(target, pathToFileURL(path.join(root, e.document))).href}">Source file</a>`);
      return `<figure id="${e.id}"><h2>${escapeHtml(e.title)}</h2>${section}</figure>`;
    }))).join('\n');
    const gallery = path.join(directory, 'index.html');
    await fs.writeFile(gallery, '<!doctype html><meta charset="utf-8"><title>SVG image review</title>' +
      '<style>body{background:white;color:#162e49;font:16px Arial;margin:24px}figure{margin:32px 0}' +
      'img{width:100%;max-width:100%;height:auto;border:1px solid #ddd}</style>' + figures);
    await page.setViewport({ width: 1180, height: 900, deviceScaleFactor: 1 });
    await page.goto(pathToFileURL(gallery).href, { waitUntil: 'networkidle0' });
    const loaded = await page.$$eval('img', (images) =>
      images.length === 7 && images.every((image) => image.complete && image.naturalWidth > 0));
    if (!loaded) throw new Error('Ordinary SVG image embeds failed to load.');
    for (const width of [900, 320]) {
      await page.setViewport({ width, height: 900, deviceScaleFactor: 1 });
      const sizes = await page.$$eval('img', (images) => images.map((image) => ({
        actual: image.getBoundingClientRect().width,
        limit: Number(image.getAttribute('width')) + 2,
      })));
      if (sizes.some((size) => size.actual > size.limit || size.actual > width - 46)) {
        throw new Error(`Image enlarged beyond native/pane width at viewport ${width}.`);
      }
    }
    await page.setViewport({ width: 1180, height: 900, deviceScaleFactor: 1 });
    await page.screenshot({ path: path.join(directory, 'image-embeds.png'), fullPage: true });
    console.log('PASS: seven SVG embeds load without Mermaid, stay native-sized and shrink at 900px/320px panes.');
    const bundle = path.join(path.dirname(fileURLToPath(import.meta.resolve('mermaid'))), 'mermaid.js');
    await page.addScriptTag({ path: bundle });
    await page.addStyleTag({ path: path.join(tool, 'labels.css') });
    const config = JSON.parse(await read(path.join(tool, 'mermaid.json')));
    const count = await page.evaluate(async (config) => {
      window.mermaid.initialize({ ...config, startOnLoad: false });
      const references = [...document.querySelectorAll('pre.mermaid')];
      for (let i = 0; i < references.length; i++) {
        const rendered = await window.mermaid.render(`reference-${i}`, references[i].textContent);
        const container = document.createElement('div');
        container.className = 'rendered-reference';
        container.innerHTML = rendered.svg;
        references[i].replaceWith(container);
      }
      return references.length;
    }, config);
    if (count !== 7) throw new Error('Expected seven rendered Mermaid references.');
    await page.setViewport({ width: 900, height: 900, deviceScaleFactor: 1 });
    const workflow = await page.$('#master-sync-workflow');
    await workflow.screenshot({ path: path.join(directory, 'workflow-collapsed.png') });
    await page.$eval('#master-sync-workflow details', (details) => { details.open = true; });
    await workflow.screenshot({ path: path.join(directory, 'workflow-reference.png') });
    console.log('PASS: all seven collapsible Mermaid references render; UI workflow previews captured.');
  } finally { await b.close(); }
  console.log(`Preview images: ${relative(directory)}`);
}

try {
  const entries = await inventory();
  if (command === 'build') await build(entries);
  else if (command === 'check') await check(entries);
  else if (command === 'preview') await preview(entries);
  else throw new Error('Usage: node diagrams.mjs build|check|preview');
} catch (error) {
  console.error(`Diagram tooling: ${error.message}`);
  process.exitCode = 1;
}
