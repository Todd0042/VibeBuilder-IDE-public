//! VibeBuilder IDE mobile native bridge:
//! - Android KeyStore-backed device token storage + Build.MODEL + Foreground Service via VbAndroidPlugin
//! - Port forwarding via `tunnel_core`
//! - QR code scanning via `tauri-plugin-barcode-scanner`

#[cfg(target_os = "android")]
use serde::{Deserialize, Serialize};
use tunnel_core::Tunnels;

#[cfg(target_os = "android")]
struct AndroidBridge<R: tauri::Runtime>(tauri::plugin::PluginHandle<R>);

#[cfg(not(target_os = "android"))]
#[derive(Default)]
struct MemoryTokens(tokio::sync::Mutex<std::collections::HashMap<String, String>>);

#[cfg(target_os = "android")]
#[derive(Serialize)]
struct TokenKey<'a> {
    server: &'a str,
}

#[cfg(target_os = "android")]
#[derive(Serialize)]
struct TokenPair<'a> {
    server: &'a str,
    token: &'a str,
}

#[cfg(target_os = "android")]
#[derive(Deserialize)]
struct TokenGetResp {
    token: Option<String>,
}

#[cfg(target_os = "android")]
#[derive(Deserialize)]
struct DeviceNameResp {
    name: String,
}

#[cfg(target_os = "android")]
#[derive(Serialize)]
struct ServiceState {
    active: bool,
}

#[tauri::command]
async fn token_get<R: tauri::Runtime>(
    app: tauri::AppHandle<R>,
    server: String,
) -> Result<Option<String>, String> {
    #[cfg(target_os = "android")]
    {
        use tauri::Manager;
        let bridge = app.state::<AndroidBridge<R>>();
        let resp: TokenGetResp = bridge
            .0
            .run_mobile_plugin("tokenGet", TokenKey { server: &server })
            .map_err(|e| format!("Couldn't read Android Keystore: {e}"))?;
        return Ok(resp.token);
    }
    #[cfg(not(target_os = "android"))]
    {
        use tauri::Manager;
        let mem = app.state::<MemoryTokens>();
        let val = mem.0.lock().await.get(&server).cloned();
        Ok(val)
    }
}

#[tauri::command]
async fn token_set<R: tauri::Runtime>(
    app: tauri::AppHandle<R>,
    server: String,
    token: String,
) -> Result<(), String> {
    #[cfg(target_os = "android")]
    {
        use tauri::Manager;
        let bridge = app.state::<AndroidBridge<R>>();
        bridge
            .0
            .run_mobile_plugin::<serde_json::Value>(
                "tokenSet",
                TokenPair {
                    server: &server,
                    token: &token,
                },
            )
            .map_err(|e| format!("Couldn't save token to Android Keystore: {e}"))?;
        return Ok(());
    }
    #[cfg(not(target_os = "android"))]
    {
        use tauri::Manager;
        let mem = app.state::<MemoryTokens>();
        let mut g = mem.0.lock().await;
        g.insert(server, token);
        Ok(())
    }
}

#[tauri::command]
async fn token_delete<R: tauri::Runtime>(
    app: tauri::AppHandle<R>,
    server: String,
) -> Result<(), String> {
    #[cfg(target_os = "android")]
    {
        use tauri::Manager;
        let bridge = app.state::<AndroidBridge<R>>();
        bridge
            .0
            .run_mobile_plugin::<serde_json::Value>("tokenDelete", TokenKey { server: &server })
            .map_err(|e| e.to_string())?;
        return Ok(());
    }
    #[cfg(not(target_os = "android"))]
    {
        use tauri::Manager;
        let mem = app.state::<MemoryTokens>();
        let mut g = mem.0.lock().await;
        g.remove(&server);
        Ok(())
    }
}

#[tauri::command]
async fn device_name<R: tauri::Runtime>(app: tauri::AppHandle<R>) -> String {
    #[cfg(target_os = "android")]
    {
        use tauri::Manager;
        let bridge = app.state::<AndroidBridge<R>>();
        if let Ok(resp) = bridge.0.run_mobile_plugin::<DeviceNameResp>("deviceName", ()) {
            if !resp.name.trim().is_empty() {
                return resp.name;
            }
        }
        return "Android Phone".into();
    }
    #[cfg(not(target_os = "android"))]
    {
        let _ = app;
        "Android (Desktop Preview)".into()
    }
}

fn sync_foreground_service<R: tauri::Runtime>(app: &tauri::AppHandle<R>, active: bool) {
    #[cfg(target_os = "android")]
    {
        use tauri::Manager;
        if let Some(bridge) = app.try_state::<AndroidBridge<R>>() {
            let _ = bridge
                .0
                .run_mobile_plugin::<serde_json::Value>("setTunnelService", ServiceState { active });
        }
    }
    #[cfg(not(target_os = "android"))]
    {
        let _ = (app, active);
    }
}

#[tauri::command]
async fn tunnel_session<R: tauri::Runtime>(
    app: tauri::AppHandle<R>,
    t: tauri::State<'_, Tunnels>,
    server: String,
    session: Option<String>,
) -> Result<(), String> {
    let signed_out = session.is_none();
    t.set_session(server, session).await;
    if signed_out {
        sync_foreground_service(&app, false);
    }
    Ok(())
}

#[tauri::command]
async fn port_forward<R: tauri::Runtime>(
    app: tauri::AppHandle<R>,
    t: tauri::State<'_, Tunnels>,
    remote: u16,
    local: u16,
) -> Result<u16, String> {
    let got = t.forward(remote, local).await?;
    sync_foreground_service(&app, true);
    Ok(got)
}

#[tauri::command]
async fn port_unforward<R: tauri::Runtime>(
    app: tauri::AppHandle<R>,
    t: tauri::State<'_, Tunnels>,
    remote: u16,
) -> Result<(), String> {
    t.unforward(remote).await;
    let remaining = t.forwards().await;
    sync_foreground_service(&app, !remaining.is_empty());
    Ok(())
}

#[tauri::command]
async fn port_forwards(t: tauri::State<'_, Tunnels>) -> Result<Vec<(u16, u16)>, String> {
    Ok(t.forwards().await)
}

fn init_vb_android<R: tauri::Runtime>() -> tauri::plugin::TauriPlugin<R> {
    tauri::plugin::Builder::new("vb-android")
        .setup(|app, api| {
            #[cfg(target_os = "android")]
            {
                use tauri::Manager;
                let handle = api.register_android_plugin("dev.vibebuilder.ide.mobile", "VbAndroidPlugin")?;
                app.manage(AndroidBridge(handle));
            }
            #[cfg(not(target_os = "android"))]
            {
                let _ = (app, api);
            }
            Ok(())
        })
        .build()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let _ = rustls::crypto::ring::default_provider().install_default();

    let builder = tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(init_vb_android())
        .manage(Tunnels::default());

    #[cfg(not(target_os = "android"))]
    let builder = builder.manage(MemoryTokens::default());

    #[cfg(mobile)]
    let builder = builder.plugin(tauri_plugin_barcode_scanner::init());

    builder
        .invoke_handler(tauri::generate_handler![
            token_get,
            token_set,
            token_delete,
            device_name,
            tunnel_session,
            port_forward,
            port_unforward,
            port_forwards,
        ])
        .run(tauri::generate_context!())
        .expect("error while running VibeBuilder IDE mobile");
}
