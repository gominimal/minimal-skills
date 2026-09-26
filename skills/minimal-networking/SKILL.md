---
name: minimal-networking
description: Experimental and subject to change. Use when previewing a dev server running inside a Minimal session, exposing or viewing a port from a Minimal sandbox, wiring session-to-session networking, reaching the host from inside a session, getting a Minimal preview URL, or when session hostnames stop resolving or minimald warns it could not publish port 7654. Do not use for general nginx, proxy, or networking questions unrelated to Minimal, production ingress, or Docker networking.
---

# Minimal session networking (experimental)

Treat everything here as experimental and subject to change. This surface has
no public docs on purpose: hostnames, ports, and flags were verified on
2026-07-31; the provider, host-alias, and network-mode claims were
re-verified on 2026-08-26 against min 0.5.4-dev.23.g5e4c5ae1 (Linux aarch64);
and the proxy port, the session-hostname route and the 502 shape were
re-checked on 2026-09-03 against min 0.5.4-dev.62.g30a3031d (macOS arm64);
and the bind each preview route needs was checked on 2026-09-25 against
min 0.5.5-dev.15.gc6cc5fe5 (macOS arm64), then re-checked the same day
against min 0.6.0 (macOS arm64), which also showed that the proxy route does
not reach own-ip sessions. None of it is a stable contract. For general
`min` CLI context see https://minimal.dev/docs/reference/cli-min (the only relevant public page).
Do not cite or invent any other minimal.dev URL for networking topics; none
exists.

On Linux the provider and the network mode decide the topology together.
`--provider local-minimald` (the default) puts the session in the host's
network namespace — but only under the default `--network host-net`;
`--network own-ip` gives the session its own namespace on either provider.
`--provider local-minvmd` puts it in the minvmd microVM behind gvproxy. macOS
has only minvmd. Every address claim below depends on which combination is in
play; see minimal-setup for the flag itself.

## Preview a dev server running in a session

1. Activate and attach the session:

   ```bash
   min session activate --attach
   ```

2. Inside the session, start the dev server normally. The default localhost
   bind is fine for this proxy route in a default `host-net` session; nothing
   needs to be declared up front. The proxy route does not reach an own-ip
   session; preview one through `--ingress` (see own-ip mode below).

   ```bash
   npm run dev
   ```

3. From the host, route through the HTTP proxy on `127.0.0.1:7654`:

   ```bash
   curl -x http://127.0.0.1:7654 http://<name>.local.min.internal:4321/
   ```

   The host always reaches the proxy on `127.0.0.1:7654`, whatever the
   session's provider or network mode, macOS included. `100.64.255.254:7654`
   is only for callers inside a session with its own namespace (see
   Session-to-session traffic); never give it as the proxy for a host
   browser or host `curl`.

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

   This proxy route is the answer for a dev server that is already running:
   it needs no reactivation. Do not tell the user to open
   `http://127.0.0.1:<port>` directly on the host unless the session is a
   Linux `host-net` session on the default `local-minimald` provider, where
   session and host share one loopback, or the port was published with
   `--ingress` at activation and the server binds all addresses (below).
   Every macOS session has its own namespace, so without `--ingress` a bare
   `127.0.0.1:<port>` on the host does not reach it.

## Hostname rule

Every active session registers `<name>.local.min.internal`. `<name>` is the
session name if set, otherwise the project directory basename, lowercased.
`min session rename <id> <name>` re-registers the hostname live. The
hostname only gates the request: it must name an active session. The port in
the URL is then looked up in the shared `host-net` namespace, not inside the
named session. For a default session that is where its server listens, so
the URL works. It also means the hostname does not isolate sessions:
`<any-session>.local.min.internal:<port>` reaches whichever `host-net`
session listens on that port, and never an own-ip session (see own-ip mode
below).

## WebSockets and HMR

WebSockets survive the proxy bidirectionally, both plain Upgrade and the
CONNECT tunnel. Vite and Astro HMR work through it; do not blame the proxy
for broken HMR.

## Session-to-session traffic

Sessions on the same host reach each other through the same proxy. Inside the
calling session:

```bash
export http_proxy=http://127.0.0.1:7654
export https_proxy=http://127.0.0.1:7654
curl http://<peer>.local.min.internal:<port>/
```

Export the lowercase names. curl deliberately ignores an uppercase
`HTTP_PROXY` for `http://` URLs, so setting only that leaves the request
going direct and the peer hostname fails to resolve. Per-call, `curl -x
http://127.0.0.1:7654 http://<peer>.local.min.internal:<port>/` works too.

From an own-ip session (either OS), or on Linux a `--provider local-minvmd`
session, `127.0.0.1:7654` is the sandbox's own loopback and nothing listens
there. Point the proxy at the host alias instead; peer hostnames resolve
through it exactly the same way:

```bash
export http_proxy=http://100.64.255.254:7654
export https_proxy=http://100.64.255.254:7654
curl http://<peer>.local.min.internal:<port>/
```

The recipe applies in both cases; only the proxy address changes. Verified
from an own-ip session against a peer session serving on port 4321: via the
alias the peer's own server answered, while `127.0.0.1:7654` refused the
connection. A 502 from the alias means the proxy is up, not that the route
is unavailable: either the peer hostname is wrong, or nothing in the shared
`host-net` namespace listens on the requested port. On 0.6.0 a default macOS
session reaches the proxy on both addresses; only an own-ip session needs the
alias.

A task run in a session (`min session run`) takes that session's network
mode. Verified on 0.6.0 (macOS arm64) against a peer's `.local.min.internal`
hostname: a task in a default session reached the peer through both
`127.0.0.1:7654` and the alias; a task in an own-ip session reached it only
through the alias (`127.0.0.1:7654`: network unreachable); a task in a
`--network no-net` session reached neither address.

Single host only. Do not claim credential or egress isolation: egress policy
is topology only today, enforcement is not wired, and default sessions share
one network namespace, so they can also reach each other's ports directly.

## Reach the host from inside a session

Which address reaches the host depends on whether the session has its own
network namespace. Check the provider and network mode before picking one.

**A session with its own namespace** — every macOS session, and on Linux
`--provider local-minvmd` or `--network own-ip`. Here `127.0.0.1` is the
sandbox's own loopback, and the host's loopback is behind the gvproxy alias:

```bash
curl http://100.64.255.254:8787/
```

**A Linux `host-net` session on the default `local-minimald` provider** shares
the host's network namespace outright. `127.0.0.1` *is* the host's loopback,
and the alias does not resolve at all:

```bash
curl http://127.0.0.1:8787/
```

The alias is a property of the namespace, not of the operating system. Verified
by binding one host listener to `127.0.0.1:8080` only: it answered on
`127.0.0.1:8080` from a default Linux session, and on `100.64.255.254:8080`
from both a `local-minvmd` and an `own-ip` session, where `127.0.0.1:8080` was
unreachable.

## own-ip mode and --ingress

For a plain `localhost:<port>` preview with no proxy configuration, activate
the session in own-ip mode and publish ports at activation:

```bash
min session activate --network own-ip --ingress 4321:4321 --attach
# inside the session, bind all addresses: npx astro dev --host
curl http://127.0.0.1:4321/    # on the host, no proxy needed
```

The server in the session must listen on all addresses (`0.0.0.0`; for
Astro and Vite, `--host`). One on the default localhost bind is not reached
through `--ingress`: the host's connection is reset. Verified on the
2026-09-25 check: in one own-ip session, a `127.0.0.1:4321` listener reset
the host's `curl` through `--ingress 18431:4321`, a `0.0.0.0:4322` listener
answered through `--ingress 18432:4322`. Same result on 0.6.0.

The proxy route does not reach an own-ip session. The port in its
`<name>.local.min.internal` URL is looked up in the shared `host-net`
namespace (see Hostname rule): the result is a `502` when nothing there
listens on that port, or some other session's server when one does. On macOS
this holds even at the session's `--ingress` external port. Verified on 0.6.0
(macOS arm64) with a different response body in each session:
- Through the proxy, the own-ip session's hostname returned the `host-net`
  session's body on both ports.
- It kept returning `502` for 13 minutes while no `host-net` session
  listened.
- `<name>.local.min.internal:18432` returned `502` while `127.0.0.1:18432`
  directly returned the own-ip session's own body.

For an own-ip session, use `--ingress` with an all-addresses bind and browse
`127.0.0.1:<EXT>` directly; do not offer the proxy route.

These flags take effect at activation. For a default `host-net` session
whose dev server is already running, offer the proxy route first; for an
own-ip session, `--ingress` is the only host route.

| Option | Effect |
|---|---|
| `--network <no-net\|host-net\|own-ip>` | Network mode. `host-net` is the default (shared namespace, possible port collisions, direct peer reach; the namespace is the host's only on Linux `local-minimald`, otherwise the minvmd VM's, so it shares the host's loopback only there). `no-net` is zero networking. `own-ip` gives the session its own namespace and IP. |
| `--ingress EXT:INT[/PROTO]` | Publish session port `INT` as `127.0.0.1:EXT` on the host. Repeatable. `PROTO` is `tcp` (default) or `udp`. Requires `--network own-ip`. |
| `min session policy <session>` | Print the session's effective network policy as JSON. Works for any session. |

`--network` and `--ingress` are still absent from `min session activate
--help` as of 0.5.4-dev.62; they are hidden, not removed. Both are still
accepted and effective: `--ingress 4321:4321` produces a real
`127.0.0.1:4321` listener on the host and a matching `port_mappings` entry in
`min session policy`. Do not conclude from help output that they are gone.

## Sharp edges

- Port 7654 is fixed. If anything else on the host holds it, the daemon says
  so at startup — `warning: session hostnames will not route: the daemon
  could not publish port 7654 ... bind: address already in use` — and then
  runs on without hostname routing. Confirm the holder with
  `lsof -nP -iTCP:7654 -sTCP:LISTEN`. The daemon does not retry once the port
  frees: free it, then `min stop` and let the next `min` command respawn the
  daemon, or routing stays down for the life of that daemon.
- Everything binds loopback only; there is no public URL. Bring your own
  tunnel (for example cloudflared) pointed at the routed port.
- An unknown hostname returns a well-formed `502 Bad Gateway` carrying
  `Content-Length: 0` and `Connection: close`, and the socket closes
  immediately — raw `nc`/`socat` probes return rather than hang. Read a 502
  as "the proxy is up": either the session name in the URL is wrong, or
  nothing in the shared `host-net` namespace listens on that port (an
  own-ip session's own listeners never count). It does not indicate a stuck
  connection.
- Never forward port 7654 itself off the machine. The proxy trusts whoever
  reaches it; tunnel a single session's port instead.
