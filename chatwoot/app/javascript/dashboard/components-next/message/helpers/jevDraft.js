// DX-OSD staff assist: the reply text inside the bot's draft notes, for the one-click send on the note.
// Formats written by mmm_custom: engine/draft.py ("💡 Jev gợi ý (...):\n\n<reply>[\n\nNút gợi ý: ...]")
// and engine/llm_draft.py ("✍️ Nháp AI ...\n\n<reply>").
const DRAFT_PREFIXES = ['💡', '✍️'];
const BUTTONS_LINE = /\n\nNút gợi ý: [^\n]*$/;

export const jevDraftReply = content => {
  const text = (content || '').trim();
  if (!DRAFT_PREFIXES.some(prefix => text.startsWith(prefix))) return null;
  const start = text.indexOf('\n\n');
  if (start === -1) return null;
  return (
    text
      .slice(start + 2)
      .replace(BUTTONS_LINE, '')
      .trim() || null
  );
};
