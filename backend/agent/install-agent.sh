#!/bin/sh
set -eu

log() {
	printf '%s\n' "$*"
}

die() {
	printf 'ERROR: %s\n' "$*" >&2
	exit 1
}

need_command() {
	command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"
}

regular_file_or_missing() {
	path=$1
	if [ -L "$path" ]; then
		die "$path must not be a symlink"
	fi
	if [ -e "$path" ] && [ ! -f "$path" ]; then
		die "$path must be a regular file"
	fi
}

script_dir() {
	case "$0" in
		/*) script_path=$0 ;;
		*) script_path=$(pwd)/$0 ;;
	esac
	CDPATH= cd -- "$(dirname -- "$script_path")" && pwd
}

detect_arch() {
	if [ -n "${ARCH:-}" ]; then
		case "$ARCH" in
			linux-amd64) GOARCH=amd64 ;;
			linux-arm64) GOARCH=arm64 ;;
			*) die "unsupported ARCH: $ARCH; use linux-amd64 or linux-arm64" ;;
		esac
		return
	fi

	case "$(uname -m)" in
		x86_64|amd64)
			ARCH=linux-amd64
			GOARCH=amd64
			;;
		aarch64|arm64)
			ARCH=linux-arm64
			GOARCH=arm64
			;;
		*)
			die "unsupported machine architecture: $(uname -m)"
			;;
	esac
}

find_file() {
	for candidate in "$@"; do
		if [ -f "$candidate" ]; then
			printf '%s\n' "$candidate"
			return 0
		fi
	done
	return 1
}

build_binaries() {
	version=dev
	if [ -f "$ROOT_DIR/VERSION" ]; then
		version=$(tr -d '\r\n' < "$ROOT_DIR/VERSION")
	fi
	ldflags="-s -w -X github.com/kejilion/devops-agent/internal/version.Version=$version"

	agent_binary=$(find_file \
		"$DEPLOY_DIR/bin/$ARCH/devops-agent" \
		"$ROOT_DIR/release/devops-agent" \
		"$ROOT_DIR/dist/$ARCH/devops-agent" || true)
	if [ -n "$agent_binary" ]; then
		AGENT_BINARY=$agent_binary
		log "Using prebuilt Agent binary: $AGENT_BINARY"
	else
		command -v go >/dev/null 2>&1 || die "Go toolchain is required when no prebuilt Agent binary is available"
		if [ -z "${BUILD_DIR:-}" ]; then
			BUILD_DIR=$(mktemp -d "${TMPDIR:-/tmp}/devops-agent-build.XXXXXX")
			cleanup() {
				rm -rf "$BUILD_DIR"
			}
			trap cleanup EXIT HUP INT TERM
		fi
		log "Building Agent binary for $ARCH on host..."
		CGO_ENABLED=0 GOOS=linux GOARCH="$GOARCH" go build -trimpath -ldflags "$ldflags" -o "$BUILD_DIR/devops-agent" "$ROOT_DIR/cmd/devops-agent"
		AGENT_BINARY="$BUILD_DIR/devops-agent"
	fi

	if [ "$INSTALL_GATEWAY" != "0" ]; then
		gateway_binary=$(find_file \
			"$DEPLOY_DIR/bin/$ARCH/devops-agent-gateway" \
			"$ROOT_DIR/release/devops-agent-gateway" \
			"$ROOT_DIR/dist/$ARCH/devops-agent-gateway" || true)
		if [ -n "$gateway_binary" ]; then
			GATEWAY_BINARY=$gateway_binary
			log "Using prebuilt Gateway binary: $GATEWAY_BINARY"
		else
			command -v go >/dev/null 2>&1 || die "Go toolchain is required when no prebuilt Gateway binary is available"
			if [ -z "${BUILD_DIR:-}" ]; then
				BUILD_DIR=$(mktemp -d "${TMPDIR:-/tmp}/devops-agent-build.XXXXXX")
				cleanup() {
					rm -rf "$BUILD_DIR"
				}
				trap cleanup EXIT HUP INT TERM
			fi
			log "Building Gateway binary for $ARCH on host..."
			CGO_ENABLED=0 GOOS=linux GOARCH="$GOARCH" go build -trimpath -ldflags "$ldflags" -o "$BUILD_DIR/devops-agent-gateway" "$ROOT_DIR/cmd/devops-agent-gateway"
			GATEWAY_BINARY="$BUILD_DIR/devops-agent-gateway"
		fi
	fi
}

resolve_asset() {
	name=$1
	find_file \
		"$DEPLOY_DIR/systemd/$name" \
		"$ROOT_DIR/deploy/systemd/$name" \
		"$ROOT_DIR/release/$name" || die "cannot find deployment asset: $name"
}

generate_token() {
	if command -v openssl >/dev/null 2>&1; then
		openssl rand -hex 32
		return
	fi
	tr -dc 'A-Za-z0-9' </dev/urandom | head -c 64
	printf '\n'
}

ensure_token() {
	token_file=$1
	regular_file_or_missing "$token_file"
	if [ ! -s "$token_file" ]; then
		tmp_file="$token_file.tmp.$$"
		generate_token > "$tmp_file"
		chown "root:$AGENT_GROUP" "$tmp_file"
		chmod 0640 "$tmp_file"
		mv "$tmp_file" "$token_file"
	fi
	chown "root:$AGENT_GROUP" "$token_file"
	chmod 0640 "$token_file"
}

install_env_if_missing() {
	source_file=$1
	target_file=$2
	regular_file_or_missing "$target_file"
	if [ ! -e "$target_file" ]; then
		install -o root -g root -m 0640 "$source_file" "$target_file"
	fi
}

ensure_text_file() {
	target_file=$1
	regular_file_or_missing "$target_file"
	if [ ! -e "$target_file" ]; then
		tmp_file="$target_file.tmp.$$"
		cat > "$tmp_file"
		chown root:root "$tmp_file"
		chmod 0640 "$tmp_file"
		mv "$tmp_file" "$target_file"
	fi
}

ipv4_to_cidr24() {
	ipv4=$1
	old_ifs=$IFS
	IFS=.
	set -- $ipv4
	IFS=$old_ifs
	[ "$#" -eq 4 ] || return 1
	case "$1:$2:$3:$4" in
		*[!0-9:]*|*::* ) return 1 ;;
	esac
	printf '%s.%s.%s.0/24\n' "$1" "$2" "$3"
}

detect_primary_ipv4() {
	if command -v ip >/dev/null 2>&1; then
		candidate=$(ip -4 route get 1.1.1.1 2>/dev/null | sed -n 's/.* src \([0-9][0-9.]*\).*/\1/p' | head -n 1)
		case "$candidate" in
			*.*.*.*) printf '%s\n' "$candidate"; return 0 ;;
		esac
		candidate=$(ip -o -4 addr show scope global 2>/dev/null | sed -n 's|.* inet \([0-9][0-9.]*\)/[0-9][0-9]* .*|\1|p' | head -n 1)
		case "$candidate" in
			*.*.*.*) printf '%s\n' "$candidate"; return 0 ;;
		esac
	fi
	if command -v hostname >/dev/null 2>&1; then
		for candidate in $(hostname -I 2>/dev/null); do
			case "$candidate" in
				127.*|0.*|::1|'') continue ;;
			esac
			case "$candidate" in
				*.*.*.*) printf '%s\n' "$candidate"; return 0 ;;
			esac
		done
	fi
	return 1
}

default_gateway_allowed_cidrs() {
	base_cidrs='127.0.0.0/8,::1/128,172.16.0.0/24'
	candidate=$(detect_primary_ipv4 || true)
	if cidr24=$(ipv4_to_cidr24 "$candidate" 2>/dev/null); then
		case ",$base_cidrs," in
			*",$cidr24,"*) printf '%s\n' "$base_cidrs" ;;
			*) printf '%s,%s\n' "$base_cidrs" "$cidr24" ;;
		esac
		return 0
	fi
	printf '%s\n' "$base_cidrs"
}

set_env_value() {
	env_file=$1
	key=$2
	value=$3
	regular_file_or_missing "$env_file"
	tmp_file="$env_file.tmp.$$"
	if grep -q "^$key=" "$env_file"; then
		sed "s|^$key=.*|$key=$value|" "$env_file" > "$tmp_file"
	else
		cat "$env_file" > "$tmp_file"
		printf '%s=%s\n' "$key" "$value" >> "$tmp_file"
	fi
	cat "$tmp_file" > "$env_file"
	rm -f "$tmp_file"
	chown root:root "$env_file"
	chmod 0640 "$env_file"
}

wait_for_agent_healthcheck() {
	timeout_seconds=${AGENT_HEALTHCHECK_TIMEOUT:-60}
	case "$timeout_seconds" in
		*[!0-9]*|''|0) die "AGENT_HEALTHCHECK_TIMEOUT must be a positive integer" ;;
	esac

	log "Waiting for Agent healthcheck (up to ${timeout_seconds}s)..."
	attempt=0
	while [ "$attempt" -lt "$timeout_seconds" ]; do
		if "$LIBEXEC_DIR/devops-agent" healthcheck >/dev/null 2>&1; then
			log "Agent healthcheck passed."
			return
		fi
		attempt=$((attempt + 1))
		if [ $((attempt % 5)) -eq 0 ]; then
			log "Still waiting for Agent healthcheck... (${attempt}s)"
		fi
		[ "$attempt" -ge "$timeout_seconds" ] || sleep 1
	done
	if ! "$LIBEXEC_DIR/devops-agent" healthcheck; then
		systemctl --no-pager --full status devops-agent.service || true
		die "Agent did not become healthy after restart"
	fi
}

[ "$(id -u)" -eq 0 ] || die "run as root, for example: sudo sh deploy/install-agent.sh"

SCRIPT_DIR=$(script_dir)
DEPLOY_DIR=$SCRIPT_DIR
ROOT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
INSTALL_GATEWAY=${INSTALL_GATEWAY:-1}
AGENT_GROUP=${AGENT_GROUP:-devops-agent}
CONFIG_DIR=${CONFIG_DIR:-/etc/devops-agent}
LIBEXEC_DIR=${LIBEXEC_DIR:-/usr/local/libexec}
STATE_DIR=${STATE_DIR:-/var/lib/devops-agent}
SERVICE_DIR=${SERVICE_DIR:-/etc/systemd/system}
WEB_ROOT=${WEB_ROOT:-/home/web}
APP_ROOT=${APP_ROOT:-/home/docker}
GATEWAY_ALLOWED_CIDRS=${GATEWAY_ALLOWED_CIDRS:-}

require_install_commands() {
	need_command uname
	need_command install
	need_command systemctl
	need_command chown
	need_command chmod
	need_command mv
	need_command groupadd
	need_command sed
	need_command grep
	need_command head
	need_command mktemp
	need_command sleep
}

require_uninstall_commands() {
	need_command systemctl
	need_command rm
}

bootstrap_runtime_scaffold() {
	install -d -o root -g root -m 0755 \
		"$WEB_ROOT" \
		"$WEB_ROOT/conf.d" \
		"$WEB_ROOT/html" \
		"$WEB_ROOT/certs" \
		"$WEB_ROOT/stream.d" \
		"$WEB_ROOT/letsencrypt" \
		"$WEB_ROOT/log" \
		"$WEB_ROOT/log/nginx" \
		"$APP_ROOT" \
		"$APP_ROOT/devops-agent" \
		"$APP_ROOT/devops-agent/bin" \
		"$APP_ROOT/devops-agent/secrets" \
		"$APP_ROOT/devops-agent/data" \
		"$APP_ROOT/devops-agent/data/panel" \
		"$APP_ROOT/devops-agent/data/agent" \
		"$APP_ROOT/devops-agent/run"
	ensure_text_file "$WEB_ROOT/nginx.conf" <<'EOF'
events {}
http {
    include /etc/nginx/conf.d/*.conf;
}
EOF
}

stop_and_disable_unit() {
	unit=$1
	systemctl stop "$unit" >/dev/null 2>&1 || true
	systemctl disable "$unit" >/dev/null 2>&1 || true
}

remove_path() {
	path=$1
	case "$path" in
		''|/) die "refusing to remove unsafe path: $path" ;;
		/*) ;;
		*) die "refusing to remove non-absolute path: $path" ;;
	esac
	if [ -e "$path" ] || [ -L "$path" ]; then
		rm -rf "$path"
	fi
}

do_install() {
	case "$INSTALL_GATEWAY" in
		0|1) ;;
		*) die "INSTALL_GATEWAY must be 0 or 1" ;;
	esac

	require_install_commands
	detect_arch
	build_binaries
	AGENT_SERVICE=$(resolve_asset devops-agent.service)
	AGENT_ENV_EXAMPLE=$(resolve_asset agent.env.example)

	log "Installing DevOps Agent on host..."
	groupadd --system "$AGENT_GROUP" 2>/dev/null || true
	install -d -o root -g "$AGENT_GROUP" -m 0750 "$CONFIG_DIR"
	install -d -o root -g root -m 0755 "$LIBEXEC_DIR" "$STATE_DIR" "$SERVICE_DIR"
	ensure_token "$CONFIG_DIR/agent.token"
	install -o root -g root -m 0755 "$AGENT_BINARY" "$LIBEXEC_DIR/devops-agent"
	install -o root -g root -m 0644 "$AGENT_SERVICE" "$SERVICE_DIR/devops-agent.service"
	install_env_if_missing "$AGENT_ENV_EXAMPLE" "$CONFIG_DIR/agent.env"
	set_env_value "$CONFIG_DIR/agent.env" DEVOPS_AGENT_STATE_DIR "$STATE_DIR"
	set_env_value "$CONFIG_DIR/agent.env" DEVOPS_WEB_ROOT "$WEB_ROOT"
	bootstrap_runtime_scaffold
	if [ -n "$GATEWAY_ALLOWED_CIDRS" ]; then
		GATEWAY_ALLOWED_CIDRS_EFFECTIVE=$GATEWAY_ALLOWED_CIDRS
	else
		GATEWAY_ALLOWED_CIDRS_EFFECTIVE=$(default_gateway_allowed_cidrs)
	fi

	if [ "$INSTALL_GATEWAY" = "1" ]; then
		GATEWAY_SERVICE=$(resolve_asset devops-agent-gateway.service)
		GATEWAY_ENV_EXAMPLE=$(resolve_asset agent-gateway.env.example)
		log "Installing DevOps Agent Gateway on host..."
		ensure_token "$CONFIG_DIR/agent-gateway.token"
		install -o root -g root -m 0755 "$GATEWAY_BINARY" "$LIBEXEC_DIR/devops-agent-gateway"
		install -o root -g root -m 0644 "$GATEWAY_SERVICE" "$SERVICE_DIR/devops-agent-gateway.service"
		install_env_if_missing "$GATEWAY_ENV_EXAMPLE" "$CONFIG_DIR/agent-gateway.env"
		set_env_value "$CONFIG_DIR/agent-gateway.env" DEVOPS_AGENT_GATEWAY_LISTEN "0.0.0.0:9081"
		set_env_value "$CONFIG_DIR/agent-gateway.env" DEVOPS_AGENT_GATEWAY_ALLOWED_CIDRS "$GATEWAY_ALLOWED_CIDRS_EFFECTIVE"
	fi

	systemctl daemon-reload
	systemctl enable devops-agent.service
	systemctl restart devops-agent.service
	wait_for_agent_healthcheck

	if [ "$INSTALL_GATEWAY" = "1" ]; then
		systemctl enable devops-agent-gateway.service
		systemctl restart devops-agent-gateway.service
		"$LIBEXEC_DIR/devops-agent-gateway" version
	fi

	log "DevOps Agent deployment finished."
	log "Agent service: systemctl status devops-agent.service"
	if [ "$INSTALL_GATEWAY" = "1" ]; then
		log "Gateway service: systemctl status devops-agent-gateway.service"
		log "Gateway listens on 0.0.0.0:9081. Allowed CIDRs are configured in $CONFIG_DIR/agent-gateway.env"
	fi
}

do_uninstall() {
	require_uninstall_commands
	log "Uninstalling DevOps Agent from host..."
	stop_and_disable_unit devops-agent-gateway.service
	stop_and_disable_unit devops-agent.service
	remove_path "$SERVICE_DIR/devops-agent-gateway.service"
	remove_path "$SERVICE_DIR/devops-agent.service"
	remove_path "$LIBEXEC_DIR/devops-agent-gateway"
	remove_path "$LIBEXEC_DIR/devops-agent"
	remove_path "$APP_ROOT/devops-agent"
	remove_path "$CONFIG_DIR"
	remove_path "$STATE_DIR"
	command -v groupdel >/dev/null 2>&1 && groupdel "$AGENT_GROUP" >/dev/null 2>&1 || true
	systemctl daemon-reload
	log "DevOps Agent removal finished."
}

ACTION=${1:-install}
if [ "$#" -gt 0 ]; then
	shift
fi
if [ "$#" -ne 0 ]; then
	die "usage: sh deploy/install-agent.sh [install|uninstall]"
fi

case "$ACTION" in
	install) do_install ;;
	uninstall) do_uninstall ;;
	*) die "usage: sh deploy/install-agent.sh [install|uninstall]" ;;
esac
