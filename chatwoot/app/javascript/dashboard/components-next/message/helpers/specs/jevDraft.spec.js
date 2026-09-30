import { jevDraftReply } from '../jevDraft';

describe('jevDraftReply', () => {
  it('returns the reply of a Jev suggestion without its header', () => {
    expect(
      jevDraftReply(
        '💡 Jev gợi ý (khóa Excel; dựa trên: chào hỏi):\n\nDạ em chào anh/chị ạ!\n\nAnh/chị cần tư vấn gì ạ?'
      )
    ).toBe('Dạ em chào anh/chị ạ!\n\nAnh/chị cần tư vấn gì ạ?');
  });

  it('drops the suggested buttons line', () => {
    expect(
      jevDraftReply(
        '💡 Jev gợi ý:\n\nDạ học phí là 1.500.000đ ạ.\n\nNút gợi ý: Lịch học · Đăng ký'
      )
    ).toBe('Dạ học phí là 1.500.000đ ạ.');
  });

  it('returns the reply of a Gemini draft', () => {
    expect(
      jevDraftReply('✍️ Nháp AI (Gemini) · kiểm tra trước khi gửi\n\nDạ có ạ.')
    ).toBe('Dạ có ạ.');
  });

  it('ignores other notes', () => {
    expect(jevDraftReply('⚠ Jev chưa có tri thức để trả lời câu này.')).toBe(
      null
    );
    expect(jevDraftReply('Ghi chú của nhân viên')).toBe(null);
    expect(jevDraftReply('💡 Jev gợi ý')).toBe(null);
    expect(jevDraftReply(null)).toBe(null);
  });
});
