// Timeline loader: maps data/lines.json and data/words.json into cut(i) and Wd(word, line).
export const T = { dur: 10, lines: [], words: [] };

export async function loadTiming() {
  const [lj, wj] = await Promise.all([
    fetch('./data/lines.json').then((r) => r.json()),
    fetch('./data/words.json').then((r) => r.json()),
  ]);
  T.dur = lj.duration;
  T.lines = lj.lines;
  T.words = wj;
  return T;
}

export const cut = (i) => (T.lines[i] ? T.lines[i].start : 0);
export const lineEnd = (i) => (T.lines[i] ? T.lines[i].end : T.dur);
export const lineWords = (i) => T.words.filter((w) => w.line === i);

export function Wd(word, lineIdx) {
  const norm = (s) => String(s).toLowerCase().replace(/[^a-z0-9']+/g, '');
  const needle = norm(word);
  const hit = T.words.find(
    (w) => (lineIdx === undefined || w.line === lineIdx) && norm(w.w).includes(needle)
  );
  return hit ? hit.s : cut(lineIdx || 0);
}
