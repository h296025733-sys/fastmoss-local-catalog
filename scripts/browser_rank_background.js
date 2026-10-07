// Launch through cua_repl CDP only after the new-product history runner finishes.
// Replace __COLLECTOR_TOKEN__, __START_DATE__, __END_DATE__ before injection.
// For an interrupted first day, optionally replace __START_MODULE__ (sales,
// managed, or hot) and __START_PAGE__. Defaults are sales and page 1.
// __PERIOD__ defaults to day; month uses date values such as 2026-09.
(() => {
  if (location.origin !== 'https://www.fastmoss.com' ||
      typeof globalThis.__SIG__?.gen !== 'function') {
    throw new Error('FastMoss signed-in page is unavailable');
  }
  if (window.__fastmossRankCollector?.status === 'running') {
    return { status: 'already_running' };
  }
  const token = __COLLECTOR_TOKEN__;
  const startDate = __START_DATE__;
  const endDate = __END_DATE__;
  const period = typeof __PERIOD__ === 'string' ? __PERIOD__ : 'day';
  const dateType = { day: 1, week: 2, month: 3 }[period];
  if (!dateType) throw new Error('Invalid ranking period');
  const receiver = 'http://127.0.0.1:8768';
  const modules = [
    { name: '销量榜', prefix: 'sales', path: '/api/goods/saleRank', order: '1,2' },
    { name: '全托管商品榜', prefix: 'managed', path: '/api/goods/sShopHotList', order: '8,2' },
    { name: '热推榜', prefix: 'hot', path: '/api/goods/popRank', order: '4,2' },
  ];
  const startModule = typeof __START_MODULE__ === 'string' ? __START_MODULE__ : 'sales';
  const startPage = typeof __START_PAGE__ === 'number' ? __START_PAGE__ : 1;
  const startModuleIndex = modules.findIndex(config => config.prefix === startModule);
  if (startModuleIndex < 0 || !Number.isInteger(startPage) || startPage < 1) {
    throw new Error('Invalid rank collector starting module or page');
  }
  const state = {
    status: 'running', phase: 'rankings', period, startDate, endDate, startModule, startPage,
    currentDate: startDate, module: null, page: 0, lastSaved: null,
    requests: 0, batches: 0, datesComplete: 0, datesWithSourceEmpty: 0,
    sourceEmptyUnverified: [],
    startedAt: new Date().toISOString(), updatedAt: new Date().toISOString(),
    error: null, stopRequested: false,
    stop() { this.stopRequested = true; },
  };
  window.__fastmossRankCollector = state;
  const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
  const encode = value => encodeURIComponent(String(value))
    .replace(/%20/g, '+')
    .replace(/[!'()*~]/g, char => '%' + char.charCodeAt(0).toString(16).toUpperCase());

  async function report() {
    const progress = {
      status: state.status, phase: state.phase, period,
      start_date: startDate, end_date: endDate,
      start_module: startModule, start_page: startPage,
      current_date: state.currentDate, module: state.module,
      page: state.page, last_saved: state.lastSaved,
      requests: state.requests, batches: state.batches,
      dates_complete: state.datesComplete,
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

  async function sourcePage(config, day, page) {
    const params = {
      page, pagesize: 10, order: config.order, region: 'US',
      date_type: dateType, date_value: day,
      _time: Math.floor(Date.now() / 1000),
      cnonce: Math.floor(1e7 + 9e7 * Math.random()),
    };
    const signedQuery = Object.keys(params).sort()
      .map(key => `${key}=${encode(params[key])}`).join('&');
    const url = config.path + `?page=${page}&pagesize=10&order=${config.order}` +
      `&region=US&date_type=${dateType}&date_value=${day}` +
      `&_time=${params._time}&cnonce=${params.cnonce}`;
    const response = await fetch(url, {
      credentials: 'same-origin',
      headers: {
        Accept: 'application/json',
        'fm-sig': globalThis.__SIG__.gen(config.path + '?' + signedQuery, { source: 'pc' }),
        lang: 'ZH_CN', region: 'US', source: 'pc',
      },
    });
    const body = await response.json();
    state.requests++;
    state.page = page;
    state.updatedAt = new Date().toISOString();
    if (response.status !== 200 || body.code !== 200 ||
        !Array.isArray(body.data?.rank_list)) {
      throw new Error(`Source rejected ${config.name} ${day} p${page}: ` +
                      `HTTP ${response.status}, code ${body.code}`);
    }
    return { page, body };
  }

  async function sourcePageWithRetry(config, day, page) {
    let lastError;
    for (let attempt = 1; attempt <= 3; attempt++) {
      try { return await sourcePage(config, day, page); }
      catch (error) {
        lastError = error;
        if (/code MSG_SAFE_|verification|验证码/i.test(String(error))) break;
        if (attempt < 3) await wait(attempt * 2000);
      }
    }
    throw lastError;
  }

  async function saveBatch(config, day, pages) {
    const first = pages[0].page, last = pages[pages.length - 1].page;
    const filename = `FastMoss_US_${config.prefix}_${period}_${day}_p` +
      `${String(first).padStart(3, '0')}-${String(last).padStart(3, '0')}.json`;
    const payload = {
      filename, module: config.name, region: 'US',
      date_type: dateType, date_value: day,
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
    const dates = [];
    if (period === 'day') {
      for (let current = new Date(startDate + 'T00:00:00Z');
           current >= new Date(endDate + 'T00:00:00Z');
           current.setUTCDate(current.getUTCDate() - 1)) {
        dates.push(current.toISOString().slice(0, 10));
      }
    } else if (startDate === endDate) {
      dates.push(startDate);
    } else {
      throw new Error('Non-daily periods require one value');
    }
    for (const day of dates) {
      if (state.stopRequested) break;
      state.currentDate = day;
      let dayHasSourceEmpty = false;
      for (let moduleIndex = 0; moduleIndex < modules.length; moduleIndex++) {
        if (state.stopRequested) break;
        if (day === startDate && moduleIndex < startModuleIndex) continue;
        const config = modules[moduleIndex];
        state.module = config.name;
        state.page = 0;
        const firstPage = day === startDate && moduleIndex === startModuleIndex
          ? startPage : 1;
        const first = await sourcePageWithRetry(config, day, firstPage);
        const total = Number(first.body.data.total_count);
        if (!Number.isInteger(total) || total < 0 || total > 10000) {
          throw new Error(`Unexpected total ${config.name} ${day}: ${total}`);
        }
        if (total === 0) {
          if (firstPage !== 1 || first.body.data.rank_list.length !== 0) {
            throw new Error(`Unexpected page shape ${config.name} ${day} p${firstPage}`);
          }
          dayHasSourceEmpty = true;
          state.sourceEmptyUnverified.push({ date: day, module: config.name, page: firstPage });
          await saveBatch(config, day, [first]);
          continue;
        }
        const pageCount = Math.max(1, Math.ceil(total / 10));
        if (firstPage > pageCount) {
          throw new Error(`Start page ${firstPage} exceeds ${config.name} ${day} page count ${pageCount}`);
        }
        let batch = [];
        for (let page = firstPage; page <= pageCount; page++) {
          if (state.stopRequested) break;
          if (page > firstPage) await wait(600);
          const item = page === firstPage ? first : await sourcePageWithRetry(config, day, page);
          const rows = item.body.data.rank_list;
          if (Number(item.body.data.total_count) !== total || rows.length > 10 ||
              (rows.length === 0 && total > 0) ||
              (page < pageCount && rows.length !== 10)) {
            throw new Error(`Unexpected page shape ${config.name} ${day} p${page}`);
          }
          batch.push(item);
          if (batch.length === 5 || page === pageCount) {
            await saveBatch(config, day, batch);
            batch = [];
          }
        }
      }
      if (state.stopRequested) break;
      if (dayHasSourceEmpty) state.datesWithSourceEmpty++;
      else state.datesComplete++;
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
  return { status: 'started', period, startDate, endDate, startModule, startPage };
})()
