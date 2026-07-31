---
name: minimal-networking
description: Experimental and subject to change. Use when previewing a dev server running inside a Minimal session, exposing or viewing a port from a Minimal sandbox, wiring session-to-session networking, reaching the host from inside a session, or getting a Minimal preview URL. Do not use for general nginx, proxy, or networking questions unrelated to Minimal, production ingress, or Docker networking.
---

# Minimal session networking (experimental)

Treat everything here as experimental and subject to change. This surface has
no public docs on purpose: hostnames, ports, and flags were verified on
2026-07-31 but are not a stable contract. For general `min` CLI context see
https://minimal.dev/docs/reference/cli-min (the only relevant public page).
Do not cite or invent any other minimal.dev URL for networking topics; none
exists.

## Preview a dev server running in a session

1. Activate and attach the session:

   ```bash
   min session activate --attach
   ```

2. Inside the session, start the dev server normally. The default localhost
   bind is fine; nothing needs to be declared up front.

   ```bash
   npm run dev
   ```

3. From the host, route through the HTTP proxy on `127.0.0.1:7654`:

   ```bash
   curl -x http://127.0.0.1:7654 http://<name>.local.min.internal:4321/
   ```

4. For a browser, launch a dedicated Chrome profile through the proxy:

   ```bash
   open -na "Google Chrome" --args \
     --user-data-dir=/tmp/min-preview \
     --proxy-server="http://127.0.0.1:7654"
   # then open http://<name>.local.min.internal:4321
   ```

   External CDN assets will not load in that profile (only `*.min.internal`
   resolves through the proxy). If that matters, use a PAC file that returns
   `PROXY 127.0.0.1:7654` for `.min.internal` hosts and `DIRECT` for
   everything else, passed with `--proxy-pac-url`.

## Hostname rule

Every active session registers `<name>.local.min.internal`. `<name>` is the
session name if set, otherwise the project directory basename, lowercased.
`min session rename <id> <name>` re-registers the hostname live. The port in
the URL selects the port inside the session.

## WebSockets and HMR

WebSockets survive the proxy bidirectionally, both plain Upgrade and the
CONNECT tunnel. Vite and Astro HMR work through it; do not blame the proxy
for broken HMR.

## Session-to-session traffic

Sessions on the same host reach each other through the same proxy. Inside the
calling session:

```bash
export HTTP_PROXY=http://127.0.0.1:7654
export HTTPS_PROXY=http://127.0.0.1:7654
curl http://<peer>.local.min.internal:<port>/
```

Single host only. Do not claim credential or egress isolation: egress policy
is topology only today, enforcement is not wired, and default sessions share
one network namespace, so they can also reach each other's ports directly.

## Reach the host from inside a session

Inside a session, `127.0.0.1` is the sandbox's own loopback, not the host's.
To reach a service listening on the host's loopback, use the host alias IP:

```bash
curl http://100.64.255.254:8787/
```

## own-ip mode and --ingress

For a plain `localhost:<port>` preview with no proxy configuration, activate
the session in own-ip mode and publish ports at activation:

```bash
min session activate --network own-ip --ingress 4321:4321 --attach
curl http://127.0.0.1:4321/    # on the host, no proxy needed
```

| Option | Effect |
|---|---|
| `--network <no-net\|host-net\|own-ip>` | Network mode. `host-net` is the default (shared namespace, shared loopback, possible port collisions, direct peer reach). `no-net` is zero networking. `own-ip` gives the session its own namespace and IP. |
| `--ingress EXT:INT[/PROTO]` | Publish session port `INT` as `127.0.0.1:EXT` on the host. Repeatable. `PROTO` is `tcp` (default) or `udp`. Requires `--network own-ip`. |
| `min session policy <session>` | Print the session's effective network policy as JSON. Works for any session. |

## Sharp edges

- Port 7654 is fixed. If anything else on the host holds it, the publish
  fails silently. First debugging step, always:
  `lsof -nP -iTCP:7654 -sTCP:LISTEN`.
- Everything binds loopback only; there is no public URL. Bring your own
  tunnel (for example cloudflared) pointed at the routed port.
- Error responses hold the connection open: an unknown hostname returns 502
  without closing the socket, so raw `nc`/`socat` probes appear to hang while
  curl and browsers are fine.
- Never forward port 7654 itself off the machine. The proxy trusts whoever
  reaches it; tunnel a single session's port instead.
