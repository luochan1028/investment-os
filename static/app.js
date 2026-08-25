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
    navigate('dashboard');
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


// ==================== 驾驶舱（新首页） ====================
route('dashboard', async () => {
    const tabs = [
        {key:'today',label:'今日看板'},
        {key:'todo',label:'待办中心'},
        {key:'temp',label:'市场温度'},
    ];
    $('pageContent').innerHTML = `<div class="page-header">
        <div>
            <div class="page-title">投资驾驶舱 <span class="page-badge">决策首页</span></div>
            <div class="page-subtitle">今天要做什么 · 3 秒看懂市场 · 一眼掌握风险</div>
        </div>
        <div>
            <button class="btn btn-sm btn-secondary" onclick="navigate('portfolio')">💼 查看持仓</button>
        </div>
    </div>${renderTabs(tabs,'today','db')}`;

    tabRenderers.db = {
        // ====== 今日看板 ======
        today: async c => {
            // 并行拉取：总览数据 + 宏观日历(近3天) + 告警 + 推送状态
            const [ov, mac, al, ps, mc] = await Promise.all([
                fetchJSON('/api/overview').catch(()=>({positions:[],quotes:[],alerts:[],news:[]})),
                fetchJSON('/api/macro/calendar').catch(()=>({events:[]})),
                fetchWithUser('/api/alerts').catch(()=>({alerts:[]})),
                fetchJSON('/api/macro/push-status').catch(()=>({running:false})),
                fetchJSON('/api/market/quotes').catch(()=>({quotes:[]})),
            ]);
            const today = new Date().toISOString().slice(0,10);
            const upcoming = (mac.events||[]).filter(e=>{
                const dt = (e.event_datetime_bj||'').slice(0,10);
                return dt === today || (e.days_until||0) <= 2;
            }).slice(0,4);
            const highAlerts = (al.alerts||[]).filter(a=>a.level==='high').length;
            const medAlerts = (al.alerts||[]).filter(a=>a.level==='medium').length;
            const q = mc.quotes || [];
            const upCount = q.filter(x=>x.change_pct>=0).length;
            const downCount = q.length - upCount;
            const marketEmoji = upCount > downCount ? '🟢' : upCount < downCount ? '🔴' : '🟡';

            c.innerHTML = `
            <!-- 顶部：4 个 KPI + 市场状态 -->
            <div class="stats-grid">
                ${statsGrid([
                    {label:'待处理告警',value:highAlerts+medAlerts,sub:`P0 ${highAlerts} · P1 ${medAlerts}`,cls:highAlerts>0?'down':medAlerts>0?'warn':''},
                    {label:'宏观事件(3日内)',value:upcoming.length,sub:upcoming[0]?upcoming[0].name:'无'},
                    {label:'全球市场',value:marketEmoji,sub:`涨 ${upCount} / 跌 ${downCount}`,cls:upCount>=downCount?'up':'down'},
                    {label:'推送服务',value:ps.running?'运行':'停止',sub:ps.running?`最后: ${(ps.last_result||{}).last_run||'-'}`:'未启动',cls:ps.running?'up':'down'},
                ])}
            </div>

            <!-- 中栏：左右 2 列 -->
            <div class="grid-2">
                <!-- 左：今日宏观倒计时 -->
                <div class="card">
                    <div class="card-title">⏰ 即将发布 / 3天内</div>
                    ${upcoming.length ? upcoming.map(e=>`
                        <div style="padding:12px 0;border-bottom:1px solid var(--border-light);display:flex;justify-content:space-between;align-items:center;gap:8px">
                            <div style="flex:1;min-width:0">
                                <div style="font-weight:700;font-size:14px">${e.name}
                                    ${e.importance==='critical'?'<span class="tag tag-red">极度</span>':e.importance==='high'?'<span class="tag tag-yellow">重要</span>':''}
                                </div>
                                <div style="font-size:12px;color:var(--text-muted);margin-top:2px">北京 ${e.event_datetime_bj} · ${e.name_en||''}</div>
                                ${e.impact?`<div style="font-size:12px;color:var(--warning);margin-top:4px">${e.impact}</div>`:''}
                            </div>
                            <div style="text-align:right">
                                <div style="font-weight:800;font-size:16px;color:var(--primary)">${e.countdown||''}</div>
                                <div style="font-size:11px;color:var(--text-muted);margin-top:2px">${e.days_until===0?'今日':e.days_until===1?'明日':e.days_until+'天后'}</div>
                            </div>
                        </div>
                    `).join('') : '<div class="empty"><span class="empty-icon">📅</span>3日内无宏观数据</div>'}
                    <div style="margin-top:10px;display:flex;gap:6px">
                        <button class="btn btn-sm" onclick="navigate('market');setTimeout(()=>switchTab('ma','macro'),60)">完整日历 →</button>
                        <button class="btn btn-sm btn-success" onclick="macroPushWeekly(this)">推送本周</button>
                    </div>
                </div>

                <!-- 右：持仓盈亏概览 -->
                <div class="card">
                    <div class="card-title">💼 持仓速览</div>
                    ${(async()=>{ try {
                        const pf = await fetchWithUser('/api/portfolio');
                        const pos = pf.positions||[];
                        const pnlCls = pf.total_pnl>=0?'up':'down';
                        const top3 = pos.slice(0,3);
                        return `<div class="stats-grid" style="margin-bottom:14px">${statsGrid([
                            {label:'总市值',value:`¥${fmt(pf.total_market)}`,sub:`成本 ¥${fmt(pf.total_cost)}`},
                            {label:'浮动盈亏',value:`${pf.total_pnl>=0?'+':''}¥${fmt(pf.total_pnl)}`,sub:pct(pf.total_pnl_pct),cls:pnlCls,valueCls:pf.total_pnl>=0?'up-text':'down-text'},
                            {label:'组合VaR',value:pf.portfolio_var!=null?pct(pf.portfolio_var):'N/A',cls:'warn'},
                            {label:'持仓数',value:pos.length},
                        ])}</div>
                        ${top3.length?`<div style="font-size:12px;color:var(--text-muted);margin-bottom:6px;font-weight:700">重点持仓</div>` + top3.map(p=>`
                            <div style="padding:8px 0;border-bottom:1px solid var(--border-light);display:flex;justify-content:space-between;font-size:13px">
                                <span><span class="tag tag-blue">${p.symbol}</span> <span style="color:var(--text-secondary)">${(p.market_value/pf.total_market*100).toFixed(1)}%</span></span>
                                <span class="${p.pnl>=0?'up-text':'down-text'}" style="font-weight:700">${p.pnl>=0?'+':''}${pct(p.pnl_pct)}</span>
                            </div>
                        `).join(''):''}
                        <div style="margin-top:10px"><button class="btn btn-sm" onclick="navigate('portfolio')">持仓中心 →</button></div>`;
                    } catch(e) { return '<div class="empty"><span class="empty-icon">💼</span>暂无持仓</div>'; } })()}
                </div>
            </div>

            <!-- 底部：告警条 + 今日研究提示 -->
            <div class="card" style="margin-top:20px">
                <div class="card-title">🔥 今日待办 / 最新告警</div>
                ${al.alerts && al.alerts.length ? al.alerts.slice(0,4).map(a=>`
                    <div class="alert-item ${a.level}">
                        <div class="alert-level">${a.level==='high'?'🔴':a.level==='medium'?'🟡':'🟢'}</div>
                        <div style="flex:1">
                            <div class="alert-title">${a.title}</div>
                            <div class="alert-detail">${(a.detail||'').slice(0,80)}${(a.detail||'').length>80?'...':''}</div>
                            <div class="alert-meta">${a.alert_type} · ${a.symbol||'组合'} · ${a.created_at}</div>
                        </div>
                    </div>
                `).join('') : '<div class="empty"><span class="empty-icon">✅</span>暂无告警 · 持仓状态稳定</div>'}
                <div style="margin-top:10px;display:flex;gap:6px">
                    <button class="btn btn-sm btn-secondary" onclick="navigate('portfolio');setTimeout(()=>switchTab('pf','alerts'),60)">全部告警 →</button>
                    <button class="btn btn-sm" onclick="triggerScan()">扫描风险</button>
                </div>
            </div>`;
        },

        // ====== 待办中心 ======
        todo: async c => {
            const [al,sig,mac,pf] = await Promise.all([
                fetchWithUser('/api/alerts').catch(()=>({alerts:[]})),
                fetchWithUser('/api/signals').catch(()=>({signals:[]})),
                fetchJSON('/api/macro/calendar').catch(()=>({events:[]})),
                fetchWithUser('/api/portfolio').catch(()=>({positions:[],total_pnl_pct:0})),
            ]);
            const todos = [];
            // 高优先级告警
            (al.alerts||[]).filter(a=>a.level==='high').forEach(a=>{
                todos.push({type:'告警',priority:1,emoji:'🔴',title:a.title,desc:a.detail||'',time:a.created_at,action:'去处理',route:'portfolio',tab:'alerts'});
            });
            // 宏观倒计时 1 天内
            (mac.events||[]).filter(e=>(e.days_until||99)<=1 && e.importance==='critical').forEach(e=>{
                todos.push({type:'宏观',priority:1,emoji:'📅',title:e.name,desc:`${e.event_datetime_bj} · ${e.impact||''}`,time:e.event_datetime_bj,action:'查看影响',route:'market',tab:'macro'});
            });
            // 买入/卖出信号
            (sig.signals||[]).slice(0,3).forEach(s=>{
                todos.push({type:'信号',priority:2,emoji:s.type==='买入'?'🟢':'🔴',title:`${s.symbol} · ${s.type}信号`,desc:`${s.strategy} · 置信度 ${(s.confidence*100).toFixed(0)}%`,time:'',action:s.type,route:'portfolio',tab:'signals'});
            });
            // 中优先级告警
            (al.alerts||[]).filter(a=>a.level==='medium').forEach(a=>{
                todos.push({type:'关注',priority:3,emoji:'🟡',title:a.title,desc:a.detail||'',time:a.created_at,action:'查看',route:'portfolio',tab:'alerts'});
            });
            // 行业集中度过高提醒
            const sec = pf.concentration?.by_sector || {};
            Object.entries(sec).filter(([,w])=>w>0.3).forEach(([s,w])=>{
                todos.push({type:'风控',priority:2,emoji:'⚠️',title:`${s} 集中度过高`,desc:`占比 ${(w*100).toFixed(1)}%，建议分散`,time:'',action:'调仓',route:'portfolio',tab:'rebalance'});
            });
            todos.sort((a,b)=>a.priority-b.priority);

            c.innerHTML = `
            <div class="stats-grid" style="margin-bottom:20px">${statsGrid([
                {label:'P0 紧急',value:todos.filter(t=>t.priority===1).length,cls:'down'},
                {label:'P1 关注',value:todos.filter(t=>t.priority===2).length,cls:'warn'},
                {label:'P2 建议',value:todos.filter(t=>t.priority===3).length},
                {label:'总计',value:todos.length},
            ])}</div>
            ${todos.length ? todos.map(t=>`
                <div class="card" style="padding:16px 20px;margin-bottom:10px;display:flex;gap:14px;align-items:center;${t.priority===1?'border-left:4px solid var(--danger)':t.priority===2?'border-left:4px solid var(--warning)':'border-left:4px solid var(--border)'}">
                    <div style="font-size:26px">${t.emoji}</div>
                    <div style="flex:1;min-width:0">
                        <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:4px">
                            <span class="tag ${t.type==='告警'?'tag-red':t.type==='信号'?'tag-blue':t.type==='宏观'?'tag-purple':t.type==='风控'?'tag-yellow':'tag-gray'}">${t.type}</span>
                            <span style="font-weight:800;font-size:15px">${t.title}</span>
                        </div>
                        <div style="font-size:13px;color:var(--text-secondary);line-height:1.5">${t.desc||''}</div>
                        ${t.time?`<div style="font-size:11px;color:var(--text-muted);margin-top:4px">${t.time}</div>`:''}
                    </div>
                    <button class="btn btn-sm ${t.priority===1?'btn-danger':''}" onclick="navigate('${t.route}')${t.tab?`;setTimeout(()=>switchTab('${t.tab==='pf'?'pf':t.tab==='ma'?'ma':t.tab}','${t.tab===undefined?'':t.tab}'),80)`:''}">${t.action}</button>
                </div>
            `).join('') : '<div class="empty"><span class="empty-icon">🎯</span>今日无待办 · 市场平静</div>'}
            `;
        },

        // ====== 市场温度 ======
        temp: async c => {
            // 拉取多源数据：行情、收益率曲线、流动性、估值
            const [mc, yc, riskDash, xst, cm] = await Promise.all([
                fetchJSON('/api/market/quotes').catch(()=>({quotes:[]})),
                fetchJSON('/api/crisis/risk/yield-curve').catch(()=>({})),
                fetchJSON('/api/crisis/risk/dashboard').catch(()=>({})),
                fetchJSON('/api/sentiment/status').catch(()=>({})),
                fetchJSON('/api/cross-market').catch(()=>({markets:[]})),
            ]);
            const q = mc.quotes || [];
            const up = q.filter(x=>x.change_pct>=0).length;
            const breath = q.length ? (up/q.length*100) : 50;

            // 综合温度：各维度评分 (0-100，50中性)
            const dims = [
                {name:'市场宽度', score: Math.round(breath), weight: 0.2, hint: breath>60?'普涨':breath<40?'普跌':'分化'},
                {name:'舆情情绪', score: Math.round(50 + ((xst.x_monitor?.high_impact||0) / 10) * -15), weight: 0.2, hint: (xst.x_monitor?.total||0)+'条推文'},
                {name:'收益率曲线', score: Math.round(50 + ((yc.yields_pct||[]).find(y=>y.maturity==='10Y-2Y')?.value||0) * -10), weight: 0.2, hint: yc.yields_pct?((yc.yields_pct.find(y=>y.maturity==='10Y-2Y')?.value||0).toFixed(2)+'% 利差'):'-'},
                {name:'估值水平', score: Math.round(50), weight: 0.15, hint: (riskDash.valuation_risk||'N/A')},
                {name:'流动性', score: Math.round(55), weight: 0.15, hint: (riskDash.liquidity_risk||'N/A')},
                {name:'跨市场联动', score: Math.round(50 + ((cm.markets||[]).filter(m=>m.change?.startsWith('+')).length / Math.max(1,(cm.markets||[]).length) - 0.5) * 30), weight: 0.1, hint: (cm.markets||[]).length+'个市场'},
            ];
            let temp = 0;
            dims.forEach(d=>temp += d.score * d.weight);
            temp = Math.round(temp);

            const tempLabel = temp>=75?'🔥 过热':temp>=62?'🟢 贪婪':temp>=45?'🟡 中性':temp>=30?'🟠 恐惧':'❄️ 恐慌';
            const tempColor = temp>=75?'var(--danger)':temp>=62?'var(--success)':temp>=45?'var(--warning)':temp>=30?'#f97316':'var(--primary)';

            c.innerHTML = `
            <!-- 综合温度仪表盘 -->
            <div class="card" style="margin-bottom:20px;background:linear-gradient(135deg,rgba(99,102,241,0.05),rgba(16,185,129,0.03));border:1px solid var(--border)">
                <div style="display:flex;align-items:center;gap:32px;flex-wrap:wrap">
                    <div style="flex-shrink:0;width:200px;text-align:center">
                        <svg viewBox="0 0 200 120" width="200" height="120">
                            <defs>
                                <linearGradient id="tg" x1="0" y1="0" x2="1" y2="0">
                                    <stop offset="0%" stop-color="#6366f1"/><stop offset="25%" stop-color="#f97316"/>
                                    <stop offset="50%" stop-color="#f59e0b"/><stop offset="75%" stop-color="#10b981"/>
                                    <stop offset="100%" stop-color="#ef4444"/>
                                </linearGradient>
                            </defs>
                            <path d="M20 110 A80 80 0 0 1 180 110" fill="none" stroke="#e2e8f0" stroke-width="16" stroke-linecap="round"/>
                            <path d="M20 110 A80 80 0 0 1 180 110" fill="none" stroke="url(#tg)" stroke-width="16" stroke-linecap="round" stroke-dasharray="${(temp/100)*251.3} 251.3"/>
                            <polygon points="100,110 ${95+Math.cos((180-temp*1.8)*Math.PI/180)*56},${100-Math.sin((180-temp*1.8)*Math.PI/180)*56} ${105+Math.cos((180-temp*1.8)*Math.PI/180)*56},${100-Math.sin((180-temp*1.8)*Math.PI/180)*56}" fill="${tempColor}"/>
                            <circle cx="100" cy="100" r="6" fill="${tempColor}"/>
                        </svg>
                        <div style="font-size:42px;font-weight:900;color:${tempColor};margin-top:-10px">${temp}</div>
                        <div style="font-size:14px;color:var(--text-secondary);font-weight:700;margin-top:2px">${tempLabel}</div>
                    </div>
                    <div style="flex:1;min-width:260px">
                        <div style="font-size:22px;font-weight:800;margin-bottom:12px">今日市场综合温度</div>
                        <div style="font-size:14px;color:var(--text-secondary);line-height:1.7;margin-bottom:14px">
                            融合 6 大维度加权计算。<strong>0-30</strong> 恐慌/可布局，<strong>45-62</strong> 中性/持有，
                            <strong>75+</strong> 过热/谨慎。当前 ${temp>=60?'可考虑逐步兑现盈利':temp<=40?'可考虑分批布局':'持有观察'}。
                        </div>
                        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px">
                            <div class="stat-card" style="padding:12px;margin:0;background:var(--surface-muted)"><div class="stat-label">恐慌区</div><div class="stat-value" style="font-size:16px">0-30</div></div>
                            <div class="stat-card" style="padding:12px;margin:0;background:var(--surface-muted)"><div class="stat-label">中性区</div><div class="stat-value" style="font-size:16px">45-62</div></div>
                            <div class="stat-card" style="padding:12px;margin:0;background:var(--surface-muted)"><div class="stat-label">过热区</div><div class="stat-value" style="font-size:16px">75-100</div></div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- 维度明细 -->
            <div class="card" style="margin-bottom:20px">
                <div class="card-title">6 维度分项评分</div>
                ${dims.map(d=>`
                    <div style="padding:10px 0;border-bottom:1px solid var(--border-light);display:flex;align-items:center;gap:14px">
                        <div style="min-width:96px;font-weight:700;font-size:13px">${d.name}</div>
                        <div class="progress-bar" style="flex:1;height:10px;background:var(--border-light)">
                            <div class="progress-bar-fill" style="width:${d.score}%;background:${d.score>=75?'var(--danger)':d.score>=60?'var(--success)':d.score>=40?'var(--warning)':'var(--primary)'};height:100%;border-radius:4px"></div>
                        </div>
                        <div style="min-width:50px;text-align:right;font-weight:800;font-size:15px">${d.score}</div>
                        <div style="min-width:110px;text-align:right;font-size:12px;color:var(--text-muted)">${d.hint}</div>
                    </div>
                `).join('')}
            </div>

            <!-- 跨市场一览 -->
            <div class="card">
                <div class="card-title">跨市场实时状态</div>
                <div class="grid-3">${(cm.markets||[]).map(m=>`
                    <div class="stat-card" style="margin:0;${m.lead?'border-left:4px solid var(--primary);':''}">
                        <div class="stat-label">${m.market}${m.lead?' <span class="badge badge-live">领先</span>':''}</div>
                        <div class="stat-value ${m.change?.startsWith('+')?'up-text':'down-text'}" style="font-size:22px">${m.change||'-'}</div>
                        <div class="stat-sub">${m.status||''}</div>
                    </div>
                `).join('')}</div>
            </div>
            `;
        },
    };
    await tabRenderers.db.today($('db'));
});

// ==================== 市场监控（原市场情报，8→4 Tab） ====================
route('market', async () => {
    const tabs = [
        {key:'quotes',label:'全球行情'},
        {key:'macro',label:'宏观日历'},
        {key:'sentiment',label:'舆情监控'},
        {key:'events',label:'关键事件'},
    ];
    $('pageContent').innerHTML = `<div class="page-header"><div>
        <div class="page-title">市场监控</div>
        <div class="page-subtitle">行情 · 宏观 · 舆情 · 事件 — 4 个维度全覆盖</div>
    </div></div>${renderTabs(tabs,'quotes','ma')}`;

    tabRenderers.ma = {
        // 1. 全球行情（复用原 mt.market）
        quotes: async c => {
            const d = await fetchJSON('/api/market/quotes');
            const g={'美股':[],'A股':[],'港股':[],'加密/商品':[]};
            d.quotes.forEach(q=>{const s=q.symbol;if(s.endsWith('.SS')||s.endsWith('.SZ'))g['A股'].push(q);else if(s.endsWith('.HK'))g['港股'].push(q);else if(['BTC-USD','ETH-USD','GLD','CL=F'].includes(s))g['加密/商品'].push(q);else g['美股'].push(q);});
            c.innerHTML = Object.entries(g).map(([n,l])=>`<div class="card" style="margin-bottom:14px"><div class="card-title">${n} (${l.length})</div><div class="stats-grid" style="margin-bottom:0">${l.map(q=>{const up=q.change_pct>=0;return `<div class="stat-card"><div style="display:flex;justify-content:space-between"><span style="font-weight:700;font-size:14px">${q.symbol}</span><span class="${up?'up-text':'down-text'}" style="font-weight:700;font-size:14px">${up?'+':''}${q.change_pct.toFixed(2)}%</span></div><div class="stat-value ${up?'up-text':'down-text'}" style="font-size:20px;margin:6px 0">${fmt(q.price)}</div><div class="stat-sub">高 ${fmt(q.high)} / 低 ${fmt(q.low)}</div></div>`}).join('')}</div></div>`).join('');
        },
        // 2. 宏观日历（复用原 mt.macro + 推送控制）
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
            <div class="stats-grid" style="margin-bottom:16px">${statsGrid([
                {label:'极度重要',value:crit,cls:'down'},
                {label:'重要',value:high,cls:'warn'},
                {label:'未来60天',value:evs.length},
            ])}</div>
            <div class="card" style="margin-bottom:14px;display:flex;gap:8px;align-items:center;flex-wrap:wrap">
                <div style="font-size:13px;color:var(--text-secondary)">推送: ${ps.running?'<span style="color:var(--success);font-weight:700">● 运行中</span>':'<span style="color:var(--text-muted)">○ 已停止</span>'}</div>
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
        // 3. 舆情监控（复用原 mt.sentiment）
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
                    <button class="btn btn-sm btn-danger" onclick="pushHighImpact()">推送 P0</button>
                </div>
            </div>
            <div class="card" style="margin-bottom:14px">
                <div class="card-title">监控账号 (${accList.length})</div>
                <div style="font-size:13px;line-height:2">${accBadges || '<span style="color:var(--text-muted)">暂无账号</span>'}</div>
            </div>
            <div class="stats-grid" style="margin-bottom:16px">${statsGrid([
                {label:'P0 重大影响',value:highCount,cls:'down'},
                {label:'P1 中等',value:d.tweets.filter(t=>t.impact_level==='medium').length,cls:'warn'},
                {label:'总计',value:d.tweets.length},
                {label:'监控账号',value:accList.length},
            ])}</div>
            ${d.tweets.length ? d.tweets.slice(0,15).map(t=>`
                <div class="alert-item ${t.impact_level}">
                    <div class="alert-level">${t.impact_level==='high'?'🔴':t.impact_level==='medium'?'🟡':'🟢'}</div>
                    <div style="flex:1">
                        <div class="alert-title">${t.username ? `<span class="tag tag-blue">@${t.username}</span> `:''}${levelLabels[t.impact_level]||t.impact_level}</div>
                        <div class="alert-detail">${(t.content||t.text||'').slice(0,200)}${(t.content||t.text||'').length>200?'...':''}</div>
                        <div class="alert-meta">${t.published_at||t.created_at||''} · ${t.source||t.platform||''} ${t.impact_reason?`· <span style="color:var(--warning)">${t.impact_reason}</span>`:''}</div>
                    </div>
                </div>
            `).join('') : '<div class="empty"><span class="empty-icon">📱</span>暂无舆情数据</div>'}`;
        },
        // 4. 关键事件（合并原 央行/地缘/产业链/社交/财报 5合1）
        events: async c => {
            const [cb, geo, sc, fil] = await Promise.all([
                fetchJSON('/api/central-bank/calendar').catch(()=>({events:[]})),
                fetchJSON('/api/geopolitics').catch(()=>({events:[]})),
                fetchJSON('/api/supply-chain').catch(()=>({chains:[],news:[]})),
                fetchJSON('/api/filings').catch(()=>({filings:[]})),
            ]);
            // 合并所有事件并排序
            const all = [];
            (cb.events||[]).slice(0,5).forEach(e=>all.push({cat:'央行动态',tag:'tag-blue',icon:'🏦',title:e.event||`${e.central_bank||''} ${e.date||''}`,desc:`${e.decision||e.type||''} · ${e.impact||''}`,time:e.date||''}));
            (geo.events||[]).slice(0,5).forEach(e=>all.push({cat:'地缘政治',tag:'tag-red',icon:'🌍',title:e.title,desc:`${e.regions||''} · ${e.affected_assets||''}`,time:e.published_at||''}));
            (sc.news||[]).slice(0,5).forEach(e=>all.push({cat:'产业链',tag:'tag-green',icon:'🔗',title:e.title||e.event,desc:e.companies?`涉及: ${e.companies.join(', ')}`:`${e.sector||''} ${e.impact||''}`,time:e.date||''}));
            (fil.filings||[]).filter(f=>f.unread).slice(0,5).forEach(f=>all.push({cat:'财报/10-K',tag:'tag-purple',icon:'📑',title:`${f.symbol} · ${f.filing_type||''}`,desc:`${f.summary_zh?.slice(0,60)||f.key_findings?.[0]?.slice(0,60)||''}`,time:f.filed_at||''}));

            c.innerHTML = `
            <!-- 分类统计 -->
            <div class="stats-grid" style="margin-bottom:16px">${statsGrid([
                {label:'央行动态',value:(cb.events||[]).length},
                {label:'地缘政治',value:(geo.events||[]).length,cls:(geo.events||[]).length?'warn':''},
                {label:'产业链',value:(sc.news||[]).length},
                {label:'未读财报',value:(fil.filings||[]).filter(f=>f.unread).length,cls:(fil.filings||[]).filter(f=>f.unread).length?'warn':''},
            ])}</div>

            <!-- 央行日历 -->
            <div class="card" style="margin-bottom:16px">
                <div class="card-title">🏦 央行日历</div>
                ${table(
                    ['央行','事件','日期','预期','关注点'],
                    (cb.events||[]).map(e=>`<tr>
                        <td><strong>${e.central_bank||''}</strong></td>
                        <td>${e.event||e.type||''}</td>
                        <td>${e.date||''}</td>
                        <td>${e.expected_decision||e.expected||'-'}</td>
                        <td style="color:var(--warning);font-size:12px">${e.impact||''}</td>
                    </tr>`), '暂无央行动态'
                )}
            </div>

            <!-- 合并事件流 -->
            <div class="card">
                <div class="card-title">🌍 地缘 · 产业链 · 财报 · 社交事件流 (${all.length})</div>
                ${all.length ? all.slice(0,15).map(e=>`
                    <div style="padding:12px 0;border-bottom:1px solid var(--border-light);display:flex;gap:12px">
                        <div style="font-size:20px;flex-shrink:0">${e.icon}</div>
                        <div style="flex:1;min-width:0">
                            <div style="margin-bottom:4px"><span class="tag ${e.tag}">${e.cat}</span>
                                <span style="font-weight:700;font-size:14px;margin-left:6px">${e.title}</span>
                            </div>
                            ${e.desc?`<div style="font-size:13px;color:var(--text-secondary);line-height:1.5">${e.desc}</div>`:''}
                            ${e.time?`<div style="font-size:11px;color:var(--text-muted);margin-top:4px">${e.time}</div>`:''}
                        </div>
                    </div>
                `).join('') : '<div class="empty"><span class="empty-icon">-</span>暂无关键事件</div>'}
            </div>

            <!-- 产业链详情 -->
            ${(sc.chains&&sc.chains.length)?`
            <div class="card" style="margin-top:16px">
                <div class="card-title">🔗 产业链传导链 (${sc.chains.length})</div>
                ${sc.chains.map(ch=>`
                    <div class="chain-card" style="margin-bottom:12px">
                        <div class="chain-title">${ch.name||ch.title}</div>
                        <div class="chain-nodes">
                            ${(ch.nodes||[]).map((n,i,a)=>`
                                <div class="chain-node">
                                    <div class="chain-node-name">${n.name||n.company}</div>
                                    <div class="chain-node-role">${n.role||n.sector||''}</div>
                                    <div class="chain-node-alert">${n.alert||n.risk||''}</div>
                                </div>
                                ${i<a.length-1?'<div class="chain-arrow">→</div>':''}
                            `).join('')}
                        </div>
                    </div>
                `).join('')}
            </div>`:''}`;
        },
    };
    await tabRenderers.ma.quotes($('ma'));
});

// ==================== 深度研究（原智能分析，6→4 Tab） ====================
route('research', async () => {
    const tabs = [
        {key:'report',label:'AI 研报'},
        {key:'earnings',label:'财报季'},
        {key:'screener',label:'选股模型'},
        {key:'cross',label:'跨市场'},
    ];
    $('pageContent').innerHTML = `<div class="page-header"><div>
        <div class="page-title">深度研究</div>
        <div class="page-subtitle">AI 驱动 · 量化支撑 · 多维度验证</div>
    </div></div>${renderTabs(tabs,'report','re')}`;

    tabRenderers.re = {
        // 1. AI 研报（合并原 report + correlation）
        report: async c => {
            const [d, corr] = await Promise.all([
                fetchJSON('/api/daily-report'),
                fetchJSON('/api/correlation'),
            ]);
            c.innerHTML = `
            <div class="card" style="margin-bottom:16px;padding:22px;background:linear-gradient(135deg,var(--primary-soft),rgba(16,185,129,0.05));border:1px solid var(--primary-light)">
                <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:20px;flex-wrap:wrap">
                    <div style="flex:1;min-width:280px">
                        <div style="font-size:11px;font-weight:700;color:var(--primary);letter-spacing:1.5px;text-transform:uppercase;margin-bottom:6px">AI Daily Research · 每日市场研究</div>
                        <div style="font-size:13px;line-height:1.8;color:var(--text)">${d.market_overview}</div>
                    </div>
                    <div style="display:flex;flex-direction:column;gap:6px;align-items:flex-end">
                        <button class="btn btn-sm" onclick="navigate('review');setTimeout(()=>switchTab('rv','query'),80)">继续提问 →</button>
                        <span style="font-size:11px;color:var(--text-muted)">生成于每日开盘前</span>
                    </div>
                </div>
            </div>
            <div class="grid-2" style="margin-bottom:20px">
                <div class="card"><div class="card-title">关键事件 · 催化剂</div>${d.key_events.length?d.key_events.map(e=>`<div style="padding:8px 0;border-bottom:1px solid var(--border-light);font-size:13px">${e}</div>`).join(''):'<div class="empty">暂无</div>'}</div>
                <div class="card"><div class="card-title">持仓动态建议</div><p style="font-size:14px;line-height:1.7">${d.portfolio_movement}</p></div>
            </div>
            <div class="card" style="margin-bottom:16px">
                <div class="card-title">多因子归因分析 · ${corr.case}</div>
                <div class="stats-grid" style="margin-bottom:14px">${statsGrid([
                    {label:'标的',value:corr.asset,cls:'up'},
                    {label:'驱动方向',value:corr.movement,cls:corr.movement?.startsWith('+')?'up':'down'},
                ])}</div>
                ${table(['因子','证据','贡献','置信'],(corr.drivers||[]).map(dr=>`<tr>
                    <td><strong>${dr.factor}</strong></td>
                    <td style="color:var(--text-muted)">${dr.evidence}</td>
                    <td><div class="progress-bar" style="width:120px;display:inline-block;vertical-align:middle"><div class="progress-bar-fill" style="background:var(--primary);width:${(dr.contribution*100).toFixed(0)}%"></div></div> <span style="font-size:12px;font-weight:700;margin-left:6px">${(dr.contribution*100).toFixed(0)}%</span></td>
                    <td><span class="tag ${dr.confidence==='高'?'tag-green':'tag-yellow'}">${dr.confidence}</span></td>
                </tr>`), '暂无归因数据')}
                <div style="margin-top:12px;padding:12px;background:var(--bg);border-radius:8px;font-size:13px;line-height:1.7;color:var(--text-secondary)"><strong style="color:var(--text)">结论:</strong> ${corr.conclusion}</div>
            </div>
            <div class="card"><div class="card-title">📌 明日关注</div>${d.tomorrow_focus.length?d.tomorrow_focus.map(f=>`<div style="padding:8px 0;font-size:14px;border-bottom:1px solid var(--border-light)">${f}</div>`).join(''):'<div class="empty">暂无</div>'}</div>`;
        },
        // 2. 财报季
        earnings: async c => {
            const d = await fetchJSON('/api/earnings-season');
            c.innerHTML = table(
                ['标的','公司','财报日','EPS预期','营收(B)','惊喜'],
                (d.calendar||[]).map(x=>`<tr>
                    <td><span class="tag tag-blue">${x.symbol}</span></td>
                    <td>${x.company}</td>
                    <td>${x.date}</td>
                    <td>${x.eps_estimate}</td>
                    <td>${x.rev_estimate}</td>
                    <td>${x.surprise?`<span class="tag ${x.surprise.startsWith('+')?'tag-green':'tag-red'}">${x.surprise}</span>`:'-'}</td>
                </tr>`), '暂无财报数据'
            );
        },
        // 3. 选股模型（合并原 AI选股 + 技术面）
        screener: async c => {
            c.innerHTML = `
            <div class="card" style="margin-bottom:14px">
                <div class="card-title">筛选参数 + 技术分析</div>
                <div class="form-row" style="margin-bottom:0">
                    <div class="form-field"><label>行业</label>
                        <select id="scSec"><option value="all">全部</option><option value="科技">科技</option><option value="金融">金融</option><option value="消费">消费</option><option value="能源">能源</option><option value="医药">医药</option></select>
                    </div>
                    <div class="form-field"><label>最低分</label>
                        <select id="scMin"><option value="50">50</option><option value="60" selected>60</option><option value="70">70</option></select>
                    </div>
                    <div class="form-field"><label>数量</label>
                        <select id="scTop"><option value="5">5</option><option value="10" selected>10</option></select>
                    </div>
                    <div class="form-field"><label>技术标的</label><input id="techSym" placeholder="AAPL" value="AAPL"></div>
                    <div class="form-field"><button class="btn" onclick="loadScreener();loadTech()">同时分析</button></div>
                </div>
            </div>
            <div id="scRes"></div>
            <div id="techRes" style="margin-top:16px"></div>`;
            loadScreener();
            loadTech();
        },
        // 4. 跨市场
        cross: async c => {
            const d = await fetchJSON('/api/cross-market');
            c.innerHTML = `
            <div class="grid-3" style="margin-bottom:20px">${(d.markets||[]).map(m=>`
                <div class="card" style="${m.lead?'border-left:4px solid var(--primary)':''}">
                    <div class="card-title">${m.market}${m.lead?' <span class="badge badge-live">领涨</span>':''}</div>
                    <div class="stat-value ${m.change?.startsWith('+')?'up-text':'down-text'}" style="font-size:22px">${m.change||'-'}</div>
                    <div class="stat-sub">${m.status||''}</div>
                </div>`).join('')}
            </div>
            <div class="card" style="margin-bottom:16px"><div class="card-title">联动分析</div><p style="font-size:14px;line-height:1.7">${d.analysis||''}</p></div>
            <div class="card"><div class="card-title">盘前简报</div><p style="font-size:14px;line-height:1.7">${d.pre_market_brief||''}</p></div>`;
        },
    };
    await tabRenderers.re.report($('re'));
});

// ==================== 投资决策（原持仓风控，4→4，新增调仓助手） ====================
route('portfolio', async () => {
    const tabs = [
        {key:'holdings',label:'持仓中心'},
        {key:'signals',label:'信号建议'},
        {key:'scenario',label:'压力测试'},
        {key:'rebalance',label:'调仓助手'},
    ];
    $('pageContent').innerHTML = `<div class="page-header"><div>
        <div class="page-title">投资决策</div>
        <div class="page-subtitle">持仓 · 信号 · 压测 · 调仓 — 闭环决策链</div>
    </div></div>${renderTabs(tabs,'holdings','pf')}`;

    tabRenderers.pf = {
        // 1. 持仓中心（原 rk.portfolio）
        holdings: async c => {
            const d = await fetchWithUser('/api/portfolio');
            const pnlCls = d.total_pnl>=0?'up':'down';
            c.innerHTML = `
            <div style="margin-bottom:14px;display:flex;gap:8px;flex-wrap:wrap">
                <button class="btn btn-sm" onclick="toggleAdd()">+ 添加持仓</button>
                <button class="btn btn-sm btn-success" onclick="triggerScan()">风险扫描</button>
                <button class="btn btn-sm btn-secondary" onclick="showRebalance()">调仓建议</button>
            </div>
            <div id="addForm" style="display:none;margin-bottom:14px" class="card">
                <div class="form-row" style="margin-bottom:0">
                    <div class="form-field"><label>标的</label><input id="hSym" placeholder="AAPL"></div>
                    <div class="form-field"><label>成本</label><input id="hCost" type="number"></div>
                    <div class="form-field"><label>数量</label><input id="hSh" type="number"></div>
                    <div class="form-field"><label>行业</label><input id="hSec" placeholder="科技"></div>
                    <div class="form-field"><button class="btn btn-success" onclick="addH()">保存</button></div>
                </div>
            </div>
            <div class="stats-grid">${statsGrid([
                {label:'总市值',value:`¥${fmt(d.total_market)}`,sub:`成本 ¥${fmt(d.total_cost)}`},
                {label:'浮动盈亏',value:`${d.total_pnl>=0?'+':''}¥${fmt(d.total_pnl)}`,sub:pct(d.total_pnl_pct),cls:pnlCls,valueCls:d.total_pnl>=0?'up-text':'down-text'},
                {label:'组合VaR',value:d.portfolio_var!=null?pct(d.portfolio_var):'N/A',cls:'warn'},
                {label:'持仓数',value:d.positions.length},
            ])}</div>
            <div class="grid-2" style="margin:20px 0">
                <div class="card"><div class="card-title">盈亏分布</div><div class="chart-box"><canvas id="pnlChart"></canvas></div></div>
                <div class="card"><div class="card-title">行业集中度</div><div class="chart-box"><canvas id="secChart"></canvas></div></div>
            </div>
            ${table(
                ['标的','成本','现价','仓位','浮盈亏','VaR','回撤','操作'],
                (d.positions||[]).length ? d.positions.map(p=>`<tr>
                    <td><span class="tag tag-blue">${p.symbol}</span></td>
                    <td>${fmt(p.cost_price)}</td>
                    <td>${fmt(p.current_price)}</td>
                    <td>${d.total_market?(p.market_value/d.total_market*100).toFixed(1):0}%</td>
                    <td class="${p.pnl>=0?'up-text':'down-text'}">${p.pnl>=0?'+':''}¥${fmt(p.pnl)}<br><small>(${pct(p.pnl_pct)})</small></td>
                    <td>${p.var!=null?pct(p.var):'N/A'}</td>
                    <td>${pct(p.max_drawdown)}</td>
                    <td><button class="btn btn-sm btn-danger" onclick="rmH('${p.symbol}')">删除</button></td>
                </tr>`) : [], '暂无持仓，请点击「添加持仓」')
            }
            <div class="card" style="margin-top:14px">
                <div class="card-title">行业集中度检查</div>
                ${Object.entries(d.concentration.by_sector||{}).map(([s,w])=>`
                    <div style="display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid var(--border-light);font-size:14px">
                        <span>${s}</span>
                        <span class="${w>0.3?'down-text':''}">${(w*100).toFixed(1)}%${w>0.3?' <span class="tag tag-red">过高</span>':''}</span>
                    </div>`).join('') || '<div class="empty"><span class="empty-icon">-</span>暂无</div>'}
            </div>`;
            if (d.positions?.length) {
                new Chart($('pnlChart').getContext('2d'),{
                    type:'bar',
                    data:{labels:d.positions.map(p=>p.symbol),datasets:[{data:d.positions.map(p=>p.pnl),backgroundColor:d.positions.map(p=>p.pnl>=0?'var(--success)':'var(--danger)')}]},
                    options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{ticks:{color:'var(--text-secondary)',font:{size:12}},grid:{color:'var(--border-light)'}},y:{ticks:{color:'var(--text-secondary)',font:{size:12}},grid:{color:'var(--border-light)'}}}}
                });
                const sec = d.concentration.by_sector || {};
                if (Object.keys(sec).length) new Chart($('secChart').getContext('2d'),{
                    type:'doughnut',
                    data:{labels:Object.keys(sec),datasets:[{data:Object.values(sec).map(v=>(v*100).toFixed(1)),backgroundColor:['var(--primary)','var(--success)','var(--warning)','var(--danger)','#a855f7','#0ea5e9']}]},
                    options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:'right',labels:{color:'var(--text-secondary)',font:{size:12}}}}}
                });
            }
        },
        // 2. 信号建议（原 rk.signals）
        signals: async c => {
            const d = await fetchWithUser('/api/signals');
            c.innerHTML = (d.signals?.length ? `
            <div class="stats-grid" style="margin-bottom:16px">${statsGrid([
                {label:'买入信号',value:d.signals.filter(s=>s.type==='买入').length,cls:'up'},
                {label:'卖出信号',value:d.signals.filter(s=>s.type==='卖出').length,cls:'down'},
                {label:'总计',value:d.signals.length},
            ])}</div>` : '') +
            table(
                ['标的','信号','策略','置信度','理由'],
                (d.signals||[]).map(s=>`<tr>
                    <td><span class="tag tag-blue">${s.symbol}</span></td>
                    <td><span class="tag ${s.type==='买入'?'tag-green':s.type==='卖出'?'tag-red':'tag-gray'}">${s.type}</span></td>
                    <td>${s.strategy}</td>
                    <td>${scoreBar(Math.round(s.confidence*100))}</td>
                    <td style="color:var(--text-muted)">${s.reason}</td>
                </tr>`), '暂无信号'
            ) + `<div class="card" style="margin-top:14px"><p style="font-size:12px;color:var(--text-muted)">${d.disclaimer||''}</p></div>`;
        },
        // 3. 压力测试（原 rk.scenario）
        scenario: async c => {
            const d = await fetchWithUser('/api/scenario');
            c.innerHTML = table(
                ['情景','影响','预估损益','受影响','严重度'],
                (d.scenarios||[]).map(s=>`<tr>
                    <td><strong>${s.name}</strong></td>
                    <td class="${s.impact_pct<0?'down-text':'up-text'}">${(s.impact_pct*100).toFixed(1)}%</td>
                    <td class="${s.estimated_loss<0?'down-text':'up-text'}">${s.estimated_loss>=0?'+':''}¥${fmt(s.estimated_loss)}</td>
                    <td style="color:var(--text-muted)">${(s.affected||[]).join(', ')}</td>
                    <td>${s.severity==='极高'||s.severity==='极端'?'<span class="tag tag-red">'+s.severity+'</span>':s.severity==='高'?'<span class="tag tag-red">高</span>':s.severity==='中'?'<span class="tag tag-yellow">中</span>':'<span class="tag tag-green">利好</span>'}</td>
                </tr>`), '暂无压测数据'
            );
        },
        // 4. 调仓助手（NEW：整合告警 + rebalance API + 建议）
        rebalance: async c => {
            const [pf, rb] = await Promise.all([
                fetchWithUser('/api/portfolio'),
                fetchWithUser('/api/rebalance').catch(()=>({suggestions:[],summary:'',target_allocation:{}})),
            ]);
            const sec = pf.concentration?.by_sector || {};
            const overSecs = Object.entries(sec).filter(([,w])=>w>0.3);
            c.innerHTML = `
            <div class="card" style="margin-bottom:16px;background:linear-gradient(135deg,rgba(245,158,11,0.05),rgba(239,68,68,0.03));border:1px solid var(--warning)">
                <div class="card-title">🎯 调仓摘要</div>
                <div style="font-size:14px;line-height:1.8">${rb.summary||'暂无调仓建议'}</div>
                ${overSecs.length?`<div style="margin-top:10px;padding:10px;background:#fff7ed;border-radius:8px;border-left:3px solid var(--warning);font-size:13px"><strong>⚠️ 行业集中度风险:</strong> ${overSecs.map(([s,w])=>`${s}占 ${(w*100).toFixed(1)}%`).join('，')}，建议分散</div>`:''}
            </div>

            ${rb.target_allocation && Object.keys(rb.target_allocation).length?`
            <div class="card" style="margin-bottom:16px">
                <div class="card-title">行业目标配置对比</div>
                ${(Object.entries(rb.target_allocation||{})).map(([sec,tg])=>{
                    const cur = (pf.concentration?.by_sector?.[sec]||0);
                    const gap = (tg-cur);
                    return `<div style="padding:12px 0;border-bottom:1px solid var(--border-light)">
                        <div style="display:flex;justify-content:space-between;margin-bottom:6px">
                            <strong>${sec}</strong>
                            <span style="font-size:13px;color:var(--text-secondary)">当前 ${pct(cur)} → 目标 ${pct(tg)}</span>
                        </div>
                        <div style="position:relative;height:10px;background:var(--border-light);border-radius:4px;margin-bottom:4px">
                            <div style="position:absolute;top:0;left:0;height:100%;width:${cur*100}%;background:var(--primary);border-radius:4px;opacity:0.4"></div>
                            <div style="position:absolute;top:-2px;left:${tg*100}%;height:14px;width:3px;background:var(--success);border-radius:2px"></div>
                        </div>
                        <div style="font-size:12px;color:${gap>0?'var(--success)':gap<0?'var(--danger)':'var(--text-muted)'};font-weight:700">${gap>0?'⬆ 建议加仓':'⬇ 建议减仓'} ${pct(Math.abs(gap))}</div>
                    </div>`;
                }).join('')}
            </div>`:''}

            <div class="card">
                <div class="card-title">📋 具体调仓建议</div>
                ${(rb.suggestions||[]).length ? rb.suggestions.map(s=>`
                    <div class="alert-item ${s.priority==='high'?'high':s.priority==='medium'?'medium':'low'}" style="margin-bottom:10px">
                        <div class="alert-level">${s.side==='buy'||s.action?.includes('买')?'🟢':s.side==='sell'||s.action?.includes('卖')?'🔴':'ℹ️'}</div>
                        <div style="flex:1">
                            <div class="alert-title">${s.action} ${s.symbol||s.asset||''} <span class="tag ${s.priority==='high'?'tag-red':s.priority==='medium'?'tag-yellow':'tag-gray'}">${s.priority}</span></div>
                            <div class="alert-detail">${s.reason||s.rationale||''}</div>
                            ${s.estimated_impact_pct?`<div class="alert-meta">预计组合影响: <span class="${(s.estimated_impact_pct||0)>=0?'up-text':'down-text'}" style="font-weight:700">${pct(s.estimated_impact_pct)}</span></div>`:''}
                        </div>
                    </div>
                `).join('') : '<div class="empty"><span class="empty-icon">✅</span>当前组合合理，无需调仓</div>'}
            </div>`;
        },
    };
    await tabRenderers.pf.holdings($('pf'));
});

// ==================== 危机知识库（原 crisis 专题，14→4 分组 Tab） ====================
route('crisis', async () => {
    // 4 个大 Tab，每个内部再用二级分组
    const tabs = [
        {key:'compare',label:'危机对比'},
        {key:'radar',label:'风险预警'},
        {key:'playbook',label:'人物策略'},
        {key:'library',label:'知识库'},
    ];
    $('pageContent').innerHTML = `<div class="page-header"><div>
        <div class="page-title">危机知识库 <span class="page-badge">专题</span></div>
        <div class="page-subtitle">历史教训 · 实时预警 · 策略借鉴</div>
    </div></div>${renderTabs(tabs,'compare','cr')}`;

    tabRenderers.cr = {
        // ======= 1. 危机对比（总览/历史时间线/对比2008/跨周期） =======
        compare: async c => {
            c.innerHTML = `<div class="card" style="margin-bottom:14px">
                <div class="card-title">对比对象选择</div>
                ${renderTabs([
                    {key:'cv',label:'危机总览'},
                    {key:'tl',label:'历史时间线'},
                    {key:'cp08',label:'对比 2008'},
                    {key:'cc',label:'跨周期对比'},
                ],'cv','cr-cmp')}</div><div id="cr-cmp"></div>`;
            tabRenderers['cr-cmp'] = {
                cv: async sc => {
                    const [d,rd] = await Promise.all([fetchJSON('/api/crisis/list'),fetchJSON('/api/crisis/risk/dashboard')]);
                    const crises = d.crises;const sc2={'2008-level':'#dc2626','major':'#f59e0b','moderate':'#3b82f6'};
                    const riskColors = {low:'#10b981',moderate:'#f59e0b',elevated:'#f97316',high:'#ef4444',extreme:'#dc2626'};
                    sc.innerHTML = `
                    <div class="card" style="margin-bottom:16px;padding:20px;background:linear-gradient(135deg,#1e293b,#0f172a);color:#fff;border-radius:var(--radius)">
                        <div style="font-size:18px;font-weight:700;margin-bottom:8px">Financial Crisis Research Center</div>
                        <div style="font-size:13px;color:#94a3b8;line-height:1.6">系统研究 1929 大萧条、1997 亚洲金融风暴、2000 互联网泡沫、2008 全球金融危机和 2020 新冠崩盘，全面评估当前市场与历史危机的相似度。</div>
                    </div>
                    <div class="stats-grid">${statsGrid([
                        {label:'收录危机',value:crises.length},
                        {label:'收录机构报告',value:crises.reduce((s,c)=>s+(c.institution_reports?.length||0),0)},
                        {label:'人物行为记录',value:25},
                        {label:'当前风险等级',value:rd.current_level||'N/A',cls:rd.current_level==='high'||rd.current_level==='extreme'?'down':rd.current_level==='elevated'?'warn':''},
                    ])}</div>
                    ${table(
                        ['危机','年份','严重度','标普跌幅','持续月数','核心原因','状态'],
                        crises.map(cr=>`<tr>
                            <td><strong style="font-size:14px">${cr.name}</strong><br><small style="color:var(--text-muted)">${cr.name_en||''}</small></td>
                            <td>${cr.years||cr.year}</td>
                            <td><span class="tag" style="background:${sc2[cr.severity]||'#475569'};color:#fff">${cr.severity}</span></td>
                            <td class="down-text" style="font-weight:700">${cr.sp500_drop||'-'}</td>
                            <td>${cr.duration_months||'-'}</td>
                            <td style="color:var(--text-secondary);font-size:12px">${(cr.key_causes_zh||[]).slice(0,2).join('，')}</td>
                            <td><button class="btn btn-sm" onclick="navigate('crisis');setTimeout(()=>switchTab('cr','library');setTimeout(()=>switchTab('cr-lib','cv'),200);localStorage.setItem('target_crisis','${cr.id}')">详情 →</button></td>
                        </tr>`)
                    )}`;
                },
                tl: async sc => {
                    try {
                        // 加载第一个危机的时间线作演示
                        const d = await fetchJSON('/api/crisis/list');
                        const first = d.crises[0];
                        const tl = await fetchJSON(`/api/crisis/${first.id}/multi-timeline`);
                        sc.innerHTML = `
                        <div class="card" style="margin-bottom:14px"><div class="card-title">选择危机</div>
                            ${d.crises.map(cr=>`<span class="tag tag-gray" style="cursor:pointer;margin:3px" onclick="loadCrisisTL('${cr.id}',this)">${cr.name}</span>`).join('')}
                        </div>
                        <div id="crisisTL">${tl.phases?tl.phases.map(p=>`
                            <div style="padding:14px 0;border-bottom:1px solid var(--border-light);display:flex;gap:14px">
                                <div style="min-width:120px;text-align:right"><div style="font-weight:800;color:var(--primary)">${p.period||p.range}</div><div style="font-size:11px;color:var(--text-muted)">${p.duration||''}</div></div>
                                <div style="flex:1;border-left:2px solid var(--primary);padding-left:14px">
                                    <div style="font-weight:700;font-size:15px">${p.phase_name||p.name}</div>
                                    <div style="font-size:13px;color:var(--text-secondary);margin-top:4px;line-height:1.7">${p.description||p.desc||''}</div>
                                    ${(p.events||p.keypoints||[]).length?`<div style="margin-top:8px">${(p.events||p.keypoints).map(k=>`<div style="font-size:12px;padding:4px 0;color:var(--text-muted)">• ${k}</div>`).join('')}</div>`:''}
                                </div>
                            </div>
                        `).join('') : '<div class="empty">暂无时间线</div>'}</div>`;
                    } catch(e) { sc.innerHTML = `<div class="empty">Error: ${e.message}</div>`; }
                },
                cp08: async sc => {
                    const d = await fetchJSON('/api/crisis/compare/2008');
                    sc.innerHTML = `
                    <div class="card" style="margin-bottom:14px"><div class="card-title">2008 vs 当前 · 核心指标对比</div>
                    ${table(
                        ['指标','2008 危机','当前','差异'],
                        (d.comparisons||[]).map(c=>`<tr>
                            <td><strong>${c.metric||c.label}</strong></td>
                            <td>${c.value_2008||c['2008_value']||'-'}</td>
                            <td>${c.value_current||c.current_value||'-'}</td>
                            <td style="color:${(c.delta_direction||'')==='better'?'var(--success)':(c.delta_direction||'')==='worse'?'var(--danger)':'var(--text-muted)'};font-weight:700">${c.delta_hint||c.difference||'-'}</td>
                        </tr>`)
                    )}</div>
                    <div class="card"><div class="card-title">专家综合判断</div>
                    <p style="font-size:14px;line-height:1.8">${d.conclusion_zh||d.conclusion||'暂无'}</p></div>`;
                },
                cc: async sc => {
                    const d = await fetchJSON('/api/crisis/risk/cross-cycle');
                    sc.innerHTML = `
                    <div class="stats-grid">${statsGrid([
                        {label:'当前阶段',value:d.current_phase||'-',cls:'warn'},
                        {label:'对标年份',value:d.benchmark_year||'-'},
                        {label:'相似度',value:d.similarity?`${d.similarity}%`:'-'},
                    ])}</div>
                    <div class="card" style="margin-top:14px"><div class="card-title">跨周期指标对比</div>
                    ${table(
                        ['指标','过热期','顶部','衰退','底部','复苏','当前'],
                        (d.indicators||[]).map(i=>`<tr>
                            <td><strong>${i.name}</strong></td>
                            ${['boom','top','recession','bottom','recovery','current'].map(k=>`<td style="font-weight:${k==='current'?'800':'500'};${k==='current'?'color:var(--primary)':''}">${i[k]||i[k.toUpperCase()]||'-'}</td>`).join('')}
                        </tr>`), '暂无数据'
                    )}</div>
                    <div class="card" style="margin-top:14px"><div class="card-title">策略建议</div>
                    <div style="font-size:14px;line-height:1.8">${d.strategy_zh||d.strategy||d.conclusion||'暂无'}</div></div>`;
                },
            };
            await tabRenderers['cr-cmp'].cv($('cr-cmp'));
        },

        // ======= 2. 风险预警（风险看板/收益率曲线/估值/政策工具箱/传导/恢复） =======
        radar: async c => {
            c.innerHTML = `<div class="card" style="margin-bottom:14px"><div class="card-title">预警维度</div>
                ${renderTabs([
                    {key:'dash',label:'综合看板'},
                    {key:'yc',label:'收益率曲线'},
                    {key:'val',label:'估值杠杆'},
                    {key:'liq',label:'流动性'},
                    {key:'tb',label:'政策工具箱'},
                    {key:'rec',label:'恢复看板'},
                ],'dash','cr-rd')}</div><div id="cr-rd"></div>`;
            tabRenderers['cr-rd'] = {
                dash: async sc => {
                    const d = await fetchJSON('/api/crisis/risk/dashboard');
                    sc.innerHTML = `
                    <div class="stats-grid">${statsGrid([
                        {label:'综合风险',value:d.current_level||'-',cls:d.current_level==='high'||d.current_level==='extreme'?'down':d.current_level==='elevated'?'warn':''},
                        {label:'估值风险',value:d.valuation_risk||'-'},
                        {label:'流动性',value:d.liquidity_risk||'-'},
                        {label:'收益率曲线',value:d.yield_curve_status||'-'},
                    ])}</div>
                    <div class="card" style="margin-top:16px">
                        <div class="card-title">分项预警信号</div>
                        ${(d.signals||[]).map(s=>`
                            <div class="alert-item ${s.level==='high'||s.level==='critical'?'high':s.level==='medium'?'medium':'low'}">
                                <div class="alert-level">${s.level==='high'||s.level==='critical'?'🔴':s.level==='medium'?'🟡':'🟢'}</div>
                                <div><div class="alert-title">${s.metric||s.name}</div>
                                <div class="alert-detail">${s.value} · ${s.description||s.threshold||''}</div>
                                <div class="alert-meta">${s.advice||''}</div></div>
                            </div>`).join('') || '<div class="empty"><span class="empty-icon">✅</span>暂无预警信号</div>'}
                    </div>`;
                },
                yc: async sc => {
                    const d = await fetchJSON('/api/crisis/risk/yield-curve');
                    sc.innerHTML = `
                    <div class="stats-grid" style="margin-bottom:16px">${statsGrid([
                        {label:'10Y-2Y 利差',value:(d.yields_pct?.find(y=>y.maturity==='10Y-2Y')?.value||0).toFixed?((d.yields_pct.find(y=>y.maturity==='10Y-2Y')?.value||0).toFixed(2)+'%'):d.spread_10y_2y||'-',cls:(d.yields_pct?.find(y=>y.maturity==='10Y-2Y')?.value||0)<0?'down':''},
                        {label:'曲线形态',value:d.curve_shape||'-',cls:d.curve_shape==='inverted'?'down':d.curve_shape==='flat'?'warn':''},
                        {label:'衰退概率',value:d.recession_probability?`${d.recession_probability}%`:'-'},
                    ])}</div>
                    ${table(['期限','收益率'],(d.yields_pct||[]).map(y=>`<tr><td><strong>${y.maturity}</strong></td><td style="font-weight:800;font-size:14px">${y.value.toFixed?y.value.toFixed(2):y.value}%</td></tr>`))}
                    ${d.historical_comparison?`<div class="card" style="margin-top:16px"><div class="card-title">历史倒挂对比</div>${table(
                        ['时期','10Y-2Y 利差','结果'],
                        (d.historical_comparison.inversions||[]).map(h=>`<tr>
                            <td>${h.period}</td><td>${h.spread}</td>
                            <td style="color:var(--text-secondary)">${h.outcome_zh||h.outcome||''}</td>
                        </tr>`)
                    )}</div>`:''}`;
                },
                val: async sc => {
                    const d = await fetchJSON('/api/crisis/risk/valuation');
                    sc.innerHTML = `
                    <div class="stats-grid" style="margin-bottom:16px">${statsGrid([
                        {label:'标普 PE',value:d.sp500_pe||'-'},
                        {label:'席勒 CAPE',value:d.shiller_cape||'-',cls:(d.shiller_cape||0)>30?'warn':''},
                        {label:'巴菲特指标',value:d.buffett_indicator?`${d.buffett_indicator}%`:'-'},
                        {label:'杠杆水平',value:d.aggregate_leverage||'-'},
                    ])}</div>
                    ${table(
                        ['指标','当前','历史分位','阈值','风险'],
                        (d.metrics||[]).map(m=>`<tr>
                            <td><strong>${m.label_zh||m.label}</strong></td>
                            <td style="font-weight:700">${m.current||m.value||'-'}</td>
                            <td>${m.percentile||'-'}</td>
                            <td style="color:var(--text-muted)">${m.threshold||'-'}</td>
                            <td><span class="tag ${m.risk_level==='high'?'tag-red':m.risk_level==='elevated'?'tag-yellow':'tag-green'}">${m.risk_level||m.risk||'低'}</span></td>
                        </tr>`), '暂无估值数据'
                    )}
                    ${d.conclusion?`<div class="card" style="margin-top:16px"><div class="card-title">综合判断</div><p style="font-size:14px;line-height:1.8">${d.conclusion}</p></div>`:''}`;
                },
                liq: async sc => {
                    const d = await fetchJSON('/api/crisis/risk/liquidity');
                    sc.innerHTML = `
                    <div class="stats-grid" style="margin-bottom:16px">${statsGrid([
                        {label:'TED 利差',value:d.ted_spread||'-'},
                        {label:'OIS 利差',value:d.ois_spread||'-'},
                        {label:'压力等级',value:d.stress_level||'-',cls:d.stress_level==='high'?'down':''},
                    ])}</div>
                    ${table(['指标','当前值','阈值','状态'],
                        (d.indicators||[]).map(i=>`<tr>
                            <td><strong>${i.label_zh||i.label}</strong></td>
                            <td>${i.current||i.value}</td>
                            <td style="color:var(--text-muted)">${i.threshold||'-'}</td>
                            <td><span class="tag ${i.status==='warning'?'tag-yellow':i.status==='stress'?'tag-red':'tag-green'}">${i.status||'正常'}</span></td>
                        </tr>`), '暂无流动性数据'
                    )}`;
                },
                tb: async sc => {
                    const tools = await fetchJSON('/api/crisis/policy/toolbox');
                    const hist = await fetchJSON('/api/crisis/policy/historical').catch(()=>({responses:[]}));
                    sc.innerHTML = `
                    <div class="card" style="margin-bottom:14px"><div class="card-title">政策工具箱 · 选择组合后运行模拟</div>
                    <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:14px">
                        ${(tools.tools||[]).slice(0,8).map(t=>`
                            <label style="display:inline-flex;align-items:center;gap:6px;padding:8px 12px;border:1px solid var(--border);border-radius:var(--radius-sm);cursor:pointer;font-size:13px;transition:var(--transition-fast)" onmouseover="this.style.borderColor='var(--primary)'" onmouseout="this.style.borderColor='var(--border)'">
                                <input type="checkbox" class="pol-tool" value="${t.id||t.name}" style="accent-color:var(--primary)"> ${t.short_name||t.name_zh||t.name}
                            </label>`).join('')}
                    </div>
                    <button class="btn" onclick="runPolicySim()">运行政策模拟 →</button></div>
                    <div id="polSimResult"></div>
                    <div class="card" style="margin-top:14px">
                        <div class="card-title">历史政策应对参考</div>
                        ${(hist.responses||[]).slice(0,6).map(r=>`
                            <div style="padding:12px 0;border-bottom:1px solid var(--border-light)">
                                <div style="display:flex;justify-content:space-between;margin-bottom:4px">
                                    <strong style="font-size:14px">${r.crisis||r.period} · ${r.country||r.region}</strong>
                                    <span class="tag tag-blue">${r.policy_type||'政策'}</span>
                                </div>
                                <div style="font-size:13px;color:var(--text-secondary);line-height:1.7">${r.response_zh||r.response||r.measures?.join('，')||''}</div>
                                ${r.outcome?`<div style="font-size:12px;color:var(--text-muted);margin-top:4px">结果: ${r.outcome}</div>`:''}
                            </div>`).join('') || '<div class="empty">暂无数据</div>'}
                    </div>`;
                },
                rec: async sc => {
                    const d = await fetchJSON('/api/crisis/recovery/dashboard');
                    sc.innerHTML = `
                    <div class="stats-grid">${statsGrid([
                        {label:'当前阶段',value:d.current_phase||'-',cls:'warn'},
                        {label:'恢复进度',value:d.progress_percent?`${d.progress_percent}%`:'-'},
                        {label:'预计见底',value:d.expected_bottom||'-'},
                        {label:'政策响应',value:d.policy_response_count||0},
                    ])}</div>
                    <div class="card" style="margin-top:16px"><div class="card-title">恢复阶段指标</div>
                    ${table(['指标','危机前','底部','当前','恢复率'],
                        (d.phase_metrics||[]).map(m=>`<tr>
                            <td><strong>${m.label_zh||m.label}</strong></td>
                            <td>${m.pre_crisis||'-'}</td><td class="down-text">${m.bottom||'-'}</td>
                            <td style="font-weight:700">${m.current||'-'}</td>
                            <td>${m.recovery_rate?m.recovery_rate+'%':'-'}</td>
                        </tr>`), '暂无恢复数据'
                    )}</div>`;
                },
            };
            await tabRenderers['cr-rd'].dash($('cr-rd'));
        },

        // ======= 3. 人物策略（危机人物行为 + 机构报告入口） =======
        playbook: async c => {
            const d = await fetchJSON('/api/crisis/figures/actions');
            // 按危机分组
            const byCrisis = {};
            (d.actions||[]).forEach(a=>{
                byCrisis[a.crisis_id||a.crisis] = byCrisis[a.crisis_id||a.crisis] || [];
                byCrisis[a.crisis_id||a.crisis].push(a);
            });
            c.innerHTML = `
            <div class="card" style="margin-bottom:16px;padding:18px;background:linear-gradient(135deg,rgba(99,102,241,0.06),rgba(245,158,11,0.04));border:1px solid var(--border)">
                <div style="font-size:11px;font-weight:700;color:var(--primary);letter-spacing:1.5px;text-transform:uppercase;margin-bottom:8px">Crisis Playbook · 危机应对策略手册</div>
                <div style="font-size:13px;color:var(--text-secondary);line-height:1.7">
                    收录 <strong style="color:var(--text)">${d.total||25}</strong> 条历史关键人物/机构在危机中的行为和策略。
                    按危机分类浏览：他们在什么时点做了什么？用了什么策略？最终收益如何？—— 为当下决策提供可复用的行动剧本。
                </div>
            </div>
            <div class="stats-grid" style="margin-bottom:16px">${statsGrid([
                {label:'收录危机',value:Object.keys(byCrisis).length},
                {label:'总记录数',value:d.total||(d.actions||[]).length},
                {label:'平均收益率',value:(d.avg_gain||0)>0?'+':'-'+(Math.abs(d.avg_gain||0).toFixed(0))+'%',cls:(d.avg_gain||0)>=0?'up':'down'},
            ])}</div>
            ${Object.entries(byCrisis).map(([cid,acts])=>`
                <div class="card" style="margin-bottom:14px">
                    <div class="card-title">${(d.crisis_names||{})[cid]||cid} (${acts.length} 条)</div>
                    ${acts.sort((a,b)=>(a.gain_pct||0)<(b.gain_pct||0)?1:-1).map(a=>`
                        <div style="padding:14px 0;border-bottom:1px solid var(--border-light);display:flex;gap:14px;align-items:flex-start">
                            <div style="flex-shrink:0;min-width:80px;text-align:center;padding:8px;background:var(--surface-muted);border-radius:var(--radius-sm)">
                                <div style="font-weight:800;font-size:11px;color:var(--text-muted)">日期</div>
                                <div style="font-weight:700;font-size:12px">${a.date}</div>
                            </div>
                            <div style="flex:1;min-width:0">
                                <div style="margin-bottom:6px;display:flex;align-items:center;gap:8px;flex-wrap:wrap">
                                    <strong style="font-size:15px">${a.figure}</strong>
                                    <span class="tag tag-purple">${a.asset_class||''}</span>
                                    ${(a.tags||[]).map(t=>`<span class="tag tag-gray" style="font-size:10px">${t}</span>`).join('')}
                                </div>
                                <div style="font-size:14px;margin-bottom:4px"><strong>行动:</strong> ${a.action_zh}</div>
                                <div style="font-size:13px;color:var(--text-secondary);margin-bottom:4px"><strong>策略:</strong> ${a.strategy_zh}</div>
                                <div style="font-size:13px;color:var(--text-muted);margin-bottom:4px"><strong>结果:</strong> ${a.outcome_zh}</div>
                            </div>
                            <div style="min-width:80px;text-align:right">
                                <div class="stat-value ${(a.gain_pct||0)>=0?'up-text':'down-text'}" style="font-size:22px">${(a.gain_pct||0)>=0?'+':''}${a.gain_pct||0}%</div>
                                <div style="font-size:10px;color:var(--text-muted)">估算收益</div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            `).join('')}`;
        },

        // ======= 4. 知识库（宏观指标/金融机构/机构报告，带危机切换） =======
        library: async c => {
            c.innerHTML = `<div class="card" style="margin-bottom:14px"><div class="card-title">知识库内容</div>
                ${renderTabs([
                    {key:'cv',label:'危机详情'},
                    {key:'ma',label:'宏观指标'},
                    {key:'inst',label:'金融机构'},
                    {key:'repo',label:'机构报告'},
                ],'cv','cr-lib')}</div><div id="cr-lib"></div>`;
            tabRenderers['cr-lib'] = {
                cv: async sc => {
                    const d = await fetchJSON('/api/crisis/list');
                    const target = localStorage.getItem('target_crisis') || d.crises[0]?.id;
                    localStorage.removeItem('target_crisis');
                    const crMap = {}; d.crises.forEach(x=>crMap[x.id]=x);
                    sc.innerHTML = `
                    <div style="margin-bottom:14px;display:flex;flex-wrap:wrap;gap:6px">
                        ${d.crises.map(x=>`<span class="tag ${x.id===target?'tag-blue':'tag-gray'}" style="cursor:pointer;padding:6px 12px;font-size:12px" onclick="showCrisisDetail('${x.id}')">${x.name}</span>`).join('')}
                    </div>
                    <div id="crisisDetailBox">${await renderCrisisDetail(target)}</div>`;
                },
                ma: async sc => {
                    const d = await fetchJSON('/api/crisis/list');
                    const first = d.crises[0]?.id;
                    const md = first ? await fetchJSON(`/api/crisis/${first}/macro`) : {indicators:[]};
                    sc.innerHTML = `
                    <div style="margin-bottom:14px;display:flex;flex-wrap:wrap;gap:6px">
                        ${d.crises.map(x=>`<span class="tag tag-gray" style="cursor:pointer;padding:6px 12px;font-size:12px" onclick="loadCrisisMacro('${x.id}')">${x.name}</span>`).join('')}
                    </div>
                    <div id="crMacBox">
                        ${table(
                            ['指标','危机前','峰值/谷底','恢复','最终结果'],
                            (md.indicators||[]).map(i=>`<tr>
                                <td><strong>${i.label_zh||i.label||i.name}</strong></td>
                                <td>${i.pre_crisis||'-'}</td><td class="${i.direction==='down'?'down-text':'up-text'}">${i.peak||i.trough||i.extreme||'-'}</td>
                                <td>${i.recovery||'-'}</td>
                                <td style="color:var(--text-secondary)">${i.outcome_zh||i.final_result||'-'}</td>
                            </tr>`), '暂无宏观指标数据'
                        )}
                    </div>`;
                },
                inst: async sc => {
                    const d = await fetchJSON('/api/crisis/list');
                    const first = d.crises[0]?.id;
                    const inst = first ? await fetchJSON(`/api/crisis/${first}/institutions`) : {institutions:[]};
                    sc.innerHTML = `
                    <div style="margin-bottom:14px;display:flex;flex-wrap:wrap;gap:6px">
                        ${d.crises.map(x=>`<span class="tag tag-gray" style="cursor:pointer;padding:6px 12px;font-size:12px" onclick="loadCrisisInst('${x.id}')">${x.name}</span>`).join('')}
                    </div>
                    <div id="crInstBox">
                        ${table(
                            ['机构','状态','事件','救助/损失','后续'],
                            (inst.institutions||[]).map(i=>`<tr>
                                <td><strong>${i.name_zh||i.name}</strong></td>
                                <td><span class="tag ${i.fate==='破产'||i.fate==='倒闭'||i.fate==='被收购'?'tag-red':i.fate==='救助'||i.fate==='国有化'?'tag-yellow':'tag-green'}">${i.fate||i.status||'-'}</span></td>
                                <td style="font-size:13px">${i.key_events?.join('，')||i.event||i.event_zh||'-'}</td>
                                <td>${i.bailout||i.loss?`${i.bailout?'救 '+i.bailout+' ':''}${i.loss?'损 '+i.loss:''}`:'-'}</td>
                                <td style="font-size:12px;color:var(--text-secondary)">${i.aftermath||i.outcome||'-'}</td>
                            </tr>`), '暂无机构数据'
                        )}
                    </div>`;
                },
                repo: async sc => {
                    const d = await fetchJSON('/api/crisis/list');
                    const all = [];
                    d.crises.forEach(cr=>(cr.institution_reports||[]).forEach(r=>all.push({...r, crisis:cr.name, crisis_id:cr.id})));
                    sc.innerHTML = table(
                        ['危机','机构','标题','摘要','结论',''],
                        all.map(r=>`<tr>
                            <td><span class="tag tag-blue">${r.crisis}</span></td>
                            <td><strong>${r.institution||r.issuer}</strong></td>
                            <td style="max-width:240px">${r.title_zh||r.title||'-'}</td>
                            <td style="font-size:12px;color:var(--text-secondary);max-width:260px">${(r.summary_zh||r.summary||'').slice(0,60)}...</td>
                            <td style="font-size:12px;${r.conclusion_zh?.includes('减')||r.conclusion_zh?.includes('风险')?'color:var(--danger)':'color:var(--success)'}">${(r.conclusion_zh||r.conclusion||'').slice(0,40)}</td>
                            <td>${r.download_url?`<a href="${r.download_url}" target="_blank" class="btn btn-sm" style="padding:4px 10px;font-size:11px">${r.download_url.toLowerCase().endsWith('.pdf')?'下载PDF':'查看资源'}</a>`:'-'}</td>
                        </tr>`), '暂无机构报告'
                    );
                },
            };
            await tabRenderers['cr-lib'].cv($('cr-lib'));
        },
    };
    await tabRenderers.cr.compare($('cr'));
});

// ==================== 复盘验证（原知识与复盘，保持 4 Tab） ====================
route('review', async () => {
    const tabs = [
        {key:'kb',label:'知识沉淀'},
        {key:'review',label:'交易复盘'},
        {key:'backtest',label:'策略回测'},
        {key:'query',label:'AI 问答'},
    ];
    $('pageContent').innerHTML = `<div class="page-header"><div>
        <div class="page-title">复盘验证</div>
        <div class="page-subtitle">经验沉淀 · 策略验证 · 闭环学习</div>
    </div></div>${renderTabs(tabs,'kb','rv')}`;

    tabRenderers.rv = {
        kb: async c => { const d=await fetchJSON('/api/knowledge'); c.innerHTML=d.items.length?d.items.map(k=>`<div class="card" style="margin-bottom:12px"><div style="display:flex;justify-content:space-between;margin-bottom:8px"><strong style="font-size:15px">${k.title}</strong><span class="tag tag-blue">${k.category}</span></div><div style="font-size:12px;color:var(--text-muted);margin-bottom:8px">${k.tags}</div><div style="font-size:14px;line-height:1.7">${k.content}</div></div>`).join(''):'<div class="empty"><span class="empty-icon">-</span>暂无内容</div>'; },
        review: async c => {
            const d = await fetchWithUser('/api/review');
            const t = await fetchWithUser('/api/trades');
            // 拆出中间变量，避免多层模板嵌套的语法解析歧义（手机端 JS 引擎更敏感）
            const tradeRows = (t.trades||[]).map(x => {
                const sideCls = x.side === 'buy' ? 'tag-green' : 'tag-red';
                const oc = x.outcome || '-';
                const ocCls = (oc || '').startsWith('+') ? 'up-text' : 'down-text';
                return '<tr>' +
                    '<td><span class="tag tag-blue">' + x.symbol + '</span></td>' +
                    '<td><span class="tag ' + sideCls + '">' + x.side + '</span></td>' +
                    '<td>' + fmt(x.price) + '</td>' +
                    '<td style="color:var(--text-muted);font-size:12px">' + x.reason + '</td>' +
                    '<td>' + x.trade_date + '</td>' +
                    '<td class="' + ocCls + '" style="font-weight:700">' + oc + '</td>' +
                    '</tr>';
            });
            const tradeTableHtml = table(['标的','方向','价格','理由','日期','结果'], tradeRows, '暂无交易记录');

            // 常见错误模式
            let mistakesHtml = '<div class="empty"><span class="empty-icon">-</span>暂无</div>';
            if ((d.common_mistakes||[]).length) {
                mistakesHtml = d.common_mistakes.map(function(m){
                    return '<div class="alert-item high"><div class="alert-level">!</div><div>' +
                        '<div class="alert-title">' + m.pattern + ' (' + m.frequency + '次)</div>' +
                        '<div class="alert-detail">' + m.example + '</div>' +
                        '</div></div>';
                }).join('');
            }
            // 最佳实践模式
            let bestHtml = '<div class="empty"><span class="empty-icon">-</span>暂无</div>';
            if ((d.best_practices||[]).length) {
                bestHtml = d.best_practices.map(function(m){
                    return '<div class="alert-item medium"><div class="alert-level">+</div><div>' +
                        '<div class="alert-title">' + m.pattern + ' (' + m.frequency + '次)</div>' +
                        '<div class="alert-detail">' + m.example + '</div>' +
                        '</div></div>';
                }).join('');
            }

            c.innerHTML = '' +
            '<div class="stats-grid">' + statsGrid([
                {label:'总交易',value:d.total_trades},
                {label:'胜率',value:d.win_rate + '%',cls:d.win_rate>=50?'up':'down'},
                {label:'盈利次数',value:d.wins,cls:'up'},
                {label:'亏损次数',value:d.losses,cls:'down'},
            ]) + '</div>' +
            '<div class="grid-2" style="margin:20px 0">' +
                '<div class="card"><div class="card-title">⚠️ 常见错误模式</div>' + mistakesHtml + '</div>' +
                '<div class="card"><div class="card-title">✅ 最佳实践模式</div>' + bestHtml + '</div>' +
            '</div>' +
            tradeTableHtml;
        },
        backtest: async c => {
            const d = await fetchJSON('/api/backtest');
            const r = d.results || {};
            c.innerHTML = `
            <div class="stats-grid">${statsGrid([
                {label:'总交易',value:r.total_trades},
                {label:'胜率',value:pct(r.win_rate),cls:r.win_rate>=0.5?'up':'down'},
                {label:'最大回撤',value:pct(r.max_drawdown),cls:'down'},
                {label:'夏普比率',value:r.sharpe_ratio,cls:(r.sharpe_ratio||0)>=1?'up':''},
                {label:'年化收益',value:pct(r.annual_return),cls:r.annual_return>=0?'up':'down'},
            ])}</div>
            <div class="card" style="margin:20px 0"><div class="card-title">权益曲线</div><div class="chart-box"><canvas id="eqChart"></canvas></div></div>
            <div class="card"><p style="font-size:14px">基准对比：${d.comparison?.benchmark||'-'} (${pct(d.comparison?.benchmark_return)}) · Alpha：${pct(d.comparison?.alpha)}</p></div>`;
            if (d.equity_curve?.length) {
                setTimeout(()=>new Chart($('eqChart').getContext('2d'),{
                    type:'line',
                    data:{labels:d.equity_curve.map((_,i)=>i),datasets:[{data:d.equity_curve,borderColor:'var(--primary)',backgroundColor:'rgba(99,102,241,0.08)',fill:true,tension:0.4}]},
                    options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{display:false},y:{ticks:{color:'var(--text-secondary)',font:{size:12}},grid:{color:'var(--border-light)'}}}}
                }), 100);
            }
        },
        query: async c => {
            c.innerHTML = `
            <div class="query-box">
                <div class="form-row" style="margin-bottom:10px">
                    <div class="form-field" style="grid-column:1/-1"><label>向 AI 提问</label>
                        <input id="qIn" placeholder="如：特斯拉利空因素？黄金美元相关性？持仓行业集中度？美联储加息路径？" onkeydown="if(event.key==='Enter')ask2()"></div>
                    <div class="form-field"><button class="btn" onclick="ask2()">提问</button></div>
                </div>
                <div style="display:flex;flex-wrap:wrap;gap:6px">
                    ${['特斯拉利空因素?','黄金与美元相关性?','持仓行业集中度风险?','美联储未来加息路径?','当前类似哪次历史危机?','对科技股的估值建议?'].map(q=>`
                        <span class="tag tag-gray" style="cursor:pointer;padding:5px 10px;font-size:12px" onclick="$('qIn').value='${q}';ask2()">${q}</span>
                    `).join('')}
                </div>
            </div>
            <div id="qOut"></div>`;
        },
    };
    await tabRenderers.rv.kb($('rv'));
});

// ==================== 系统设置（新增） ====================
route('settings', async () => {
    const tabs = [
        {key:'users',label:'账户管理'},
        {key:'push',label:'推送配置'},
    ];
    $('pageContent').innerHTML = `<div class="page-header"><div>
        <div class="page-title">系统设置</div>
        <div class="page-subtitle">用户 · 推送 · 个性化</div>
    </div></div>${renderTabs(tabs,'users','st')}`;

    tabRenderers.st = {
        users: async c => {
            const [ul, cfg] = await Promise.all([
                fetchJSON('/api/users'),
                fetchJSON('/api/config').catch(()=>({config:{}})),
            ]);
            c.innerHTML = `
            <div class="stats-grid" style="margin-bottom:16px">${statsGrid([
                {label:'用户总数',value:(ul.users||[]).length},
                {label:'当前登录',value:currentUsername,cls:'up'},
                {label:'推送通道',value:cfg.push_type||'-'},
            ])}</div>
            <div class="card" style="margin-bottom:14px">
                <div class="card-title">用户列表</div>
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
                    <span style="font-size:13px;color:var(--text-secondary)">多用户独立持仓与交易记录</span>
                    <button class="btn btn-sm" onclick="createUser()">+ 添加用户</button>
                </div>
                ${table(
                    ['ID','用户名','显示名','创建时间',''],
                    (ul.users||[]).map(u=>`<tr>
                        <td>${u.id}</td><td><code style="background:var(--bg);padding:2px 6px;border-radius:4px;font-size:12px">${u.username}</code></td>
                        <td>${u.display_name||'-'}</td><td style="color:var(--text-muted);font-size:12px">${u.created_at||'-'}</td>
                        <td><button class="btn btn-sm btn-secondary" onclick="switchUser(${u.id})">${u.id===currentUserId?'● 当前':'切换'}</button></td>
                    </tr>`), '暂无用户'
                )}
            </div>
            <div class="card">
                <div class="card-title">系统信息</div>
                <div style="font-size:13px;line-height:2;color:var(--text-secondary)">
                    <div><strong style="color:var(--text)">版本:</strong> v3.0 · 决策优先架构</div>
                    <div><strong style="color:var(--text)">数据源:</strong> OpenBB · us-stock-monitor · SEC EDGAR · X/Twitter RSS</div>
                    <div><strong style="color:var(--text)">推送:</strong> PushPlus / WxPusher / Server酱</div>
                    <div><strong style="color:var(--text)">收录危机:</strong> 5 次（1929、1997、2000、2008、2020）</div>
                    <div><strong style="color:var(--text)">人物行为记录:</strong> 25 条</div>
                </div>
            </div>`;
        },
        push: async c => {
            const ps = await fetchJSON('/api/macro/push-status').catch(()=>({running:false,last_result:{}}));
            const st = await fetchJSON('/api/sentiment/status').catch(()=>({}));
            const pushStats = await fetchJSON('/api/push/stats').catch(()=>({}));
            c.innerHTML = `
            <div class="stats-grid" style="margin-bottom:16px">${statsGrid([
                {label:'宏观推送',value:ps.running?'● 运行中':'○ 已停止',cls:ps.running?'up':'warn'},
                {label:'推送间隔',value:ps.interval_seconds?`${ps.interval_seconds}s`:'-'},
                {label:'提醒窗口',value:(ps.remind_intervals||[]).map(m=>m>=1440?`${m/1440}天`:m>=60?`${m/60}时`:`${m}分`).join(' / ')||'-'},
                {label:'今日推送',value:(pushStats.today||0),cls:(pushStats.today||0)>0?'up':''},
            ])}</div>

            <div class="card" style="margin-bottom:14px">
                <div class="card-title">推送控制面板</div>
                <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px">
                    <button class="btn btn-sm" onclick="macroCheckNow(this)">⏰ 立即检查宏观</button>
                    <button class="btn btn-sm btn-success" onclick="macroPushWeekly(this)">📅 推送本周日历</button>
                    <button class="btn btn-sm btn-danger" onclick="pushHighImpact()">🔥 推送高影响舆情</button>
                    <button class="btn btn-sm btn-secondary" onclick="triggerScan()">📊 扫描持仓风险</button>
                </div>
                ${ps.last_result?.last_run?`<div style="font-size:12px;color:var(--text-muted);margin-bottom:10px">宏观上次检查: ${ps.last_result.last_run} · 推送 ${ps.last_result.pushed||0} / 跳过 ${ps.last_result.skipped||0}</div>`:''}
                <div style="font-size:12px;color:var(--text-muted)">推送配置（在 .env 设置）：
                    <code style="background:var(--bg);padding:2px 6px;border-radius:4px;margin:0 3px">PUSH_TYPE</code>
                    <code style="background:var(--bg);padding:2px 6px;border-radius:4px;margin:0 3px">PUSHPLUS_TOKEN</code>
                    <code style="background:var(--bg);padding:2px 6px;border-radius:4px;margin:0 3px">WXPUSHER_TOKEN</code>
                </div>
            </div>

            <div class="card" style="margin-bottom:14px">
                <div class="card-title">推送统计</div>
                <div style="font-size:13px;line-height:2">
                    ${pushStats.today!==undefined?`今日推送: <strong>${pushStats.today||0}</strong> 条<br>`:''}
                    ${pushStats.week!==undefined?`本周推送: <strong>${pushStats.week||0}</strong> 条<br>`:''}
                    ${pushStats.total!==undefined?`累计推送: <strong>${pushStats.total||0}</strong> 条<br>`:''}
                    冷却时间: 60 分钟 / 每日上限: 50 条
                </div>
            </div>

            <div class="card">
                <div class="card-title">环境变量参考</div>
                <div style="font-size:12px;font-family:monospace;background:var(--bg);padding:14px;border-radius:8px;line-height:1.9;overflow-x:auto">
PUSH_TYPE=pushplus<br>
PUSHPLUS_TOKEN=你的Token<br>
WXPUSHER_TOKEN=你的Token<br>
WXPUSHER_UID=你的UID<br>
SERVERCHAN_KEY=你的Key<br>
# 宏观推送间隔(秒)<br>
MACRO_PUSH_INTERVAL=300<br>
# 每日推送上限<br>
MAX_DAILY_PUSH=50<br>
ALERT_COOLDOWN_MINUTES=60
                </div>
            </div>`;
        },
    };
    await tabRenderers.st.users($('st'));
});

// ==================== 辅助函数（危机详情/切换） ====================
let _cdpCache = {};
async function renderCrisisDetail(cid) {
    if (_cdpCache[cid]) return _cdpCache[cid];
    try {
        const d = await fetchJSON(`/api/crisis/${cid}`);
        const cr = d.crisis || d;
        const html = `
        <div class="card" style="padding:20px;background:linear-gradient(135deg,var(--primary-soft),transparent);border:1px solid var(--primary-light);border-radius:var(--radius);margin-bottom:14px">
            <div style="display:flex;gap:12px;align-items:flex-start;flex-wrap:wrap">
                <div style="flex:1;min-width:260px">
                    <div style="font-size:11px;font-weight:700;color:var(--primary);letter-spacing:1.5px;text-transform:uppercase;margin-bottom:4px">${cr.severity||'Major'} · ${cr.years||cr.year||''}</div>
                    <div style="font-size:22px;font-weight:900;margin-bottom:6px">${cr.name}</div>
                    <div style="font-size:13px;color:var(--text-secondary);margin-bottom:4px">${cr.name_en||''}</div>
                    <div style="font-size:13px;color:var(--text-secondary);line-height:1.7">${cr.summary_zh||cr.summary||''}</div>
                </div>
                <div class="stats-grid" style="min-width:300px;gap:10px;margin:0">${statsGrid([
                    {label:'持续',value:`${cr.duration_months||'-'} 月`},
                    {label:'标普跌幅',value:cr.sp500_drop||'-',cls:'down'},
                    {label:'失业峰值',value:cr.unemployment_peak||'-',cls:'warn'},
                    {label:'GDP 最大降幅',value:cr.gdp_decline||'-',cls:'down'},
                ])}</div>
            </div>
        </div>
        <div class="card" style="margin-bottom:14px">
            <div class="card-title">核心原因</div>
            ${(cr.key_causes_zh||cr.key_causes||[]).map((c,i)=>`<div style="padding:10px 0;border-bottom:1px solid var(--border-light);font-size:14px"><strong style="color:var(--primary);margin-right:8px">#${i+1}</strong>${c}</div>`).join('')||'<div class="empty">暂无</div>'}
        </div>
        <div class="grid-2">
            <div class="card"><div class="card-title">关键时点</div>
            ${(cr.key_events||[]).map(e=>`<div style="padding:10px 0;border-bottom:1px solid var(--border-light)"><div style="font-weight:700">${e.date||e.time}</div><div style="font-size:13px;color:var(--text-secondary)">${e.event_zh||e.event||e.description}</div></div>`).join('')||'<div class="empty">暂无</div>'}</div>
            <div class="card"><div class="card-title">政策与应对</div>
            ${(cr.policy_responses_zh||cr.policy_responses||cr.responses||[]).map(p=>`<div style="padding:10px 0;border-bottom:1px solid var(--border-light);font-size:13px">${p}</div>`).join('')||'<div class="empty">暂无</div>'}</div>
        </div>`;
        _cdpCache[cid] = html;
        return html;
    } catch(e) { return `<div class="empty">Error: ${e.message}</div>`; }
}
async function showCrisisDetail(cid) {
    const box = $('crisisDetailBox'); if (!box) return;
    document.querySelectorAll('#cr-lib .tag').forEach(el=>{
        el.classList.toggle('tag-blue', el.textContent.trim() === (document.querySelector(`[onclick*="${cid}"]`)?.textContent?.trim()));
        el.classList.toggle('tag-gray', el.textContent.trim() !== (document.querySelector(`[onclick*="${cid}"]`)?.textContent?.trim()));
    });
    box.innerHTML = '<div class="loading"><span class="spinner"></span>加载中...</div>';
    box.innerHTML = await renderCrisisDetail(cid);
}
async function loadCrisisTL(cid, el) {
    try {
        const tl = await fetchJSON(`/api/crisis/${cid}/multi-timeline`);
        const box = $('crisisTL'); if (!box) return;
        box.innerHTML = (tl.phases||[]).map(p=>`
            <div style="padding:14px 0;border-bottom:1px solid var(--border-light);display:flex;gap:14px">
                <div style="min-width:120px;text-align:right">
                    <div style="font-weight:800;color:var(--primary)">${p.period||p.range}</div>
                    <div style="font-size:11px;color:var(--text-muted)">${p.duration||''}</div>
                </div>
                <div style="flex:1;border-left:2px solid var(--primary);padding-left:14px">
                    <div style="font-weight:700;font-size:15px">${p.phase_name||p.name}</div>
                    <div style="font-size:13px;color:var(--text-secondary);margin-top:4px;line-height:1.7">${p.description||p.desc||''}</div>
                    ${(p.events||p.keypoints||[]).length?`<div style="margin-top:8px">${(p.events||p.keypoints).map(k=>`<div style="font-size:12px;padding:4px 0;color:var(--text-muted)">• ${k}</div>`).join('')}</div>`:''}
                </div>
            </div>`).join('') || '<div class="empty">暂无时间线</div>';
    } catch(e) { showToast('加载失败: '+e.message, true); }
}
async function loadCrisisMacro(cid) {
    try {
        const md = await fetchJSON(`/api/crisis/${cid}/macro`);
        const box = $('crMacBox'); if (!box) return;
        box.innerHTML = table(['指标','危机前','峰值/谷底','恢复','最终结果'],
            (md.indicators||[]).map(i=>`<tr>
                <td><strong>${i.label_zh||i.label||i.name}</strong></td>
                <td>${i.pre_crisis||'-'}</td>
                <td class="${i.direction==='down'?'down-text':'up-text'}">${i.peak||i.trough||i.extreme||'-'}</td>
                <td>${i.recovery||'-'}</td>
                <td style="color:var(--text-secondary)">${i.outcome_zh||i.final_result||'-'}</td>
            </tr>`), '暂无数据');
    } catch(e) { showToast('加载失败: '+e.message, true); }
}
async function loadCrisisInst(cid) {
    try {
        const inst = await fetchJSON(`/api/crisis/${cid}/institutions`);
        const box = $('crInstBox'); if (!box) return;
        box.innerHTML = table(['机构','状态','事件','救助/损失','后续'],
            (inst.institutions||[]).map(i=>`<tr>
                <td><strong>${i.name_zh||i.name}</strong></td>
                <td><span class="tag ${i.fate==='破产'||i.fate==='倒闭'||i.fate==='被收购'?'tag-red':i.fate==='救助'||i.fate==='国有化'?'tag-yellow':'tag-green'}">${i.fate||i.status||'-'}</span></td>
                <td style="font-size:13px">${i.key_events?.join('，')||i.event||i.event_zh||'-'}</td>
                <td>${i.bailout||i.loss?`${i.bailout?'救 '+i.bailout+' ':''}${i.loss?'损 '+i.loss:''}`:'-'}</td>
                <td style="font-size:12px;color:var(--text-secondary)">${i.aftermath||i.outcome||'-'}</td>
            </tr>`), '暂无数据');
    } catch(e) { showToast('加载失败: '+e.message, true); }
}
function runPolicySim() {
    const sel = [...document.querySelectorAll('.pol-tool:checked')].map(x=>x.value);
    const result = $('polSimResult');
    if (!sel.length) { showToast('请至少选择一项政策工具',true); return; }
    if (!result) return;
    result.innerHTML = '<div class="loading"><span class="spinner"></span>模拟中...</div>';
    fetchJSON('/api/crisis/policy/simulate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({selected_tools:sel})})
        .then(d=>{
            const m = d.metrics || d;
            result.innerHTML = `
            <div class="card">
                <div class="card-title">📊 模拟结果 · 已选: ${sel.length} 项</div>
                <div class="stats-grid">${statsGrid([
                    {label:'GDP 影响',value:`${m.gdp_impact||0}pp`,cls:(m.gdp_impact||0)>0?'up':'down'},
                    {label:'失业变动',value:`${m.unemployment_change||0}pp`,cls:(m.unemployment_change||0)>0?'down':'up'},
                    {label:'通胀影响',value:`${m.inflation_impact||0}pp`,cls:'warn'},
                    {label:'财政成本',value:`${m.fiscal_cost||0}%`,cls:'down'},
                    {label:'信心提升',value:`${m.confidence_boost_score||0}/100`,cls:'up'},
                    {label:'副作用风险',value:`${m.side_effect_risk||0}/100`,cls:'down'},
                ])}</div>
                ${d.narrative_zh?`<div style="margin-top:12px;padding:14px;background:var(--bg);border-radius:8px;font-size:13px;color:var(--text-secondary);line-height:1.7">${d.narrative_zh}</div>`:''}
                ${d.side_effects?`<div style="margin-top:10px;font-size:12px;color:var(--text-muted)">⚠️ 副作用: ${d.side_effects}</div>`:''}
            </div>`;
        }).catch(e=>result.innerHTML = `<div class="empty">Error: ${e.message}</div>`);
}
function ask2(){
    const q = $('qIn')?.value.trim();
    if(!q) return;
    const out = $('qOut'); if(!out) return;
    out.innerHTML = '<div class="loading"><span class="spinner"></span>思考中...</div>';
    fetchJSON('/api/query',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:q})})
        .then(d=>{ out.innerHTML = (d.answers||[]).map(a=>`<div class="query-answer">${a}</div>`).join(''); })
        .catch(e=>{ out.innerHTML = `<div class="empty"><span class="empty-icon">!</span>${e.message}</div>`; });
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
        switchTab('ma','sentiment');
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
        switchTab('ma','sentiment');
    } catch(e) {
        showToast(`${e.message}`, true);
    }
}

async function toggleXAccount(username, enabled){
    try {
        await fetchJSON(`/api/sentiment/accounts/${username}?enabled=${enabled}`, {method: 'PUT'});
        showToast(enabled ? `已启用 @${username}` : `已禁用 @${username}`);
        switchTab('ma','sentiment');
    } catch(e) {
        showToast(`${e.message}`, true);
    }
}

async function removeXAccount(username){
    if(!confirm(`确定删除 @${username}?`)) return;
    try {
        await fetchJSON(`/api/sentiment/accounts/${username}`, {method: 'DELETE'});
        showToast(`已删除 @${username}`);
        switchTab('ma','sentiment');
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

// ====== 新增：持仓/选股/调仓/扫描 辅助函数 ======
function toggleAdd() {
    const f = $('addForm'); if (f) f.style.display = f.style.display==='none' ? 'block' : 'none';
}
async function addH() {
    const sym = $('hSym')?.value.trim(); const cost = parseFloat($('hCost')?.value);
    const sh = parseFloat($('hSh')?.value); const sec = $('hSec')?.value.trim() || '';
    if (!sym || !cost || !sh) return showToast('请填写完整信息', true);
    try {
        await fetchWithUser('/api/portfolio', {method:'POST',headers:{'Content-Type':'application/json'},
            body:JSON.stringify({symbol:sym,cost_price:cost,shares:sh,sector:sec})});
        showToast('已添加持仓'); toggleAdd(); switchTab('pf','holdings');
    } catch(e){ showToast(e.message, true); }
}
async function rmH(sym) {
    if (!confirm(`确定删除 ${sym}?`)) return;
    try {
        await fetchWithUser(`/api/portfolio/${sym}`, {method:'DELETE'});
        showToast('已删除'); switchTab('pf','holdings');
    } catch(e){ showToast(e.message, true); }
}
function showRebalance() { switchTab('pf','rebalance'); }
async function triggerScan() {
    try { showToast('扫描中...');
        const d = await fetchWithUser('/api/alerts/scan', {method:'POST'});
        showToast(`扫描完成，新增 ${d.new_alerts||0} 条告警`);
    } catch(e){ showToast(e.message, true); }
}
function pushHighImpact() { pushHighSentiment(); }
async function loadScreener() {
    const sec = $('scSec')?.value || 'all'; const min = parseInt($('scMin')?.value||60);
    const top = parseInt($('scTop')?.value||10); const box = $('scRes'); if(!box) return;
    box.innerHTML = '<div class="loading"><span class="spinner"></span>筛选中...</div>';
    try {
        const d = await fetchWithUser(`/api/screener?sector=${sec}&min_score=${min}&top=${top}`);
        box.innerHTML = table(
            ['标的','公司','行业','总分','估值','质量','动量','信号'],
            (d.stocks||[]).map(s=>`<tr>
                <td><span class="tag tag-blue">${s.symbol}</span></td><td>${s.company||'-'}</td>
                <td>${s.sector||'-'}</td>
                <td style="font-weight:800">${s.total_score||'-'}</td>
                <td>${scoreBar(s.val_score||0)}</td><td>${scoreBar(s.qual_score||0)}</td>
                <td>${scoreBar(s.mom_score||0)}</td>
                <td>${s.signal?`<span class="tag ${s.signal==='买入'?'tag-green':'tag-red'}">${s.signal}</span>`:'-'}</td>
            </tr>`), '暂无符合条件标的');
    } catch(e){ box.innerHTML = `<div class="empty">${e.message}</div>`; }
}
async function loadTech() {
    const sym = $('techSym')?.value?.trim() || 'AAPL'; const box = $('techRes'); if(!box) return;
    box.innerHTML = '<div class="loading"><span class="spinner"></span>技术分析中...</div>';
    try {
        const d = await fetchJSON(`/api/technical/${sym}`);
        box.innerHTML = `
        <div class="card">
            <div class="card-title">技术分析 · ${sym}</div>
            <div class="grid-3" style="margin-bottom:14px">${statsGrid([
                {label:'RSI(14)',value:d.rsi!=null?d.rsi.toFixed(1):'-',cls:(d.rsi||50)>70?'warn':(d.rsi||50)<30?'up':''},
                {label:'MACD',value:d.macd||'-',cls:(d.macd||0)>0?'up':'down'},
                {label:'趋势',value:d.trend||'-',cls:d.trend==='上涨'?'up':d.trend==='下跌'?'down':''},
            ])}</div>
            <div class="card-title">支撑与压力</div>
            <div style="font-size:13px;line-height:2">
                阻力位: <strong>${d.resistance||'-'}</strong> · 支撑位: <strong>${d.support||'-'}</strong><br>
                MA20: ${d.ma20||'-'} · MA50: ${d.ma50||'-'} · MA200: ${d.ma200||'-'}
            </div>
            ${d.summary?`<div style="margin-top:12px;padding:12px;background:var(--bg);border-radius:8px;font-size:13px;line-height:1.7">${d.summary}</div>`:''}
        </div>`;
    } catch(e){ box.innerHTML = `<div class="empty">技术分析接口暂未实现: ${e.message}</div>`; }
}

// 启动
(async () => {
    await loadUsers();
    navigate('dashboard');
})();
