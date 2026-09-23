const test = require('node:test');
const assert = require('node:assert/strict');
const { normalizePhone, buildLeadSearchFilters, buildNewLeadPayload } = require('./dedupe');

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

test('n8n "Build Lead Payload" Code node embeds these functions verbatim (the two copies must not drift)', () => {
	const workflow = require('../workflows/messenger-to-crm.export.json');
	const node = workflow.nodes.find((n) => n.name === 'Build Lead Payload');
	for (const fn of [normalizePhone, buildLeadSearchFilters, buildNewLeadPayload]) {
		assert.ok(node.parameters.jsCode.includes(fn.toString()), `${fn.name} differs from n8n/logic/dedupe.js`);
	}
});
