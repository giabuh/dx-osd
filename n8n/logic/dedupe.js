function normalizePhone(raw) {
	const digits = raw.replace(/[\s-]/g, '');
	if (digits.startsWith('+84')) return digits;
	if (digits.startsWith('0')) return '+84' + digits.slice(1);
	return digits;
}

function buildLeadSearchFilters({ email, phone }) {
	return [
		['CRM Lead', 'email', '=', email],
		['CRM Lead', 'mobile_no', '=', normalizePhone(phone)],
	];
}

function buildNewLeadPayload({ source, name, email, phone, chatwootContactId }) {
	return {
		source,
		lead_name: name,
		email,
		mobile_no: normalizePhone(phone),
		chatwoot_contact_id: chatwootContactId,
	};
}

module.exports = { normalizePhone, buildLeadSearchFilters, buildNewLeadPayload };
