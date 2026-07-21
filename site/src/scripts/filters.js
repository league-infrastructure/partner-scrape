/**
 * Client-side filtering for opportunities and partners pages.
 * Cards have data-* attributes; checkboxes have data-filter attributes.
 * Filter logic: AND across groups, OR within groups.
 * Syncs with URL query params for shareable filtered views.
 */

document.addEventListener('DOMContentLoaded', () => {
  const sidebar = document.querySelector('.filter-sidebar');
  if (!sidebar) return;

  // Scoped to the card grid only. Do NOT widen this back to a page-wide
  // `[data-type]` selector: the Opportunities page (sprint 007, ticket
  // 007-002) also renders a Calendar view whose day-entries carry the
  // same data-* attributes so they can be filtered by the same
  // mechanism. If `cards` swept those up too, "Showing X of Y" would
  // double-count every dated opportunity whenever Calendar is present in
  // the DOM. Calendar entries are queried separately below and kept out
  // of this count on purpose — see sprint.md's Design Rationale.
  const cards = document.querySelectorAll('#results-grid [data-type]');
  // Calendar view's day-entries (absent on pages with no calendar), kept
  // as a separate element set from `cards` for the same reason as above.
  const calendarEntries = document.querySelectorAll('#calendar-container [data-type]');
  const checkboxes = sidebar.querySelectorAll('input[type="checkbox"]');
  const searchInput = sidebar.querySelector('.filter-search');
  const clearBtn = document.getElementById('clear-filters');
  const sectionClearLinks = sidebar.querySelectorAll('[data-clear-section]');
  const toggleBtn = document.getElementById('filter-toggle-btn');
  const countEl = document.querySelector('.results-count');

  // Toggle filter sidebar on mobile
  toggleBtn?.addEventListener('click', () => {
    sidebar.classList.toggle('collapsed');
    toggleBtn.textContent = sidebar.classList.contains('collapsed')
      ? (toggleBtn.dataset.label || 'Filter')
      : 'Hide Filters';
  });

  // Restore filter state from URL
  restoreFromURL();

  // Bind events
  checkboxes.forEach(cb => cb.addEventListener('change', () => { applyFilters(); syncToURL(); }));
  searchInput?.addEventListener('input', debounce(() => { applyFilters(); syncToURL(); }, 200));
  clearBtn?.addEventListener('click', (e) => { e.preventDefault(); clearAll(); });
  sectionClearLinks.forEach(link => {
    link.addEventListener('click', (e) => { e.preventDefault(); clearSection(link); });
  });

  // Shared match predicate for one element (a card OR a calendar entry).
  // Extracted so List's cards and Calendar's day-entries are filtered by
  // exactly one algorithm — see the `cards`/`calendarEntries` comment
  // above for why they're still queried, counted, and shown/hidden as
  // two separate element sets.
  function matchesFilters(el, activeFilters, searchTerm) {
    // Text search: match against title+desc or name+desc
    if (searchTerm) {
      const title = el.dataset.title || el.dataset.name || '';
      const desc = el.dataset.desc || '';
      if (!title.includes(searchTerm) && !desc.includes(searchTerm)) {
        return false;
      }
    }

    // Checkbox filters: AND across groups, OR within
    for (const [filterKey, checkedValues] of Object.entries(activeFilters)) {
      if (checkedValues.length === 0) continue;

      const elValue = el.dataset[filterKey] || '';
      const elValues = elValue.split(',').map(v => v.trim());

      // OR within group: element must have at least one matching value
      const hasMatch = checkedValues.some(cv => elValues.includes(cv));
      if (!hasMatch) {
        return false;
      }
    }

    return true;
  }

  function applyFilters() {
    const activeFilters = getActiveFilters();
    const searchTerm = searchInput?.value.toLowerCase().trim() || '';
    let visibleCount = 0;

    cards.forEach(card => {
      const show = matchesFilters(card, activeFilters, searchTerm);
      if (show) {
        card.removeAttribute('data-hidden');
        card.style.display = '';
        visibleCount++;
      } else {
        card.setAttribute('data-hidden', '');
        card.style.display = 'none';
      }
    });

    // `cards.length` is the denominator on purpose: it must reflect only
    // the card grid, unaffected by whether Calendar is open or how many
    // (duplicate, per-day) entries it renders for the same opportunities.
    if (countEl) {
      countEl.textContent = `Showing ${visibleCount} of ${cards.length}`;
    }

    // Second pass: same predicate, applied to Calendar's day-entries.
    // Deliberately NOT folded into visibleCount/cards.length above.
    calendarEntries.forEach(entry => {
      const show = matchesFilters(entry, activeFilters, searchTerm);
      if (show) {
        entry.removeAttribute('data-hidden');
        entry.style.display = '';
      } else {
        entry.setAttribute('data-hidden', '');
        entry.style.display = 'none';
      }
    });
  }

  function getActiveFilters() {
    const filters = {};
    checkboxes.forEach(cb => {
      if (!cb.checked) return;
      const key = cb.dataset.filter;
      if (key === 'search') return;
      if (!filters[key]) filters[key] = [];
      filters[key].push(cb.value);
    });
    return filters;
  }

  function syncToURL() {
    const params = new URLSearchParams();
    const search = searchInput?.value.trim();
    if (search) params.set('q', search);

    checkboxes.forEach(cb => {
      if (cb.checked) {
        const key = cb.dataset.filter;
        if (key === 'search') return;
        params.append(key, cb.value);
      }
    });

    const qs = params.toString();
    const url = qs ? `${window.location.pathname}?${qs}` : window.location.pathname;
    history.replaceState(null, '', url);
  }

  function restoreFromURL() {
    const params = new URLSearchParams(window.location.search);

    const q = params.get('q');
    if (q && searchInput) searchInput.value = q;

    checkboxes.forEach(cb => {
      const key = cb.dataset.filter;
      if (key === 'search') return;
      const values = params.getAll(key);
      cb.checked = values.includes(cb.value);
    });

    applyFilters();
  }

  function clearAll() {
    checkboxes.forEach(cb => cb.checked = false);
    if (searchInput) searchInput.value = '';
    applyFilters();
    history.replaceState(null, '', window.location.pathname);
  }

  // Reset only the inputs within the filter-group that owns the given link.
  function clearSection(link) {
    const group = link.closest('.filter-group');
    if (!group) return;
    group.querySelectorAll('input').forEach(input => {
      if (input.type === 'checkbox') input.checked = false;
      else input.value = '';
    });
    applyFilters();
    syncToURL();
  }

  function debounce(fn, ms) {
    let timer;
    return (...args) => {
      clearTimeout(timer);
      timer = setTimeout(() => fn(...args), ms);
    };
  }
});
