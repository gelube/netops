#!/usr/bin/env python3
"""
结构化日志模块 — 替代散落的 print() 调用

用法：
    from app.logger import get_logger
    log = get_logger(__name__)
    log.info("设备连接成功", device="SW-Core", vendor="huawei")
    log.warning("命令被拦截", command="erase flash", reason="CRITICAL")
    log.error("SSH连接失败", device="SW-Core", error=str(e))
"""
import logging
import json
import sys
import os
from datetime import datetime


class StructuredFormatter(logging.Formatter):
    """结构化日志格式器"""

    def format(self, record):
        # 基础信息
        log_entry = {
            "ts": datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "level": record.levelname,
            "module": record.name,
            "msg": record.getMessage(),
        }

        # 附加结构化字段
        if hasattr(record, "struct_data"):
            log_entry.update(record.struct_data)

        # 开发模式：彩色可读格式
        if os.environ.get("NETOPS_LOG_FORMAT", "text") == "json":
            return json.dumps(log_entry, ensure_ascii=False)

        # 文本格式：更易读
        level_colors = {
            "DEBUG": "\033[36m",    # cyan
            "INFO": "\033[32m",     # green
            "WARNING": "\033[33m",  # yellow
            "ERROR": "\033[31m",    # red
            "CRITICAL": "\033[35m", # magenta
        }
        color = level_colors.get(record.levelname, "")
        reset = "\033[0m"

        extra = ""
        if hasattr(record, "struct_data") and record.struct_data:
            parts = [f"{k}={v}" for k, v in record.struct_data.items()]
            extra = " | " + " ".join(parts)

        return f"{log_entry['ts']} {color}{record.levelname:8}{reset} {record.name}: {record.getMessage()}{extra}"


class StructuredLogger(logging.Logger):
    """支持结构化字段的标准 Logger"""

    def _log_struct(self, level, msg, **kwargs):
        """带结构化字段的日志"""
        super().log(level, msg, extra={"struct_data": kwargs})

    def info(self, msg, *args, **kwargs):
        if kwargs:
            self._log_struct(logging.INFO, msg, **kwargs)
        else:
            super().info(msg, *args)

    def warning(self, msg, *args, **kwargs):
        if kwargs:
            self._log_struct(logging.WARNING, msg, **kwargs)
        else:
            super().warning(msg, *args)

    def error(self, msg, *args, **kwargs):
        if kwargs:
            self._log_struct(logging.ERROR, msg, **kwargs)
        else:
            super().error(msg, *args)

    def debug(self, msg, *args, **kwargs):
        if kwargs:
            self._log_struct(logging.DEBUG, msg, **kwargs)
        else:
            super().debug(msg, *args)

    def critical(self, msg, *args, **kwargs):
        if kwargs:
            self._log_struct(logging.CRITICAL, msg, **kwargs)
        else:
            super().critical(msg, *args)


# 注册自定义 Logger 类
logging.setLoggerClass(StructuredLogger)

# 默认 handler
_handler = logging.StreamHandler(sys.stderr)
_handler.setFormatter(StructuredFormatter())

# 默认级别（可通过环境变量覆盖）
_default_level = os.environ.get("NETOPS_LOG_LEVEL", "INFO").upper()


def get_logger(name: str) -> StructuredLogger:
    """获取结构化 Logger"""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.addHandler(_handler)
    logger.setLevel(getattr(logging, _default_level, logging.INFO))
    return logger
