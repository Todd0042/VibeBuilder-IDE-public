//! The native side is deliberately tiny: the device token lives in the system keychain (Secret
//! Service: KWallet or GNOME Keyring), never in a file or in the web view's storage. Everything else
//! (the IDE itself) is the web UI talking to the server.

mod tunnel;

use tunnel::Tunnels;

const SERVICE: &str = "VibeBuilder-IDE";

fn entry(server: &str) -> Result<keyring::Entry, String> {
    keyring::Entry::new(SERVICE, server).map_err(|e| e.to_string())
}

#[tauri::command]
fn token_get(server: String) -> Result<Option<String>, String> {
    match entry(&server)?.get_password() {
        Ok(t) => Ok(Some(t)),
        Err(keyring::Error::NoEntry) => Ok(None),
        Err(e) => Err(format!("Couldn't read the keychain: {e}")),
    }
}

#[tauri::command]
fn token_set(server: String, token: String) -> Result<(), String> {
    entry(&server)?
        .set_password(&token)
        .map_err(|e| format!("Couldn't save to the keychain (is KWallet or GNOME Keyring running?): {e}"))
}

#[tauri::command]
fn token_delete(server: String) -> Result<(), String> {
    match entry(&server)?.delete_credential() {
        Ok(()) | Err(keyring::Error::NoEntry) => Ok(()),
        Err(e) => Err(e.to_string()),
    }
}

#[tauri::command]
fn device_name() -> String {
    hostname::get()
        .ok()
        .and_then(|h| h.into_string().ok())
        .unwrap_or_else(|| "Laptop".into())
}

// ---- app testing (see tunnel.rs) --------------------------------------------------------------------

#[tauri::command]
async fn tunnel_session(t: tauri::State<'_, Tunnels>, server: String, session: Option<String>) -> Result<(), String> {
    t.set_session(server, session).await;
    Ok(())
}

#[tauri::command]
async fn port_forward(t: tauri::State<'_, Tunnels>, remote: u16, local: u16) -> Result<u16, String> {
    t.forward(remote, local).await
}

#[tauri::command]
async fn port_unforward(t: tauri::State<'_, Tunnels>, remote: u16) -> Result<(), String> {
    t.unforward(remote).await;
    Ok(())
}

#[tauri::command]
async fn port_forwards(t: tauri::State<'_, Tunnels>) -> Result<Vec<(u16, u16)>, String> {
    Ok(t.forwards().await)
}

#[tauri::command]
async fn adb_connect(t: tauri::State<'_, Tunnels>) -> Result<(), String> {
    t.adb_connect().await
}

#[tauri::command]
async fn adb_disconnect(t: tauri::State<'_, Tunnels>) -> Result<(), String> {
    t.adb_disconnect().await;
    Ok(())
}

#[tauri::command]
async fn adb_status(t: tauri::State<'_, Tunnels>) -> Result<bool, String> {
    Ok(t.adb_on().await)
}

#[tauri::command]
async fn gui_start(t: tauri::State<'_, Tunnels>, run_id: String) -> Result<String, String> {
    t.gui_start(&run_id).await
}

#[tauri::command]
async fn gui_stop(t: tauri::State<'_, Tunnels>, run_id: String) -> Result<(), String> {
    t.gui_stop(&run_id).await;
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    // The tunnels use rustls; it needs one crypto provider chosen before the first TLS connection.
    let _ = rustls::crypto::ring::default_provider().install_default();
    tauri::Builder::default()
        .manage(Tunnels::default())
        .invoke_handler(tauri::generate_handler![
            token_get, token_set, token_delete, device_name, tunnel_session, port_forward, port_unforward,
            port_forwards, adb_connect, adb_disconnect, adb_status, gui_start, gui_stop
        ])
        .run(tauri::generate_context!())
        .expect("error while running VibeBuilder IDE");
}
