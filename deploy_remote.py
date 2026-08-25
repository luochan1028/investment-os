"""在远程服务器上修复并重启"""
import paramiko

HOST = "159.138.92.82"
USER = "root"
PASSWORD = "zdmy3n14F"

def run_ssh(cmd):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=120)
    out = stdout.read().decode()
    err = stderr.read().decode()
    ssh.close()
    return out, err

# 1. 直接修复远程 server.py 中的 random 问题
print("=== 1. 修复 random 导入 ===")
out, err = run_ssh("cd /opt/investment-os && sed -i \"s/random.randint(1, 48)/__import__('random').randint(1, 48)/g\" server.py && grep -n 'random' server.py | head -5")
print(out, err)

# 2. 停止旧进程
print("=== 2. 停止旧进程 ===")
out, err = run_ssh("pkill -f 'python3.*server.py' 2>/dev/null; sleep 1; echo 'done'")
print(out, err)

# 3. 启动服务
print("=== 3. 启动服务 ===")
out, err = run_ssh("cd /opt/investment-os && nohup python3 server.py > /tmp/investment-os.log 2>&1 & sleep 5 && curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8088/api/users")
print("HTTP:", out)

# 4. 检查日志
print("=== 4. 日志 ===")
out, err = run_ssh("tail -15 /tmp/investment-os.log")
print(out)

# 5. 验证
print("=== 5. 验证 ===")
out, err = run_ssh("curl -s http://127.0.0.1:8088/api/macro/calendar | python3 -c 'import sys,json; d=json.load(sys.stdin); print(\"Events:\", len(d[\"events\"]), \"Source:\", d[\"source\"])' 2>&1")
print(out)

out, err = run_ssh("curl -s http://127.0.0.1:8088/api/crisis/figures/actions | python3 -c 'import sys,json; d=json.load(sys.stdin); print(\"Figure actions:\", d[\"total\"])' 2>&1")
print(out)

print("=== 部署完成 ===")
print(f"访问: http://{HOST}:8088/static/index.html")
