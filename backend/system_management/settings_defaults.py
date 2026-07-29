DEFAULT_LOG_RETENTION = {
    "loginLogsDays": 180,
    "operationLogsDays": 180,
    "terminalCommandAuditDays": 180,
    "terminalFileAuditDays": 180,
    "terminalSessionDays": 180,
    "rdpRecordingEnabled": False,
    "rdpRecordingDays": 30,
}

LOG_RETENTION_DAY_FIELDS = {
    "loginLogsDays",
    "operationLogsDays",
    "terminalCommandAuditDays",
    "terminalFileAuditDays",
    "terminalSessionDays",
    "rdpRecordingDays",
}
