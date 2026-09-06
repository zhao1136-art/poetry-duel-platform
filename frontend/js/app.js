/* AI 自动对诗平台 · 前端逻辑 */
(() => {
  "use strict";

  const LS_SESSIONS = "poetry_duel_sessions";
  const LS_HISTORY_LEGACY = "poetry_duel_history";
  const LS_SETTINGS = "poetry_duel_settings";

  const MODE_NAMES = { duilian: "对联", jielong: "接龙", changhe: "唱和", feihualing: "飞花令" };
  const MODE_EXAMPLES = {
    duilian: "例如：绿水青山 / 风声雨声读书声",
    jielong: "例如：床前明月光 / 白日依山尽",
    changhe: "例如：床前明月光 / 一首原创小诗",
    feihualing: "例如：月 / 春 / 花",
  };
  const MODE_PLACEHOLDERS = {
    duilian: "请输入上联，如：绿水青山",
    jielong: "请输入诗句，如：床前明月光",
    changhe: "请输入你的诗，AI 将以相近风格回应",
    feihualing: "请输入关键字，如：月",
  };
  const PROVIDER_NAMES = {
    cloud: "云端模型",
    local: "本地模型",
    library: "诗词库",
    mock: "内置示例",
  };
  const BADGE_TEXT = { cloud: "云端", local: "本地", mock: "示例", library: "词库" };

  const $ = (sel) => document.querySelector(sel);
  const els = {
    chat: $("#chat"),
    chatEmpty: $("#chat-empty"),
    emptyExamples: $("#empty-examples"),
    tabs: $("#mode-tabs"),
    input: $("#input"),
    send: $("#btn-send"),
    badge: $("#ai-badge"),
    settings: $("#settings"),
    settingsMask: $("#settings-mask"),
    btnSettings: $("#btn-settings"),
    btnCloseSettings: $("#btn-close-settings"),
    btnSave: $("#btn-save-settings"),
    historyPanel: $("#history-panel"),
    historyMask: $("#history-mask"),
    historyList: $("#history-list"),
    btnHistory: $("#btn-history"),
    btnNewSession: $("#btn-new-session"),
    btnClearHistory: $("#btn-clear-history"),
    btnCloseHistory: $("#btn-close-history"),
    btnMic: $("#btn-mic"),
  };

  let currentMode = "duilian";
  let streaming = false;
  let sessions = loadSessions();
  let currentSessionId = sessions.length ? sessions[0].id : null;
  let activePanel = null;

  /* ---------- 会话数据 ---------- */
  function loadSessions() {
    try {
      const raw = localStorage.getItem(LS_SESSIONS);
      if (raw) {
        const arr = JSON.parse(raw);
        if (Array.isArray(arr) && arr.length) {
          return arr
            .map(normalizeSession)
            .sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0));
        }
      }
    } catch { /* 数据损坏则走迁移 */ }
    return migrateLegacy();
  }

  function normalizeSession(s) {
    s.messages = Array.isArray(s.messages) ? s.messages : [];
    s.title = s.title || "新对诗";
    s.createdAt = s.createdAt || 0;
    s.updatedAt = s.updatedAt || s.createdAt;
    return s;
  }

  function migrateLegacy() {
    try {
      const old = JSON.parse(localStorage.getItem(LS_HISTORY_LEGACY) || "[]");
      if (!Array.isArray(old) || !old.length) return [];
      const session = {
        id: Date.now(),
        title: old.find((m) => m.role === "user")?.text?.slice(0, 10) || "对诗记录",
        createdAt: Date.now(),
        updatedAt: Date.now(),
        messages: old.map((m) => ({
          role: m.role,
          text: m.text || "",
          provider: m.meta?.provider || null,
          mode: m.meta?.mode || null,
        })),
      };
      localStorage.setItem(LS_SESSIONS, JSON.stringify([session]));
      localStorage.removeItem(LS_HISTORY_LEGACY);
      return [session];
    } catch {
      return [];
    }
  }

  function saveSessions() {
    try {
      localStorage.setItem(LS_SESSIONS, JSON.stringify(sessions.slice(0, 50)));
    } catch {
      sessions = sessions.slice(0, 20);
      localStorage.setItem(LS_SESSIONS, JSON.stringify(sessions));
    }
  }

  function getCurrent() {
    return sessions.find((s) => s.id === currentSessionId) || null;
  }

  function ensureSession() {
    if (!getCurrent()) {
      const now = Date.now();
      const s = { id: now, title: "新对诗", createdAt: now, updatedAt: now, messages: [] };
      sessions.unshift(s);
      currentSessionId = s.id;
      saveSessions();
    }
    return getCurrent();
  }

  function fmtTime(t) {
    if (!t) return "";
    const d = new Date(t);
    const pad = (n) => String(n).padStart(2, "0");
    return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }

  function summarize(text, len) {
    text = (text || "").replace(/\s+/g, " ");
    return text.length > len ? text.slice(0, len) + "…" : text;
  }

  /* ---------- 工具 ---------- */
  function b64Encode(str) {
    return btoa(unescape(encodeURIComponent(str)));
  }
  function b64Decode(str) {
    try {
      return decodeURIComponent(escape(atob(str)));
    } catch {
      return "";
    }
  }
  function loadSettings() {
    const d = JSON.parse(localStorage.getItem(LS_SETTINGS) || "{}");
    return {
      cloudUrl: d.cloudUrl || "",
      cloudKey: d.cloudKey ? b64Decode(d.cloudKey) : "",
      cloudModel: d.cloudModel || "",
      localUrl: d.localUrl || "http://localhost:11434/v1",
      localModel: d.localModel || "qwen2.5:7b",
      forceLocal: !!d.forceLocal,
    };
  }
  function saveSettings(s) {
    const payload = {
      cloudUrl: s.cloudUrl,
      cloudKey: s.cloudKey ? b64Encode(s.cloudKey) : "",
      cloudModel: s.cloudModel,
      localUrl: s.localUrl,
      localModel: s.localModel,
      forceLocal: s.forceLocal,
    };
    localStorage.setItem(LS_SETTINGS, JSON.stringify(payload));
  }
  function esc(text) {
    return text.replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }

  /* ---------- 主区渲染 ---------- */
  function renderChat() {
    els.chat.innerHTML = "";
    const session = getCurrent();
    if (!session || !session.messages.length) {
      els.chatEmpty.style.display = "";
      els.chat.appendChild(els.chatEmpty);
      return;
    }
    for (const m of session.messages) {
      appendMessageNode(m.role, m.text, m.provider ? { provider: m.provider } : null);
    }
    scrollBottom();
  }

  function createMsgNode(role, text, meta) {
    const wrap = document.createElement("div");
    wrap.className = `msg ${role}`;

    const avatar = document.createElement("div");
    avatar.className = "msg-avatar";
    avatar.textContent = role === "user" ? "我" : "AI";

    const col = document.createElement("div");
    col.className = "msg-col";

    const bubble = document.createElement("div");
    bubble.className = "msg-bubble";
    bubble.textContent = text;

    const metaEl = document.createElement("div");
    metaEl.className = "msg-meta";
    if (meta && role === "ai") {
      const tag = document.createElement("span");
      tag.className = `provider-tag ${meta.provider || ""}`;
      tag.textContent = PROVIDER_NAMES[meta.provider] || "AI";
      metaEl.appendChild(tag);
    }

    col.appendChild(bubble);
    col.appendChild(metaEl);
    wrap.appendChild(avatar);
    wrap.appendChild(col);
    return { wrap, bubble, metaEl };
  }

  function appendMessageNode(role, text, meta) {
    els.chatEmpty.style.display = "none";
    const { wrap, bubble } = createMsgNode(role, text, meta);
    els.chat.appendChild(wrap);
    scrollBottom();
    return { wrap, bubble };
  }

  function scrollBottom() {
    const stage = document.querySelector(".stage");
    stage.scrollTop = stage.scrollHeight;
  }

  /* ---------- AI 通道徽章 ---------- */
  function updateBadge(health) {
    const badge = els.badge;
    if (!health) {
      badge.textContent = "未连接";
      badge.className = "ai-badge mock";
      return;
    }
    let key;
    if (health.cloud_configured && health.cloud) key = "cloud";
    else if (health.local) key = "local";
    else key = "mock";
    badge.textContent = BADGE_TEXT[key];
    badge.className = `ai-badge ${key}`;
  }

  async function refreshHealth() {
    if (location.protocol === "file:") {
      updateBadge(null);
      return;
    }
    const s = loadSettings();
    try {
      const res = await fetch("/api/health", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          cloud_url: s.cloudUrl,
          cloud_key: s.cloudKey,
          cloud_model: s.cloudModel,
          local_url: s.localUrl,
          local_model: s.localModel,
        }),
      });
      updateBadge(await res.json());
    } catch {
      try {
        const res = await fetch("/api/health");
        updateBadge(await res.json());
      } catch {
        updateBadge(null);
      }
    }
  }

  /* ---------- file:// 打开时的引导 ---------- */
  function showFileModeHint() {
    const badge = els.badge;
    badge.textContent = "需服务访问";
    badge.className = "ai-badge mock";

    els.chatEmpty.style.display = "none";
    const { wrap } = createMsgNode(
      "ai",
      "当前以文件方式直接打开，无法连接对诗服务。\n\n请先在终端运行：\npython start_server.py\n\n然后通过 http://127.0.0.1:8000 访问本平台。",
      { provider: "mock" }
    );
    els.chat.appendChild(wrap);
    els.input.disabled = true;
    els.send.disabled = true;
    els.input.placeholder = "需通过 http://127.0.0.1:8000 访问";
  }

  /* ---------- 发送与流式 ---------- */
  async function send() {
    if (streaming || location.protocol === "file:") return;
    const content = els.input.value.trim();
    if (!content) return;

    const session = ensureSession();
    const settings = loadSettings();
    session.messages.push({ role: "user", text: content, mode: currentMode, provider: null });
    if (!session.title || session.title === "新对诗") {
      session.title = summarize(content, 10);
    }
    session.updatedAt = Date.now();
    saveSessions();

    appendMessageNode("user", content, null);
    els.input.value = "";
    els.input.focus();

    const { wrap, bubble } = appendMessageNode("ai", "", null);
    streaming = true;
    els.send.disabled = true;
    bubble.classList.add("cursor-blink");
    const metaEl = wrap.querySelector(".msg-meta");
    const tag = document.createElement("span");
    tag.className = "provider-tag";
    metaEl.appendChild(tag);

    let fullText = "";
    let provider = "";
    try {
      const res = await fetch("/api/duel/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mode: currentMode,
          content,
          force_local: settings.forceLocal,
          cloud_url: settings.cloudUrl,
          cloud_key: settings.cloudKey,
          cloud_model: settings.cloudModel,
          local_url: settings.localUrl,
          local_model: settings.localModel,
        }),
      });
      if (!res.ok || !res.body) {
        const err = await res.json().catch(() => ({ detail: "请求失败" }));
        throw new Error(err.detail || "请求失败");
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const frames = buf.split("\n\n");
        buf = frames.pop();
        for (const frame of frames) {
          const line = frame.split("\n").find((l) => l.startsWith("data:"));
          if (!line) continue;
          const data = JSON.parse(line.slice(5).trim());
          if (data.error) throw new Error(data.error);
          if (data.delta) {
            fullText += data.delta;
            bubble.textContent = fullText;
            provider = data.provider || provider;
            scrollBottom();
          }
          if (data.done) {
            provider = data.provider || provider;
          }
        }
      }
    } catch (e) {
      bubble.textContent = "对诗出错了：" + e.message;
      fullText = bubble.textContent;
    } finally {
      streaming = false;
      els.send.disabled = false;
      bubble.classList.remove("cursor-blink");
    }

    tag.textContent = PROVIDER_NAMES[provider] || "AI";
    tag.className = `provider-tag ${provider || ""}`;
    const cur = getCurrent();
    if (cur) {
      cur.messages.push({ role: "ai", text: fullText, mode: currentMode, provider });
      cur.updatedAt = Date.now();
      saveSessions();
    }
    scrollBottom();
  }

  /* ---------- 语音输入 ---------- */
  const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
  let micRec = null;
  let micOn = false;

  function setMicPlaceholder(text) {
    els.input.placeholder = text;
  }

  function micEndCleanup() {
    micOn = false;
    els.btnMic.classList.remove("listening");
    els.btnMic.title = "语音输入";
    if (els.input.placeholder === "正在聆听…") {
      setMicPlaceholder(MODE_PLACEHOLDERS[currentMode]);
    }
    els.input.focus();
  }

  function toggleMic() {
    if (micOn) {
      if (micRec) micRec.stop();
      return;
    }
    if (!SpeechRec) return;
    try {
      const r = new SpeechRec();
      r.lang = "zh-CN";
      r.interimResults = true;
      r.continuous = false;
      let hasFinal = false;

      r.onstart = () => {
        micOn = true;
        els.btnMic.classList.add("listening");
        els.btnMic.title = "点击结束录音";
        setMicPlaceholder("正在聆听…");
      };
      r.onresult = (e) => {
        let interim = "";
        for (let i = e.resultIndex; i < e.results.length; i++) {
          const res = e.results[i];
          if (res.isFinal) {
            hasFinal = true;
            els.input.value = res[0].transcript;
          } else {
            interim += res[0].transcript;
          }
        }
        if (!hasFinal && interim) els.input.value = interim;
      };
      r.onerror = (e) => {
        if (e.error === "not-allowed" || e.error === "service-not-allowed") {
          setMicPlaceholder("未获麦克风权限，请在浏览器中允许");
        } else if (e.error === "no-speech") {
          setMicPlaceholder("未听清，请再试一次");
        }
      };
      r.onend = () => {
        micRec = null;
        micEndCleanup();
      };
      micRec = r;
      r.start();
    } catch {
      els.btnMic.disabled = true;
      els.btnMic.title = "当前浏览器不支持语音输入";
    }
  }

  function initMic() {
    if (!SpeechRec || location.protocol === "file:") {
      els.btnMic.disabled = true;
      els.btnMic.title = SpeechRec ? "需通过 http 服务访问" : "当前浏览器不支持语音输入，请用 Edge/Chrome";
      return;
    }
    els.btnMic.addEventListener("click", toggleMic);
  }

  /* ---------- 模式切换 ---------- */
  function switchMode(mode) {
    currentMode = mode;
    els.tabs.querySelectorAll(".mode-tab").forEach((t) => {
      t.classList.toggle("active", t.dataset.mode === mode);
    });
    els.input.placeholder = MODE_PLACEHOLDERS[mode];
    els.emptyExamples.textContent = MODE_EXAMPLES[mode];
    els.input.focus();
  }

  /* ---------- 历史记录面板 ---------- */
  function openHistory() {
    closePanel("settings");
    renderHistoryList();
    els.historyPanel.hidden = false;
    els.historyMask.hidden = false;
    activePanel = "history";
  }
  function closeHistory() {
    els.historyPanel.hidden = true;
    els.historyMask.hidden = true;
    if (activePanel === "history") activePanel = null;
  }

  function renderHistoryList() {
    const list = els.historyList;
    list.innerHTML = "";
    const sorted = [...sessions].sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0));
    if (!sorted.length) {
      list.innerHTML = '<p class="hist-empty">暂无对诗记录，先来对一句吧</p>';
      return;
    }
    for (const s of sorted) {
      const last = s.messages[s.messages.length - 1];
      const lastText = last ? summarize(last.text, 16) : "";
      const mode = last?.mode || s.messages.find((m) => m.mode)?.mode || "";
      const item = document.createElement("div");
      item.className = "hist-item" + (s.id === currentSessionId ? " active" : "");
      item.dataset.id = s.id;
      item.innerHTML = `
        <div class="hist-head">
          <span class="hist-title">${esc(s.title)}</span>
          <span class="hist-time">${fmtTime(s.updatedAt)}</span>
        </div>
        <div class="hist-sub">
          ${mode ? `<span class="hist-mode">${MODE_NAMES[mode] || mode}</span>` : ""}
          <span class="hist-summary">${esc(lastText) || "（空会话）"} · ${s.messages.length} 条</span>
        </div>
        <button class="hist-del" data-del="${s.id}" title="删除此会话" aria-label="删除会话">✕</button>`;
      list.appendChild(item);
    }
  }

  function switchSession(id) {
    if (!sessions.some((s) => s.id === id)) return;
    currentSessionId = id;
    renderChat();
    renderHistoryList();
  }

  function deleteSession(id) {
    sessions = sessions.filter((s) => s.id !== id);
    if (currentSessionId === id) {
      currentSessionId = sessions.length ? sessions[0].id : null;
    }
    saveSessions();
    renderChat();
    renderHistoryList();
  }

  function clearAllHistory() {
    sessions = [];
    currentSessionId = null;
    saveSessions();
    renderChat();
    renderHistoryList();
  }

  function newSession() {
    const now = Date.now();
    const s = { id: now, title: "新对诗", createdAt: now, updatedAt: now, messages: [] };
    sessions.unshift(s);
    currentSessionId = s.id;
    saveSessions();
    renderChat();
    renderHistoryList();
    els.input.focus();
    return s;
  }

  /* ---------- 设置面板 ---------- */
  function openSettings() {
    closePanel("history");
    const s = loadSettings();
    $("#set-cloud-url").value = s.cloudUrl;
    $("#set-cloud-key").value = s.cloudKey;
    $("#set-cloud-model").value = s.cloudModel;
    $("#set-local-url").value = s.localUrl;
    $("#set-local-model").value = s.localModel;
    $("#set-force-local").checked = s.forceLocal;
    els.settings.hidden = false;
    els.settingsMask.hidden = false;
    activePanel = "settings";
  }
  function closeSettings() {
    els.settings.hidden = true;
    els.settingsMask.hidden = true;
    if (activePanel === "settings") activePanel = null;
  }
  function closePanel(name) {
    if (name === "settings") closeSettings();
    if (name === "history") closeHistory();
  }
  function applySettings() {
    const s = {
      cloudUrl: $("#set-cloud-url").value.trim(),
      cloudKey: $("#set-cloud-key").value.trim(),
      cloudModel: $("#set-cloud-model").value.trim(),
      localUrl: $("#set-local-url").value.trim(),
      localModel: $("#set-local-model").value.trim(),
      forceLocal: $("#set-force-local").checked,
    };
    saveSettings(s);
    closeSettings();
    refreshHealth();
  }

  /* ---------- 初始化 ---------- */
  function init() {
    els.tabs.addEventListener("click", (e) => {
      const btn = e.target.closest(".mode-tab");
      if (btn) switchMode(btn.dataset.mode);
    });
    els.send.addEventListener("click", send);
    els.input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        send();
      }
    });
    els.btnSettings.addEventListener("click", openSettings);
    els.btnCloseSettings.addEventListener("click", closeSettings);
    els.settingsMask.addEventListener("click", closeSettings);
    els.btnSave.addEventListener("click", applySettings);

    els.btnHistory.addEventListener("click", openHistory);
    els.btnCloseHistory.addEventListener("click", closeHistory);
    els.historyMask.addEventListener("click", closeHistory);
    els.btnNewSession.addEventListener("click", newSession);
    let clearArmed = false;
    els.btnClearHistory.addEventListener("click", () => {
      if (!sessions.length) return;
      if (!clearArmed) {
        clearArmed = true;
        els.btnClearHistory.textContent = "确认清空？";
        els.btnClearHistory.classList.add("armed");
        setTimeout(() => {
          clearArmed = false;
          els.btnClearHistory.textContent = "清空";
          els.btnClearHistory.classList.remove("armed");
        }, 3000);
        return;
      }
      clearArmed = false;
      els.btnClearHistory.textContent = "清空";
      els.btnClearHistory.classList.remove("armed");
      clearAllHistory();
    });
    els.historyList.addEventListener("click", (e) => {
      const del = e.target.closest("[data-del]");
      if (del) {
        e.stopPropagation();
        deleteSession(Number(del.dataset.del));
        return;
      }
      const item = e.target.closest(".hist-item");
      if (item) switchSession(Number(item.dataset.id));
    });

    switchMode("duilian");
    initMic();
    renderChat();
    if (location.protocol === "file:") {
      showFileModeHint();
    } else {
      refreshHealth();
    }
  }

  init();
})();
