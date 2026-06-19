export function setupClickWords() {
  const words = ['爱心', '前端', 'C++', 'Python', '运维', '安全', 'PHP', 'Java', 'HTML', 'CSS', 'JavaScript', 'MySQL', 'Linux'];
  let index = 0;
  const handler = (event: MouseEvent) => {
    const span = document.createElement('span');
    span.className = 'click-word';
    span.textContent = words[index];
    index = (index + 1) % words.length;
    span.style.left = `${event.pageX}px`;
    span.style.top = `${event.pageY}px`;
    span.style.color = `hsl(${Math.round(Math.random() * 280 + 180)}deg 90% 58%)`;
    document.body.appendChild(span);
    window.setTimeout(() => span.remove(), 1500);
  };
  document.body.addEventListener('click', handler);
  return () => document.body.removeEventListener('click', handler);
}

export function setupPointerTrail() {
  let last = 0;
  const handler = (event: PointerEvent) => {
    if (!(event.buttons & 1) || performance.now() - last < 28) return;
    last = performance.now();
    const dot = document.createElement('span');
    dot.className = 'pointer-trail';
    dot.style.left = `${event.pageX}px`;
    dot.style.top = `${event.pageY}px`;
    dot.style.setProperty('--hue', `${Math.round(Math.random() * 280 + 180)}deg`);
    document.body.appendChild(dot);
    window.setTimeout(() => dot.remove(), 900);
  };
  window.addEventListener('pointermove', handler);
  return () => window.removeEventListener('pointermove', handler);
}
