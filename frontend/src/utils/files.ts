export async function readJsonFile(event: Event) {
  const text = await readFileText(event);
  if (!text) return null;
  return JSON.parse(text);
}

export async function readFileText(event: Event) {
  const file = readSelectedFile(event);
  if (!file) return null;
  return file.text();
}

export async function readFileBuffer(event: Event) {
  const file = readSelectedFile(event);
  if (!file) return null;
  return file.arrayBuffer();
}

function readSelectedFile(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0] ?? null;
  input.value = '';
  return file;
}
