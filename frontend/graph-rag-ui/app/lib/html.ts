const DEFAULT_HTML = `<!doctype html><html lang="en"><head><meta charset="utf-8" /><meta name="viewport" content="width=device-width, initial-scale=1" /></head><body>{{body}}</body></html>`;

export const ensureHtmlDocument = (html: string) => {
  const trimmed = html.trim();
  if (!trimmed) return "";
  if (trimmed.includes("<html") || trimmed.includes("<body")) {
    return trimmed;
  }
  return DEFAULT_HTML.replace("{{body}}", trimmed);
};
