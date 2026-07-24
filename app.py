"""Точка входа для remote-деплоя (FastMCP Cloud, mcphosting, VPS).

Локальный запуск через stdio не затрагивается — он живёт в __main__.py.
Здесь объект создаётся на уровне модуля, потому что облачные платформы
ищут инстанс FastMCP по пути вида ``app.py:mcp``.

Локальная проверка HTTP-режима:
    .venv/bin/python app.py
    -> сервер поднимется на http://0.0.0.0:8000/mcp

Ключи Ozon в облаке задаются переменными окружения на стороне хостинга,
в репозиторий они не попадают (см. .gitignore).
"""

from __future__ import annotations

import os

from ozon_mcp.server import create_server

mcp = create_server()


if __name__ == "__main__":
    mcp.run(
        transport="http",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
    )
