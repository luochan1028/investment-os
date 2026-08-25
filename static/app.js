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

function createUser() {
    console.log('[createUser] called');
    const modal = $('modal');
    if (!modal) {
        console.error('[createUser] modal element not found');
        alert('页面错误：找不到弹窗元素，请刷新页面重试');
        return;
    }
    modal.innerHTML = `<div class="modal-box" style="max-width:460px">
        <div class="modal-header">
            <div class="modal-title">添加用户</div>
            <button class="btn btn-sm btn-ghost" onclick="closeModal()">关闭</button>
        </div>
        <div class="form-field" style="margin-bottom:14px">
            <label>用户名</label>
            <input id="newUsername" placeholder="只能包含字母、数字、下划线和连字符" style="width:100%;padding:10px;border:1.5px solid var(--border);border-radius:var(--radius-sm);font-size:14px;font-family:inherit">
        </div>
        <div class="form-field" style="margin-bottom:20px">
            <label>显示名称（可选）</label>
            <input id="newDisplayName" placeholder="如：张三" style="width:100%;padding:10px;border:1.5px solid var(--border);border-radius:var(--radius-sm);font-size:14px;font-family:inherit">
        </div>
        <div style="display:flex;gap:10px;justify-content:flex-end">
            <button class="btn btn-secondary" onclick="closeModal()">取消</button>
            <button class="btn btn-success" onclick="doCreateUser()">确认添加</button>
        </div>
    </div>`;
    modal.style.display = 'flex';
    setTimeout(() => $('newUsername')?.focus(), 100);
}

async function doCreateUser() {
    const username = $('newUsername')?.value.trim();
    const displayName = $('newDisplayName')?.value.trim() || '';
    if (!username) return showToast('请输入用户名', true);
    try {
        await fetchJSON('/api/users', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({username, display_name: displayName})
        });
        showToast('用户创建成功');
        closeModal();
        loadUsers();
    } catch(e) {
        showToast('创建失败: ' + e.message, true);
    }
}

// 宏观推送操作
async function macroCheckNow(btn) {
    btn.disabled = true; btn.textContent = '检查中...';
    try {
        const r = await fetchJSON('/api/macro/push-check', {method: 'POST'});
        showToast(`检查完成: ${r.pushed||0}条已推送, ${r.skipped||0}条跳过`);
    } catch(e) { showToast('检查失败: ' + e.message, true); }
    finally { btn.disabled = false; btn.textContent = '立即检查推送'; }
}

async function macroPushWeekly(btn) {
    btn.disabled = true; btn.textContent = '推送中...';
    try {
        const r = await fetchJSON('/api/macro/push-weekly', {method: 'POST'});
        showToast(r.pushed ? `已推送本周日历 (${r.events_count}个事件)` : (r.reason || '推送失败'));
    } catch(e) { showToast('推送失败: ' + e.message, true); }
    finally { btn.disabled = false; btn.textContent = '推送本周日历'; }
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
            <div class="card"><div class="card-title">Latest Sentiment</div>${d.recent_tweets.length?d.recent_tweets.map(t=>`<div class="alert-item ${t.impact_level||'low'}"><div class="alert-level">${levelIcon(t.impact_level)}</div><div><div class="alert-title">@${t.username}</div><div class="alert-detail" style="font-size:13px">${t.title||''}</div><div class="alert-meta">${t.category||''} · ${t.published||''}</div></div></div>`).join(''):'<div class="empty"><span class="empty-icon">-</span>No sentiment data</div>'}</div>
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
            const levelLabels = {'high':'P0 High','medium':'P1 Medium','low':'P2 Low'};
            c.innerHTML = `
            <div style="margin-bottom:12px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
                <div style="font-size:13px;color:var(--text-secondary)">Total: ${d.tweets.length} · High: ${highCount} · Source: ${d.source} · Last: ${lastRun}</div>
                <div style="display:flex;gap:6px">
                    <button class="btn btn-sm" onclick="refreshSentiment(this)">Refresh</button>
                    <button class="btn btn-sm btn-secondary" onclick="showAddAccount()">Add Account</button>
                    <button class="btn btn-sm btn-success" onclick="pushHighSentiment()">Push WeChat</button>
                </div>
            </div>
            <div class="card" style="margin-bottom:12px">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
                    <div class="card-title">Monitored Accounts (${accList.length})</div>
                    <div style="font-size:11px;color:var(--text-muted)">Interval: ${st.poll_interval||300}s · Enabled: ${accList.filter(a=>a.enabled).length}</div>
                </div>
                <div>${accBadges || '<span style="color:var(--text-muted)">No accounts</span>'}</div>
                ${xm.total_fetched !== undefined ? `<div style="margin-top:8px;font-size:12px;color:var(--text-secondary)">Last Poll: Fetched ${xm.total_fetched||0} · New ${xm.new_saved||0} · Pushed ${xm.pushed||0}${xm.errors&&xm.errors.length?` · Errors ${xm.errors.length}`:''}</div>` : ''}
            </div>
            ${table(['Level / 级别','User / 用户','Content / 内容','Category / 分类','Time / 时间','Action / 操作'],d.tweets.map(t=>`<tr><td>${levelTag(t.impact_level)}<span style="font-size:10px;color:var(--text-muted);margin-left:4px">${levelLabels[t.impact_level]||''}</span></td><td><strong>@${t.username}</strong>${t.pushed?'<span style="font-size:10px;color:var(--success);margin-left:4px">Pushed</span>':''}</td><td>${t.title||'-'}${t.summary?`<br><small style="color:var(--text-muted)">${t.summary.slice(0,80)}${t.summary.length>80?'...':''}</small>`:''}</td><td><span class="tag tag-blue">${t.category||'-'}</span></td><td style="color:var(--text-muted)">${t.published||t.created_at}</td><td><a href="${t.link||'#'}" target="_blank" style="font-size:12px;color:var(--primary);font-weight:600">Original</a></td></tr>`))}`;
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
            const ps = await fetchJSON('/api/macro/push-status').catch(()=>({running:false,last_result:{}}));
            const evs = d.events || [];
            const crit = evs.filter(e=>e.importance==='critical').length;
            const high = evs.filter(e=>e.importance==='high').length;
            const next = evs[0];
            const impEmoji = {critical:'🔴',high:'🟡',medium:'🟢'};
            const impTag = i => i==='critical'?'<span class="tag tag-red">极度重要</span>':i==='high'?'<span class="tag tag-yellow">重要</span>':'<span class="tag tag-gray">一般</span>';
            c.innerHTML = `
            <div class="stats-grid" style="margin-bottom:16px">
                ${statsGrid([
                    {label:'极度重要',value:crit,cls:'down'},
                    {label:'重要',value:high,cls:'warn'},
                    {label:'未来60天',value:evs.length},
                ])}
            </div>
            <div class="card" style="margin-bottom:14px;display:flex;gap:8px;align-items:center;flex-wrap:wrap">
                <div style="font-size:13px;color:var(--text-secondary)">推送状态: ${ps.running?'<span style="color:var(--success);font-weight:700">● 运行中</span>':'<span style="color:var(--text-muted)">○ 已停止</span>'}</div>
                ${ps.last_result?.last_run?`<span style="font-size:12px;color:var(--text-muted)">上次检查: ${ps.last_result.last_run}</span>`:''}
                <button class="btn btn-sm" style="padding:6px 12px;font-size:12px" onclick="macroCheckNow(this)">立即检查推送</button>
                <button class="btn btn-sm btn-success" style="padding:6px 12px;font-size:12px" onclick="macroPushWeekly(this)">推送本周日历</button>
            </div>
            ${next ? `<div class="card" style="margin-bottom:14px;border-left:3px solid var(--warning)">
                <div style="display:flex;justify-content:space-between;align-items:center">
                    <div>
                        <div style="font-size:12px;color:var(--text-muted)">${impEmoji[next.importance]||''} 最近一次宏观数据发布</div>
                        <div style="font-size:18px;font-weight:800;margin-top:6px">${next.name} <span style="font-size:13px;color:var(--text-muted);font-weight:400">${next.name_en||''}</span></div>
                        <div style="font-size:13px;color:var(--text-secondary);margin-top:4px">北京 ${next.event_datetime_bj} · 美东 ${next.event_datetime_et}</div>
                        ${next.impact ? `<div style="font-size:12px;color:var(--warning);margin-top:6px">${next.impact}</div>` : ''}
                    </div>
                    <div style="text-align:right">
                        <div style="font-size:22px;font-weight:800;color:var(--warning)">${next.countdown}</div>
                        <div style="font-size:11px;color:var(--text-muted);margin-top:4px">还有 ${next.days_until} 天</div>
                    </div>
                </div>
                ${next.impact_analysis ? `<div style="margin-top:12px;border-top:1px solid var(--border);padding-top:10px">
                    ${next.impact_analysis.key_point?`<div style="font-size:12px;color:var(--text-secondary);margin-bottom:6px"><strong>核心关注:</strong> ${next.impact_analysis.key_point}</div>`:''}
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
                        <div><div style="font-size:11px;font-weight:700;color:var(--success);margin-bottom:4px">好于预期</div>${(next.impact_analysis.better_than_expected||[]).map(p=>`<div style="font-size:11px;color:var(--text-secondary);margin-bottom:2px">• ${p}</div>`).join('')}</div>
                        <div><div style="font-size:11px;font-weight:700;color:var(--danger);margin-bottom:4px">差于预期</div>${(next.impact_analysis.worse_than_expected||[]).map(p=>`<div style="font-size:11px;color:var(--text-secondary);margin-bottom:2px">• ${p}</div>`).join('')}</div>
                    </div>
                </div>` : ''}
                ${next.historical_data && next.historical_data.length ? `<div style="margin-top:10px;border-top:1px solid var(--border);padding-top:8px"><div style="font-size:11px;font-weight:700;color:var(--text-muted);margin-bottom:4px">上次数据</div><div style="font-size:12px">实际: <strong>${next.historical_data[0].actual||'-'}</strong> · 预期: ${next.historical_data[0].expected||'-'} · 前值: ${next.historical_data[0].previous||'-'}</div>${next.historical_data[0].market_reaction?`<div style="font-size:11px;color:var(--text-muted);margin-top:2px">${next.historical_data[0].market_reaction}</div>`:''}</div>` : ''}
            </div>` : '<div class="empty"><span class="empty-icon">-</span>未来60天无宏观数据</div>'}
            ${evs.length ? table(
                ['事件','重要度','北京时间','美东时间','倒计时','关注点'],
                evs.map(e=>`<tr>
                    <td><strong>${e.name}</strong>${e.name_en?`<br><small style="color:var(--text-muted)">${e.name_en}</small>`:''}</td>
                    <td>${impTag(e.importance)}</td>
                    <td>${e.event_datetime_bj}</td>
                    <td style="color:var(--text-muted)">${e.event_datetime_et}</td>
                    <td class="${e.days_until<=3?'down-text':e.days_until<=7?'warn':''}" style="font-weight:700">${e.countdown}</td>
                    <td style="color:var(--warning);font-size:12px">${e.impact||'-'}</td>
                </tr>`)
            ) : ''}
            <div class="card" style="margin-top:14px">
                <div style="font-size:12px;color:var(--text-muted)">
                    数据源：${d.source === 'us-stock-monitor' ? 'us-stock-monitor ECONOMIC_CALENDAR（14个核心事件）' : '内置 fallback 规则推算'}<br>
                    抓取时间：${d.fetched_at} · 提醒规则: 提前1天/1小时/15分钟推送微信
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

// ==================== 金融危机专题 ====================
route('crisis', async () => {
    const tabs = [
        {key:'overview',label:'危机总览'},
        {key:'timeline',label:'历史时间线'},
        {key:'macro',label:'宏观指标'},
        {key:'institutions',label:'金融机构'},
        {key:'risk',label:'风险看板'},
        {key:'compare',label:'对比2008'},
        {key:'yield',label:'收益率曲线'},
        {key:'valuation',label:'估值杠杆'},
        {key:'crosscycle',label:'跨周期对比'},
        {key:'toolbox',label:'政策工具箱'},
        {key:'transmission',label:'传导图谱'},
        {key:'recovery',label:'恢复看板'},
        {key:'figures',label:'人物行为'},
        {key:'reports',label:'机构报告'},
    ];
    $('pageContent').innerHTML = `<div class="page-header"><div><div class="page-title">金融危机专题</div><div class="page-subtitle">Crisis Research: History · Monitoring · Simulation</div></div></div>${renderTabs(tabs,'overview','cr')}`;
    tabRenderers.cr = {
        overview: async c => {
            const [d, rd] = await Promise.all([fetchJSON('/api/crisis/list'), fetchJSON('/api/crisis/risk/dashboard')]);
            const crises = d.crises;
            const sc = {'2008-level':'#dc2626','major':'#f59e0b','moderate':'#3b82f6'};
            const riskColors = {low:'#10b981',moderate:'#f59e0b',elevated:'#f97316',high:'#ef4444',extreme:'#dc2626'};
            c.innerHTML = `
            <div class="card" style="margin-bottom:16px;padding:20px;background:linear-gradient(135deg,#1e293b,#0f172a);color:#fff">
                <div style="font-size:18px;font-weight:700;margin-bottom:8px">Financial Crisis Research Center / 金融危机研究中心</div>
                <div style="font-size:13px;color:#94a3b8;line-height:1.6">系统研究1929大萧条、1997亚洲金融风暴、2000互联网泡沫、2008全球金融危机和2020新冠崩盘，通过历史事件时间线、宏观指标回溯、机构演变追踪、实时风险监测和政策推演沙盘，全面评估当前市场与历史危机的相似度。</div>
            </div>
            <div class="stats-grid" style="margin-bottom:16px">${statsGrid([
                {label:'研究危机数 / Crises',value:crises.length},
                {label:'2008级别 / Severity',value:crises.filter(x=>x.severity==='2008-level').length,cls:'down'},
                {label:'最大跌幅 / Max Drop',value:`${Math.min(...crises.map(x=>x.peak_decline_snp)).toFixed(1)}%`,cls:'down'},
                {label:'当前风险评分 / Risk Score',value:`${rd.risk_score||0}/100`,cls:rd.risk_level==='low'?'up':'down'},
            ])}</div>
            ${rd.risk_level ? `<div class="card" style="margin-bottom:16px;display:flex;align-items:center;gap:16px">
                <div style="width:60px;height:60px;border-radius:50%;background:${riskColors[rd.risk_level]}20;display:flex;align-items:center;justify-content:center;border:3px solid ${riskColors[rd.risk_level]}">
                    <span style="font-size:18px;font-weight:800;color:${riskColors[rd.risk_level]}">${rd.risk_score}</span>
                </div>
                <div style="flex:1">
                    <div style="font-size:16px;font-weight:700;color:${riskColors[rd.risk_level]}">${rd.risk_level_zh||rd.risk_level} / ${rd.risk_level_en||rd.risk_level}</div>
                    <div style="font-size:13px;color:var(--text-secondary);margin-top:4px">${rd.assessment_zh||''}</div>
                </div>
            </div>` : ''}
            ${crises.map(cr => `
                <div class="card" style="margin-bottom:12px;cursor:pointer" onclick="showCrisisDetail('${cr.id}')">
                    <div style="display:flex;justify-content:space-between;align-items:flex-start">
                        <div style="flex:1">
                            <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px">
                                <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${sc[cr.severity]||'#64748b'}"></span>
                                <strong style="font-size:15px">${cr.name_zh}</strong>
                                <span style="font-size:12px;color:var(--text-muted)">${cr.name_en}</span>
                            </div>
                            <div style="font-size:13px;color:var(--text-secondary);margin-bottom:8px">${cr.period} · 持续${cr.duration_months}个月</div>
                            <div style="display:flex;gap:16px;flex-wrap:wrap">
                                <span style="font-size:12px;color:var(--text-muted)">S&P: <strong style="color:var(--danger)">${cr.peak_decline_snp}%</strong></span>
                                <span style="font-size:12px;color:var(--text-muted)">GDP: <strong style="color:var(--danger)">${cr.peak_decline_gdp}%</strong></span>
                                <span style="font-size:12px;color:var(--text-muted)">Unemployment: <strong>${cr.peak_unemployment}%</strong></span>
                                <span style="font-size:12px;color:var(--text-muted)">Events: <strong>${cr.key_events.length}</strong></span>
                            </div>
                        </div>
                        <span class="tag" style="background:${sc[cr.severity]}20;color:${sc[cr.severity]};border:1px solid ${sc[cr.severity]}40">${cr.severity}</span>
                    </div>
                </div>`).join('')}`;
        },
        timeline: async c => {
            const d = await fetchJSON('/api/crisis/list');
            c.innerHTML = `<div class="card" style="margin-bottom:12px"><div class="card-title">Select Crisis / 选择危机</div><div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px">${d.crises.map((cr,i)=>`<button class="btn ${i===0?'':'btn-secondary'}" style="font-size:12px" onclick="loadMultiTimeline('${cr.id}',this)">${cr.name_zh}</button>`).join('')}</div></div><div id="crisisTimelineContent"><div class="loading"><span class="spinner"></span>Loading...</div></div>`;
            loadMultiTimeline(d.crises[0].id);
        },
        macro: async c => {
            const d = await fetchJSON('/api/crisis/list');
            c.innerHTML = `<div class="card" style="margin-bottom:12px"><div class="card-title">Select Crisis / 选择危机</div><div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px">${d.crises.map((cr,i)=>`<button class="btn ${i===0?'':'btn-secondary'}" style="font-size:12px" onclick="loadMacroIndicators('${cr.id}',this)">${cr.name_zh}</button>`).join('')}</div></div><div id="macroContent"><div class="loading"><span class="spinner"></span>Loading...</div></div>`;
            loadMacroIndicators(d.crises[0].id);
        },
        institutions: async c => {
            const d = await fetchJSON('/api/crisis/list');
            c.innerHTML = `<div class="card" style="margin-bottom:12px"><div class="card-title">Select Crisis / 选择危机</div><div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px">${d.crises.map((cr,i)=>`<button class="btn ${i===0?'':'btn-secondary'}" style="font-size:12px" onclick="loadInstitutions('${cr.id}',this)">${cr.name_zh}</button>`).join('')}</div></div><div id="instContent"><div class="loading"><span class="spinner"></span>Loading...</div></div>`;
            loadInstitutions(d.crises[0].id);
        },
        risk: async c => {
            const d = await fetchJSON('/api/crisis/risk/dashboard');
            const rc = {low:'#10b981',moderate:'#f59e0b',elevated:'#f97316',high:'#ef4444',extreme:'#dc2626'};
            const top5 = d.top_5_risk_signals||[];
            const safe = d.safe_signals||[];
            c.innerHTML = `
            <div class="card" style="margin-bottom:16px;padding:20px;background:linear-gradient(135deg,#1e293b,#0f172a);color:#fff">
                <div style="display:flex;justify-content:space-between;align-items:center">
                    <div>
                        <div style="font-size:16px;font-weight:700">Risk Dashboard / 风险总览看板</div>
                        <div style="font-size:13px;color:#94a3b8;margin-top:4px">${d.assessment_zh||''}</div>
                    </div>
                    <div style="text-align:right">
                        <div style="font-size:36px;font-weight:800;color:${rc[d.risk_level]||'#64748b'}">${d.risk_score||0}</div>
                        <div style="font-size:11px;color:#94a3b8">${d.risk_level_zh||d.risk_level} / Risk Score</div>
                    </div>
                </div>
            </div>
            <div class="stats-grid" style="margin-bottom:16px">${statsGrid([
                {label:'Warning Signals',value:d.summary?.total_warning_signals||d.summary?.warning||0,cls:'down'},
                {label:'Danger Signals',value:d.summary?.danger||0,cls:'down'},
                {label:'Normal',value:d.summary?.normal||(safe.length),cls:'up'},
                {label:'Total Metrics',value:d.summary?.total||(top5.length+safe.length)},
            ])}</div>
            <div class="grid-2">
                <div class="card"><div class="card-title">Top 5 Risk Signals / 五大风险信号</div>${top5.length?top5.map(s=>{const lv={normal:'var(--success)',warning:'var(--warning)',danger:'var(--danger)'};return `<div class="alert-item ${s.warning_level||'medium'}"><div class="alert-level">!</div><div><div class="alert-title">${s.label_zh||s.label_en||''}</div><div class="alert-meta">${s.label_en||''} · 当前: ${s.current}${s.unit||''}</div></div></div>`}).join(''):'<div class="empty"><span class="empty-icon">-</span>No signals</div>'}</div>
                <div class="card"><div class="card-title">Safe Signals / 安全信号</div>${safe.length?safe.map(s=>`<div class="alert-item low"><div class="alert-level">+</div><div><div class="alert-title">${s.label_zh||s.label_en||''}</div><div class="alert-meta">${s.label_en||''} · 当前: ${s.current}${s.unit||''}</div></div></div>`).join(''):'<div class="empty"><span class="empty-icon">-</span>No data</div>'}</div>
            </div>`;
        },
        compare: async c => {
            const d = await fetchJSON('/api/crisis/compare/2008');
            const avg = d.avg_crisis_progress_pct;
            const pc = avg<25?'var(--success)':(avg<50?'var(--warning)':'var(--danger)');
            c.innerHTML = `
            <div class="card" style="margin-bottom:16px;padding:20px;background:linear-gradient(135deg,#1e293b,#0f172a);color:#fff">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
                    <div style="font-size:16px;font-weight:700">Current vs 2008 / 当前与2008对比</div>
                    <div style="text-align:right"><div style="font-size:28px;font-weight:800;color:${pc}">${avg}%</div><div style="font-size:11px;color:#94a3b8">Crisis Progress / 危机进度</div></div>
                </div>
                <div style="background:rgba(255,255,255,0.1);border-radius:8px;height:8px;overflow:hidden;margin-bottom:12px"><div style="width:${avg}%;height:100%;background:${pc};border-radius:8px"></div></div>
                <div style="font-size:13px;color:#94a3b8">${d.assessment_zh||''}</div>
            </div>
            ${table(['Indicator / 指标','Current','2008 Peak','Normal','Progress','Status'],d.indicators.map(i=>{const sc={normal:'var(--success)',warning:'var(--warning)',danger:'var(--danger)'};const sl={normal:'正常',warning:'警告',danger:'危险'};const pb=`<div style="background:var(--bg);border-radius:4px;height:6px;overflow:hidden;width:80px"><div style="width:${i.crisis_progress_pct}%;height:100%;background:${sc[i.status]};border-radius:4px"></div></div>`;return `<tr><td><strong style="font-size:13px">${i.key.replace(/_/g,' ')}</strong>${i.note?`<br><small style="color:var(--text-muted)">${i.note}</small>`:''}</td><td style="font-weight:700;color:${sc[i.status]}">${i.value}</td><td style="color:var(--danger)">${i.crisis_2008}</td><td style="color:var(--text-muted)">${i.normal}</td><td>${pb}<span style="font-size:11px;color:var(--text-muted)">${i.crisis_progress_pct}%</span></td><td><span class="tag" style="background:${sc[i.status]}20;color:${sc[i.status]};border:1px solid ${sc[i.status]}40">${sl[i.status]}</span></td></tr>`}))}`;
        },
        yield: async c => {
            const d = await fetchJSON('/api/crisis/risk/yield-curve');
            const status = d.inversion_status || 'normal';
            const status_zh = d.inversion_status_zh || status;
            const sc = {inverted:'var(--danger)',normal:'var(--success)',flat:'var(--warning)'};
            c.innerHTML = `
            <div class="card" style="margin-bottom:16px;display:flex;align-items:center;gap:16px">
                <div style="width:60px;height:60px;border-radius:50%;background:${sc[status]||'var(--text-muted)'}20;display:flex;align-items:center;justify-content:center;border:3px solid ${sc[status]||'var(--text-muted)'}"><span style="font-size:20px">${status==='inverted'?'!':'O'}</span></div>
                <div><div style="font-size:16px;font-weight:700;color:${sc[status]||'var(--text-muted)'}">${status_zh} / ${status}</div><div style="font-size:13px;color:var(--text-secondary);margin-top:4px">${d.assessment_zh||''}</div></div>
            </div>
            <div class="stats-grid" style="margin-bottom:16px">${statsGrid((d.spreads||[]).map(s=>({label:s.label,value:`${s.value>0?'+':''}${s.value.toFixed?s.value.toFixed(2):s.value}%`,cls:s.inverted?'down':'up',sub:s.inverted?'Inverted':'Normal'})))}</div>
            ${table(['Maturity / 期限','Yield / 收益率'],(d.yields_pct||[]).map(y=>`<tr><td><strong>${y.maturity}</strong></td><td style="font-weight:700;font-size:14px">${y.value.toFixed?y.value.toFixed(2):y.value}%</td></tr>`))}
            ${d.historical_comparison?`<div class="card" style="margin-top:16px"><div class="card-title">Historical Inversions / 历史倒挂</div>${table(['Period','10Y-2Y','Result'],(d.historical_comparison.inversions||[]).map(h=>`<tr><td>${h.period}</td><td>${h.spread}</td><td style="color:var(--text-secondary)">${h.outcome_zh||h.outcome||''}</td></tr>`))}</div>`:''}`;
        },
        valuation: async c => {
            const d = await fetchJSON('/api/crisis/risk/valuation');
            const sc = {normal:'var(--success)',warning:'var(--warning)',danger:'var(--danger)'};
            const sl = {normal:'正常 Normal',warning:'警告 Warning',danger:'危险 Danger'};
            c.innerHTML = `
            <div class="stats-grid" style="margin-bottom:16px">${statsGrid((d.metrics||[]).slice(0,4).map(m=>({label:m.label_zh||m.label_en,value:m.current,cls:m.warning_level==='danger'?'down':(m.warning_level==='warning'?'warn':'up'),sub:`阈值: ${m.warning_threshold||'-'}`})))}</div>
            ${table(['Metric / 指标','Current','2008','Historical Median','Warning Threshold','Level'],(d.metrics||[]).map(m=>`<tr><td><strong style="font-size:13px">${m.label_zh||m.label_en}</strong><br><small style="color:var(--text-muted)">${m.label_en||''}</small></td><td style="font-weight:700;color:${sc[m.warning_level]||'var(--text-muted)'}">${m.current}${m.unit||''}</td><td style="color:var(--danger)">${m.crisis_2008_peak||'-'}</td><td style="color:var(--text-muted)">${(m.normal_range||[]).join('-')||'-'}</td><td>${m.warning_threshold||'-'}</td><td><span class="tag" style="background:${sc[m.warning_level]}20;color:${sc[m.warning_level]};border:1px solid ${sc[m.warning_level]}40">${sl[m.warning_level]||'-'}</span></td></tr>`))}`;
        },
        crosscycle: async c => {
            const d = await fetchJSON('/api/crisis/risk/cross-cycle');
            const score = d.overall_risk_score||0;
            const pc = score<30?'var(--success)':(score<60?'var(--warning)':'var(--danger)');
            const mt = d.metrics_table||[];
            const periods = d.periods||{};
            const periodKeys = Object.keys(periods);
            const headers = ['指标', ...periodKeys.map(k=>periods[k].label_zh||k)];
            const rows = mt.map(m => [m.label_zh||m.label_en||m.key, ...periodKeys.map(k=>(m.values_by_period||{})[k]??'-')]);
            c.innerHTML = `
            <div class="card" style="margin-bottom:16px;padding:20px;background:linear-gradient(135deg,#1e293b,#0f172a);color:#fff">
                <div style="display:flex;justify-content:space-between;align-items:center">
                    <div style="font-size:16px;font-weight:700">Cross-Cycle Comparison / 跨周期对比</div>
                    <div style="text-align:right"><div style="font-size:28px;font-weight:800;color:${pc}">${score}/100</div><div style="font-size:11px;color:#94a3b8">Risk Score</div></div>
                </div>
                <div style="background:rgba(255,255,255,0.1);border-radius:8px;height:6px;overflow:hidden;margin-top:12px"><div style="width:${score}%;height:100%;background:${pc};border-radius:8px"></div></div>
            </div>
            <div style="font-size:13px;color:var(--text-secondary);margin-bottom:8px">${d.assessment_zh||''}</div>
            ${table(headers,rows.map(r=>`<tr>${r.map((cell,i)=>`<td style="${i===0?'font-weight:700;font-size:13px':''}">${cell}</td>`).join('')}</tr>`))}`;
        },
        toolbox: async c => {
            const d = await fetchJSON('/api/crisis/policy/toolbox');
            const cats = d.categories||{};
            c.innerHTML = `
            <div class="card" style="margin-bottom:16px;padding:20px;background:linear-gradient(135deg,#1e293b,#0f172a);color:#fff">
                <div style="font-size:16px;font-weight:700;margin-bottom:8px">Policy Toolbox / 政策工具箱</div>
                <div style="font-size:13px;color:#94a3b8">选择政策工具进行模拟，查看组合效果。Select tools to simulate their combined impact.</div>
            </div>
            <div style="margin-bottom:16px">
                <label style="font-size:13px;color:var(--text-secondary);margin-bottom:6px;display:block">Crisis Severity / 危机严重度</label>
                <select id="severitySelect" style="padding:8px 12px;border:1.5px solid var(--border);border-radius:8px;font-size:14px;width:100%;max-width:300px">
                    <option value="mild">Mild / 轻度</option>
                    <option value="moderate" selected>Moderate / 中度</option>
                    <option value="severe">Severe / 严重</option>
                    <option value="2008-level">2008-Level / 2008级别</option>
                </select>
            </div>
            ${Object.entries(cats).map(([catKey, catData]) => `
                <div class="card" style="margin-bottom:12px">
                    <div class="card-title">${catData.label_zh||catKey}</div>
                    <div style="font-size:11px;color:var(--text-muted);margin-bottom:8px">${catData.label_en||''}</div>
                    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:8px;margin-top:8px">
                        ${(catData.tools||[]).map(t=>`<label style="display:flex;align-items:flex-start;gap:8px;padding:10px;border:1px solid var(--border);border-radius:8px;cursor:pointer;transition:var(--transition)" onmouseover="this.style.borderColor='var(--primary)'" onmouseout="this.style.borderColor='var(--border)'"><input type="checkbox" value="${t.id}" class="policy-checkbox" style="margin-top:2px"><div><div style="font-size:13px;font-weight:600">${t.name_zh||t.name}</div><div style="font-size:11px;color:var(--text-muted)">${t.name_en||t.name}</div><div style="font-size:11px;color:var(--text-muted);margin-top:4px">${t.description_zh||''}</div></div></label>`).join('')}
                    </div>
                </div>`).join('')}
            <button class="btn btn-success" style="width:100%;padding:12px;font-size:15px" onclick="runPolicySimulation()">Run Simulation / 运行模拟</button>
            <div id="simResult" style="margin-top:16px"></div>`;
        },
        transmission: async c => {
            const d = await fetchJSON('/api/crisis/transmission/graph');
            const nodes = d.nodes||[];
            const edges = d.edges||[];
            const catColors = {asset_class:'#ef4444',institution:'#f59e0b',market:'#3b82f6',real_economy:'#10b981'};
            c.innerHTML = `
            <div class="card" style="margin-bottom:16px;padding:20px;background:linear-gradient(135deg,#1e293b,#0f172a);color:#fff">
                <div style="font-size:16px;font-weight:700;margin-bottom:8px">Risk Transmission Graph / 风险传导图谱</div>
                <div style="font-size:13px;color:#94a3b8">展示局部风险如何通过金融系统传导为系统性风险。Shows how localized risk transmits through the financial system into systemic risk.</div>
            </div>
            <div class="stats-grid" style="margin-bottom:16px">${statsGrid([
                {label:'Nodes / 节点',value:nodes.length},
                {label:'Edges / 边',value:edges.length},
                {label:'Feedback Loops',value:(d.feedback_loops||[]).length},
                {label:'High Severity',value:edges.filter(e=>e.severity==='high').length,cls:'down'},
            ])}</div>
            <div class="grid-2">
                <div class="card"><div class="card-title">Nodes / 节点 (${nodes.length})</div><div style="margin-top:8px">${nodes.map(n=>`<div style="display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid var(--border)"><span style="width:10px;height:10px;border-radius:50%;background:${catColors[n.category]||'#64748b'}"></span><div><div style="font-size:13px;font-weight:600">${n.label_zh||n.label||n.id}</div><div style="font-size:11px;color:var(--text-muted)">${n.label_en||n.id}</div></div></div>`).join('')}</div></div>
                <div class="card"><div class="card-title">Transmission Paths / 传导路径 (${edges.length})</div><div style="margin-top:8px;max-height:500px;overflow-y:auto">${edges.map(e=>{const sv={high:'var(--danger)',medium:'var(--warning)',low:'var(--text-muted)'};return `<div style="padding:8px 0;border-bottom:1px solid var(--border)"><div style="display:flex;align-items:center;gap:6px;margin-bottom:4px"><span style="font-size:12px;font-weight:600">${e.from_label||e.from}</span><span style="color:var(--text-muted)">&rarr;</span><span style="font-size:12px;font-weight:600">${e.to_label||e.to}</span><span style="width:8px;height:8px;border-radius:50%;background:${sv[e.severity]||'var(--text-muted)'};margin-left:auto"></span></div><div style="font-size:11px;color:var(--text-muted)">${e.description_zh||e.description||''}</div></div>`}).join('')}</div></div>
            </div>`;
        },
        recovery: async c => {
            const [rd, hp] = await Promise.all([fetchJSON('/api/crisis/recovery/dashboard'), fetchJSON('/api/crisis/policy/historical')]);
            const score = rd.overall_recovery_capacity_score||0;
            const pc = score>=70?'var(--success)':(score>=40?'var(--warning)':'var(--danger)');
            c.innerHTML = `
            <div class="card" style="margin-bottom:16px;padding:20px;background:linear-gradient(135deg,#1e293b,#0f172a);color:#fff">
                <div style="display:flex;justify-content:space-between;align-items:center">
                    <div><div style="font-size:16px;font-weight:700">Recovery Dashboard / 恢复进程看板</div><div style="font-size:13px;color:#94a3b8;margin-top:4px">${rd.assessment_zh||''}</div></div>
                    <div style="text-align:right"><div style="font-size:36px;font-weight:800;color:${pc}">${score}</div><div style="font-size:11px;color:#94a3b8">Recovery Capacity / 100</div></div>
                </div>
            </div>
            <div class="stats-grid" style="margin-bottom:16px">${statsGrid([
                {label:'Monetary Space / 货币空间',value:`${rd.monetary_space?.fed_rate||'5.5%'} → 0%`,sub:`Room: ${rd.monetary_space?.room_to_cut||'538bps'}`},
                {label:'Fiscal Space / 财政空间',value:`${rd.fiscal_space?.debt_to_gdp||124}%`,sub:`Debt/GDP`,cls:'warn'},
                {label:'Bank Capital / 银行资本',value:`${rd.banking_resilience?.tier1_ratio||14.7}%`,sub:`Tier 1`,cls:'up'},
                {label:'LCR / 流动性覆盖率',value:`${rd.banking_resilience?.lcr||121}%`,sub:`>100% required`,cls:'up'},
            ])}</div>
            <div class="card" style="margin-bottom:12px">
                <div class="card-title">Historical Policy Comparison / 历史政策对比</div>
                ${table(['Crisis','Policies','Fiscal Cost','Effectiveness','Recovery','Lessons'],(hp.crises||[]).map(cr=>`<tr><td><strong style="font-size:13px">${cr.name_zh||cr.name}</strong></td><td style="font-size:12px">${(cr.policies||[]).join(', ')}</td><td style="font-weight:600">${cr.total_fiscal_cost||'-'}</td><td><span class="tag ${cr.effectiveness>=4?'tag-green':cr.effectiveness>=3?'tag-blue':'tag-red'}">${'★'.repeat(cr.effectiveness||1)}</span></td><td style="font-size:12px">${cr.recovery_time||'-'}</td><td style="font-size:11px;color:var(--text-muted);max-width:300px">${cr.lessons_zh||cr.lessons||''}</td></tr>`))}
            </div>`;
        },
        figures: async c => {
            const d = await fetchJSON('/api/crisis/figures/actions');
            const actions = d.actions||[];
            const grouped = {};
            actions.forEach(a => {
                const k = a.crisis_id;
                if (!grouped[k]) grouped[k] = {name: a.crisis_name_zh, name_en: a.crisis_name_en, items: []};
                grouped[k].items.push(a);
            });
            const gainColor = g => g>=100?'var(--success)':g>=0?'var(--primary)':'var(--danger)';
            c.innerHTML = `
            <div class="card" style="margin-bottom:16px;padding:20px;background:linear-gradient(135deg,#1e293b,#0f172a);color:#fff">
                <div style="font-size:16px;font-weight:700;margin-bottom:8px">Crisis Figures & Actions / 危机人物行为与收益时间线</div>
                <div style="font-size:13px;color:#94a3b8">历次金融危机中，巴菲特、索罗斯、保尔森等关键人物的操作、策略和收益。共 ${actions.length} 条记录。</div>
            </div>
            ${Object.values(grouped).map(g => `
                <div class="card" style="margin-bottom:16px">
                    <div class="card-title" style="font-size:15px;border-bottom:1px solid var(--border);padding-bottom:8px;margin-bottom:12px">${g.name} <span style="font-size:12px;color:var(--text-muted);font-weight:400">${g.name_en}</span></div>
                    <div style="position:relative;padding-left:24px">
                        <div style="position:absolute;left:8px;top:0;bottom:0;width:2px;background:var(--border)"></div>
                        ${g.items.sort((a,b)=>a.date.localeCompare(b.date)).map(a => `
                            <div style="position:relative;margin-bottom:16px;padding-left:20px">
                                <div style="position:absolute;left:-16px;top:4px;width:10px;height:10px;border-radius:50%;background:${gainColor(a.gain_pct)};border:2px solid var(--card-bg)"></div>
                                <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px">
                                    <div>
                                        <span style="font-size:12px;font-weight:700;color:var(--primary)">${a.date}</span>
                                        <span style="font-size:14px;font-weight:700;margin-left:8px">${a.figure}</span>
                                        <span class="tag tag-blue" style="margin-left:6px">${a.asset_class}</span>
                                    </div>
                                    <span style="font-size:16px;font-weight:800;color:${gainColor(a.gain_pct)}">${a.gain_pct>0?'+':''}${a.gain_pct}%</span>
                                </div>
                                <div style="font-size:13px;color:var(--text);margin-top:4px;line-height:1.5">${a.action_zh}</div>
                                <div style="font-size:12px;color:var(--text-muted);margin-top:2px">${a.action_en}</div>
                                <div style="font-size:12px;color:var(--text-secondary);margin-top:6px"><strong>策略:</strong> ${a.strategy_zh}</div>
                                <div style="font-size:12px;color:var(--text-secondary);margin-top:4px"><strong>结果:</strong> ${a.outcome_zh}</div>
                                <div style="margin-top:4px">${(a.tags||[]).map(t=>`<span class="tag" style="font-size:10px;padding:2px 6px;margin-right:4px">${t}</span>`).join('')}</div>
                            </div>`).join('')}
                    </div>
                </div>`).join('')}
            `;
        },
        reports: async c => {
            const d = await fetchJSON('/api/crisis/list');
            const all = [];
            d.crises.forEach(cr=>{(cr.institutional_analyses||[]).forEach(a=>all.push({...a,crisis:cr.name_zh,crisis_id:cr.id}))});
            c.innerHTML = `
            <div class="card" style="margin-bottom:16px;padding:20px;background:linear-gradient(135deg,#1e293b,#0f172a);color:#fff">
                <div style="font-size:16px;font-weight:700;margin-bottom:8px">Institutional Reports / 机构分析报告</div>
                <div style="font-size:13px;color:#94a3b8">来自美联储、IMF、BIS、高盛、摩根大通等权威机构的深度研究报告。共 ${all.length} 份报告。</div>
            </div>
            ${all.map((a,i)=>`
                <div class="card" style="margin-bottom:12px;border:1px solid var(--border);border-radius:12px;overflow:hidden">
                    <div style="padding:16px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:flex-start">
                        <div>
                            <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px">
                                <strong style="font-size:15px;font-weight:700;color:var(--text)">${a.institution}</strong>
                                <span class="tag tag-blue">${a.crisis}</span>
                                ${a.date?`<span style="font-size:12px;color:var(--text-muted)">${a.date}</span>`:''}
                            </div>
                            <div style="font-size:14px;color:var(--text-secondary);font-weight:600">${a.report}</div>
                        </div>
                        <div style="display:flex;gap:8px">
                            ${a.download_url?`<a href="${a.download_url}" target="_blank" class="btn btn-sm" style="padding:6px 12px;font-size:12px">📥 ${a.download_url.toLowerCase().endsWith('.pdf')?'下载 PDF':'查看资源'}</a>`:''}
                            ${a.url?`<a href="${a.url}" target="_blank" class="btn btn-sm btn-secondary" style="padding:6px 12px;font-size:12px">查看原文</a>`:''}
                        </div>
                    </div>
                    <div style="padding:16px">
                        <div style="margin-bottom:12px">
                            <div style="font-size:12px;font-weight:700;color:var(--primary);margin-bottom:4px">KEY FINDING / 核心发现</div>
                            <div style="font-size:13px;color:var(--text);line-height:1.6;font-weight:600">${a.key_finding_zh}</div>
                            <div style="font-size:12px;color:var(--text-muted);margin-top:4px">${a.key_finding_en}</div>
                        </div>
                        ${a.summary_zh?`<div style="margin-bottom:12px;padding:12px;background:var(--bg);border-radius:8px">
                            <div style="font-size:12px;font-weight:700;color:var(--text-secondary);margin-bottom:6px">报告摘要 / Report Summary</div>
                            <div style="font-size:13px;color:var(--text);line-height:1.7">${a.summary_zh}</div>
                        </div>`:''}
                        ${a.conclusion_zh?`<div style="padding:12px;background:linear-gradient(135deg,var(--primary)10,var(--primary)5);border-left:4px solid var(--primary);border-radius:0 8px 8px 0">
                            <div style="font-size:13px;color:var(--text);line-height:1.7;font-weight:500">${a.conclusion_zh}</div>
                        </div>`:''}
                    </div>
                </div>
            `).join('')}`;
        },
    };
    await tabRenderers.cr.overview($('cr'));
});

// ---- 金融危机辅助函数 ----
async function loadMultiTimeline(crisisId, btn) {
    if (btn) { document.querySelectorAll('#cr .btn').forEach(b=>b.classList.add('btn-secondary')); btn.classList.remove('btn-secondary'); }
    const content = $('crisisTimelineContent'); if (!content) return;
    content.innerHTML = '<div class="loading"><span class="spinner"></span>Loading...</div>';
    try {
        const d = await fetchJSON(`/api/crisis/${crisisId}/multi-timeline`);
        const dims = d.dimensions||{};
        const dimLabels = {market:'市场 / Market',institution:'机构 / Institution',policy:'政策 / Policy',economic:'经济 / Economic'};
        const dimColors = {market:'#ef4444',institution:'#f59e0b',policy:'#3b82f6',economic:'#10b981'};
        content.innerHTML = Object.entries(dimLabels).map(([dk,dl])=>{
            const events = dims[dk]||[];
            if(!events.length) return '';
            return `<div class="card" style="margin-bottom:12px"><div style="display:flex;align-items:center;gap:8px;margin-bottom:8px"><span style="width:10px;height:10px;border-radius:50%;background:${dimColors[dk]}"></span><strong style="font-size:14px">${dl}</strong><span style="font-size:12px;color:var(--text-muted)">(${events.length})</span></div><div style="position:relative;padding-left:20px"><div style="position:absolute;left:6px;top:0;bottom:0;width:2px;background:${dimColors[dk]}40"></div>${events.map(e=>`<div style="position:relative;margin-bottom:10px;padding-left:16px"><div style="position:absolute;left:-14px;top:4px;width:8px;height:8px;border-radius:50%;background:${dimColors[dk]}"></div><div style="font-size:12px;font-weight:700;color:var(--primary)">${e.date}</div><div style="font-size:13px;font-weight:600">${e.event_zh||e.event}</div><div style="font-size:11px;color:var(--text-muted)">${e.event_en||''}</div></div>`).join('')}</div></div>`;
        }).join('') || '<div class="empty">No data</div>';
    } catch(e) { content.innerHTML = `<div class="empty">${e.message}</div>`; }
}

async function loadMacroIndicators(crisisId, btn) {
    if (btn) { document.querySelectorAll('#cr .btn').forEach(b=>b.classList.add('btn-secondary')); btn.classList.remove('btn-secondary'); }
    const content = $('macroContent'); if (!content) return;
    content.innerHTML = '<div class="loading"><span class="spinner"></span>Loading...</div>';
    try {
        const d = await fetchJSON(`/api/crisis/${crisisId}/macro`);
        const data = d.data||d.indicators||[];
        if (!data.length) { content.innerHTML = '<div class="empty">No data</div>'; return; }
        const cols = Object.keys(data[0]);
        content.innerHTML = `<div class="card"><div class="card-title">Macroeconomic Indicators / 宏观经济指标</div><div style="overflow-x:auto">${table(cols.map(c=>c.replace(/_/g,' ').replace(/\b\w/g,x=>x.toUpperCase())),data.map(r=>`<tr>${cols.map(c=>`<td style="font-size:12px">${r[c]??'-'}</td>`).join('')}</tr>`))}</div></div>`;
    } catch(e) { content.innerHTML = `<div class="empty">${e.message}</div>`; }
}

async function loadInstitutions(crisisId, btn) {
    if (btn) { document.querySelectorAll('#cr .btn').forEach(b=>b.classList.add('btn-secondary')); btn.classList.remove('btn-secondary'); }
    const content = $('instContent'); if (!content) return;
    content.innerHTML = '<div class="loading"><span class="spinner"></span>Loading...</div>';
    try {
        const d = await fetchJSON(`/api/crisis/${crisisId}/institutions`);
        const events = d.events||d.institutions||[];
        if (!events.length) { content.innerHTML = '<div class="empty">No data</div>'; return; }
        const typeColors = {bankruptcy:'#dc2626',acquisition:'#3b82f6',bailout:'#f59e0b',government_takeover:'#8b5cf6',recapitalization:'#10b981'};
        const typeLabels = {bankruptcy:'破产 Bankruptcy',acquisition:'收购 Acquisition',bailout:'救助 Bailout',government_takeover:'政府接管 Gov Takeover',recapitalization:'注资 Recapitalization'};
        content.innerHTML = events.map(e=>`<div class="card" style="margin-bottom:10px"><div style="display:flex;justify-content:space-between;align-items:flex-start"><div><div style="display:flex;align-items:center;gap:8px;margin-bottom:4px"><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${typeColors[e.event_type]||'#64748b'}"></span><strong style="font-size:14px">${e.name_zh||e.name||''}</strong><span style="font-size:11px;color:var(--text-muted)">${e.name_en||''}</span></div><div style="font-size:13px;color:var(--text-secondary)">${e.description_zh||e.description||''}</div>${e.acquirer?`<div style="font-size:12px;color:var(--text-muted);margin-top:4px">Acquirer: ${e.acquirer}</div>`:''}${e.bailout_amount?`<div style="font-size:12px;color:var(--text-muted)">Bailout: ${e.bailout_amount}</div>`:''}</div><div style="text-align:right"><span style="font-size:12px;font-weight:700;color:var(--primary)">${e.date||''}</span><div style="margin-top:4px"><span class="tag" style="background:${typeColors[e.event_type]||'#64748b'}20;color:${typeColors[e.event_type]||'#64748b'};border:1px solid ${typeColors[e.event_type]||'#64748b'}40;font-size:10px">${typeLabels[e.event_type]||e.event_type||''}</span></div></div></div></div>`).join('');
    } catch(e) { content.innerHTML = `<div class="empty">${e.message}</div>`; }
}

function showCrisisDetail(crisisId) {
    const modal = $('modal'); if (!modal) return;
    modal.innerHTML = '<div class="modal-box" style="max-width:900px"><div class="loading"><span class="spinner"></span>Loading...</div></div>';
    modal.style.display = 'flex';
    fetchJSON(`/api/crisis/${crisisId}`).then(d => {
        modal.innerHTML = `<div class="modal-box" style="max-width:900px;max-height:85vh;overflow-y:auto">
            <div class="modal-header"><div><div class="modal-title" style="font-size:18px">${d.name_zh}</div><div style="font-size:12px;color:var(--text-muted);margin-top:2px">${d.name_en} · ${d.period}</div></div><button class="btn btn-sm btn-ghost" onclick="closeModal()">Close</button></div>
            <div class="stats-grid" style="margin-bottom:16px">${statsGrid([{label:'S&P 500 Drop',value:`${d.peak_decline_snp}%`,cls:'down'},{label:'GDP Decline',value:`${d.peak_decline_gdp}%`,cls:'down'},{label:'Peak Unemployment',value:`${d.peak_unemployment}%`},{label:'Duration',value:`${d.duration_months}m`}])}</div>
            <div class="card" style="margin-bottom:12px"><div class="card-title">Causes / 危机原因</div><div style="font-size:13px;color:var(--text-secondary);white-space:pre-wrap;line-height:1.7;margin-top:8px">${d.causes_zh}</div></div>
            <div class="card" style="margin-bottom:12px"><div class="card-title">Recovery Actions / 应对措施</div><div style="font-size:13px;color:var(--text-secondary);white-space:pre-wrap;line-height:1.7;margin-top:8px">${d.recovery_actions_zh}</div></div>
            <div class="card" style="margin-bottom:12px"><div class="card-title">Lessons Learned / 经验教训</div><div style="font-size:13px;color:var(--text-secondary);white-space:pre-wrap;line-height:1.7;margin-top:8px">${d.lessons_zh}</div></div>
            <div class="card"><div class="card-title">Key Events / 关键事件</div><div style="margin-top:8px">${d.key_events.map(e=>{const ic={high:'var(--danger)',medium:'var(--warning)',low:'var(--text-muted)'};return `<div style="display:flex;gap:10px;padding:8px 0;border-bottom:1px solid var(--border)"><span style="font-size:12px;font-weight:700;color:var(--primary);min-width:80px">${e.date}</span><div style="flex:1"><div style="font-size:13px;font-weight:600">${e.event_zh}</div><div style="font-size:11px;color:var(--text-muted)">${e.event_en}</div></div><span style="width:8px;height:8px;border-radius:50%;background:${ic[e.impact]||'var(--text-muted)'};flex-shrink:0;margin-top:4px"></span></div>`}).join('')}</div></div>
        </div>`;
    }).catch(e => { modal.innerHTML = `<div class="modal-box"><div class="empty">Error: ${e.message}</div></div>`; });
}

async function runPolicySimulation() {
    const selected = Array.from(document.querySelectorAll('.policy-checkbox:checked')).map(cb=>cb.value);
    const severity = $('severitySelect')?.value || 'moderate';
    const result = $('simResult');
    if (!result) return;
    if (!selected.length) { result.innerHTML = '<div class="empty">Please select at least one tool / 请选择至少一个工具</div>'; return; }
    result.innerHTML = '<div class="loading"><span class="spinner"></span>Simulating...</div>';
    try {
        const d = await fetchJSON('/api/crisis/policy/simulate', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({selected_tools:selected, severity})});
        const sc = {recovery_time:'var(--primary)',gdp_impact:'var(--success)',unemployment_change:'var(--warning)',inflation_impact:'var(--warning)',fiscal_cost:'var(--danger)',confidence_boost:'var(--success)',side_effect_risk:'var(--danger)'};
        result.innerHTML = `
        <div class="card">
            <div class="card-title">Simulation Result / 模拟结果</div>
            <div class="stats-grid" style="margin-top:8px">${statsGrid([
                {label:'Recovery Time / 恢复时间',value:`${d.recovery_time_months||0}m`,cls:'up'},
                {label:'GDP Impact / GDP影响',value:`${d.gdp_impact||0}pp`,cls:(d.gdp_impact||0)>0?'up':'down'},
                {label:'Unemployment / 失业',value:`${d.unemployment_change||0}pp`,cls:(d.unemployment_change||0)>0?'down':'up'},
                {label:'Inflation / 通胀',value:`${d.inflation_impact||0}pp`,cls:'warn'},
                {label:'Fiscal Cost / 财政成本',value:`${d.fiscal_cost||0}%`,cls:'down'},
                {label:'Confidence / 信心',value:`${d.confidence_boost_score||0}/100`,cls:'up'},
                {label:'Side Effect Risk / 副作用',value:`${d.side_effect_risk||0}/100`,cls:'down'},
                {label:'Tools Selected',value:selected.length},
            ])}</div>
            ${d.narrative_zh?`<div style="margin-top:12px;padding:12px;background:var(--bg);border-radius:8px;font-size:13px;color:var(--text-secondary);line-height:1.6">${d.narrative_zh}</div>`:''}
            ${d.side_effects?`<div style="margin-top:8px;font-size:12px;color:var(--text-muted)">${d.side_effects}</div>`:''}
        </div>`;
    } catch(e) { result.innerHTML = `<div class="empty">Error: ${e.message}</div>`; }
}

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
