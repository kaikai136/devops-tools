export interface AvatarIdentity {
  username?: string | null;
  displayName?: string | null;
  firstName?: string | null;
  email?: string | null;
}

export function getAvatarInitial(identity: AvatarIdentity): string {
  const source = [identity.username, identity.displayName, identity.firstName, identity.email]
    .map((value) => String(value ?? '').trim())
    .find(Boolean);

  if (!source) return '?';

  const letter = Array.from(source).find((character) => /[\p{L}\p{N}]/u.test(character));
  return letter ? letter.toLocaleUpperCase('zh-CN') : '?';
}
