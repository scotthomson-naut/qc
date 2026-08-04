(() => {
  const records = Array.isArray(window.QC_CHECKS) ? window.QC_CHECKS : [];
  const normalize = value => String(value || "").toLowerCase();
  const urlFor = record => `checks/${record.categoryId}/${record.id}.html`;

  document.querySelectorAll('[data-site-search]').forEach(input => {
    input.addEventListener('keydown', event => {
      if (event.key !== 'Enter') return;
      const query = input.value.trim();
      const prefix = location.pathname.includes('/categories/') ? '../' : location.pathname.includes('/checks/') ? '../../' : '';
      location.href = `${prefix}search.html?q=${encodeURIComponent(query)}`;
    });
  });

  const searchInput = document.querySelector('[data-search-page-input]');
  const resultsNode = document.querySelector('[data-search-results]');
  if (!searchInput || !resultsNode) return;

  const params = new URLSearchParams(location.search);
  searchInput.value = params.get('q') || '';

  function render() {
    const query = normalize(searchInput.value).trim();
    const matches = !query ? records : records.filter(record => normalize([
      record.label, record.category, record.description, record.severity,
      record.source, JSON.stringify(record.settings || [])
    ].join(' ')).includes(query));

    resultsNode.innerHTML = matches.length
      ? matches.map(record => `
          <a class="search-result" href="${urlFor(record)}">
            <strong>${record.label}</strong>
            <span>${record.category} · ${record.description || ''}</span>
          </a>`).join('')
      : '<div class="callout">No checks matched your search.</div>';
  }

  searchInput.addEventListener('input', render);
  render();
})();
