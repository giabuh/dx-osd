// Lead intelligence agent (DX-OS [I] space). Source of the "Analyze with Jev" Code step in
// activepieces/flows/lead-intelligence.json (Activepieces Code steps can't import local files).
// On every incoming Chatwoot message it asks TypeSafe Jev for structured decisions about the
// conversation and applies only the ones Jev is confident about.
import crypto from 'crypto'; // bare specifier: the Activepieces sandbox rejects 'node:' imports

// --- Copied verbatim from sync.mjs; intelligence.test.mjs fails if the copies drift. ---

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

// --- Also copied verbatim into followup.mjs. ---

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

// --- Intelligence-specific. ---

// Keys must match the ai_intent / ai_hotness Select options in frappe-custom/mmm_custom/mmm_custom/setup.py.
export const INTENTS = {
	purchase: 'The customer wants to buy, order, or book something now',
	price_inquiry: 'The customer asks about price, promotions, or availability before deciding',
	support: 'The customer already bought and needs help or information about an existing order',
	complaint: 'The customer is unhappy or complains about a product or service',
	spam: 'Spam, advertising, or a message that is not from a real prospective customer',
	other: 'Anything else, such as a greeting with no clear request',
};
export const HOTNESS = ['cold', 'warm', 'hot'];
const HOTNESS_CRITERIA = [
	'Cold: no buying signal, just browsing or off-topic',
	'Warm: interested and asking questions, but not ready to buy yet',
	'Hot: clear intent to buy soon, asks how to order, or gives contact details to be called',
];

const PHONE_RE = /(?:\+84|0)(?:[\s.-]?\d){9}/g;
const EMAIL_RE = /[\w.+-]+@[\w-]+(?:\.[\w-]+)+/g;

// Regex finds candidates; Jev only decides which one (if any) is the customer's own.
export function findCandidates(texts) {
	const all = texts.join('\n');
	const phones = [...new Set((all.match(PHONE_RE) || []).map((p) => normalizePhone(p.replace(/\./g, ''))))];
	const emails = [...new Set((all.match(EMAIL_RE) || []).map((e) => e.toLowerCase()))];
	return { phones, emails };
}

export function buildQuestions({ candidates, templates }) {
	const questions = {
		intent: {
			type: 'choice',
			instructions: 'What does the customer want in this Vietnamese chat with a shop?',
			criteria: INTENTS,
		},
		hotness: {
			type: 'score',
			instructions: 'How close is the customer to buying, based on the whole chat?',
			criteria: HOTNESS_CRITERIA,
		},
	};
	const pick = (values, what) => ({
		type: 'choice',
		instructions: `Which of these ${what} did the customer give as their own contact? Answer "none" if it belongs to someone else or is not a contact.`,
		criteria: { ...Object.fromEntries(values.map((v) => [v, null])), none: 'None of these is the customer’s own contact' },
	});
	if (candidates.phones.length) questions.phone = pick(candidates.phones, 'phone numbers');
	if (candidates.emails.length) questions.email = pick(candidates.emails, 'email addresses');
	if (Object.keys(templates).length) {
		questions.reply = {
			type: 'choice',
			instructions: 'Which reply template best answers the customer’s latest message?',
			criteria: { ...templates, none: 'No template fits the latest message' },
		};
	}
	return questions;
}

// Pure decision step: turns Jev's answers into the changes to apply, gated on confidence.
export function decideActions({ answers, templates, threshold, lead }) {
	const sure = (a) => a && (a.confidence ?? 0) >= threshold;
	const plan = { leadUpdate: {}, labels: [], replyNote: null, skipped: [] };

	if (sure(answers.intent)) {
		plan.leadUpdate.ai_intent = answers.intent.choice;
		plan.labels.push('ai-' + answers.intent.choice);
	} else plan.skipped.push('intent');

	if (sure(answers.hotness)) {
		const hotness = HOTNESS[Math.round(answers.hotness.score)];
		plan.leadUpdate.ai_hotness = hotness;
		if (hotness === 'hot') plan.labels.push('hot');
	} else plan.skipped.push('hotness');

	for (const [key, field] of [['phone', 'mobile_no'], ['email', 'email']]) {
		const a = answers[key];
		// Spam ads carry their own phone numbers; never copy those onto the Lead.
		if (!a || a.choice === 'none' || lead[field] || plan.leadUpdate.ai_intent === 'spam') continue;
		if (sure(a)) plan.leadUpdate[field] = a.choice;
		else plan.skipped.push(key);
	}

	const reply = answers.reply;
	if (reply && reply.choice !== 'none' && plan.leadUpdate.ai_intent !== 'spam') {
		if (sure(reply)) plan.replyNote = `Gợi ý trả lời (AI, độ tin cậy ${reply.confidence.toFixed(2)}):\n\n${templates[reply.choice]}`;
		else plan.skipped.push('reply');
	}
	return plan;
}

export async function analyzeMessage({ event, config, fetchFn }) {
	if (event.event !== 'message_created') throw new Error(`Unsupported Chatwoot event: ${event.event}`);
	if (event.message_type !== 'incoming' || event.private) return { action: 'ignored' };

	const chatwoot = (method, path, body) =>
		request(fetchFn, method, `${config.chatwootBaseUrl}/api/v1/accounts/${config.chatwootAccountId}${path}`, { api_access_token: config.chatwootApiToken }, body);
	const crmHeaders = { Authorization: `token ${config.crmApiToken}`, ...(config.crmHost && { Host: config.crmHost }) };
	const crm = (method, path, body) => request(fetchFn, method, config.crmBaseUrl + path, crmHeaders, body);

	const conversationId = event.conversation.id;
	const convo = await chatwoot('GET', `/conversations/${conversationId}/messages`);
	const leadId = convo.meta.contact.custom_attributes?.crm_lead_id;
	// The "Messenger to CRM" flow links the Lead on conversation_created, which races the first
	// message; throwing lets this step's retry-on-failure run it again once the link exists.
	if (!leadId) throw new Error('Contact not linked to a CRM Lead yet');

	const chat = convo.payload
		.filter((m) => !m.private && (m.message_type === 0 || m.message_type === 1) && m.content)
		.slice(-20)
		.map((m) => ({ from: m.message_type === 0 ? 'customer' : 'shop', text: m.content }));
	const templates = typeof config.replyTemplates === 'string' ? JSON.parse(config.replyTemplates) : config.replyTemplates || {};
	const candidates = findCandidates(chat.filter((m) => m.from === 'customer').map((m) => m.text));
	const lead = (await crm('GET', '/api/resource/CRM Lead/' + encodeURIComponent(leadId))).data;

	const answers = await askJev({ config, fetchFn, state: { chat }, questions: buildQuestions({ candidates, templates }) });
	const plan = decideActions({ answers, templates, threshold: Number(config.confidenceThreshold ?? 0.7), lead });

	const applied = [];
	if (Object.keys(plan.leadUpdate).length) {
		await crm('PUT', '/api/resource/CRM Lead/' + encodeURIComponent(leadId), plan.leadUpdate);
		applied.push('lead_updated');
		// A newly found contact may belong to another Lead (e.g. from Lead Ads): flag it, never auto-merge.
		const filters = buildLeadSearchFilters({ email: plan.leadUpdate.email, phone: plan.leadUpdate.mobile_no });
		if (filters) {
			const others = (await crm('GET', '/api/resource/CRM Lead?or_filters=' + encodeURIComponent(JSON.stringify(filters)))).data
				.map((l) => l.name)
				.filter((name) => name !== leadId);
			if (others.length) {
				const note = `AI: số điện thoại/email khách vừa cung cấp trùng với ${others.join(', ')} — có thể là cùng một khách, cần kiểm tra và gộp.`;
				await crm('POST', '/api/resource/FCRM Note', { reference_doctype: 'CRM Lead', reference_docname: leadId, title: 'Possible duplicate', content: note });
				applied.push('duplicate_flagged');
			}
		}
	}
	const labels = [...new Set([...convo.meta.labels, ...plan.labels])];
	if (labels.length !== convo.meta.labels.length) {
		await chatwoot('POST', `/conversations/${conversationId}/labels`, { labels }); // replaces the list, hence the union
		applied.push('labels_added');
	}
	if (plan.replyNote) {
		await chatwoot('POST', `/conversations/${conversationId}/messages`, { content: plan.replyNote, message_type: 'outgoing', private: true });
		applied.push('reply_suggested');
	}
	return { action: 'analyzed', leadId, decisions: plan.leadUpdate, skipped: plan.skipped, applied };
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
	return analyzeMessage({ event: JSON.parse(inputs.rawBody), config: inputs, fetchFn: fetch });
};
