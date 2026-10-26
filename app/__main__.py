import uvicorn

from .config import settings

if __name__ == "__main__":  # python -m app
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.port, proxy_headers=True, forwarded_allow_ips="*")
