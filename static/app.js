// 投资研究操作系统 - 前端 SPA
const fmt = (n, d=2) => n == null ? '-' : Number(n).toLocaleString('zh-CN', {minimumFractionDigits:d, maximumFractionDigits:d});
const pct = (n, d=2) => n == null ? '-' : (n*100).toFixed(d) + '%';
const $ = id => document.getElementById(id);

let currentUserId = 1;
let currentUsername = 'default';
let userList = [];

function showToast(msg, isError=false) {
    const t = $('toast');
    t.textContent = msg;
    t.className = 'toast show' + (isError ? ' error' : '');
    setTimeout(() => t.className = 'toast', 2500);
}

async function fetchJSON(url, opts) {
    const r = await fetch(url, opts);
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
    return r.json();
}

async function fetchWithUser(url, opts = {}) {
    const hasQuery = url.includes('?');
    const userUrl = `${url}${hasQuery ? '&' : '?'}user_id=${currentUserId}`;
    return fetchJSON(userUrl, opts);
}

// 侧边栏切换（手机端）
function toggleSidebar() {
    $('sidebar').classList.toggle('open');
    $('overlay').classList.toggle('show');
}

// 用户管理
async function loadUsers() {
    try {
        const d = await fetchJSON('/api/users');
        userList = d.users || [];
        const select = $('userSelect');
        if (select) {
            select.innerHTML = userList.map(u =>
                `<option value="${u.id}" ${u.id === currentUserId ? 'selected' : ''}>${u.display_name || u.username}</option>`
            ).join('');
        }
    } catch(e) {
        console.error('加载用户列表失败:', e);
    }
}

function switchUser(userId) {
    currentUserId = parseInt(userId);
    const user = userList.find(u => u.id === currentUserId);
    if (user) {
        currentUsername = user.display_name || user.username;
    }
    showToast(`已切换到用户: ${currentUsername}`);
    loadUsers();
    navigate('overview');
}

async function createUser() {
    const username = prompt('请输入用户名（只能包含字母、数字、下划线和连字符）:');
    if (!username) return;
    const displayName = prompt('请输入显示名称:');
    try {
        await fetchJSON('/api/users', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({username, display_name: displayName || ''})
        });
        showToast('用户创建成功');
        loadUsers();
    } catch(e) {
        showToast('创建失败: ' + e.message, true);
    }
}

// 路由
const routes = {};
function route(name, fn) { routes[name] = fn; }
async function navigate(name) {
    document.querySelectorAll('.nav-item').forEach(el => el.classList.toggle('active', el.dataset.route === name));
    $('pageContent').innerHTML = '<div class="loading"><span class="spinner"></span> 加载中...</div>';
    if (window.innerWidth <= 768) toggleSidebar();
    try { await routes[name](); }
    catch (e) { $('pageContent').innerHTML = `<div class="empty"><span class="empty-icon">!</span>加载失败: ${e.message}</div>`; }
}
document.querySelectorAll('.nav-item').forEach(el => el.addEventListener('click', () => navigate(el.dataset.route)));

// Tab 框架
function renderTabs(tabs, activeKey, containerId) {
    tabLabels[containerId] = {};
    tabs.forEach(t => tabLabels[containerId][t.key] = t.label);
    return `<div class="tabs">${tabs.map(t => `<button class="tab ${t.key===activeKey?'active':''}" onclick="switchTab('${containerId}','${t.key}')">${t.label}</button>`).join('')}</div><div id="${containerId}"></div>`;
}
async function switchTab(containerId, tabKey) {
    const c = $(containerId);
    if (!c || !tabRenderers[containerId] || !tabRenderers[containerId][tabKey]) return;
    document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', tabLabels[containerId] && t.textContent.trim() === tabLabels[containerId][tabKey]));
    c.innerHTML = '<div class="loading"><span class="spinner"></span> 加载中...</div>';
    try { await tabRenderers[containerId][tabKey](c); }
    catch(e) { c.innerHTML = `<div class="empty"><span class="empty-icon">!</span>${e.message}</div>`; }
}
const tabLabels = {};
const tabRenderers = {};

// 通用组件
function statsGrid(stats) {
    return stats.map(s => `<div class="stat-card ${s.cls||''}"><div class="stat-label">${s.label}</div><div class="stat-value ${s.valueCls||''}">${s.value}</div>${s.sub?`<div class="stat-sub ${s.subCls||''}">${s.sub}</div>`:''}</div>`).join('');
}
function table(headers, rows, emptyMsg='暂无数据') {
    if (!rows.length) return `<div class="table-wrap"><table class="desktop-table"><thead><tr>${headers.map(h=>`<th>${h}</th>`).join('')}</tr></thead><tbody><tr><td colspan="${headers.length}" style="text-align:center;color:var(--text-muted);padding:40px">${emptyMsg}</td></tr></tbody></table></div>`;
    return `<div class="table-wrap"><table class="desktop-table"><thead><tr>${headers.map(h=>`<th>${h}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table></div>`;
}
function levelIcon(l) { return l==='high'?'!':l==='medium'?'?':'-'; }
function levelTag(l) { return `<span class="tag ${l==='high'?'tag-red':l==='medium'?'tag-yellow':'tag-gray'}">${l==='high'?'P0':l==='medium'?'P1':'P2'}</span>`; }
function scoreBar(score) {
    const color = score>=80?'var(--success)':score>=60?'var(--primary)':score>=40?'var(--warning)':'var(--danger)';
    return `<div style="display:flex;align-items:center;gap:8px"><div class="progress-bar" style="width:60px"><div class="progress-bar-fill" style="background:${color};width:${score}%"></div></div><span style="font-size:12px;font-weight:700;color:${color}">${score}</span></div>`;
}

// ==================== 总览 ====================
route('overview', async () => {
    const d = await fetchWithUser('/api/overview');
    const ms = d.modules_status;
    const userInfo = d.user || {username: currentUsername};
    $('pageContent').innerHTML = `
        <div class="page-header"><div><div class="page-title">总览 <span class="page-badge">${userInfo.display_name || userInfo.username}</span></div><div class="page-subtitle">${d.market_status} · ${d.updated_at}</div></div></div>
        <div class="stats-grid">${statsGrid([
            {label:'组合总市值',value:`¥${fmt(d.portfolio.total_market)}`,sub:`浮盈 ¥${fmt(d.portfolio.total_pnl)} (${pct(d.portfolio.total_pnl_pct)})`,cls:d.portfolio.total_pnl>=0?'up':'down',valueCls:d.portfolio.total_pnl>=0?'up-text':'down-text'},
            {label:'数据信号',value:ms.data_collection.signals_today,sub:`采集层 ${ms.data_collection.active}/${ms.data_collection.total} 活跃`},
            {label:'今日报告',value:ms.analysis.reports_today,sub:`分析层 ${ms.analysis.active}/${ms.analysis.total} 活跃`},
            {label:'风控告警',value:ms.risk.alerts_today,sub:`风控层 ${ms.risk.active}/${ms.risk.total} 活跃`,cls:ms.risk.alerts_today?'warn':''},
        ])}</div>
        <div class="grid-2">
            <div class="card"><div class="card-title">最近告警</div>${d.recent_alerts.length?d.recent_alerts.map(a=>`<div class="alert-item ${a.level}"><div class="alert-level">${levelIcon(a.level)}</div><div><div class="alert-title">${a.title}</div><div class="alert-meta">${a.symbol||'组合'} · ${a.created_at}</div></div></div>`).join(''):'<div class="empty"><span class="empty-icon">-</span>暂无告警</div>'}</div>
            <div class="card"><div class="card-title">最新舆情</div>${d.recent_tweets.length?d.recent_tweets.map(t=>`<div class="alert-item ${t.impact_level||'low'}"><div class="alert-level">${levelIcon(t.impact_level)}</div><div><div class="alert-title">@${t.username}</div><div class="alert-detail" style="font-size:13px">${t.title||''}</div><div class="alert-meta">${t.category||''} · ${t.published||''}</div></div></div>`).join(''):'<div class="empty"><span class="empty-icon">-</span>暂无舆情</div>'}</div>
        </div>
        <div class="card"><div class="card-title">快捷入口</div>
        <div class="stats-grid" style="margin-bottom:0">${[['market-intel','市场情报','&#9733;'],['analysis','智能分析','&#9881;'],['risk','持仓风控','&#9733;'],['knowledge','知识复盘','&#9776;']].map(([r,n,icon])=>`<div class="quick-entry" onclick="navigate('${r}')"><div class="quick-entry-icon">${icon}</div><div>${n}</div></div>`).join('')}</div></div>`;
});

// ==================== 市场情报 ====================
route('market-intel', async () => {
    const tabs = [
        {key:'market',label:'实时行情'},{key:'sentiment',label:'舆情监控'},{key:'filings',label:'财报'},
        {key:'central',label:'央行'},{key:'macro',label:'宏观'},{key:'geopolitics',label:'地缘'},{key:'supply',label:'产业链'},{key:'social',label:'社交'},
    ];
    $('pageContent').innerHTML = `<div class="page-header"><div><div class="page-title">市场情报</div><div class="page-subtitle">全球市场实时监控</div></div></div>${renderTabs(tabs,'market','mt')}`;
    tabRenderers.mt = {
        market: async c => { const d=await fetchJSON('/api/market/quotes'); const g={'美股':[],'A股':[],'港股':[],'加密/商品':[]}; d.quotes.forEach(q=>{const s=q.symbol;if(s.endsWith('.SS')||s.endsWith('.SZ'))g['A股'].push(q);else if(s.endsWith('.HK'))g['港股'].push(q);else if(['BTC-USD','ETH-USD','GLD','CL=F'].includes(s))g['加密/商品'].push(q);else g['美股'].push(q);}); c.innerHTML=Object.entries(g).map(([n,l])=>`<div class="card" style="margin-bottom:14px"><div class="card-title">${n}</div><div class="stats-grid" style="margin-bottom:0">${l.map(q=>{const up=q.change_pct>=0;return `<div class="stat-card"><div style="display:flex;justify-content:space-between"><span style="font-weight:700;font-size:14px">${q.symbol}</span><span class="${up?'up-text':'down-text'}" style="font-weight:700;font-size:14px">${up?'+':''}${q.change_pct.toFixed(2)}%</span></div><div class="stat-value ${up?'up-text':'down-text'}" style="font-size:20px;margin:6px 0">${fmt(q.price)}</div><div class="stat-sub">高 ${fmt(q.high)} / 低 ${fmt(q.low)}</div></div>`}).join('')}</div></div>`).join(''); },
        sentiment: async c => {
            const [d, st, accs] = await Promise.all([
                fetchJSON('/api/sentiment/tweets'),
                fetchJSON('/api/sentiment/status'),
                fetchJSON('/api/sentiment/accounts'),
            ]);
            const highCount = d.tweets.filter(t=>t.impact_level==='high').length;
            const xm = st.x_monitor || {};
            const lastRun = xm.last_run || '未运行';
            const accList = accs.accounts || [];
            const accBadges = accList.map(a => `<span style="display:inline-block;padding:3px 10px;margin:3px;border-radius:12px;font-size:12px;background:${a.enabled?'var(--primary-soft)':'var(--bg)'};color:${a.enabled?'var(--primary)':'var(--text-muted)'};cursor:pointer;border:1px solid ${a.enabled?'var(--primary-light)':'var(--border)'}" onclick="toggleXAccount('${a.username}',${a.enabled?0:1})" title="点击${a.enabled?'禁用':'启用'}">@${a.username}${a.enabled?'':' [已暂停]'}</span>`).join('');
            c.innerHTML = `
            <div style="margin-bottom:12px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
                <div style="font-size:13px;color:var(--text-secondary)">共 ${d.tweets.length} 条 · 高级别 ${highCount} 条 · 来源: ${d.source} · 上次刷新: ${lastRun}</div>
                <div style="display:flex;gap:6px">
                    <button class="btn btn-sm" onclick="refreshSentiment(this)">刷新</button>
                    <button class="btn btn-sm btn-secondary" onclick="showAddAccount()">添加账号</button>
                    <button class="btn btn-sm btn-success" onclick="pushHighSentiment()">推送微信</button>
                </div>
            </div>
            <div class="card" style="margin-bottom:12px">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
                    <div class="card-title">监控账号 (${accList.length})</div>
                    <div style="font-size:11px;color:var(--text-muted)">轮询间隔: ${st.poll_interval||300}秒 · 启用: ${accList.filter(a=>a.enabled).length}</div>
                </div>
                <div>${accBadges || '<span style="color:var(--text-muted)">暂无账号</span>'}</div>
                ${xm.total_fetched !== undefined ? `<div style="margin-top:8px;font-size:12px;color:var(--text-secondary)">最近一轮: 拉取 ${xm.total_fetched||0} 条 · 新增 ${xm.new_saved||0} 条 · 推送 ${xm.pushed||0} 条${xm.errors&&xm.errors.length?` · 错误 ${xm.errors.length} 条`:''}</div>` : ''}
            </div>
            ${table(['级别','用户','内容','分类','时间','操作'],d.tweets.map(t=>`<tr><td>${levelTag(t.impact_level)}</td><td><strong>@${t.username}</strong>${t.pushed?'<span style="font-size:10px;color:var(--success);margin-left:4px">已推</span>':''}</td><td>${t.title||'-'}${t.summary?`<br><small style="color:var(--text-muted)">${t.summary.slice(0,80)}${t.summary.length>80?'...':''}</small>`:''}</td><td><span class="tag tag-blue">${t.category||'-'}</span></td><td style="color:var(--text-muted)">${t.published||t.created_at}</td><td><a href="${t.link||'#'}" target="_blank" style="font-size:12px;color:var(--primary);font-weight:600">原文</a></td></tr>`))}`;
        },
        filings: async c => {
            const d = await fetchJSON('/api/filings');
            const unpushed = d.filings.filter(f=>!f.pushed).length;
            c.innerHTML = `<div style="margin-bottom:12px;display:flex;justify-content:space-between;align-items:center">
                <div style="font-size:13px;color:var(--text-secondary)">共 ${d.filings.length} 条 · 未推送 ${unpushed} 条 · 来源: ${d.source}</div>
                <button class="btn btn-sm" onclick="autoPushFilings(this)">自动推送最新财报</button>
            </div>` + table(
                ['标的','公司','类型','财报日','信号','摘要','操作'],
                d.filings.map(f=>`<tr>
                    <td><span class="tag tag-blue">${f.symbol}</span>${f.pushed?'<span style="font-size:10px;color:var(--success);margin-left:4px">已推</span>':'<span style="font-size:10px;color:var(--warning);margin-left:4px">未推</span>'}</td>
                    <td>${f.company}</td>
                    <td>${f.filing_type}</td>
                    <td>${f.filing_date}</td>
                    <td>${f.signal}</td>
                    <td><a href="javascript:void(0)" onclick="showFilingDetail('${f.symbol}')" style="color:var(--primary);text-decoration:underline;font-weight:600">${(f.summary||'-').slice(0,40)}${(f.summary||'').length>40?'...':''}</a></td>
                    <td><button class="btn btn-sm" onclick="pushFiling('${f.symbol}')">推送</button></td>
                </tr>`)
            );
        },
        central: async c => {
            const d = await fetchJSON('/api/central-bank/calendar');
            const evs = d.events || [];
            const crit = evs.filter(e=>e.importance==='critical').length;
            const high = evs.filter(e=>e.importance==='high').length;
            const next = evs[0];
            const srcBadge = d.source === 'us-stock-monitor'
                ? '<span class="badge badge-live">实时</span>'
                : '<span class="tag tag-gray">静态</span>';
            c.innerHTML = `<div class="stats-grid" style="margin-bottom:16px">
                ${statsGrid([
                    {label:'极度重要',value:crit,cls:'down'},
                    {label:'重要',value:high,cls:'warn'},
                    {label:'即将到来',value:evs.length},
                ])}
            </div>
            ${next ? `<div class="card" style="margin-bottom:14px;border-left:3px solid var(--danger)">
                <div style="display:flex;justify-content:space-between;align-items:center">
                    <div>
                        <div style="font-size:12px;color:var(--text-muted)">最近一次央行事件 ${srcBadge}</div>
                        <div style="font-size:18px;font-weight:800;margin-top:6px">${next.name}</div>
                        <div style="font-size:13px;color:var(--text-secondary);margin-top:4px">北京时间 ${next.event_datetime_bj} · 美东 ${next.event_datetime_et}</div>
                        ${next.impact ? `<div style="font-size:12px;color:var(--warning);margin-top:6px">${next.impact}</div>` : ''}
                    </div>
                    <div style="text-align:right">
                        <div style="font-size:22px;font-weight:800;color:var(--danger)">${next.countdown}</div>
                        <div style="font-size:11px;color:var(--text-muted);margin-top:4px">还有 ${next.days_until} 天</div>
                    </div>
                </div>
            </div>` : '<div class="empty"><span class="empty-icon">-</span>未来120天无央行事件</div>'}
            ${evs.length ? table(
                ['事件','重要度','北京时间','美东时间','倒计时','关注点'],
                evs.map(e=>`<tr>
                    <td><strong>${e.name}</strong></td>
                    <td>${e.importance==='critical'?'<span class="tag tag-red">极度重要</span>':'<span class="tag tag-yellow">重要</span>'}</td>
                    <td>${e.event_datetime_bj}</td>
                    <td style="color:var(--text-muted)">${e.event_datetime_et}</td>
                    <td class="${e.days_until<=3?'down-text':e.days_until<=7?'warn':''}" style="font-weight:700">${e.countdown}</td>
                    <td style="color:var(--warning);font-size:12px">${e.impact||'-'}</td>
                </tr>`)
            ) : ''}
            <div class="card" style="margin-top:14px">
                <div style="font-size:12px;color:var(--text-muted)">
                    数据源：${d.source === 'us-stock-monitor' ? 'us-stock-monitor（已修复央行会议日期 Bug）' : '内置 fallback 日期表'}<br>
                    抓取时间：${d.fetched_at}
                </div>
            </div>`;
        },
        macro: async c => {
            const d = await fetchJSON('/api/macro/calendar');
            const evs = d.events || [];
            const crit = evs.filter(e=>e.importance==='critical').length;
            const high = evs.filter(e=>e.importance==='high').length;
            const next = evs[0];
            c.innerHTML = `<div class="stats-grid" style="margin-bottom:16px">
                ${statsGrid([
                    {label:'极度重要',value:crit,cls:'down'},
                    {label:'重要',value:high,cls:'warn'},
                    {label:'未来60天',value:evs.length},
                ])}
            </div>
            ${next ? `<div class="card" style="margin-bottom:14px;border-left:3px solid var(--warning)">
                <div style="display:flex;justify-content:space-between;align-items:center">
                    <div>
                        <div style="font-size:12px;color:var(--text-muted)">最近一次宏观数据发布</div>
                        <div style="font-size:18px;font-weight:800;margin-top:6px">${next.name}</div>
                        <div style="font-size:13px;color:var(--text-secondary);margin-top:4px">北京 ${next.event_datetime_bj} · 美东 ${next.event_datetime_et}</div>
                        ${next.impact ? `<div style="font-size:12px;color:var(--warning);margin-top:6px">${next.impact}</div>` : ''}
                    </div>
                    <div style="text-align:right">
                        <div style="font-size:22px;font-weight:800;color:var(--warning)">${next.countdown}</div>
                        <div style="font-size:11px;color:var(--text-muted);margin-top:4px">还有 ${next.days_until} 天</div>
                    </div>
                </div>
            </div>` : '<div class="empty"><span class="empty-icon">-</span>未来60天无宏观数据</div>'}
            ${evs.length ? table(
                ['事件','重要度','北京时间','美东时间','倒计时','关注点'],
                evs.map(e=>`<tr>
                    <td><strong>${e.name}</strong></td>
                    <td>${e.importance==='critical'?'<span class="tag tag-red">极度重要</span>':e.importance==='high'?'<span class="tag tag-yellow">重要</span>':'<span class="tag tag-gray">一般</span>'}</td>
                    <td>${e.event_datetime_bj}</td>
                    <td style="color:var(--text-muted)">${e.event_datetime_et}</td>
                    <td class="${e.days_until<=3?'down-text':e.days_until<=7?'warn':''}" style="font-weight:700">${e.countdown}</td>
                    <td style="color:var(--warning);font-size:12px">${e.impact||'-'}</td>
                </tr>`)
            ) : ''}
            <div class="card" style="margin-top:14px">
                <div style="font-size:12px;color:var(--text-muted)">
                    数据源：${d.source === 'us-stock-monitor' ? 'us-stock-monitor ECONOMIC_CALENDAR（14个核心事件）' : '内置 fallback 规则推算'}<br>
                    抓取时间：${d.fetched_at}
                </div>
            </div>`;
        },
        geopolitics: async c => { const d=await fetchJSON('/api/geopolitics'); c.innerHTML=d.events.length?d.events.map(e=>`<div class="news-item"><div class="news-title">${e.title}</div><div class="news-meta">${e.regions} · ${e.source} · ${e.published_at}</div><div class="news-impact">受影响资产：${e.affected_assets}</div></div>`).join(''):'<div class="empty"><span class="empty-icon">-</span>暂无地缘事件</div>'; },
        supply: async c => { const d=await fetchJSON('/api/supply-chain'); c.innerHTML=d.chains.length?d.chains.map(ch=>`<div class="chain-card"><div class="chain-title">${ch.name}</div><div class="chain-nodes">${ch.nodes.map((n,i)=>`<div class="chain-node"><div class="chain-node-name">${n.name} <span class="tag tag-blue">${n.symbol}</span></div><div class="chain-node-role">${n.role}</div><div class="chain-node-alert">${n.alert}</div></div>${i<ch.nodes.length-1?'<div class="chain-arrow">&rarr;</div>':''}`).join('')}</div></div>`).join(''):'<div class="empty"><span class="empty-icon">-</span>暂无产业链数据</div>'; },
        social: async c => { const d=await fetchJSON('/api/social/sentiment'); c.innerHTML=`<div class="grid-3">${d.platforms.map(p=>`<div class="card"><div class="card-title">${p.name}</div><div class="stat-value ${p.sentiment>0.6?'up-text':'down-text'}" style="font-size:28px">${(p.sentiment*100).toFixed(0)}%</div><div class="stat-sub">情绪 · 24h 提及 ${p.mention_24h}</div><div style="margin-top:10px">${p.hot_stocks.map(s=>`<span class="tag tag-blue" style="margin-right:4px">${s}</span>`).join('')}</div></div>`).join('')}</div><div class="card"><div class="card-title">逼空预警</div>${d.alerts.length?d.alerts.map(a=>`<div class="alert-item medium"><div class="alert-level">?</div><div><div class="alert-title">${a.symbol} - ${a.type}</div><div class="alert-detail">${a.detail}</div></div></div>`).join(''):'<div class="empty"><span class="empty-icon">-</span>暂无预警</div>'}</div>`; },
    };
    await tabRenderers.mt.market($('mt'));
});

// ==================== 智能分析 ====================
route('analysis', async () => {
    const tabs = [
        {key:'report',label:'AI日报'},{key:'correlation',label:'多因子'},{key:'earnings',label:'财报季'},
        {key:'technical',label:'技术面'},{key:'cross',label:'跨市场'},{key:'ai',label:'AI选股'},
    ];
    $('pageContent').innerHTML = `<div class="page-header"><div><div class="page-title">智能分析</div><div class="page-subtitle">AI 驱动的深度市场分析</div></div></div>${renderTabs(tabs,'report','an')}`;
    tabRenderers.an = {
        report: async c => { const d=await fetchJSON('/api/daily-report'); c.innerHTML=`<div class="card" style="margin-bottom:14px"><div class="card-title">市场概览</div><p style="font-size:14px;line-height:1.7">${d.market_overview}</p></div><div class="grid-2"><div class="card"><div class="card-title">关键事件</div>${d.key_events.length?d.key_events.map(e=>`<div style="padding:8px 0;border-bottom:1px solid var(--border-light);font-size:14px">${e}</div>`).join(''):'<div class="empty">暂无</div>'}</div><div class="card"><div class="card-title">持仓动态</div><p style="font-size:14px">${d.portfolio_movement}</p></div></div><div class="card"><div class="card-title">明日关注</div>${d.tomorrow_focus.length?d.tomorrow_focus.map(f=>`<div style="padding:6px 0;font-size:14px">${f}</div>`).join(''):'<div class="empty">暂无</div>'}</div>`; },
        correlation: async c => { const d=await fetchJSON('/api/correlation'); c.innerHTML=`<div class="card" style="margin-bottom:14px"><div class="card-title">${d.case}</div><div class="stat-value up-text" style="font-size:22px">${d.asset} ${d.movement}</div></div>${table(['因子','证据','贡献','置信'],d.drivers.map(dr=>`<tr><td><strong>${dr.factor}</strong></td><td style="color:var(--text-muted)">${dr.evidence}</td><td><div class="progress-bar" style="width:100px"><div class="progress-bar-fill" style="background:var(--primary);width:${dr.contribution*100}%"></div></div><span style="font-size:12px;font-weight:700;margin-left:6px">${(dr.contribution*100).toFixed(0)}%</span></td><td><span class="tag ${dr.confidence==='高'?'tag-green':'tag-yellow'}">${dr.confidence}</span></td></tr>`))}<div class="card"><p style="font-size:14px;line-height:1.7">${d.conclusion}</p></div>`; },
        earnings: async c => { const d=await fetchJSON('/api/earnings-season'); c.innerHTML=table(['标的','公司','财报日','EPS预期','营收(B)','惊喜'],d.calendar.map(x=>`<tr><td><span class="tag tag-blue">${x.symbol}</span></td><td>${x.company}</td><td>${x.date}</td><td>${x.eps_estimate}</td><td>${x.rev_estimate}</td><td>${x.surprise||'-'}</td></tr>`)); },
        technical: async c => { c.innerHTML=`<div class="card" style="margin-bottom:14px"><div class="form-row" style="margin-bottom:0"><div class="form-field"><label>标的</label><input id="techSym" value="AAPL"></div><div class="form-field"><button class="btn" onclick="loadTech()">分析</button></div></div></div><div id="techRes"></div>`; loadTech(); },
        cross: async c => { const d=await fetchJSON('/api/cross-market'); c.innerHTML=`<div class="grid-3">${d.markets.map(m=>`<div class="card" style="${m.lead?'border-left:3px solid var(--primary)':''}"><div class="card-title">${m.market}${m.lead?' <span class="badge badge-live">领涨</span>':''}</div><div class="stat-value ${m.change.startsWith('+')?'up-text':'down-text'}" style="font-size:22px">${m.change}</div><div class="stat-sub">${m.status}</div></div>`).join('')}</div><div class="card"><div class="card-title">联动分析</div><p style="font-size:14px;line-height:1.7">${d.analysis}</p></div><div class="card"><div class="card-title">盘前简报</div><p style="font-size:14px">${d.pre_market_brief}</p></div>`; },
        ai: async c => { c.innerHTML=`<div class="card" style="margin-bottom:14px"><div class="card-title">筛选</div><div class="form-row" style="margin-bottom:0"><div class="form-field"><label>行业</label><select id="scSec"><option value="all">全部</option><option value="科技">科技</option><option value="金融">金融</option><option value="消费">消费</option><option value="能源">能源</option><option value="医药">医药</option></select></div><div class="form-field"><label>最低分</label><select id="scMin"><option value="50">50</option><option value="60" selected>60</option><option value="70">70</option></select></div><div class="form-field"><label>数量</label><select id="scTop"><option value="5">5</option><option value="10" selected>10</option></select></div><div class="form-field"><button class="btn" onclick="loadScreener()">筛选</button></div></div></div><div id="scRes"></div>`; loadScreener(); },
    };
    await tabRenderers.an.report($('an'));
});

async function loadTech() {
    const sym = $('techSym').value.trim().toUpperCase(); if(!sym) return;
    const res = $('techRes'); if(!res) return;
    res.innerHTML='<div class="loading"><span class="spinner"></span>分析中...</div>';
    try { const d=await fetchJSON(`/api/technical/${sym}`); res.innerHTML=`<div class="stats-grid">${statsGrid([{label:'最新价',value:fmt(d.last_price)},{label:'MA5',value:fmt(d.ma5),valueCls:d.last_price>d.ma5?'up-text':'down-text'},{label:'MA20',value:fmt(d.ma20)},{label:'RSI',value:fmt(d.rsi),valueCls:d.rsi>70?'down-text':d.rsi<30?'up-text':''}])}</div><div class="card"><div class="card-title">技术形态</div>${d.patterns.length?d.patterns.map(p=>`<div class="alert-item ${p.signal==='看涨'?'medium':p.signal==='看跌'?'high':'low'}"><div class="alert-level">${p.signal==='看涨'?'&#9650;':p.signal==='看跌'?'&#9660;':'-'}</div><div><div class="alert-title">${p.name}</div><div class="alert-detail">${p.signal} · 置信度 ${(p.confidence*100).toFixed(0)}%</div></div></div>`).join(''):'<div class="empty"><span class="empty-icon">-</span>暂无形态信号</div>'}</div>`; }
    catch(e){ res.innerHTML=`<div class="empty"><span class="empty-icon">!</span>${e.message}</div>`; }
}
async function loadScreener() {
    const res = $('scRes'); if(!res) return;
    res.innerHTML='<div class="loading"><span class="spinner"></span>AI 扫描中...</div>';
    try { const d=await fetchJSON(`/api/ai-screener?sector=${$('scSec')?.value||'all'}&min_score=${$('scMin')?.value||60}&top_n=${$('scTop')?.value||10}`);
        const rc=r=>r==='强烈推荐'?'tag-green':r==='推荐'?'tag-blue':r==='关注'?'tag-yellow':'tag-gray';
        res.innerHTML=`<div class="stats-grid">${statsGrid([{label:'扫描',value:d.total_scanned},{label:'符合',value:d.total_qualified,cls:'up'},{label:'展示',value:d.candidates.length}])}</div>${table(['#','标的','名称','行业','现价','20日','综合分','评级','理由'],d.candidates.map((c,i)=>`<tr><td style="font-weight:800;font-size:16px;color:var(--primary)">${i+1}</td><td><span class="tag tag-blue">${c.symbol}</span></td><td>${c.name}</td><td><span class="tag tag-gray">${c.sector}</span></td><td style="font-weight:700">${fmt(c.price)}</td><td class="${c.change_20d>=0?'up-text':'down-text'}">${c.change_20d>=0?'+':''}${c.change_20d}%</td><td><div style="font-size:22px;font-weight:800;color:${c.final_score>=85?'var(--success)':c.final_score>=75?'var(--primary)':'var(--warning)'}">${c.final_score}</div></td><td><span class="tag ${rc(c.rating)}">${c.rating}</span></td><td style="color:var(--text-secondary);font-size:12px">${c.reasons.join('、')}</td></tr>`))}<div class="card"><p style="font-size:12px;color:var(--text-muted)">仅供参考，非投资建议</p></div>`; }
    catch(e){ res.innerHTML=`<div class="empty"><span class="empty-icon">!</span>${e.message}</div>`; }
}

// ==================== 持仓与风控 ====================
route('risk', async () => {
    const tabs = [
        {key:'portfolio',label:'持仓'},{key:'scenario',label:'压测'},{key:'signals',label:'信号'},{key:'alerts',label:'告警'},
    ];
    $('pageContent').innerHTML = `<div class="page-header"><div><div class="page-title">持仓与风控</div><div class="page-subtitle">实时监控与风险管理</div></div></div>${renderTabs(tabs,'portfolio','rk')}`;
    tabRenderers.rk = {
        portfolio: async c => { const d=await fetchWithUser('/api/portfolio'); const pnlCls=d.total_pnl>=0?'up':'down';
            c.innerHTML=`<div style="margin-bottom:14px;display:flex;gap:8px;flex-wrap:wrap"><button class="btn btn-sm" onclick="toggleAdd()">添加持仓</button> <button class="btn btn-sm btn-success" onclick="triggerScan()">扫描</button> <button class="btn btn-sm btn-secondary" onclick="showRebalance()">调仓建议</button></div><div id="addForm" style="display:none;margin-bottom:14px" class="card"><div class="form-row" style="margin-bottom:0"><div class="form-field"><label>标的</label><input id="hSym" placeholder="AAPL"></div><div class="form-field"><label>成本</label><input id="hCost" type="number"></div><div class="form-field"><label>数量</label><input id="hSh" type="number"></div><div class="form-field"><label>行业</label><input id="hSec" placeholder="科技"></div><div class="form-field"><button class="btn btn-success" onclick="addH()">保存</button></div></div></div><div class="stats-grid">${statsGrid([{label:'总市值',value:`¥${fmt(d.total_market)}`,sub:`成本 ¥${fmt(d.total_cost)}`},{label:'浮盈亏',value:`${d.total_pnl>=0?'+':''}¥${fmt(d.total_pnl)}`,sub:`${d.total_pnl>=0?'+':''}${pct(d.total_pnl_pct)}`,cls:pnlCls,valueCls:d.total_pnl>=0?'up-text':'down-text'},{label:'组合VaR',value:d.portfolio_var!=null?pct(d.portfolio_var):'N/A',cls:'warn'},{label:'持仓数',value:d.positions.length}])}</div><div class="grid-2"><div class="card"><div class="card-title">盈亏分布</div><div class="chart-box"><canvas id="pnlChart"></canvas></div></div><div class="card"><div class="card-title">行业集中度</div><div class="chart-box"><canvas id="secChart"></canvas></div></div></div>${table(['标的','成本','现价','仓位','浮盈亏','VaR','回撤','操作'],d.positions.length?d.positions.map(p=>`<tr><td><span class="tag tag-blue">${p.symbol}</span></td><td>${fmt(p.cost_price)}</td><td>${fmt(p.current_price)}</td><td>${d.total_market?(p.market_value/d.total_market*100).toFixed(1):0}%</td><td class="${p.pnl>=0?'up-text':'down-text'}">${p.pnl>=0?'+':''}¥${fmt(p.pnl)}<br><small>(${pct(p.pnl_pct)})</small></td><td>${p.var!=null?pct(p.var):'N/A'}</td><td>${pct(p.max_drawdown)}</td><td><button class="btn btn-sm btn-danger" onclick="rmH('${p.symbol}')">删除</button></td></tr>`):[],'暂无持仓')}<div class="card"><div class="card-title">行业集中度</div>${Object.entries(d.concentration.by_sector||{}).map(([s,w])=>`<div style="display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid var(--border-light);font-size:14px"><span>${s}</span><span class="${w>0.3?'down-text':''}">${(w*100).toFixed(1)}%${w>0.3?' [过高]':''}</span></div>`).join('')||'<div class="empty"><span class="empty-icon">-</span>暂无</div>'}</div>`;
            if(d.positions.length){new Chart($('pnlChart').getContext('2d'),{type:'bar',data:{labels:d.positions.map(p=>p.symbol),datasets:[{data:d.positions.map(p=>p.pnl),backgroundColor:d.positions.map(p=>p.pnl>=0?'var(--success)':'var(--danger)')}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{ticks:{color:'var(--text-secondary)',font:{size:12}},grid:{color:'var(--border-light)'}},y:{ticks:{color:'var(--text-secondary)',font:{size:12}},grid:{color:'var(--border-light)'}}}}});const sec=d.concentration.by_sector||{};if(Object.keys(sec).length)new Chart($('secChart').getContext('2d'),{type:'doughnut',data:{labels:Object.keys(sec),datasets:[{data:Object.values(sec).map(v=>(v*100).toFixed(1)),backgroundColor:['var(--primary)','var(--success)','var(--warning)','var(--danger)','#a855f7']}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:'right',labels:{color:'var(--text-secondary)',font:{size:12}}}}}});}
        },
        scenario: async c => { const d=await fetchWithUser('/api/scenario'); c.innerHTML=table(['情景','影响','预估损益','受影响','严重度'],d.scenarios.map(s=>`<tr><td><strong>${s.name}</strong></td><td class="${s.impact_pct<0?'down-text':'up-text'}">${(s.impact_pct*100).toFixed(1)}%</td><td class="${s.estimated_loss<0?'down-text':'up-text'}">${s.estimated_loss>=0?'+':''}¥${fmt(s.estimated_loss)}</td><td style="color:var(--text-muted)">${s.affected.join(', ')}</td><td>${s.severity==='极高'||s.severity==='极端'?'<span class="tag tag-red">'+s.severity+'</span>':s.severity==='高'?'<span class="tag tag-red">高</span>':s.severity==='中'?'<span class="tag tag-yellow">中</span>':'<span class="tag tag-green">利好</span>'}</td></tr>`)); },
        signals: async c => { const d=await fetchWithUser('/api/signals'); c.innerHTML=table(['标的','信号','策略','置信度','理由'],d.signals.map(s=>`<tr><td><span class="tag tag-blue">${s.symbol}</span></td><td><span class="tag ${s.type==='买入'?'tag-green':s.type==='卖出'?'tag-red':'tag-gray'}">${s.type}</span></td><td>${s.strategy}</td><td>${scoreBar(Math.round(s.confidence*100))}</td><td style="color:var(--text-muted)">${s.reason}</td></tr>`))+`<div class="card"><p style="font-size:12px;color:var(--text-muted)">${d.disclaimer}</p></div>`; },
        alerts: async c => { const d=await fetchWithUser('/api/alerts'); const h=d.alerts.filter(a=>a.level==='high'),m=d.alerts.filter(a=>a.level==='medium'); c.innerHTML=`<div class="stats-grid">${statsGrid([{label:'P0 重大',value:h.length,cls:'down'},{label:'P1 关注',value:m.length,cls:'warn'},{label:'总计',value:d.alerts.length}])}</div><div class="card"><div class="card-title">告警历史</div>${d.alerts.length?d.alerts.map(a=>`<div class="alert-item ${a.level}"><div class="alert-level">${levelIcon(a.level)}</div><div style="flex:1"><div class="alert-title">${a.title}</div><div class="alert-detail">${(a.detail||'').replace(/\n/g,'<br>')}</div><div class="alert-meta">${a.alert_type} · ${a.symbol||'组合'} · ${a.created_at}</div></div></div>`).join(''):'<div class="empty"><span class="empty-icon">-</span>暂无告警</div>'}</div>`; },
    };
    await tabRenderers.rk.portfolio($('rk'));
});
function toggleAdd(){$('addForm').style.display=$('addForm').style.display==='none'?'block':'none';}
async function addH(){const p={symbol:$('hSym').value.trim(),cost_price:parseFloat($('hCost').value),shares:parseFloat($('hSh').value),sector:$('hSec').value.trim()};if(!p.symbol||!p.cost_price||!p.shares)return showToast('请填写完整',true);await fetchWithUser('/api/holdings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)});showToast('添加成功');switchTab('rk','portfolio');}
async function rmH(s){if(!confirm(`删除 ${s}?`))return;await fetchWithUser(`/api/holdings/${s}`,{method:'DELETE'});showToast('已删除');switchTab('rk','portfolio');}
async function triggerScan(){showToast('扫描中...');await fetchWithUser('/api/scan',{method:'POST'});showToast('完成');switchTab('rk','portfolio');}
async function showRebalance() {
    const modal = $('modal');
    if(!modal) return;
    modal.innerHTML = '<div class="modal-box"><div class="loading"><span class="spinner"></span>AI分析中...</div></div>';
    modal.style.display = 'flex';
    try {
        const d = await fetchWithUser('/api/rebalance');
        const an = d.analysis;
        const sevCls = s => s==='高'?'tag-red':s==='中'?'tag-yellow':'tag-green';
        const sevText = s => s==='高'?'P0 高风险':s==='中'?'P1 中风险':'P2 低风险';
        modal.innerHTML = `<div class="modal-box" style="max-width:800px">
            <div class="modal-header">
                <div class="modal-title">AI 调仓建议</div>
                <button class="btn btn-sm btn-ghost" onclick="closeModal()">关闭</button>
            </div>
            <div class="stats-grid" style="margin-bottom:14px">
                ${statsGrid([
                    {label:'总市值',value:`¥${fmt(an.total_market)}`},
                    {label:'总盈亏',value:`${an.total_pnl>=0?'+':''}${pct(an.total_pnl_pct)}`,cls:an.total_pnl>=0?'up':'down'},
                    {label:'持仓数',value:an.total_positions},
                    {label:'集中度',value:an.concentration_risk,cls:an.concentration_risk==='高'?'down':an.concentration_risk==='中'?'warn':'up'},
                ])}
            </div>
            ${d.action_items.length ? `<div class="card" style="margin-bottom:14px;border-left:3px solid var(--primary)"><div class="card-title">待办事项</div>${d.action_items.map((a,i)=>`<div style="padding:8px 0;border-bottom:1px solid var(--border-light);font-size:14px">${i+1}. ${a}</div>`).join('')}</div>` : ''}
            <div class="card" style="margin-bottom:14px"><div class="card-title">持仓分析</div>${table(['标的','行业','现价','盈亏','仓位','RSI','趋势'],an.stock_analysis.map(s=>`<tr><td><span class="tag tag-blue">${s.symbol}</span></td><td><span class="tag tag-gray">${s.sector||'-'}</span></td><td>${fmt(s.price)}</td><td class="${s.pnl_pct>=0?'up-text':'down-text'}">${s.pnl_pct>=0?'+':''}${pct(s.pnl_pct)}</td><td>${(s.weight*100).toFixed(1)}%</td><td class="${s.rsi&&s.rsi>70?'down-text':s.rsi&&s.rsi<30?'up-text':''}">${s.rsi||'-'}</td><td><span class="tag ${s.trend==='上升'?'tag-green':s.trend==='下降'?'tag-red':'tag-gray'}">${s.trend||'-'}</span></td></tr>`))}</div>
            <div class="card"><div class="card-title">调仓建议</div>${d.recommendations.length?d.recommendations.map(r=>`<div class="alert-item ${r.severity==='high'?'high':r.severity==='medium'?'medium':'low'}" style="margin-bottom:12px"><div class="alert-level">${levelIcon(r.severity)}</div><div style="flex:1"><div style="display:flex;justify-content:space-between"><div class="alert-title">${r.type}</div><span class="tag ${sevCls(r.severity)}">${sevText(r.severity)}</span></div><div class="alert-detail">${r.description}</div><div style="font-size:13px;color:var(--primary);margin-top:4px">${r.suggestion}</div></div></div>`).join(''):'<div class="empty"><span class="empty-icon">-</span>暂无建议</div>'}</div>
        </div>`;
    } catch(e) {
        modal.innerHTML = `<div class="modal-box"><div class="empty"><span class="empty-icon">!</span>${e.message}</div></div>`;
    }
}

// ==================== 知识与复盘 ====================
route('knowledge', async () => {
    const tabs = [
        {key:'kb',label:'知识库'},{key:'review',label:'复盘'},{key:'query',label:'问答'},{key:'backtest',label:'回测'},
    ];
    $('pageContent').innerHTML = `<div class="page-header"><div><div class="page-title">知识与复盘</div><div class="page-subtitle">经验沉淀与策略验证</div></div></div>${renderTabs(tabs,'kb','kn')}`;
    tabRenderers.kn = {
        kb: async c => { const d=await fetchJSON('/api/knowledge'); c.innerHTML=d.items.length?d.items.map(k=>`<div class="card" style="margin-bottom:12px"><div style="display:flex;justify-content:space-between"><strong style="font-size:15px">${k.title}</strong><span class="tag tag-blue">${k.category}</span></div><div style="font-size:12px;color:var(--text-muted);margin:8px 0">${k.tags}</div><div style="font-size:14px;line-height:1.6">${k.content}</div></div>`).join(''):'<div class="empty"><span class="empty-icon">-</span>暂无内容</div>'; },
        review: async c => { const d=await fetchWithUser('/api/review'); const t=await fetchWithUser('/api/trades'); c.innerHTML=`<div class="stats-grid">${statsGrid([{label:'总交易',value:d.total_trades},{label:'胜率',value:`${d.win_rate}%`,cls:d.win_rate>=50?'up':'down'},{label:'盈利',value:d.wins,cls:'up'},{label:'亏损',value:d.losses,cls:'down'}])}</div><div class="grid-2"><div class="card"><div class="card-title">错误模式</div>${d.common_mistakes.length?d.common_mistakes.map(m=>`<div class="alert-item high"><div class="alert-level">!</div><div><div class="alert-title">${m.pattern} (${m.frequency}次)</div><div class="alert-detail">${m.example}</div></div></div>`).join(''):'<div class="empty"><span class="empty-icon">-</span>暂无</div>'}</div><div class="card"><div class="card-title">最佳实践</div>${d.best_practices.length?d.best_practices.map(m=>`<div class="alert-item medium"><div class="alert-level">+</div><div><div class="alert-title">${m.pattern} (${m.frequency}次)</div><div class="alert-detail">${m.example}</div></div></div>`).join(''):'<div class="empty"><span class="empty-icon">-</span>暂无</div>'}</div></div>${table(['标的','方向','价格','理由','日期','结果'],t.trades.map(x=>`<tr><td><span class="tag tag-blue">${x.symbol}</span></td><td><span class="tag ${x.side==='buy'?'tag-green':'tag-red'}">${x.side}</span></td><td>${fmt(x.price)}</td><td style="color:var(--text-muted)">${x.reason}</td><td>${x.trade_date}</td><td class="${(x.outcome||'').startsWith('+')?'up-text':'down-text'}">${x.outcome||'-'}</td></tr>`))}`; },
        query: async c => { c.innerHTML=`<div class="query-box"><div class="form-row" style="margin-bottom:10px"><div class="form-field" style="grid-column:1/-1"><label>提问</label><input id="qIn" placeholder="如：特斯拉利空？黄金美元相关性？持仓行业集中度？" onkeydown="if(event.key==='Enter')ask()"></div><div class="form-field"><button class="btn" onclick="ask()">提问</button></div></div><div>${['特斯拉利空?','黄金美元相关性?','持仓行业集中度?','美联储加息?'].map(q=>`<span class="tag tag-gray" style="cursor:pointer;margin-right:6px" onclick="$('qIn').value='${q}';ask()">${q}</span>`).join('')}</div></div><div id="qOut"></div>`; },
        backtest: async c => { const d=await fetchJSON('/api/backtest'); const r=d.results; c.innerHTML=`<div class="stats-grid">${statsGrid([{label:'总交易',value:r.total_trades},{label:'胜率',value:pct(r.win_rate),cls:r.win_rate>=0.5?'up':'down'},{label:'最大回撤',value:pct(r.max_drawdown),cls:'down'},{label:'夏普',value:r.sharpe_ratio,cls:r.sharpe_ratio>=1?'up':''},{label:'年化',value:pct(r.annual_return),cls:'up'}])}</div><div class="card"><div class="card-title">权益曲线</div><div class="chart-box"><canvas id="eqChart"></canvas></div></div><div class="card"><p style="font-size:14px">基准：${d.comparison.benchmark} (${pct(d.comparison.benchmark_return)}) · Alpha：${pct(d.comparison.alpha)}</p></div>`; new Chart($('eqChart').getContext('2d'),{type:'line',data:{labels:d.equity_curve.map((_,i)=>i),datasets:[{data:d.equity_curve,borderColor:'var(--primary)',backgroundColor:'rgba(79,70,229,0.08)',fill:true,tension:0.4}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{display:false},y:{ticks:{color:'var(--text-secondary)',font:{size:12}},grid:{color:'var(--border-light)'}}}}}); },
    };
    await tabRenderers.kn.kb($('kn'));
});
async function ask(){const q=$('qIn').value.trim();if(!q)return;$('qOut').innerHTML='<div class="loading"><span class="spinner"></span>思考中...</div>';try{const d=await fetchJSON('/api/query',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:q})});$('qOut').innerHTML=d.answers.map(a=>`<div class="query-answer">${a}</div>`).join('');}catch(e){$('qOut').innerHTML=`<div class="empty"><span class="empty-icon">!</span>${e.message}</div>`;}}

// ==================== 财报详情与推送 ====================
async function showFilingDetail(symbol){
    const modal = $('modal');
    if(!modal) return;
    modal.innerHTML = '<div class="modal-box"><div class="loading"><span class="spinner"></span>加载财报详情...</div></div>';
    modal.style.display = 'flex';
    try {
        const d = await fetchJSON(`/api/filings/${symbol}`);
        const f = d.filing;
        const fmtM = v => {
            if (v == null) return 'N/A';
            if (Math.abs(v) >= 1e9) return (v/1e9).toFixed(2) + ' B';
            if (Math.abs(v) >= 1e6) return (v/1e6).toFixed(2) + ' M';
            return v.toFixed(0);
        };
        const gm = f.gross_margin != null ? (f.gross_margin*100).toFixed(1)+'%' : 'N/A';
        const bullishList = (f.bullish||[]).map(b=>`<li style="padding:4px 0;color:var(--success)">${b}</li>`).join('') || '<li style="color:var(--text-muted)">无</li>';
        const bearishList = (f.bearish||[]).map(b=>`<li style="padding:4px 0;color:var(--danger)">${b}</li>`).join('') || '<li style="color:var(--text-muted)">无</li>';
        const sigTag = (f.signal||'').includes('利好') ? 'tag-green' :
                       (f.signal||'').includes('利空') ? 'tag-red' : 'tag-gray';
        modal.innerHTML = `<div class="modal-box" style="max-width:720px">
            <div class="modal-header">
                <div class="modal-title">${f.company||symbol} 财报详情</div>
                <button class="btn btn-sm btn-ghost" onclick="closeModal()">关闭</button>
            </div>
            <div class="stats-grid" style="margin-bottom:14px">
                ${statsGrid([
                    {label:'标的', value:symbol},
                    {label:'报告期', value:f.period||'-'},
                    {label:'发布日', value:f.filing_date||'-'},
                    {label:'类型', value:f.filing_type||'-'},
                ])}
            </div>
            <div class="card" style="margin-bottom:14px">
                <div class="card-title">核心财务指标</div>
                <div class="stats-grid" style="margin-bottom:0">
                    ${statsGrid([
                        {label:'营收', value:fmtM(f.revenue)},
                        {label:'净利润', value:fmtM(f.net_income)},
                        {label:'毛利率', value:gm},
                    ])}
                </div>
            </div>
            <div class="card" style="margin-bottom:14px">
                <div class="card-title">投资信号</div>
                <p style="font-size:16px;margin:8px 0"><span class="tag ${sigTag}" style="font-size:13px">${f.signal||'中性'}</span></p>
                <p style="font-size:14px;line-height:1.7;color:var(--text-secondary)">${f.summary||'-'}</p>
            </div>
            <div class="grid-2">
                <div class="card">
                    <div class="card-title">利好因素</div>
                    <ul style="padding-left:20px;margin:8px 0">${bullishList}</ul>
                </div>
                <div class="card">
                    <div class="card-title">利空因素</div>
                    <ul style="padding-left:20px;margin:8px 0">${bearishList}</ul>
                </div>
            </div>
            <div style="margin-top:14px;display:flex;gap:8px;justify-content:flex-end">
                <button class="btn btn-sm" onclick="pushFiling('${symbol}', this)">推送到微信</button>
                <button class="btn btn-sm btn-ghost" onclick="closeModal()">关闭</button>
            </div>
        </div>`;
    } catch(e) {
        modal.innerHTML = `<div class="modal-box" style="max-width:480px"><div class="empty"><span class="empty-icon">!</span>${e.message}</div><button class="btn btn-sm" onclick="closeModal()" style="margin-top:14px">关闭</button></div>`;
    }
}

function closeModal(){
    const modal = $('modal');
    if(modal){ modal.style.display = 'none'; modal.innerHTML = ''; }
}

async function pushFiling(symbol, btn){
    if(btn){ const t=btn.textContent; btn.disabled=true; btn.textContent='推送中...'; try{await _doPushFiling(symbol); btn.textContent='已推送'; btn.disabled=false; setTimeout(()=>{btn.textContent=t;},2500);}catch(e){btn.textContent='失败'; btn.disabled=false; setTimeout(()=>{btn.textContent=t;},3000);} }
    else { await _doPushFiling(symbol); }
}

async function _doPushFiling(symbol){
    try {
        const d = await fetchJSON(`/api/filings/${symbol}/push`, {method:'POST'});
        if (d.pushed) {
            showToast(`已推送到微信 (级别: ${d.level})`);
        } else {
            const cfg = await fetchJSON('/api/config').catch(()=>null);
            if (cfg && !cfg.push_enabled) {
                showToast(`微信推送未配置！请在 .env 文件中设置 PUSHPLUS_TOKEN（前往 pushplus.plus 注册）`, true);
            } else if (cfg && cfg.today_failed > 0) {
                showToast(`推送失败，请检查 PUSHPLUS_TOKEN 是否正确`, true);
            } else {
                showToast(`推送被冷却，请稍后再试`, true);
            }
        }
    } catch(e) {
        showToast(`${e.message}`, true);
    }
}

async function pushHighSentiment(){
    const btn = event?.target;
    const t = btn ? btn.textContent : '';
    if(btn){ btn.disabled = true; btn.textContent = '推送中...'; }
    try {
        const d = await fetchJSON('/api/sentiment/push-high', {method:'POST'});
        if (d.pushed_count > 0) {
            showToast(`已推送 ${d.pushed_count} 条高级别舆情到微信`);
        } else {
            showToast(`${d.msg || '暂无可推送的舆情'}`, true);
        }
    } catch(e) {
        showToast(`${e.message}`, true);
    } finally {
        if(btn){ btn.disabled = false; btn.textContent = t; }
    }
}

async function refreshSentiment(btn){
    const t = btn ? btn.textContent : '';
    if(btn){ btn.disabled = true; btn.textContent = '刷新中...'; }
    try {
        const d = await fetchJSON('/api/sentiment/refresh', {method:'POST'});
        showToast(`拉取${d.total_fetched||0}条, 新增${d.new_saved||0}条, 推送${d.pushed||0}条`);
        switchTab('mt','sentiment');
    } catch(e) {
        showToast(`${e.message}`, true);
    } finally {
        if(btn){ btn.disabled = false; btn.textContent = t; }
    }
}

function showAddAccount(){
    const modal = $('modal');
    if(!modal) return;
    modal.innerHTML = `<div class="modal-box" style="max-width:460px">
        <div class="modal-header">
            <div class="modal-title">添加 X 监控账号</div>
            <button class="btn btn-sm btn-ghost" onclick="closeModal()">关闭</button>
        </div>
        <div class="form-field" style="margin-bottom:14px">
            <label>X 用户名</label>
            <input id="xAccName" placeholder="如 elonmusk" style="width:100%;padding:10px;border:1.5px solid var(--border);border-radius:var(--radius-sm);font-size:14px;font-family:inherit">
        </div>
        <div class="form-field" style="margin-bottom:20px">
            <label>显示名称（可选）</label>
            <input id="xAccDisplay" placeholder="如 埃隆·马斯克" style="width:100%;padding:10px;border:1.5px solid var(--border);border-radius:var(--radius-sm);font-size:14px;font-family:inherit">
        </div>
        <div style="display:flex;gap:10px;justify-content:flex-end">
            <button class="btn btn-secondary" onclick="closeModal()">取消</button>
            <button class="btn btn-success" onclick="addXAccount()">添加</button>
        </div>
    </div>`;
    modal.style.display = 'flex';
    setTimeout(() => $('xAccName')?.focus(), 100);
}

async function addXAccount(){
    const username = $('xAccName')?.value.trim();
    const displayName = $('xAccDisplay')?.value.trim() || '';
    if(!username) return showToast('请输入用户名', true);
    try {
        const d = await fetchJSON('/api/sentiment/accounts', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({username, display_name: displayName}),
        });
        showToast(`已添加 @${username}`);
        closeModal();
        switchTab('mt','sentiment');
    } catch(e) {
        showToast(`${e.message}`, true);
    }
}

async function toggleXAccount(username, enabled){
    try {
        await fetchJSON(`/api/sentiment/accounts/${username}?enabled=${enabled}`, {method: 'PUT'});
        showToast(enabled ? `已启用 @${username}` : `已禁用 @${username}`);
        switchTab('mt','sentiment');
    } catch(e) {
        showToast(`${e.message}`, true);
    }
}

async function removeXAccount(username){
    if(!confirm(`确定删除 @${username}?`)) return;
    try {
        await fetchJSON(`/api/sentiment/accounts/${username}`, {method: 'DELETE'});
        showToast(`已删除 @${username}`);
        switchTab('mt','sentiment');
    } catch(e) {
        showToast(`${e.message}`, true);
    }
}

async function autoPushFilings(btn){
    const t = btn ? btn.textContent : '';
    if(btn){ btn.disabled = true; btn.textContent = '检测并推送中...'; }
    try {
        const d = await fetchJSON('/api/filings/auto-push', {method:'POST'});
        if (d.pushed_count > 0) {
            showToast(`成功推送 ${d.pushed_count}/${d.total_unpushed} 条财报到微信`);
        } else {
            showToast(`${d.msg || '暂无未推送的财报'}`, true);
        }
    } catch(e) {
        showToast(`${e.message}`, true);
    } finally {
        if(btn){ btn.disabled = false; btn.textContent = t; }
    }
}

// 启动
(async () => {
    await loadUsers();
    navigate('overview');
})();
