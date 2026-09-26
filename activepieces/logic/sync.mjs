// Chatwoot -> Frappe CRM sync. This whole file is the source of the "Sync to CRM" Code step in
// activepieces/flows/messenger-to-crm.json (Activepieces Code steps can't import local files);
// sync.test.mjs fails if the two copies drift.
import crypto from 'crypto'; // bare specifier: the Activepieces sandbox rejects 'node:' imports

export function normalizePhone(raw) {
	const digits = raw.replace(/[\s-]/g, '');
	if (digits.startsWith('+84')) return digits;
	if (digits.startsWith('0')) return '+84' + digits.slice(1);
	return digits;
}

export function buildLeadSearchFilters({ email, phone }) {
	const conditions = [];
	if (email) conditions.push(['CRM Lead', 'email', '=', email]);
	if (phone) conditions.push(['CRM Lead', 'mobile_no', '=', normalizePhone(phone)]);
	// Caller must send this as or_filters (not filters) -- Frappe ANDs a plain filters list,
	// and an unfiltered blank-vs-blank match would attach a contact to an unrelated Lead.
	return conditions.length ? conditions : null;
}

export function buildNewLeadPayload({ source, name, email, phone, chatwootContactId }) {
	return {
		source,
		first_name: name || 'Unknown', // CRM Lead.first_name is mandatory; Messenger contacts can have no name
		lead_name: name,
		email,
		mobile_no: normalizePhone(phone),
		chatwoot_contact_id: chatwootContactId,
	};
}

// Chatwoot signs "<timestamp>.<raw body>" with HMAC-SHA256 and sends "sha256=<hex>".
export function verifyChatwootSignature({ secret, timestamp, signature, rawBody, nowSeconds }) {
	const expected = Buffer.from('sha256=' + crypto.createHmac('sha256', secret).update(timestamp + '.' + rawBody).digest('hex'));
	const received = Buffer.from(signature || '');
	if (expected.length !== received.length || !crypto.timingSafeEqual(expected, received)) {
		throw new Error('Invalid Chatwoot webhook signature');
	}
	const tsNum = parseInt(timestamp, 10);
	if (!tsNum || Math.abs(nowSeconds - tsNum) > 300) {
		throw new Error('Chatwoot webhook timestamp missing or too old (possible replay)');
	}
}

async function request(fetchFn, method, url, headers, body) {
	const res = await fetchFn(url, {
		method,
		headers: { 'Content-Type': 'application/json', ...headers },
		body: body === undefined ? undefined : JSON.stringify(body),
	});
	if (!res.ok) throw new Error(`${method} ${url} failed: ${res.status} ${await res.text()}`);
	return res.json();
}

export async function syncConversation({ event, config, fetchFn }) {
	// Chatwoot's conversation_created payload is NOT wrapped in a "conversation" key --
	// conversation.webhook_data.merge(event: ...) puts id/channel/meta at the top level.
	if (event.event !== 'conversation_created') {
		throw new Error(`Unsupported Chatwoot event: ${event.event}`);
	}
	// crmHost: Frappe picks the site from the Host header; set it when crmBaseUrl is not the site's own domain.
	const crmHeaders = { Authorization: `token ${config.crmApiToken}`, ...(config.crmHost && { Host: config.crmHost }) };
	const crm = (method, path, body) => request(fetchFn, method, config.crmBaseUrl + path, crmHeaders, body);
	const contact = event.meta.sender;
	const conversationId = event.id;

	const mappedLeadId = contact.custom_attributes?.crm_lead_id;
	if (mappedLeadId) {
		const note = 'New message from Chatwoot conversation #' + conversationId;
		await crm('POST', '/api/resource/FCRM Note', {
			reference_doctype: 'CRM Lead',
			reference_docname: mappedLeadId,
			title: note,
			content: note,
		});
		return { action: 'note_logged', leadId: mappedLeadId };
	}

	const email = contact.email || '';
	const phone = contact.phone_number || '';
	const searchFilters = buildLeadSearchFilters({ email, phone });
	let leadId;
	let action;
	if (searchFilters) {
		const found = await crm('GET', '/api/resource/CRM Lead?or_filters=' + encodeURIComponent(JSON.stringify(searchFilters)));
		if (found.data.length > 0) {
			leadId = found.data[0].name;
			await crm('PUT', '/api/resource/CRM Lead/' + encodeURIComponent(leadId), { chatwoot_contact_id: String(contact.id) });
			action = 'lead_linked';
		}
	}
	if (!leadId) {
		const payload = buildNewLeadPayload({
			source: (event.channel || '').includes('Instagram') ? 'Instagram' : 'Messenger',
			name: contact.name,
			email,
			phone,
			chatwootContactId: String(contact.id),
		});
		leadId = (await crm('POST', '/api/resource/CRM Lead', payload)).data.name;
		action = 'lead_created';
	}

	await request(
		fetchFn,
		'PUT',
		`${config.chatwootBaseUrl}/api/v1/accounts/${config.chatwootAccountId}/contacts/${contact.id}`,
		{ api_access_token: config.chatwootApiToken },
		{ custom_attributes: { crm_lead_id: leadId } },
	);
	return { action, leadId };
}

// Activepieces Code step entry point. inputs.rawBody / inputs.headers come from the Catch Webhook trigger.
export const code = async (inputs) => {
	verifyChatwootSignature({
		secret: inputs.chatwootSigningSecret,
		timestamp: inputs.headers['x-chatwoot-timestamp'],
		signature: inputs.headers['x-chatwoot-signature'],
		rawBody: inputs.rawBody,
		nowSeconds: Date.now() / 1000,
	});
	return syncConversation({ event: JSON.parse(inputs.rawBody), config: inputs, fetchFn: fetch });
};
