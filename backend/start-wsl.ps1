# 在 WSL(Ubuntu) 里启动 Django 后端 (daphne)。
# 原因：批量执行依赖 ansible，而 ansible 控制端无法在原生 Windows 运行，故后端跑在 WSL。
# venv 位于 WSL 家目录 ~/venv-opstool（避开 /mnt/c 的 9p 慢速）；代码与 db.sqlite3 仍在 Windows 原地。
# 用法：在本文件所在目录执行  ./start-wsl.ps1   （保持该窗口开启，关闭即停止服务）

# 关键：把 venv 的 bin 加入 PATH，否则 ansible-runner 找不到 ansible-playbook，
# 批量执行会报 "No result returned by Ansible"（子进程 RC 127）。
wsl.exe -e bash -lc "export PATH=~/venv-opstool/bin:`$PATH; cd /mnt/c/Users/kaikai/Desktop/django-vue/backend && exec ~/venv-opstool/bin/python -m daphne -b 0.0.0.0 -p 8001 ops_tool.asgi:application"
