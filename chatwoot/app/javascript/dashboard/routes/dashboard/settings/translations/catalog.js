const flatten = (node, prefix = '', result = {}) => {
  Object.entries(node).forEach(([name, value]) => {
    const key = prefix ? `${prefix}.${name}` : name;
    if (typeof value === 'string') {
      result[key] = value;
    } else if (value && typeof value === 'object') {
      flatten(value, key, result);
    }
  });
  return result;
};

export const buildTranslationRows = ({ english, vietnamese, overrides }) => {
  const sources = flatten(english);
  const shipped = flatten(vietnamese);

  return Object.entries(sources)
    .map(([key, source]) => {
      const base = shipped[key] || '';
      const overridden = Object.prototype.hasOwnProperty.call(overrides, key);
      let status = 'translated';
      if (overridden) status = 'overridden';
      else if (!base) status = 'missing';
      else if (base === source) status = 'unchanged';

      return {
        key,
        source,
        base,
        effective: overridden ? overrides[key] : base || source,
        status,
      };
    })
    .sort((a, b) => a.key.localeCompare(b.key));
};

export const filterTranslationRows = (rows, { search, status }) => {
  const query = search.trim().toLocaleLowerCase();
  return rows.filter(row => {
    const matchesStatus = status === 'all' || row.status === status;
    const matchesSearch =
      !query ||
      row.key.toLocaleLowerCase().includes(query) ||
      row.source.toLocaleLowerCase().includes(query);
    return matchesStatus && matchesSearch;
  });
};
