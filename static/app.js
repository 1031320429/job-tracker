const STATUS_LABELS = {
  wishlist: "想投",
  applied: "已投递",
  oa: "笔试/测评",
  interview: "面试中",
  offer: "拿到 Offer",
  rejected: "被拒",
  ghosted: "已读不回",
  withdrawn: "已放弃",
};
const STATUS_ORDER = Object.keys(STATUS_LABELS);

let currentStatusFilter = "";
let currentSearch = "";
let resumes = [];
const DOW_LABELS = ["一", "二", "三", "四", "五", "六", "日"];

const $ = (id) => document.getElementById(id);

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || "请求失败");
  }
  if (res.status === 204) return null;
  return res.json();
}

function fmtDate(d) {
  if (!d) return "—";
  return d;
}

function renderStatusFilters() {
  const wrap = $("statusFilters");
  wrap.innerHTML = "";
  const allChip = document.createElement("span");
  allChip.className = "chip" + (currentStatusFilter === "" ? " active" : "");
  allChip.textContent = "全部";
  allChip.onclick = () => { currentStatusFilter = ""; refresh(); };
  wrap.appendChild(allChip);
  for (const s of STATUS_ORDER) {
    const chip = document.createElement("span");
    chip.className = "chip" + (currentStatusFilter === s ? " active" : "");
    chip.textContent = STATUS_LABELS[s];
    chip.onclick = () => { currentStatusFilter = s; refresh(); };
    wrap.appendChild(chip);
  }
}

function renderStats(stats) {
  $("topbarStatNum").textContent = stats.by_status.applied || 0;

  const wrap = $("stats");
  wrap.innerHTML = "";
  const cards = STATUS_ORDER.filter((s) => stats.by_status[s]).map((s) => ({
    label: STATUS_LABELS[s],
    num: stats.by_status[s],
  }));
  for (const c of cards) {
    const card = document.createElement("div");
    card.className = "stat-card";
    card.innerHTML = `<div class="num">${c.num}</div><div class="label">${c.label}</div>`;
    wrap.appendChild(card);
  }
}

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const URL_RE = /^https?:\/\//i;

function isEmail(value) {
  return EMAIL_RE.test(value);
}

function isUrl(value) {
  return URL_RE.test(value);
}

function renderApplyChannelCell(a) {
  const value = (a.apply_channel || "").trim();
  if (!value) return "—";
  if (isEmail(value)) {
    const subject = encodeURIComponent(`关于${escapeHtml(a.position)}一职 - ${escapeHtml(a.company)}`);
    return `<a class="app-table-link" href="mailto:${value}?subject=${subject}">${escapeHtml(value)}</a>`;
  }
  if (isUrl(value)) {
    return `<a class="app-table-link" href="${value}" target="_blank" rel="noopener">${escapeHtml(value)}</a>`;
  }
  return escapeHtml(value);
}

function renderTable(apps) {
  const tbody = $("appTableBody");
  tbody.innerHTML = "";
  $("emptyState").hidden = apps.length !== 0;
  for (const a of apps) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${escapeHtml(a.company)}</td>
      <td>${escapeHtml(a.position)}</td>
      <td><span class="badge" style="background:var(--c-${a.status})">${STATUS_LABELS[a.status] || a.status}</span></td>
      <td>${fmtDate(a.applied_date)}</td>
      <td>${escapeHtml(a.source || "—")}</td>
      <td>${renderApplyChannelCell(a)}</td>
      <td>${escapeHtml(a.resume_name || "—")}</td>
      <td>${escapeHtml(a.referral || "—")}</td>
      <td>${fmtDate(a.next_step_date)}</td>
      <td class="row-actions"><button data-id="${a.id}" class="del-btn">删除</button></td>
    `;
    tr.addEventListener("click", (e) => {
      if (e.target.closest(".del-btn") || e.target.closest("a")) return;
      openModal(a);
    });
    tbody.appendChild(tr);
    tr.querySelector(".del-btn").onclick = async (e) => {
      e.stopPropagation();
      if (!confirm(`确定删除 ${a.company} - ${a.position} 吗？`)) return;
      await api(`/api/applications/${a.id}`, { method: "DELETE" });
      refresh();
    };
  }
}

function escapeHtml(str) {
  if (str == null) return "";
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

async function refresh() {
  renderStatusFilters();
  const params = new URLSearchParams();
  if (currentStatusFilter) params.set("status", currentStatusFilter);
  if (currentSearch) params.set("q", currentSearch);
  const [apps, stats] = await Promise.all([
    api(`/api/applications?${params}`),
    api("/api/stats"),
  ]);
  renderTable(apps);
  renderStats(stats);
}

async function loadResumes() {
  resumes = await api("/api/resumes");
  const sel = $("f_resume_id");
  const prevValue = sel.value;
  sel.innerHTML = '<option value="">（不选）</option>' +
    resumes.map((r) => `<option value="${r.id}">${escapeHtml(r.name)}</option>`).join("");
  sel.value = prevValue;
  updateResumeViewLink();
  renderResumeList();
}

function updateApplyChannelLink() {
  const value = $("f_apply_channel").value.trim();
  const link = $("f_apply_channel_link");
  if (isEmail(value)) {
    link.href = `mailto:${value}`;
    link.textContent = "发邮件";
    link.hidden = false;
  } else if (isUrl(value)) {
    link.href = value;
    link.textContent = "打开";
    link.hidden = false;
  } else {
    link.hidden = true;
  }
}

function updateResumeViewLink() {
  const sel = $("f_resume_id");
  const link = $("f_resume_view");
  const resume = resumes.find((r) => String(r.id) === sel.value);
  if (resume && resume.file_path) {
    link.href = `/api/resumes/${resume.id}/file`;
    link.hidden = false;
  } else {
    link.hidden = true;
  }
}

function renderResumeList() {
  const list = $("resumeList");
  if (!list) return;
  if (resumes.length === 0) {
    list.innerHTML = '<li class="resume-empty" style="border:none;">还没有上传简历</li>';
    return;
  }
  list.innerHTML = resumes.map((r) => `
    <li>
      <div>
        <div class="resume-name">${escapeHtml(r.name)}</div>
        ${r.notes ? `<div class="resume-notes">${escapeHtml(r.notes)}</div>` : ""}
      </div>
      <div class="resume-actions">
        ${r.file_path ? `<a href="/api/resumes/${r.id}/file" target="_blank">查看 PDF</a>` : '<span class="resume-notes">未上传文件</span>'}
        <button type="button" class="danger" data-id="${r.id}">删除</button>
      </div>
    </li>
  `).join("");
  list.querySelectorAll(".danger").forEach((btn) => {
    btn.onclick = async () => {
      if (!confirm("删除这个简历版本？关联的投递记录不会被删除。")) return;
      await api(`/api/resumes/${btn.dataset.id}`, { method: "DELETE" });
      await loadResumes();
    };
  });
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result.split(",")[1]);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

async function handleResumeSubmit(e) {
  e.preventDefault();
  const name = $("rf_name").value.trim();
  if (!name) return;
  const fileInput = $("rf_file");
  const payload = { name, notes: $("rf_notes").value.trim() || null };
  const file = fileInput.files[0];
  if (file) {
    if (file.type !== "application/pdf") {
      alert("只支持 PDF 文件");
      return;
    }
    payload.file_data = await fileToBase64(file);
    payload.file_name = file.name;
  }
  try {
    await api("/api/resumes", { method: "POST", body: JSON.stringify(payload) });
    $("resumeForm").reset();
    await loadResumes();
  } catch (err) {
    alert(err.message);
  }
}

function pad2(n) {
  return String(n).padStart(2, "0");
}

function toDateStr(y, m, d) {
  return `${y}-${pad2(m)}-${pad2(d)}`;
}

async function renderCheckinCalendar() {
  const now = new Date();
  const year = now.getFullYear();
  const month = now.getMonth() + 1;
  const todayStr = toDateStr(year, month, now.getDate());
  const monthKey = `${year}-${pad2(month)}`;

  $("checkinMonthLabel").textContent = `${year} 年 ${month} 月打卡`;

  const { dates } = await api(`/api/checkins?month=${monthKey}`);
  const checkedSet = new Set(dates);

  const daysInMonth = new Date(year, month, 0).getDate();
  const firstWeekday = (new Date(year, month - 1, 1).getDay() + 6) % 7; // Monday = 0

  const grid = $("checkinGrid");
  grid.innerHTML = DOW_LABELS.map((d) => `<div class="checkin-dow">${d}</div>`).join("");

  for (let i = 0; i < firstWeekday; i++) {
    grid.insertAdjacentHTML("beforeend", '<div class="checkin-day empty"></div>');
  }

  for (let day = 1; day <= daysInMonth; day++) {
    const dateStr = toDateStr(year, month, day);
    const isToday = dateStr === todayStr;
    const isFuture = dateStr > todayStr;
    const isChecked = checkedSet.has(dateStr);
    const isClickable = !isFuture;
    const classes = ["checkin-day"];
    if (isToday) classes.push("today");
    if (isChecked) classes.push("checked");
    if (isFuture) classes.push("future");
    if (isClickable) classes.push("clickable");
    const cell = document.createElement("div");
    cell.className = classes.join(" ");
    cell.textContent = day;
    if (isClickable) {
      cell.title = isChecked ? "点击取消这天的打卡" : "点击补记这天的打卡";
      cell.onclick = () => toggleCheckin(dateStr, isChecked);
    }
    grid.appendChild(cell);
  }

  $("checkinSummary").textContent = `本月已打卡 ${checkedSet.size} 天`;
}

async function toggleCheckin(dateStr, isChecked) {
  if (isChecked) {
    await api(`/api/checkins/${dateStr}`, { method: "DELETE" });
  } else {
    await api("/api/checkins", { method: "POST", body: JSON.stringify({ date: dateStr }) });
  }
  renderCheckinCalendar();
}

async function loadNote() {
  const { content } = await api("/api/note");
  $("noteText").innerHTML = content || "";
  updateNotePlaceholder();
}

function updateNotePlaceholder() {
  const noteText = $("noteText");
  noteText.classList.toggle("is-empty", noteText.textContent.trim() === "");
}

function initNoteAutosave() {
  const noteText = $("noteText");
  const status = $("noteStatus");
  let saveTimer;
  let savedRange = null;

  function scheduleSave() {
    updateNotePlaceholder();
    status.textContent = "输入中...";
    clearTimeout(saveTimer);
    saveTimer = setTimeout(async () => {
      status.textContent = "保存中...";
      try {
        await api("/api/note", { method: "PUT", body: JSON.stringify({ content: noteText.innerHTML }) });
        status.textContent = "已保存";
      } catch (err) {
        status.textContent = "保存失败";
      }
    }, 500);
  }

  function saveSelection() {
    const sel = window.getSelection();
    if (sel.rangeCount > 0 && noteText.contains(sel.anchorNode)) {
      savedRange = sel.getRangeAt(0).cloneRange();
    }
  }

  function restoreSelection() {
    const sel = window.getSelection();
    // If the live selection is still inside the note (true for every
    // toolbar button, since mousedown preventDefault keeps focus from
    // leaving), leave it alone - re-applying a stale cloned range here
    // was the bug that made bold/italic/underline impossible to toggle
    // back off after the DOM around the selection changed.
    if (sel.rangeCount > 0 && noteText.contains(sel.anchorNode)) {
      return;
    }
    sel.removeAllRanges();
    if (savedRange) {
      sel.addRange(savedRange);
    } else {
      // No prior selection captured - collapse to the end instead of
      // leaving an empty selection (some browsers fall back to "select all"
      // when execCommand runs with no active range).
      const range = document.createRange();
      range.selectNodeContents(noteText);
      range.collapse(false);
      sel.addRange(range);
    }
  }

  noteText.addEventListener("input", scheduleSave);
  noteText.addEventListener("mouseup", saveSelection);
  noteText.addEventListener("keyup", saveSelection);

  function bindFormatButton(id, command) {
    const btn = $(id);
    btn.addEventListener("mousedown", (e) => e.preventDefault());
    btn.addEventListener("click", () => {
      noteText.focus();
      restoreSelection();
      document.execCommand(command, false, null);
      scheduleSave();
    });
  }

  bindFormatButton("noteBoldBtn", "bold");
  bindFormatButton("noteItalicBtn", "italic");
  bindFormatButton("noteUnderlineBtn", "underline");

  function applyColor(color) {
    noteText.focus();
    restoreSelection();
    document.execCommand("foreColor", false, color);
    scheduleSave();
  }

  document.querySelectorAll(".note-swatch").forEach((btn) => {
    btn.addEventListener("mousedown", (e) => {
      e.preventDefault();
      saveSelection();
    });
    btn.addEventListener("click", () => applyColor(btn.dataset.color));
  });

  const colorInput = $("noteColorInput");
  colorInput.addEventListener("mousedown", saveSelection);
  colorInput.addEventListener("input", (e) => applyColor(e.target.value));
}

function initAgentModal() {
  const overlay = $("agentModalOverlay");
  const status = $("agentStatus");
  const fileInput = $("agentFile");
  const submitBtn = $("agentSubmitBtn");

  $("agentBtn").onclick = () => {
    status.hidden = true;
    status.classList.remove("error");
    fileInput.value = "";
    overlay.hidden = false;
  };
  $("agentCloseBtn").onclick = () => { overlay.hidden = true; };
  overlay.addEventListener("click", (e) => {
    if (e.target.id === "agentModalOverlay") overlay.hidden = true;
  });

  submitBtn.onclick = async () => {
    const file = fileInput.files[0];
    if (!file) {
      alert("请先选择一张截图");
      return;
    }
    status.hidden = false;
    status.classList.remove("error");
    status.textContent = "识别中，请稍候...";
    submitBtn.disabled = true;
    try {
      const imageData = await fileToBase64(file);
      const result = await api("/api/agent/process_screenshot", {
        method: "POST",
        body: JSON.stringify({ image_data: imageData, media_type: file.type }),
      });
      status.textContent = result.summary || "处理完成。";
      await refresh();
    } catch (err) {
      status.classList.add("error");
      status.textContent = err.message;
    } finally {
      submitBtn.disabled = false;
    }
  };
}

function populateStatusSelect() {
  const sel = $("f_status");
  sel.innerHTML = STATUS_ORDER.map(
    (s) => `<option value="${s}">${STATUS_LABELS[s]}</option>`
  ).join("");
}

function openModal(app) {
  $("modalTitle").textContent = app ? "编辑投递" : "新增投递";
  $("f_id").value = app ? app.id : "";
  $("f_company").value = app ? app.company : "";
  $("f_position").value = app ? app.position : "";
  $("f_status").value = app ? app.status : "wishlist";
  $("f_location").value = app ? (app.location || "") : "";
  $("f_source").value = app ? (app.source || "") : "";
  $("f_apply_channel").value = app ? (app.apply_channel || "") : "";
  updateApplyChannelLink();
  $("f_resume_id").value = app && app.resume_id ? app.resume_id : "";
  updateResumeViewLink();
  $("f_referral").value = app ? (app.referral || "") : "";
  $("f_applied_date").value = app ? (app.applied_date || "") : "";
  $("f_next_step_date").value = app ? (app.next_step_date || "") : "";
  $("f_notes").value = app ? (app.notes || "") : "";
  $("modalOverlay").hidden = false;
}

function closeModal() {
  $("modalOverlay").hidden = true;
}

async function handleSubmit(e) {
  e.preventDefault();
  const id = $("f_id").value;
  const payload = {
    company: $("f_company").value.trim(),
    position: $("f_position").value.trim(),
    status: $("f_status").value,
    location: $("f_location").value.trim() || null,
    source: $("f_source").value.trim() || null,
    apply_channel: $("f_apply_channel").value.trim() || null,
    resume_id: $("f_resume_id").value ? Number($("f_resume_id").value) : null,
    referral: $("f_referral").value.trim() || null,
    applied_date: $("f_applied_date").value || null,
    next_step_date: $("f_next_step_date").value || null,
    notes: $("f_notes").value.trim() || null,
  };
  try {
    if (id) {
      await api(`/api/applications/${id}`, { method: "PUT", body: JSON.stringify(payload) });
    } else {
      await api("/api/applications", { method: "POST", body: JSON.stringify(payload) });
    }
    closeModal();
    refresh();
  } catch (err) {
    alert(err.message);
  }
}

function init() {
  populateStatusSelect();
  loadResumes();
  renderCheckinCalendar();
  loadNote();
  initNoteAutosave();
  initAgentModal();
  refresh();

  $("addBtn").onclick = () => openModal(null);
  $("cancelBtn").onclick = closeModal;
  $("modalOverlay").addEventListener("click", (e) => {
    if (e.target.id === "modalOverlay") closeModal();
  });
  $("appForm").addEventListener("submit", handleSubmit);
  $("f_resume_id").addEventListener("change", updateResumeViewLink);
  $("f_apply_channel").addEventListener("input", updateApplyChannelLink);

  $("resumeManagerBtn").onclick = () => { $("resumeModalOverlay").hidden = false; };
  $("resumeCloseBtn").onclick = () => { $("resumeModalOverlay").hidden = true; };
  $("resumeModalOverlay").addEventListener("click", (e) => {
    if (e.target.id === "resumeModalOverlay") $("resumeModalOverlay").hidden = true;
  });
  $("resumeForm").addEventListener("submit", handleResumeSubmit);

  let searchTimer;
  $("searchInput").addEventListener("input", (e) => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      currentSearch = e.target.value.trim();
      refresh();
    }, 250);
  });
  $("searchBtn").onclick = () => {
    clearTimeout(searchTimer);
    currentSearch = $("searchInput").value.trim();
    refresh();
  };
  $("searchInput").addEventListener("keydown", (e) => {
    if (e.key === "Enter") $("searchBtn").click();
  });
}

init();
