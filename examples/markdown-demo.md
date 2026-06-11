# Markdown demo

A page authored as plain Markdown. The kit converts it into the same
page-JSON shape used by hand-authored pages, so links, code, headings,
diagrams, and lists all render natively.

## Headings + paragraphs

Plain paragraphs with **bold**, *italic*, and `inline code`. Links
follow the standard form: [Apache Iceberg](https://iceberg.apache.org).

## Code blocks

Code fences become live `<pre>` blocks with the kit's line-number
gutter, fold gutter, copy + wrap buttons:

```python
def hello(name: str) -> None:
    print(f"hello, {name}")
```

A fenced `mermaid` block becomes a live diagram:

```mermaid
graph LR
  A[Markdown] --> B[md_to_page]
  B --> C[Page JSON]
  C --> D[Renderer]
  D --> E[DOM]
```

## Lists

- Unordered item one
- Unordered item two with `code` inline
- Unordered item three

1. Ordered item one
2. Ordered item two
3. Ordered item three

## Blockquote

> A blockquote becomes a callout. Useful for asides and warnings
> that aren't quite scary enough for the danger variant.

## Task list

- [x] Parse markdown body
- [x] Lift typed fences
- [ ] Profit

## Definition list

Island
: A block-level raw-HTML region that the kit renders untouched.

Fence
: A backtick-delimited block; `oku-*` tags lift to typed primitives.

## HTML island

A block-level HTML region passes through to the DOM untouched —
script included. External markdown viewers strip it; the kit runs it.

<div class="demo-island" style="padding:12px;border:1px dashed currentColor;border-radius:8px;">
  <label>Bandwidth (MB/s): <input id="md-demo-bw" type="number" value="1000" style="width:6em"></label>
  <output id="md-demo-out">8.00 ms per GB</output>
</div>
<script>
(function () {
  var bw = document.getElementById('md-demo-bw');
  var out = document.getElementById('md-demo-out');
  if (!bw || !out) return;
  bw.addEventListener('input', function () {
    out.textContent = (8000 / (+bw.value || 1)).toFixed(2) + ' ms per GB';
  });
})();
</script>

## Closing

That's the round-trip: write Markdown, run `oku build`, get the
same interactive page you'd get from authoring the source by hand.
