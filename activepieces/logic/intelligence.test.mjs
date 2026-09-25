import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import * as sync from './sync.mjs';
import {
	normalizePhone,
	buildLeadSearchFilters,
	verifyChatwootSignature,
	findCandidates,
	buildQuestions,
	decideActions,
	analyzeMessage,
	INTENTS,
	HOTNESS,
} from './intelligence.mjs';

const source = (file) => readFileSync(new URL(file, import.meta.url), 'utf8');
const requestSource = (file) => source(file).match(/async function request\([\s\S]*?\n}\n/)[0];

test('helpers shared with sync.mjs are verbatim copies (the copies must not drift)', () => {
	assert.equal(normalizePhone.toString(), sync.normalizePhone.toString());
	assert.equal(buildLeadSearchFilters.toString(), sync.buildLeadSearchFilters.toString());
	assert.equal(verifyChatwootSignature.toString(), sync.verifyChatwootSignature.toString());
	assert.equal(requestSource('./intelligence.mjs'), requestSource('./sync.mjs'));
});

test('intent and hotness keys match the ai_intent / ai_hotness Select options in mmm_custom', () => {
	const setup = readFileSync(new URL('../../frappe-custom/mmm_custom/mmm_custom/setup.py', import.meta.url), 'utf8');
	const options = (field) => setup.match(new RegExp(`"fieldname": "${field}"[\\s\\S]*?"options": "([^"]*)"`))[1].split('\\n').filter(Boolean);
	assert.deepEqual(options('ai_intent'), Object.keys(INTENTS));
	assert.deepEqual(options('ai_hotness'), HOTNESS);
});

test('findCandidates extracts Vietnamese phone numbers in common spellings and emails, normalized and deduped', () => {
	const c = findCandidates(['sđt em 0901 234 567 nhé', 'hoặc 090.123.4567', 'mail: An.Nguyen@Gmail.com', 'số +84 912 345 678']);
	assert.deepEqual(c.phones, ['+84901234567', '+84912345678']);
	assert.deepEqual(c.emails, ['an.nguyen@gmail.com']);
});

test('findCandidates ignores order numbers and prices that are not phone numbers', () => {
	assert.deepEqual(findCandidates(['đơn #12345, giá 350.000đ']).phones, []);
});

test('buildQuestions asks phone/email/reply only when there is something to choose', () => {
	const bare = buildQuestions({ candidates: { phones: [], emails: [] }, templates: {} });
	assert.deepEqual(Object.keys(bare), ['intent', 'hotness']);
	const full = buildQuestions({ candidates: { phones: ['+84901234567'], emails: ['a@b.com'] }, templates: { price: 'Dạ giá ...' } });
	assert.deepEqual(Object.keys(full), ['intent', 'hotness', 'phone', 'email', 'reply']);
	assert.deepEqual(Object.keys(full.phone.criteria), ['+84901234567', 'none']);
	assert.equal(full.reply.criteria.price, 'Dạ giá ...');
	assert.equal(full.hotness.criteria.length, HOTNESS.length);
});

const templates = { price: 'Dạ bên em gửi bảng giá ạ', ask_phone: 'Anh/chị cho em xin SĐT ạ' };
const confident = {
	intent: { choice: 'price_inquiry', confidence: 0.9 },
	hotness: { score: 2, confidence: 0.8 },
	phone: { choice: '+84901234567', confidence: 0.95 },
	reply: { choice: 'price', confidence: 0.85 },
};

test('decideActions applies confident answers: fields, labels, missing phone, reply note', () => {
	const plan = decideActions({ answers: confident, templates, threshold: 0.7, lead: { mobile_no: '', email: '' } });
	assert.deepEqual(plan.leadUpdate, { ai_intent: 'price_inquiry', ai_hotness: 'hot', mobile_no: '+84901234567' });
	assert.deepEqual(plan.labels, ['ai-price_inquiry', 'hot']);
	assert.match(plan.replyNote, /độ tin cậy 0\.85/);
	assert.match(plan.replyNote, /bảng giá/);
	assert.deepEqual(plan.skipped, []);
});

test('decideActions skips everything below the confidence threshold (no automatic action when unsure)', () => {
	const unsure = Object.fromEntries(Object.entries(confident).map(([k, v]) => [k, { ...v, confidence: 0.4 }]));
	const plan = decideActions({ answers: unsure, templates, threshold: 0.7, lead: { mobile_no: '', email: '' } });
	assert.deepEqual(plan.leadUpdate, {});
	assert.deepEqual(plan.labels, []);
	assert.equal(plan.replyNote, null);
	assert.deepEqual(plan.skipped, ['intent', 'hotness', 'phone', 'reply']);
});

test('decideActions never overwrites a phone the Lead already has, and never suggests replies to spam', () => {
	const answers = { ...confident, intent: { choice: 'spam', confidence: 0.9 } };
	const plan = decideActions({ answers, templates, threshold: 0.7, lead: { mobile_no: '+84999999999', email: '' } });
	assert.equal(plan.leadUpdate.mobile_no, undefined);
	assert.equal(plan.replyNote, null);
});

test('decideActions never copies contact details out of a message it is sure is spam', () => {
	// Real Jev run: an ad for "tăng like" was spam (0.87) and its Zalo number scored 0.69 as "the customer's own".
	const answers = { ...confident, intent: { choice: 'spam', confidence: 0.87 }, phone: { choice: '+84988111222', confidence: 0.95 } };
	const plan = decideActions({ answers, templates, threshold: 0.7, lead: { mobile_no: '', email: '' } });
	assert.equal(plan.leadUpdate.ai_intent, 'spam');
	assert.equal(plan.leadUpdate.mobile_no, undefined);
});

// --- analyzeMessage against fake Chatwoot / CRM / Jev ---

const config = {
	chatwootBaseUrl: 'http://chat',
	chatwootAccountId: '1',
	chatwootApiToken: 'cw',
	crmBaseUrl: 'http://crm',
	crmApiToken: 'k:s',
	jevApiKey: 'jev-key',
	confidenceThreshold: '0.7',
	replyTemplates: JSON.stringify(templates),
};

function fakeFetch(routes) {
	const calls = [];
	const fetchFn = async (url, init) => {
		const body = init.body && JSON.parse(init.body);
		calls.push({ method: init.method, url, headers: init.headers, body });
		const route = routes.find(([m, re]) => m === init.method && re.test(url));
		if (!route) throw new Error(`unexpected ${init.method} ${url}`);
		const data = typeof route[2] === 'function' ? route[2](body) : route[2];
		return { ok: true, status: 200, json: async () => data, text: async () => '' };
	};
	return { fetchFn, calls };
}

const incoming = { event: 'message_created', message_type: 'incoming', private: false, conversation: { id: 5 } };
const conversation = (leadId, labels = []) => ({
	meta: { labels, contact: { id: 42, custom_attributes: leadId ? { crm_lead_id: leadId } : {} } },
	payload: [
		{ message_type: 0, private: false, content: 'Cho em hỏi giá sản phẩm này' },
		{ message_type: 1, private: false, content: 'Dạ anh/chị cần mẫu nào ạ' },
		{ message_type: 1, private: true, content: 'internal note' },
		{ message_type: 2, private: false, content: 'Conversation assigned' },
		{ message_type: 0, private: false, content: 'mẫu A, sđt em 0901234567' },
	],
});

test('analyzeMessage ignores outgoing and private messages', async () => {
	const { fetchFn, calls } = fakeFetch([]);
	assert.deepEqual(await analyzeMessage({ event: { ...incoming, message_type: 'outgoing' }, config, fetchFn }), { action: 'ignored' });
	assert.deepEqual(await analyzeMessage({ event: { ...incoming, private: true }, config, fetchFn }), { action: 'ignored' });
	assert.equal(calls.length, 0);
});

test('analyzeMessage throws (so the step retries) while the contact is not linked to a Lead yet', async () => {
	const { fetchFn } = fakeFetch([['GET', /\/conversations\/5\/messages$/, conversation(null)]]);
	await assert.rejects(analyzeMessage({ event: incoming, config, fetchFn }), /not linked to a CRM Lead yet/);
});

test('analyzeMessage sends the chat to Jev, then updates the Lead, merges labels and posts a private reply note', async () => {
	const { fetchFn, calls } = fakeFetch([
		['GET', /\/conversations\/5\/messages$/, conversation('LEAD-1', ['vip'])],
		['GET', /CRM Lead\/LEAD-1$/, { data: { name: 'LEAD-1', mobile_no: '', email: '' } }],
		['POST', /\/v1\/systemone$/, { answers: confident }],
		['PUT', /CRM Lead\/LEAD-1$/, { data: {} }],
		['GET', /CRM Lead\?or_filters=/, { data: [{ name: 'LEAD-1' }] }],
		['POST', /\/conversations\/5\/labels$/, {}],
		['POST', /\/conversations\/5\/messages$/, {}],
	]);
	const result = await analyzeMessage({ event: incoming, config, fetchFn });
	assert.deepEqual(result.applied, ['lead_updated', 'labels_added', 'reply_suggested']);

	const jev = calls.find((c) => c.url.endsWith('/v1/systemone'));
	assert.equal(jev.url, 'https://api.typesafe.ai/v1/systemone');
	assert.equal(jev.headers.Authorization, 'Bearer jev-key');
	assert.equal(jev.body.model, 'jev-latest');
	assert.deepEqual(jev.body.state.chat.map((m) => m.from), ['customer', 'shop', 'customer'], 'private notes and activity are not sent');
	assert.deepEqual(jev.body.questions.phone.criteria, { '+84901234567': null, none: 'None of these is the customer’s own contact' });

	assert.deepEqual(calls.find((c) => c.method === 'PUT').body, { ai_intent: 'price_inquiry', ai_hotness: 'hot', mobile_no: '+84901234567' });
	assert.deepEqual(calls.find((c) => c.url.endsWith('/labels')).body, { labels: ['vip', 'ai-price_inquiry', 'hot'] });
	const note = calls.find((c) => c.method === 'POST' && c.url.endsWith('/messages')).body;
	assert.equal(note.private, true);
	assert.match(note.content, /bảng giá/);
});

test('analyzeMessage flags (never merges) another Lead that already has the newly found phone', async () => {
	const { fetchFn, calls } = fakeFetch([
		['GET', /\/conversations\/5\/messages$/, conversation('LEAD-1', ['ai-price_inquiry', 'hot'])],
		['GET', /CRM Lead\/LEAD-1$/, { data: { name: 'LEAD-1', mobile_no: '', email: '' } }],
		['POST', /\/v1\/systemone$/, { answers: { ...confident, reply: { choice: 'none', confidence: 0.9 } } }],
		['PUT', /CRM Lead\/LEAD-1$/, { data: {} }],
		['GET', /CRM Lead\?or_filters=/, { data: [{ name: 'LEAD-1' }, { name: 'LEAD-ADS-7' }] }],
		['POST', /FCRM Note$/, {}],
	]);
	const result = await analyzeMessage({ event: incoming, config, fetchFn });
	assert.deepEqual(result.applied, ['lead_updated', 'duplicate_flagged'], 'labels unchanged and no reply → no extra calls');
	const note = calls.find((c) => c.url.endsWith('FCRM Note')).body;
	assert.equal(note.reference_docname, 'LEAD-1');
	assert.match(note.content, /LEAD-ADS-7/);
	assert.ok(!calls.some((c) => c.method === 'DELETE'));
});

test('the "Analyze with Jev" Code step in the flow export embeds intelligence.mjs verbatim', () => {
	const flow = JSON.parse(source('../flows/lead-intelligence.json'));
	const step = flow.flows[0].trigger.nextAction;
	assert.equal(step.displayName, 'Analyze with Jev');
	assert.equal(step.settings.sourceCode.code, source('./intelligence.mjs'), 'intelligence.mjs differs from the flow export -- re-import and re-export it (see activepieces/README.md)');
});
