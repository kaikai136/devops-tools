export function prefixToMask(prefix: number) {
  const mask = prefix === 0 ? 0 : (0xffffffff << (32 - prefix)) >>> 0;
  return [24, 16, 8, 0].map((shift) => (mask >>> shift) & 255).join('.');
}

export function subnetBinaryParts(binary: string, prefix: number) {
  const clean = binary.replace(/\./g, '').padEnd(32, '0').slice(0, 32);
  return Array.from({ length: 4 }, (_, octetIndex) => {
    const start = octetIndex * 8;
    const octet = clean.slice(start, start + 8);
    const networkLength = Math.min(Math.max(prefix - start, 0), 8);
    return {
      network: octet.slice(0, networkLength),
      host: octet.slice(networkLength),
    };
  });
}
