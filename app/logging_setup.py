"""日志配置：日志文件位于项目内的 data/logs。"""

from __future__ import annotations

import logging
import sys

from . import clock
from . import paths


def setup_logging(level: int = logging.INFO) -> None:
    paths.ensure_directories()
    root = logging.getLogger()
    root.setLevel(level)
    if any(isinstance(handler, logging.FileHandler) for handler in root.handlers):
        return

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # 日志时间也用北京时间（logging 默认按系统本地时区格式化）
    formatter.converter = lambda *args: clock.now().timetuple()
    file_handler = logging.FileHandler(paths.LOG_PATH, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    # 启动方式为 .pyw 时没有控制台，stderr 可能为 None。
    if sys.stderr is not None and sys.stderr.isatty():
        stream_handler = logging.StreamHandler(sys.stderr)
        stream_handler.setFormatter(formatter)
        root.addHandler(stream_handler)

    logging.getLogger(__name__).info("日志系统就绪：%s", paths.LOG_PATH)
