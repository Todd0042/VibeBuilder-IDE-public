# Remote Access Setup Guide

`vb-server` binds **only to `127.0.0.1:8765`** on your desktop (`VB_SERVER_PORT`). It does not handle TLS certificates directly — instead, you place an HTTPS tunnel or reverse proxy in front of `127.0.0.1:8765` and point `VB_PUBLIC_URL` at it.

> **Why HTTPS is required:** Both the desktop and Android Tauri apps enforce a Content Security Policy that only allows `https://` and `wss://` for remote servers (`http://` and `ws://` are permitted only for `localhost` / `127.0.0.1`). This ensures TOTP codes, device tokens, and terminal streams are never sent unencrypted over Wi-Fi or the internet.

Pick whichever setup fits your environment best:

| Option | Domain needed? | Router port forward? | Phone + Laptop? | Recommended `VB_PROXY` |
|---|---|---|---|---|
| **Tailscale Serve** *(recommended)* | No (free `*.ts.net`) | No | Yes (with Tailscale app) | `none` |
| **Tailscale Funnel** | No (free `*.ts.net`) | No | Yes (public URL) | `forwarded` |
| **Cloudflare Tunnel** | Yes (any cheap domain) | No | Yes (public URL) | `cloudflare` |
| **DuckDNS / Domain + Caddy** | Free subdomain or own domain | Yes (`443/tcp`) | Yes (public URL) | `forwarded` |
| **SSH Port Forward** | No | Port `22` (or LAN) | Laptop only | `none` |

---

## 1. Tailscale Serve (Recommended for Most Users)

**Best if you don't own a domain and don't want your login screen exposed to the public internet.** Tailscale gives your machine a free, valid Let's Encrypt HTTPS URL (`https://<machine>.<tailnet>.ts.net`), and only devices logged into your own Tailscale account can reach it.

1. Install and sign into [Tailscale](https://tailscale.com/) on your desktop, laptop, and/or Android phone.
2. Check that HTTPS certificates are enabled in your Tailscale admin DNS settings, then publish local port `8765` privately to your tailnet:
   ```bash
   tailscale serve --bg 8765
   ```
   Tailscale prints your HTTPS URL, e.g. `https://desktop.tail1234.ts.net`.
3. In `vibebuilder.env`:
   ```env
   VB_PUBLIC_URL=https://desktop.tail1234.ts.net
   VB_PROXY=none
   ```
4. Apply and start/restart:
   ```bash
   bin/vibebuilder start
   ```

> **Want access from a device without Tailscale installed?** Enable Funnel in your Tailscale ACLs and use `tailscale funnel --bg 8765` instead, with `VB_PROXY=forwarded` so sign-in lockouts track each visitor IP via `X-Forwarded-For`.

---

## 2. Cloudflare Tunnel (Own Domain, Zero Open Router Ports)

**Best if you already have (or buy) a domain whose DNS lives on Cloudflare.** No router port forwarding is required.

1. Install `cloudflared` on your desktop, then follow [deploy/cloudflared.example.yml](deploy/cloudflared.example.yml):
   ```bash
   cloudflared tunnel login
   cloudflared tunnel create vibebuilder
   cloudflared tunnel route dns vibebuilder ide.example.com
   ```
2. Copy the example `~/.cloudflared/config.yml` from [deploy/cloudflared.example.yml](deploy/cloudflared.example.yml), fill in your tunnel ID and username, and run it as a service (`sudo cloudflared service install` or `cloudflared tunnel run vibebuilder`).
3. In `vibebuilder.env`:
   ```env
   VB_PUBLIC_URL=https://ide.example.com
   VB_PROXY=cloudflare
   ```
4. Apply:
   ```bash
   bin/vibebuilder start
   ```

*(Legacy `VB_TRUST_CF=1` in older `vibebuilder.env` files still enables `cloudflare` mode automatically.)*

---

## 3. Free Subdomain (DuckDNS) + Caddy or Nginx

**Best if you don't want Cloudflare or Tailscale and can forward port `443` on your home router.**

1. Claim a free hostname at [DuckDNS](https://www.duckdns.org/) (e.g., `mybox.duckdns.org`) and keep your home IP updated, or use any domain pointing to your public IP.
2. Forward **TCP port `443`** (and `80` for HTTP-01 ACME challenges if using Caddy's default challenge) on your router to your desktop.
3. Put a reverse proxy in front of `127.0.0.1:8765`:

   **Option A — Caddy (simplest; automatic Let's Encrypt TLS & WebSockets):**  
   See [deploy/Caddyfile.example](deploy/Caddyfile.example):
   ```caddyfile
   mybox.duckdns.org {
   	reverse_proxy 127.0.0.1:8765
   }
   ```

   **Option B — Nginx (with Certbot TLS):**
   ```nginx
   server {
       listen 443 ssl http2;
       server_name mybox.duckdns.org;

       # ssl_certificate /etc/letsencrypt/live/mybox.duckdns.org/fullchain.pem;
       # ssl_certificate_key /etc/letsencrypt/live/mybox.duckdns.org/privkey.pem;

       client_max_body_size 16m;

       location / {
           proxy_pass http://127.0.0.1:8765;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection "upgrade";
           proxy_set_header Host $host;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```
4. In `vibebuilder.env`:
   ```env
   VB_PUBLIC_URL=https://mybox.duckdns.org
   VB_PROXY=forwarded
   ```

---

## 4. SSH Port Forwarding (Laptop Only, Zero TLS Setup)

Because the Tauri CSP permits plain `http://localhost:*`, you can tunnel straight to loopback from a laptop without configuring TLS or DNS:

1. On the desktop (`vibebuilder.env`):
   ```env
   VB_PUBLIC_URL=http://localhost:8765
   VB_PROXY=none
   ```
2. On the laptop, open the SSH tunnel before launching VibeBuilder IDE:
   ```bash
   ssh -N -L 8765:127.0.0.1:8765 you@your-desktop
   ```
3. Enter `http://localhost:8765` as the server address in the desktop app.

*(This is less convenient on Android because Android doesn't run background OpenSSH tunnels natively.)*

---

## 5. Cloudflare Quick Tunnel (Temporary Testing Only)

To try VibeBuilder IDE immediately with zero accounts or DNS setup:

```bash
cloudflared tunnel --url http://127.0.0.1:8765
```

This prints a temporary `https://<random>.trycloudflare.com` URL you can put in `VB_PUBLIC_URL` with `VB_PROXY=cloudflare`. Note that **the URL changes every time `cloudflared` restarts**, so it is only meant for quick testing rather than daily use.

---

## How `VB_PROXY` Protects Per-IP Lockouts

`vb-server` locks out an IP for 15 minutes after 5 failed sign-in or pairing attempts. Because every local tunnel/proxy opens its TCP connection from `127.0.0.1`, `vb-server` uses `VB_PROXY` to decide which header (if any) identifies the real client:

- **`none`** *(default)*: Ignores `CF-Connecting-IP` and `X-Forwarded-For`, using the direct socket peer (`127.0.0.1` when tunneled). Safe against header spoofing anywhere.
- **`forwarded`**: Reads the **rightmost** entry of `X-Forwarded-For` (appended by your local proxy, e.g. Caddy, Nginx, or Tailscale Funnel), ignoring any spoofed leftmost values sent by the client.
- **`cloudflare`**: Reads `CF-Connecting-IP`. Only enable this when `cloudflared` is the sole path to `127.0.0.1:8765`.
