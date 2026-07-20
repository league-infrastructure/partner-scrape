/**
 * Client-side filtering for opportunities and partners pages.
 * Cards have data-* attributes; checkboxes have data-filter attributes.
 * Filter logic: AND across groups, OR within groups.
 * Syncs with URL query params for shareable filtered views.
 */

document.addEventListener('DOMContentLoaded', () => {
  const sidebar = document.querySelector('.filter-sidebar');
  if (!sidebar) return;

  const cards = document.querySelectorAll('[data-type]');
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

  function applyFilters() {
    const activeFilters = getActiveFilters();
    const searchTerm = searchInput?.value.toLowerCase().trim() || '';
    let visibleCount = 0;

    cards.forEach(card => {
      let show = true;

      // Text search: match against title+desc or name+desc
      if (searchTerm) {
        const title = card.dataset.title || card.dataset.name || '';
        const desc = card.dataset.desc || '';
        if (!title.includes(searchTerm) && !desc.includes(searchTerm)) {
          show = false;
        }
      }

      // Checkbox filters: AND across groups, OR within
      if (show) {
        for (const [filterKey, checkedValues] of Object.entries(activeFilters)) {
          if (checkedValues.length === 0) continue;

          const cardValue = card.dataset[filterKey] || '';
          const cardValues = cardValue.split(',').map(v => v.trim());

          // OR within group: card must have at least one matching value
          const hasMatch = checkedValues.some(cv => cardValues.includes(cv));
          if (!hasMatch) {
            show = false;
            break;
          }
        }
      }

      if (show) {
        card.removeAttribute('data-hidden');
        card.style.display = '';
        visibleCount++;
      } else {
        card.setAttribute('data-hidden', '');
        card.style.display = 'none';
      }
    });

    if (countEl) {
      countEl.textContent = `Showing ${visibleCount} of ${cards.length}`;
    }
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
