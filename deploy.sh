#!/bin/bash
set -e
cd "$(dirname "$0")"
echo "=== 投资研究操作系统 部署 ==="
python3 -m venv venv 2>/dev/null || true
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
[ ! -f .env ] && cp .env.example .env && echo "已生成 .env"
mkdir -p data
python -c "from server import app; print('应用导入成功')"
# systemd
cat > /etc/systemd/system/investment-os.service <<EOF
[Unit]
Description=Investment Research OS
After=network.target
[Service]
Type=simple
WorkingDirectory=$(pwd)
EnvironmentFile=$(pwd)/.env
ExecStart=$(pwd)/venv/bin/python $(pwd)/server.py --port 8188
Restart=always
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now investment-os
sleep 2
systemctl status investment-os --no-pager -l | head -15
echo ""
echo "=== 部署完成 ==="
echo "访问: http://$(hostname -I | awk '{print $1}'):8188"
echo "日志: journalctl -u investment-os -f"
