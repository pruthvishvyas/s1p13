export function highlight(text, q) {
  if (!q) return text;
  const s = String(text);
  const i = s.toLowerCase().indexOf(q.toLowerCase());
  if (i < 0) return s;
  return (<>{s.slice(0, i)}<mark>{s.slice(i, i + q.length)}</mark>{s.slice(i + q.length)}</>);
}

export function ManualSection({ section, q }) {
  return (
    <section id={section.id}>
      <h2>{highlight(section.title, q)}</h2>
      {section.blocks.map((b, i) => (
        <div key={i}>
          <h3>{highlight(b.h, q)}</h3>
          {b.p.map((t, j) => <p key={j}>{highlight(t, q)}</p>)}
        </div>
      ))}
    </section>
  );
}
