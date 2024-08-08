# entity

This sample demonstrates an `employee` entity (aka durable object) that has a lifecycle in different contexts.

## The Domain

Our Domain has three different bounded contexts:
1. Personnel : Bookkeeping information and employment status for each Employee. 
   1. This acts as the entrypoint for an Employee (Onboarding)
2. Locations: Employee sync operations with scheduling systems for workplace
3. Notifications: Employee work digest publication behaviors 