import asyncio
import uuid
from datetime import timedelta
from typing import List

from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.worker import Worker


@activity.defn
async def say_hello_activity(name: str) -> str:
    return f"Hello, {name}!"



@workflow.defn
class SayHelloWorkflow:

    async def delayHello(self, name: str, timeout: float):
        await asyncio.sleep(timeout)
        return await workflow.execute_activity(say_hello_activity, f"{name}. It took me {timeout} secs to speak",
                                 start_to_close_timeout=timedelta(seconds=5))
    @workflow.run
    async def run(self) -> List[str]:
        # Run 5 activities at the same time
        results = await asyncio.gather(
            self.delayHello("user1", timeout=1),
            self.delayHello("user2", timeout=6),
            self.delayHello("user3", timeout=3),
            self.delayHello("user4", timeout=5)
        )

        # Sort the results because they can complete in any order
        return list(results)


async def main():
    # Start client
    client = await Client.connect("localhost:7233")

    # Run a worker for the workflow
    async with Worker(
        client,
        task_queue="hello-parallel-activity-task-queue",
        workflows=[SayHelloWorkflow],
        activities=[say_hello_activity],
    ):

        # While the worker is running, use the client to run the workflow and
        # print out its result. Note, in many production setups, the client
        # would be in a completely separate process from the worker.
        result = await client.execute_workflow(
            SayHelloWorkflow.run,
            id=str(uuid.uuid4()),
            task_queue="hello-parallel-activity-task-queue",
        )
        print(f"Result: {result}")


if __name__ == "__main__":
    asyncio.run(main())
