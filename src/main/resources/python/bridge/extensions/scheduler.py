"""Scheduler extension — cron-like real-world-time scheduling with named tasks."""
from __future__ import annotations

import asyncio
import inspect
import time
from typing import Any, Callable, Dict, List, Optional

class ScheduledTask:
    """A single scheduled task.

    Args:
        name: Task identifier.
        handler: Async or sync callable to run.
        interval: Seconds between executions (0 = one-shot).
        delay: Initial delay in seconds before first run.
        repeat: Whether to repeat. Default True for interval tasks.
    """
    __slots__ = ("name", "handler", "interval", "delay", "repeat",
                 "_cancelled", "_task", "_run_count", "_last_run")

    def __init__(self, name: str, handler: Callable[..., Any],
            interval: float = 0, delay: float = 0,
            repeat: bool = True) -> None:
        """Initialise a new ScheduledTask."""
        self.name = name
        self.handler = handler
        self.interval = interval
        self.delay = delay
        self.repeat = repeat if interval > 0 else False
        self._cancelled = False
        self._task: Optional[asyncio.Task] = None
        self._run_count = 0
        self._last_run: Optional[float] = None

    @property
    def cancelled(self) -> bool:
        """The cancelled value."""
        return self._cancelled

    @property
    def run_count(self) -> int:
        """The run count value."""
        return self._run_count

    @property
    def last_run(self) -> Optional[float]:
        """Timestamp of last execution, or None."""
        return self._last_run

    def cancel(self) -> None:
        """Cancel this task."""
        self._cancelled = True
        if self._task:
            self._task.cancel()
            self._task = None

    async def _execute(self) -> None:
        """Execute the handler."""
        try:
            r = self.handler()
            if inspect.isawaitable(r):
                await r

            self._run_count += 1
            self._last_run = time.time()
        except Exception:
            pass

class Scheduler:
    """Cron-like scheduler with named tasks and real-world-time intervals.

    Example::
        sched = Scheduler()

        @sched.every(60, name="announce")
        async def announce():
            await bridge.server.broadcast("&6Remember to vote!")

        @sched.after(10, name="welcome")
        async def welcome():
            await bridge.server.broadcast("&aServer started 10 seconds ago!")

        # Cancel a task
        sched.cancel("announce")

        # Start all tasks
        sched.start()
    """
    __slots__ = ("_tasks", "_running")

    def __init__(self) -> None:
        """Initialise a new Scheduler."""
        self._tasks: Dict[str, ScheduledTask] = {}
        self._running = False

    @property
    def tasks(self) -> Dict[str, ScheduledTask]:
        """The tasks value."""
        return dict(self._tasks)

    def every(self, seconds: float, name: Optional[str] = None,
            delay: float = 0) -> Any:
        """Decorator: schedule a function to run every *seconds* seconds.

        Args:
            seconds: Interval between executions.
            name: Task name. Defaults to function name.
            delay: Initial delay before first execution.
        """
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            """Register as a decorator."""
            task_name = name or func.__name__
            task = ScheduledTask(task_name, func, interval=seconds,
                delay=delay, repeat=True)

            self._tasks[task_name] = task
            if self._running:
                self._launch(task)

            return func

        return decorator

    def after(self, seconds: float, name: Optional[str] = None) -> Any:
        """Decorator: schedule a function to run once after *seconds* seconds.

        Args:
            seconds: Delay before execution.
            name: Task name. Defaults to function name.
        """
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            """Register as a decorator."""
            task_name = name or func.__name__
            task = ScheduledTask(task_name, func, interval=0,
                delay=seconds, repeat=False)

            self._tasks[task_name] = task
            if self._running:
                self._launch(task)

            return func

        return decorator

    def schedule(self, name: str, handler: Callable[..., Any],
            interval: float = 0, delay: float = 0,
            repeat: bool = True) -> Any:
        """Imperatively schedule a task.

        Args:
            name: Task identifier.
            handler: Callable to run.
            interval: Seconds between runs (0 = one-shot).
            delay: Initial delay in seconds.
            repeat: Whether to repeat.
        """
        task = ScheduledTask(name, handler, interval=interval,
            delay=delay, repeat=repeat)

        self._tasks[name] = task
        if self._running:
            self._launch(task)

        return task

    def cancel(self, name: str) -> None:
        """Cancel a named task."""
        task = self._tasks.pop(name, None)
        if task:
            task.cancel()

    def cancel_all(self) -> None:
        """Cancel all tasks."""
        for task in self._tasks.values():
            task.cancel()

        self._tasks.clear()

    def _launch(self, task: ScheduledTask) -> None:
        """Launch a task's async loop."""
        async def _run() -> None:
            """Asynchronously handle run."""
            if task.delay > 0:
                await asyncio.sleep(task.delay)

            if task.cancelled:
                return

            await task._execute()
            while task.repeat and not task.cancelled and task.interval > 0:
                await asyncio.sleep(task.interval)
                if task.cancelled:
                    break

                await task._execute()

        task._task = asyncio.ensure_future(_run())

    def start(self) -> None:
        """Start all registered tasks."""
        self._running = True
        for task in self._tasks.values():
            if not task.cancelled and task._task is None:
                self._launch(task)

    def stop(self) -> None:
        """Stop all tasks."""
        self._running = False
        for task in self._tasks.values():
            task.cancel()
