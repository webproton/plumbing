import logging

from kombu.exceptions import OperationalError

logger = logging.getLogger(__name__)


class QueueUnavailable(Exception):
    pass


def enqueue(task, *args, run_inline_on_failure=False, **kwargs):
    """
    Ставит задачу Celery в очередь. Если брокер (Redis) недоступен:
    run_inline_on_failure=True — выполняет сразу (лёгкие задачи вроде уведомлений),
    иначе — QueueUnavailable (вызывающий код отвечает пользователю «попробуйте позже»).
    """
    try:
        return task.delay(*args, **kwargs)
    except OperationalError:
        logger.exception("Очередь задач недоступна (%s)", task.name)
        if run_inline_on_failure:
            return task.apply(args=args, kwargs=kwargs)
        raise QueueUnavailable from None
