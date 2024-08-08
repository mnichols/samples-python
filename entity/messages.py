from dataclasses import dataclass


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
class EmployeeLocationDetailsResponse:
    employee_id: str
    location: str
    timezone: str
    location_id: str


NotificationFrequency = Enum('NotificationFrequency', ['NEVER', 'DAILY', 'MONDAY', 'FRIDAY'])


@dataclass
class StartEmployeeNotificationsRequest:
    employee_id: str
    frequency: str
    paused: bool

@dataclass
class RescheduleNotificationsRequest:
    frequency: str
    paused: bool

@dataclass
class EmployeeNotificationsResponse:
    employee_id: str
    frequency: str
    paused: bool
    next_digest_send_n_seconds: float

@dataclass
class SendDigestRequest:
    employee_id: str