/* global axios */

const accountURL = accountId =>
  `/api/v1/accounts/${accountId}/locale_overrides`;

export default {
  async list(accountId, locale) {
    const { data } = await axios.get(accountURL(accountId), {
      params: { locale },
    });
    return data;
  },
  async save(accountId, translation) {
    const { data } = await axios.put(accountURL(accountId), translation);
    return data;
  },
  async remove(accountId, translation) {
    await axios.delete(accountURL(accountId), { data: translation });
  },
};
