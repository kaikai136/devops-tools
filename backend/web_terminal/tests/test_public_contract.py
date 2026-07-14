from importlib import import_module
from unittest.mock import patch

from django.test import SimpleTestCase


EXPECTED_SERVICE_EXPORTS = [
    'DEFAULT_TERMINAL_COLS',
    'DEFAULT_TERMINAL_ROWS',
    'LiveTerminalConnection',
    'TerminalConnectionError',
    'append_audit_output',
    'append_session_recording_event',
    'asciicast_event',
    'asciicast_header',
    'build_rdp_connection_parameters',
    'build_rdp_recording_file',
    'calculate_monitor_cpu_usage',
    'clamp_rdp_dimension',
    'classify_command_risk',
    'cleanup_expired_rdp_recordings',
    'command_audit_payload',
    'create_command_audit',
    'create_rdp_terminal_session',
    'create_remote_directory',
    'create_remote_file',
    'create_remote_symlink',
    'create_terminal_session',
    'delete_remote_file',
    'detect_monitor_cpu_cores',
    'download_remote_file',
    'download_remote_file_content',
    'download_remote_file_content_with_scp_enhanced',
    'download_remote_file_content_with_scp_normal',
    'download_remote_file_content_with_sftp',
    'download_remote_file_with_scp_enhanced',
    'download_remote_file_with_scp_normal',
    'download_remote_file_with_sftp',
    'encode_remote_download',
    'enrich_remote_entries_with_stat',
    'ensure_remote_sftp_directory',
    'find_guacamole_instruction_end',
    'format_remote_timestamp',
    'get_remote_file_properties',
    'get_remote_file_properties_with_sftp',
    'get_remote_file_properties_with_stat',
    'get_remote_resource_monitor',
    'greeting_for',
    'group_payload',
    'guacamole_element',
    'guacamole_instruction',
    'host_payload',
    'initialize_session_recording',
    'is_guacamole_internal_instruction',
    'is_rdp_recording_enabled',
    'is_session_audit_enabled',
    'join_remote_path',
    'json_dumps',
    'list_remote_directory',
    'list_remote_directory_with_scp_enhanced',
    'list_remote_directory_with_scp_normal',
    'list_remote_directory_with_sftp',
    'load_private_key',
    'natural_sort_key',
    'normalize_remote_download_protocol',
    'normalize_remote_file_name',
    'normalize_remote_file_octal_mode',
    'normalize_remote_file_owner',
    'normalize_remote_file_path',
    'normalize_remote_relative_file_path',
    'normalize_remote_stat_identity',
    'normalize_remote_symlink_target',
    'normalize_terminal_output',
    'open_live_terminal',
    'open_ssh_client',
    'parent_remote_entry',
    'parent_remote_path',
    'parse_guacamole_instruction',
    'parse_monitor_cpu_line',
    'parse_monitor_disks',
    'parse_monitor_float',
    'parse_monitor_int',
    'parse_monitor_key_values',
    'parse_monitor_load',
    'parse_monitor_memory',
    'parse_monitor_network',
    'parse_monitor_network_rates',
    'parse_remote_find_entries',
    'parse_remote_ls_entries',
    'parse_remote_resource_monitor_output',
    'parse_remote_stat_output',
    'prune_empty_recording_parents',
    'rdp_recording_root',
    'read_guacamole_instruction',
    'remote_file_properties_payload',
    'remote_file_sort_key',
    'remote_file_sort_rank',
    'remote_stat_command',
    'rename_remote_file',
    'resolve_remote_directory_path',
    'resolve_remote_file_path',
    'resolve_remote_group_name',
    'resolve_remote_identity_names',
    'resolve_remote_user_name',
    'run_client_command',
    'run_live_terminal_command',
    'run_one_shot_ssh_command',
    'run_one_shot_ssh_upload',
    'run_optional_client_command',
    'run_remote_file_operation',
    'run_session_command',
    'safe_recording_relative_path',
    'save_session_recording',
    'session_payload',
    'should_retry_ssh_connect_error',
    'split_monitor_sections',
    'stream_remote_file_content',
    'stream_remote_file_content_with_scp',
    'stream_remote_file_content_with_sftp',
    'terminal_protocol_for_host',
    'terminal_tree_payload',
    'update_remote_file_properties',
    'upload_remote_file',
    'upload_remote_file_with_scp_enhanced',
    'upload_remote_file_with_scp_normal',
    'upload_remote_file_with_sftp',
]


class ServiceExportContractTests(SimpleTestCase):
    def test_existing_service_exports_remain_importable(self):
        module = import_module("web_terminal.services")
        missing = [
            name for name in EXPECTED_SERVICE_EXPORTS if not hasattr(module, name)
        ]
        self.assertEqual(missing, [])

    def test_temporary_service_attributes_do_not_propagate_to_implementation_modules(self):
        services = import_module("web_terminal.services")
        implementation_modules = [
            import_module("web_terminal.services_legacy"),
            import_module("web_terminal.services.payloads"),
            import_module("web_terminal.services.recordings"),
            import_module("web_terminal.services.audit"),
        ]
        attribute_name = "_temporary_service_contract_attribute"

        try:
            with patch.object(services, attribute_name, object(), create=True):
                leaked_modules = [
                    module.__name__
                    for module in implementation_modules
                    if hasattr(module, attribute_name)
                ]
                self.assertEqual(leaked_modules, [])
        finally:
            for module in implementation_modules:
                if hasattr(module, attribute_name):
                    delattr(module, attribute_name)

    def test_consumer_classes_remain_importable(self):
        module = import_module("web_terminal.consumers")
        self.assertTrue(hasattr(module, "TerminalConsumer"))
        self.assertTrue(hasattr(module, "RdpTerminalConsumer"))
