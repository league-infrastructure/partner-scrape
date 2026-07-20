# Filter sidebar must scroll independently of the opportunities list

**Reported by stakeholder (Eric), 2026-07-20, from the live Opportunities page.**

The opportunities list is long. Right now, scrolling while the pointer is
over the **filter sidebar** scrolls the *opportunities list* — you can only
scroll the filters after reaching the bottom of the whole list. Wrong.

The filter sidebar needs its **own scroll container**: sticky positioning
with a bounded height (`max-height: calc(100vh - <header>)`) and
`overflow-y: auto`, so hovering it scrolls the filters independently while
the list scrolls on its own.

- Component: `src/pages/opportunities/index.astro` (two-column layout) + CSS.
- Make sure it degrades gracefully on mobile (filters stack above the list).
