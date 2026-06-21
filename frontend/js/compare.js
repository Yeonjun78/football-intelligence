/**
 * Football Intelligence — Head-to-Head Comparison (Phase 4)
 *
 * Reads p1 and p2 from URLSearchParams, fires three parallel requests:
 *   comparePlayer(p1, p2)  → verdict, metrics with percentiles, S&W
 *   getPlayer(p1)          → raw stats for player 1
 *   getPlayer(p2)          → raw stats for player 2
 *
 * Renders: player cards, data warning, verdict, comparison table, S&W.
 *
 * Depends on: api.js (must load first)
 * Entry point: initComparison() — called on DOMContentLoaded
 */

var _CM_P1_ID = null;
var _CM_P2_ID = null;

// ---------------------------------------------------------------------------
// Public
// ---------------------------------------------------------------------------

function initComparison() {
  var params = new URLSearchParams(window.location.search);
  var rawP1  = params.get('p1');
  var rawP2  = params.get('p2');

  if (!rawP1 || !rawP2) {
    _cmShowGuidance('Select two players from the leaderboard or a player profile to begin a comparison.');
    return;
  }

  _CM_P1_ID = parseInt(rawP1, 10);
  _CM_P2_ID = parseInt(rawP2, 10);

  if (isNaN(_CM_P1_ID) || isNaN(_CM_P2_ID)) {
    _cmShowError('Invalid player IDs in the URL. Return to the leaderboard and select two players.');
    return;
  }

  if (_CM_P1_ID === _CM_P2_ID) {
    _cmShowError('Please select two different players to compare.');
    return;
  }

  _cmLoad(_CM_P1_ID, _CM_P2_ID);
}

// ---------------------------------------------------------------------------
// Data loading
// ---------------------------------------------------------------------------

function _cmLoad(p1id, p2id) {
  var loadingEl = document.getElementById('cm-loading');
  if (loadingEl) loadingEl.hidden = false;

  Promise.all([
    comparePlayer(p1id, p2id),
    getPlayer(p1id),
    getPlayer(p2id),
  ]).then(function(results) {
    if (loadingEl) loadingEl.hidden = true;
    _cmRender(results[0], results[1], results[2]);
  }).catch(function(err) {
    if (loadingEl) loadingEl.hidden = true;
    _cmShowError((err && err.detail) ? err.detail : 'Failed to load comparison. Check that both player IDs are valid.');
  });
}

// ---------------------------------------------------------------------------
// Top-level render
// ---------------------------------------------------------------------------

function _cmRender(cmp, p1data, p2data) {
  // Update browser title and swap button
  document.title = _cmEsc(cmp.player1.player_name) + ' vs ' +
                   _cmEsc(cmp.player2.player_name) + ' — Football Intelligence';
  _cmBindSwap(_CM_P2_ID, _CM_P1_ID);

  // Sections in order
  _cmRenderWarning(cmp);
  _cmRenderHeaders(cmp, p1data, p2data);
  _cmRenderVerdict(cmp);
  _cmRenderTable(cmp, p1data, p2data);
  _cmRenderSW(cmp);

  var content = document.getElementById('cm-content');
  if (content) content.hidden = false;
}

// ---------------------------------------------------------------------------
// Data warning
// ---------------------------------------------------------------------------

function _cmRenderWarning(cmp) {
  if (!cmp.data_warning) return;
  var el = document.getElementById('cm-warning');
  if (!el) return;
  el.textContent = cmp.data_warning;
  el.hidden = false;
  // Cross-position comparison → amber styling
  if (!cmp.same_position) {
    el.classList.remove('banner--warning');
    el.classList.add('banner--warning-cross');
  }
}

// ---------------------------------------------------------------------------
// Player header cards
// ---------------------------------------------------------------------------

function _cmRenderHeaders(cmp, p1data, p2data) {
  _cmFillCard('cm-p1-card', cmp.player1, p1data.stats, 'cm-p1');
  _cmFillCard('cm-p2-card', cmp.player2, p2data.stats, 'cm-p2');
}

function _cmFillCard(cardId, identity, stats, labelClass) {
  var card = document.getElementById(cardId);
  if (!card) return;

  var posClass = 'pos-badge pos-' + identity.position.toLowerCase();
  var profileHref = '/player.html?id=' + encodeURIComponent(identity.id);

  card.innerHTML =
    '<a class="cm-player-name" href="' + profileHref + '">' + _cmEsc(identity.player_name) + '</a>' +
    '<div class="cm-player-meta">' +
      _cmEsc(identity.club) + ' · ' + _cmEsc(identity.competition) +
    '</div>' +
    '<div class="cm-player-sub">' +
      '<span class="' + posClass + '">' + _cmEsc(identity.position) + '</span>' +
      ' · Age ' + identity.age +
    '</div>' +
    '<div class="cm-player-stats">' +
      '<span>' + stats.goals + ' goals</span>' +
      '<span class="pf-sep">·</span>' +
      '<span>' + stats.appearances + ' apps</span>' +
    '</div>';
}

// ---------------------------------------------------------------------------
// Verdict
// ---------------------------------------------------------------------------

function _cmRenderVerdict(cmp) {
  var el = document.getElementById('cm-verdict');
  if (!el) return;

  var v       = cmp.verdict;
  var p1name  = cmp.player1.player_name;
  var p2name  = cmp.player2.player_name;
  var isDraw  = v.winner === 'draw';
  var isCross = !cmp.same_position;

  var winnerLabel;
  if (isDraw) {
    winnerLabel = 'Even Match';
  } else {
    winnerLabel = (v.winner === 'player1') ? p1name : p2name;
  }

  // Verdict card colour class
  var verdictClass = 'cm-verdict';
  if (isDraw) {
    verdictClass += ' cm-verdict--draw';
  } else if (isCross) {
    verdictClass += ' cm-verdict--cross';
  } else {
    verdictClass += ' cm-verdict--win';
  }
  el.className = verdictClass;

  // Metrics-won line (scored metrics only; gc_p90 is not scored)
  var pw = v.metrics_won['player1'] || 0;
  var lw = v.metrics_won['player2'] || 0;
  var dw = v.metrics_won['draw']    || 0;
  var metricsLine;
  if (isDraw) {
    metricsLine = 'Evenly matched across all scored metrics';
  } else {
    var winner2 = (v.winner === 'player1') ? p1name : p2name;
    var loser   = (v.winner === 'player1') ? p2name : p1name;
    var ww      = (v.winner === 'player1') ? pw : lw;
    var loseW   = (v.winner === 'player1') ? lw : pw;
    metricsLine = _cmEsc(winner2) + ' leads on ' + ww +
      ' of ' + (pw + lw + dw) + ' scored metrics · ' +
      _cmEsc(loser) + ' leads on ' + loseW +
      (dw > 0 ? ' · ' + dw + ' draw' + (dw > 1 ? 's' : '') : '');
  }

  // WAS display
  var was1 = (v.advantage_score['player1'] || 0).toFixed(1);
  var was2 = (v.advantage_score['player2'] || 0).toFixed(1);

  el.innerHTML =
    '<div class="cm-verdict-inner">' +
      '<div class="cm-verdict-winner">' + _cmEsc(winnerLabel) + '</div>' +
      '<div class="cm-verdict-score">Weighted Score: ' + was1 + ' vs ' + was2 + '</div>' +
      '<p class="cm-verdict-summary">' + _cmEsc(v.summary) + '</p>' +
      '<div class="cm-verdict-metrics">' + metricsLine + '</div>' +
    '</div>';
}

// ---------------------------------------------------------------------------
// Comparison table
// ---------------------------------------------------------------------------

function _cmRenderTable(cmp, p1data, p2data) {
  var table = document.getElementById('cm-table');
  if (!table) return;

  var p1s = p1data.stats;
  var p2s = p2data.stats;
  var p1n = cmp.player1.player_name;
  var p2n = cmp.player2.player_name;

  // Build lookup from compare API metrics
  var apiMetric = {};
  cmp.metrics.forEach(function(m) { apiMetric[m.metric] = m; });

  // ---- Volume rows (raw counts, higher = better) ----
  var volumeRows = [
    { label: 'Goals',              v1: p1s.goals,             v2: p2s.goals             },
    { label: 'Assists',            v1: p1s.assists,           v2: p2s.assists           },
    { label: 'Non-Penalty Goals',  v1: p1s.non_penalty_goals, v2: p2s.non_penalty_goals },
    { label: 'Goal Contributions', v1: p1s.goal_contributions,v2: p2s.goal_contributions},
    { label: 'Appearances',        v1: p1s.appearances,       v2: p2s.appearances       },
    { label: 'Minutes Played',     v1: p1s.minutes_played,    v2: p2s.minutes_played    },
  ];

  // ---- Rate rows (from API metrics, includes percentile) ----
  var rateRows = [
    {
      label:       'Goals / 90',
      metricKey:   'goals_p90',
      v1:          p1s.goals_per_90,
      v2:          p2s.goals_per_90,
      fmt:         function(v) { return v.toFixed(2); },
      displayOnly: false,
    },
    {
      label:       'Assists / 90',
      metricKey:   'assists_p90',
      v1:          p1s.assists_per_90,
      v2:          p2s.assists_per_90,
      fmt:         function(v) { return v.toFixed(2); },
      displayOnly: false,
    },
    {
      label:       'Contributions / 90',
      metricKey:   'gc_p90',
      v1:          p1s.goal_contributions_per_90,
      v2:          p2s.goal_contributions_per_90,
      fmt:         function(v) { return v.toFixed(2); },
      displayOnly: true,
    },
  ];

  var html =
    '<thead>' +
      '<tr>' +
        '<th class="cm-th-metric">Metric</th>' +
        '<th class="cm-th-player cm-th-p1">' + _cmEsc(p1n) + '</th>' +
        '<th class="cm-th-player cm-th-p2">' + _cmEsc(p2n) + '</th>' +
      '</tr>' +
    '</thead>' +
    '<tbody>';

  // Section: volume
  html += '<tr class="cm-section-row"><td colspan="3">Volume</td></tr>';
  volumeRows.forEach(function(r) {
    var w = _cmWinner(r.v1, r.v2);
    var d1 = r.label === 'Minutes Played' ? r.v1.toLocaleString() : String(r.v1);
    var d2 = r.label === 'Minutes Played' ? r.v2.toLocaleString() : String(r.v2);
    html += _cmRow(r.label, d1, d2, w, null, null, false, false);
  });

  // Section: rate
  html += '<tr class="cm-section-row"><td colspan="3">Rate (per 90 minutes)</td></tr>';
  rateRows.forEach(function(r) {
    var api = apiMetric[r.metricKey];
    var w, p1pct, p2pct;
    if (api) {
      w     = api.winner;
      p1pct = api.player1.percentile;
      p2pct = api.player2.percentile;
    } else {
      w     = _cmWinner(r.v1, r.v2);
      p1pct = null;
      p2pct = null;
    }
    html += _cmRow(r.label, r.fmt(r.v1), r.fmt(r.v2), w, p1pct, p2pct, r.displayOnly, true);
  });

  html += '</tbody>';
  table.innerHTML = html;
}

function _cmRow(label, v1, v2, winner, p1pct, p2pct, displayOnly, isRate) {
  var c1 = winner === 'player1' ? ' cm-win' : (winner === 'draw' ? ' cm-draw' : '');
  var c2 = winner === 'player2' ? ' cm-win' : (winner === 'draw' ? ' cm-draw' : '');

  var pct1 = (p1pct !== null && p1pct !== undefined)
    ? ' <span class="cm-pct">' + Math.round(p1pct) + 'th</span>' : '';
  var pct2 = (p2pct !== null && p2pct !== undefined)
    ? ' <span class="cm-pct">' + Math.round(p2pct) + 'th</span>' : '';

  var labelCell = _cmEsc(label);
  if (displayOnly) {
    labelCell += ' <span class="cm-display-only" title="Equals Goals/90 + Assists/90. Not scored in the verdict.">(display only)</span>';
  }

  return '<tr>' +
    '<td class="cm-td-metric">' + labelCell + '</td>' +
    '<td class="cm-td-val' + c1 + '">' + _cmEsc(v1) + pct1 + '</td>' +
    '<td class="cm-td-val' + c2 + '">' + _cmEsc(v2) + pct2 + '</td>' +
  '</tr>';
}

// ---------------------------------------------------------------------------
// Strengths & Weaknesses
// ---------------------------------------------------------------------------

function _cmRenderSW(cmp) {
  var el = document.getElementById('cm-sw');
  if (!el) return;

  var p1n = cmp.player1.player_name;
  var p2n = cmp.player2.player_name;
  var str = cmp.strengths;
  var wk  = cmp.weaknesses;

  // Combine into display groups
  var groups = [
    { title: _cmEsc(p1n) + ' only — Strengths',   items: str.player1_only, cls: 'chip-strength' },
    { title: _cmEsc(p2n) + ' only — Strengths',   items: str.player2_only, cls: 'chip-strength' },
    { title: 'Shared Strengths',                    items: str.shared,       cls: 'chip-strength chip-shared' },
    { title: _cmEsc(p1n) + ' only — Weaknesses',  items: wk.player1_only,  cls: 'chip-weakness' },
    { title: _cmEsc(p2n) + ' only — Weaknesses',  items: wk.player2_only,  cls: 'chip-weakness' },
    { title: 'Shared Weaknesses',                   items: wk.shared,        cls: 'chip-weakness chip-shared' },
  ].filter(function(g) { return g.items && g.items.length > 0; });

  if (groups.length === 0) {
    el.innerHTML = '';
    return;
  }

  el.innerHTML =
    '<div class="card cm-sw-card">' +
      '<h2 class="cm-section-title">Strengths &amp; Weaknesses</h2>' +
      '<div class="cm-sw-groups">' +
        groups.map(function(g) {
          return '<div class="cm-sw-group">' +
            '<div class="cm-sw-group-title">' + g.title + '</div>' +
            '<div class="pf-chip-list">' +
              g.items.map(function(item) {
                return '<span class="sw-chip ' + g.cls + '">' + _cmEsc(item) + '</span>';
              }).join('') +
            '</div>' +
          '</div>';
        }).join('') +
      '</div>' +
    '</div>';
}

// ---------------------------------------------------------------------------
// Swap button
// ---------------------------------------------------------------------------

function _cmBindSwap(newP1, newP2) {
  var btn = document.getElementById('cm-swap-btn');
  if (!btn) return;
  btn.hidden = false;
  btn.addEventListener('click', function() {
    window.location.href =
      '/compare.html?p1=' + encodeURIComponent(newP1) +
      '&p2=' + encodeURIComponent(newP2);
  });
}

// ---------------------------------------------------------------------------
// Utility
// ---------------------------------------------------------------------------

function _cmWinner(v1, v2) {
  if (v1 > v2) return 'player1';
  if (v2 > v1) return 'player2';
  return 'draw';
}

function _cmShowGuidance(msg) {
  var el = document.getElementById('cm-guidance');
  if (!el) return;
  el.textContent = msg;
  el.hidden = false;
}

function _cmShowError(msg) {
  var el = document.getElementById('compare-error');
  if (!el) return;
  el.textContent = msg;
  el.hidden = false;
}

function _cmEsc(value) {
  return String(value == null ? '' : value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
