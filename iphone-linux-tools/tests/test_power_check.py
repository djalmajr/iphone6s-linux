import pathlib
import subprocess
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "phone/diagnostics/power-check.sh"


class PowerCheckTests(unittest.TestCase):
    def run_check(self, root):
        return subprocess.check_output(["sh", str(SCRIPT), str(root)], text=True)

    def test_missing_sensors_do_not_claim_charging(self):
        with tempfile.TemporaryDirectory() as folder:
            output = self.run_check(pathlib.Path(folder))
        self.assertIn("power_supply=unavailable\n", output)
        self.assertIn("thermal_zone=unavailable\n", output)
        self.assertIn("charging_validation=unverified\n", output)

    def test_reports_readings_without_certifying_charging(self):
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            battery = root / "class/power_supply/battery"
            thermal = root / "class/thermal/thermal_zone0"
            battery.mkdir(parents=True)
            thermal.mkdir(parents=True)
            (battery / "capacity").write_text("64\n")
            (battery / "status").write_text("Charging\n")
            (thermal / "temp").write_text("35000\n")
            output = self.run_check(root)
        self.assertIn("capacity=64\n", output)
        self.assertIn("status=Charging\n", output)
        self.assertIn("temp=35000\n", output)
        self.assertIn("charging_validation=unverified\n", output)

    def test_empty_and_non_file_readings_are_unavailable(self):
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            battery = root / "class/power_supply/battery"
            battery.mkdir(parents=True)
            (battery / "capacity").write_text("")
            (battery / "status").mkdir()
            output = self.run_check(root)
        self.assertIn("capacity=unavailable\n", output)
        self.assertIn("status=unavailable\n", output)


if __name__ == "__main__":
    unittest.main()
