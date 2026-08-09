use std::io::{BufRead, BufReader};
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};
use std::sync::mpsc::Sender;
use std::thread;
use std::time::Duration;

use crate::protocol::{parse_stream_line, AppEvent, StreamEvent};

/// Shared, killable handle to a spawned VulnClaw Python core process.
///
/// The child is wrapped in `Arc<Mutex<Option<Child>>>` so the TUI can abort it
/// (by taking and killing the `Child`) while a watcher thread awaits its
/// natural exit via non-blocking `try_wait` polling. The watcher only *borrows*
/// the child for polling and never takes ownership, so the TUI is always the
/// sole taker — this guarantees a quit/abort can actually terminate the
/// process and prevents it from outliving the TUI as an orphan.
pub type WorkerHandle = Arc<Mutex<Option<Child>>>;

pub fn spawn_vulnclaw(args: Vec<String>, sender: Sender<AppEvent>) -> std::io::Result<WorkerHandle> {
    let python = std::env::var("VULNCLAW_PYTHON").unwrap_or_else(|_| "python".to_owned());
    let mut command = if cfg!(windows) && python == "python" {
        let mut command = Command::new("py");
        command.arg("-3");
        command
    } else {
        Command::new(python)
    };
    let mut child = command
        .arg("-m")
        .arg("vulnclaw")
        .args(&args)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()?;
    let stdout = child.stdout.take().expect("stdout is piped");
    let stderr = child.stderr.take().expect("stderr is piped");
    let handle: WorkerHandle = Arc::new(Mutex::new(Some(child)));

    let output_sender = sender.clone();
    thread::spawn(move || {
        for line in BufReader::new(stdout).lines().map_while(Result::ok) {
            let event = parse_stream_line(&line).unwrap_or(StreamEvent::Log(line));
            let _ = output_sender.send(AppEvent::Stream(event));
        }
    });

    let err_sender = sender.clone();
    let waiter = handle.clone();
    thread::spawn(move || {
        for line in BufReader::new(stderr).lines().map_while(Result::ok) {
            let _ = err_sender.send(AppEvent::Error(line));
        }
        // Poll for natural exit. We only *borrow* the child here, so the TUI
        // can still take and kill it on abort/quit. If the TUI already took it
        // (guard is `None`), stand down and send nothing.
        loop {
            let next = {
                let mut guard = match waiter.lock() {
                    Ok(g) => g,
                    Err(_) => break,
                };
                match guard.as_mut() {
                    Some(child) => child.try_wait(),
                    None => break,
                }
            };
            match next {
                Ok(Some(status)) => {
                    let _ = sender.send(AppEvent::Finished(status.success()));
                    break;
                }
                Ok(None) => thread::sleep(Duration::from_millis(200)),
                Err(error) => {
                    let _ = sender.send(AppEvent::Error(format!(
                        "could not wait for VulnClaw: {error}"
                    )));
                    break;
                }
            }
        }
    });

    Ok(handle)
}

/// Synchronous `vulnclaw` invocation used for config writes / read-only probes
/// during the first-run setup wizard (where we must wait for completion before
/// continuing, unlike the streaming `spawn_vulnclaw`).
pub fn run_vulnclaw_sync(args: &[&str]) -> std::io::Result<std::process::Output> {
    run_vulnclaw_with_stdin(args, "")
}

/// Run a short-lived CLI command with a private JSON payload on stdin. Draft
/// configuration values, especially API keys, must not be placed in argv where
/// they can be exposed by process listings or shell history.
pub fn run_vulnclaw_with_stdin(
    args: &[&str],
    input: &str,
) -> std::io::Result<std::process::Output> {
    use std::io::Write;

    let python = std::env::var("VULNCLAW_PYTHON").unwrap_or_else(|_| "python".to_owned());
    let mut command = if cfg!(windows) && python == "python" {
        let mut command = Command::new("py");
        command.arg("-3");
        command
    } else {
        Command::new(python)
    };
    let mut child = command
        .arg("-m")
        .arg("vulnclaw")
        .args(args)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()?;
    if !input.is_empty() {
        if let Some(mut stdin) = child.stdin.take() {
            if let Err(error) = stdin.write_all(input.as_bytes()) {
                let _ = child.kill();
                let _ = child.wait();
                return Err(error);
            }
        }
    } else {
        drop(child.stdin.take());
    }
    child.wait_with_output()
}
