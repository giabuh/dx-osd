// Cold-lead follow-up agent (DX-OS [I] space). Source of the "Plan follow-ups with Jev" Code step in
// activepieces/flows/cold-lead-followup.json, which runs on a daily schedule. For every open Lead with
// no change in `staleDays`, Jev decides the next action and a CRM Task is created for the Lead owner.
// It never changes a Lead's status itself -- closing a Lead stays a human decision.

// --- Copied verbatim from sync.mjs / intelligence.mjs; followup.test.mjs fails if the copies drift. ---

async function request(fetchFn, method, url, headers, body) {
	const res = await fetchFn(url, {
		method,
		headers: { 'Content-Type': 'application/json', ...headers },
		body: body === undefined ? undefined : JSON.stringify(body),
	});
	if (!res.ok) throw new Error(`${method} ${url} failed: ${res.status} ${await res.text()}`);
	return res.json();
}

// One TypeSafe System One call: every question is evaluated against the same state.
export async function askJev({ config, fetchFn, state, questions }) {
	const res = await request(
		fetchFn,
		'POST',
		(config.jevBaseUrl || 'https://api.typesafe.ai') + '/v1/systemone',
		{ Authorization: `Bearer ${config.jevApiKey}` },
		{ model: config.jevModel || 'jev-latest', state, questions },
	);
	return res.answers;
}

// --- Follow-up-specific. ---

export const NEXT_ACTIONS = {
	call: 'Call the customer: they showed buying interest or left a phone number',
	message: 'Send a follow-up message: they were interested but went quiet in chat',
	review_close: 'The Lead looks dead, spam, or not a real customer; a salesperson should review closing it',
	wait: 'Too early or nothing useful to do yet',
};
const TASKS = {
	call: { title: 'Gọi lại khách', priority: 'High' },
	message: { title: 'Nhắn tin chăm sóc lại khách', priority: 'Medium' },
	review_close: { title: 'Xem xét đóng Lead', priority: 'Low' },
};

// Frappe stores datetimes as "YYYY-MM-DD HH:MM:SS" in the site timezone (Asia/Kolkata when unset), so
// every date we compare or write is rendered in that zone. Date math stays in code, not in Jev.
const siteDatetime = (d, timeZone) =>
	new Intl.DateTimeFormat('sv-SE', { timeZone, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23' }).format(d);
const daysBetween = (earlier, later) => Math.floor((Date.parse(later.replace(' ', 'T') + 'Z') - Date.parse(earlier.replace(' ', 'T') + 'Z')) / 86400000);

export async function planFollowups({ config, fetchFn, now = new Date() }) {
	const crmHeaders = { Authorization: `token ${config.crmApiToken}`, ...(config.crmHost && { Host: config.crmHost }) };
	const crm = (method, path, body) => request(fetchFn, method, config.crmBaseUrl + path, crmHeaders, body);
	const query = (doctype, params) =>
		crm('GET', `/api/resource/${doctype}?` + new URLSearchParams(Object.fromEntries(Object.entries(params).map(([k, v]) => [k, JSON.stringify(v)]))));

	const staleDays = Number(config.staleDays ?? 3);
	const threshold = Number(config.confidenceThreshold ?? 0.7);
	const openStatuses = String(config.openStatuses ?? 'New,Contacted,Nurture').split(',').map((s) => s.trim());
	const timeZone = (await crm('GET', '/api/method/frappe.client.get_time_zone')).message.time_zone || 'Asia/Kolkata';
	const siteNow = siteDatetime(now, timeZone);

	const leads = (
		await query('CRM Lead', {
			filters: [['status', 'in', openStatuses], ['modified', '<', siteDatetime(new Date(now.getTime() - staleDays * 86400000), timeZone)]],
			fields: ['name', 'lead_name', 'status', 'source', 'lead_owner', 'modified', 'mobile_no', 'email', 'ai_intent', 'ai_hotness'],
			order_by: 'modified asc',
			limit_page_length: Number(config.maxLeads ?? 20),
		})
	).data;

	const results = [];
	for (const lead of leads) {
		const openTasks = (
			await query('CRM Task', {
				filters: [['reference_doctype', '=', 'CRM Lead'], ['reference_docname', '=', lead.name], ['status', 'in', ['Backlog', 'Todo', 'In Progress']]],
				fields: ['name'],
			})
		).data;
		if (openTasks.length) {
			results.push({ lead: lead.name, action: 'skipped', reason: 'open task exists' });
			continue;
		}
		const notes = (
			await query('FCRM Note', {
				filters: [['reference_doctype', '=', 'CRM Lead'], ['reference_docname', '=', lead.name]],
				fields: ['title', 'content'],
				order_by: 'creation desc',
				limit_page_length: 5,
			})
		).data;
		const daysSinceUpdate = daysBetween(lead.modified.slice(0, 19), siteNow);
		const answers = await askJev({
			config,
			fetchFn,
			state: { lead: { ...lead, days_since_update: daysSinceUpdate }, recent_notes: notes },
			questions: { next_action: { type: 'choice', instructions: 'What should the salesperson do next with this quiet sales lead?', criteria: NEXT_ACTIONS } },
		});
		const { choice, confidence } = answers.next_action;
		if (confidence < threshold || choice === 'wait') {
			results.push({ lead: lead.name, action: 'none', choice, confidence });
			continue;
		}
		const task = TASKS[choice];
		await crm('POST', '/api/resource/CRM Task', {
			title: `${task.title}: ${lead.lead_name || lead.name}`,
			description: `AI (độ tin cậy ${confidence.toFixed(2)}): Lead không có cập nhật ${daysSinceUpdate} ngày. ${NEXT_ACTIONS[choice]}.`,
			priority: task.priority,
			status: 'Todo',
			assigned_to: lead.lead_owner || undefined,
			reference_doctype: 'CRM Lead',
			reference_docname: lead.name,
			due_date: siteDatetime(new Date(now.getTime() + 86400000), timeZone),
		});
		results.push({ lead: lead.name, action: 'task_created', choice, confidence });
	}
	return { checked: leads.length, results };
}

// Activepieces Code step entry point (Schedule trigger; all configuration comes from step inputs).
export const code = async (inputs) => planFollowups({ config: inputs, fetchFn: fetch });
