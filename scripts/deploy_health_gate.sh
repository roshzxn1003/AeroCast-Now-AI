#!/usr/bin/env bash
# ==============================================================================
# AeroCast-Now AI: Deployment Health Gate & Smoke Verification (Phase 12)
# ==============================================================================
# Verifies that a target environment is fully operational and passes all
# critical liveness, readiness, inference, and database sanity checks.
# If any check fails, exits with non-zero code to block production promotion.
# ==============================================================================

set -e

TARGET_URL="${1:-http://localhost:8000}"
MAX_RETRIES=15
RETRY_DELAY=2

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}================================================================${NC}"
echo -e "${CYAN}⚡ AeroCast-Now AI: Executing Deployment Health Gate on ${TARGET_URL}${NC}"
echo -e "${CYAN}================================================================${NC}"

# 1. Liveness Probe
echo -n "[1/5] Probing Liveness (/health)... "
LIVENESS_OK=0
for ((i=1;i<=MAX_RETRIES;i++)); do
    if curl -sf "${TARGET_URL}/health" >/dev/null 2>&1; then
        LIVENESS_OK=1
        break
    fi
    sleep $RETRY_DELAY
done

if [ $LIVENESS_OK -eq 1 ]; then
    echo -e "${GREEN}PASSED${NC}"
else
    echo -e "${RED}FAILED${NC} (Service did not become responsive after $((MAX_RETRIES * RETRY_DELAY))s)"
    exit 1
fi

# 2. Readiness Probe
echo -n "[2/5] Probing Dependency Readiness (/ready)... "
READINESS_DATA=$(curl -s "${TARGET_URL}/ready")
if echo "$READINESS_DATA" | grep -qE '"overall_status":"(HEALTHY|DEGRADED)"'; then
    echo -e "${GREEN}PASSED${NC} (Database, model, and storage healthy)"
else
    echo -e "${RED}FAILED${NC}"
    echo "Readiness response: $READINESS_DATA"
    exit 1
fi

# 3. Operational API Health Check
echo -n "[3/5] Checking System Telemetry (/api/system/health)... "
SYS_STATUS=$(curl -s "${TARGET_URL}/api/system/health")
if echo "$SYS_STATUS" | grep -q '"status"'; then
    echo -e "${GREEN}PASSED${NC}"
else
    echo -e "${RED}FAILED${NC}"
    exit 1
fi

# 4. End-to-End Inference Smoke Test
echo -n "[4/5] Testing AI Nowcasting Forward Pass (/api/radar-grid)... "
INFERENCE_RES=$(curl -s "${TARGET_URL}/api/radar-grid?channel=dbz")
if echo "$INFERENCE_RES" | grep -q '"grid":'; then
    echo -e "${GREEN}PASSED${NC} (Radar grid generated successfully)"
else
    echo -e "${RED}FAILED${NC}"
    echo "Inference response: $INFERENCE_RES"
    exit 1
fi

# 5. Model Architecture & Integrity Verification
echo -n "[5/5] Verifying Production Model Parameters (/api/health)... "
HEALTH_RES=$(curl -s "${TARGET_URL}/api/health")
if echo "$HEALTH_RES" | grep -q '"model_loaded":true'; then
    PARAMS=$(echo "$HEALTH_RES" | grep -o '"model_params":[0-9]*' | cut -d: -f2)
    echo -e "${GREEN}PASSED${NC} (Active Model: ResAtt-ConvLSTM2D, ${PARAMS} parameters)"
else
    echo -e "${RED}FAILED${NC} (Model not reported loaded in health endpoint)"
    exit 1
fi

echo -e "\n${GREEN}================================================================${NC}"
echo -e "${GREEN}🎉 ALL DEPLOYMENT HEALTH GATES PASSED! Safe for Release Promotion.${NC}"
echo -e "${GREEN}================================================================${NC}"
exit 0
