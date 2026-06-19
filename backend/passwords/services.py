import secrets


def generate_password(
    length: int,
    include_uppercase: bool,
    include_lowercase: bool,
    include_numbers: bool,
    include_symbols: bool,
) -> str:
    groups = []
    if include_uppercase:
        groups.append("ABCDEFGHJKLMNPQRSTUVWXYZ")
    if include_lowercase:
        groups.append("abcdefghijkmnopqrstuvwxyz")
    if include_numbers:
        groups.append("23456789")
    if include_symbols:
        groups.append("!@#$%^&*_-+=?")

    if not groups:
        raise ValueError("至少选择一种字符类型")

    length = max(len(groups), min(64, max(6, int(length))))
    characters = [secrets.choice(group) for group in groups]
    pool = "".join(groups)
    characters.extend(secrets.choice(pool) for _ in range(length - len(characters)))
    secrets.SystemRandom().shuffle(characters)
    return "".join(characters)
