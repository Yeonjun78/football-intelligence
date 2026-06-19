/**
 * Football Intelligence — Player Profile (Phase 3)
 *
 * Loads GET /api/v1/players/{id} and renders the full profile page:
 *   - Identity header card
 *   - Data warning banner (low-sample players)
 *   - Overview text
 *   - Season stats grid
 *   - Strengths / Weaknesses chips
 *   - Similar players (same-position, nearest G/90 + A/90)
 *   - "Compare with…" inline search
 *
 * Depends on: api.js (must load first)
 * Entry point: initProfile() — called on DOMContentLoaded
 */

var _PF_ID   = null;
var _PF_DATA = null;

var _PF_DEBOUNCE_MS     = 250;
var _PF_MIN_QUERY_CHARS = 2;
var _PF_MAX_RESULTS     = 5;
var _pfDebounceTimer    = null;
var _pfSearchResults    = [];

// ---------------------------------------------------------------------------
// Public
// ---------------------------------------------------------------------------

function initProfile() {
  var params = new URLSearchParams(window.location.search);
  var rawId  = params.get('id');

  if (!rawId) {
    window.location.replace('/');
    return;
  }

  _PF_ID = parseInt(rawId, 10);
  if (isNaN(_PF_ID)) {
    window.location.replace('/');
    return;
  }

  _pfLoadProfile(_PF_ID);
}

// ---------------------------------------------------------------------------
// Data loading
// ---------------------------------------------------------------------------

function _pfLoadProfile(id) {
  getPlayer(id).then(function(data) {
    _PF_DATA = data;
    var loading = document.getElementById('player-loading');
    if (loading) loading.hidden = true;
    _pfRender(data);
    _pfLoadSimilar(data);
    _pfBindCompareSearch(id);
  }).catch(function(err) {
    var loading = document.getElementById('player-loading');
    if (loading) loading.hidden = true;
    var msg = err && err.status === 404
      ? 'Player not found. The player may have been removed or the ID is incorrect.'
      : (err && err.detail ? err.detail : 'Failed to load player profile.');
    _pfShowError(msg);
  });
}

function _pfLoadSimilar(data) {
  var gp90 = data.stats.goals_per_90;
  var ap90 = data.stats.assists_per_90;

  getLeaderboard({
    position:        data.position,
    sort_by:         'goals_p90',
    sort_order:      'desc',
    min_appearances: 5,
    limit:           500,
  }).then(function(res) {
    var others = res.players.filter(function(p) { return p.id !== data.id; });

    others.sort(function(a, b) {
      var dA = Math.sqrt(Math.pow(a.goals_p90 - gp90, 2) + Math.pow(a.assists_p90 - ap90, 2));
      var dB = Math.sqrt(Math.pow(b.goals_p90 - gp90, 2) + Math.pow(b.assists_p90 - ap90, 2));
      return dA - dB;
    });

    _pfRenderSimilar(others.slice(0, 4), data.peer_group_size, data.position);
  }).catch(function() {
    var el = document.getElementById('pf-similar');
    if (el) el.innerHTML = '<p class="text-muted" style="padding:12px 0">Similar players unavailable.</p>';
  });
}

// ---------------------------------------------------------------------------
// Rendering — profile
// ---------------------------------------------------------------------------

function _pfRender(data) {
  // page title
  document.title = _pfEsc(data.player_name) + ' — Football Intelligence';

  // identity header
  _pfSet('pf-name',        data.player_name);
  _pfSet('pf-club',        data.club);
  _pfSet('pf-competition', data.competition);
  _pfSet('pf-nationality', data.nationality + ' · ' + data.season);
  _pfSet('pf-age',         'Age ' + data.age);

  var posBadge = document.getElementById('pf-position');
  if (posBadge) {
    posBadge.textContent = data.position;
    posBadge.className   = 'pos-badge pos-' + data.position.toLowerCase();
  }

  // data warning — low sample size
  var stats    = data.stats;
  var warnEl   = document.getElementById('pf-warning');
  if (warnEl) {
    if (stats.appearances < 5 || stats.minutes_played < 270) {
      warnEl.textContent =
        'Small sample warning: this player has fewer than 5 appearances or 270 minutes played. ' +
        'Per-90 statistics may be unreliable.';
      warnEl.hidden = false;
    }
  }

  // overview text
  _pfSet('pf-overview', data.overview || '');

  // stats
  _pfRenderStats(stats);

  // DF / GK disclaimer
  var disclaimer = document.getElementById('pf-pos-disclaimer');
  if (disclaimer && (data.position === 'DF' || data.position === 'GK')) {
    disclaimer.hidden = false;
  }

  // strengths
  _pfRenderChips('pf-strengths', data.strengths || [], 'chip-strength');

  // weaknesses
  _pfRenderChips('pf-weaknesses', data.weaknesses || [], 'chip-weakness');

  // peer group note
  _pfSet('pf-peer-note',
    'Similarity based on ' + data.peer_group_size.toLocaleString() +
    ' ' + data.position + ' players in the dataset.'
  );

  // show content
  var content = document.getElementById('profile-content');
  if (content) content.hidden = false;
}

function _pfRenderStats(stats) {
  var rows = [
    { label: 'Goals',                value: stats.goals },
    { label: 'Assists',              value: stats.assists },
    { label: 'Non-penalty goals',    value: stats.non_penalty_goals },
    { label: 'Goal contributions',   value: stats.goal_contributions },
    { label: 'Appearances',          value: stats.appearances },
    { label: 'Minutes played',       value: stats.minutes_played.toLocaleString() },
    { label: 'Goals / 90',           value: stats.goals_per_90.toFixed(2) },
    { label: 'Assists / 90',         value: stats.assists_per_90.toFixed(2) },
    { label: 'Contributions / 90',   value: stats.goal_contributions_per_90.toFixed(2) },
  ];

  var grid = document.getElementById('pf-stats-grid');
  if (!grid) return;

  grid.innerHTML = rows.map(function(r) {
    return '<div class="stat-card">' +
      '<div class="stat-value">' + _pfEsc(String(r.value)) + '</div>' +
      '<div class="stat-label">' + _pfEsc(r.label) + '</div>' +
    '</div>';
  }).join('');
}

function _pfRenderChips(containerId, items, chipClass) {
  var el = document.getElementById(containerId);
  if (!el) return;

  if (!items || items.length === 0) {
    el.innerHTML = '<span class="text-muted" style="font-size:.8125rem">None listed</span>';
    return;
  }

  el.innerHTML = items.map(function(item) {
    return '<span class="sw-chip ' + chipClass + '">' + _pfEsc(item) + '</span>';
  }).join('');
}

// ---------------------------------------------------------------------------
// Rendering — similar players
// ---------------------------------------------------------------------------

function _pfRenderSimilar(players, peerSize, position) {
  var el = document.getElementById('pf-similar');
  if (!el) return;

  if (!players || players.length === 0) {
    el.innerHTML = '<p class="text-muted" style="padding:12px 0">No comparable players found.</p>';
    return;
  }

  el.innerHTML = players.map(function(p) {
    var posClass = 'pos-badge pos-' + p.position.toLowerCase();
    var href = '/player.html?id=' + encodeURIComponent(p.id);
    return '<a class="similar-card" href="' + href + '">' +
      '<div class="similar-name">' + _pfEsc(p.player_name) + '</div>' +
      '<div class="similar-meta">' +
        _pfEsc(p.club) + ' · <span class="' + posClass + '">' + _pfEsc(p.position) + '</span>' +
      '</div>' +
      '<div class="similar-stats">' +
        '<span>G/90 <strong>' + p.goals_p90.toFixed(2) + '</strong></span>' +
        '<span>A/90 <strong>' + p.assists_p90.toFixed(2) + '</strong></span>' +
      '</div>' +
    '</a>';
  }).join('');
}

// ---------------------------------------------------------------------------
// "Compare with…" inline search
// ---------------------------------------------------------------------------

function _pfBindCompareSearch(currentId) {
  var input    = document.getElementById('compare-search-input');
  var dropdown = document.getElementById('compare-search-dropdown');
  if (!input || !dropdown) return;

  input.addEventListener('input', function() {
    clearTimeout(_pfDebounceTimer);
    var q = input.value.trim();
    if (q.length < _PF_MIN_QUERY_CHARS) {
      _pfCloseDropdown();
      return;
    }
    _pfDebounceTimer = setTimeout(function() { _pfRunSearch(q, currentId); }, _PF_DEBOUNCE_MS);
  });

  // Close on outside click
  document.addEventListener('click', function(e) {
    if (!e.target.closest('.compare-search-wrapper')) {
      _pfCloseDropdown();
    }
  });
}

function _pfRunSearch(query, currentId) {
  searchPlayers(query).then(function(data) {
    var list = Array.isArray(data) ? data : (Array.isArray(data.players) ? data.players : []);
    // Exclude the current player from results
    list = list.filter(function(p) { return p.id !== currentId; });
    _pfSearchResults = list.slice(0, _PF_MAX_RESULTS);
    _pfRenderDropdown(currentId);
  }).catch(function() {
    _pfCloseDropdown();
  });
}

function _pfRenderDropdown(currentId) {
  var dropdown = document.getElementById('compare-search-dropdown');
  if (!dropdown) return;

  if (_pfSearchResults.length === 0) {
    dropdown.innerHTML = '<li class="nav-dropdown-empty">No players found</li>';
    dropdown.classList.add('nav-dropdown--open');
    return;
  }

  dropdown.innerHTML = _pfSearchResults.map(function(p) {
    return '<li class="nav-dropdown-item" data-id="' + _pfEsc(p.id) + '">' +
      '<span class="nav-dropdown-name">' + _pfEsc(p.player_name) + '</span>' +
      '<span class="nav-dropdown-meta">' + _pfEsc(p.club) + ' · ' + _pfEsc(p.position) + '</span>' +
    '</li>';
  }).join('');

  dropdown.querySelectorAll('.nav-dropdown-item').forEach(function(el) {
    el.addEventListener('mousedown', function(e) {
      e.preventDefault();
      var p2id = el.dataset.id;
      window.location.href =
        '/compare.html?p1=' + encodeURIComponent(currentId) + '&p2=' + encodeURIComponent(p2id);
    });
  });

  dropdown.classList.add('nav-dropdown--open');
}

function _pfCloseDropdown() {
  var dropdown = document.getElementById('compare-search-dropdown');
  if (dropdown) {
    dropdown.innerHTML = '';
    dropdown.classList.remove('nav-dropdown--open');
  }
  _pfSearchResults = [];
}

// ---------------------------------------------------------------------------
// Utility
// ---------------------------------------------------------------------------

function _pfSet(id, value) {
  var el = document.getElementById(id);
  if (el) el.textContent = value;
}

function _pfShowError(msg) {
  var errEl = document.getElementById('player-error');
  if (errEl) {
    errEl.textContent = msg;
    errEl.hidden = false;
  }
}

function _pfEsc(value) {
  return String(value == null ? '' : value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
