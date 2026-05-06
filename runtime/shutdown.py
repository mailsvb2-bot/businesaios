from runtime.runtime_state import RuntimeState


class Shutdown:
    def stop(self, state: RuntimeState) -> None:
        state.shutting_down = True
        state.ready = False
