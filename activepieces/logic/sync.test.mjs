import test from 'node:test';
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import { readFileSync } from 'node:fs';
import {
	normalizePhone,
	buildLeadSearchFilters,
	buildNewLeadPayload,
	verifyChatwootSignature,
	syncConversation,
} from './sync.mjs';

test('normalizePhone strips spaces, dashes, and adds +84 for local VN numbers', () => {
	assert.equal(normalizePhone('090 123 4567'), '+84901234567');
	assert.equal(normalizePhone('0901234567'), '+84901234567');
	assert.equal(normalizePhone('+84901234567'), '+84901234567');
});

test('buildLeadSearchFilters builds OR-ready conditions on email and mobile_no when both present', () => {
	const filters = buildLeadSearchFilters({ email: 'a@b.com', phone: '0901234567' });
	assert.deepEqual(filters, [
		['CRM Lead', 'email', '=', 'a@b.com'],
		['CRM Lead', 'mobile_no', '=', '+84901234567'],
	]);
});

test('buildLeadSearchFilters omits the email condition when email is empty', () => {
	const filters = buildLeadSearchFilters({ email: '', phone: '0901234567' });
	assert.deepEqual(filters, [['CRM Lead', 'mobile_no', '=', '+84901234567']]);
});

test('buildLeadSearchFilters omits the phone condition when phone is empty', () => {
	const filters = buildLeadSearchFilters({ email: 'a@b.com', phone: '' });
	assert.deepEqual(filters, [['CRM Lead', 'email', '=', 'a@b.com']]);
});

test('buildLeadSearchFilters returns null when both email and phone are empty (never search on blanks)', () => {
	const filters = buildLeadSearchFilters({ email: '', phone: '' });
	assert.equal(filters, null);
});

test('buildNewLeadPayload sets first_name, source and chatwoot_contact_id', () => {
	const payload = buildNewLeadPayload({
		source: 'Messenger',
		name: 'Nguyen Van A',
		email: 'a@b.com',
		phone: '0901234567',
		chatwootContactId: '42',
	});
	assert.equal(payload.source, 'Messenger');
	assert.equal(payload.first_name, 'Nguyen Van A');
	assert.equal(payload.lead_name, 'Nguyen Van A');
	assert.equal(payload.mobile_no, '+84901234567');
	assert.equal(payload.chatwoot_contact_id, '42');
});

test('buildNewLeadPayload falls back to a placeholder first_name when name is blank (first_name is mandatory on CRM Lead)', () => {
	const payload = buildNewLeadPayload({
		source: 'Messenger',
		name: '',
		email: 'a@b.com',
		phone: '',
		chatwootContactId: '42',
	});
	assert.equal(payload.first_name, 'Unknown');
});

// --- webhook signature ---

const sign = (secret, timestamp, rawBody) =>
	'sha256=' + crypto.createHmac('sha256', secret).update(timestamp + '.' + rawBody).digest('hex');

test('verifyChatwootSignature accepts a valid, fresh signature', () => {
	const rawBody = '{"event":"conversation_created"}';
	verifyChatwootSignature({ secret: 's', timestamp: '1000', signature: sign('s', '1000', rawBody), rawBody, nowSeconds: 1100 });
});

test('verifyChatwootSignature rejects a wrong signature', () => {
	assert.throws(
		() => verifyChatwootSignature({ secret: 's', timestamp: '1000', signature: sign('other', '1000', '{}'), rawBody: '{}', nowSeconds: 1000 }),
		/Invalid Chatwoot webhook signature/,
	);
});

test('verifyChatwootSignature rejects a missing signature', () => {
	assert.throws(
		() => verifyChatwootSignature({ secret: 's', timestamp: '1000', signature: undefined, rawBody: '{}', nowSeconds: 1000 }),
		/Invalid Chatwoot webhook signature/,
	);
});

test('verifyChatwootSignature rejects a timestamp older than 5 minutes (replay)', () => {
	assert.throws(
		() => verifyChatwootSignature({ secret: 's', timestamp: '1000', signature: sign('s', '1000', '{}'), rawBody: '{}', nowSeconds: 1301 }),
		/too old/,
	);
});

// --- syncConversation against a fake CRM/Chatwoot ---

const config = {
	crmBaseUrl: 'http://crm',
	crmApiToken: 'key:secret',
	crmHost: 'crm.localhost',
	chatwootBaseUrl: 'http://chat',
	chatwootAccountId: '1',
	chatwootApiToken: 'cw-token',
};

function fakeFetch(responses) {
	const calls = [];
	const fetchFn = async (url, init) => {
		calls.push({ method: init.method, url, headers: init.headers, body: init.body && JSON.parse(init.body) });
		const data = responses.shift();
		return { ok: true, status: 200, json: async () => data, text: async () => '' };
	};
	return { fetchFn, calls };
}

const event = (sender, channel = 'Channel::FacebookPage') => ({
	event: 'conversation_created',
	id: 7,
	channel,
	meta: { sender: { id: 42, name: 'Nguyen Van A', email: '', phone_number: '', custom_attributes: {}, ...sender } },
});

test('syncConversation rejects events other than conversation_created', async () => {
	const { fetchFn } = fakeFetch([]);
	await assert.rejects(syncConversation({ event: { event: 'message_created' }, config, fetchFn }), /Unsupported Chatwoot event/);
});

test('already-mapped contact only logs a note on its Lead', async () => {
	const { fetchFn, calls } = fakeFetch([{}]);
	const result = await syncConversation({ event: event({ custom_attributes: { crm_lead_id: 'CRM-LEAD-1' } }), config, fetchFn });
	assert.deepEqual(result, { action: 'note_logged', leadId: 'CRM-LEAD-1' });
	assert.equal(calls.length, 1);
	assert.equal(calls[0].url, 'http://crm/api/resource/FCRM Note');
	assert.equal(calls[0].body.reference_docname, 'CRM-LEAD-1');
	assert.equal(calls[0].headers.Authorization, 'token key:secret');
	assert.equal(calls[0].headers.Host, 'crm.localhost');
});

test('existing Lead matching email/phone is linked with PUT, then written back to Chatwoot', async () => {
	const { fetchFn, calls } = fakeFetch([{ data: [{ name: 'CRM-LEAD-9' }] }, { data: { name: 'CRM-LEAD-9' } }, {}]);
	const result = await syncConversation({ event: event({ email: 'a@b.com', phone_number: '0901234567' }), config, fetchFn });
	assert.deepEqual(result, { action: 'lead_linked', leadId: 'CRM-LEAD-9' });
	assert.deepEqual(calls.map((c) => c.method), ['GET', 'PUT', 'PUT']);
	const orFilters = JSON.parse(decodeURIComponent(calls[0].url.split('or_filters=')[1]));
	assert.deepEqual(orFilters, buildLeadSearchFilters({ email: 'a@b.com', phone: '0901234567' }));
	assert.equal(calls[1].url, 'http://crm/api/resource/CRM Lead/CRM-LEAD-9');
	assert.deepEqual(calls[1].body, { chatwoot_contact_id: '42' });
	assert.equal(calls[2].url, 'http://chat/api/v1/accounts/1/contacts/42');
	assert.equal(calls[2].headers.api_access_token, 'cw-token');
	assert.deepEqual(calls[2].body, { custom_attributes: { crm_lead_id: 'CRM-LEAD-9' } });
});

test('no matching Lead creates one, then writes crm_lead_id back', async () => {
	const { fetchFn, calls } = fakeFetch([{ data: [] }, { data: { name: 'CRM-LEAD-10' } }, {}]);
	const result = await syncConversation({ event: event({ email: 'new@b.com' }, 'Channel::Instagram'), config, fetchFn });
	assert.deepEqual(result, { action: 'lead_created', leadId: 'CRM-LEAD-10' });
	assert.deepEqual(calls.map((c) => c.method), ['GET', 'POST', 'PUT']);
	assert.equal(calls[1].body.source, 'Instagram');
	assert.equal(calls[1].body.chatwoot_contact_id, '42');
	assert.deepEqual(calls[2].body, { custom_attributes: { crm_lead_id: 'CRM-LEAD-10' } });
});

test('contact with no email or phone skips the search and creates a Lead (never matches on blanks)', async () => {
	const { fetchFn, calls } = fakeFetch([{ data: { name: 'CRM-LEAD-11' } }, {}]);
	const result = await syncConversation({ event: event({}), config, fetchFn });
	assert.equal(result.action, 'lead_created');
	assert.deepEqual(calls.map((c) => c.method), ['POST', 'PUT']);
});

test('a failed CRM call throws with the status (the run fails instead of silently skipping)', async () => {
	const fetchFn = async () => ({ ok: false, status: 403, json: async () => ({}), text: async () => 'forbidden' });
	await assert.rejects(syncConversation({ event: event({ email: 'a@b.com' }), config, fetchFn }), /failed: 403 forbidden/);
});

test('the "Sync to CRM" Code step in the flow export embeds sync.mjs verbatim (the two copies must not drift)', () => {
	const flow = JSON.parse(readFileSync(new URL('../flows/messenger-to-crm.json', import.meta.url)));
	const step = flow.flows[0].trigger.nextAction;
	assert.equal(step.displayName, 'Sync to CRM');
	assert.equal(
		step.settings.sourceCode.code,
		readFileSync(new URL('./sync.mjs', import.meta.url), 'utf8'),
		'sync.mjs differs from the flow export -- re-import the flow and re-export it (see activepieces/README.md)',
	);
});
