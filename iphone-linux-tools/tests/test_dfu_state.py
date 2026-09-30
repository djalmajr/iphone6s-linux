import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from dfu_state import finish_output, process_output


class DfuProgressTests(unittest.TestCase):
    def state(self):
        return {"ready": False, "phase": "starting", "log": ""}

    def test_timeout_after_checkmate_is_terminal_failure(self):
        # Mutation detected: removing the download-mode timeout marker.
        state = self.state()
        process_output(state, "Device entered DFU\nCheckmate!\n")
        process_output(state, "Timed out waiting for download mode (error code)")
        self.assertEqual(state["phase"], "failed")
        process_output(state, "Press Enter when ready for DFU mode")
        self.assertFalse(state["ready"])
        self.assertEqual(state["phase"], "failed")

    def test_error_split_across_reads_is_detected(self):
        state = self.state()
        process_output(state, "Device entered DFU\nTimed out waiting for down")
        process_output(state, "load mode\n")
        self.assertEqual(state["phase"], "failed")

    def test_pongo_success_is_preserved_on_exit(self):
        state = self.state()
        process_output(state, "Device entered DFU\nBooting pongoOS\n")
        finish_output(state)
        self.assertEqual(state["phase"], "pongo")
        self.assertFalse(state["ready"])

    def test_exit_after_dfu_waits_for_usb_enumeration(self):
        state = self.state()
        process_output(state, "Device entered DFU\n")
        finish_output(state)
        self.assertEqual(state["phase"], "dfu")
        self.assertFalse(state["ready"])


if __name__ == "__main__":
    unittest.main()
