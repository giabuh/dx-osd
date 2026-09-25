import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import * as intelligence from './intelligence.mjs';
import { askJev, planFollowups } from './followup.mjs';

const source = (file) => readFileSync(new URL(file, import.meta.url), 'utf8');
const requestSource = (file) => source(file).match(/async function request\([\s\S]*?\n}\n/)[0];

test('helpers shared with sync.mjs / intelligence.mjs are verbatim copies (the copies must not drift)', () => {
	assert.equal(requestSource('./followup.mjs'), requestSource('./sync.mjs'));
	assert.equal(askJev.toString(), intelligence.askJev.toString());
});

const config = { crmBaseUrl: 'http://crm', crmApiToken: 'k:s', jevApiKey: 'jev', staleDays: '3', confidenceThreshold: '0.7', maxLeads: '20' };
const now = new Date('2026-09-25T00:00:00Z');
const lead = (name, owner = 'sale@shop.vn') => ({ name, lead_name: 'Khách ' + name, status: 'New', lead_owner: owner, modified: '2026-09-20 00:00:00' });

function fakeCrm({ leads, openTasks = {}, jev = {}, timeZone = 'UTC' }) {
	const calls = [];
	const fetchFn = async (url, init) => {
		const body = init.body && JSON.parse(init.body);
		calls.push({ method: init.method, url: decodeURIComponent(url), body });
		const u = new URL(url);
		const filters = u.searchParams.get('filters');
		let data;
		if (u.pathname.endsWith('/api/method/frappe.client.get_time_zone')) return { ok: true, json: async () => ({ message: { time_zone: timeZone } }) };
		if (u.pathname.endsWith('/CRM Lead') || u.pathname.endsWith('/CRM%20Lead')) data = leads;
		else if (/CRM(%20| )Task$/.test(u.pathname) && init.method === 'GET') data = openTasks[JSON.parse(filters)[1][2]] || [];
		else if (/FCRM(%20| )Note$/.test(u.pathname)) data = [];
		else if (u.pathname.endsWith('/v1/systemone')) return { ok: true, json: async () => ({ answers: { next_action: jev[body.state.lead.name] } }) };
		else data = {};
		return { ok: true, json: async () => ({ data }), text: async () => '' };
	};
	return { fetchFn, calls };
}

test('planFollowups queries only open Leads unchanged for staleDays, oldest first', async () => {
	const { fetchFn, calls } = fakeCrm({ leads: [] });
	const result = await planFollowups({ config, fetchFn, now });
	assert.deepEqual(result, { checked: 0, results: [] });
	const q = new URL(calls[1].url.replace(/ /g, '%20')).searchParams;
	assert.deepEqual(JSON.parse(q.get('filters')), [['status', 'in', ['New', 'Contacted', 'Nurture']], ['modified', '<', '2026-09-22 00:00:00']]);
	assert.equal(JSON.parse(q.get('order_by')), 'modified asc');
});

test('confident "call" creates a high-priority Task for the Lead owner, due tomorrow, with days computed in code', async () => {
	const { fetchFn, calls } = fakeCrm({ leads: [lead('L1')], jev: { L1: { choice: 'call', confidence: 0.9 } } });
	const result = await planFollowups({ config, fetchFn, now });
	assert.deepEqual(result.results, [{ lead: 'L1', action: 'task_created', choice: 'call', confidence: 0.9 }]);
	const jev = calls.find((c) => c.url.endsWith('/v1/systemone')).body;
	assert.equal(jev.state.lead.days_since_update, 5);
	const task = calls.find((c) => c.method === 'POST' && c.url.endsWith('CRM Task')).body;
	assert.equal(task.priority, 'High');
	assert.equal(task.assigned_to, 'sale@shop.vn');
	assert.equal(task.reference_docname, 'L1');
	assert.equal(task.due_date, '2026-09-26 00:00:00');
	assert.match(task.title, /Khách L1/);
});

test('dates are compared and written in the CRM site timezone, not UTC', async () => {
	// Frappe stores `modified` in the site timezone (Asia/Kolkata when unset). At 00:00 UTC it is 05:30 there.
	const { fetchFn, calls } = fakeCrm({ leads: [{ ...lead('L1'), modified: '2026-09-20 05:30:00' }], timeZone: 'Asia/Kolkata', jev: { L1: { choice: 'call', confidence: 0.9 } } });
	await planFollowups({ config, fetchFn, now });
	const q = new URL(calls[1].url.replace(/ /g, '%20')).searchParams;
	assert.deepEqual(JSON.parse(q.get('filters'))[1], ['modified', '<', '2026-09-22 05:30:00']);
	assert.equal(calls.find((c) => c.url.endsWith('/v1/systemone')).body.state.lead.days_since_update, 5);
	assert.equal(calls.find((c) => c.method === 'POST' && c.url.endsWith('CRM Task')).body.due_date, '2026-09-26 05:30:00');
});

test('no Task when Jev is unsure or says wait, and Leads with an open Task are skipped (no daily duplicates)', async () => {
	const { fetchFn, calls } = fakeCrm({
		leads: [lead('L1'), lead('L2'), lead('L3')],
		openTasks: { L3: [{ name: 'T1' }] },
		jev: { L1: { choice: 'call', confidence: 0.5 }, L2: { choice: 'wait', confidence: 0.95 } },
	});
	const result = await planFollowups({ config, fetchFn, now });
	assert.deepEqual(result.results.map((r) => r.action), ['none', 'none', 'skipped']);
	assert.ok(!calls.some((c) => c.method === 'POST' && c.url.endsWith('CRM Task')));
	assert.ok(!calls.some((c) => c.method === 'PUT'), 'never changes the Lead itself');
});

test('the "Plan follow-ups with Jev" Code step in the flow export embeds followup.mjs verbatim', () => {
	const flow = JSON.parse(source('../flows/cold-lead-followup.json'));
	const step = flow.flows[0].trigger.nextAction;
	assert.equal(step.displayName, 'Plan follow-ups with Jev');
	assert.equal(step.settings.sourceCode.code, source('./followup.mjs'), 'followup.mjs differs from the flow export -- re-import and re-export it (see activepieces/README.md)');
});
