import structlog
import logging
import uuid

from .settings import settings


def add_trace_id(logger, method_name, event_dict):
    request = event_dict.pop("request", None)
    if request:
        trace_id = getattr(request.state, "trace_id", None)
        if trace_id:
            event_dict["trace_id"] = trace_id
    if "trace_id" not in event_dict:
        event_dict["trace_id"] = uuid.uuid4().hex[:16]
    return event_dict


def setup_logging():
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            add_trace_id,
            structlog.dev.ConsoleRenderer()
            if settings.log_level == "debug"
            else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
    )
