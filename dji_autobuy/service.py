from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from threading import Event, Lock, Thread
from typing import Callable

from .models import Account, JobConfig, WorkerResult
from .worker import run_worker

ResultFn = Callable[[WorkerResult], None]
DoneFn = Callable[[], None]
TaskFn = Callable[[str], None]


@dataclass
class TaskRunSpec:
    task_name: str
    accounts: list[Account]
    config: JobConfig


class AutobuyService:
    def __init__(self) -> None:
        self._stop_event = Event()
        self._running = False
        self._lock = Lock()

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._running

    def start(
        self,
        accounts: list[Account],
        config: JobConfig,
        log_fn: Callable[[str], None],
        result_fn: ResultFn,
        done_fn: DoneFn,
    ) -> bool:
        with self._lock:
            if self._running:
                return False
            self._running = True
            self._stop_event = Event()

        def run_all() -> None:
            try:
                with ThreadPoolExecutor(max_workers=config.max_workers) as pool:
                    futures: list[Future[WorkerResult]] = []
                    for account in accounts:
                        futures.append(
                            pool.submit(run_worker, account, config, log_fn, self._stop_event)
                        )
                    for future in futures:
                        result = future.result()
                        result_fn(result)
            finally:
                with self._lock:
                    self._running = False
                done_fn()

        Thread(target=run_all, daemon=True).start()
        return True

    def start_tasks(
        self,
        task_specs: list[TaskRunSpec],
        log_fn: Callable[[str], None],
        result_fn: ResultFn,
        task_event_fn: TaskFn,
        done_fn: DoneFn,
    ) -> bool:
        with self._lock:
            if self._running:
                return False
            self._running = True
            self._stop_event = Event()

        def run_all_tasks() -> None:
            try:
                for task_spec in task_specs:
                    if self._stop_event.is_set():
                        break
                    task_event_fn(f"start:{task_spec.task_name}")
                    with ThreadPoolExecutor(max_workers=task_spec.config.max_workers) as pool:
                        futures: list[Future[WorkerResult]] = []
                        for account in task_spec.accounts:
                            futures.append(
                                pool.submit(
                                    run_worker,
                                    account,
                                    task_spec.config,
                                    log_fn,
                                    self._stop_event,
                                )
                            )
                        for future in futures:
                            result = future.result()
                            result_fn(result)
                    task_event_fn(f"done:{task_spec.task_name}")
            finally:
                with self._lock:
                    self._running = False
                done_fn()

        Thread(target=run_all_tasks, daemon=True).start()
        return True

    def stop(self) -> None:
        self._stop_event.set()
