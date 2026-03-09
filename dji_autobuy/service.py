from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from threading import Event, Lock, Thread
from typing import Callable

from .models import Account, JobConfig, WorkerResult
from .worker import run_worker

ResultFn = Callable[[WorkerResult], None]
DoneFn = Callable[[], None]


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

    def stop(self) -> None:
        self._stop_event.set()
