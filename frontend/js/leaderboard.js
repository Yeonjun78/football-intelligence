/**
 * Football Intelligence — Leaderboard (Phase 2)
 *
 * Connects to GET /api/v1/leaderboard.
 * Renders a sortable table with position, competition, and min-appearances
 * filters. Filtering and sorting are server-side; pagination is offset-based.
 *
 * Depends on: api.js (must be loaded before this file)
 * Entry point: initLeaderboard() — called on DOMContentLoaded
 */

var _LB = {
  position:    '',
  competition: '',
  minApps:     5,
  sortBy:      'goals_p90',
  sortOrder:   'desc',
  offset:      0,
  limit:       25,
  total:       0,
  loading:     false,
};

// ---------------------------------------------------------------------------
// Public
// ---------------------------------------------------------------------------

function initLeaderboard() {
  _lbBindFilters();
  _lbUpdateSortHeaders();
  _lbLoadCompetitions();
  _lbFetch();
}

// ---------------------------------------------------------------------------
// Data loading
// ---------------------------------------------------------------------------

function _lbLoadCompetitions() {
  getLeaderboard({ limit: 500, min_appearances: 0 }).then(function(data) {
    var seen = {};
    var comps = [];
    data.players.forEach(function(p) {
      if (p.competition && !seen[p.competition]) {
        seen[p.competition] = true;
        comps.push(p.competition);
      }
    });
    comps.sort();

    var sel = document.getElementById('competition-select');
    if (!sel) return;
    comps.forEach(function(c) {
      var opt = document.createElement('option');
      opt.value = c;
      opt.textContent = c;
      sel.appendChild(opt);
    });
  }).catch(function() {
    // Competition dropdown degrades gracefully to "All competitions" only
  });
}

function _lbFetch() {
  if (_LB.loading) return;
  _LB.loading = true;

  var loadingEl = document.getElementById('lb-loading');
  var errorEl   = document.getElementById('lb-error');

  if (loadingEl) loadingEl.hidden = false;
  if (errorEl)   errorEl.hidden   = true;

  var params = {
    sort_by:         _LB.sortBy,
    sort_order:      _LB.sortOrder,
    limit:           _LB.limit,
    offset:          _LB.offset,
    min_appearances: _LB.minApps,
  };
  if (_LB.position)    params.position    = _LB.position;
  if (_LB.competition) params.competition = _LB.competition;

  getLeaderboard(params).then(function(data) {
    _LB.total   = data.total;
    _LB.loading = false;
    if (loadingEl) loadingEl.hidden = true;
    _lbRenderRows(data.players);
    _lbRenderStatus();
    _lbRenderPagination();
  }).catch(function(err) {
    _LB.loading = false;
    if (loadingEl) loadingEl.hidden = true;
    if (errorEl) {
      errorEl.textContent = (err && err.detail) ? err.detail : 'Failed to load leaderboard. Is the server running?';
      errorEl.hidden = false;
    }
    var tbody = document.getElementById('lb-tbody');
    if (tbody) tbody.innerHTML = '';
  });
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

function _lbRenderRows(players) {
  var tbody = document.getElementById('lb-tbody');
  if (!tbody) return;

  if (!players || players.length === 0) {
    tbody.innerHTML =
      '<tr><td colspan="8" class="lb-empty">No players match the current filters.</td></tr>';
    return;
  }

  tbody.innerHTML = players.map(function(p, i) {
    var rank     = _LB.offset + i + 1;
    var posClass = 'pos-badge pos-' + _lbEsc(p.position.toLowerCase());
    var href     = '/player.html?id=' + encodeURIComponent(p.id);
    return '<tr>' +
      '<td class="col-rank">' + rank + '</td>' +
      '<td class="col-player">' +
        '<a class="player-link" href="' + href + '">' + _lbEsc(p.player_name) + '</a>' +
        '<span class="player-nat">' + _lbEsc(p.nationality) + '</span>' +
      '</td>' +
      '<td class="col-club">' + _lbEsc(p.club) + '</td>' +
      '<td class="col-pos"><span class="' + posClass + '">' + _lbEsc(p.position) + '</span></td>' +
      '<td class="col-num">' + p.goals_p90.toFixed(2) + '</td>' +
      '<td class="col-num">' + p.assists_p90.toFixed(2) + '</td>' +
      '<td class="col-num">' + p.goals + '</td>' +
      '<td class="col-num">' + p.appearances + '</td>' +
    '</tr>';
  }).join('');
}

function _lbRenderStatus() {
  var el = document.getElementById('lb-status');
  if (!el) return;
  if (_LB.total === 0) {
    el.textContent = 'No players found.';
    return;
  }
  var from = _LB.offset + 1;
  var to   = Math.min(_LB.offset + _LB.limit, _LB.total);
  el.textContent =
    'Showing ' + from + '–' + to + ' of ' + _LB.total.toLocaleString() + ' players';
}

function _lbRenderPagination() {
  var prevBtn  = document.getElementById('lb-prev');
  var nextBtn  = document.getElementById('lb-next');
  var pageInfo = document.getElementById('lb-status-page');
  if (!prevBtn || !nextBtn) return;

  prevBtn.disabled = _LB.offset === 0;
  nextBtn.disabled = _LB.offset + _LB.limit >= _LB.total;

  if (pageInfo && _LB.total > 0) {
    var page  = Math.floor(_LB.offset / _LB.limit) + 1;
    var pages = Math.ceil(_LB.total / _LB.limit);
    pageInfo.textContent = 'Page ' + page + ' of ' + pages;
  } else if (pageInfo) {
    pageInfo.textContent = '';
  }
}

function _lbUpdateSortHeaders() {
  document.querySelectorAll('th[data-col]').forEach(function(th) {
    th.classList.remove('sort-asc', 'sort-desc');
    if (th.dataset.col === _LB.sortBy) {
      th.classList.add(_LB.sortOrder === 'asc' ? 'sort-asc' : 'sort-desc');
    }
  });
}

// ---------------------------------------------------------------------------
// Event binding
// ---------------------------------------------------------------------------

function _lbBindFilters() {
  // Position chips
  var chips = document.querySelectorAll('.chip[data-position]');
  chips.forEach(function(btn) {
    btn.addEventListener('click', function() {
      chips.forEach(function(b) {
        b.classList.remove('chip--active');
        b.setAttribute('aria-pressed', 'false');
      });
      btn.classList.add('chip--active');
      btn.setAttribute('aria-pressed', 'true');
      _LB.position = btn.dataset.position;
      _LB.offset   = 0;
      _lbFetch();
    });
  });

  // Competition select
  var compSel = document.getElementById('competition-select');
  if (compSel) {
    compSel.addEventListener('change', function() {
      _LB.competition = compSel.value;
      _LB.offset      = 0;
      _lbFetch();
    });
  }

  // Min appearances slider — update label on input, fetch on change
  var slider    = document.getElementById('min-apps-slider');
  var sliderVal = document.getElementById('min-apps-value');
  if (slider) {
    slider.addEventListener('input', function() {
      if (sliderVal) sliderVal.textContent = slider.value;
      slider.setAttribute('aria-valuenow', slider.value);
    });
    slider.addEventListener('change', function() {
      _LB.minApps = parseInt(slider.value, 10);
      _LB.offset  = 0;
      _lbFetch();
    });
  }

  // Sortable column headers
  document.querySelectorAll('th[data-col]').forEach(function(th) {
    th.addEventListener('click', function() {
      var col = th.dataset.col;
      if (_LB.sortBy === col) {
        _LB.sortOrder = _LB.sortOrder === 'desc' ? 'asc' : 'desc';
      } else {
        _LB.sortBy    = col;
        _LB.sortOrder = 'desc';
      }
      _LB.offset = 0;
      _lbUpdateSortHeaders();
      _lbFetch();
    });
  });

  // Pagination buttons
  var prevBtn = document.getElementById('lb-prev');
  var nextBtn = document.getElementById('lb-next');
  if (prevBtn) {
    prevBtn.addEventListener('click', function() {
      if (_LB.offset > 0) {
        _LB.offset = Math.max(0, _LB.offset - _LB.limit);
        _lbFetch();
      }
    });
  }
  if (nextBtn) {
    nextBtn.addEventListener('click', function() {
      if (_LB.offset + _LB.limit < _LB.total) {
        _LB.offset += _LB.limit;
        _lbFetch();
      }
    });
  }
}

// ---------------------------------------------------------------------------
// Utility
// ---------------------------------------------------------------------------

function _lbEsc(value) {
  return String(value == null ? '' : value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
