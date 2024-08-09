import asyncio
import sys
import uuid
from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio.workflow import ParentClosePolicy

from messages import EmployeeLocationDetailsResponse, SetCurrentLocationRequest, StartLocationServicesRequest, \
    EmployeeNotificationsResponse, RescheduleNotificationsRequest, StartEmployeeNotificationsRequest, \
    EmployeeDetailsResponse, OnboardEmployeeRequest, SendDigestRequest, UpdateEmployeeDetailsRequest
from notifications import NotificationHandlers


@workflow.defn
class EmployeeLocations:
    def __init__(self) -> None:
        self.state: EmployeeLocationDetailsResponse = EmployeeLocationDetailsResponse(
            employee_id='',
            location='',
            timezone='',
            location_id='')

    @workflow.signal
    async def set_current_location(self, params: SetCurrentLocationRequest):
        self.state = EmployeeLocationDetailsResponse(
            self.state.employee_id,
            params.location,
            params.timezone,
            workflow.info().workflow_id)

    @workflow.run
    async def execute(self, params: StartLocationServicesRequest):
        self.state = EmployeeLocationDetailsResponse(
            self.state.employee_id,
            params.location,
            params.timezone,
            workflow.info().workflow_id)
        await workflow.wait_condition(lambda: False)
        # periodically sync this location / tz with downstream services here.
        # this could take similar approach to the EmployeeNotifications service with a periodic task to perform



@workflow.defn
class EmployeeNotifications:
    def __init__(self) -> None:
        self.state: EmployeeNotificationsResponse = EmployeeNotificationsResponse(
            employee_id='',
            frequency='',
            paused=False,
            next_digest_send_n_seconds=0
        )
        self.schedule_change = None

    @workflow.query
    def get_notifications_state(self):
        return self.state

    @workflow.signal(name='reschedule_notifications')
    async def reschedule_notifications(self, params: RescheduleNotificationsRequest)->None:
        workflow.logger.debug("Executing reschedule notifications")
        self.state = EmployeeNotificationsResponse(self.state.employee_id,
                                                   frequency=params.frequency,
                                                   paused=params.paused,
                                                   next_digest_send_n_seconds= self.state.next_digest_send_n_seconds)
        self.schedule_change = params

    @workflow.run
    async def execute(self, params: StartEmployeeNotificationsRequest) -> None:
        self.schedule_change = None
        self.state = EmployeeNotificationsResponse(
            params.employee_id,
            params.frequency,
            params.paused,
            next_digest_send_n_seconds=sys.float_info.max)
        if params.paused:
            await workflow.wait_condition(lambda: not self.state.paused)

        self.state.next_digest_send_n_seconds = await workflow.execute_local_activity_method(NotificationHandlers.calculate_next_digest_send_n_seconds,
                                                            params.frequency,
                                                            start_to_close_timeout=timedelta(seconds=3))

        # using a poor man's way to monitor for changes to our schedule change
        # inspect after-the-fact
        await workflow.wait_condition(lambda: self.schedule_change is not None, timeout=timedelta(seconds=self.state.next_digest_send_n_seconds))

        if self.schedule_change is not None:
            workflow.logger.info("schedule was changed. continuing as new")
            workflow.continue_as_new(StartEmployeeNotificationsRequest(
                employee_id=params.employee_id,
                frequency=self.state.frequency,
                paused = self.state.paused
            ))
        else:
            workflow.logger.info("sending digest notification")
            await workflow.execute_activity(NotificationHandlers.send_digest,
                                            SendDigestRequest(employee_id=self.state.employee_id),
                                            start_to_close_timeout=timedelta(seconds=120))
            # error handling skipped for brevity
            workflow.continue_as_new(
                StartEmployeeNotificationsRequest(params.employee_id,
                                                  frequency=self.state.frequency,
                                                  paused=self.state.paused))

@workflow.defn
class Employee:
    def __init__(self) -> None:
        self.offboarded: bool = False
        self.state: EmployeeDetailsResponse = EmployeeDetailsResponse(id='',
                                                                      first_name='',
                                                                      last_name='', default_location='',
                                                                      default_timezone='',
                                                                      locations_id='',
                                                                      notifications_id='')

    @workflow.query
    async def get_employee_details(self) -> EmployeeDetailsResponse:
        return self.state

    @workflow.signal
    async def update_employee_details(self, params: UpdateEmployeeDetailsRequest):
        self.state.first_name = params.first_name
        self.state.last_name = params.last_name

    @workflow.signal
    async def offboard(self):
        self.offboarded = True

    @workflow.run
    async def execute(self, params: OnboardEmployeeRequest):

        self.state = EmployeeDetailsResponse(params.id,
                                             params.first_name,
                                             params.last_name,
                                             params.default_location,
                                             params.default_timezone,
                                             f"locations_{params.id}",
                                             f"notifications_{params.id}"
                                             )

        notifications = asyncio.create_task(workflow.execute_child_workflow(
            EmployeeNotifications.execute,
            StartEmployeeNotificationsRequest(params.id, 'DAILY', paused=False),
            id=self.state.notifications_id,
            parent_close_policy=ParentClosePolicy.REQUEST_CANCEL,
        ))

        locations = asyncio.create_task(workflow.execute_child_workflow(
            EmployeeLocations.execute,
            args=[StartLocationServicesRequest(params.id, params.default_location, params.default_timezone)],
            id=self.state.locations_id,
            parent_close_policy=ParentClosePolicy.REQUEST_CANCEL,
        ))

        await workflow.wait_condition(lambda: self.offboarded)
        await locations
        await notifications


async def main():
    # Start client
    client = await Client.connect("localhost:7233")
    notifications = NotificationHandlers()

    # Run a worker for the workflow
    handle =  Worker(
            client,
            task_queue="app",
            workflows=[Employee, EmployeeNotifications, EmployeeLocations],
            activities=[notifications.calculate_next_digest_send_n_seconds, notifications.send_digest],
    )
    await handle.run()

if __name__ == "__main__":
    asyncio.run(main())
