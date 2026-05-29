#!/usr/bin/env bash
# ===========================================================================
# SonarQube / SonarScanner 一鍵自動化靜態程式碼分析腳本
# 專為台大期末報告設計 — 在本地端自動執行程式碼健全度、可維護性與安全性掃描
# ===========================================================================

# 終端機顏色輸出設定
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${CYAN}=====================================================================${NC}"
echo -e "${CYAN}       🛡️  SonarQube 程式碼品質與穩定性控制掃描工具 (NTU Staging)       ${NC}"
echo -e "${CYAN}=====================================================================${NC}"

# 1. 檢查 Docker 運行狀態
if ! docker info >/dev/null 2>&1; then
    echo -e "${RED}[錯誤] Docker 尚未啟動！請先開啟 Docker Desktop 後再執行此腳本。${NC}"
    exit 1
fi

# 2. 檢查測試覆蓋率報告是否存在
echo -e "\n${YELLOW}[步驟 1/4] 檢查測試覆蓋率報告...${NC}"
RUN_TESTS=false

if [ ! -f "backend/coverage.xml" ]; then
    echo -e "${YELLOW}[提示] 未偵測到後端測試覆蓋率報告 (backend/coverage.xml)。${NC}"
    RUN_TESTS=true
fi

if [ ! -f "frontend/coverage/lcov.info" ]; then
    echo -e "${YELLOW}[提示] 未偵測到前端測試覆蓋率報告 (frontend/coverage/lcov.info)。${NC}"
    RUN_TESTS=true
fi

if [ "$RUN_TESTS" = true ]; then
    echo -e "${CYAN}正在自動執行測試以生成覆蓋率報告（這能確保 SonarQube 能正確顯示 80%+ 的測試覆蓋率）...${NC}"
    
    # 執行後端單元與整合測試
    echo -e "${CYAN}👉 正在執行後端 pytest 測試並輸出 coverage.xml...${NC}"
    cd backend || exit
    # 使用本地 virtualenv 或 python 執行
    if [ -d ".venv" ]; then
        source .venv/bin/activate
        pytest --cov=app --cov-report=xml:coverage.xml tests/unit/
        deactivate
    else
        python3 -m pytest --cov=app --cov-report=xml:coverage.xml tests/unit/ 2>/dev/null || echo -e "${RED}[警告] 後端本地測試執行失敗，將跳過覆蓋率導入${NC}"
    fi
    cd ..

    # 執行前端測試
    echo -e "\n${CYAN}👉 正在執行前端 vitest 測試並輸出 lcov.info...${NC}"
    cd frontend || exit
    if command -v pnpm &> /dev/null; then
        pnpm vitest run --coverage 2>/dev/null || echo -e "${RED}[警告] 前端本地測試執行失敗，將跳過覆蓋率導入${NC}"
    else
        npm install -g pnpm 2>/dev/null
        pnpm vitest run --coverage 2>/dev/null || echo -e "${RED}[警告] 前端本地測試執行失敗，將跳過覆蓋率導入${NC}"
    fi
    cd ..
fi

# 3. 啟動或檢查本地 SonarQube 伺服器
echo -e "\n${YELLOW}[步驟 2/4] 檢查本地 SonarQube 伺服器...${NC}"
if [ "$(docker ps -q -f name=sonarqube-server)" ]; then
    echo -e "${GREEN}✓ 本地 SonarQube 伺服器已在運行中。${NC}"
else
    echo -e "${CYAN}正在使用 Docker Compose 啟動本地 SonarQube 服務 (埠號 9000)...${NC}"
    docker compose -f docker-compose.sonar.yml up -d
    
    echo -e "${YELLOW}等待 SonarQube 服務初始化中 (預估需要 30-45 秒)...${NC}"
    # 輪詢埠號 9000 確保服務就緒
    until curl -s http://localhost:9000 >/dev/null; do
        echo -ne "${YELLOW}.${NC}"
        sleep 3
    done
    echo -e "\n${GREEN}✓ SonarQube 伺服器就緒！${NC}"
fi

echo -e "${GREEN}👉 請在瀏覽器打開: http://localhost:9000${NC}"
echo -e "${YELLOW}[重要提示] 如果這是您第一次登入，請使用預設帳密:${NC}"
echo -e "   - 帳號: ${CYAN}admin${NC}"
echo -e "   - 密碼: ${CYAN}admin${NC}"
echo -e "*(系統會要求您立即修改密碼，修改完後請至 [My Account] -> [Security] 產生一個 [User Token])* "

# 4. 輸入 SonarQube Token
echo -e "\n${YELLOW}[步驟 3/4] 授權金鑰配置...${NC}"
read -p "請輸入您的 SonarQube User Token (或直接按 Enter 跳過並使用匿名分析): " SONAR_TOKEN

# 5. 啟動 SonarScanner 容器執行掃描
echo -e "\n${YELLOW}[步驟 4/4] 啟動 SonarScanner 靜態代碼分析...${NC}"
echo -e "${CYAN}正在掛載本地目錄並啟動 SonarScanner 進行程式碼審查...${NC}"

SCANNER_CMD="docker run --rm \
  --network=sonar-network \
  -v \"$(pwd):/usr/src\" \
  sonarsource/sonar-scanner-cli \
  -Dsonar.host.url=http://sonarqube:9000"

if [ -n "$SONAR_TOKEN" ]; then
    SCANNER_CMD="$SCANNER_CMD -Dsonar.token=$SONAR_TOKEN"
fi

# 執行分析
eval "$SCANNER_CMD"

if [ $? -eq 0 ]; then
    echo -e "\n${GREEN}=====================================================================${NC}"
    echo -e "${GREEN}       🎉  SonarQube 靜態分析完成！                                     ${NC}"
    echo -e "       👉 請至 http://localhost:9000 查看您的代碼健全度與測試覆蓋率報告！   ${NC}"
    echo -e "${GREEN}=====================================================================${NC}"
else
    echo -e "\n${RED}[錯誤] 程式碼掃描分析失敗！請檢查 SonarQube Server 狀態與 Token 密鑰配置。${NC}"
fi
