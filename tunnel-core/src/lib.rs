//! Shared client-side tunnel engine (port forwards + reverse control WebSocket) for desktop and Android.

use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::Arc;
use std::time::Duration;

use futures_util::{SinkExt, StreamExt};
use serde_json::{json, Value};
use tokio::io::{AsyncRead, AsyncReadExt, AsyncWrite, AsyncWriteExt};
use tokio::net::{TcpListener, TcpStream};
#[cfg(unix)]
use tokio::net::UnixStream;
use tokio::sync::{mpsc, oneshot, Mutex};
use tokio::task::JoinHandle;
use tokio_tungstenite::tungstenite::Message;

#[derive(Clone)]
pub enum Target {
    Tcp(u16),
    #[cfg(unix)]
    Unix(PathBuf),
}

#[derive(Default)]
struct Inner {
    server: String,
    session: Option<String>,
    forwards: HashMap<u16, (u16, JoinHandle<()>)>,
    control: Option<mpsc::UnboundedSender<String>>,
    control_task: Option<JoinHandle<()>>,
    targets: HashMap<String, Target>,
    waiting: HashMap<String, oneshot::Sender<Value>>,
}

#[derive(Clone, Default)]
pub struct Tunnels(Arc<Mutex<Inner>>);

fn ws_url(server: &str, path: &str) -> String {
    let base = server.trim_end_matches('/');
    let base = if let Some(rest) = base.strip_prefix("https://") {
        format!("wss://{rest}")
    } else if let Some(rest) = base.strip_prefix("http://") {
        format!("ws://{rest}")
    } else {
        base.to_string()
    };
    format!("{base}{path}")
}

/// Open /api/v1/tunnel for one connection (auth + open request) and wait for the server's go-ahead.
async fn open_tunnel(
    server: &str,
    session: &str,
    request: Value,
) -> Result<tokio_tungstenite::WebSocketStream<tokio_tungstenite::MaybeTlsStream<TcpStream>>, String> {
    let (mut ws, _) = tokio_tungstenite::connect_async(ws_url(server, "/api/v1/tunnel"))
        .await
        .map_err(|e| format!("can't reach the IDE server: {e}"))?;
    ws.send(Message::text(json!({"type": "auth", "session": session}).to_string()))
        .await
        .map_err(|e| e.to_string())?;
    ws.send(Message::text(request.to_string()))
        .await
        .map_err(|e| e.to_string())?;
    match tokio::time::timeout(Duration::from_secs(10), ws.next()).await {
        Ok(Some(Ok(Message::Text(t)))) if t.as_str().contains("\"open\"") => Ok(ws),
        _ => Err("the builder refused the connection (nothing listening?)".into()),
    }
}

/// Bytes both ways between a WebSocket and a socket, until either closes.
async fn pipe<S>(
    ws: tokio_tungstenite::WebSocketStream<tokio_tungstenite::MaybeTlsStream<TcpStream>>,
    sock: S,
) where
    S: AsyncRead + AsyncWrite + Send + 'static,
{
    let (mut ws_tx, mut ws_rx) = ws.split();
    let (mut rd, mut wr) = tokio::io::split(sock);
    let up = async move {
        let mut buf = vec![0u8; 64 * 1024];
        loop {
            match rd.read(&mut buf).await {
                Ok(0) | Err(_) => break,
                Ok(n) => {
                    if ws_tx.send(Message::binary(buf[..n].to_vec())).await.is_err() {
                        break;
                    }
                }
            }
        }
        let _ = ws_tx.close().await;
    };
    let down = async move {
        while let Some(Ok(msg)) = ws_rx.next().await {
            match msg {
                Message::Binary(b) => {
                    if wr.write_all(&b).await.is_err() {
                        break;
                    }
                }
                Message::Close(_) => break,
                _ => {}
            }
        }
        let _ = wr.shutdown().await;
    };
    tokio::select! { _ = up => {}, _ = down => {} }
}

impl Tunnels {
    /// Signed in (Some) or out (None). Signing out stops every tunnel.
    pub async fn set_session(&self, server: String, session: Option<String>) {
        let mut g = self.0.lock().await;
        g.server = server;
        g.session = session.clone();
        if session.is_none() {
            for (_, (_, task)) in g.forwards.drain() {
                task.abort();
            }
            if let Some(t) = g.control_task.take() {
                t.abort();
            }
            g.control = None;
            g.targets.clear();
            g.waiting.clear();
        }
    }

    async fn creds(&self) -> Result<(String, String), String> {
        let g = self.0.lock().await;
        match &g.session {
            Some(s) => Ok((g.server.clone(), s.clone())),
            None => Err("Not signed in".into()),
        }
    }

    // ---- port forwards ------------------------------------------------------------------------
    pub async fn forward(&self, remote: u16, local: u16) -> Result<u16, String> {
        let (server, session) = self.creds().await?;
        if self.0.lock().await.forwards.contains_key(&remote) {
            return Err(format!("port {remote} is already forwarded"));
        }
        let listener = TcpListener::bind(("127.0.0.1", local))
            .await
            .map_err(|e| format!("localhost:{local} is busy on this device ({e})"))?;
        let local = listener.local_addr().map_err(|e| e.to_string())?.port();
        let task = tokio::spawn(async move {
            while let Ok((sock, _)) = listener.accept().await {
                let (server, session) = (server.clone(), session.clone());
                tokio::spawn(async move {
                    if let Ok(ws) = open_tunnel(&server, &session, json!({"kind": "port", "port": remote})).await {
                        pipe(ws, sock).await;
                    }
                });
            }
        });
        self.0.lock().await.forwards.insert(remote, (local, task));
        Ok(local)
    }

    pub async fn unforward(&self, remote: u16) {
        if let Some((_, task)) = self.0.lock().await.forwards.remove(&remote) {
            task.abort();
        }
    }

    pub async fn forwards(&self) -> Vec<(u16, u16)> {
        self.0.lock().await.forwards.iter().map(|(r, (l, _))| (*r, *l)).collect()
    }

    pub async fn has_target(&self, id: &str) -> bool {
        self.0.lock().await.targets.contains_key(id)
    }

    // ---- reverse --------------------------------------------------------------------------------
    async fn ensure_control(&self) -> Result<mpsc::UnboundedSender<String>, String> {
        if let Some(tx) = self.0.lock().await.control.clone() {
            if !tx.is_closed() {
                return Ok(tx);
            }
        }
        let (server, session) = self.creds().await?;
        let (mut ws, _) = tokio_tungstenite::connect_async(ws_url(&server, "/api/v1/reverse"))
            .await
            .map_err(|e| format!("can't reach the IDE server: {e}"))?;
        ws.send(Message::text(json!({"type": "auth", "session": session}).to_string()))
            .await
            .map_err(|e| e.to_string())?;
        match tokio::time::timeout(Duration::from_secs(10), ws.next()).await {
            Ok(Some(Ok(Message::Text(t)))) if t.as_str().contains("\"ready\"") => {}
            _ => return Err("the builder isn't answering (is it running?)".into()),
        }
        let (tx, mut rx) = mpsc::unbounded_channel::<String>();
        let me = self.clone();
        let task = tokio::spawn(async move {
            let (mut ws_tx, mut ws_rx) = ws.split();
            loop {
                tokio::select! {
                    out = rx.recv() => match out {
                        Some(text) => { if ws_tx.send(Message::text(text)).await.is_err() { break; } }
                        None => break,
                    },
                    inc = ws_rx.next() => match inc {
                        Some(Ok(Message::Text(t))) => {
                            if let Ok(v) = serde_json::from_str::<Value>(t.as_str()) { me.on_control(v).await; }
                        }
                        Some(Ok(_)) => {}
                        _ => break,
                    },
                }
            }
            let mut g = me.0.lock().await;
            g.control = None;
            g.targets.clear();
        });
        let mut g = self.0.lock().await;
        g.control = Some(tx.clone());
        g.control_task = Some(task);
        Ok(tx)
    }

    async fn on_control(&self, v: Value) {
        let id = v["id"].as_str().unwrap_or_default().to_string();
        match v["type"].as_str() {
            Some("listening") | Some("error") => {
                if let Some(w) = self.0.lock().await.waiting.remove(&id) {
                    let _ = w.send(v);
                }
            }
            Some("conn") => {
                let conn = v["conn"].as_str().unwrap_or_default().to_string();
                let (target, creds) = {
                    let g = self.0.lock().await;
                    (g.targets.get(&id).cloned(), g.session.clone().map(|s| (g.server.clone(), s)))
                };
                let (Some(target), Some((server, session))) = (target, creds) else { return };
                tokio::spawn(async move {
                    let Ok(ws) = open_tunnel(&server, &session, json!({"kind": "reverse", "conn": conn})).await else { return };
                    match target {
                        Target::Tcp(port) => {
                            if let Ok(s) = TcpStream::connect(("127.0.0.1", port)).await {
                                pipe(ws, s).await;
                            }
                        }
                        #[cfg(unix)]
                        Target::Unix(path) => {
                            if let Ok(s) = UnixStream::connect(&path).await {
                                pipe(ws, s).await;
                            }
                        }
                    }
                });
            }
            _ => {}
        }
    }

    /// Ask the builder to listen; connections there come to `target` here. Returns the builder's reply.
    pub async fn listen(&self, id: &str, builder_side: Value, target: Target) -> Result<Value, String> {
        let tx = self.ensure_control().await?;
        let (wtx, wrx) = oneshot::channel();
        {
            let mut g = self.0.lock().await;
            g.targets.insert(id.to_string(), target);
            g.waiting.insert(id.to_string(), wtx);
        }
        let mut msg = json!({"type": "listen", "id": id});
        for (k, v) in builder_side.as_object().into_iter().flatten() {
            msg[k] = v.clone();
        }
        tx.send(msg.to_string()).map_err(|_| "the builder connection dropped".to_string())?;
        let reply = tokio::time::timeout(Duration::from_secs(10), wrx)
            .await
            .map_err(|_| "the builder didn't answer".to_string())?
            .map_err(|_| "the builder connection dropped".to_string())?;
        if reply["type"] == "error" {
            self.0.lock().await.targets.remove(id);
            return Err(reply["detail"].as_str().unwrap_or("the builder refused").to_string());
        }
        Ok(reply)
    }

    pub async fn unlisten(&self, id: &str) {
        let tx = {
            let mut g = self.0.lock().await;
            g.targets.remove(id);
            g.control.clone()
        };
        if let Some(tx) = tx {
            let _ = tx.send(json!({"type": "close", "id": id}).to_string());
        }
    }
}
