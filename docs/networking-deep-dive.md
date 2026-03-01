# Networking Deep Dive

How InfraProbe implements networking protocols from scratch.

## ICMP Ping (`network/icmp.py`)

We build ICMP Echo Request packets manually using `struct.pack()`:

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|   Type (8)    |   Code (0)    |          Checksum             |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|         Identifier            |        Sequence Number        |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                         Payload (56 bytes)                    |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

**Key implementation details:**
- Opens a raw socket with `socket.SOCK_RAW, socket.IPPROTO_ICMP`
- Checksum calculated per RFC 1071 (one's complement sum)
- RTT measured with `time.perf_counter()` for microsecond precision
- Requires `CAP_NET_RAW` capability (or root)

## DNS Resolution (`network/dns_resolver.py`)

We construct DNS query packets byte-by-byte per RFC 1035:

```
 Header (12 bytes):
   ID | Flags | QDCOUNT | ANCOUNT | NSCOUNT | ARCOUNT

 Question Section:
   QNAME (length-prefixed labels) | QTYPE | QCLASS
```

**Domain name encoding:** `example.com` becomes `\x07example\x03com\x00`

**Compression pointers:** Response names can use 2-byte pointers (`0xC0xx`) to reference previously seen names, reducing packet size.

## TCP Port Scanner (`network/tcp.py`)

Uses Python's `asyncio.open_connection()` for concurrent scanning:
- Performs full TCP three-way handshake (SYN -> SYN-ACK -> ACK)
- Semaphore limits concurrent connections to prevent resource exhaustion
- Banner grabbing reads first 1024 bytes after connection to identify services

## Traceroute (`network/traceroute.py`)

Sends ICMP packets with incrementing TTL:
1. TTL=1: First router responds with ICMP Time Exceeded (Type 11)
2. TTL=2: Second router responds
3. Continue until destination responds with Echo Reply (Type 0)

## TLS Certificate Inspection (`network/http_checker.py`)

Uses `ssl.create_default_context()` + `context.wrap_socket()`:
- Extracts subject, issuer, SANs, validity dates
- Calculates days until expiry for alerting
- Reports protocol version and cipher suite

## Socket State Monitoring (`system/sockets.py`)

Reads `/proc/net/tcp` where IP addresses are hex-encoded in little-endian:
- `0100007F` = `127.0.0.1` (bytes reversed)
- State `0A` = `LISTEN`, `01` = `ESTABLISHED`, `06` = `TIME_WAIT`
