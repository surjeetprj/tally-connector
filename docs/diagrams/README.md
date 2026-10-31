# Documentation diagrams

The architecture and master-sync documents embed the SVG images in this directory.
Readers need only a normal Markdown image preview for the primary SVG image.
Each image has a collapsed **Editable Mermaid source** section containing the
matching Mermaid block, like BahiAI-Desktop's diagram guides. Expand it to see
the rendered reference in Markdown Preview Enhanced or another Mermaid-capable
viewer; plain Markdown viewers may show the code instead. Open an SVG directly
to zoom into a larger sequence diagram.

SVGs have native pixel dimensions, and the image embeds cap their display width
while allowing shrink-to-fit in narrower panes. In particular, the vertical UI
workflow stays about 273 pixels wide instead of stretching to the full pane.

## Editable sources

| Diagram | Editable Mermaid source | SVG |
| --- | --- | --- |
| Architecture overview | [Source](sources/architecture-overview.mmd) | [Image](architecture-overview.svg) |
| Connector components | [Source](sources/connector-components.mmd) | [Image](connector-components.svg) |
| Master-sync UI workflow | [Source](sources/master-sync-workflow.mmd) | [Image](master-sync-workflow.svg) |
| Link existing masters | [Source](sources/master-link-existing.mmd) | [Image](master-link-existing.svg) |
| Successful master transfer | [Source](sources/master-transfer.mmd) | [Image](master-transfer.svg) |
| Uncertain-write recovery | [Source](sources/master-recovery.mmd) | [Image](master-recovery.svg) |
| Operation states | [Source](sources/master-operation-states.mmd) | [Image](master-operation-states.svg) |

Edit the `.mmd` source, not the generated SVG or its generated Markdown reference.
The build synchronizes the collapsed reference blocks; check rejects drift.
Component names are uppercase;
flowcharts use Mermaid Markdown bold titles and other diagrams use export styling.
Do not put `<b>` tags inside participant names: some Mermaid renderers display
them literally. Flowchart labels use native Mermaid multiline Markdown strings;
the SVG contains text lines, not HTML elements. Sources remain design diagrams,
not proof of runtime behavior.

## Generate and check

Prerequisite: Node.js 22.13 or later and npm. These tools are documentation-only;
the connector's Python runtime does not depend on them. Run from the repo root:

```powershell
npm.cmd ci --prefix tools/docs-diagrams
npm.cmd run diagrams:build --prefix tools/docs-diagrams
npm.cmd run diagrams:check --prefix tools/docs-diagrams
npm.cmd run diagrams:preview --prefix tools/docs-diagrams
```

The initial install needs internet access for packages and Puppeteer's managed
browser. Browser/cache files and preview PNGs stay in ignored `build/docs-diagrams/`;
installed packages stay in the ignored tooling `node_modules/`. Subsequent exports
use the installed toolchain and do not contact Bahi or Tally. Restricted automation
sandboxes may require approval to launch the managed browser; no user-specific
browser or VS Code extension path is hardcoded in the exporter.

The build stages all seven outputs and validates them before replacing committed
images and synchronizing the marked Markdown sections. Surrounding prose is
preserved. A render/validation failure leaves existing images, reference blocks
and the manifest intact.
Temporary exports are retained under ignored build output for investigation.
The check command does not rewrite committed files: it checks registered sources,
SVG image/source links, input/output hashes, XML, accessibility metadata and
portable native SVG content. Missing assets, manual edits or changed inputs fail.

The freshness manifest hashes normalized text (CRLF and LF are equivalent),
including renderer configuration, source files, exporter code and dependency
lockfile. It tracks freshness/integrity; it does not replace reviewing the images.
The preview command renders the actual exported SVGs and collapsible references,
checks image sizing in wide/narrow panes and captures PNGs for visual inspection.
Check line wrapping, arrow labels, clipping, component boldness and the behavior
of Markdown image previews before committing regenerated assets.

Commit source, SVG, manifest and relevant tooling changes together. See
[tooling notes](../../tools/docs-diagrams/README.md) for the pinned renderer and
failure behavior. The [documentation index](../README.md) links the main guides.
