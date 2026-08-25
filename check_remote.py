"""检查远程服务状态"""
import paramiko

HOST = "159.138.92.82"
USER = "root"
PASSWORD = "zdmy3n14F"

def run_ssh(cmd):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=60)
    out = stdout.read().decode()
    err = stderr.read().decode()
    ssh.close()
    return out, err

# 检查日志
out, err = run_ssh("tail -30 /tmp/investment-os.log")
print("=== 日志 ===")
print(out)
print(err)

# 检查进程
out, err = run_ssh("ps aux | grep server.py | grep -v grep")
print("\n=== 进程 ===")
print(out)

# 检查端口
out, err = run_ssh("curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8088/api/users")
print("\n=== HTTP状态 ===")
print(out)
