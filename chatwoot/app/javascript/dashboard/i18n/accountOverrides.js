const FORBIDDEN_SEGMENTS = new Set(['__proto__', 'prototype', 'constructor']);

const sourceContainsKey = (source, segments) => {
  let current = source;
  const validPath = segments.every(segment => {
    if (
      !segment ||
      FORBIDDEN_SEGMENTS.has(segment) ||
      !current ||
      typeof current !== 'object' ||
      !Object.prototype.hasOwnProperty.call(current, segment)
    ) {
      return false;
    }
    current = current[segment];
    return true;
  });
  return validPath && typeof current === 'string';
};

const setLeaf = (tree, segments, value) => {
  let current = tree;
  segments.slice(0, -1).forEach(segment => {
    if (!current[segment] || typeof current[segment] !== 'object') {
      current[segment] = {};
    }
    current = current[segment];
  });
  current[segments.at(-1)] = value;
};

export const createAccountOverrideLoader = ({
  composer,
  fetchOverrides,
  baseMessages,
}) => {
  let generation = 0;
  let activeAccountId = null;

  const freshMessages = () => structuredClone(baseMessages);
  const reset = () => composer.setLocaleMessage('vi', freshMessages());

  const clear = () => {
    generation += 1;
    activeAccountId = null;
    reset();
  };

  const load = async accountId => {
    generation += 1;
    const currentGeneration = generation;
    activeAccountId = accountId;
    reset();

    try {
      const { overrides } = await fetchOverrides(accountId, 'vi');
      if (generation !== currentGeneration || activeAccountId !== accountId) {
        return { ok: false, stale: true };
      }

      const messages = freshMessages();
      const english = composer.getLocaleMessage('en');
      Object.entries(overrides).forEach(([key, value]) => {
        const segments = key.split('.');
        if (typeof value === 'string' && sourceContainsKey(english, segments)) {
          setLeaf(messages, segments, value);
        }
      });
      composer.setLocaleMessage('vi', messages);
      return { ok: true };
    } catch (error) {
      if (generation !== currentGeneration || activeAccountId !== accountId) {
        return { ok: false, stale: true };
      }
      reset();
      return { ok: false, error };
    }
  };

  return { load, clear, refresh: load };
};
