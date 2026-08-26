---
name: minimal-networking
description: Experimental and subject to change. Use when previewing a dev server running inside a Minimal session, exposing or viewing a port from a Minimal sandbox, wiring session-to-session networking, reaching the host from inside a session, or getting a Minimal preview URL. Do not use for general nginx, proxy, or networking questions unrelated to Minimal, production ingress, or Docker networking.
---

# Minimal session networking (experimental)

Treat everything here as experimental and subject to change. This surface has
no public docs on purpose: hostnames, ports, and flags were verified on
2026-07-31, and the provider, host-alias, and network-mode claims were
re-verified on 2026-08-26 against min 0.5.4-dev.23.g5e4c5ae1 (Linux aarch64),
but none of it is a stable contract. For general `min` CLI context see
https://minimal.dev/docs/reference/cli-min (the only relevant public page).
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
export http_proxy=http://127.0.0.1:7654
export https_proxy=http://127.0.0.1:7654
curl http://<peer>.local.min.internal:<port>/
```

Export the lowercase names. curl deliberately ignores an uppercase
`HTTP_PROXY` for `http://` URLs, so setting only that leaves the request
going direct and the peer hostname fails to resolve. Per-call, `curl -x
http://127.0.0.1:7654 http://<peer>.local.min.internal:<port>/` works too.

From a session with its own network namespace — every macOS session, and on
Linux `--provider local-minvmd` or `--network own-ip` — `127.0.0.1:7654` is
the sandbox's own loopback and nothing listens there. Point the proxy at the
host alias instead; peer hostnames resolve through it exactly the same way:

```bash
export http_proxy=http://100.64.255.254:7654
export https_proxy=http://100.64.255.254:7654
curl http://<peer>.local.min.internal:<port>/
```

The recipe applies in both cases; only the proxy address changes. Verified
from an own-ip session against a peer session serving on port 4321: via the
alias the peer's own server answered, while `127.0.0.1:7654` refused the
connection. A 502 from the alias means the proxy is up and the peer hostname
is wrong — not that the route is unavailable.

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
curl http://127.0.0.1:4321/    # on the host, no proxy needed
```

| Option | Effect |
|---|---|
| `--network <no-net\|host-net\|own-ip>` | Network mode. `host-net` is the default (shared namespace, shared loopback, possible port collisions, direct peer reach). `no-net` is zero networking. `own-ip` gives the session its own namespace and IP. |
| `--ingress EXT:INT[/PROTO]` | Publish session port `INT` as `127.0.0.1:EXT` on the host. Repeatable. `PROTO` is `tcp` (default) or `udp`. Requires `--network own-ip`. |
| `min session policy <session>` | Print the session's effective network policy as JSON. Works for any session. |

`--network` and `--ingress` are not listed in `min session activate --help` on
0.5.4-dev.23 — they are hidden, not removed. Both are still accepted and
effective: `--ingress 4321:4321` produces a real `127.0.0.1:4321` listener on
the host and a matching `port_mappings` entry in `min session policy`. Do not
conclude from help output that they are gone.

## Sharp edges

- Port 7654 is fixed. If anything else on the host holds it, the publish
  fails silently. First debugging step, always:
  `lsof -nP -iTCP:7654 -sTCP:LISTEN`.
- Everything binds loopback only; there is no public URL. Bring your own
  tunnel (for example cloudflared) pointed at the routed port.
- An unknown hostname returns a well-formed `502 Bad Gateway` carrying
  `Content-Length: 0` and `Connection: close`, and the socket closes
  immediately — raw `nc`/`socat` probes return rather than hang. Read a 502
  as "the proxy is up and the session name in the URL is wrong"; it does not
  indicate a stuck connection.
- Never forward port 7654 itself off the machine. The proxy trusts whoever
  reaches it; tunnel a single session's port instead.
