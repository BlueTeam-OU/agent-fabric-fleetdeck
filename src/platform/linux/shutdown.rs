use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::Duration;

use futures_util::StreamExt;

pub(crate) fn monitor_host_shutdown(
    requested: Arc<AtomicBool>,
    // logind has no cancellable announcement to carry across handoff.
    _intent: crate::platform::HostShutdownIntentCell,
    wake: impl Fn() + Send + Sync + 'static,
) -> Option<tokio::task::JoinHandle<()>> {
    Some(tokio::spawn(async move {
        let mut retry = Duration::from_secs(1);
        loop {
            match watch_shutdown(&requested, &wake).await {
                Ok(()) => retry = Duration::from_secs(1),
                Err(err) => {
                    tracing::debug!(err = %err, retry_seconds = retry.as_secs(), "host shutdown notification unavailable");
                    tokio::time::sleep(retry).await;
                    retry = (retry * 2).min(Duration::from_secs(60));
                }
            }
        }
    }))
}

async fn watch_shutdown(
    requested: &AtomicBool,
    wake: &(impl Fn() + Send + Sync),
) -> zbus::Result<()> {
    let connection = zbus::Connection::system().await?;
    watch_connection(connection, requested, wake).await
}

async fn watch_connection(
    connection: zbus::Connection,
    requested: &AtomicBool,
    wake: &(impl Fn() + Send + Sync),
) -> zbus::Result<()> {
    let manager = zbus::Proxy::new(
        &connection,
        "org.freedesktop.login1",
        "/org/freedesktop/login1",
        "org.freedesktop.login1.Manager",
    )
    .await?;
    let mut owners = manager.receive_owner_changed().await?;
    let mut signals = manager.receive_signal("PrepareForShutdown").await?;
    // zbus 6.0 receives the lock without MSG_CMSG_CLOEXEC and returns a
    // close-on-exec duplicate. A child that another thread forks between the two
    // keeps a copy, and shutdown then waits out logind's InhibitDelayMaxSec.
    // Panes close inherited descriptors themselves. Drop this note once zbus
    // receives with the flag.
    let inhibitor: zbus::OwnedFd = manager
        .call(
            "Inhibit",
            &(
                "shutdown",
                "FleetDeck",
                "Save terminal workspace layout",
                "delay",
            ),
        )
        .await?;
    tracing::debug!("host shutdown notification ready");

    let mut preparing: bool = manager.get_property("PreparingForShutdown").await?;
    loop {
        if preparing {
            tracing::info!("host shutdown requested; preserving session before pane termination");
            requested.store(true, Ordering::Release);
            wake();
            // Keep the delay lock until the server has saved and drops its monitor.
            // logind caps the delay even if the server gets stuck.
            std::future::pending::<()>().await;
        }
        tokio::select! {
            biased;
            _ = owners.next() => break,
            signal = signals.next() => {
                let Some(signal) = signal else { break };
                preparing = signal.body().deserialize()?;
            }
        }
    }
    drop(inhibitor);
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::{BufRead, Read};
    use std::os::unix::net::UnixStream;
    use std::process::{Child, Command, Stdio};
    use std::sync::Mutex;

    struct KillOnDrop(Child);

    impl Drop for KillOnDrop {
        fn drop(&mut self) {
            let _ = self.0.kill();
            let _ = self.0.wait();
        }
    }

    struct LoginManager {
        preparing: bool,
        peer: Arc<Mutex<Option<UnixStream>>>,
    }

    #[zbus::interface(name = "org.freedesktop.login1.Manager")]
    impl LoginManager {
        fn inhibit(
            &self,
            what: &str,
            _who: &str,
            _why: &str,
            mode: &str,
        ) -> zbus::fdo::Result<zbus::OwnedFd> {
            assert_eq!((what, mode), ("shutdown", "delay"));
            let (lock, peer) = UnixStream::pair().unwrap();
            peer.set_nonblocking(true).unwrap();
            *self.peer.lock().unwrap() = Some(peer);
            Ok(std::os::fd::OwnedFd::from(lock).into())
        }

        #[zbus(property)]
        fn preparing_for_shutdown(&self) -> bool {
            self.preparing
        }
    }

    #[tokio::test]
    #[ignore = "requires dbus-daemon; uses a private bus, never requests host shutdown"]
    async fn shutdown_warning_holds_inhibitor_until_monitor_is_dropped() {
        for already_preparing in [false, true] {
            let mut bus = KillOnDrop(
                Command::new("dbus-daemon")
                    .args(["--session", "--nofork", "--print-address=1"])
                    .stdout(Stdio::piped())
                    .spawn()
                    .unwrap(),
            );
            let mut address = String::new();
            std::io::BufReader::new(bus.0.stdout.take().unwrap())
                .read_line(&mut address)
                .unwrap();
            let peer = Arc::new(Mutex::new(None));
            let service = zbus::connection::Builder::address(address.trim())
                .name("org.freedesktop.login1")
                .serve_at(
                    "/org/freedesktop/login1",
                    LoginManager {
                        preparing: already_preparing,
                        peer: peer.clone(),
                    },
                )
                .build()
                .await
                .unwrap();
            let client = zbus::connection::Builder::address(address.trim())
                .build()
                .await
                .unwrap();
            let requested = Arc::new(AtomicBool::new(false));
            let wake = Arc::new(tokio::sync::Notify::new());
            let task = tokio::spawn({
                let requested = requested.clone();
                let wake = wake.clone();
                async move {
                    watch_connection(client, &requested, &move || wake.notify_one())
                        .await
                        .unwrap();
                }
            });
            tokio::time::timeout(Duration::from_secs(5), async {
                while peer.lock().unwrap().is_none() {
                    tokio::task::yield_now().await;
                }
                if !already_preparing {
                    assert!(!requested.load(Ordering::Acquire));
                    service
                        .emit_signal(
                            None::<&str>,
                            "/org/freedesktop/login1",
                            "org.freedesktop.login1.Manager",
                            "PrepareForShutdown",
                            &true,
                        )
                        .await
                        .unwrap();
                }
                wake.notified().await;
            })
            .await
            .unwrap();
            assert!(requested.load(Ordering::Acquire));
            let mut peer = peer.lock().unwrap().take().unwrap();
            assert_eq!(
                peer.read(&mut [0]).unwrap_err().kind(),
                std::io::ErrorKind::WouldBlock,
                "shutdown must remain inhibited while the server saves"
            );
            // A child started while the lock is held, as a hook or a handed-off
            // server is, must not keep shutdown delayed after the server lets go.
            let _child = KillOnDrop(Command::new("sleep").arg("30").spawn().unwrap());
            task.abort();
            assert!(task.await.unwrap_err().is_cancelled());
            assert_eq!(
                peer.read(&mut [0]).ok(),
                Some(0),
                "a child process must not inherit the delay lock"
            );
        }
    }
}
