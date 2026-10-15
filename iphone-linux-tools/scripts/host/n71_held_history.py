"""Preserve held history while admitting the qualified REG_ON getter records."""
import re
import n71_session_history


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify(live, prior, *, reg_present):
    before = n71_session_history.kernel_lines(prior)
    after = n71_session_history.kernel_lines(live)
    require(after[:len(before)] == before, 'Held diagnostic history prefix changed')
    extra = after[len(before):]
    if not reg_present:
        require(not extra, 'Diagnostic history changed with REG_ON absent')
        return
    values = re.findall(r'^N71_REG_ON_CONTROL_READBACK value=([0-9a-f]{2})$', live, re.M)
    require(len(values) == live.count('N71_REG_ON_CONTROL_READBACK ') == 1,
            'Unique live REG_ON getter required')
    pattern = r'\[\s*\d+\.\d+\] N71_REG_ON_READ error=0 value_valid=1 value=' + values[0]
    require(extra and all(re.fullmatch(pattern, line) for line in extra),
            'Held history includes an unproved operation or REG_ON read')
