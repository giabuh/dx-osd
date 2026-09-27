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
    if (!response.ok || data.exc) throw new Error(data._server_messages ? "Không tải được dữ liệu. Vui lòng thử lại." : `Lỗi máy chủ (${response.status}).`);
    return data.message;
  }

  function showError(target, error) {
    target.innerHTML = `<p class="error">${escapeHtml(error.message || error)}</p>`;
  }

  function switchTab(name) {
    document.querySelectorAll(".tabs button").forEach((button) => {
      button.setAttribute("aria-selected", String(button.dataset.tab === name));
    });
    document.querySelectorAll(".pane").forEach((pane) => { pane.hidden = pane.id !== name; });
    if (name === "knowledge" && !knowledgeLoaded) loadKnowledge();
  }
  document.querySelectorAll(".tabs button").forEach((button) => button.addEventListener("click", () => switchTab(button.dataset.tab)));

  async function loadOverview() {
    try {
      const data = await call("mmm_custom.engine.dashboard.summary");
      const cards = [
        ["Lead mới hôm nay", data.new_today], ["Đủ điều kiện hôm nay", data.qualified_today],
        ["Chưa phù hợp hôm nay", data.unqualified_today], ["Đã chuyển tư vấn hôm nay", data.handed_off_today],
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
    } catch (error) { showError(detail, error); }
  }

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
  loadOverview();
})();
