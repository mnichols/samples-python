from temporalio import activity
from temporalio.exceptions import ApplicationError

from messages import SendDigestRequest


class NotificationHandlers:
    def __init__(self) -> None:
        pass

    @activity.defn
    async def calculate_next_digest_send_n_seconds(self, frequency: str) -> float:
        if frequency == 'DAILY':
            return 86400
        if frequency == 'MONDAY':
            # algorithm for delta seconds until next monday
            # here i am just stubbing a number
            return 86400 * 7
        if frequency == 'FRIDAY':
            return 86400 * 14
        raise ApplicationError('Invalid frequency')

    @activity.defn
    async def send_digest(self, cmd: SendDigestRequest):
        activity.logger.info(f"Sending digest to {cmd.employee_id}")
