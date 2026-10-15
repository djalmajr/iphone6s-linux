"""Bounded read-only DMA wire protocol; timestamps describe reads, not faults."""
import re

RELEASE = '7.2.0-iphone6s-dart-serdev-pmd1'
BOOT = r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}'
LIMIT = 256 * 1024
READY = re.compile(r'N71_DMA_OBSERVER_READY boot=(' + BOOT + r') release=('
    + re.escape(RELEASE) + r') interval=(0\.1|1) count=(100|20)')
HEADER = re.compile(r'requested=1 iova=000000003ffff028 complete=([0-2]) stable=([01]) error=(-?[0-9]{1,4})')
ROW = re.compile(r'sample=([01]) time_ns=([0-9]{1,20}) pa=([0-9a-f]{16}) valid=([0-9a-f]{8})'
    r' command=([0-9a-f]{8}) tcr=([0-9a-f]{8}) error=([0-9a-f]{8}) error_addr=([0-9a-f]{8})'
    r' ttbr=([0-9a-f]{8}),([0-9a-f]{8}),([0-9a-f]{8}),([0-9a-f]{8})')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def identity(boot):
    require(isinstance(boot, str) and re.fullmatch(BOOT, boot), 'DMA boot identity differs')


def command(boot):
    identity(boot)
    return f'''set -eu
test "$(id -u)" = 0
test "$(uname -r)" = {RELEASE}
test "$(cat /proc/sys/kernel/random/boot_id)" = {boot}
p=/sys/module/n71_pcie_diagnostic/parameters
test "$(cat "$p/held")" = held=1
for flag in driver_runtime iommu_parent msi_parent scan_hold dma_observe; do
    test "$(cat "$p/$flag")" = Y
done
test "$(cat "$p/dma_iova")" = 1073737768
interval=1; count=20
if sleep 0.1 2>/dev/null; then interval=0.1; count=100; fi
printf 'N71_DMA_OBSERVER_READY boot=%s release=%s interval=%s count=%s\\n' {boot} {RELEASE} "$interval" "$count"
i=0
while test "$i" -lt "$count"; do
    printf 'N71_DMA_FRAME_BEGIN index=%s\\n' "$i"
    cat "$p/dma_observation"
    printf 'N71_DMA_FRAME_END index=%s\\n' "$i"
    i=$((i + 1))
    sleep "$interval"
done
test "$(cat /proc/sys/kernel/random/boot_id)" = {boot}
printf 'N71_DMA_OBSERVER_DONE count=%s\\n' "$count"
'''


def ready(line, boot):
    identity(boot)
    match = READY.fullmatch(line)
    require(match is not None and match[1] == boot, 'DMA readiness scope differs')
    interval, count = match[3], int(match[4])
    require((interval, count) in (('0.1', 100), ('1', 20)), 'DMA sampling budget differs')
    return interval, count


def observation(lines):
    require(len(lines) == 3, 'DMA observation row count differs')
    match = HEADER.fullmatch(lines[0])
    require(match is not None, 'DMA observation header differs')
    complete, stable, error = map(int, match.groups())
    require(-4095 <= error <= 0, 'DMA error is outside the kernel errno range')
    rows = []
    for index, line in enumerate(lines[1:]):
        row = ROW.fullmatch(line)
        require(row is not None and int(row[1]) == index, 'DMA sample order or schema differs')
        time_ns = int(row[2]); physical = int(row[3], 16); valid = int(row[4], 16)
        words = [int(value, 16) for value in row.groups()[4:]]
        require(time_ns < 1 << 64 and valid <= 0x3ff, 'DMA validity or timestamp exceeds its width')
        if index < complete:
            require(valid == 0x3ff and physical < 1 << 36 and 0xffffffff not in words,
                    'DMA completed sample contains unavailable fields')
        rows.append({'time_ns': time_ns, 'physical': physical, 'valid': valid, 'words': words})
    if stable:
        require(error == 0 and complete == 2 and rows[1]['time_ns'] >= rows[0]['time_ns']
            and rows[0]['physical'] == rows[1]['physical'] and rows[0]['words'] == rows[1]['words']
            and not rows[0]['words'][0] & 8, 'DMA stability claim differs from its samples')
    require(error != 0 or stable == 1, 'DMA success lacks a stable pair')
    return {'complete': complete, 'stable': bool(stable), 'error': error, 'samples': rows}


def parse(raw, boot):
    require(type(raw) is bytes and len(raw) <= LIMIT, 'DMA output exceeds its byte budget')
    try:
        text = raw.decode('ascii')
    except UnicodeDecodeError as error:
        raise ValueError('DMA output is not ASCII') from error
    lines = text.splitlines()
    require(lines and all(len(line) <= 512 for line in lines), 'DMA output line budget differs')
    interval, count = ready(lines[0], boot)
    frames = []; position = 1; done = False
    while position < len(lines):
        index = len(frames)
        if lines[position] == f'N71_DMA_OBSERVER_DONE count={count}':
            require(index == count and position == len(lines) - 1 and text.endswith('\n'),
                    'DMA completion budget or trailing data differs')
            done = True
            break
        require(index < count and lines[position] == f'N71_DMA_FRAME_BEGIN index={index}',
                'DMA frame order differs')
        if len(lines) - position < 5:
            break
        require(lines[position + 4] == f'N71_DMA_FRAME_END index={index}', 'DMA frame boundary differs')
        frames.append(observation(lines[position + 1:position + 4])); position += 5
    times = [row['time_ns'] for frame in frames for row in frame['samples'] if row['valid'] & 1]
    return {'format': 1, 'boot_id': boot, 'interval': interval, 'declared_count': count,
            'done': done, 'truncated': not done, 'frames': frames,
            'clock_monotonic': all(after >= before for before, after in zip(times, times[1:])),
            'stable_mappings': sum(frame['stable'] and frame['samples'][0]['physical'] != 0 for frame in frames),
            'hardware_translation_proved': False}
