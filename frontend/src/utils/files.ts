export async function readJsonFile(event: Event) {
  const text = await readFileText(event);
  if (!text) return null;
  return JSON.parse(text);
}

export async function readFileText(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = '';
  if (!file) return null;
  return file.text();
}
