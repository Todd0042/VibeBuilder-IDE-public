//! App testing: the laptop ends of the tunnels to the builder (delegates port forwards & reverse
//! control to `tunnel_core`, and adds laptop-specific adb + waypipe process management).

use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::Arc;
use std::time::Duration;

use serde_json::json;
use tokio::process::{Child, Command};
use tokio::sync::Mutex;
use tunnel_core::Target;

#[derive(Clone, Default)]
pub struct Tunnels {
    core: tunnel_core::Tunnels,
    runs: Arc<Mutex<HashMap<String, Child>>>,
}

impl Tunnels {
    /// Signed in (Some) or out (None). Signing out stops every tunnel and GUI run.
    pub async fn set_session(&self, server: String, session: Option<String>) {
        let sign_out = session.is_none();
        self.core.set_session(server, session).await;
        if sign_out {
            for (_, mut child) in self.runs.lock().await.drain() {
                let _ = child.start_kill();
            }
        }
    }

    pub async fn forward(&self, remote: u16, local: u16) -> Result<u16, String> {
        self.core.forward(remote, local).await
    }

    pub async fn unforward(&self, remote: u16) {
        self.core.unforward(remote).await;
    }

    pub async fn forwards(&self) -> Vec<(u16, u16)> {
        self.core.forwards().await
    }

    // ---- the phone (adb) ------------------------------------------------------------------------
    /// The builder's `adb` talks to this laptop's adb server, so a phone plugged in here shows up there.
    pub async fn adb_connect(&self) -> Result<(), String> {
        let run = Command::new("adb").arg("start-server").output();
        match tokio::time::timeout(Duration::from_secs(10), run).await {
            Err(_) => return Err("adb start-server didn't finish within 10 seconds (try: adb kill-server)".into()),
            Ok(Err(e)) if e.kind() == std::io::ErrorKind::NotFound => {
                return Err("adb isn't installed on this laptop (sudo pacman -S android-tools)".into())
            }
            Ok(Err(e)) => return Err(format!("couldn't run adb: {e}")),
            Ok(Ok(out)) if !out.status.success() => {
                let why = String::from_utf8_lossy(&out.stderr);
                return Err(format!("adb start-server failed ({}): {}", out.status, why.trim()));
            }
            Ok(Ok(_)) => {}
        }
        self.core.listen("adb", json!({"tcp": 5037}), Target::Tcp(5037)).await.map(|_| ())
    }

    pub async fn adb_disconnect(&self) {
        self.core.unlisten("adb").await;
    }

    pub async fn adb_on(&self) -> bool {
        self.core.has_target("adb").await
    }

    // ---- GUI runs (waypipe) -----------------------------------------------------------------------
    /// Start a local `waypipe client` for this run and a builder listener for it. Returns the socket
    /// path in the builder, which the run's `waypipe server` connects to.
    pub async fn gui_start(&self, run_id: &str) -> Result<String, String> {
        if !run_id.chars().all(|c| c.is_ascii_alphanumeric() || c == '-') || run_id.len() > 30 {
            return Err("bad run id".into());
        }
        if std::env::var_os("WAYLAND_DISPLAY").is_none() {
            return Err("App windows need a Wayland session on this laptop".into());
        }
        let dir = std::env::var_os("XDG_RUNTIME_DIR").map(PathBuf::from).unwrap_or_else(std::env::temp_dir);
        let sock = dir.join(format!("vb-wp-{run_id}.sock"));
        let _ = tokio::fs::remove_file(&sock).await;
        let child = Command::new("waypipe")
            .args(["--socket", &sock.to_string_lossy(), "--compress", "zstd", "client"])
            .kill_on_drop(true)
            .spawn()
            .map_err(|_| "waypipe isn't installed on this laptop (sudo pacman -S waypipe)".to_string())?;
        for _ in 0..50 {
            if sock.exists() {
                break;
            }
            tokio::time::sleep(Duration::from_millis(50)).await;
        }
        self.runs.lock().await.insert(run_id.to_string(), child);
        let id = format!("wp-{run_id}");
        match self.core.listen(&id, json!({"unix": true}), Target::Unix(sock)).await {
            Ok(reply) => reply["path"].as_str().map(str::to_string).ok_or_else(|| "the builder gave no socket".into()),
            Err(e) => {
                self.gui_stop(run_id).await;
                Err(e)
            }
        }
    }

    pub async fn gui_stop(&self, run_id: &str) {
        self.core.unlisten(&format!("wp-{run_id}")).await;
        if let Some(mut child) = self.runs.lock().await.remove(run_id) {
            let _ = child.start_kill();
        }
    }
}
