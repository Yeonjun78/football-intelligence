/**
 * Football Intelligence — Navigation bar
 *
 * Responsibilities:
 *  - Render the persistent nav bar into #nav-root
 *  - Search autocomplete (debounced 250ms, min 2 chars, top 5 results)
 *  - Keyboard navigation in the dropdown (↑ ↓ Enter Escape)
 *  - Health indicator dot (polls /health every 60s)
 *
 * Usage: call initNav() on DOMContentLoaded from every page.
 * Depends on: api.js (must be loaded before nav.js)
 */

const _NAV_HEALTH_POLL_MS  = 60_000;
const _NAV_DEBOUNCE_MS     = 250;
const _NAV_MIN_QUERY_CHARS = 2;
const _NAV_MAX_RESULTS     = 5;

let _debounceTimer  = null;
let _searchResults  = [];
let _selectedIndex  = -1;

// ---------------------------------------------------------------------------
// Public
// ---------------------------------------------------------------------------

function initNav() {
  const root = document.getElementById('nav-root');
  if (!root) return;

  root.innerHTML = _navTemplate();
  _bindSearch();
  _startHealthPoll();
}

// ---------------------------------------------------------------------------
// Template
// ---------------------------------------------------------------------------

function _navTemplate() {
  return `
<div class="nav-inner">
  <a class="nav-logo" href="/">Football Intelligence</a>

  <div class="nav-search-wrapper" role="search">
    <input
      id="nav-search"
      class="nav-search-input"
      type="search"
      placeholder="Search player name…"
      autocomplete="off"
      spellcheck="false"
      aria-label="Search players"
      aria-autocomplete="list"
      aria-controls="nav-dropdown"
      aria-haspopup="listbox"
    />
    <ul
      id="nav-dropdown"
      class="nav-dropdown"
      role="listbox"
      aria-label="Player search results"
    ></ul>
  </div>

  <span
    id="health-dot"
    class="health-dot health-dot--pending"
    title="Checking server…"
    aria-label="Server status"
  ></span>
</div>`;
}

// ---------------------------------------------------------------------------
// Search
// ---------------------------------------------------------------------------

function _bindSearch() {
  const input    = document.getElementById('nav-search');
  const dropdown = document.getElementById('nav-dropdown');
  if (!input || !dropdown) return;

  input.addEventListener('input', () => {
    clearTimeout(_debounceTimer);
    const q = input.value.trim();
    if (q.length < _NAV_MIN_QUERY_CHARS) {
      _closeDropdown();
      return;
    }
    _debounceTimer = setTimeout(() => _runSearch(q), _NAV_DEBOUNCE_MS);
  });

  input.addEventListener('keydown', (e) => {
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        _moveCursor(1);
        break;
      case 'ArrowUp':
        e.preventDefault();
        _moveCursor(-1);
        break;
      case 'Enter':
        e.preventDefault();
        _selectCurrent();
        break;
      case 'Escape':
        _closeDropdown();
        input.blur();
        break;
    }
  });

  // Close when focus leaves the search widget
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.nav-search-wrapper')) {
      _closeDropdown();
    }
  });
}

async function _runSearch(query) {
  try {
    const data = await searchPlayers(query);
    // API may return an array or an object with a .players / .results key
    const list = Array.isArray(data)
      ? data
      : (Array.isArray(data.players) ? data.players : []);
    _searchResults = list.slice(0, _NAV_MAX_RESULTS);
    _selectedIndex = -1;
    _renderDropdown();
  } catch (_err) {
    _closeDropdown();
  }
}

function _renderDropdown() {
  const dropdown = document.getElementById('nav-dropdown');
  if (!dropdown) return;

  if (_searchResults.length === 0) {
    dropdown.innerHTML = '<li class="nav-dropdown-empty">No players found</li>';
    dropdown.classList.add('nav-dropdown--open');
    return;
  }

  dropdown.innerHTML = _searchResults
    .map((p, i) => `
      <li
        class="nav-dropdown-item"
        role="option"
        aria-selected="${i === _selectedIndex}"
        data-index="${i}"
        data-id="${_esc(p.id)}"
      >
        <span class="nav-dropdown-name">${_esc(p.player_name)}</span>
        <span class="nav-dropdown-meta">${_esc(p.club)} · ${_esc(p.position)}</span>
      </li>
    `)
    .join('');

  dropdown.querySelectorAll('.nav-dropdown-item').forEach((el) => {
    // mousedown fires before blur, so the click is not lost
    el.addEventListener('mousedown', (e) => {
      e.preventDefault();
      _navigateTo(el.dataset.id);
    });
  });

  dropdown.classList.add('nav-dropdown--open');
}

function _moveCursor(delta) {
  const items = document.querySelectorAll('.nav-dropdown-item');
  if (!items.length) return;

  _selectedIndex = Math.max(
    -1,
    Math.min(_searchResults.length - 1, _selectedIndex + delta),
  );

  items.forEach((el, i) => {
    const active = i === _selectedIndex;
    el.classList.toggle('nav-dropdown-item--active', active);
    el.setAttribute('aria-selected', String(active));
  });
}

function _selectCurrent() {
  if (_selectedIndex >= 0 && _searchResults[_selectedIndex]) {
    _navigateTo(_searchResults[_selectedIndex].id);
  } else if (_searchResults.length > 0) {
    _navigateTo(_searchResults[0].id);
  }
}

function _closeDropdown() {
  const dropdown = document.getElementById('nav-dropdown');
  if (dropdown) {
    dropdown.innerHTML = '';
    dropdown.classList.remove('nav-dropdown--open');
  }
  _searchResults = [];
  _selectedIndex = -1;
}

function _navigateTo(id) {
  _closeDropdown();
  window.location.href = `/player.html?id=${encodeURIComponent(id)}`;
}

// ---------------------------------------------------------------------------
// Health indicator
// ---------------------------------------------------------------------------

function _startHealthPoll() {
  _checkHealth();
  setInterval(_checkHealth, _NAV_HEALTH_POLL_MS);
}

async function _checkHealth() {
  const dot = document.getElementById('health-dot');
  if (!dot) return;
  try {
    await getHealth();
    dot.className = 'health-dot health-dot--ok';
    dot.title     = 'Server online';
  } catch (_) {
    dot.className = 'health-dot health-dot--error';
    dot.title     = 'Server offline';
  }
}

// ---------------------------------------------------------------------------
// Utility
// ---------------------------------------------------------------------------

function _esc(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
