// Inject only into the logged-in FastMoss tab through cua_repl's CDP capability.
// Replace the three required __PLACEHOLDERS__ in the CUA REPL before Runtime.evaluate.
// For an interrupted first day, replace optional __START_PAGE__ too; otherwise it defaults to 1.
(() => {
  if (location.origin !== 'https://www.fastmoss.com') {
    throw new Error('Wrong browser origin');
  }
  if (typeof globalThis.__SIG__?.gen !== 'function') {
    throw new Error('FastMoss page signature function unavailable');
  }
  if (window.__fastmossNewCollector?.status === 'running') {
    return { status: 'already_running' };
  }
  const token = __COLLECTOR_TOKEN__;
  const startDate = __START_DATE__;
  const endDate = __END_DATE__;
  const startPage = typeof __START_PAGE__ === 'number' ? __START_PAGE__ : 1;
  if (!Number.isInteger(startPage) || startPage < 1) {
    throw new Error('Invalid start page');
  }
  const endpoint = '/api/goods/newProduct';
  const receiver = 'http://127.0.0.1:8768';
  const delayMs = 600;
  const state = {
    status: 'running', startDate, endDate, startPage,
    currentDate: startDate, page: 0, lastSaved: null,
    requests: 0, batches: 0, datesComplete: 0, datesWithSourceEmpty: 0,
    sourceEmptyUnverified: [],
    startedAt: new Date().toISOString(), updatedAt: new Date().toISOString(),
    error: null, stopRequested: false,
    stop() { this.stopRequested = true; },
  };
  window.__fastmossNewCollector = state;
  const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
  const encode = value => encodeURIComponent(String(value))
    .replace(/%20/g, '+')
    .replace(/[!'()*~]/g, char => '%' + char.charCodeAt(0).toString(16).toUpperCase());

  async function report() {
    const progress = {
      status: state.status,
      start_date: startDate, end_date: endDate, start_page: startPage,
      current_date: state.currentDate, page: state.page,
      last_saved: state.lastSaved, requests: state.requests,
      batches: state.batches, dates_complete: state.datesComplete,
      dates_with_source_empty: state.datesWithSourceEmpty,
      source_empty_unverified: state.sourceEmptyUnverified,
      started_at: state.startedAt, updated_at: state.updatedAt,
      error: state.error,
    };
    const body = JSON.stringify(progress);
    let lastError;
    for (let attempt = 1; attempt <= 3; attempt++) {
      try {
        const response = await fetch(receiver + '/progress', {
          method: 'POST',
          headers: { 'content-type': 'application/json', 'x-capture-token': token },
          body,
        });
        if (response.status === 200) return;
        const detail = (await response.text()).slice(0, 500);
        lastError = new Error(`Progress receiver rejected update: HTTP ${response.status}, ${detail}`);
        if (response.status === 403) break;
      } catch (error) {
        lastError = error;
      }
      if (attempt < 3) await wait(attempt * 500);
    }
    throw lastError;
  }

  async function sourcePage(day, page) {
    const params = {
      rank_type: 11, page, order: '1,2', pagesize: 10,
      region: 'US', start_date: day, end_date: day,
      _time: Math.floor(Date.now() / 1000),
      cnonce: Math.floor(1e7 + 9e7 * Math.random()),
    };
    const signedQuery = Object.keys(params).sort()
      .map(key => `${key}=${encode(params[key])}`).join('&');
    const url = endpoint + `?rank_type=11&page=${page}&order=1,2&pagesize=10` +
      `&region=US&start_date=${day}&end_date=${day}` +
      `&_time=${params._time}&cnonce=${params.cnonce}`;
    const response = await fetch(url, {
      credentials: 'same-origin',
      headers: {
        Accept: 'application/json',
        'fm-sig': globalThis.__SIG__.gen(endpoint + '?' + signedQuery, { source: 'pc' }),
        lang: 'ZH_CN', region: 'US', source: 'pc',
      },
    });
    const body = await response.json();
    state.requests++;
    state.page = page;
    state.updatedAt = new Date().toISOString();
    if (response.status !== 200 || body.code !== 200 || !Array.isArray(body.data?.list)) {
      throw new Error(`Source rejected ${day} p${page}: HTTP ${response.status}, code ${body.code}`);
    }
    return { page, body };
  }

  async function sourcePageWithRetry(day, page) {
    let lastError;
    for (let attempt = 1; attempt <= 3; attempt++) {
      try {
        return await sourcePage(day, page);
      } catch (error) {
        lastError = error;
        if (/code MSG_SAFE_|verification|验证码/i.test(String(error))) break;
        if (attempt < 3) await wait(attempt * 2000);
      }
    }
    throw lastError;
  }

  async function saveBatch(day, pages) {
    const first = pages[0].page, last = pages[pages.length - 1].page;
    const filename = `FastMoss_US_new_day_${day}_p` +
      `${String(first).padStart(3, '0')}-${String(last).padStart(3, '0')}.json`;
    const payload = {
      filename, module: '新品榜', region: 'US',
      start_date: day, end_date: day,
      captured_at: new Date().toISOString(), pages,
    };
    const response = await fetch(receiver + '/capture', {
      method: 'POST',
      headers: { 'content-type': 'application/json', 'x-capture-token': token },
      body: JSON.stringify(payload),
    });
    if (response.status !== 201) {
      throw new Error(`Receiver rejected ${filename}: HTTP ${response.status}`);
    }
    state.lastSaved = filename;
    state.batches++;
    state.updatedAt = new Date().toISOString();
    await report();
  }

  async function run() {
    await report();
    for (let current = new Date(startDate + 'T00:00:00Z');
         current >= new Date(endDate + 'T00:00:00Z');
         current.setUTCDate(current.getUTCDate() - 1)) {
      if (state.stopRequested) break;
      const day = current.toISOString().slice(0, 10);
      state.currentDate = day;
      state.page = 0;
      const firstPage = day === startDate ? startPage : 1;
      let first = await sourcePageWithRetry(day, firstPage);
      const total = Number(first.body.data.total);
      if (!Number.isInteger(total) || total < 0 || total > 10000) {
        throw new Error(`Unexpected total ${day}: ${total}`);
      }
      if (total === 0) {
        if (firstPage !== 1 || first.body.data.list.length !== 0) {
          throw new Error(`Unexpected page shape ${day} p${firstPage}`);
        }
        state.datesWithSourceEmpty++;
        state.sourceEmptyUnverified.push({ date: day, page: firstPage });
        await saveBatch(day, [first]);
        continue;
      }
      const pageCount = Math.max(1, Math.ceil(total / 10));
      if (firstPage > pageCount) {
        throw new Error(`Start page ${firstPage} exceeds ${day} page count ${pageCount}`);
      }
      let batch = [];
      for (let page = firstPage; page <= pageCount; page++) {
        if (state.stopRequested) break;
        if (page > firstPage) await wait(delayMs);
        const item = page === firstPage ? first : await sourcePageWithRetry(day, page);
        const rows = item.body.data.list;
        if (Number(item.body.data.total) !== total || rows.length > 10 ||
            (rows.length === 0 && total > 0) ||
            (page < pageCount && rows.length !== 10)) {
          throw new Error(`Unexpected page shape ${day} p${page}`);
        }
        batch.push(item);
        if (batch.length === 5 || page === pageCount) {
          await saveBatch(day, batch);
          batch = [];
        }
      }
      if (state.stopRequested) break;
      state.datesComplete++;
      state.updatedAt = new Date().toISOString();
      await report();
    }
    state.status = state.stopRequested ? 'stopped' : 'complete';
    state.updatedAt = new Date().toISOString();
    await report();
  }

  Promise.resolve().then(run).catch(async error => {
    state.status = 'error';
    state.error = String(error).slice(0, 1000);
    state.updatedAt = new Date().toISOString();
    try { await report(); } catch (_) { /* retain error in page state */ }
  });
  return { status: 'started', startDate, endDate, startPage };
})()
