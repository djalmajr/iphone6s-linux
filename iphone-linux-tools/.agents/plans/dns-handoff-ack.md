# DNS descriptor handoff acknowledgement

## Context

Native Mac helper passes identity/groups/FD validation but UDP recv returns empty data with no source. Non-root loopback reproduction fails when donor exits immediately; succeeds when donor holds descriptors through receiver adoption. Root drop alone and receiver validation alone pass. Phone remains iOS, verified USB/model and98% charging after manual fallback; prior return CLI failure preserved.

## Files

First phase (five public files): scripts/host/dns_privileged.py, scripts/host/dns_activation.py, tests/test_dns_activation.py, tests/run_dns_activation_mutations.py, docs/DNS-STANDARD.md, all under iphone-linux-tools. This plan can be versioned; raw runtime diagnostics remain private.

## Details

After frame/FD send, helper half-closes Unix output while retaining UDP/TCP. It then requires exact32-byte nonce acknowledgement plus EOF, with overall3s deadline, after dropping groups/GID/UID. Receiver acknowledges only after peer/frame/nonce/two FDs/binds/types/state validate, and half-closes output; helper exit0 remains required before returning ownership. Refusal closes every received FD and own child. No global configuration or protocol fallback.

## Tasks

- [x] Register reproducible failure in GitHub issue.
- [x] Add native cross-process acquire regression before source change; preserve assertion failure evidence.
- [x] Implement two-way handshake; add real ACK exact/fragmented/negative/timeout tests and source mutations.
- [x] Mac focused baseline/mutations/AST/lint; private Linux VM gates for changed privileged protocol.
- [x] Native exact-source Darwin helper: UDP/TCP data and cleanup.
- [ ] Document/publish scoped evidence and await native phoneDNS53 pilot separately.

## Verification

No error/compilation/skip counted as mutation kill. Reuse unchanged gates. Own listeners only; kernel exact/wildcard check before and after. No phone reboot needed in this phase. No packages, DNSpolicy/PF/firewall/sudoers changes, merge/tag/release.


## Evidence documentation phase

Five files: this plan, docs/evidence/dns-standard-port.json, docs/STATUS.md, docs/EXECUCAO.md, docs/PR-REVIEW.md. Preserve initial failure/returnCLI1, add manual iOS USB98% charging confirmation; native donor-close controls and handshake source32c39d4,33/26 Mac and37/31 VM, VM stopped, CI only after observed terminal state. The corrected native helper attempt expired at sudo-v90s without executing helper or producing result; keep that gate and phoneDNS53 pending. Verify JSON/links/public guard/diff before commit/publication. No repeat tests for unchanged source.

Native gate completed after focused TTY authentication: exact source hashes, UDP/TCP data after donor exit, peer/nonce/groups, descriptors/private directory and kernel listener cleanup verified. Code32c39d4 CI completed successfully in six jobs. The earlier sudo timeout remains historical. PhoneDNS53 pilot is still pending.
