function normalizePhone(raw) {
	const digits = raw.replace(/[\s-]/g, '');
	if (digits.startsWith('+84')) return digits;
	if (digits.startsWith('0')) return '+84' + digits.slice(1);
	return digits;
}

function buildLeadSearchFilters({ email, phone }) {
	const conditions = [];
	if (email) conditions.push(['CRM Lead', 'email', '=', email]);
	if (phone) conditions.push(['CRM Lead', 'mobile_no', '=', normalizePhone(phone)]);
	// Caller must send this as or_filters (not filters) -- Frappe ANDs a plain filters list,
	// and an unfiltered blank-vs-blank match would attach a contact to an unrelated Lead.
	return conditions.length ? conditions : null;
}

function buildNewLeadPayload({ source, name, email, phone, chatwootContactId }) {
	return {
		source,
		first_name: name || 'Unknown', // CRM Lead.first_name is mandatory; Messenger contacts can have no name
		lead_name: name,
		email,
		mobile_no: normalizePhone(phone),
		chatwoot_contact_id: chatwootContactId,
	};
}

module.exports = { normalizePhone, buildLeadSearchFilters, buildNewLeadPayload };
