import asyncio
import uuid
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum

from temporalio import workflow, activity
from temporalio.client import Client
from temporalio.exceptions import ApplicationError
from temporalio.worker import Worker
from temporalio.workflow import ParentClosePolicy

from entity.messages import EmployeeLocationDetailsResponse, SetCurrentLocationRequest, StartLocationServicesRequest, \
    EmployeeNotificationsResponse, RescheduleNotificationsRequest, StartEmployeeNotificationsRequest, \
    EmployeeDetailsResponse, OnboardEmployeeRequest
from entity.notifications import NotificationHandlers


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

    @workflow.signal
    async def reschedule_notifications(self, params: RescheduleNotificationsRequest):
        self.state = EmployeeNotificationsResponse(self.state.employee_id,
                                                   frequency=params.frequency,
                                                   paused=params.paused,
                                                   next_digest_send_n_seconds= self.state.next_digest_send_n_seconds)

    @workflow.run
    async def execute(self, params: StartEmployeeNotificationsRequest):
        secs = await workflow.execute_local_activity_method(NotificationHandlers.calculate_next_digest_send_n_seconds,
                                                            params.frequency,
                                                            start_to_close_timeout=timedelta(seconds=3))
        self.state = EmployeeNotificationsResponse(
            params.employee_id,
            params.frequency,
            params.paused,
            next_digest_send_n_seconds=secs)

        await workflow.wait_condition(lambda: not self.state.paused, timeout=self.state.next_digest_send_n_seconds)
        if self.state.paused:
            return workflow.continue_as_new(
                StartEmployeeNotificationsRequest(params.employee_id, frequency=self.state.frequency, paused=True))
        await workflow.execute_activity(NotificationHandlers.send_digest, self.state.employee_id, start_to_close_timeout=timedelta(seconds=120))
        # error handling skipped for brevity
        return workflow.continue_as_new(
            StartEmployeeNotificationsRequest(params.employee_id, frequency=self.state.frequency, paused=self.state.paused))

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
            StartEmployeeNotificationsRequest(params.id, 'DAILY'),
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

    # Run a worker for the workflow
    async with Worker(
            client,
            task_queue="app",
            workflows=[Employee, EmployeeNotifications, EmployeeLocations],
    ):
        ee_id = f"ee_{str(uuid.uuid4())}"
        # While the worker is running, use the client to run the workflow and
        # print out its result. Note, in many production setups, the client
        # would be in a completely separate process from the worker.
        result = await client.execute_workflow(
            Employee.execute,
            arg=OnboardEmployeeRequest(
                id=ee_id,
                first_name='Mikey',
                last_name='Nichols',
                default_location='North Carolina',
                default_timezone='EST'),
            id=ee_id,
            task_queue="app",
        )
        result.close()
        print(f"Result: {result}")


if __name__ == "__main__":
    asyncio.run(main())
