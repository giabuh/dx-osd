const test = require('node:test');
const assert = require('node:assert/strict');
const { normalizePhone, buildLeadSearchFilters, buildNewLeadPayload } = require('./dedupe');

test('normalizePhone strips spaces, dashes, and adds +84 for local VN numbers', () => {
	assert.equal(normalizePhone('090 123 4567'), '+84901234567');
	assert.equal(normalizePhone('0901234567'), '+84901234567');
	assert.equal(normalizePhone('+84901234567'), '+84901234567');
});

test('buildLeadSearchFilters builds OR filter on email and mobile_no', () => {
	const filters = buildLeadSearchFilters({ email: 'a@b.com', phone: '0901234567' });
	assert.deepEqual(filters, [
		['CRM Lead', 'email', '=', 'a@b.com'],
		['CRM Lead', 'mobile_no', '=', '+84901234567'],
	]);
});

test('buildNewLeadPayload sets source and chatwoot_contact_id', () => {
	const payload = buildNewLeadPayload({
		source: 'Messenger',
		name: 'Nguyen Van A',
		email: 'a@b.com',
		phone: '0901234567',
		chatwootContactId: '42',
	});
	assert.equal(payload.source, 'Messenger');
	assert.equal(payload.lead_name, 'Nguyen Van A');
	assert.equal(payload.mobile_no, '+84901234567');
	assert.equal(payload.chatwoot_contact_id, '42');
});
