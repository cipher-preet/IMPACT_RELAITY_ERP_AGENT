import asyncio

from apps.agent_runtime.agents.executor.task_executor import TaskExecutor


class ParallelExecutor:

    def __init__(self):

        self.task_executor = TaskExecutor()

    async def execute_tasks(self, tasks, state):

        coroutines = [self.task_executor.execute(task, state) for task in tasks]

        return await asyncio.gather(*coroutines, return_exceptions=True)
