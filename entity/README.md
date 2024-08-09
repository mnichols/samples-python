# entity

This sample demonstrates an `employee` entity (aka durable object) that has a lifecycle in different contexts.

## The Domain

Our Domain has three different bounded contexts:
1. Personnel : Bookkeeping information and employment status for each Employee. 
   1. This acts as the entrypoint for an Employee (Onboarding)
2. Locations: Employee sync operations with scheduling systems for workplace
3. Notifications: Employee work digest publication behaviors 

## Run It

From the root of the repository:

_Onboard the Employee_
`temporal workflow start --workflow-id ee_id --task-queue app --type Employee --input-file entity/ee.json`

_Query Employee Details And Related Entities in other contexts_
`temporal workflow query --workflow-id ee_id --name get_employee_details`

_Reschedule Employee Notifications Digest To Be Paused_
`temporal workflow signal --workflow-id ee_id --name reschedule_notifications --input '{"frequency":"DAILY", "paused":true}'` 

_Reschedule Employee Notifications Digest To Resume_
`temporal workflow signal --workflow-id ee_id --name reschedule_notifications --input '{"frequency":"MONDAY", "paused":false}'` 

