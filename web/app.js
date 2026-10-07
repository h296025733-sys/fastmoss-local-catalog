const MODULES = ['商品搜索', '销量榜', '新品榜', '全托管商品榜', '热推榜', '视频商品榜'];
const RANKING_DATE = '2026-09-29';
const utcToday = new Date();
utcToday.setUTCHours(0,0,0,0);
const daysBeforeToday = days => new Date(utcToday.getTime()-days*86400000).toISOString().slice(0,10);
const LAST_RANK_DATE = daysBeforeToday(1);
const NEW_DATE = daysBeforeToday(3);
const FIRST_DATE = '2026-03-30';
const lastWeekThursday = new Date(utcToday);
lastWeekThursday.setUTCDate(lastWeekThursday.getUTCDate()-(lastWeekThursday.getUTCDay()||7)-3);
const lastWeekYear = lastWeekThursday.getUTCFullYear();
const lastWeekNumber = Math.ceil(((lastWeekThursday-Date.UTC(lastWeekYear,0,1))/86400000+1)/7);
const LAST_WEEK = `${lastWeekYear}-W${String(lastWeekNumber).padStart(2,'0')}`;
const FIRST_WEEK = '2026-W14';
const LAST_MONTH = new Date(Date.UTC(utcToday.getUTCFullYear(),utcToday.getUTCMonth(),0)).toISOString().slice(0,7);
const FIRST_MONTH = '2026-03';
const COUNTRIES = ['全部','美国','印度尼西亚','英国','越南','泰国','马来西亚','菲律宾','西班牙','墨西哥','德国','法国','意大利','巴西','日本','新加坡','奥地利','比利时','荷兰','波兰','葡萄牙'];
const MANAGED_COUNTRIES = ['美国','英国','西班牙','墨西哥','德国','法国','意大利'];
const SITE_CATEGORIES = ['美妆个护','女装与女士内衣','保健','时尚配件','运动与户外','手机与数码','居家日用','食品饮料','汽车与摩托车','男装与男士内衣','收藏品','玩具和爱好','厨房用品','家装建材','电脑办公','箱包','鞋靴','五金工具','家纺布艺','家电','宠物用品','珠宝与衍生品','图书&杂志&音频','母婴用品','家具','儿童时尚','穆斯林时尚','二手','预订和优惠券','虚拟商品'];
const FINE_CATEGORY_MODULES = new Set(['销量榜','新品榜','全托管商品榜','热推榜']);
const SORT_LABELS = {rank:'原榜单排序','7d_sold':'近7天销量','7d_gmv':'近7天销售额',total_sold:'总销量',sold:'销量',gmv:'销售额',total_gmv:'总销售额',authors:'关联达人',views:'视频播放量'};
const NUMBER = new Intl.NumberFormat('zh-CN');
const BASE_PRESETS = [{label:'<500',max:499},{label:'500–1000',min:500,max:1000},{label:'1000–5000',min:1000,max:5000},{label:'5000–1万',min:5000,max:10000},{label:'1万–5万',min:10000,max:50000},{label:'>5万',min:50000}];
const MONEY_PRESETS = [{label:'<$500',max:499},{label:'$500–$1000',min:500,max:1000},{label:'$1000–$5000',min:1000,max:5000},{label:'$5000–$1万',min:5000,max:10000},{label:'$1万–$5万',min:10000,max:50000},{label:'>$5万',min:50000}];
const PERCENT_PRESETS = [{label:'<25%',max:24.99},{label:'25%–50%',min:25,max:50},{label:'50%–75%',min:50,max:75},{label:'75%–100%',min:75,max:100}];
const PRICE_PRESETS = [{label:'<$5',max:4.99},{label:'$5–$10',min:5,max:10},{label:'$10–$15',min:10,max:15},{label:'$15–$20',min:15,max:20},{label:'$20–$30',min:20,max:30},{label:'$30–$40',min:30,max:40},{label:'$40–$60',min:40,max:60},{label:'$60–$80',min:60,max:80},{label:'$80–$100',min:80,max:100},{label:'>$100',min:100}];
const RANGE_FIELDS = {
  order_rate:{label:'达人出单率',presets:PERCENT_PRESETS,unit:'%'},
  total_sold:{label:'总销量',presets:BASE_PRESETS},
  total_gmv:{label:'总GMV',presets:MONEY_PRESETS,unit:'$'},
  sold_7d:{label:'近7天销量',presets:BASE_PRESETS},
  gmv_7d:{label:'近7天GMV',presets:MONEY_PRESETS,unit:'$'},
  authors:{label:'带货达人数',presets:BASE_PRESETS},
  min_price:{label:'最低售价',presets:PRICE_PRESETS,unit:'$'},
  commission:{label:'佣金比例',presets:PERCENT_PRESETS,unit:'%'},
};
const TABLE_COLUMNS = {
  '商品搜索': [['商品','product'],['所属店铺','shop'],['达人出单率','12'],['近7天销量趋势','trend'],['近7天销量','7'],['近7天销售额','money:8'],['总销量','9'],['总销售额','money:10'],['关联达人','11'],['操作','action']],
  '销量榜': [['排名','rank'],['商品','product'],['国家/地区','region'],['所属店铺','shop'],['商品分类','category'],['佣金比例','7'],['销量','8'],['销量环比','9'],['销售额','money:12'],['总销量','10'],['总销售额','money:11'],['操作','action']],
  '新品榜': [['排名','rank'],['商品','product'],['国家/地区','region'],['所属店铺','shop'],['商品分类','category'],['佣金比例','9'],['三日销量','10'],['三日销售额','money:12'],['总销量','13'],['总销售额','api:total_sale_amount'],['操作','action']],
  '全托管商品榜': [['排名','rank'],['商品','product'],['国家/地区','region'],['所属店铺','shop'],['销量','5'],['环比增长','6'],['销售额','money:7'],['总销量','8'],['总销售额','money:9'],['操作','action']],
  '热推榜': [['排名','rank'],['商品','product'],['国家/地区','region'],['所属店铺','shop'],['商品分类','category'],['佣金比例','7'],['销量','8'],['销售额','money:9'],['关联达人','10'],['总关联达人','11'],['操作','action']],
  '视频商品榜': [['带货商品','product'],['视频内容','video'],['总销量','8'],['总销售额','money:9'],['总播放量','10'],['总点赞数','11'],['总评论数','api:comment_count'],['操作','action']],
};

const initial = new URLSearchParams(location.search);
const state = {
  module: MODULES.includes(initial.get('module')) ? initial.get('module') : '商品搜索',
  page: Math.max(1, Number(initial.get('page')) || 1), pageSize:10,
  category:'', categoryLevel:'fine', categoriesExpanded:false, fineCategoriesExpanded:false, fineCategoriesOpen:false, countriesExpanded:false,
  q:'', sort:'rank', launchStart:'', launchEnd:'', ranges:{}, openRange:'',
  period:initial.get('period')||'day', rankingDate:initial.get('date')||LAST_RANK_DATE,
  videoDays:Number(initial.get('video_days'))||7, managed:'', storeType:'', freeShipping:false,
};
if(state.module==='新品榜'){
  state.launchStart=initial.get('launch_start')||NEW_DATE;
  state.launchEnd=initial.get('launch_end')||NEW_DATE;
}else if(state.module==='商品搜索'){
  state.launchStart=initial.get('launch_start')||FIRST_DATE;
  state.launchEnd=initial.get('launch_end')||RANKING_DATE;
}
let current = null;
let status = null;
let requestSerial = 0;
const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const safeUrl = value => {try{const url=new URL(value,location.origin);return (url.protocol==='https:' || (url.origin===location.origin && url.pathname.startsWith('/media/')))?url.href:''}catch{return ''}};
const pretty = value => value===null || value===undefined || value==='' ? '—' : typeof value==='number' ? NUMBER.format(value) : String(value);
const rankMetric = value => {
  if(value===null || value===undefined || value==='')return '—';
  const numeric=Number(value);
  if(!Number.isFinite(numeric))return String(value);
  if(Math.abs(numeric)>=100000000)return `${(Math.trunc(numeric/1000000)/100).toFixed(2)}亿`;
  if(Math.abs(numeric)>=10000)return `${(Math.trunc(numeric/100)/100).toFixed(2)}万`;
  return String(value);
};
const knownCaptureIncident = data => data?.module==='热推榜' && data.coverage==='not_collected' &&
  state.module==='热推榜' && state.period==='day' && state.rankingDate==='2026-09-19';
const filterRow = (label, html, extra='') => `<div class="filter-row ${extra}"><span class="filter-label">${esc(label)}：</span><div class="filter-options">${html}</div></div>`;
const chip = (label, active=false, disabled=false, attrs='') => `<button type="button" class="chip ${active?'active':''}" ${disabled?'disabled title="此条件尚未采集"':''} ${attrs}>${esc(label)}</button>`;

function renderNav(){
  $('module-nav').innerHTML = MODULES.map(module=>`<button type="button" data-module="${module}" class="${module===state.module?'active':''}">${module}</button>`).join('');
  $('page-title').textContent = `TikTok 美国 ${state.module}`;
  const coverage=current?.coverage;
  $('snapshot-note').textContent = knownCaptureIncident(current)?'原站第 3 页异常 · 待补':
    coverage==='not_collected'?'该日期尚未采集':
    coverage==='source_empty_unverified'?'原站空榜响应 · 待核对':
    coverage==='partial'?`已采 ${current.captured_pages||0} 页 · ${current.captured_rows||0}/${current.source_total||'?'} 条`:
    coverage==='pages_complete_with_duplicates'?`已采齐页码 · ${current.duplicate_ids||0} 个重复 ID`:
    coverage==='pages_complete_no_duplicates'?'已采齐页码 · 无重复 ID':
    coverage==='reconciled_export'?'整段导出已校对':
    coverage==='export_snapshot'?`原站导出快照 · ${NUMBER.format(current?.total||0)} 条`:
    `本地快照 · ${NUMBER.format(current?.total||status?.modules[state.module]?.rows||0)} 条`;
  $('snapshot-note').title=coverage==='export_snapshot'?'售价等字段保留导出时的原值，可能与原站当前页面不同':'';
}
function sortedCategories(categories){
  return [...categories].sort((a,b)=>{
    const ai=SITE_CATEGORIES.indexOf(a), bi=SITE_CATEGORIES.indexOf(b);
    if(ai>=0 && bi>=0)return ai-bi;
    if(ai>=0)return -1;
    if(bi>=0)return 1;
    return a.localeCompare(b,'zh-CN');
  });
}
function renderCountries(){
  return chip('美国',true)+ '<span class="filter-note">范围：美国</span>';
}
function renderCategories(categories){
  const fine=FINE_CATEGORY_MODULES.has(state.module);
  const majorAvailable=Boolean(current?.capabilities?.major_category);
  const available=new Set(categories);
  const visible=state.categoriesExpanded ? SITE_CATEGORIES : SITE_CATEGORIES.slice(0,12);
  const fineCount=(current?.fine_categories||categories).length;
  const fineToggle=fine&&!majorAvailable&&current?.coverage!=='not_collected'?
    chip(state.fineCategoriesOpen?'收起细分类':`细分类 ${fineCount} 类`,false,false,'data-toggle-fine-panel="1"'):'';
  return '<div class="chips '+(state.categoriesExpanded?'expanded':'')+'">'+
    chip('全部',!state.category,'', 'data-category=""')+
    visible.map(category=>chip(category,category===state.category,(fine&&!majorAvailable)||!available.has(category),
      ((fine||majorAvailable)?`data-major-category="${esc(category)}"`:`data-category="${esc(category)}"`))).join('')+
    chip(state.categoriesExpanded?'收起':'展开',false,false,'data-toggle-categories="1"')+fineToggle+'</div>';
}
function renderFineCategories(categories){
  const ordered=sortedCategories(categories);
  const visible=state.fineCategoriesExpanded ? ordered : ordered.slice(0,14);
  if(state.category && !visible.includes(state.category))visible.push(state.category);
  const label=ordered.length>14?chip(state.fineCategoriesExpanded?'收起':`展开全部 ${ordered.length} 类`,false,false,'data-toggle-fine-categories="1"'):'';
  return '<div class="chips '+(state.fineCategoriesExpanded?'expanded':'')+'">'+
    chip('全部',state.category==='','', 'data-category=""')+
    visible.map(category=>chip(category,category===state.category,false,`data-category="${esc(category)}"`)).join('')+label+'</div>';
}
function rangeSummary(key){
  const range=state.ranges[key];
  if(!range)return '全部';
  const config=RANGE_FIELDS[key], unit=config.unit||'';
  if(range.label)return range.label;
  return `${range.min===''?'不限':unit+range.min}–${range.max===''?'不限':unit+range.max}`;
}
function renderRangePanel(){
  const key=state.openRange;
  if(!key)return '';
  const config=RANGE_FIELDS[key], range=state.ranges[key]||{min:'',max:''};
  return `<div class="range-panel"><strong>${config.label}</strong><div class="range-presets">${chip('全部',!state.ranges[key],false,'data-range-reset="'+key+'"')}${config.presets.map((preset,index)=>chip(preset.label,range.label===preset.label,false,`data-range-preset="${key}" data-preset-index="${index}"`)).join('')}</div><div class="range-custom"><label>最小值 <input id="range-min" type="number" min="0" step="any" value="${esc(range.min??'')}"></label><span>—</span><label>最大值 <input id="range-max" type="number" min="0" step="any" value="${esc(range.max??'')}"></label><button type="button" class="apply-button" data-range-apply="${key}">确认</button><button type="button" class="plain-button" data-range-close="1">关闭</button></div><div id="range-error" class="range-error" aria-live="polite"></div></div>`;
}
function renderManagedFilter(){
  if(!current?.capabilities?.is_sshop)
    return '<span class="range-trigger unavailable" title="此快照缺少全托管店标记">是否为全托管店：未采集</span>';
  const unknown=current?.unknown_fields?.is_sshop||0;
  return `<label class="select-filter">是否为全托管店：<select data-managed="1"><option value="" ${!state.managed?'selected':''}>全部</option><option value="1" ${state.managed==='1'?'selected':''}>是</option><option value="0" ${state.managed==='0'?'selected':''}>否</option></select></label>${unknown?`<span class="filter-note">${unknown} 条无此标记</span>`:''}`;
}
function renderFilters(categories){
  const coverage=current?.coverage||'not_collected';
  const coverageText=knownCaptureIncident(current)?'2026-09-19 美国热推榜第 3 页在原站返回 0 条，而相邻页有数据；该日完整快照未保存，待补采。':
    coverage==='not_collected'?'当前日期或周期尚未采集；切换到已采集日期可查看数据。':
    coverage==='source_empty_unverified'?'原站第一页返回 0 条；尚未确认榜单为空，不能将这一天标为采齐。待补采与核对。':
    coverage==='partial'?`原站显示 ${current.source_total||'?'} 条，已保存 ${current.captured_rows||0} 条；短页：${(current.short_pages||[]).map(p=>`${p.page} 页 ${p.rows} 条`).join('、')||'采集仍未完成'}。${current.duplicate_ids?`另有 ${current.duplicate_ids} 个重复 ID。`:''}`:
    coverage==='pages_complete_with_duplicates'?`页码已采齐，但有 ${current.duplicate_ids||0} 个重复 ID；可能漏项，待核对。`:
    coverage==='pages_complete_no_duplicates'?'原站页码与返回条数已采齐，商品 ID 无重复；尚未用独立整段导出核对。':
    coverage==='reconciled_export'?'此日期已采齐页码，并用原站整段导出核对了商品 ID。':
    '本地快照；仅展示已保存的原站数据。';
  const needsNote=['not_collected','source_empty_unverified','partial','pages_complete_with_duplicates'].includes(coverage);
  let html=needsNote?`<div class="coverage-note">${coverageText} 国家仅美国；日榜从 ${FIRST_DATE} 起，月榜保留 2026 年 3 月整月。</div>`:'';
  if(current?.subset_of_capture)html+='<div class="coverage-note">当前日期条件仅在已保存的 5,000 条商品中筛选；原站在此条件下可能还有其他商品，结果不等于原站完整搜索结果。</div>';
  if(['商品搜索','视频商品榜'].includes(state.module)){
    html+=`<div class="module-search"><input id="module-search" aria-label="商品搜索" placeholder="商品搜索" value="${esc(state.q)}"><button type="button" data-module-search="1" class="search-button">搜索</button><button type="button" disabled title="翻译未采集">翻译</button>${state.module==='商品搜索'?'<button type="button" disabled title="图搜同款未接通">图搜同款</button>':''}</div>`;
  }
  if(['销量榜','全托管商品榜','热推榜'].includes(state.module)){
    const kind=state.period==='week'?'week':state.period==='month'?'month':'date';
    const value=state.period==='week'?state.rankingDate.replace(/-(\d{2})$/,'-W$1'):state.rankingDate;
    const min=state.period==='week'?FIRST_WEEK:state.period==='month'?FIRST_MONTH:FIRST_DATE;
    const max=state.period==='week'?LAST_WEEK:state.period==='month'?LAST_MONTH:LAST_RANK_DATE;
    html+=filterRow('时间筛选',chip('日',state.period==='day',false,'data-period="day"')+
      chip('周',state.period==='week',false,'data-period="week"')+
      chip('月',state.period==='month',false,'data-period="month"')+
      `<input type="${kind}" data-ranking-date="1" value="${esc(value)}" min="${min}" max="${max}" aria-label="榜单日期"><span class="filter-note">${state.period==='day'?'日榜':state.period==='week'?'周榜':'月榜'} · ${esc(state.rankingDate)}</span>`);
  }else if(state.module==='新品榜'){
    html+=filterRow('上架时间',`<input type="date" data-launch="start" value="${esc(state.launchStart||NEW_DATE)}" min="${FIRST_DATE}" max="${NEW_DATE}" aria-label="上架开始日期"><span>至</span><input type="date" data-launch="end" value="${esc(state.launchEnd||NEW_DATE)}" min="${FIRST_DATE}" max="${NEW_DATE}" aria-label="上架结束日期">`);
  }
  html+=filterRow('国家/地区',renderCountries());
  html+=filterRow('商品分类',renderCategories(categories),'category-row');
  if(state.fineCategoriesOpen&&FINE_CATEGORY_MODULES.has(state.module)&&!current?.capabilities?.major_category&&coverage!=='not_collected')
    html+=filterRow('本地细分类',renderFineCategories(current?.fine_categories||categories));
  if(['商品搜索','销量榜','新品榜','热推榜'].includes(state.module)){
    const canStore=Boolean(current?.capabilities?.is_cross_border);
    html+=filterRow('店铺类型',chip('全部',!state.storeType,false,'data-store-type=""')+
      chip('跨境店',state.storeType==='cross',!canStore,'data-store-type="cross"')+
      chip('本土店',state.storeType==='local',!canStore,'data-store-type="local"')+
      (!canStore?'<span class="filter-note">此快照缺少店铺类型字段</span>':''));
  }
  if(state.module==='商品搜索'){
    html+=filterRow('商品类型',['上新商品','包邮商品','本地仓商品','爆款商品'].map(x=>`<label class="disabled-check"><input type="checkbox" ${x==='包邮商品'&&current?.capabilities?.is_free_shipping?'data-free-shipping="1"'+(state.freeShipping?' checked':''):'disabled'}>${x}</label>`).join(''));
    html+=filterRow('商品状态',chip('全部',false,true)+chip('在售',true)+chip('下架',false,true)+'<span class="filter-note">本次只采集在售商品</span>');
    const datesReady=status?.features?.search_subset_dates===true;
    html+=filterRow('上架时间',`<input type="date" data-launch="start" aria-label="上架开始日期" min="${FIRST_DATE}" max="${RANKING_DATE}" value="${esc(state.launchStart)}" ${datesReady?'':'disabled title="本地预览服务更新后可用"'}><span>至</span><input type="date" data-launch="end" aria-label="上架结束日期" min="${FIRST_DATE}" max="${RANKING_DATE}" value="${esc(state.launchEnd)}" ${datesReady?'':'disabled title="本地预览服务更新后可用"'}>${datesReady?'':'<span class="filter-note">待服务更新</span>'}`);
    html+=filterRow('筛选条件',Object.entries(RANGE_FIELDS).map(([key,config])=>{
      const ready=!['min_price','order_rate','commission'].includes(key)||status?.features?.numeric_ranges_v2===true;
      return `<button type="button" class="range-trigger ${state.ranges[key]?'selected':''}" ${ready?`data-range-open="${key}"`:'disabled title="本地预览服务更新后可用"'}>${config.label}：${ready?esc(rangeSummary(key)):'待服务更新'}</button>`;
    }).join('')+
      `<span class="range-trigger unavailable" title="此快照缺少带货方式字段">带货方式：未采集</span>`+
      renderManagedFilter());
    html+=renderRangePanel();
  }else if(['销量榜','新品榜','热推榜'].includes(state.module)){
    html+=filterRow('筛选条件',renderManagedFilter());
  }else if(state.module==='视频商品榜'){
    html+=filterRow('视频发布时间',[7,28,90].map(days=>chip(`近${days}天`,state.videoDays===days,false,`data-video-days="${days}"`)).join(''));
  }
  $('page-size-control').innerHTML='<span>每页</span>'+[10,20,50].map(size=>chip(`${size}`,size===state.pageSize,false,`data-size="${size}"`)).join('');
  if(state.module==='视频商品榜'&&state.videoDays===7)html+='<div class="coverage-alert">原始近 7 天导出在第 2998 / 3001 名出现同一商品与视频，交界漏项待核对。</div>';
  $('module-filters').innerHTML=html;
  const active=['国家/地区：美国'];
  if(state.category)active.push((state.categoryLevel==='major'?'商品分类：':'本地细分类：')+state.category);
  if(['销量榜','全托管商品榜','热推榜'].includes(state.module))active.push('时间：'+state.period+' '+state.rankingDate);
  if(state.module==='视频商品榜')active.push('视频发布时间：近'+state.videoDays+'天');
  if(state.managed)active.push('全托管店：'+(state.managed==='1'?'是':'否'));
  if(state.q)active.push('搜索：'+state.q);
  if(state.launchStart||state.launchEnd)active.push('上架时间：'+(state.launchStart||'不限')+' 至 '+(state.launchEnd||'不限'));
  for(const key of Object.keys(state.ranges))active.push(RANGE_FIELDS[key].label+'：'+rangeSummary(key));
  $('active-filters').textContent=active.join(' · ');
}
function renderSort(options){
  $('sort-select').innerHTML=options.map(key=>`<option value="${key}">${esc(SORT_LABELS[key]||key)}</option>`).join('');
  $('sort-select').value=state.sort;
}
function productCell(item){
  const image=safeUrl(item.image_url);
  const thumb=image?`<img class="thumb" src="${esc(image)}" alt="" loading="lazy">`:'<div class="no-thumb">暂无图片</div>';
  const launchDate=item.launch_date||String(item.raw_values?.[15]||'').slice(0,10);
  const fields=item.api_fields||{};
  const rating=Number(fields.product_rating);
  const searchMeta=state.module==='商品搜索'?
    `<div class="product-meta search-product-meta"><span class="price">售价：${esc(pretty(item.price))}</span>${fields.is_free_shipping===1?'<span class="shipping-tag" title="包邮商品">🚚</span>':''}</div>`+
    `<div class="product-meta search-product-meta"><span>🇺🇸</span><span>${esc(item.category||'')}</span>${Number.isFinite(rating)&&rating>0?`<span class="rating-tag">${esc(rating)}</span>`:''}</div>`+
    (fields.crate_show||fields.crate?`<div class="product-meta search-product-meta"><span>佣金比例：${esc(fields.crate_show||fields.crate)}</span></div>`:''):'';
  const meta=state.module==='商品搜索'?searchMeta:state.module==='新品榜'?
    `<div class="product-meta new-product-meta"><span class="price">售价：${esc(pretty(item.price))}</span>${launchDate?`<span>上架时间：${esc(launchDate)}</span>`:''}</div>`:
    `<div class="product-meta"><span class="price">售价：${esc(pretty(item.price))}</span>${state.module==='热推榜'?'':`<span>${esc(item.category||'')}</span>`}</div>`;
  return `<div class="product">${thumb}<div class="product-main"><button class="product-title" type="button" data-detail-rank="${item.rank}" title="${esc(item.title)}">${esc(item.title)}</button>${meta}</div></div>`;
}
function cellContent(item,key){
  if(key==='rank')return `<span class="rank ${item.rank<=3?'rank-medal rank-'+item.rank:''}">${NUMBER.format(item.rank)}</span>`;
  if(key==='product')return productCell(item);
  if(key==='region')return '🇺🇸 美国';
  if(key==='category')return `<span class="category-badge">${esc(item.category||'—')}</span>`;
  if(key==='shop'){
    const logo=safeUrl(item.shop_logo);
    const shopInfo=item.api_fields?.shop_info||{};
    const missingAtSource=Boolean(item.api_fields?.shop_info)&&!shopInfo.avatar_oss&&!item.shop_logo;
    const missingLogoText=missingAtSource?'原站响应未提供店铺头像':'此快照未保存店铺头像';
    const shopSales=['商品搜索','销量榜','新品榜','全托管商品榜','热推榜'].includes(state.module)?
      (shopInfo.sold_count_show??shopInfo.sold_count??
        (state.module==='销量榜'?item.raw_values?.[14]:
         state.module==='新品榜'?item.raw_values?.[7]:
         state.module==='热推榜'?item.raw_values?.[5]:null)):null;
    const salesLine=shopSales!==null&&shopSales!==undefined&&shopSales!==''?`<small>店铺销量：${esc(rankMetric(shopSales))}</small>`:'';
    const avatar=logo?`<img class="shop-logo" src="${esc(logo)}" alt="" loading="lazy">`:
      `<span class="shop-logo-placeholder" title="${missingLogoText}" aria-label="${missingLogoText}">—</span>`;
    return `<span class="shop-with-logo">${avatar}<span class="shop-copy"><span>${esc(item.shop||'—')}</span>${salesLine}</span></span>`;
  }
  if(key==='video'){
    const values=item.raw_values||[], video=item.api_fields?.video_list?.[0]||{};
    const cover=safeUrl(item.video_cover||video.cover), avatar=safeUrl(item.video_author_avatar||video.author_avatar);
    const derived=video.video_id&&video.author_unique_id&&/^\d+$/.test(String(video.video_id))?
      `https://www.tiktok.com/@${encodeURIComponent(video.author_unique_id)}/video/${video.video_id}`:'';
    const link=safeUrl(values[7]||derived), description=esc(video.video_desc||values[4]||'暂无视频描述');
    const author=esc(video.author_nickname||'');
    return `<div class="video-cell">${cover?`<img class="video-cover" src="${esc(cover)}" alt="视频封面" loading="lazy">`:''}<div class="video-copy">${link?`<a href="${esc(link)}" target="_blank" rel="noopener noreferrer">${description}</a>`:`<span class="video-description">${description}</span>`}${author?`<span class="video-author">${avatar?`<img class="video-author-avatar" src="${esc(avatar)}" alt="" loading="lazy">`:''}${author}</span>`:''}<small>视频播放量：${esc(pretty(video.play_count??values[5]))}　视频销量：${esc(pretty(video.sold_count??values[6]))}</small></div></div>`;
  }
  if(key==='action')return `<button type="button" class="detail-action" data-detail-rank="${item.rank}">查看详情</button>`;
  if(key==='missing')return '<span class="unavailable-value" title="该字段未包含在本次导出中">—</span>';
  if(key==='trend'){
    const trend=item.api_fields?.trend||[];
    if(!trend.length)return '<span class="unavailable-value">—</span>';
    const vals=trend.map(entry=>Number(entry.inc_sold_count)||0),max=Math.max(...vals,1);
    const points=vals.map((v,i)=>`${Math.round(i*96/Math.max(vals.length-1,1))},${Math.round(29-v/max*25)}`).join(' ');
    const first=points.split(' ')[0],last=points.split(' ').at(-1);
    return `<svg class="sparkline" viewBox="0 0 96 32" role="img" aria-label="近7天销量趋势：${esc(vals.join('、'))}"><polygon points="${first} ${points} ${last.split(',')[0]},32 0,32" fill="#ffe7f0"/><polyline points="${points}" fill="none" stroke="#f72472" stroke-width="1.8" stroke-linejoin="round" stroke-linecap="round"/></svg>`;
  }
  if(state.module==='新品榜'&&key==='api:total_sale_amount'){
    const shown=item.api_fields?.total_sale_amount_show;
    if(shown!==null&&shown!==undefined&&shown!=='')return esc(String(shown));
    const raw=item.api_fields?.total_sale_amount;
    return raw!==null&&raw!==undefined?esc('$'+rankMetric(raw)):
      '<span class="unavailable-value" title="本次原站导出未包含总销售额">—</span>';
  }
  if(key.startsWith('api:'))return esc(pretty(item.api_fields?.[key.slice(4)]));
  const values=item.raw_values||[], money=key.startsWith('money:'), index=Number(money?key.slice(6):key);
  const value=values[index];
  if((state.module==='销量榜'||state.module==='全托管商品榜')&&(money||key==='8'||key==='10'||key==='5')){
    const showField=state.module==='销量榜'?
      {'8':'sold_count_show','10':'total_sold_count_show','money:12':'sale_amount_show','money:11':'total_sale_amount_show'}[key]:
      {'5':'sold_count_show','8':'total_sold_count_show','money:7':'sale_amount_show','money:9':'total_sale_amount_show'}[key];
    const shown=item.api_fields?.[showField];
    if(shown!==null&&shown!==undefined&&shown!=='')return esc(String(shown));
    return esc((money&&value!==null&&value!==undefined&&value!==''?'$':'')+rankMetric(value));
  }
  if(state.module==='热推榜'&&(money||['8','10','11'].includes(key))){
    const showField={'8':'sold_count_show','money:9':'sale_amount_show','10':'author_count_show','11':'total_author_count_show'}[key];
    const shown=item.api_fields?.[showField];
    if(shown!==null&&shown!==undefined&&shown!=='')return esc(String(shown));
    return esc((money&&value!==null&&value!==undefined&&value!==''?'$':'')+rankMetric(value));
  }
  if(state.module==='新品榜'&&(money||key==='10'||key==='13')){
    const showField={'10':'sold_count_show','money:12':'sale_amount_show','13':'total_sold_count_show'}[key];
    const shown=item.api_fields?.[showField];
    if(shown!==null&&shown!==undefined&&shown!=='')return esc(String(shown));
    return esc((money&&value!==null&&value!==undefined&&value!==''?'$':'')+rankMetric(value));
  }
  if(state.module==='商品搜索'){
    const showField={'12':'author_order_rate_show','7':'day7_sold_count_show','money:8':'day7_sale_amount_show','9':'sold_count_show','money:10':'sale_amount_show','11':'relate_author_count_show'}[key];
    const shown=item.api_fields?.[showField];
    if(shown!==null&&shown!==undefined&&shown!=='')return esc(String(shown));
    if(showField)return esc((money&&value!==null&&value!==undefined&&value!==''?'$':'')+rankMetric(value));
  }
  return esc((money&&value!==null&&value!==undefined&&value!==''?'$':'')+pretty(value));
}
function renderTable(data){
  const columns=TABLE_COLUMNS[state.module];
  $('table-head').innerHTML='<tr>'+columns.map(([label])=>`<th>${esc(label)}</th>`).join('')+'</tr>';
  $('table-body').innerHTML=data.items.map(item=>'<tr>'+columns.map(([label,key])=>`<td class="${key==='product'?'product-cell':key==='shop'?'shop-cell':key==='video'?'video-col':''}" data-label="${esc(label)}">${cellContent(item,key)}</td>`).join('')+'</tr>').join('');
  $('result-count').textContent=knownCaptureIncident(data)?'原站空页 · 该日未采齐':
    data.coverage==='not_collected'?'该日期尚未采集':
    data.coverage==='source_empty_unverified'?'原站空榜响应 · 待核对':
    `${NUMBER.format(data.total)} 条${state.module==='商品搜索'?'已采商品':'商品'}记录`;
  $('result-hint').textContent=['not_collected','source_empty_unverified'].includes(data.coverage)?'':
    `第 ${NUMBER.format(data.page)} / ${NUMBER.format(data.pages||1)} 页`+
    (state.module==='新品榜'&&data.coverage==='export_snapshot'?' · 原始导出不含总销售额':'');
  $('empty').textContent=knownCaptureIncident(data)?'原站第 3 页返回空页，该日热推榜尚未取得完整数据。':
    data.coverage==='not_collected'?'该日期或周期没有本地数据；采集后会显示在这里。':
    data.coverage==='source_empty_unverified'?'原站第一页返回 0 条；不能据此认定该日热推榜为空。':'此筛选条件下没有已采集的商品。';
  $('empty').hidden=data.items.length>0;
  $('page-summary').textContent=data.total?`${NUMBER.format((data.page-1)*data.page_size+1)}–${NUMBER.format(Math.min(data.page*data.page_size,data.total))} / ${NUMBER.format(data.total)}`:'0 条';
  renderPagination(data.page,data.pages);
  $('export-csv').disabled=['not_collected','source_empty_unverified'].includes(data.coverage);
}
function renderPagination(page,pages){
  const buttons=[];
  const add=(label,target,active=false,disabled=false)=>buttons.push(`<button type="button" class="page-button ${active?'active':''}" data-page="${target}" ${disabled?'disabled':''}>${label}</button>`);
  add('‹',page-1,false,page<=1);
  const indexes=new Set([1,pages,page-2,page-1,page,page+1,page+2].filter(x=>x>=1&&x<=pages));
  let previous=0;
  for(const index of [...indexes].sort((a,b)=>a-b)){if(previous&&index-previous>1)buttons.push('<span>…</span>');add(index,index,index===page);previous=index}
  add('›',page+1,false,page>=pages);
  $('page-controls').innerHTML=buttons.join('');
  $('jump-page').value='';$('jump-page').max=String(pages);
}
function buildParams(){
  const params=new URLSearchParams({module:state.module,page:String(state.page),page_size:String(state.pageSize),sort:state.sort});
  if(state.q)params.set('q',state.q);
  if(state.category)params.set(state.categoryLevel==='major'?'major_category':'category',state.category);
  if(['销量榜','全托管商品榜','热推榜'].includes(state.module)){
    params.set('period',state.period);params.set('date',state.rankingDate);
  }
  if(state.module==='视频商品榜')params.set('video_days',String(state.videoDays));
  if(state.managed)params.set('is_sshop',state.managed);
  if(state.storeType)params.set('store_type',state.storeType);
  if(state.freeShipping)params.set('free_shipping','1');
  if(['商品搜索','新品榜'].includes(state.module)){
    if(state.launchStart)params.set('launch_start',state.launchStart);
    if(state.launchEnd)params.set('launch_end',state.launchEnd);
  }
  if(state.module==='商品搜索'){
    for(const [key,range] of Object.entries(state.ranges)){
      if(range.min!=='' && range.min!==undefined)params.set(`r_${key}_min`,String(range.min));
      if(range.max!=='' && range.max!==undefined)params.set(`r_${key}_max`,String(range.max));
    }
  }
  return params;
}
function syncUrl(){
  const params=new URLSearchParams({module:state.module});
  if(state.page>1)params.set('page',String(state.page));
  if(['销量榜','全托管商品榜','热推榜'].includes(state.module)){
    params.set('period',state.period);params.set('date',state.rankingDate);
  }
  if(state.module==='新品榜'||state.module==='商品搜索'){
    if(state.launchStart)params.set('launch_start',state.launchStart);
    if(state.launchEnd)params.set('launch_end',state.launchEnd);
  }
  if(state.module==='视频商品榜')params.set('video_days',String(state.videoDays));
  history.replaceState(null,'',`/?${params}`);
}
async function loadList(){
  const serial=++requestSerial;
  $('loading').hidden=false;$('empty').hidden=true;renderNav();syncUrl();
  try{
    const response=await fetch('/api/list?'+buildParams());
    const data=await response.json();
    if(!response.ok)throw Error(data.error||`HTTP ${response.status}`);
    if(serial!==requestSerial)return;
    if(state.page>data.pages&&data.pages>0){state.page=data.pages;return loadList()}
    current=data;renderNav();renderFilters(data.categories);renderSort(data.sort_options);renderTable(data);
  }catch(error){if(serial===requestSerial){$('table-body').innerHTML='';$('empty').textContent=`读取失败：${error.message}`;$('empty').hidden=false}}
  finally{if(serial===requestSerial)$('loading').hidden=true}
}
async function openDetail(rank){
  $('detail-overlay').hidden=false;$('detail-content').innerHTML='<div class="loading">正在读取商品详情…</div>';
  try{
    const params=buildParams();params.set('rank',String(rank));
    const response=await fetch('/api/detail?'+params), data=await response.json();
    if(!response.ok)throw Error(data.error||`HTTP ${response.status}`);
    const item=data.item, image=safeUrl(item.image_url), source=safeUrl(item.detail_url);
    const gallery=(data.gallery||[]).map(entry=>safeUrl(entry.image_url)).filter(Boolean);
    const photos=gallery.length?gallery:(image?[image]:[]), mainPhoto=photos[0]||image;
    $('detail-content').innerHTML=`<div class="detail-header">${mainPhoto?`<img id="detail-main-photo" src="${esc(mainPhoto)}" alt="商品图片">`:''}<div><h2 id="detail-title">${esc(item.title)}</h2><p>售价：${esc(pretty(item.price))}　 · 　${esc(item.category||'未分类')}</p><p>店铺：${esc(item.shop||'—')}　 · 　商品 ID：${esc(item.product_id||'待核对')}</p><p>本地榜单：${esc(item.module)} 第 ${item.rank} 名</p>${source?`<a class="detail-link" href="${esc(source)}" target="_blank" rel="noopener noreferrer">查看原站商品详情 ↗</a>`:''}</div></div>${photos.length>1?`<div class="detail-gallery">${photos.map((photo,index)=>`<button class="gallery-thumb ${index===0?'active':''}" data-gallery-src="${esc(photo)}" aria-label="查看第 ${index+1} 张图片"><img src="${esc(photo)}" alt=""></button>`).join('')}</div>`:''}<div class="detail-section"><h3>当前快照中的榜单位置</h3>${data.appearances.map(entry=>`<span class="appearance">${esc(entry.module)} · ${entry.rank} 名</span>`).join('')}</div><div class="detail-section"><h3>已保存字段</h3><div class="detail-grid">${data.fields.map(field=>`<div>${esc(field.label)}</div><div>${esc(pretty(field.value))}</div>`).join('')}</div></div>`;
    if(data.gallery_unavailable){const note=document.createElement('p');note.className='gallery-warning';note.textContent=`${data.gallery_unavailable} 张原站详情图已失效`;($('detail-content').querySelector('.detail-gallery')||$('detail-content').querySelector('.detail-header')).after(note)}
  }catch(error){$('detail-content').textContent='详情读取失败：'+error.message}
}
function closeDetail(){$('detail-overlay').hidden=true;$('detail-content').innerHTML=''}
function resetFilters(){state.category='';state.categoryLevel='fine';state.q='';state.sort='rank';state.launchStart=state.module==='新品榜'?NEW_DATE:state.module==='商品搜索'?FIRST_DATE:'';state.launchEnd=state.module==='新品榜'?NEW_DATE:state.module==='商品搜索'?RANKING_DATE:'';state.ranges={};state.openRange='';state.period='day';state.rankingDate=LAST_RANK_DATE;state.videoDays=7;state.managed='';state.storeType='';state.freeShipping=false;state.page=1;$('global-search').value=''}
function applySearch(){state.q=($('module-search')?.value??$('global-search').value).trim();$('global-search').value=state.q;state.page=1;loadList()}

$('module-nav').addEventListener('click',event=>{const module=event.target.closest('[data-module]')?.dataset.module;if(!module)return;state.module=module;state.categoriesExpanded=false;state.fineCategoriesExpanded=false;state.fineCategoriesOpen=false;state.countriesExpanded=false;resetFilters();loadList();window.scrollTo({top:0})});
$('module-filters').addEventListener('click',event=>{
  const target=event.target;
  if(target.closest('[data-toggle-countries]')){state.countriesExpanded=!state.countriesExpanded;renderFilters(current?.categories||[]);return}
  if(target.closest('[data-toggle-categories]')){state.categoriesExpanded=!state.categoriesExpanded;renderFilters(current?.categories||[]);return}
  if(target.closest('[data-toggle-fine-panel]')){state.fineCategoriesOpen=!state.fineCategoriesOpen;renderFilters(current?.categories||[]);return}
  if(target.closest('[data-toggle-fine-categories]')){state.fineCategoriesExpanded=!state.fineCategoriesExpanded;renderFilters(current?.categories||[]);return}
  const period=target.closest('[data-period]');if(period){state.period=period.dataset.period;state.rankingDate=state.period==='week'?LAST_WEEK.replace('-W','-'):state.period==='month'?LAST_MONTH:LAST_RANK_DATE;state.page=1;loadList();return}
  const video=target.closest('[data-video-days]');if(video){state.videoDays=Number(video.dataset.videoDays);state.page=1;loadList();return}
  const store=target.closest('[data-store-type]');if(store){state.storeType=store.dataset.storeType;state.page=1;loadList();return}
  const major=target.closest('[data-major-category]');if(major){state.category=major.dataset.majorCategory;state.categoryLevel='major';state.page=1;loadList();return}
  const category=target.closest('[data-category]');if(category){state.category=category.dataset.category;state.categoryLevel='fine';state.page=1;loadList();return}
  if(target.closest('[data-module-search]')){applySearch();return}
  const opener=target.closest('[data-range-open]');if(opener){state.openRange=state.openRange===opener.dataset.rangeOpen?'':opener.dataset.rangeOpen;renderFilters(current?.categories||[]);return}
  if(target.closest('[data-range-close]')){state.openRange='';renderFilters(current?.categories||[]);return}
  const preset=target.closest('[data-range-preset]');if(preset){const key=preset.dataset.rangePreset, choice=RANGE_FIELDS[key].presets[Number(preset.dataset.presetIndex)];state.ranges[key]={min:choice.min??'',max:choice.max??'',label:choice.label};state.openRange='';state.page=1;loadList();return}
  const reset=target.closest('[data-range-reset]');if(reset){delete state.ranges[reset.dataset.rangeReset];state.openRange='';state.page=1;loadList();return}
  const apply=target.closest('[data-range-apply]');if(apply){const min=$('range-min').value,max=$('range-max').value;if((min!==''&&(!Number.isFinite(Number(min))||Number(min)<0))||(max!==''&&(!Number.isFinite(Number(max))||Number(max)<0))||(min!==''&&max!==''&&Number(min)>Number(max))){$('range-error').textContent='请输入有效区间，最小值不能大于最大值。';return}if(min===''&&max==='')delete state.ranges[apply.dataset.rangeApply];else state.ranges[apply.dataset.rangeApply]={min,max};state.openRange='';state.page=1;loadList()}
});
$('page-size-control').addEventListener('click',event=>{const size=event.target.closest('[data-size]');if(!size)return;state.pageSize=Number(size.dataset.size);state.page=1;loadList()});
$('module-filters').addEventListener('change',event=>{
  const date=event.target.closest('[data-ranking-date]');
  if(date){state.rankingDate=date.type==='week'?date.value.replace('-W','-'):date.value;state.page=1;loadList();return}
  const input=event.target.closest('[data-launch]');
  if(input){const value=input.value||(state.module==='商品搜索'?(input.dataset.launch==='start'?FIRST_DATE:RANKING_DATE):NEW_DATE);
    if(input.dataset.launch==='start')state.launchStart=value;else state.launchEnd=value;
    if(state.launchStart&&state.launchEnd&&state.launchStart>state.launchEnd){
      if(input.dataset.launch==='start')state.launchEnd=state.launchStart;else state.launchStart=state.launchEnd;
    }
    state.page=1;loadList();return}
  const managed=event.target.closest('[data-managed]');
  if(managed){state.managed=managed.value;state.page=1;loadList();return}
  const shipping=event.target.closest('[data-free-shipping]');
  if(shipping){state.freeShipping=shipping.checked;state.page=1;loadList()}
});
$('module-filters').addEventListener('keydown',event=>{if(event.key==='Enter'&&event.target.id==='module-search')applySearch()});
$('sort-select').addEventListener('change',event=>{state.sort=event.target.value;state.page=1;loadList()});
$('page-controls').addEventListener('click',event=>{const button=event.target.closest('[data-page]');if(!button||button.disabled)return;state.page=Number(button.dataset.page);loadList();window.scrollTo({top:0,behavior:'smooth'})});
$('jump-page').addEventListener('keydown',event=>{if(event.key==='Enter'){const page=Number(event.target.value);if(Number.isInteger(page)&&page>=1&&page<=(current?.pages||1)){state.page=page;loadList();window.scrollTo({top:0,behavior:'smooth'})}}});
$('global-search-button').addEventListener('click',()=>{state.q=$('global-search').value.trim();state.page=1;loadList()});
$('global-search').addEventListener('keydown',event=>{if(event.key==='Enter')$('global-search-button').click()});
$('clear-filters').addEventListener('click',()=>{resetFilters();loadList()});
$('export-csv').addEventListener('click',()=>{const params=buildParams();params.delete('page');params.delete('page_size');const link=document.createElement('a');link.href='/api/export.csv?'+params;link.download='';document.body.append(link);link.click();link.remove()});
$('table-body').addEventListener('click',event=>{const button=event.target.closest('[data-detail-rank]');if(button)openDetail(Number(button.dataset.detailRank))});
$('table-body').addEventListener('error',event=>{const image=event.target;if(!image.matches('img'))return;if(image.classList.contains('thumb')||image.classList.contains('video-cover')){const fallback=document.createElement('div');fallback.className='no-thumb';fallback.textContent='原图失效';image.replaceWith(fallback)}else if(image.classList.contains('shop-logo')){const fallback=document.createElement('span');fallback.className='shop-logo-placeholder';fallback.title='原站头像链接失效';fallback.setAttribute('aria-label','店铺头像无法读取');fallback.textContent='—';image.replaceWith(fallback)}else if(image.classList.contains('video-author-avatar')){const fallback=document.createElement('span');fallback.className='video-author-avatar-missing';fallback.title='原站达人头像链接失效';fallback.setAttribute('aria-label','达人头像无法读取');fallback.textContent='—';image.replaceWith(fallback)}else image.remove()},true);
$('detail-content').addEventListener('error',event=>{const image=event.target;if(!image.matches('img'))return;if(image.id==='detail-main-photo'){image.hidden=true;let fallback=$('detail-image-missing');if(!fallback){fallback=document.createElement('div');fallback.id='detail-image-missing';fallback.className='detail-image-missing';fallback.setAttribute('role','img');fallback.setAttribute('aria-label','商品图片无法读取');fallback.textContent='原图暂不可用';image.after(fallback)}}else if(image.closest('.gallery-thumb')){const button=image.closest('.gallery-thumb');button.disabled=true;button.title='原图暂不可用';const fallback=document.createElement('span');fallback.className='gallery-image-missing';fallback.textContent='缺图';image.replaceWith(fallback)}},true);
$('detail-content').addEventListener('click',event=>{const button=event.target.closest('[data-gallery-src]');if(!button||button.disabled)return;const main=$('detail-main-photo');if(main){$('detail-image-missing')?.remove();main.hidden=false;main.src=button.dataset.gallerySrc}document.querySelectorAll('.gallery-thumb').forEach(item=>item.classList.toggle('active',item===button))});
$('detail-close').addEventListener('click',closeDetail);
$('detail-overlay').addEventListener('click',event=>{if(event.target===$('detail-overlay'))closeDetail()});
document.addEventListener('keydown',event=>{if(event.key==='Escape'&&!$('detail-overlay').hidden)closeDetail()});

fetch('/api/status').then(response=>response.json()).then(data=>{status=data;renderNav();if(current)renderFilters(current.categories||[])}).catch(()=>{});
loadList();
