#!/bin/bash

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON_CMD="${PYTHON_CMD:-python3}"
MARK_EXPRESSION="live"
DRY_RUN=false
WITH_GENERATION=true
PYTEST_ARGS=()

usage() {
    cat <<'EOF'
用法:
  ./run_live_smoke.sh [选项] [-- pytest额外参数]

选项:
  --keyword <关键词>           覆盖 LIVE_TEST_KEYWORD
  --account-file <路径>        覆盖 LIVE_TEST_ACCOUNT_STATE_FILE
  --task-name <名称>           覆盖 LIVE_TEST_TASK_NAME
  --timeout <秒>               覆盖 LIVE_TIMEOUT_SECONDS
  --min-items <数量>           覆盖 LIVE_EXPECT_MIN_ITEMS
  --debug-limit <数量>         覆盖 LIVE_TEST_DEBUG_LIMIT（默认 1，仅分析前 N 个新商品）
  --with-generation            显式开启 live_slow（默认已开启）
  --without-generation         关闭 live_slow，只执行主 smoke
  --dry-run                    只打印配置和将执行的命令，不真正运行
  --help                       显示帮助

示例:
  ./run_live_smoke.sh
  ./run_live_smoke.sh --keyword "MacBook Air M1" --min-items 2
  ./run_live_smoke.sh --without-generation
  ./run_live_smoke.sh -- -k live_real_traffic

说明:
  1. 脚本会自动设置 RUN_LIVE_TESTS=1
  2. 若未设置 LIVE_TEST_ACCOUNT_STATE_FILE，会自动尝试使用 state/ 下第一个 *.json
  3. 默认使用 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1，避免本机第三方 pytest 插件干扰
  4. 默认设置 LIVE_TEST_DEBUG_LIMIT=1，使冒烟测试只抓取并分析 1 个新商品
EOF
}

require_value() {
    local option="$1"
    local value="${2:-}"
    if [[ -z "$value" ]]; then
        echo -e "${RED}错误:${NC} ${option} 需要一个值"
        exit 1
    fi
}

resolve_default_account_file() {
    local first_match=""
    while IFS= read -r file; do
        first_match="$file"
        break
    done < <(find "$SCRIPT_DIR/state" -maxdepth 1 -type f -name '*.json' | sort)
    printf '%s' "$first_match"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --keyword)
            require_value "$1" "${2:-}"
            export LIVE_TEST_KEYWORD="$2"
            shift 2
            ;;
        --account-file)
            require_value "$1" "${2:-}"
            export LIVE_TEST_ACCOUNT_STATE_FILE="$2"
            shift 2
            ;;
        --task-name)
            require_value "$1" "${2:-}"
            export LIVE_TEST_TASK_NAME="$2"
            shift 2
            ;;
        --timeout)
            require_value "$1" "${2:-}"
            export LIVE_TIMEOUT_SECONDS="$2"
            shift 2
            ;;
        --min-items)
            require_value "$1" "${2:-}"
            export LIVE_EXPECT_MIN_ITEMS="$2"
            shift 2
            ;;
        --debug-limit)
            require_value "$1" "${2:-}"
            export LIVE_TEST_DEBUG_LIMIT="$2"
            shift 2
            ;;
        --with-generation)
            WITH_GENERATION=true
            shift
            ;;
        --without-generation)
            WITH_GENERATION=false
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        --)
            shift
            PYTEST_ARGS+=("$@")
            break
            ;;
        *)
            PYTEST_ARGS+=("$1")
            shift
            ;;
    esac
done

if ! command -v "$PYTHON_CMD" >/dev/null 2>&1; then
    echo -e "${RED}错误:${NC} 未找到 Python 命令: $PYTHON_CMD"
    exit 1
fi

if ! "$PYTHON_CMD" -m pytest --version >/dev/null 2>&1; then
    echo -e "${RED}错误:${NC} 当前 Python 环境缺少 pytest"
    exit 1
fi

if ! "$PYTHON_CMD" -m playwright --version >/dev/null 2>&1; then
    echo -e "${RED}错误:${NC} 当前 Python 环境缺少 Playwright，请先安装浏览器依赖"
    exit 1
fi

export RUN_LIVE_TESTS=1
export PYTEST_DISABLE_PLUGIN_AUTOLOAD="${PYTEST_DISABLE_PLUGIN_AUTOLOAD:-1}"
export LIVE_TEST_KEYWORD="${LIVE_TEST_KEYWORD:-MacBook Pro M2}"
export LIVE_TEST_TASK_NAME="${LIVE_TEST_TASK_NAME:-Live Smoke Task}"
export LIVE_EXPECT_MIN_ITEMS="${LIVE_EXPECT_MIN_ITEMS:-1}"
export LIVE_TEST_DEBUG_LIMIT="${LIVE_TEST_DEBUG_LIMIT:-1}"
export LIVE_TIMEOUT_SECONDS="${LIVE_TIMEOUT_SECONDS:-180}"

if [[ -z "${LIVE_TEST_ACCOUNT_STATE_FILE:-}" ]]; then
    DEFAULT_ACCOUNT_FILE="$(resolve_default_account_file)"
    if [[ -n "$DEFAULT_ACCOUNT_FILE" ]]; then
        export LIVE_TEST_ACCOUNT_STATE_FILE="$DEFAULT_ACCOUNT_FILE"
    fi
fi

if [[ -z "${LIVE_TEST_ACCOUNT_STATE_FILE:-}" ]]; then
    echo -e "${RED}错误:${NC} 未找到 live 登录态文件。请使用 --account-file 指定，或在 state/ 下放置 *.json"
    exit 1
fi

if [[ ! -f "${LIVE_TEST_ACCOUNT_STATE_FILE}" ]]; then
    echo -e "${RED}错误:${NC} 登录态文件不存在: ${LIVE_TEST_ACCOUNT_STATE_FILE}"
    exit 1
fi

if [[ "$WITH_GENERATION" == "true" ]]; then
    export LIVE_ENABLE_TASK_GENERATION=1
    MARK_EXPRESSION="live"
else
    export LIVE_ENABLE_TASK_GENERATION=0
    MARK_EXPRESSION="live and not live_slow"
fi

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}闲鱼真实流量 Live Smoke 一键测试${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "${YELLOW}Python:${NC} $PYTHON_CMD"
echo -e "${YELLOW}关键词:${NC} ${LIVE_TEST_KEYWORD}"
echo -e "${YELLOW}任务名:${NC} ${LIVE_TEST_TASK_NAME}"
echo -e "${YELLOW}登录态:${NC} ${LIVE_TEST_ACCOUNT_STATE_FILE}"
echo -e "${YELLOW}最少结果数:${NC} ${LIVE_EXPECT_MIN_ITEMS}"
echo -e "${YELLOW}抓取/分析商品上限:${NC} ${LIVE_TEST_DEBUG_LIMIT}"
echo -e "${YELLOW}超时(秒):${NC} ${LIVE_TIMEOUT_SECONDS}"
echo -e "${YELLOW}任务生成慢用例:${NC} ${LIVE_ENABLE_TASK_GENERATION}"
echo -e "${YELLOW}Pytest Marker:${NC} ${MARK_EXPRESSION}"
echo -e "${YELLOW}禁用插件自动加载:${NC} ${PYTEST_DISABLE_PLUGIN_AUTOLOAD}"

CMD=(
    "$PYTHON_CMD" -m pytest
    tests/live
    -m "$MARK_EXPRESSION"
    -v
)

if [[ ${#PYTEST_ARGS[@]} -gt 0 ]]; then
    CMD+=("${PYTEST_ARGS[@]}")
fi

echo -e "${YELLOW}执行命令:${NC} ${CMD[*]}"

if [[ "$DRY_RUN" == "true" ]]; then
    echo -e "${GREEN}Dry run 完成，未实际执行测试。${NC}"
    exit 0
fi

"${CMD[@]}"
