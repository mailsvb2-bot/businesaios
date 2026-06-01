from __future__ import annotations

"""Evolution worker: poll durable outbox and execute jobs.

Hard invariants:
- No Telegram side-effects (no outbound messages).
- Writes only to durable stores (event_store / outbox state).
- Never crashes the process on a single bad job.
"""

import logging
import time
from dataclasses import dataclass

from runtime.evolution import EvolutionOutbox, handle_evolution_job
from runtime.observability.error_handling import swallow
from runtime.platform.config.env_flags import env_bool, env_int

log = logging.getLogger("runtime.evolution.worker")


@dataclass
class EvolutionWorkerState:
    ok: bool = True
    last_tick_ms: int = 0
    last_ok_ms: int = 0
    last_error: str = ""
    processed_total: int = 0
    processed_last_tick: int = 0
    pending: int = 0


class EvolutionWorker:
    def __init__(
        self,
        *,
        outbox: EvolutionOutbox,
        poll_interval_sec: int = 2,
        batch_size: int = 10,
        max_runtime_sec: int = 0,
    ):
        self._outbox = outbox
        self._poll_s = max(1, int(poll_interval_sec))
        self._batch = max(1, int(batch_size))
        self._max_runtime = max(0, int(max_runtime_sec))
        self._state = EvolutionWorkerState()

    @property
    def state(self) -> EvolutionWorkerState:
        return self._state

    def _now_ms(self) -> int:
        return int(time.time() * 1000)

    def tick_once(self) -> int:
        """Process up to batch_size pending jobs. Returns processed count."""
        st = self._state
        st.ok = True
        st.last_error = ""
        st.last_tick_ms = self._now_ms()
        st.processed_last_tick = 0

        try:
            items = self._outbox.list_pending(limit=int(self._batch))
        except Exception as e:
            st.ok = False
            st.last_error = f"list_pending:{type(e).__name__}"
            return 0

        processed = 0
        for job in items or []:
            jid = str(getattr(job, "job_id", "") or "")
            if not jid:
                continue
            try:
                handle_evolution_job(job)
                try:
                    self._outbox.mark_done(jid)
                except Exception:
                    swallow(__name__, 'runtime/evolution/worker.py')
                processed += 1
            except Exception as e:
                try:
                    self._outbox.mark_failed(jid, error=f"{type(e).__name__}:{str(e)[:200]}")
                except Exception:
                    swallow(__name__, 'runtime/evolution/worker.py')
                st.ok = False
                st.last_error = f"job_failed:{type(e).__name__}"

        st.processed_last_tick = int(processed)
        st.processed_total += int(processed)
        if processed > 0:
            st.last_ok_ms = self._now_ms()

        try:
            st.pending = int(self._outbox.count_pending())
        except Exception:
            swallow(__name__, 'runtime/evolution/worker.py')

        return int(processed)

    def run_forever(self) -> None:
        """Main loop. If max_runtime_sec>0, stops after the duration (useful for tests/watchdogs)."""
        st = self._state
        start_ms = self._now_ms()
        st.last_ok_ms = start_ms

        while True:
            if self._max_runtime > 0 and (self._now_ms() - start_ms) > int(self._max_runtime) * 1000:
                log.info("evolution_worker_soft_stop max_runtime_sec=%s", self._max_runtime)
                return

            try:
                n = self.tick_once()
            except Exception as e:
                st.ok = False
                st.last_error = f"tick_once:{type(e).__name__}"
                n = 0

            time.sleep(0.1 if n > 0 else float(self._poll_s))


def build_worker_from_env() -> EvolutionWorker:
    poll_s = env_int("EVOLUTION_POLL_INTERVAL_SEC", 2, lo=1, hi=60)
    batch = env_int("EVOLUTION_BATCH_SIZE", 10, lo=1, hi=10_000)
    max_rt = env_int("EVOLUTION_MAX_RUNTIME_SEC", 0, lo=0, hi=24 * 3600)

    return EvolutionWorker(
        outbox=EvolutionOutbox.from_env(),
        poll_interval_sec=int(poll_s),
        batch_size=int(batch),
        max_runtime_sec=int(max_rt),
    )


def evolution_enabled() -> bool:
    return env_bool("EVOLUTION_ENABLED", True)
