(() => {
  "use strict";

  const state = { page: "dashboard", rows: [], columns: [], rowId: "id", handlers: {}, filter: "", blockFilter: "all", data: {} };
  const $ = (selector, root = document) => root.querySelector(selector);
  const content = $("#pageContent");
  const modalRoot = $("#modalRoot");
  const pageTitles = { dashboard: "Dashboard", students: "Students", blocks: "Hostel blocks", rooms: "Rooms", beds: "Beds", allocations: "Allocations", transfers: "Transfers", fees: "Fees & payments", visitors: "Visitors", complaints: "Complaints", maintenance: "Maintenance", vacating: "Vacating", reports: "Reports" };

  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
  const fmtDate = (value) => value ? new Date(value).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" }) : "—";
  const fmtDateTime = (value) => value ? new Date(value).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) : "—";
  const fmtMoney = (value) => new Intl.NumberFormat(undefined, { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(Number(value || 0));
  const titleCase = (value) => String(value || "—").toLowerCase().replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());

  async function api(url, options = {}) {
    const response = await fetch(url, { ...options, headers: { ...(options.body ? { "Content-Type": "application/json" } : {}), ...(options.headers || {}) } });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
    return data;
  }

  function toast(message, type = "success") {
    const node = document.createElement("div");
    node.className = `toast ${type}`;
    node.textContent = message;
    $("#toastRegion").append(node);
    setTimeout(() => node.remove(), 3600);
  }

  function heading(title, description, buttonLabel = "", buttonAction = "") {
    return `<div class="page-heading"><div><div class="eyebrow">Campus operations</div><h1>${esc(title)}</h1><p>${esc(description)}</p></div><div class="heading-actions">${buttonLabel ? `<button class="button button-primary" data-page-action="${esc(buttonAction)}"><span>＋</span>${esc(buttonLabel)}</button>` : ""}</div></div>`;
  }

  function badge(value) {
    const text = String(value || "—");
    const key = text.toLowerCase();
    let tone = "gray";
    if (["active", "available", "resolved", "completed", "vacated"].includes(key)) tone = "green";
    else if (["open", "in_progress", "assigned", "transferred", "medium"].includes(key)) tone = "amber";
    else if (["urgent", "high", "occupied", "closed", "cancelled"].includes(key)) tone = "red";
    else if (["low", "standard", "deluxe"].includes(key)) tone = "blue";
    return `<span class="badge ${tone}">${esc(titleCase(text))}</span>`;
  }

  function emptyState(message = "No records found", hint = "Data from your database will appear here.") {
    return `<div class="empty-state"><div class="empty-icon">⌕</div><strong>${esc(message)}</strong>${esc(hint)}</div>`;
  }

  function tableMarkup(rows, columns, rowId = "id", actions = []) {
    if (!rows.length) return emptyState();
    const head = columns.map((column) => `<th>${esc(column.label)}</th>`).join("");
    const actionHead = actions.length ? "<th>Actions</th>" : "";
    const body = rows.map((row) => `<tr>${columns.map((column) => `<td>${column.render ? column.render(row[column.key], row) : esc(row[column.key] ?? "—")}</td>`).join("")}${actions.length ? `<td><div class="table-actions">${actions.map((action) => `<button class="icon-action ${action.tone || ""}" title="${esc(action.label)}" data-action="${esc(action.key)}" data-id="${esc(row[rowId])}">${esc(action.label)}</button>`).join("")}</div></td>` : ""}</tr>`).join("");
    return `<div class="table-wrap"><table class="data-table"><thead><tr>${head}${actionHead}</tr></thead><tbody>${body}</tbody></table></div>`;
  }

  function drawTable() {
    const tableHost = $("#tableHost", content);
    if (!tableHost) return;
    const q = state.filter.trim().toLowerCase();
    const filtered = state.rows.filter((row) => !q || Object.values(row).some((value) => String(value ?? "").toLowerCase().includes(q)));
    tableHost.innerHTML = tableMarkup(filtered, state.columns, state.rowId, state.actions || []);
    const count = $("#rowCount", content);
    if (count) count.textContent = `${filtered.length} ${filtered.length === 1 ? "record" : "records"}`;
  }

  function tablePanel(rows, columns, options = {}) {
    state.rows = rows || [];
    state.columns = columns;
    state.rowId = options.rowId || "id";
    state.actions = options.actions || [];
    state.filter = "";
    const search = options.search !== false;
    const toolbar = search ? `<div class="content-toolbar"><div class="search-wrap"><input class="search-input" id="tableSearch" type="search" placeholder="Search ${esc(options.searchLabel || "records")}…" autocomplete="off"></div><span id="rowCount" class="form-hint"></span></div>` : "";
    return `<div class="panel">${toolbar}<div id="tableHost">${tableMarkup(state.rows, state.columns, state.rowId, state.actions)}</div></div>`;
  }

  function listenSearch() {
    const input = $("#tableSearch", content);
    if (input) input.addEventListener("input", () => { state.filter = input.value; drawTable(); });
    const count = $("#rowCount", content);
    if (count) count.textContent = `${state.rows.length} ${state.rows.length === 1 ? "record" : "records"}`;
  }

  function optionList(rows, valueKey, labelFn, placeholder = "Select…") {
    return [{ value: "", label: placeholder }, ...rows.map((row) => ({ value: row[valueKey], label: labelFn(row) }))];
  }

  function fieldMarkup(field, value = "") {
    const required = field.required ? "required" : "";
    const id = `field-${field.name}`;
    const label = `<label for="${esc(id)}">${esc(field.label)}${field.required ? " <em>*</em>" : ""}</label>`;
    const common = `id="${esc(id)}" name="${esc(field.name)}" class="form-control" ${required} ${field.min != null ? `min="${field.min}"` : ""} ${field.max != null ? `max="${field.max}"` : ""} ${field.step ? `step="${field.step}"` : ""} ${field.maxlength ? `maxlength="${field.maxlength}"` : ""} placeholder="${esc(field.placeholder || "")}"`;
    let input;
    if (field.type === "select") {
      const options = (field.options || []).map((option) => `<option value="${esc(option.value)}" ${String(option.value) === String(value) ? "selected" : ""}>${esc(option.label)}</option>`).join("");
      input = `<select ${common}><option value="">${esc(field.placeholder || "Select an option")}</option>${options}</select>`;
    } else if (field.type === "textarea") {
      input = `<textarea ${common} rows="3">${esc(value)}</textarea>`;
    } else if (field.type === "checkbox") {
      input = `<label class="check-control"><input id="${esc(id)}" name="${esc(field.name)}" type="checkbox" ${value === true || value === 1 ? "checked" : ""}><span>${esc(field.checkboxLabel || field.label)}</span></label>`;
    } else {
      input = `<input ${common} type="${esc(field.type || "text")}" value="${esc(value)}" ${field.autocomplete ? `autocomplete="${esc(field.autocomplete)}"` : ""}>`;
    }
    return `<div class="form-field ${field.full ? "full" : ""}">${field.type === "checkbox" ? input : label + input}${field.hint ? `<small class="form-hint">${esc(field.hint)}</small>` : ""}</div>`;
  }

  function closeModal() { modalRoot.innerHTML = ""; }

  function openForm(title, fields, onSubmit, initial = {}, subtitle = "Fields marked with * are required.") {
    modalRoot.innerHTML = `<div class="modal" role="dialog" aria-modal="true"><div class="modal-header"><div><h2>${esc(title)}</h2><p>${esc(subtitle)}</p></div><button class="modal-close" data-modal-close aria-label="Close">×</button></div><form class="modal-form" id="dataForm" novalidate><div class="form-grid">${fields.map((field) => fieldMarkup(field, initial[field.name] ?? field.default ?? "")).join("")}</div><div class="form-error" id="formError"></div><div class="modal-footer"><button type="button" class="button button-secondary" data-modal-close>Cancel</button><button type="submit" class="button button-primary">Save changes</button></div></form></div>`;
    $("#dataForm", modalRoot).addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      if (!form.reportValidity()) return;
      const data = {};
      for (const field of fields) {
        const element = form.elements[field.name];
        if (!element) continue;
        if (field.type === "checkbox") { data[field.name] = element.checked; continue; }
        const value = element.value;
        if (value === "" && !field.required) { if (field.nullable) data[field.name] = null; continue; }
        // The existing student API validates year_of_study as a non-empty
        // string before converting it to an integer; preserve that contract.
        data[field.name] = field.type === "number" && field.name !== "year_of_study" ? Number(value) : value;
      }
      const submit = $("button[type=submit]", form);
      submit.disabled = true; submit.innerHTML = `<span class="spinner"></span>Saving…`;
      try { await onSubmit(data); closeModal(); toast("Changes saved successfully."); await loadPage(state.page); }
      catch (error) { $("#formError", form).textContent = error.message; submit.disabled = false; submit.textContent = "Save changes"; }
    });
  }

  function openDetails(title, row, fields) {
    modalRoot.innerHTML = `<div class="modal" role="dialog" aria-modal="true"><div class="modal-header"><div><h2>${esc(title)}</h2><p>Record details from the live database</p></div><button class="modal-close" data-modal-close aria-label="Close">×</button></div><div class="detail-grid">${fields.map(([label, key]) => `<div class="detail-item"><span>${esc(label)}</span><strong>${esc(row[key] == null || row[key] === "" ? "—" : row[key])}</strong></div>`).join("")}</div><div class="modal-footer"><button class="button button-secondary" data-modal-close>Close</button></div></div>`;
  }

  function askDelete(label, url, refresh = state.page) {
    if (!window.confirm(`Delete ${label}? This cannot be undone.`)) return;
    api(url, { method: "DELETE" }).then(() => { toast(`${label} deleted.`); loadPage(refresh); }).catch((error) => toast(error.message, "error"));
  }

  async function pageStudents() {
    const rows = await api("/api/students");
    content.innerHTML = heading("Students", "Student records, contact details and academic information.", "Add student", "add-student") + tablePanel(rows, [
      { key: "registration_no", label: "Registration no.", render: (v, r) => `<span class="primary-cell">${esc(v)}</span><span class="sub-cell">${esc(r.email)}</span>` },
      { key: "first_name", label: "Student", render: (_, r) => `<span class="primary-cell">${esc(r.first_name)} ${esc(r.last_name)}</span><span class="sub-cell">${esc(r.department)}</span>` },
      { key: "course", label: "Course" }, { key: "year_of_study", label: "Year" },
      { key: "gender", label: "Gender", render: (v) => badge(v) }, { key: "phone", label: "Phone" },
    ], { rowId: "student_id", searchLabel: "students", actions: [{ key: "student-view", label: "View" }, { key: "student-edit", label: "Edit" }, { key: "student-delete", label: "Delete", tone: "danger" }] });
    listenSearch(); state.data.students = rows;
    state.handlers = {
      "student-view": (id) => { const r = rows.find((x) => x.student_id == id); openDetails(`${r.first_name} ${r.last_name}`, r, [["Registration", "registration_no"], ["Email", "email"], ["Phone", "phone"], ["Gender", "gender"], ["Date of birth", "date_of_birth"], ["Department", "department"], ["Course", "course"], ["Year", "year_of_study"], ["Emergency contact", "emergency_contact_name"], ["Emergency phone", "emergency_contact_phone"]]); },
      "student-edit": (id) => { const r = rows.find((x) => x.student_id == id); openForm("Edit student", studentFields, (data) => api(`/api/students/${id}`, { method: "PUT", body: JSON.stringify(data) }), r); },
      "student-delete": (id) => askDelete("this student", `/api/students/${id}`),
    };
  }

  const studentFields = [
    { name: "registration_no", label: "Registration number", required: true, maxlength: 30 }, { name: "email", label: "Email address", type: "email", required: true, maxlength: 254 },
    { name: "first_name", label: "First name", required: true }, { name: "last_name", label: "Last name", required: true },
    { name: "phone", label: "Phone", required: true }, { name: "gender", label: "Gender", type: "select", required: true, options: ["MALE", "FEMALE", "OTHER"].map((v) => ({ value: v, label: titleCase(v) })) },
    { name: "date_of_birth", label: "Date of birth", type: "date" }, { name: "department", label: "Department", required: true },
    { name: "course", label: "Course", required: true }, { name: "year_of_study", label: "Year of study", type: "number", required: true, min: 1, max: 8 },
    { name: "emergency_contact_name", label: "Emergency contact name", required: true }, { name: "emergency_contact_phone", label: "Emergency contact phone", required: true },
  ];

  async function pageBlocks() {
    const rows = await api("/api/blocks");
    const getWarden = (id) => id ? `Warden user #${id}` : "Not assigned";
    content.innerHTML = heading("Hostel blocks", "Manage residence blocks and their assigned wardens.", "Add block", "add-block") + tablePanel(rows, [
      { key: "block_code", label: "Code", render: (v) => `<span class="primary-cell">${esc(v)}</span>` }, { key: "block_name", label: "Block name" },
      { key: "gender_policy", label: "Residence policy", render: (v) => badge(v) }, { key: "warden_user_id", label: "Warden", render: (v) => esc(getWarden(v)) },
      { key: "is_active", label: "Status", render: (v) => badge(v ? "ACTIVE" : "INACTIVE") },
    ], { rowId: "block_id", actions: [{ key: "block-edit", label: "Edit" }, { key: "block-delete", label: "Delete", tone: "danger" }] });
    listenSearch(); state.data.blocks = rows;
    state.handlers = { "block-edit": (id) => { const row = rows.find((r) => r.block_id == id); openForm("Edit hostel block", blockFields, (data) => api(`/api/blocks/${id}`, { method: "PUT", body: JSON.stringify(data) }), { ...row, is_active: Boolean(row.is_active) }); }, "block-delete": (id) => askDelete("this block", `/api/blocks/${id}`) };
  }

  const blockFields = [
    { name: "block_code", label: "Block code", required: true, maxlength: 20 }, { name: "block_name", label: "Block name", required: true },
    { name: "gender_policy", label: "Residence policy", type: "select", required: true, options: ["MALE", "FEMALE", "MIXED"].map((v) => ({ value: v, label: titleCase(v) })) },
    { name: "warden_user_id", label: "Warden user ID", type: "number", min: 1, nullable: true, hint: "The current API stores a warden user ID; it does not expose a user directory." },
    { name: "address", label: "Address", full: true }, { name: "is_active", label: "Active", type: "checkbox", checkboxLabel: "Block is active", default: true },
  ];

  async function pageRooms() {
    const [rows, blocks] = await Promise.all([api("/api/rooms"), api("/api/blocks")]);
    content.innerHTML = heading("Rooms", "Room capacity and live bed occupancy by block.", "Add room", "add-room") + `<div class="content-toolbar panel"><div><span class="form-hint">Filter by hostel block</span></div><select class="filter-select" id="blockFilter"><option value="all">All blocks</option>${blocks.map((b) => `<option value="${b.block_id}">${esc(b.block_name)}</option>`).join("")}</select></div>` + tablePanel(rows, [
      { key: "room_number", label: "Room", render: (v, r) => `<span class="primary-cell">${esc(v)}</span><span class="sub-cell">${esc(r.block_name)} · Floor ${esc(r.floor_number)}</span>` },
      { key: "room_type", label: "Type", render: (v) => badge(v) }, { key: "capacity", label: "Capacity" }, { key: "bed_count", label: "Beds" },
      { key: "occupied_beds", label: "Occupied" }, { key: "available_beds", label: "Available", render: (_, r) => badge(Math.max(Number(r.bed_count) - Number(r.occupied_beds), 0)) },
    ], { rowId: "room_id", actions: [{ key: "room-edit", label: "Edit" }, { key: "room-delete", label: "Delete", tone: "danger" }] });
    listenSearch(); state.data.blocks = blocks; state.data.rooms = rows;
    const filter = $("#blockFilter", content); filter.value = state.blockFilter || "all";
    filter.addEventListener("change", () => { state.blockFilter = filter.value; const host = $("#tableHost", content); const data = filter.value === "all" ? rows : rows.filter((r) => String(r.block_id) === filter.value); state.rows = data; drawTable(); });
    state.handlers = {
      "room-edit": (id) => { const r = rows.find((x) => x.room_id == id); openForm("Edit room", roomFields(blocks), (data) => api(`/api/rooms/${id}`, { method: "PUT", body: JSON.stringify(data) }), r); },
      "room-delete": (id) => askDelete("this room", `/api/rooms/${id}`),
    };
  }

  const roomFields = (blocks) => [
    { name: "block_id", label: "Hostel block", type: "select", required: true, options: blocks.map((b) => ({ value: b.block_id, label: b.block_name })) },
    { name: "room_number", label: "Room number", required: true }, { name: "floor_number", label: "Floor", type: "number", default: 0 },
    { name: "capacity", label: "Capacity", type: "number", min: 1, max: 12, required: true },
    { name: "room_type", label: "Room type", type: "select", default: "STANDARD", options: ["STANDARD", "DELUXE", "ACCESSIBLE"].map((v) => ({ value: v, label: titleCase(v) })) },
    { name: "is_active", label: "Active", type: "checkbox", checkboxLabel: "Room is active", default: true },
  ];

  async function pageBeds() {
    const [rows, available] = await Promise.all([api("/api/beds"), api("/api/beds/available")]);
    const availableIds = new Set(available.map((b) => b.bed_id));
    content.innerHTML = heading("Beds", "Bed inventory and live availability across all rooms.", "Add bed", "add-bed") + `<div class="mini-summary panel panel-body"><div><strong>${rows.length}</strong><span>Total beds</span></div><div><strong>${available.length}</strong><span>Available</span></div><div><strong>${rows.length - available.length}</strong><span>Occupied</span></div></div>` + tablePanel(rows, [
      { key: "block_code", label: "Block", render: (v) => `<span class="primary-cell">${esc(v)}</span>` }, { key: "room_number", label: "Room" },
      { key: "bed_label", label: "Bed" }, { key: "is_occupied", label: "Occupancy", render: (v) => badge(v ? "OCCUPIED" : "AVAILABLE") },
      { key: "is_active", label: "Status", render: (v) => badge(v ? "ACTIVE" : "INACTIVE") },
    ], { rowId: "bed_id", actions: [{ key: "bed-edit", label: "Edit" }] });
    listenSearch(); state.data.rooms = await api("/api/rooms"); state.data.availableBeds = available;
    state.handlers = { "bed-edit": (id) => { const r = rows.find((x) => x.bed_id == id); openForm("Edit bed", bedFields(state.data.rooms), (data) => api(`/api/beds/${id}`, { method: "PUT", body: JSON.stringify(data) }), r); } };
  }

  const bedFields = (rooms) => [
    { name: "room_id", label: "Room", type: "select", required: true, options: rooms.map((r) => ({ value: r.room_id, label: `${r.block_code} · ${r.room_number}` })) },
    { name: "bed_label", label: "Bed label", required: true, maxlength: 10 }, { name: "is_active", label: "Active", type: "checkbox", checkboxLabel: "Bed is active", default: true },
  ];

  async function pageAllocations() {
    const [rows, students, blocks, rooms, beds] = await Promise.all([api("/api/allocations"), api("/api/students"), api("/api/blocks"), api("/api/rooms"), api("/api/beds/available")]);
    state.data = { ...state.data, students, blocks, rooms, availableBeds: beds, allocations: rows };
    content.innerHTML = heading("Allocations", "Current residents, available assignments and complete bed history.", "Allocate bed", "add-allocation") + `<div class="mini-summary panel panel-body"><div><strong>${rows.filter((r) => r.status === "ACTIVE").length}</strong><span>Active residents</span></div><div><strong>${beds.length}</strong><span>Beds available</span></div><div><strong>${rows.filter((r) => r.status !== "ACTIVE").length}</strong><span>Past allocations</span></div></div>` + tablePanel(rows, [
      { key: "registration_no", label: "Student", render: (v, r) => `<span class="primary-cell">${esc(v)}</span><span class="sub-cell">${esc(r.first_name)} ${esc(r.last_name)}</span>` },
      { key: "block_code", label: "Residence", render: (v, r) => `${esc(v)} · ${esc(r.room_number)} · ${esc(r.bed_label)}` },
      { key: "allocation_date", label: "Allocated", render: (v) => fmtDate(v) }, { key: "expected_vacate_date", label: "Expected vacate", render: (v) => fmtDate(v) }, { key: "status", label: "Status", render: (v) => badge(v) },
    ], { rowId: "allocation_id", actions: [{ key: "allocation-view", label: "View" }] });
    listenSearch();
    state.handlers = { "allocation-view": (id) => { const r = rows.find((x) => x.allocation_id == id); openDetails(`Allocation #${id}`, r, [["Student", "registration_no"], ["Name", "first_name"], ["Hostel block", "block_name"], ["Room", "room_number"], ["Bed", "bed_label"], ["Allocation date", "allocation_date"], ["Expected vacate", "expected_vacate_date"], ["Actual vacate", "actual_vacate_date"], ["Status", "status"]]); } };
  }

  function allocationForm() {
    const students = state.data.students || [], blocks = state.data.blocks || [], rooms = state.data.rooms || [], beds = state.data.availableBeds || [];
    modalRoot.innerHTML = `<div class="modal" role="dialog" aria-modal="true"><div class="modal-header"><div><h2>Allocate a bed</h2><p>Only beds currently available in the database are selectable.</p></div><button class="modal-close" data-modal-close>×</button></div><form id="allocationForm" class="modal-form" novalidate><div class="form-grid">
      ${fieldMarkup({ name: "student_id", label: "Student", type: "select", required: true, options: students.map((s) => ({ value: s.student_id, label: `${s.registration_no} · ${s.first_name} ${s.last_name}` })) })}
      ${fieldMarkup({ name: "block_id", label: "Hostel block", type: "select", required: true, options: blocks.map((b) => ({ value: b.block_id, label: b.block_name })) })}
      ${fieldMarkup({ name: "room_id", label: "Room", type: "select", required: true, options: [] })}
      ${fieldMarkup({ name: "bed_id", label: "Available bed", type: "select", required: true, options: [] })}
      ${fieldMarkup({ name: "allocation_date", label: "Allocation date", type: "date", required: true, default: new Date().toISOString().slice(0,10) })}
      ${fieldMarkup({ name: "expected_vacate_date", label: "Expected vacate date", type: "date", required: true })}
    </div><div class="form-error" id="formError"></div><div class="modal-footer"><button type="button" class="button button-secondary" data-modal-close>Cancel</button><button class="button button-primary" type="submit">Create allocation</button></div></form></div>`;
    const blockSelect = $("#field-block_id", modalRoot), roomSelect = $("#field-room_id", modalRoot), bedSelect = $("#field-bed_id", modalRoot);
    const updateRooms = () => {
      const block = blocks.find((b) => String(b.block_id) === blockSelect.value);
      const roomsForBlock = rooms.filter((r) => String(r.block_id) === blockSelect.value);
      roomSelect.innerHTML = `<option value="">Select room</option>${roomsForBlock.map((r) => `<option value="${r.room_id}">${esc(r.room_number)} · ${esc(r.room_type)}</option>`).join("")}`;
      updateBeds();
    };
    const updateBeds = () => {
      const room = rooms.find((r) => String(r.room_id) === roomSelect.value);
      const options = beds.filter((b) => room && String(b.room_number) === String(room.room_number) && String(b.block_code) === String(blocks.find((x) => String(x.block_id) === String(room.block_id))?.block_code));
      bedSelect.innerHTML = `<option value="">Select available bed</option>${options.map((b) => `<option value="${b.bed_id}">${esc(b.bed_label)}</option>`).join("")}`;
      if (room && options.length === 0) bedSelect.innerHTML = `<option value="">No available beds</option>`;
      void block;
    };
    blockSelect.addEventListener("change", updateRooms); roomSelect.addEventListener("change", updateBeds);
    $("#allocationForm", modalRoot).addEventListener("submit", async (event) => {
      event.preventDefault(); const form = event.currentTarget; if (!form.reportValidity()) return;
      const data = Object.fromEntries(new FormData(form)); data.student_id = Number(data.student_id); data.bed_id = Number(data.bed_id);
      const button = $("button[type=submit]", form); button.disabled = true; button.textContent = "Allocating…";
      try { await api("/api/allocations", { method: "POST", body: JSON.stringify(data) }); closeModal(); toast("Bed allocated successfully."); await loadPage("allocations"); }
      catch (error) { $("#formError", form).textContent = error.message; button.disabled = false; button.textContent = "Create allocation"; }
    });
  }

  async function pageTransfers() {
    const [rows, allocations, beds] = await Promise.all([api("/api/transfers"), api("/api/allocations"), api("/api/beds/available")]);
    state.data.activeAllocations = allocations.filter((a) => a.status === "ACTIVE"); state.data.availableBeds = beds;
    content.innerHTML = heading("Transfers", "Move residents between beds while keeping the original allocation history.", "Transfer student", "add-transfer") + tablePanel(rows, [
      { key: "registration_no", label: "Student", render: (v) => `<span class="primary-cell">${esc(v)}</span>` }, { key: "from_allocation_id", label: "From allocation" },
      { key: "to_allocation_id", label: "New allocation" }, { key: "transfer_date", label: "Transfer date", render: (v) => fmtDate(v) }, { key: "reason", label: "Reason" },
    ], { rowId: "transfer_id", searchLabel: "transfers" }); listenSearch();
  }

  function transferForm() {
    const active = state.data.activeAllocations || [], beds = state.data.availableBeds || [];
    const fields = [
      { name: "from_allocation_id", label: "Resident / current allocation", type: "select", required: true, options: active.map((a) => ({ value: a.allocation_id, label: `${a.registration_no} · ${a.first_name} ${a.last_name} · ${a.block_code}/${a.room_number}/${a.bed_label}` })) },
      { name: "to_bed_id", label: "Available target bed", type: "select", required: true, options: beds.map((b) => ({ value: b.bed_id, label: `${b.block_code} · ${b.room_number} · Bed ${b.bed_label}` })) },
      { name: "transfer_date", label: "Transfer date", type: "date", required: true, default: new Date().toISOString().slice(0,10) },
      { name: "expected_vacate_date", label: "Expected vacate date", type: "date", required: true }, { name: "reason", label: "Reason", type: "textarea", required: true, full: true },
    ];
    openForm("Transfer student", fields, async (data) => {
      const allocation = active.find((a) => String(a.allocation_id) === String(data.from_allocation_id));
      data.student_id = allocation.student_id; data.from_allocation_id = Number(data.from_allocation_id); data.to_bed_id = Number(data.to_bed_id);
      await api("/api/transfers", { method: "POST", body: JSON.stringify(data) });
    });
  }

  async function pageFees() {
    const [fees, payments, dues] = await Promise.all([api("/api/fees"), api("/api/payments"), api("/api/reports/fee-dues")]);
    state.data.fees = fees; state.data.students = await api("/api/students");
    const dueTotal = dues.reduce((sum, r) => sum + Number(r.balance || 0), 0);
    content.innerHTML = heading("Fees & payments", "Fee schedules, outstanding balances and recorded payments.", "Record payment", "add-payment") + `<div class="stats-grid"><div class="stat-card gold"><div class="stat-top"><span class="stat-label">Outstanding balance</span><span class="stat-icon">₹</span></div><div class="stat-value">${esc(fmtMoney(dueTotal))}</div><div class="stat-note">Across ${dues.length} student fee items</div></div><div class="stat-card"><div class="stat-top"><span class="stat-label">Fee schedules</span><span class="stat-icon">▤</span></div><div class="stat-value">${fees.length}</div><div class="stat-note">Active and historical schedules</div></div><div class="stat-card blue"><div class="stat-top"><span class="stat-label">Payments recorded</span><span class="stat-icon">↗</span></div><div class="stat-value">${payments.length}</div><div class="stat-note">Payment history entries</div></div><div class="stat-card coral"><div class="stat-top"><span class="stat-label">Students with dues</span><span class="stat-icon">♙</span></div><div class="stat-value">${new Set(dues.map((d) => d.student_id)).size}</div><div class="stat-note">Based on live fee-dues report</div></div></div>
      <div class="two-col"><section><div class="panel"><div class="panel-header"><div><h2>Fee schedules</h2><p>Rates and due dates</p></div><button class="button button-secondary button-small" data-page-action="add-fee">＋ Add schedule</button></div><div id="feeScheduleHost"></div></div><div class="panel"><div class="panel-header"><div><h2>Student fee dues</h2><p>Outstanding balances by student and fee</p></div></div><div id="feeDuesHost"></div></div></section><section><div class="panel"><div class="panel-header"><div><h2>Payment history</h2><p>Recent transactions</p></div></div><div id="paymentHistoryHost"></div></div></section></div>`;
    $("#feeScheduleHost").innerHTML = tableMarkup(fees, [{ key: "academic_year", label: "Year" }, { key: "term", label: "Term" }, { key: "fee_type", label: "Fee type", render: (v) => titleCase(v) }, { key: "amount", label: "Amount", render: (v) => fmtMoney(v) }, { key: "due_date", label: "Due", render: (v) => fmtDate(v) }, { key: "is_active", label: "Status", render: (v) => badge(v ? "ACTIVE" : "INACTIVE") }]);
    $("#feeDuesHost").innerHTML = tableMarkup(dues, [{ key: "registration_no", label: "Student", render: (v, r) => `${esc(v)} · ${esc(r.first_name)} ${esc(r.last_name)}` }, { key: "fee_type", label: "Fee", render: (v) => titleCase(v) }, { key: "fee_amount", label: "Amount", render: (v) => fmtMoney(v) }, { key: "paid_amount", label: "Paid", render: (v) => fmtMoney(v) }, { key: "balance", label: "Balance", render: (v) => `<strong class="money-due">${esc(fmtMoney(v))}</strong>` }]);
    $("#paymentHistoryHost").innerHTML = tableMarkup(payments.slice(0, 12), [{ key: "registration_no", label: "Student" }, { key: "fee_type", label: "Fee", render: (v) => titleCase(v) }, { key: "amount", label: "Amount", render: (v) => fmtMoney(v) }, { key: "payment_method", label: "Method", render: (v) => titleCase(v) }, { key: "payment_date", label: "Date", render: (v) => fmtDate(v) }]);
  }

  async function paymentForm() {
    const [students, fees] = await Promise.all([api("/api/students"), api("/api/fees")]);
    openForm("Record payment", [
      { name: "student_id", label: "Student", type: "select", required: true, options: students.map((s) => ({ value: s.student_id, label: `${s.registration_no} · ${s.first_name} ${s.last_name}` })) },
      { name: "fee_schedule_id", label: "Fee schedule", type: "select", required: true, options: fees.map((f) => ({ value: f.fee_schedule_id, label: `${titleCase(f.fee_type)} · ${f.academic_year} · ${fmtMoney(f.amount)}` })) },
      { name: "amount", label: "Amount", type: "number", min: "0.01", step: "0.01", required: true },
      { name: "payment_method", label: "Payment method", type: "select", required: true, options: ["CASH", "CARD", "BANK_TRANSFER", "UPI", "OTHER"].map((v) => ({ value: v, label: titleCase(v) })) },
      { name: "transaction_reference", label: "Transaction reference", maxlength: 100 }, { name: "payment_date", label: "Payment date", type: "datetime-local" }, { name: "notes", label: "Notes", type: "textarea", full: true },
    ], (data) => api("/api/payments", { method: "POST", body: JSON.stringify(data) }));
  }

  async function pageVisitors() {
    const rows = await api("/api/visitors");
    content.innerHTML = heading("Visitors", "Visitor register, arrival details and active check-ins.", "Add visitor", "add-visitor") + tablePanel(rows, [
      { key: "visitor_name", label: "Visitor", render: (v, r) => `<span class="primary-cell">${esc(v)}</span><span class="sub-cell">${esc(r.relationship_to_student)} · ${esc(r.phone)}</span>` },
      { key: "registration_no", label: "Visiting student" }, { key: "purpose", label: "Purpose" }, { key: "check_in", label: "Check-in", render: (v) => fmtDateTime(v) },
      { key: "check_out", label: "Check-out", render: (v) => v ? fmtDateTime(v) : badge("ACTIVE") },
    ], { rowId: "visitor_id", searchLabel: "visitors", actions: [{ key: "visitor-checkout", label: "Check out" }] }); listenSearch(); state.data.visitors = rows;
    state.handlers = { "visitor-checkout": (id) => { const row = rows.find((r) => r.visitor_id == id); if (row.check_out) return toast("This visitor has already checked out.", "error"); api(`/api/visitors/${id}/checkout`, { method: "PUT", body: JSON.stringify({}) }).then(() => { toast("Visitor checked out."); loadPage("visitors"); }).catch((e) => toast(e.message, "error")); } };
  }

  async function visitorForm() {
    const students = await api("/api/students");
    openForm("Add visitor", [
      { name: "student_id", label: "Visiting student", type: "select", required: true, options: students.map((s) => ({ value: s.student_id, label: `${s.registration_no} · ${s.first_name} ${s.last_name}` })) },
      { name: "visitor_name", label: "Visitor name", required: true }, { name: "relationship_to_student", label: "Relationship", required: true },
      { name: "phone", label: "Phone", required: true }, { name: "purpose", label: "Purpose", required: true, full: true },
    ], (data) => api("/api/visitors", { method: "POST", body: JSON.stringify(data) }));
  }

  async function pageComplaints() {
    const rows = await api("/api/complaints"); const unresolved = rows.filter((r) => ["OPEN", "IN_PROGRESS"].includes(r.status)).length;
    content.innerHTML = heading("Complaints", "Student concerns, response priority and resolution progress.", "New complaint", "add-complaint") + `<div class="mini-summary panel panel-body"><div><strong>${rows.length}</strong><span>Total complaints</span></div><div><strong>${unresolved}</strong><span>Unresolved</span></div><div><strong>${rows.filter((r) => r.priority === "URGENT" || r.priority === "HIGH").length}</strong><span>High priority</span></div></div>` + tablePanel(rows, [
      { key: "subject", label: "Complaint", render: (v, r) => `<span class="primary-cell">${esc(v)}</span><span class="sub-cell">${esc(r.registration_no)} · ${esc(titleCase(r.category))}</span>` },
      { key: "priority", label: "Priority", render: (v) => badge(v) }, { key: "status", label: "Status", render: (v) => badge(v) },
      { key: "submitted_at", label: "Submitted", render: (v) => fmtDate(v) }, { key: "assigned_to", label: "Assigned user", render: (v) => v ? `User #${esc(v)}` : "Unassigned" },
    ], { rowId: "complaint_id", actions: [{ key: "complaint-edit", label: "Update" }] }); listenSearch(); state.data.complaints = rows;
    state.handlers = { "complaint-edit": (id) => { const r = rows.find((x) => x.complaint_id == id); openForm("Update complaint", complaintUpdateFields, (data) => api(`/api/complaints/${id}`, { method: "PUT", body: JSON.stringify(data) }), r); } };
  }

  const complaintUpdateFields = [
    { name: "status", label: "Status", type: "select", options: ["OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED"].map((v) => ({ value: v, label: titleCase(v) })) },
    { name: "priority", label: "Priority", type: "select", options: ["LOW", "MEDIUM", "HIGH", "URGENT"].map((v) => ({ value: v, label: titleCase(v) })) },
    { name: "assigned_to", label: "Assigned staff user ID", type: "number", min: 1, nullable: true }, { name: "resolved_at", label: "Resolved at", type: "datetime-local", nullable: true },
  ];

  async function complaintForm() {
    const students = await api("/api/students");
    openForm("New complaint", [
      { name: "student_id", label: "Student", type: "select", required: true, options: students.map((s) => ({ value: s.student_id, label: `${s.registration_no} · ${s.first_name} ${s.last_name}` })) },
      { name: "category", label: "Category", type: "select", required: true, options: ["CLEANLINESS", "FOOD", "NOISE", "SECURITY", "WATER", "ELECTRICAL", "OTHER"].map((v) => ({ value: v, label: titleCase(v) })) },
      { name: "priority", label: "Priority", type: "select", default: "MEDIUM", options: ["LOW", "MEDIUM", "HIGH", "URGENT"].map((v) => ({ value: v, label: titleCase(v) })) },
      { name: "subject", label: "Subject", required: true }, { name: "description", label: "Description", type: "textarea", required: true, full: true },
    ], (data) => api("/api/complaints", { method: "POST", body: JSON.stringify(data) }));
  }

  async function pageMaintenance() {
    const rows = await api("/api/maintenance"); const pending = rows.filter((r) => !["COMPLETED", "CANCELLED"].includes(r.status)).length;
    content.innerHTML = heading("Maintenance", "Facilities requests by room, category and completion status.", "Add request", "add-maintenance") + `<div class="mini-summary panel panel-body"><div><strong>${rows.length}</strong><span>Total requests</span></div><div><strong>${pending}</strong><span>Pending</span></div><div><strong>${rows.filter((r) => r.status === "COMPLETED").length}</strong><span>Completed</span></div></div>` + tablePanel(rows, [
      { key: "category", label: "Request", render: (v, r) => `<span class="primary-cell">${esc(titleCase(v))}</span><span class="sub-cell">${esc(r.block_code)} · Room ${esc(r.room_number)}</span>` },
      { key: "description", label: "Description" }, { key: "priority", label: "Priority", render: (v) => badge(v) }, { key: "status", label: "Status", render: (v) => badge(v) },
      { key: "requested_at", label: "Requested", render: (v) => fmtDate(v) },
    ], { rowId: "maintenance_id", actions: [{ key: "maintenance-edit", label: "Update" }] }); listenSearch(); state.data.maintenance = rows;
    state.handlers = { "maintenance-edit": (id) => { const r = rows.find((x) => x.maintenance_id == id); openForm("Update maintenance request", maintenanceUpdateFields, (data) => api(`/api/maintenance/${id}`, { method: "PUT", body: JSON.stringify(data) }), r); } };
  }

  const maintenanceUpdateFields = [
    { name: "status", label: "Status", type: "select", options: ["OPEN", "ASSIGNED", "IN_PROGRESS", "COMPLETED", "CANCELLED"].map((v) => ({ value: v, label: titleCase(v) })) },
    { name: "priority", label: "Priority", type: "select", options: ["LOW", "MEDIUM", "HIGH", "URGENT"].map((v) => ({ value: v, label: titleCase(v) })) },
    { name: "assigned_to", label: "Assigned staff user ID", type: "number", min: 1, nullable: true }, { name: "completed_at", label: "Completed at", type: "datetime-local", nullable: true },
  ];

  async function maintenanceForm() {
    const [rooms, students] = await Promise.all([api("/api/rooms"), api("/api/students")]);
    openForm("New maintenance request", [
      { name: "room_id", label: "Room", type: "select", required: true, options: rooms.map((r) => ({ value: r.room_id, label: `${r.block_code} · ${r.room_number}` })) },
      { name: "requested_by_student_id", label: "Requested by student", type: "select", options: students.map((s) => ({ value: s.student_id, label: `${s.registration_no} · ${s.first_name} ${s.last_name}` })) },
      { name: "category", label: "Category", type: "select", required: true, options: ["PLUMBING", "ELECTRICAL", "FURNITURE", "CLEANING", "STRUCTURAL", "OTHER"].map((v) => ({ value: v, label: titleCase(v) })) },
      { name: "priority", label: "Priority", type: "select", default: "MEDIUM", options: ["LOW", "MEDIUM", "HIGH", "URGENT"].map((v) => ({ value: v, label: titleCase(v) })) },
      { name: "description", label: "Description", type: "textarea", required: true, full: true },
    ], (data) => api("/api/maintenance", { method: "POST", body: JSON.stringify(data) }));
  }

  async function pageVacating() {
    const [rows, vacating, availableBeds] = await Promise.all([api("/api/allocations"), api("/api/vacating"), api("/api/beds/available")]);
    state.data.availableBeds = availableBeds;
    const active = rows.filter((r) => r.status === "ACTIVE");
    content.innerHTML = heading("Vacating records", "Record resident departures and release their assigned beds.", "Record vacating", "add-vacating") + `<div class="mini-summary panel panel-body"><div><strong>${active.length}</strong><span>Current residents</span></div><div><strong>${vacating.length}</strong><span>Processed departures</span></div><div><strong>${state.data.availableBeds?.length ?? "—"}</strong><span>Beds available</span></div></div><div class="panel"><div class="panel-header"><div><h2>Active allocations</h2><p>Vacating updates the allocation and makes the bed available.</p></div></div>${tableMarkup(active, [{ key: "registration_no", label: "Student", render: (v, r) => `${esc(v)} · ${esc(r.first_name)} ${esc(r.last_name)}` }, { key: "block_code", label: "Block" }, { key: "room_number", label: "Room" }, { key: "bed_label", label: "Bed" }, { key: "allocation_date", label: "Allocated", render: (v) => fmtDate(v) }, { key: "expected_vacate_date", label: "Expected vacate", render: (v) => fmtDate(v) }], "allocation_id", [{ key: "vacate", label: "Vacate" }])}</div><div class="panel"><div class="panel-header"><div><h2>Processed vacating records</h2><p>Departure history from the database</p></div></div>${tableMarkup(vacating, [{ key: "registration_no", label: "Student" }, { key: "block_code", label: "Block" }, { key: "room_number", label: "Room" }, { key: "vacating_date", label: "Vacated", render: (v) => fmtDate(v) }, { key: "reason", label: "Reason" }, { key: "deposit_refund", label: "Refund", render: (v) => fmtMoney(v) }], "vacating_id")}</div>`;
    state.data.activeAllocations = active; state.data.vacating = vacating;
    state.handlers = { vacate: (id) => { const allocation = active.find((r) => r.allocation_id == id); vacatingForm(allocation); } };
  }

  function vacatingForm(allocation) {
    openForm(`Vacate ${allocation.registration_no}`, [
      { name: "vacating_date", label: "Vacating date", type: "date", required: true, default: new Date().toISOString().slice(0,10) },
      { name: "reason", label: "Reason", required: true }, { name: "deposit_refund", label: "Deposit refund", type: "number", min: 0, step: "0.01", default: 0 },
      { name: "inspection_notes", label: "Inspection notes", type: "textarea", full: true },
    ], (data) => api("/api/vacating", { method: "POST", body: JSON.stringify({ ...data, allocation_id: allocation.allocation_id }) }));
  }

  const reportSpecs = [
    ["occupancy", "Occupancy report", "Occupied beds and capacity by room", "▥", "/api/reports/occupancy", [{ key: "block_code", label: "Block" }, { key: "room_number", label: "Room" }, { key: "capacity", label: "Capacity" }, { key: "bed_count", label: "Beds" }, { key: "occupied_beds", label: "Occupied" }, { key: "available_capacity", label: "Open capacity" }, { key: "occupancy_percent", label: "Occupancy %", render: (v) => `${v}%` }]],
    ["vacancies", "Vacancy report", "Available beds ready for allocation", "▱", "/api/reports/vacancies", [{ key: "block_code", label: "Block" }, { key: "room_number", label: "Room" }, { key: "bed_label", label: "Bed" }, { key: "block_name", label: "Residence" }]],
    ["fee-dues", "Fee dues", "Students with balances on active schedules", "₹", "/api/reports/fee-dues", [{ key: "registration_no", label: "Registration" }, { key: "first_name", label: "First name" }, { key: "last_name", label: "Last name" }, { key: "fee_type", label: "Fee", render: (v) => titleCase(v) }, { key: "fee_amount", label: "Amount", render: (v) => fmtMoney(v) }, { key: "paid_amount", label: "Paid", render: (v) => fmtMoney(v) }, { key: "balance", label: "Balance", render: (v) => fmtMoney(v) }]],
    ["allocation-history", "Allocation history", "Current and previous bed assignments", "⇄", "/api/reports/allocation-history", [{ key: "registration_no", label: "Registration" }, { key: "first_name", label: "First name" }, { key: "last_name", label: "Last name" }, { key: "block_code", label: "Block" }, { key: "room_number", label: "Room" }, { key: "bed_label", label: "Bed" }, { key: "allocation_date", label: "Allocated", render: (v) => fmtDate(v) }, { key: "status", label: "Status", render: (v) => badge(v) }]],
    ["visitors", "Visitor report", "Guest visits and check-out records", "♧", "/api/reports/visitors", [{ key: "visitor_name", label: "Visitor" }, { key: "registration_no", label: "Student" }, { key: "purpose", label: "Purpose" }, { key: "check_in", label: "Check-in", render: (v) => fmtDateTime(v) }, { key: "check_out", label: "Check-out", render: (v) => fmtDateTime(v) }]],
    ["complaints", "Unresolved complaints", "Open items prioritized for follow-up", "☷", "/api/reports/complaints", [{ key: "registration_no", label: "Student" }, { key: "category", label: "Category", render: (v) => titleCase(v) }, { key: "subject", label: "Subject" }, { key: "priority", label: "Priority", render: (v) => badge(v) }, { key: "status", label: "Status", render: (v) => badge(v) }, { key: "submitted_at", label: "Submitted", render: (v) => fmtDate(v) }]],
    ["maintenance", "Maintenance status", "Facilities queue by room and status", "⚒", "/api/reports/maintenance", [{ key: "block_code", label: "Block" }, { key: "room_number", label: "Room" }, { key: "category", label: "Category", render: (v) => titleCase(v) }, { key: "priority", label: "Priority", render: (v) => badge(v) }, { key: "status", label: "Status", render: (v) => badge(v) }, { key: "requested_at", label: "Requested", render: (v) => fmtDate(v) }]],
  ];

  async function pageReports(selected = "occupancy") {
    content.innerHTML = heading("Reports", "Live operational reports generated from the hostel database.") + `<div class="report-grid">${reportSpecs.map(([id, title, desc, icon]) => `<button class="report-card ${id === selected ? "selected" : ""}" data-report="${id}"><span class="report-icon">${icon}</span><span><strong>${esc(title)}</strong><small>${esc(desc)}</small></span></button>`).join("")}</div><div class="panel"><div class="panel-header"><div><h2 id="reportTitle">${esc(reportSpecs.find((x) => x[0] === selected)[1])}</h2><p id="reportDescription">${esc(reportSpecs.find((x) => x[0] === selected)[2])}</p></div><span class="form-hint" id="reportCount"></span></div><div id="reportHost"><div class="page-loading"><span class="spinner"></span>Loading report…</div></div></div>`;
    const loadReport = async (id) => {
      const spec = reportSpecs.find((x) => x[0] === id); if (!spec) return;
      $("#reportTitle").textContent = spec[1]; $("#reportDescription").textContent = spec[2];
      document.querySelectorAll(".report-card").forEach((b) => b.classList.toggle("selected", b.dataset.report === id));
      $("#reportHost").innerHTML = `<div class="page-loading"><span class="spinner"></span>Loading report…</div>`;
      try { const rows = await api(spec[4]); $("#reportHost").innerHTML = tableMarkup(rows, spec[5]); $("#reportCount").textContent = `${rows.length} records`; }
      catch (error) { $("#reportHost").innerHTML = `<div class="error-panel">${esc(error.message)}<button class="button button-secondary button-small" data-report="${esc(id)}">Retry</button></div>`; }
    };
    document.querySelectorAll(".report-card").forEach((button) => button.addEventListener("click", () => loadReport(button.dataset.report)));
    await loadReport(selected);
  }

  async function pageDashboard() {
    const [stats, occupancy, vacancies, dues, complaints, maintenance, visitors, allocations] = await Promise.all([
      api("/api/stats"), api("/api/reports/occupancy"), api("/api/beds/available"), api("/api/reports/fee-dues"), api("/api/complaints"), api("/api/maintenance"), api("/api/visitors"), api("/api/allocations"),
    ]);
    const pendingComplaints = complaints.filter((r) => ["OPEN", "IN_PROGRESS"].includes(r.status)).length;
    const pendingMaintenance = maintenance.filter((r) => !["COMPLETED", "CANCELLED"].includes(r.status)).length;
    const owed = dues.reduce((sum, r) => sum + Number(r.balance || 0), 0);
    const blocks = new Map();
    occupancy.forEach((r) => { const curr = blocks.get(r.block_code) || { name: r.block_name, capacity: 0, occupied: 0 }; curr.capacity += Number(r.capacity); curr.occupied += Number(r.occupied_beds); blocks.set(r.block_code, curr); });
    const blockChart = [...blocks.entries()].map(([code, row]) => `<div class="occupancy-row"><span class="occupancy-name">${esc(row.name || code)}</span><div class="progress-track"><div class="progress-fill" style="width:${row.capacity ? Math.min(100, row.occupied / row.capacity * 100) : 0}%"></div></div><span class="occupancy-value">${row.occupied} / ${row.capacity}</span></div>`).join("") || emptyState("No occupancy data");
    const activities = [
      ...allocations.map((r) => ({ when: r.created_at || r.allocation_date, icon: "⇄", title: `${r.status === "ACTIVE" ? "Allocation active" : `Allocation ${titleCase(r.status)}`} · ${r.registration_no}`, detail: `${r.block_code} · ${r.room_number} · Bed ${r.bed_label}` })),
      ...visitors.map((r) => ({ when: r.check_in, icon: "♧", title: `Visitor · ${r.visitor_name}`, detail: `Visiting ${r.registration_no}` })),
      ...complaints.map((r) => ({ when: r.submitted_at, icon: "☷", title: `Complaint · ${r.subject}`, detail: `${titleCase(r.status)} · ${r.registration_no}` })),
      ...maintenance.map((r) => ({ when: r.requested_at, icon: "⚒", title: `Maintenance · ${titleCase(r.category)}`, detail: `${r.block_code} · Room ${r.room_number}` })),
    ].sort((a, b) => new Date(b.when || 0) - new Date(a.when || 0)).slice(0, 6);
    const activityMarkup = activities.length ? activities.map((a) => `<div class="activity-item"><span class="activity-dot">${esc(a.icon)}</span><div class="activity-copy"><strong>${esc(a.title)}</strong><small>${esc(a.detail)} · ${esc(fmtDateTime(a.when))}</small></div></div>`).join("") : emptyState("No recent activity");
    content.innerHTML = heading("Good day, Administrator", "Here’s the live picture of residence operations across campus.", "Create allocation", "add-allocation") + `<div class="stats-grid">
      ${statCard("Total students", stats.students, "♙", "All registered residents", "")}${statCard("Hostel blocks", stats.hostel_blocks, "▤", "Active residences", "green")}${statCard("Total rooms", stats.rooms, "▦", "Across all blocks", "blue")}${statCard("Total beds", stats.beds, "▱", "Physical bed inventory", "gold")}
      ${statCard("Occupied beds", stats.active_allocations, "⌂", "Current active residents", "blue")}${statCard("Available beds", vacancies.length, "＋", "Ready for allocation", "green")}${statCard("Pending fees", fmtMoney(owed), "₹", `${dues.length} fee items outstanding`, "gold")}${statCard("Active allocations", stats.active_allocations, "⇄", "Current assignments", "")}
    </div><div class="dashboard-grid"><div><section class="panel"><div class="panel-header"><div><h2>Occupancy by block</h2><p>Residents compared with room capacity · live report</p></div><button class="button-plain" data-goto="reports">View report →</button></div><div class="panel-body"><div class="occupancy-list">${blockChart}</div></div></section><section class="panel"><div class="panel-header"><div><h2>Service overview</h2><p>Current work requiring attention</p></div></div><div class="panel-body"><div class="mini-summary"><div><strong>${pendingComplaints}</strong><span>Open complaints</span></div><div><strong>${pendingMaintenance}</strong><span>Maintenance requests</span></div><div><strong>${dues.length}</strong><span>Fee items due</span></div></div></div></section></div><section class="panel"><div class="panel-header"><div><h2>Recent activity</h2><p>Latest records from live modules</p></div></div><div class="panel-body"><div class="activity-list">${activityMarkup}</div></div></section></div>`;
    state.data.stats = stats; state.data.availableBeds = vacancies;
  }

  function statCard(label, value, icon, note, color) {
    return `<div class="stat-card ${esc(color)}"><div class="stat-top"><span class="stat-label">${esc(label)}</span><span class="stat-icon">${esc(icon)}</span></div><div class="stat-value">${esc(value)}</div><div class="stat-note">${esc(note)}</div></div>`;
  }

  async function loadPage(page, report = "occupancy") {
    state.page = page; state.handlers = {}; state.filter = "";
    $("#pageCrumb").textContent = pageTitles[page] || "Dashboard";
    document.querySelectorAll(".nav-item").forEach((item) => item.classList.toggle("active", item.dataset.page === page));
    closeMobileNav(); content.innerHTML = `<div class="page-loading"><span class="spinner"></span>Loading ${esc(pageTitles[page] || "workspace")}…</div>`;
    try {
      const loaders = { dashboard: pageDashboard, students: pageStudents, blocks: pageBlocks, rooms: pageRooms, beds: pageBeds, allocations: pageAllocations, transfers: pageTransfers, fees: pageFees, visitors: pageVisitors, complaints: pageComplaints, maintenance: pageMaintenance, vacating: pageVacating, reports: () => pageReports(report) };
      await (loaders[page] || pageDashboard)();
    } catch (error) {
      content.innerHTML = `${heading(pageTitles[page] || "Dashboard", "Live information from the hostel management database.")}<div class="error-panel"><span>${esc(error.message)}</span><button class="button button-secondary button-small" data-retry>Retry</button></div>`;
    }
  }

  function closeMobileNav() { $("#sidebar").classList.remove("open"); $("#mobileScrim").classList.remove("show"); }

  async function checkHealth() {
    const status = $("#apiStatus");
    try { const result = await api("/api/health"); status.className = "api-status connected"; status.innerHTML = `<i></i>${esc(result.database || "Connected")}`; }
    catch { status.className = "api-status failed"; status.innerHTML = "<i></i>Connection issue"; }
  }

  document.addEventListener("click", (event) => {
    const nav = event.target.closest("[data-page]");
    if (nav) { loadPage(nav.dataset.page); return; }
    const pageAction = event.target.closest("[data-page-action]");
    if (pageAction) { handlePageAction(pageAction.dataset.pageAction).catch((error) => toast(error.message, "error")); return; }
    const tableAction = event.target.closest("[data-action]");
    if (tableAction) { state.handlers[tableAction.dataset.action]?.(tableAction.dataset.id); return; }
    if (event.target.closest("[data-modal-close]") || event.target === modalRoot) { closeModal(); return; }
    const goto = event.target.closest("[data-goto]"); if (goto) { loadPage(goto.dataset.goto); return; }
    if (event.target.closest("[data-retry]")) { loadPage(state.page); return; }
    const report = event.target.closest("[data-report]"); if (report && state.page === "reports" && !report.classList.contains("report-card")) pageReports(report.dataset.report);
  });

  async function handlePageAction(action) {
    if (action === "add-student") openForm("Add student", studentFields, (data) => api("/api/students", { method: "POST", body: JSON.stringify(data) }));
    if (action === "add-block") openForm("Add hostel block", blockFields, (data) => api("/api/blocks", { method: "POST", body: JSON.stringify(data) }));
    if (action === "add-room") { const blocks = await api("/api/blocks"); openForm("Add room", roomFields(blocks), (data) => api("/api/rooms", { method: "POST", body: JSON.stringify(data) })); }
    if (action === "add-bed") { const rooms = await api("/api/rooms"); openForm("Add bed", bedFields(rooms), (data) => api("/api/beds", { method: "POST", body: JSON.stringify(data) })); }
    if (action === "add-allocation") { await pageAllocationsData(); allocationForm(); }
    if (action === "add-transfer") { await pageTransfersData(); transferForm(); }
    if (action === "add-fee") { openForm("Add fee schedule", [
      { name: "academic_year", label: "Academic year", required: true, placeholder: "2026-2027", maxlength: 9 }, { name: "term", label: "Term", required: true },
      { name: "fee_type", label: "Fee type", type: "select", required: true, options: ["HOSTEL", "MESS", "SECURITY_DEPOSIT", "OTHER"].map((v) => ({ value: v, label: titleCase(v) })) },
      { name: "amount", label: "Amount", type: "number", min: "0.01", step: "0.01", required: true }, { name: "due_date", label: "Due date", type: "date", required: true },
    ], (data) => api("/api/fees", { method: "POST", body: JSON.stringify(data) })); }
    if (action === "add-payment") await paymentForm();
    if (action === "add-visitor") await visitorForm();
    if (action === "add-complaint") await complaintForm();
    if (action === "add-maintenance") await maintenanceForm();
    if (action === "add-vacating") { const rows = await api("/api/allocations"); const active = rows.filter((r) => r.status === "ACTIVE"); if (!active.length) return toast("There are no active allocations to vacate.", "error"); openForm("Record vacating", [
      { name: "allocation_id", label: "Resident allocation", type: "select", required: true, options: active.map((a) => ({ value: a.allocation_id, label: `${a.registration_no} · ${a.block_code}/${a.room_number}/${a.bed_label}` })) },
      { name: "vacating_date", label: "Vacating date", type: "date", required: true, default: new Date().toISOString().slice(0,10) }, { name: "reason", label: "Reason", required: true },
      { name: "deposit_refund", label: "Deposit refund", type: "number", min: 0, step: "0.01", default: 0 }, { name: "inspection_notes", label: "Inspection notes", type: "textarea", full: true },
    ], (data) => api("/api/vacating", { method: "POST", body: JSON.stringify({ ...data, allocation_id: Number(data.allocation_id) }) })); }
  }

  async function pageAllocationsData() {
    const [students, blocks, rooms, availableBeds] = await Promise.all([api("/api/students"), api("/api/blocks"), api("/api/rooms"), api("/api/beds/available")]);
    state.data = { ...state.data, students, blocks, rooms, availableBeds };
  }
  async function pageTransfersData() {
    const [allocations, beds] = await Promise.all([api("/api/allocations"), api("/api/beds/available")]);
    state.data.activeAllocations = allocations.filter((a) => a.status === "ACTIVE"); state.data.availableBeds = beds;
  }

  $("#menuToggle").addEventListener("click", () => { $("#sidebar").classList.add("open"); $("#mobileScrim").classList.add("show"); });
  $("#mobileScrim").addEventListener("click", closeMobileNav);
  $("#refreshButton").addEventListener("click", () => { checkHealth(); loadPage(state.page); });
  document.addEventListener("keydown", (event) => { if (event.key === "Escape") closeModal(); });
  checkHealth(); loadPage("dashboard");
})();
