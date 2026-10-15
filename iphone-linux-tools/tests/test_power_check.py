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
        self.assertIn("usb_configuration=unavailable\n", output)
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

    def test_usb_budget_is_read_only_and_excludes_identifying_strings(self):
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            gadget = root / "kernel/config/usb_gadget/iphone6s"
            configuration = gadget / "configs/c.1"
            configuration.mkdir(parents=True)
            (configuration / "MaxPower").write_text("2\n")
            (configuration / "bmAttributes").write_text("0x80\n")
            strings = gadget / "strings/0x409"
            strings.mkdir(parents=True)
            (strings / "serialnumber").write_text("PRIVATE_DEVICE_CANARY\n")
            before = {p: p.read_bytes() for p in gadget.rglob("*") if p.is_file()}
            output = self.run_check(root)
            self.assertEqual(before, {p: p.read_bytes() for p in before})
        self.assertIn("usb_configuration=iphone6s/c.1\n", output)
        self.assertIn("usb_MaxPower_mA=2\n", output)
        self.assertIn("usb_bmAttributes=0x80\n", output)
        self.assertNotIn("PRIVATE_DEVICE_CANARY", output)
        self.assertIn("charging_validation=unverified\n", output)

    def test_usb_configuration_with_missing_attributes_has_no_budget_claim(self):
        with tempfile.TemporaryDirectory() as folder:
            configuration = pathlib.Path(folder) / "kernel/config/usb_gadget/iphone6s/configs/c.1"
            configuration.mkdir(parents=True)
            (configuration / "MaxPower").write_text("")
            (configuration / "bmAttributes").mkdir()
            output = self.run_check(pathlib.Path(folder))
        self.assertIn("usb_MaxPower_mA=unavailable\n", output)
        self.assertIn("usb_bmAttributes=unavailable\n", output)
        self.assertIn("charging_validation=unverified\n", output)


if __name__ == "__main__":
    unittest.main()
