/**
 * Football Intelligence — API client
 *
 * All network calls go through this module.
 * No page script calls fetch() directly.
 *
 * Each exported function returns a Promise that resolves to parsed JSON.
 * On non-2xx responses the Promise rejects with an Error whose .status
 * and .detail properties mirror the API error body.
 */

const API_BASE = '/api/v1';

/**
 * Internal GET helper.
 * @param {string} path     - absolute path, e.g. "/api/v1/players"
 * @param {Object} [params] - key/value pairs appended as query string
 * @returns {Promise<any>}
 */
async function _get(path, params = {}) {
  const url = new URL(path, window.location.origin);
  Object.entries(params).forEach(([k, v]) => {
    if (v !== null && v !== undefined && v !== '') {
      url.searchParams.set(k, String(v));
    }
  });

  const res = await fetch(url.toString(), {
    headers: { Accept: 'application/json' },
  });

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (body.detail) detail = body.detail;
    } catch (_) { /* ignore parse error; keep generic message */ }
    const err = new Error(detail);
    err.status = res.status;
    err.detail = detail;
    throw err;
  }

  return res.json();
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Search players by name fragment.
 * @param {string} query - at least 2 characters
 * @returns {Promise<Array>} array of player summary objects
 */
function searchPlayers(query) {
  return _get(`${API_BASE}/players`, { query });
}

/**
 * Fetch a single player's full profile by hash ID.
 * @param {number|string} id
 * @returns {Promise<Object>}
 */
function getPlayer(id) {
  return _get(`${API_BASE}/players/${encodeURIComponent(id)}`);
}

/**
 * Fetch the leaderboard with optional server-side filters.
 * @param {Object} [params]
 * @param {string}  [params.position]        - FW | MF | DF | GK
 * @param {string}  [params.competition]     - exact name (case-insensitive)
 * @param {number}  [params.min_appearances] - default 0
 * @param {string}  [params.sort_by]         - default goals_p90
 * @param {string}  [params.sort_order]      - asc | desc
 * @param {number}  [params.limit]           - 1–500
 * @param {number}  [params.offset]          - ≥ 0
 * @returns {Promise<Object>} LeaderboardResponse
 */
function getLeaderboard(params = {}) {
  return _get(`${API_BASE}/leaderboard`, params);
}

/**
 * Fetch a head-to-head comparison for two player hash IDs.
 * @param {number|string} p1Id
 * @param {number|string} p2Id
 * @returns {Promise<Object>} ComparisonResponse
 */
function comparePlayer(p1Id, p2Id) {
  return _get(`${API_BASE}/compare`, { player1: p1Id, player2: p2Id });
}

/**
 * Fetch server health status.
 * @returns {Promise<Object>} { status: "ok" }
 */
function getHealth() {
  return _get('/health');
}
