# SelfLore API

启动本地健康检查服务：

```powershell
uv run uvicorn app.main:app --host 127.0.0.1 --port 24566
```

健康检查地址：`http://127.0.0.1:24566/api/health`。
