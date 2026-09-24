import time
import structlog

# Configure JSON structured logging for production observability
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer()
    ]
)

logger = structlog.get_logger()

def trace_agent_execution(agent_name: str):
    """
    Decorator to log structured timing, status, and performance metrics
    for asynchronous multi-agent task execution.
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            logger.info("agent_execution_started", agent=agent_name)
            try:
                result = func(*args, **kwargs)
                duration = round(time.time() - start_time, 4)
                logger.info(
                    "agent_execution_completed",
                    agent=agent_name,
                    duration_seconds=duration,
                    status="SUCCESS"
                )
                return result
            except Exception as e:
                duration = round(time.time() - start_time, 4)
                logger.error(
                    "agent_execution_failed",
                    agent=agent_name,
                    duration_seconds=duration,
                    error=str(e),
                    status="FAILED"
                )
                raise e
        return wrapper
    return decorator