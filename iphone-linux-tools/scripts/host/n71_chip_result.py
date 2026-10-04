"""Accept one ChipCommon ID only after temporary route and mapping cleanup."""
import re


def require(condition, message):
    if not condition:
        raise ValueError(message)


def summary(text):
    rows = re.findall(r'N71_PCIE_CHIP_RESULT error=(-?\d+) config_reads=(\d+) mmio_reads=(\d+); no DMA or radio', text)
    require(len(rows) == 1, 'Exactly one chip-ID result required')
    result = dict(zip(('error', 'config_reads', 'mmio_reads'), map(int, rows[0])))
    require(0 <= result['config_reads'] <= 200 and 0 <= result['mmio_reads'] <= 1,
            'Chip-ID read budget differs')
    return result


def cleanup(text):
    if 'N71_PCIE_CHIP_' not in text:
        errors = re.findall(r'N71_PCIE_(?:LINK|INVENTORY|SIZING)_RESULT error=(-?\d+)', text)
        require(any(int(error) < 0 for error in errors), 'Missing chip-ID or earlier failure')
        return
    result = summary(text)
    require(re.findall(r'N71_PCIE_CHIP_MAP_RELEASED mapped=(\d+) claimed=(\d+)', text) == [('0', '0')],
            'BAR0 mapping/resource release not proved')
    restored = re.findall(r'N71_PCIE_CHIP_CONFIG_RESTORED error=(-?\d+); route/window/readback checked', text)
    if result['config_reads']:
        require(restored == ['0'], 'Chip-ID route/window/config restoration not proved')
    else:
        require(result['error'] < 0 and result['mmio_reads'] == 0 and not restored,
                'Chip-ID preflight failure is inconsistent')


def parse(text):
    result = summary(text)
    require(result['error'] == 0 and result['config_reads'] >= 20 and result['mmio_reads'] == 1,
            'Successful unique MMIO read required')
    cleanup(text)
    rows = re.findall(r'N71_PCIE_CHIP_ID raw=([0-9a-f]{8}) chip=([0-9a-f]{4}) revision=(\d+); one read only', text)
    require(len(rows) == 1, 'Exactly one restored chip identity required')
    raw, chip, revision = int(rows[0][0], 16), int(rows[0][1], 16), int(rows[0][2])
    require(chip == raw & 0xffff == 0x4350 and raw >> 28 == 1
            and revision == (raw >> 16) & 0xf, 'Chip/revision/backplane identity differs')
    result.update(raw=raw, chip=chip, revision=revision)
    return result
