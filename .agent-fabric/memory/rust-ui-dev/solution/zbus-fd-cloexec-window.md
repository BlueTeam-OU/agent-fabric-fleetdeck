---
role: "rust-ui-dev"
class: solution
topic: "zbus-fd-cloexec-window"
description: zbus 6.0 receives SCM_RIGHTS fds without MSG_CMSG_CLOEXEC; the returned OwnedFd is a CLOEXEC dup, so only a fork during the call leaks the logind lock
tier: 2
knowledge_scope: full
distilled_at: "2026-10-18"
origin:
  - agent: "rust-ui-dev-01"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - d63b173417c0335b
---

## zbus 6.0 receives SCM_RIGHTS fds without MSG_CMSG_CLOEXEC; the returned OwnedFd is a CLOEXEC dup, so only a fork during the call leaks the logind lock

Measured 2026-10-18 (j107) in the herdr fork's src/platform/linux/shutdown.rs, zbus 6.0.0 (the newest release):
- `runtime/io/unix.rs` `fd_recvmsg` passes `RecvFlags::empty()`, and rustix adds no flag.
- The `zbus::OwnedFd` that `Proxy::call` returns has O_CLOEXEC (flags 02000002 in /proc/self/fdinfo): deserialising makes a `try_clone` (F_DUPFD_CLOEXEC) copy, and the raw received fd goes when the reply Message drops.
- So the leak is only a race: a std::process::Command fork on another thread between recvmsg and that drop. Panes are safe because portable-pty's close_random_fds closes fds above 2 in the child. Worst cost is a shutdown delayed to logind's InhibitDelayMaxSec.
- A first naive test passed before any fix. Mutation check: clearing FD_CLOEXEC on the inhibitor makes the child-spawn test fail.
- No z-galaxy/zbus issue or PR mentions CLOEXEC (searched 2026-10-18). The real fix is upstream (pass CMSG_CLOEXEC on Linux). In-tree it would mean a custom zbus socket: judged not worth it for this bounded race.
- Commit a5066a6a (test + note) is on the j106 branch, local only, so #42's reviewed head 7d3e21df stays intact.

Related: [[herdr-host-toolchain]]

*References: herdr-host-toolchain*

*Anchors: `src/platform/linux/shutdown.rs::MSG_CMSG_CLOEXEC`, `Cargo.toml::zbus = { version = "6"`*

*Observed 2026-10-18 (rust-ui-dev)*
