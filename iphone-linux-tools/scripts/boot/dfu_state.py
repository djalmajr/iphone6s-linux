"""Track observable DFU progress without treating an exploit timeout as success."""


def process_output(state, clean):
    previous = state["log"][-100:]
    combined = previous + clean
    state["log"] = (state["log"] + clean)[-12000:]
    if state["phase"] == "failed":
        return

    def appeared(message):
        position = combined.rfind(message)
        return position >= 0 and position + len(message) > len(previous)

    if appeared("Press Enter when ready for DFU mode"):
        state.update(ready=True, phase="ready")
    if appeared("DFU mode successfully") or appeared("Device entered DFU"):
        state.update(ready=False, phase="dfu")
    if appeared("Booting pongoOS") or appeared("Booting PongoOS"):
        state.update(ready=False, phase="pongo")
    failures = ("device did not enter DFU mode", "Timed out waiting for download mode", "Exploit failed")
    if any(appeared(message) for message in failures):
        state.update(ready=False, phase="failed")


def finish_output(state):
    state["ready"] = False
    if state["phase"] not in ("dfu", "pongo", "failed"):
        state["phase"] = "failed"
