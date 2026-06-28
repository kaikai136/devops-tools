from __future__ import annotations

import re
from dataclasses import dataclass

from django.contrib.auth.models import AnonymousUser

from host_management.models import ManagedHost
from web_terminal.models import TerminalSession

from .models import SecurityCommandRecord, SecurityCommandRule


@dataclass(frozen=True)
class SecurityCommandMatch:
    rule: SecurityCommandRule
    pattern: str
    command: str

    @property
    def blocked(self) -> bool:
        return self.rule.action == SecurityCommandRule.ACTION_BLOCK

    @property
    def message(self) -> str:
        action_text = "已阻断" if self.blocked else "已告警"
        return f"安全告警：命令命中规则「{self.rule.name}」，{action_text}。"


def rule_lines(content: str) -> list[str]:
    return [line.strip() for line in str(content or "").splitlines() if line.strip()]


def validate_regex_lines(content: str, ignore_case: bool) -> None:
    flags = re.IGNORECASE if ignore_case else 0
    for line in rule_lines(content):
        re.compile(line, flags)


def match_security_command(command: str) -> SecurityCommandMatch | None:
    normalized_command = str(command or "").strip()
    if not normalized_command:
        return None

    for rule in SecurityCommandRule.objects.filter(enabled=True).order_by("id"):
        pattern = match_rule_line(rule, normalized_command)
        if pattern:
            return SecurityCommandMatch(rule=rule, pattern=pattern, command=normalized_command)
    return None


def match_rule_line(rule: SecurityCommandRule, command: str) -> str:
    flags = re.IGNORECASE if rule.ignore_case else 0
    for pattern in rule_lines(rule.content):
        if rule.match_type == SecurityCommandRule.MATCH_TYPE_REGEX:
            try:
                if re.search(pattern, command, flags):
                    return pattern
            except re.error:
                continue
        elif command_matches_literal(command, pattern, rule.ignore_case):
            return pattern
    return ""


def command_matches_literal(command: str, pattern: str, ignore_case: bool) -> bool:
    command_value = command.casefold() if ignore_case else command
    pattern_value = pattern.casefold() if ignore_case else pattern
    if command_value == pattern_value:
        return True
    if not command_value.startswith(pattern_value):
        return False
    if len(command_value) <= len(pattern_value):
        return False
    return command_value[len(pattern_value)].isspace()


def record_security_command_match(
    match: SecurityCommandMatch,
    *,
    user,
    host: ManagedHost | None,
    session: TerminalSession | None,
) -> SecurityCommandRecord:
    user_value = None if not user or isinstance(user, AnonymousUser) or not getattr(user, "is_authenticated", False) else user
    return SecurityCommandRecord.objects.create(
        user=user_value,
        host=host,
        session=session,
        rule=match.rule,
        rule_name=match.rule.name,
        command=match.command,
        action=match.rule.action,
        blocked=match.blocked,
        message=match.message,
    )
