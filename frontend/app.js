/**
 * Дневной лимит — frontend
 * Donut-чарты, кольцо лимита, чат с chips
 */

const API_BASE =
    typeof window !== "undefined" && window.location.port === "8000"
        ? ""
        : "http://127.0.0.1:8000";

const CAT_COLORS = [
    "#FFDD2D",
    "#64D2FF",
    "#BF5AF2",
    "#FF9F0A",
    "#30D158",
    "#FF453A",
    "#FF375F",
    "#5E5CE6",
];

let currentProfile = "profile_1";
let lastCategories = [];

// ——— Navigation ———
document.querySelectorAll(".nav-btn").forEach((btn) => {
    btn.addEventListener("click", () => switchScreen(btn.dataset.screen));
});

document.querySelectorAll("[data-goto]").forEach((btn) => {
    btn.addEventListener("click", () => switchScreen(btn.dataset.goto));
});

function switchScreen(name) {
    document.querySelectorAll(".screen").forEach((s) => s.classList.remove("active"));
    document.querySelectorAll(".nav-btn").forEach((b) => b.classList.remove("active"));
    const screen = document.getElementById(`screen-${name}`);
    if (screen) screen.classList.add("active");
    const nav = document.querySelector(`.nav-btn[data-screen="${name}"]`);
    if (nav) nav.classList.add("active");
}

// ——— API ———
async function apiGet(path) {
    const res = await fetch(`${API_BASE}${path}`);
    if (!res.ok) throw new Error(`API ${res.status}`);
    return res.json();
}

async function apiPost(path, body) {
    const res = await fetch(`${API_BASE}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`API ${res.status}`);
    return res.json();
}

function fmt(n) {
    if (n == null || Number.isNaN(Number(n))) return "—";
    return Math.round(Number(n)).toLocaleString("ru-RU");
}

// ——— Donut (SVG arcs) ———
function polar(cx, cy, r, angleDeg) {
    const a = ((angleDeg - 90) * Math.PI) / 180;
    return [cx + r * Math.cos(a), cy + r * Math.sin(a)];
}

function arcPath(cx, cy, r, startAngle, endAngle) {
    const [x1, y1] = polar(cx, cy, r, endAngle);
    const [x2, y2] = polar(cx, cy, r, startAngle);
    const large = endAngle - startAngle > 180 ? 1 : 0;
    return `M ${x1} ${y1} A ${r} ${r} 0 ${large} 0 ${x2} ${y2}`;
}

function renderDonut(svgEl, legendEl, categories, options = {}) {
    if (!svgEl) return;
    const total = categories.reduce((s, c) => s + c.total, 0) || 1;
    const cx = 100;
    const cy = 100;
    const r = options.r || 70;
    const stroke = options.stroke || 28;

    svgEl.innerHTML = "";
    // background ring
    const bg = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    bg.setAttribute("cx", cx);
    bg.setAttribute("cy", cy);
    bg.setAttribute("r", r);
    bg.setAttribute("fill", "none");
    bg.setAttribute("stroke", "#2c2c2e");
    bg.setAttribute("stroke-width", stroke);
    svgEl.appendChild(bg);

    let angle = 0;
    const slices = [];

    categories.forEach((c, i) => {
        const share = c.total / total;
        const sweep = Math.max(share * 360, share > 0 ? 2 : 0);
        const start = angle;
        const end = angle + sweep;
        angle = end;

        const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
        path.setAttribute("d", arcPath(cx, cy, r, start, end));
        path.setAttribute("fill", "none");
        path.setAttribute("stroke", CAT_COLORS[i % CAT_COLORS.length]);
        path.setAttribute("stroke-width", stroke);
        path.setAttribute("stroke-linecap", "butt");
        path.classList.add("donut-slice");
        path.dataset.index = String(i);
        path.dataset.name = c.name;
        path.dataset.total = String(c.total);
        path.dataset.share = String(Math.round(share * 100));

        path.addEventListener("mouseenter", () => highlightSlice(i, svgEl, legendEl));
        path.addEventListener("mouseleave", () => clearHighlight(svgEl, legendEl));
        path.addEventListener("click", () => highlightSlice(i, svgEl, legendEl));

        svgEl.appendChild(path);
        slices.push({ path, cat: c, color: CAT_COLORS[i % CAT_COLORS.length] });
    });

    if (legendEl) {
        legendEl.innerHTML = "";
        categories.forEach((c, i) => {
            const pct = Math.round((c.total / total) * 100);
            const row = document.createElement("div");
            row.className = "legend-row";
            row.dataset.index = String(i);
            row.innerHTML = `
                <span class="legend-dot" style="background:${CAT_COLORS[i % CAT_COLORS.length]}"></span>
                <span class="legend-name">${c.name}</span>
                <span class="legend-amt">${fmt(c.total)} ₽</span>
                <span class="legend-pct">${pct}%</span>
            `;
            row.addEventListener("mouseenter", () => highlightSlice(i, svgEl, legendEl));
            row.addEventListener("mouseleave", () => clearHighlight(svgEl, legendEl));
            legendEl.appendChild(row);
        });
    }
}

function highlightSlice(index, svgEl, legendEl) {
    svgEl.querySelectorAll(".donut-slice").forEach((el) => {
        const i = Number(el.dataset.index);
        el.classList.toggle("hot", i === index);
        el.classList.toggle("dim", i !== index);
    });
    if (legendEl) {
        legendEl.querySelectorAll(".legend-row").forEach((el) => {
            el.classList.toggle("hot", Number(el.dataset.index) === index);
        });
    }
    const tip = document.getElementById("donutTooltip");
    if (tip) {
        const slice = svgEl.querySelector(`.donut-slice[data-index="${index}"]`);
        if (slice) {
            tip.hidden = false;
            tip.innerHTML = `<strong>${slice.dataset.name}</strong>${fmt(Number(slice.dataset.total))} ₽ · ${slice.dataset.share}%`;
        }
    }
}

function clearHighlight(svgEl, legendEl) {
    svgEl.querySelectorAll(".donut-slice").forEach((el) => {
        el.classList.remove("hot", "dim");
    });
    if (legendEl) {
        legendEl.querySelectorAll(".legend-row").forEach((el) => el.classList.remove("hot"));
    }
    const tip = document.getElementById("donutTooltip");
    if (tip) tip.hidden = true;
}

function setLimitRing(spentRatio) {
    const fg = document.getElementById("limitRingFg");
    if (!fg) return;
    const circ = 2 * Math.PI * 52; // ~326.7
    const clamped = Math.min(Math.max(spentRatio, 0), 1);
    const offset = circ * (1 - clamped);
    fg.style.strokeDasharray = String(circ);
    fg.style.strokeDashoffset = String(offset);
    fg.style.stroke = clamped > 1 ? "#FF453A" : clamped > 0.85 ? "#FF9F0A" : "#FFDD2D";
}

// ——— Profiles ———
function resetChatForProfile() {
    const chatBox = document.getElementById("chatBox");
    if (!chatBox) return;
    chatBox.innerHTML = "";
    const welcome = document.createElement("div");
    welcome.className = "chat-message chat-assistant";
    welcome.textContent =
        "Привет! Спроси про лимит, траты, цель или «что если куплю…».";
    chatBox.appendChild(welcome);
    const badge = document.getElementById("modeBadge");
    if (badge) {
        badge.hidden = true;
        badge.textContent = "";
    }
    const whatIfResult = document.getElementById("whatIfResult");
    if (whatIfResult) whatIfResult.hidden = true;
    const whatIfAmount = document.getElementById("whatIfAmount");
    if (whatIfAmount) whatIfAmount.value = "";
}

async function loadProfiles() {
    const profiles = await apiGet("/profiles");
    const switcher = document.getElementById("profileSwitcher");
    switcher.innerHTML = "";
    const select = document.createElement("select");
    select.className = "profile-select";
    select.id = "profileSelect";
    select.setAttribute("aria-label", "Выбор профиля");
    profiles.forEach((p) => {
        const opt = document.createElement("option");
        opt.value = p.id;
        opt.textContent = p.name;
        if (p.id === currentProfile) opt.selected = true;
        select.appendChild(opt);
    });
    select.addEventListener("change", () => {
        currentProfile = select.value;
        resetChatForProfile();
        refreshAll();
    });
    switcher.appendChild(select);
}

// ——— Summary ———

function fillFormula(daily) {
    const ids = ["fBalance", "fSubs", "fReserve", "fAvailable", "fDays", "fLimit"];
    if (!daily || !daily.ok) {
        ids.forEach((id) => { const el = document.getElementById(id); if (el) el.textContent = "—"; });
        return;
    }
    const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
    set("fBalance", `${fmt(daily.balance)} ₽`);
    set("fSubs", `− ${fmt(daily.subscriptions_total)} ₽`);
    set("fReserve", `− ${fmt(daily.reserve)} ₽`);
    set("fAvailable", `${fmt(daily.available)} ₽`);
    set("fDays", `${daily.days_left}`);
    set("fLimit", `${fmt(daily.daily_limit)} ₽`);
}


function renderAiBrief(insights) {
    const title = document.getElementById("aiBriefTitle");
    const conclusion = document.getElementById("aiBriefConclusion");
    const cardsEl = document.getElementById("aiCards");
    if (!title || !cardsEl) return;
    if (!insights || !insights.ok) {
        title.textContent = "Разбор пока недоступен";
        if (conclusion) conclusion.textContent = "";
        cardsEl.innerHTML = "";
        return;
    }
    title.textContent = insights.problem || "Разбор на сегодня";
    if (conclusion) conclusion.textContent = insights.conclusion || "";
    cardsEl.innerHTML = "";
    (insights.cards || []).forEach((c) => {
        const div = document.createElement("div");
        div.className = "ai-card" + (c.kind === "warning" ? " warning" : "");
        div.innerHTML = `
            <div class="ai-card-title">${escapeHtml(c.title || "")}</div>
            <div class="ai-card-body">${escapeHtml(c.body || "")}</div>
        `;
        cardsEl.appendChild(div);
    });
}

async function loadSummary() {
    const data = await apiGet(`/profile/${currentProfile}/summary`);
    lastSummary = data;
    renderAiBrief(data.ai_insights);
    const daily = data.daily_limit;

    if (daily.ok) {
        document.getElementById("dailyLimit").textContent = fmt(daily.daily_limit);
        document.getElementById("dailyLimitSub").textContent =
            `На ${daily.days_left} дн. · платежи ${fmt(daily.subscriptions_total)} ₽ · резерв ${fmt(daily.reserve)} ₽`;
        document.getElementById("balance").textContent = `${fmt(daily.balance)} ₽`;
        document.getElementById("daysLeft").textContent = `${daily.days_left} дн.`;
        document.getElementById("subscriptions").textContent = `${fmt(daily.subscriptions_total)} ₽`;
        document.getElementById("reserve").textContent = `${fmt(daily.reserve)} ₽`;

        const hint = data.proactive_hint;
        const spent = hint && hint.ok ? hint.today_spent || 0 : 0;
        const ratio = daily.daily_limit > 0 ? spent / daily.daily_limit : 0;
        setLimitRing(ratio);
    } else {
        document.getElementById("dailyLimit").textContent = "—";
        document.getElementById("dailyLimitSub").textContent = daily.reason || "Нет данных";
        setLimitRing(0);
    }

    const hintEl = document.getElementById("proactiveHint");
    if (data.proactive_hint && data.proactive_hint.ok && data.proactive_hint.text) {
        hintEl.textContent = data.proactive_hint.text;
        hintEl.classList.add("show");
    } else if (data.proactive_hint && data.proactive_hint.text) {
        hintEl.textContent = data.proactive_hint.text;
        hintEl.classList.add("show");
    } else {
        hintEl.classList.remove("show");
    }

    // Categories + donuts
    const cats = data.categories;
    if (cats.ok && cats.categories && cats.categories.length) {
        lastCategories = cats.categories;
        document.getElementById("donutTotal").textContent = `${fmt(cats.total)} ₽`;
        document.getElementById("categoriesTotal").textContent = `${fmt(cats.total)} ₽`;

        renderDonut(
            document.getElementById("mainDonut"),
            document.getElementById("donutLegend"),
            cats.categories
        );
        renderDonut(
            document.getElementById("catsDonut"),
            document.getElementById("catsLegend"),
            cats.categories
        );

        const list = document.getElementById("categoriesList");
        list.innerHTML = "";
        const maxTotal = Math.max(...cats.categories.map((c) => c.total), 1);
        cats.categories.forEach((c, i) => {
            const color = CAT_COLORS[i % CAT_COLORS.length];
            const width = Math.round((c.total / maxTotal) * 100);
            const txs = c.transactions || [];
            const div = document.createElement("div");
            div.className = "category-item" + (c.over_limit ? " overspend" : "");
            div.innerHTML = `
                <div class="cat-head">
                    <span class="category-name">${escapeHtml(c.name)}</span>
                    <span class="category-amount">${fmt(c.total)} ₽</span>
                </div>
                <div class="cat-bar-track">
                    <div class="cat-bar-fill" style="width:${width}%;background:${color}"></div>
                </div>
                <div class="cat-meta">
                    <span>${c.count} опер. · ${Math.round(c.share * 100)}%</span>
                    ${c.over_limit ? '<span class="badge-over">перерасход</span>' : "<span></span>"}
                </div>
                ${txs.length ? `
                <button type="button" class="cat-toggle" data-cat="${i}" aria-expanded="false">
                    Показать операции (${txs.length}) ▾
                </button>
                <div class="cat-tx-list" id="cat-tx-${i}" hidden>
                    ${txs.map((t) => `
                        <div class="cat-tx">
                            <div class="cat-tx-main">
                                <span class="cat-tx-desc">${escapeHtml(t.description || c.name)}</span>
                                <span class="cat-tx-amt">${fmt(t.amount)} ₽</span>
                            </div>
                            <div class="cat-tx-meta">${escapeHtml(t.date_ru || t.date || "")}</div>
                        </div>
                    `).join("")}
                </div>` : ""}
            `;
            list.appendChild(div);
        });
        list.querySelectorAll(".cat-toggle").forEach((btn) => {
            btn.addEventListener("click", () => {
                const id = btn.dataset.cat;
                const box = document.getElementById(`cat-tx-${id}`);
                if (!box) return;
                const open = !box.hidden;
                box.hidden = open;
                btn.setAttribute("aria-expanded", open ? "false" : "true");
                const n = box.querySelectorAll(".cat-tx").length;
                btn.textContent = open ? `Показать операции (${n}) ▾` : "Скрыть операции ▴";
            });
        });
    } else {
        document.getElementById("donutTotal").textContent = "—";
        document.getElementById("categoriesTotal").textContent = "—";
        document.getElementById("categoriesList").innerHTML =
            '<div class="empty-state">Нет данных о тратах</div>';
    }

    // Goal
    const goal = data.goal;
    const goalDiv = document.getElementById("goalContent");
    if (goal.ok) {
        const percent = Math.round((goal.progress || 0) * 100);
        const circ = 2 * Math.PI * 52;
        const offset = circ * (1 - Math.min(percent / 100, 1));
        goalDiv.innerHTML = `
            <div class="card">
                <div class="goal-name">${goal.name}</div>
                <div class="goal-ring-wrap">
                    <svg class="goal-ring" viewBox="0 0 120 120">
                        <circle class="ring-bg" cx="60" cy="60" r="52"/>
                        <circle class="ring-fg" cx="60" cy="60" r="52"
                            stroke-dasharray="${circ}" stroke-dashoffset="${offset}"
                            style="stroke:#FFDD2D;stroke-width:10;fill:none;stroke-linecap:round"/>
                    </svg>
                    <div class="goal-center">
                        <div class="goal-pct">${percent}%</div>
                    </div>
                </div>
                <div class="goal-row"><span>Накоплено</span><span>${fmt(goal.saved)} ₽</span></div>
                <div class="goal-row"><span>Цель</span><span>${fmt(goal.target)} ₽</span></div>
                <div class="goal-row"><span>Осталось</span><span>${fmt(goal.remaining)} ₽</span></div>
                ${
                    goal.needed_per_day
                        ? `<div class="goal-row"><span>Нужно в день</span><span>${fmt(goal.needed_per_day)} ₽</span></div>`
                        : ""
                }
                ${goal.warning ? `<div class="goal-warn">${goal.warning}</div>` : ""}
            </div>
        `;
    } else {
        goalDiv.innerHTML = `<div class="card empty-state">${goal.reason || "Цель не задана"}</div>`;
    }

    // Risks — карточки с раскрытием списка операций
    const risks = data.risks;
    const risksList = document.getElementById("risksList");
    risksList.innerHTML = "";
    if (risks.ok && risks.risks && risks.risks.length > 0) {
        risks.risks.forEach((r, idx) => {
            const div = document.createElement("div");
            div.className = `risk-item ${r.severity || "low"}`;
            const title = r.title || "Риск";
            const details = r.details || {};
            const txs = details.transactions || [];
            const why = details.why || "";
            let body = `<div class="risk-title">${escapeHtml(title)}</div>`;
            body += `<div class="risk-message">${escapeHtml(r.message || "")}</div>`;
            if (why) {
                body += `<div class="risk-why">${escapeHtml(why)}</div>`;
            }
            if (txs.length) {
                body += `
                <button type="button" class="risk-toggle" data-risk="${idx}" aria-expanded="false">
                    Показать операции (${txs.length}) ▾
                </button>
                <div class="risk-tx-list" id="risk-tx-${idx}" hidden>
                    ${txs.map((t) => `
                        <div class="risk-tx">
                            <div class="risk-tx-main">
                                <span class="risk-tx-desc">${escapeHtml(t.description || t.category || "")}</span>
                                <span class="risk-tx-amt">${fmt(t.amount)} ₽</span>
                            </div>
                            <div class="risk-tx-meta">${escapeHtml(t.date_ru || t.date || "")} · ${escapeHtml(t.category || "")}</div>
                        </div>
                    `).join("")}
                </div>`;
            }
            body += `<div class="risk-severity">${escapeHtml(r.severity || "")}</div>`;
            div.innerHTML = body;
            risksList.appendChild(div);
        });
        risksList.querySelectorAll(".risk-toggle").forEach((btn) => {
            btn.addEventListener("click", () => {
                const id = btn.dataset.risk;
                const list = document.getElementById(`risk-tx-${id}`);
                const open = list && !list.hidden;
                if (list) list.hidden = open;
                btn.setAttribute("aria-expanded", open ? "false" : "true");
                btn.textContent = open
                    ? `Показать операции (${list.querySelectorAll(".risk-tx").length}) ▾`
                    : `Скрыть операции ▴`;
            });
        });
    } else {
        risksList.innerHTML = '<div class="card empty-state">Явных рисков не найдено</div>';
    }
}

function escapeHtml(s) {
    return String(s)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

// ——— Chat ———
const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");
const chatBox = document.getElementById("chatBox");
const chatSend = document.getElementById("chatSend");

chatForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const message = chatInput.value.trim();
    if (!message) return;
    await sendChat(message);
});

document.getElementById("quickChips").addEventListener("click", (e) => {
    const chip = e.target.closest(".chip");
    if (!chip) return;
    sendChat(chip.dataset.q);
});

async function sendChat(message) {
    addChatMessage(message, "user");
    chatInput.value = "";
    chatSend.disabled = true;
    try {
        const res = await apiPost(`/profile/${currentProfile}/chat`, { message });
        addChatMessage(res.answer, "assistant");
        const badge = document.getElementById("modeBadge");
        if (badge) {
            if (res.mode === "gigachat") {
                badge.hidden = true;
            } else {
                badge.hidden = false;
                badge.textContent = "Нет доступа к GigaChat — чат временно недоступен";
                badge.className = "mode-badge mode-off";
            }
        }
    } catch (err) {
        addChatMessage(`Ошибка: ${err.message}. Запущен ли backend на :8000?`, "assistant");
    } finally {
        chatSend.disabled = false;
        chatInput.focus();
    }
}

function addChatMessage(text, role) {
    const wrapper = document.createElement("div");
    wrapper.className = `chat-message chat-${role}`;
    wrapper.textContent = text;
    if (role === "assistant" && text.length > 80) {
        const note = document.createElement("div");
        note.className = "chat-note";
        note.textContent = "Не является финансовой рекомендацией";
        wrapper.appendChild(note);
    }
    chatBox.appendChild(wrapper);
    chatBox.scrollTop = chatBox.scrollHeight;
}

async function refreshAll() {
    try {
        await loadSummary();
    } catch (err) {
        console.error(err);
        document.getElementById("dailyLimitSub").textContent =
            "Не удалось загрузить данные. Запустите backend: uvicorn main:app --port 8000";
    }
}


/* Formula toggle */
(function () {
    const formulaToggle = document.getElementById("formulaToggle");
    const formulaBox = document.getElementById("formulaBox");
    if (formulaToggle && formulaBox) {
        formulaToggle.addEventListener("click", () => {
            const open = !formulaBox.hidden;
            formulaBox.hidden = open;
            formulaToggle.textContent = open ? "Как посчитан лимит? ▾" : "Как посчитан лимит? ▴";
        });
    }
})();

/* What-if on main */
(function () {
    const whatIfBtn = document.getElementById("whatIfBtn");
    const whatIfAmount = document.getElementById("whatIfAmount");
    const whatIfResult = document.getElementById("whatIfResult");
    if (!whatIfBtn) return;
    async function runWhatIf() {
        const amount = Number(whatIfAmount && whatIfAmount.value);
        if (!amount || amount <= 0) {
            if (whatIfResult) {
                whatIfResult.hidden = false;
                whatIfResult.textContent = "Введи сумму больше нуля.";
            }
            return;
        }
        whatIfBtn.disabled = true;
        try {
            const res = await apiPost(`/profile/${currentProfile}/chat`, {
                message: `Что если потратить ${amount} рублей?`,
            });
            if (whatIfResult) {
                whatIfResult.hidden = false;
                whatIfResult.textContent = res.answer;
            }
        } catch (e) {
            if (whatIfResult) {
                whatIfResult.hidden = false;
                whatIfResult.textContent = `Ошибка: ${e.message}`;
            }
        } finally {
            whatIfBtn.disabled = false;
        }
    }
    whatIfBtn.addEventListener("click", runWhatIf);
    if (whatIfAmount) {
        whatIfAmount.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                runWhatIf();
            }
        });
    }
})();

(async function init() {
    try {
        await loadProfiles();
    } catch (e) {
        console.error(e);
    }
    await refreshAll();
})();
