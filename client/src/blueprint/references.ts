/** Reference screenshots (repo-root screenshots/<domain>/), bundled by Vite and keyed by "<domain>/<file>". */
const files = import.meta.glob<string>('../../../screenshots/**/*.png', {
  eager: true,
  query: '?url',
  import: 'default',
});

const byPath: Record<string, string> = Object.fromEntries(
  Object.entries(files).map(([path, url]) => [path.replace('../../../screenshots/', ''), url]),
);

export const screenshotUrl = (path?: string | null) => (path ? byPath[path] ?? null : null);
