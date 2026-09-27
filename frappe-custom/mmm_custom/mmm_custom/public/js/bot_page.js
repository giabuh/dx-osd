/* Standalone bot page: existing desk APIs, with no business logic in the browser. */
(() => {
  "use strict";
  const $ = (selector) => document.querySelector(selector);
  const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[char]);
  const money = (value) => `${new Intl.NumberFormat("vi-VN").format(Number(value || 0))}đ`;
  const displayTime = (value) => value ? String(value).replace("T", " ").slice(0, 16) : "—";
  const csrf = $('meta[name="csrf-token"]').content;
  let courses = [];
  let selectedCourse = "";
  let knowledgeLoaded = false;
  let session = newSession();
  let sending = false;

  function newSession() {
    return window.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  }

  async function call(method, args = {}) {
    const response = await fetch(`/api/method/${method}`, {
      method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-Frappe-CSRF-Token": csrf },
      body: JSON.stringify(args)
    });
    if (response.status === 401 || response.status === 403) throw new Error("Phiên đăng nhập đã hết hạn hoặc bạn không có quyền.");
    const data = await response.json();
    if (!response.ok || data.exc) throw new Error(serverMessage(data) || `Lỗi máy chủ (${response.status}).`);
    return data.message;
  }

  function serverMessage(data) {  // the text of frappe.throw, stripped of markup
    try {
      const first = JSON.parse(JSON.parse(data._server_messages)[0]).message;
      const box = document.createElement("div");
      box.innerHTML = first;
      return box.textContent.trim();
    } catch { return ""; }
  }

  function showError(target, error) {
    target.innerHTML = `<p class="error">${escapeHtml(error.message || error)}</p>`;
  }

  const TABS = ["overview", "branches", "staff", "knowledge", "playground", "lead-ads"];
  const loaders = { knowledge: () => knowledgeLoaded || loadKnowledge(), branches: () => loadBranches(), staff: () => loadStaff(),
    "lead-ads": () => loadLeadAds() };

  function switchTab(name) {
    if (!TABS.includes(name)) name = "overview";
    document.querySelectorAll(".side button[data-tab]").forEach((button) => {
      button.setAttribute("aria-selected", String(button.dataset.tab === name));
    });
    document.querySelectorAll(".pane").forEach((pane) => { pane.hidden = pane.id !== name; });
    loaders[name]?.();
  }
  document.querySelectorAll(".side button[data-tab]").forEach((button) => button.addEventListener("click", () => { location.hash = button.dataset.tab; }));
  window.addEventListener("hashchange", () => switchTab(location.hash.slice(1)));

  async function loadOverview() {
    try {
      const data = await call("mmm_custom.engine.dashboard.summary");
      const cards = [
        ["Lead mới hôm nay", data.new_today], ["Khách tiềm năng hôm nay", data.qualified_today],
        ["Không tiềm năng hôm nay", data.unqualified_today], ["Đã chuyển tư vấn hôm nay", data.handed_off_today],
        ["Độ phủ tri thức trung bình", `${data.coverage}%`]
      ];
      $("#stats").innerHTML = cards.map(([label, value]) => `<div class="card"><strong>${escapeHtml(value)}</strong><span>${escapeHtml(label)}</span></div>`).join("");
      $("#latest-leads").innerHTML = data.latest_leads.length ? data.latest_leads.map((lead) => `<tr>
        <td><a href="/crm/leads/${encodeURIComponent(lead.name)}">${escapeHtml(lead.lead_name || lead.first_name || lead.name)}</a></td>
        <td>${escapeHtml(lead.mobile_no || "—")}</td><td>${escapeHtml(lead.course_interest || "—")}</td>
        <td>${escapeHtml(lead.territory || "—")}</td><td>${escapeHtml(lead.lead_owner || "—")}</td>
        <td>${escapeHtml(displayTime(lead.creation))}</td></tr>`).join("") : '<tr><td colspan="6" class="muted">Chưa có khách tiềm năng từ bot.</td></tr>';
    } catch (error) { showError($("#stats"), error); }
  }

  function renderCourses() {
    const query = $("#course-search").value.trim().toLocaleLowerCase("vi");
    const filtered = courses.filter((course) => `${course.name} ${course.code} ${course.group}`.toLocaleLowerCase("vi").includes(query));
    const groups = new Map();
    filtered.forEach((course) => {
      if (!groups.has(course.group)) groups.set(course.group, []);
      groups.get(course.group).push(course);
    });
    $("#courses").innerHTML = [...groups.entries()].sort(([a], [b]) => a.localeCompare(b, "vi")).map(([group, rows]) => `
      <div class="group-label">${escapeHtml(group || "Khác")}</div>${rows.map((course) => `
        <button type="button" class="course-row ${course.code === selectedCourse ? "active" : ""}" data-code="${escapeHtml(course.code)}">
          <strong>${escapeHtml(course.name)}</strong><small>${escapeHtml(course.faqs)} FAQ · ${escapeHtml(course.coverage)}% đầy đủ</small>
          <div class="bar"><i style="width:${Math.max(0, Math.min(100, Number(course.coverage) || 0))}%"></i></div>
        </button>`).join("")}`).join("") || '<p class="muted">Không tìm thấy khóa học.</p>';
    $("#courses").querySelectorAll(".course-row").forEach((button) => button.addEventListener("click", () => showCourse(button.dataset.code)));
  }

  async function loadKnowledge() {
    $("#courses").textContent = "Đang tải khóa học…";
    try {
      courses = await call("mmm_custom.engine.knowledge.overview") || [];
      knowledgeLoaded = true;
      renderCourses();
    } catch (error) { showError($("#courses"), error); }
  }
  $("#course-search").addEventListener("input", renderCourses);

  function list(items) {
    return items?.length ? `<ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : '<p class="muted">Chưa có dữ liệu.</p>';
  }

  async function showCourse(code) {
    selectedCourse = code;
    renderCourses();
    const detail = $("#course-detail");
    detail.textContent = "Đang tải chi tiết…";
    try {
      const course = await call("mmm_custom.engine.knowledge.course", { product: code });
      const fee = Number(course.final_fee) < Number(course.fee)
        ? `${money(course.fee)} → <strong>${money(course.final_fee)}</strong> (${escapeHtml((course.promotions || []).join(", "))})`
        : money(course.fee);
      const schedules = (course.schedules || []).map((row) => `${row.weekday || ""} ${row.date || ""} · ${row.shift || ""} · ${row.branch || ""}`);
      detail.classList.remove("muted");
      detail.innerHTML = `<h2>${escapeHtml(course.name)}</h2><p class="muted">${escapeHtml(course.code)} · ${escapeHtml(course.coverage)}% đầy đủ</p>
        <p><a href="/app/crm-product/${encodeURIComponent(course.code)}" target="_blank" rel="noopener">Sửa dữ liệu khóa học ↗</a></p>
        ${course.gaps?.length ? `<h4>Cần bổ sung</h4><ul>${course.gaps.map((gap) => `<li class="gap">${escapeHtml(gap)}</li>`).join("")}</ul>` : ""}
        <h4>Tổng quan</h4><p>${escapeHtml(course.summary || "Chưa có mô tả.")}</p>
        <p><strong>Học phí:</strong> ${fee} · <strong>Thời lượng:</strong> ${escapeHtml(course.duration || "—")}</p>
        <h4>Nội dung học</h4>${list(course.syllabus)}
        <h4>Câu hỏi thường gặp</h4>${course.faqs?.length ? course.faqs.map((faq) => `<div class="faq"><strong>${escapeHtml(faq.question)}</strong><p>${escapeHtml(faq.error || faq.reply || "Chưa có câu trả lời.")}</p></div>`).join("") : '<p class="muted">Chưa có câu hỏi thường gặp.</p>'}
        <h4>Lớp sắp khai giảng (${escapeHtml(course.schedule_count || 0)})</h4>${list(schedules)}`;
      if (window.matchMedia("(max-width: 650px)").matches) detail.scrollIntoView({ behavior: "smooth", block: "start" });  // one column: the detail sits below the list
    } catch (error) { showError(detail, error); }
  }

  /* New course: typed in, or read from a JSON file into the same form to review before saving. */
  let courseGroups = null;

  function faqRow(faq = {}) {
    const row = $("#faq-template").content.firstElementChild.cloneNode(true);
    const lines = (value) => Array.isArray(value) ? value.join("\n") : (value || "");
    row.querySelector('[data-faq="question"]').value = faq.question || "";
    row.querySelector('[data-faq="examples"]').value = lines(faq.examples);
    row.querySelector('[data-faq="answer"]').value = faq.answer || "";
    row.querySelector("[data-remove-faq]").addEventListener("click", () => row.remove());
    $("#cf-faqs").append(row);
  }

  async function openCourse(data = {}, source = "") {
    const form = $("#course-form");
    try {
      courseGroups = courseGroups || await call("mmm_custom.bot_admin.course_groups");
    } catch (error) { $("#knowledge-notice").innerHTML = `<p class="error">${escapeHtml(error.message)}</p>`; return; }
    form.reset();
    $("#course-error").textContent = "";
    $("#course-source").textContent = source ? `Đã đọc từ ${source}. Xem lại rồi bấm Lưu.` : "";
    form.course_group.innerHTML = '<option value="">— Chọn nhóm —</option>' + options(courseGroups, data.course_group);
    const plain = (html) => new DOMParser().parseFromString(html || "", "text/html").body.textContent.trim();
    ["product_name", "product_code", "button_label", "standard_rate", "duration_text", "min_age", "max_age",
      "certificate", "aliases"].forEach((key) => { if (data[key]) form[key].value = data[key]; });
    if (data.audience) form.audience.value = data.audience;
    if (data.offer) form.offer.value = data.offer;
    form.description.value = /^\s*</.test(data.description || "")
      ? plain(String(data.description).replace(/<\/p>\s*<p>/g, "\n\n")) : (data.description || "");
    form.syllabus.value = Array.isArray(data.syllabus) ? data.syllabus.join("\n") : (data.syllabus || "");
    $("#cf-faqs").replaceChildren();
    (data.faqs?.length ? data.faqs : [{}]).forEach(faqRow);
    form.dataset.nextCourses = JSON.stringify(data.next_courses || []);
    $("#course-dialog").showModal();
  }

  $("#add-course").addEventListener("click", () => openCourse());
  $("#add-faq").addEventListener("click", () => faqRow());
  $("#course-import").addEventListener("change", async (event) => {
    const file = event.target.files[0];
    event.target.value = "";  // choosing the same file again still fires
    if (!file) return;
    try {
      let data = JSON.parse(await file.text());
      if (Array.isArray(data)) {
        if (data.length !== 1) throw new Error("Mỗi file chứa một khóa học.");
        data = data[0];
      }
      if (!data || typeof data !== "object") throw new Error("File không đúng mẫu khóa học.");
      $("#knowledge-notice").replaceChildren();
      openCourse(data, file.name);
    } catch (error) {
      const message = error instanceof SyntaxError ? "File không phải JSON hợp lệ." : error.message;
      $("#knowledge-notice").innerHTML = `<p class="error">${escapeHtml(file.name)}: ${escapeHtml(message)}</p>`;
    }
  });
  $("#course-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.target;
    const course = Object.fromEntries(new FormData(form));
    course.faqs = [...form.querySelectorAll(".faq-row")].map((row) => Object.fromEntries(
      [...row.querySelectorAll("[data-faq]")].map((field) => [field.dataset.faq, field.value])));
    course.next_courses = JSON.parse(form.dataset.nextCourses || "[]");
    try {
      const code = await call("mmm_custom.bot_admin.save_course", { course });
      $("#course-dialog").close();
      $("#knowledge-notice").innerHTML = `<div class="notice">Đã thêm khóa ${escapeHtml(code)}. Bot trả lời được khóa này ngay.</div>`;
      $("#course-search").value = "";
      await loadKnowledge();
      showCourse(code);
    } catch (error) { $("#course-error").textContent = error.message; }
  });

  function bubble(text, role) {
    const item = document.createElement("div");
    item.className = `bubble ${role}`;
    item.textContent = text;
    $("#chat-log").append(item);
    $("#chat-log").scrollTop = $("#chat-log").scrollHeight;
  }

  async function send(text) {
    if (sending || !text.trim()) return;
    sending = true;
    $("#chat-form button").disabled = true;
    $("#chat-log").querySelectorAll(".chips").forEach((item) => item.remove());
    bubble(text, "customer");
    try {
      const result = await call("mmm_custom.engine.playground.simulate", { session, text, jev: $("#use-jev").checked ? 1 : 0 });
      if (!result?.duplicate) {
        (result.reply?.messages || []).forEach((message) => bubble(message, "bot"));
        const buttons = result.reply?.buttons || [];
        if (buttons.length) {
          const chips = document.createElement("div");
          chips.className = "chips";
          buttons.forEach((title) => {
            const button = document.createElement("button");
            button.type = "button";
            button.textContent = title;
            button.addEventListener("click", () => send(title));
            chips.append(button);
          });
          $("#chat-log").append(chips);
        }
        $("#inspector-content").innerHTML = `<p><strong>Lý do:</strong> ${escapeHtml(result.decision?.reason || "—")}</p>
          <h4>Từ khóa khớp</h4><pre>${escapeHtml(JSON.stringify(result.understanding?.matches || [], null, 2))}</pre>
          <h4>Câu trả lời từ Jev</h4><pre>${escapeHtml(JSON.stringify(result.jev || {}, null, 2))}</pre>`;
      }
    } catch (error) { bubble(`Lỗi: ${error.message}`, "bot"); }
    finally { sending = false; $("#chat-form button").disabled = false; $("#chat-input").focus(); }
  }
  $("#chat-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const text = $("#chat-input").value.trim();
    $("#chat-input").value = "";
    send(text);
  });
  $("#reset-chat").addEventListener("click", async () => {
    try {
      await call("mmm_custom.engine.playground.reset", { session });
      session = newSession();
      $("#chat-log").replaceChildren();
      $("#inspector-content").replaceChildren();
    } catch (error) { bubble(`Lỗi: ${error.message}`, "bot"); }
  });

  /* Branches and staff: CRM Territory and Consultant through mmm_custom.bot_admin. */
  const LEVEL_LABELS = { "Consultant": "Tư vấn viên", "Team Lead": "Trưởng nhóm" };
  let branchData = { areas: [], branches: [] };
  let staffData = { staff: [], branches: [], levels: [], groups: [] };
  const options = (items, selected, label = (x) => x) => items.map((item) => `<option value="${escapeHtml(item)}" ${item === selected ? "selected" : ""}>${escapeHtml(label(item))}</option>`).join("");

  document.querySelectorAll("dialog [data-close]").forEach((button) => button.addEventListener("click", () => button.closest("dialog").close()));

  async function loadBranches() {
    $("#branch-rows").innerHTML = '<tr><td colspan="6" class="muted">Đang tải…</td></tr>';
    try {
      branchData = await call("mmm_custom.bot_admin.branches");
      const byArea = new Map(branchData.areas.map((area) => [area, []]));
      branchData.branches.forEach((branch) => byArea.get(branch.area)?.push(branch));
      $("#branch-rows").innerHTML = [...byArea.entries()].map(([area, rows]) => `<tr class="area-row"><td colspan="6">${escapeHtml(area)} · ${rows.length} chi nhánh</td></tr>` +
        (rows.map((b) => `<tr><td><strong>${escapeHtml(b.name)}</strong></td><td>${escapeHtml(b.branch_code || "—")}</td>
          <td>${escapeHtml(b.address || "—")}</td><td>${escapeHtml(b.hotline || "—")}</td>
          <td><button type="button" class="link-btn" data-staff-of="${escapeHtml(b.name)}">${b.staff} người</button></td>
          <td><button type="button" class="secondary" data-edit-branch="${escapeHtml(b.name)}">Sửa</button></td></tr>`).join("") || '<tr><td colspan="6" class="muted">Chưa có chi nhánh.</td></tr>')).join("")
        || '<tr><td colspan="6" class="muted">Chưa có khu vực nào. Bấm “Thêm chi nhánh” để tạo.</td></tr>';
      $("#branch-rows").querySelectorAll("[data-edit-branch]").forEach((button) => button.addEventListener("click", () => openBranch(branchData.branches.find((b) => b.name === button.dataset.editBranch))));
      $("#branch-rows").querySelectorAll("[data-staff-of]").forEach((button) => button.addEventListener("click", () => { staffFilter = button.dataset.staffOf; location.hash = "staff"; }));
    } catch (error) { showError($("#branch-rows"), error); }
  }

  function openBranch(branch) {
    const form = $("#branch-form");
    form.reset();
    $("#branch-error").textContent = "";
    $("#branch-title").textContent = branch ? `Sửa ${branch.name}` : "Thêm chi nhánh";
    form.original.value = branch?.name || "";
    form.territory_name.value = branch?.name || "";
    form.territory_name.disabled = Boolean(branch);
    form.area.innerHTML = options(branchData.areas, branch?.area) + '<option value="__new">+ Khu vực mới…</option>';
    ["button_label", "branch_code", "address", "hotline", "map_url", "aliases"].forEach((key) => { form[key].value = branch?.[key] || ""; });
    $("#bf-new-area-wrap").hidden = form.area.value !== "__new";
    $("#branch-dialog").showModal();
  }
  $("#bf-area").addEventListener("change", () => { $("#bf-new-area-wrap").hidden = $("#bf-area").value !== "__new"; });
  $("#add-branch").addEventListener("click", () => openBranch(null));
  $("#branch-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.target;
    const data = Object.fromEntries(new FormData(form));
    data.name = data.original;
    delete data.original;
    data.territory_name = form.territory_name.value;
    if (data.area === "__new") { data.area = ""; } else { data.new_area = ""; }
    try {
      await call("mmm_custom.bot_admin.save_branch", data);
      $("#branch-dialog").close();
      loadBranches();
    } catch (error) { $("#branch-error").textContent = error.message; }
  });

  let staffFilter = "";
  let syncPoll = null;

  async function loadStaff() {
    try {
      staffData = await call("mmm_custom.bot_admin.staff");
      $("#staff-branch").innerHTML = '<option value="">Tất cả chi nhánh</option><option value="__none">Tổng đài / B2B (không chi nhánh)</option>' + options(staffData.branches, staffFilter);
      if (staffFilter === "__none") $("#staff-branch").value = "__none";
      renderStaff();
    } catch (error) { showError($("#staff-rows"), error); }
  }

  function renderStaff() {
    staffFilter = $("#staff-branch").value;
    const query = $("#staff-search").value.trim().toLocaleLowerCase("vi");
    const rows = staffData.staff.filter((s) => (!staffFilter || (staffFilter === "__none" ? !s.branch : s.branch === staffFilter))
      && `${s.full_name} ${s.name}`.toLocaleLowerCase("vi").includes(query));
    $("#staff-rows").innerHTML = rows.map((s) => `<tr>
      <td><strong>${escapeHtml(s.full_name || s.name)}</strong><br><small class="muted">${escapeHtml(s.name)}</small></td>
      <td>${escapeHtml(s.branch || (s.handles_b2b ? "Doanh nghiệp (B2B)" : "Tổng đài"))}</td>
      <td>${escapeHtml(LEVEL_LABELS[s.level] || s.level || "—")}</td>
      <td>${escapeHtml((s.specialties || []).join(", ") || "—")}</td>
      <td>${s.active ? '<span class="pill ok">Đang làm</span>' : '<span class="pill off">Đã nghỉ</span>'}</td>
      <td>${s.chatwoot_agent_id ? '<span class="pill ok">Đã đồng bộ</span>' : (s.active ? '<span class="pill wait">Đang đồng bộ…</span>' : "—")}</td>
      <td><button type="button" class="secondary" data-edit-staff="${escapeHtml(s.name)}">Sửa</button></td></tr>`).join("")
      || '<tr><td colspan="7" class="muted">Không có nhân viên phù hợp.</td></tr>';
    $("#staff-rows").querySelectorAll("[data-edit-staff]").forEach((button) => button.addEventListener("click", () => openStaff(staffData.staff.find((s) => s.name === button.dataset.editStaff))));
  }
  $("#staff-search").addEventListener("input", renderStaff);
  $("#staff-branch").addEventListener("change", renderStaff);

  function openStaff(person) {
    const form = $("#staff-form");
    form.reset();
    $("#staff-error").textContent = "";
    $("#staff-title").textContent = person ? `Sửa ${person.full_name || person.name}` : "Thêm nhân viên";
    form.is_new.value = person ? "0" : "1";
    form.full_name.value = person?.full_name || "";
    form.email.value = person?.name || "";
    form.email.disabled = Boolean(person);
    const branch = person ? (person.branch || "") : (staffFilter !== "__none" ? staffFilter : "");
    form.branch.innerHTML = '<option value="">Không thuộc chi nhánh (Tổng đài / B2B)</option>' + options(staffData.branches, branch);
    form.level.innerHTML = options(staffData.levels, person?.level || "Consultant", (level) => LEVEL_LABELS[level] || level);
    $("#sf-groups").innerHTML = staffData.groups.map((group) => `<label><input type="checkbox" name="specialties" value="${escapeHtml(group)}" ${(person?.specialties || []).includes(group) ? "checked" : ""}> ${escapeHtml(group)}</label>`).join("");
    form.handles_b2b.checked = Boolean(person?.handles_b2b);
    form.active.checked = person ? Boolean(person.active) : true;
    $("#staff-dialog").showModal();
  }
  $("#add-staff").addEventListener("click", () => openStaff(null));
  $("#staff-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.target;
    const data = {
      is_new: form.is_new.value, email: form.email.value, full_name: form.full_name.value, branch: form.branch.value,
      level: form.level.value, specialties: [...form.querySelectorAll('[name="specialties"]:checked')].map((box) => box.value),
      handles_b2b: form.handles_b2b.checked ? 1 : 0, active: form.active.checked ? 1 : 0
    };
    try {
      await call("mmm_custom.bot_admin.save_staff", data);
      $("#staff-dialog").close();
      $("#staff-notice").innerHTML = '<div class="notice">Đã lưu. Chatwoot sẽ cập nhật trong vài giây.</div>';
      await loadStaff();
      clearTimeout(syncPoll);
      syncPoll = setTimeout(async () => { await loadStaff(); $("#staff-notice").replaceChildren(); }, 8000);
    } catch (error) { $("#staff-error").textContent = error.message; }
  });

  /* Facebook Lead Ads: crm/lead_syncing sources through mmm_custom.lead_ads. */
  const FREQUENCY_LABELS = { "Every 5 Minutes": "5 phút", "Every 10 Minutes": "10 phút", "Every 15 Minutes": "15 phút",
    "Hourly": "Mỗi giờ", "Daily": "Mỗi ngày", "Monthly": "Mỗi tháng" };
  let leadAds = { sources: [], frequencies: [] };
  let fbPages = [];
  let mappingForm = "";
  const leadAdsNotice = (html) => { $("#lead-ads-notice").innerHTML = html; };

  async function loadLeadAds() {
    $("#source-rows").innerHTML = '<tr><td colspan="7" class="muted">Đang tải…</td></tr>';
    try {
      const [data, failed] = await Promise.all([call("mmm_custom.lead_ads.list_sources"), call("mmm_custom.lead_ads.failures")]);
      leadAds = data;
      $("#source-rows").innerHTML = data.sources.map((s) => `<tr>
        <td>${escapeHtml(s.page_name || "—")}</td><td><strong>${escapeHtml(s.form_name || "—")}</strong>${s.name !== s.form_name ? `<br><small class="muted">${escapeHtml(s.name)}</small>` : ""}</td>
        <td>${escapeHtml(FREQUENCY_LABELS[s.background_sync_frequency] || s.background_sync_frequency || "—")}</td>
        <td>${escapeHtml(displayTime(s.last_synced_at))}</td>
        <td>${s.failures ? `<span class="pill wait">${escapeHtml(s.failures)}</span>` : "0"}</td>
        <td><input type="checkbox" data-toggle-source="${escapeHtml(s.name)}" aria-label="Bật ${escapeHtml(s.name)}" ${s.enabled ? "checked" : ""}></td>
        <td><button type="button" class="secondary" data-sync-source="${escapeHtml(s.name)}">Đồng bộ ngay</button>
          <button type="button" class="secondary" data-edit-source="${escapeHtml(s.name)}">Sửa</button></td></tr>`).join("")
        || '<tr><td colspan="7" class="muted">Chưa kết nối form nào. Bấm “Kết nối form”.</td></tr>';
      $("#failure-rows").innerHTML = failed.map((f) => `<tr><td>${escapeHtml(displayTime(f.creation))}</td>
        <td>${escapeHtml(f.source || "—")}</td><td><small>${escapeHtml(f.error || "—")}</small></td>
        <td><button type="button" class="secondary" data-retry="${escapeHtml(f.name)}">Thử lại</button></td></tr>`).join("")
        || '<tr><td colspan="4" class="muted">Không có lỗi.</td></tr>';
      const rows = $("#source-rows");
      rows.querySelectorAll("[data-toggle-source]").forEach((box) => box.addEventListener("change", async () => {
        try { await call("mmm_custom.lead_ads.set_enabled", { name: box.dataset.toggleSource, enabled: box.checked ? 1 : 0 }); }
        catch (error) { box.checked = !box.checked; leadAdsNotice(`<p class="error">${escapeHtml(error.message)}</p>`); }
      }));
      rows.querySelectorAll("[data-sync-source]").forEach((button) => button.addEventListener("click", async () => {
        button.disabled = true;
        try {
          await call("mmm_custom.lead_ads.sync_now", { name: button.dataset.syncSource });
          leadAdsNotice('<div class="notice">Đang đồng bộ. Lead mới hiện trong CRM sau ít phút.</div>');
        } catch (error) { leadAdsNotice(`<p class="error">${escapeHtml(error.message)}</p>`); }
        finally { button.disabled = false; }
      }));
      rows.querySelectorAll("[data-edit-source]").forEach((button) => button.addEventListener("click", () => openSource(leadAds.sources.find((s) => s.name === button.dataset.editSource))));
      $("#failure-rows").querySelectorAll("[data-retry]").forEach((button) => button.addEventListener("click", async () => {
        button.disabled = true;
        try {
          const lead = await call("mmm_custom.lead_ads.retry", { name: button.dataset.retry });
          leadAdsNotice(`<div class="notice">Đã tạo Lead <a href="/crm/leads/${encodeURIComponent(lead)}">${escapeHtml(lead)}</a>.</div>`);
          loadLeadAds();
        } catch (error) { button.disabled = false; leadAdsNotice(`<p class="error">${escapeHtml(error.message)}</p>`); }
      }));
    } catch (error) { showError($("#source-rows"), error); }
  }

  function fillPages(page, form) {
    const select = $("#sr-page");
    select.innerHTML = '<option value="">— Chọn Page —</option>' + fbPages.map((p) => `<option value="${escapeHtml(p.id)}" ${p.id === page ? "selected" : ""}>${escapeHtml(p.name)}</option>`).join("");
    fillForms(form);
  }

  function fillForms(form) {
    const forms = fbPages.find((p) => p.id === $("#sr-page").value)?.forms || [];
    $("#sr-form").innerHTML = '<option value="">— Chọn form —</option>' + forms.map((f) => `<option value="${escapeHtml(f.id)}" ${f.id === form ? "selected" : ""}>${escapeHtml(f.name)}</option>`).join("");
  }

  async function openSource(source) {
    const form = $("#source-form");
    form.reset();
    $("#source-error").textContent = "";
    $("#mapping").hidden = true;
    $("#source-title").textContent = source ? `Sửa ${source.name}` : "Kết nối form";
    form.original.value = source?.name || "";
    form.source_name.value = source?.name || "";
    form.source_name.disabled = Boolean(source);
    form.enabled.checked = source ? Boolean(source.enabled) : true;
    form.access_token.placeholder = source ? "Để trống = giữ token cũ" : "Dán access token của Page";
    form.background_sync_frequency.innerHTML = options(leadAds.frequencies, source?.background_sync_frequency || "Hourly", (f) => FREQUENCY_LABELS[f] || f);
    $("#source-editor").hidden = false;
    $("#source-editor").scrollIntoView({ behavior: "smooth", block: "start" });
    try { fbPages = await call("mmm_custom.lead_ads.pages") || []; } catch (error) { fbPages = []; $("#source-error").textContent = error.message; }
    fillPages(source?.facebook_page, source?.facebook_lead_form);
    if (source?.facebook_lead_form) showMapping(source.facebook_lead_form);
  }

  async function showMapping(formId) {
    mappingForm = formId;
    $("#mapping-error").textContent = "";
    try {
      const data = await call("mmm_custom.lead_ads.form_mapping", { form: formId });
      const values = data.fields.map((f) => f.value);
      const labels = Object.fromEntries(data.fields.map((f) => [f.value, f.label]));
      $("#mapping-rows").innerHTML = data.questions.map((q) => `<tr><td>${escapeHtml(q.label || q.key)}<br><small class="muted">${escapeHtml(q.key)}</small></td>
        <td><select data-question="${escapeHtml(q.key)}"><option value="">— Không lấy —</option>${options(values, q.mapped_to_crm_field, (v) => labels[v] || v)}</select></td></tr>`).join("")
        || '<tr><td colspan="2" class="muted">Form này không có câu hỏi.</td></tr>';
      $("#mapping").hidden = false;
    } catch (error) { $("#mapping-error").textContent = error.message; $("#mapping").hidden = false; }
  }

  $("#add-source").addEventListener("click", () => { leadAdsNotice(""); openSource(null); });
  $("#close-source").addEventListener("click", () => { $("#source-editor").hidden = true; });
  $("#sr-page").addEventListener("change", () => fillForms(""));
  $("#load-pages").addEventListener("click", async () => {
    const button = $("#load-pages");
    $("#source-error").textContent = "";
    button.disabled = true;
    try {
      fbPages = await call("mmm_custom.lead_ads.connect", { access_token: $("#sr-token").value }) || [];
      fillPages(fbPages.length === 1 ? fbPages[0].id : "", "");
      if (!fbPages.length) $("#source-error").textContent = "Token này không quản lý Page nào.";
    } catch (error) { $("#source-error").textContent = error.message; }
    finally { button.disabled = false; }
  });
  $("#source-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.target;
    const values = {
      name: form.original.value, title: form.source_name.value, access_token: form.access_token.value,
      facebook_page: form.facebook_page.value, facebook_lead_form: form.facebook_lead_form.value,
      background_sync_frequency: form.background_sync_frequency.value, enabled: form.enabled.checked ? 1 : 0
    };
    try {
      const name = await call("mmm_custom.lead_ads.save_source", { values });
      form.original.value = name;
      form.source_name.value = name;
      form.source_name.disabled = true;
      form.access_token.value = "";
      $("#source-title").textContent = `Sửa ${name}`;
      leadAdsNotice(`<div class="notice">Đã lưu ${escapeHtml(name)}. Chọn trường CRM cho từng câu hỏi bên dưới.</div>`);
      loadLeadAds();
      showMapping(values.facebook_lead_form);
    } catch (error) { $("#source-error").textContent = error.message; }
  });
  $("#save-mapping").addEventListener("click", async () => {
    const mapping = Object.fromEntries([...$("#mapping-rows").querySelectorAll("[data-question]")].map((select) => [select.dataset.question, select.value]));
    try {
      await call("mmm_custom.lead_ads.save_mapping", { form: mappingForm, mapping });
      $("#mapping-error").textContent = "";
      leadAdsNotice('<div class="notice">Đã lưu cách lấy dữ liệu. Lead đồng bộ sau sẽ dùng cách này.</div>');
    } catch (error) { $("#mapping-error").textContent = error.message; }
  });

  loadOverview();
  switchTab(location.hash.slice(1));
})();
