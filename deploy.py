"""部署 investment-os 到云服务器"""
import paramiko
import os

HOST = "159.138.92.82"
USER = "root"
PASSWORD = "zdmy3n14F"
REMOTE_DIR = "/opt/investment-os"

def run_ssh(cmd):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=120)
    out = stdout.read().decode()
    err = stderr.read().decode()
    ssh.close()
    return out, err

def main():
    print("=== 1. 检查远程环境 ===")
    out, err = run_ssh("python3 --version; git --version; ls /opt/investment-os 2>/dev/null || echo 'NOT_FOUND'")
    print(out, err)

    print("=== 2. 克隆/更新仓库 ===")
    cmds = [
        "mkdir -p /opt",
        "cd /opt && (git clone https://github.com/luochan1028/investment-os.git 2>/dev/null || (cd investment-os && git pull origin main))",
        "cd /opt/investment-os && git log --oneline -1",
    ]
    for cmd in cmds:
        out, err = run_ssh(cmd)
        print(out, err)

    print("=== 3. 安装依赖 ===")
    out, err = run_ssh("cd /opt/investment-os && pip3 install --break-system-packages -q -r requirements.txt 2>&1 | tail -5")
    print(out, err)

    print("=== 4. 停止旧进程 ===")
    out, err = run_ssh("pkill -f 'python3.*server.py' 2>/dev/null; sleep 1; echo 'done'")
    print(out, err)

    print("=== 5. 初始化数据库 ===")
    out, err = run_ssh("cd /opt/investment-os && python3 -c 'from store import init_db; init_db(); print(\"DB init OK\")'")
    print(out, err)

    print("=== 6. 启动服务 ===")
    out, err = run_ssh("cd /opt/investment-os && nohup python3 server.py > /tmp/investment-os.log 2>&1 & sleep 3 && curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8088/api/users")
    print(out, err)

    print("=== 7. 验证 ===")
    out, err = run_ssh("curl -s http://127.0.0.1:8088/api/macro/calendar | python3 -c 'import sys,json; d=json.load(sys.stdin); print(\"Events:\", len(d[\"events\"]), \"Source:\", d[\"source\"])'")
    print(out, err)

    print("=== 部署完成 ===")
    print(f"访问: http://{HOST}:8088/static/index.html")

if __name__ == "__main__":
    main()
