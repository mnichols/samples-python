import asyncio
import uuid
from dataclasses import dataclass
from enum import Enum

from temporalio import workflow
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio.workflow import ParentClosePolicy


@dataclass
class OnboardEmployeeRequest:
    id: str
    first_name: str
    last_name: str
    default_location: str
    default_timezone: str

@dataclass
class EmployeeDetailsResponse:
    id: str
    first_name: str
    last_name: str
    default_location: str
    default_timezone: str
    locations_id: str
    notifications_id: str

@dataclass
class StartLocationServicesRequest:
    employee_id: str
    location: str
    timezone: str

@dataclass
class SetCurrentLocationRequest:
    location: str
    timezone: str

@dataclass
class EmployeeLocationDetails:
    employee_id: str
    location: str
    timezone: str
    location_id: str

class NotificationFrequency(Enum):
    NEVER = 0
    DAILY = 1
    MONDAY = 2
    FRIDAY = 3

@dataclass
class StartEmployeeNotifications:
    employee_id: str
    frequency: NotificationFrequency


@workflow.defn
class EmployeeLocations:
    def __init__(self) -> None:
        self.state: EmployeeLocationDetails = EmployeeLocationDetails(
            employee_id='',
            location='',
            timezone='',
            location_id='')

    @workflow.signal
    async def set_current_location(self, params: SetCurrentLocationRequest):
        self.state = EmployeeLocationDetails(
            self.state.employee_id,
            params.location,
            params.timezone,
            workflow.info().workflow_id )

    @workflow.run
    async def execute(self, params: StartLocationServicesRequest):
        self.state = EmployeeLocationDetails(
            self.state.employee_id,
            params.location,
            params.timezone,
            workflow.info().workflow_id)
        await workflow.wait_condition(lambda : False)


@workflow.defn
class EmployeeNotifications:
    def __init__(self) -> None:
        pass
    
    @workflow.run
    async def execute(self, params: StartEmployeeNotifications):
        await workflow.wait_condition(lambda : False)

@workflow.defn
class Employee:
    def __init__(self) -> None:
        self.offboarded : bool = False
        self.state : EmployeeDetailsResponse = EmployeeDetailsResponse(id='',
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

        locations = asyncio.create_task(workflow.execute_child_workflow(
            EmployeeLocations.execute,
            args=[StartLocationServicesRequest(params.id, params.default_location, params.default_timezone)],
            id=self.state.locations_id,
            parent_close_policy=ParentClosePolicy.REQUEST_CANCEL,
        ))
        notifications = asyncio.create_task(workflow.execute_child_workflow(
            EmployeeNotifications.execute,
            args=[StartEmployeeNotifications(params.id, NotificationFrequency.DAILY)],
            id=self.state.notifications_id,
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
