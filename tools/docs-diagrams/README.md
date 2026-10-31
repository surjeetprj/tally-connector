# SVG export tooling

This private Node package generates documentation assets only. It is not part
of the desktop executable, Python dependency declarations or runtime packaging.
See [diagram maintenance](../../docs/diagrams/README.md) for root-level commands.

## Pinned tools

- Mermaid CLI **11.12.0** and Puppeteer **23.11.1**, with transitive versions in
  `package-lock.json`; use `npm ci` rather than floating/global installations.
- Node.js **>=22.13.0**; the local implementation was checked with Node 24.15.0.
- Puppeteer's managed browser is cached under ignored `build/docs-diagrams/browser/`.
  No extension-owned Mermaid bundle or personal browser installation is required.

The earlier plan proposed CLI 12.0.0/Puppeteer 25.0.0, but the installation
registry returned no published Puppeteer 25.0.0. CLI 11.12.0 declares Puppeteer
`^23` compatibility; the tested published pair above replaces those plan pins.
No forced peer dependency bypass is used.

## Inputs and outputs

`diagrams.json` registers each source/output stem, Markdown owner, title and
description. `mermaid.json` and `labels.css` define the shared native-text SVG
appearance. Every source supplies matching Mermaid accessibility metadata.
The renderer uses a white background, system sans-serif fonts and deterministic
ID seeds; no external fonts or images are needed to display the exported SVGs.

`diagrams.mjs build` calls the installed CLI, validates every staged SVG, then
publishes bounded images, synchronizes the managed Markdown image/reference
sections from the `.mmd` sources, and updates the freshness manifest. No existing output is replaced if
a render or validation fails. A publication IO failure is reported as an error;
the manifest remains the check against partial publication, which must be repaired
by a successful rebuild. This is not a multi-file filesystem transaction.

Native SVG width/height and inline image width prevent narrow diagrams from
being enlarged by preview themes; max-width still allows shrinking on small panes.
The synchronized reference sits in a collapsed details element with a Mermaid
fence, so Markdown Preview Enhanced can render it on expansion. Markers delimit
generated content; editing the `.mmd` source and running build updates both views.

`diagrams.mjs check` validates coverage, exact Markdown image/reference content, hashes and SVG
structure without rewriting tracked assets. It requires the installed managed
browser for XML validation. `diagrams.mjs preview` captures actual SVG images,
checks native/shrink-to-fit image widths at 900px and 320px pane sizes, and renders
all seven collapsible Mermaid references using the pinned renderer. It saves
collapsed/expanded workflow screenshots under ignored build output; it does not
rebuild stale images. Run check first.

Both title/description and positive viewBox dimensions are required. The validator
rejects scripts, event attributes, external references, imported fonts/CSS,
embedded images, HTML `foreignObject` nodes and literal bold/break tags in text.
Visual review is still required: an XML-valid diagram can have poor layout.

If installation/browser launch fails, report that failure and resolve it before
claiming assets were regenerated. Do not silently substitute a VS Code bundle,
disable browser sandboxing or mark old output as current. The SVGs remain readable
without installing Node or the exporter on another reader's computer.
