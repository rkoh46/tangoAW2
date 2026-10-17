use futures_util::StreamExt;
use futures_util::TryStreamExt;
use prost::Message;

use crate::time;
use crate::ws;

pub type AbortReason = crate::proto::signaling::packet::abort::Reason;

/// The signaling websocket, whichever one this target has (see [`ws`]).
type SignalingStream = ws::Stream;

/// How long to wait for any signaling traffic before treating the websocket as
/// dead. The server echoes our pings, so a healthy idle connection reads at
/// least every `PING_INTERVAL`.
/// tangoAW2: rewrites the ICE server URLs the signalling server offered (`scheme:user:pass@host:port`) before they
/// reach WebRTC: libjuice uses only the first STUN server and two TURN servers, so which come first matters.
static ICE_FILTER: std::sync::OnceLock<fn(Vec<String>, Option<bool>) -> Vec<String>> = std::sync::OnceLock::new();

pub fn set_ice_filter(f: fn(Vec<String>, Option<bool>) -> Vec<String>) {
    let _ = ICE_FILTER.set(f);
}

const READ_TIMEOUT: std::time::Duration = std::time::Duration::from_secs(30);
const PING_INTERVAL: std::time::Duration = std::time::Duration::from_secs(15);

/// Backoff bounds for transparent reconnects while we're still waiting for the
/// peer to start the SDP exchange.
const MIN_RECONNECT_BACKOFF: std::time::Duration = std::time::Duration::from_millis(500);
const MAX_RECONNECT_BACKOFF: std::time::Duration = std::time::Duration::from_secs(8);

/// tangoAW2 patch: with `use_relay == Some(true)` (relay only) leave only TURN-relayed candidates in an SDP.
/// libdatachannel's `Relay` transport policy filters the candidates it trickles but the first offer still carries
/// the gatherer's host candidate, which the peer then connects to directly (and shows our LAN address).
fn relay_only_sdp(sdp: &str) -> String {
    let mut out = String::with_capacity(sdp.len());
    for line in sdp.split_inclusive('\n') {
        if line.starts_with("a=candidate") && !is_relay_candidate(line) {
            continue;
        }
        out.push_str(line);
    }
    out
}

/// A candidate line (`a=candidate:...` or `candidate:...`) of type `relay`.
fn is_relay_candidate(line: &str) -> bool {
    let mut words = line.split_whitespace();
    words.any(|w| w == "typ") && words.next() == Some("relay")
}

/// `sdp` as sent or applied under `use_relay`.
fn sdp_for(use_relay: Option<bool>, sdp: String) -> String {
    if use_relay == Some(true) {
        relay_only_sdp(&sdp)
    } else {
        sdp
    }
}

/// One data channel's `(label, init)`. The caller owns the channel policy
/// (label / stream id / reliability) rather than this crate hardcoding it, and
/// passes every channel the session needs so they're all created together,
/// before the offer. The `init` is cloned per attempt because [`connect`]
/// recreates the channels on every transparent reconnect (and creating one
/// consumes its `init`).
pub type ChannelSpec = (&'static str, datachannel_wrapper::DataChannelInit);

/// Build a fresh peer connection, create every requested channel on it, then
/// generate the offer. Returns as soon as the offer exists — ICE candidates are
/// trickled separately as they gather, so it ships before gathering finishes,
/// and any that arrived in the meantime come back for the caller to buffer.
/// Channels come back in the same order as `channels`.
///
/// Auto-negotiation is disabled and the offer is driven explicitly *after* all
/// channels exist: relying on auto-negotiation here raced the channel creation,
/// because creating the first channel kicks off offer generation + gathering on
/// libdatachannel's own thread, and a second `create_data_channel` landing
/// mid-negotiation made the captured `local_description` intermittently
/// inconsistent. One explicit `set_local_description` after both channels are
/// registered is deterministic (and mirrors the direct transport's bring-up).
async fn create_data_channels(
    rtc_config: datachannel_wrapper::RtcConfig,
    channels: &[ChannelSpec],
) -> Result<
    (
        Vec<datachannel_wrapper::DataChannel>,
        datachannel_wrapper::EventReceiver,
        datachannel_wrapper::PeerConnection,
        datachannel_wrapper::SessionDescription,
        Vec<String>,
    ),
    Error,
> {
    let (mut peer_conn, mut event_rx) = datachannel_wrapper::PeerConnection::new(rtc_config)?;

    let dcs = channels
        .iter()
        .map(|(label, init)| peer_conn.create_data_channel(label, init.clone()))
        .collect::<Result<Vec<_>, _>>()?;

    // All channels registered — now drive the single offer that puts them all
    // in the initial association and starts gathering.
    peer_conn.set_local_description(datachannel_wrapper::SdpType::Offer, None)?;
    let mut early_candidates = Vec::new();
    let offer = await_local_description(&mut event_rx, &mut early_candidates).await?;

    Ok((dcs, event_rx, peer_conn, offer, early_candidates))
}

/// Wait for the local description we just asked for.
///
/// libdatachannel has one ready by the time `set_local_description` returns,
/// but a browser cannot: `createOffer` / `createAnswer` are Promises, so the
/// description exists only once the microtask queue gets to it. Both targets
/// report it the same way — as a `SessionDescription` event — so awaiting that
/// is the one shape that's correct on either. Candidates gathered while we wait
/// are buffered, exactly as the exchange loop buffers them.
async fn await_local_description(
    event_rx: &mut datachannel_wrapper::EventReceiver,
    pending_local_candidates: &mut Vec<String>,
) -> Result<datachannel_wrapper::SessionDescription, Error> {
    loop {
        match event_rx.next().await {
            Some(datachannel_wrapper::PeerConnectionEvent::SessionDescription(sdp)) => return Ok(sdp),
            Some(datachannel_wrapper::PeerConnectionEvent::IceCandidate(c)) => {
                pending_local_candidates.push(c.candidate)
            }
            Some(_) => continue,
            // The peer connection died before it could produce one — a
            // failed createOffer/createAnswer drives it straight to Failed.
            None => {
                return Err(std::io::Error::new(
                    std::io::ErrorKind::ConnectionAborted,
                    "the peer connection failed before it produced a local description",
                )
                .into())
            }
        }
    }
}

/// Encode and send one signaling `Packet` over the websocket.
async fn send_signal(
    stream: &mut SignalingStream,
    which: crate::proto::signaling::packet::Which,
) -> Result<(), ws::Error> {
    ws::send_binary(
        stream,
        crate::proto::signaling::Packet { which: Some(which) }.encode_to_vec(),
    )
    .await
}

#[derive(thiserror::Error, Debug)]
pub enum Error {
    #[error("signaling abort: {0:?}")]
    ServerAbort(AbortReason),

    // Boxed: tungstenite's Error is ~136 bytes and would dominate the
    // size of every Result<_, Error> in the crate.
    #[error("websocket: {0:?}")]
    Websocket(Box<ws::Error>),

    #[error("io: {0:?}")]
    Io(#[from] std::io::Error),

    #[error("prost decode error: {0:?}")]
    ProstDecode(#[from] prost::DecodeError),

    #[error("url parse error: {0:?}")]
    UrlParse(#[from] url::ParseError),

    #[error("invalid packet: not a binary frame")]
    InvalidPacket,

    #[error("unexpected packet: {0:?}")]
    UnexpectedPacket(crate::proto::signaling::Packet),

    #[error("peer connection unexpectedly disconnected")]
    PeerConnectionDisconnected,

    #[error("peer connection failed")]
    PeerConnectionFailed,

    #[error("peer connection unexpectedly closed")]
    PeerConnectionClosed,
}

impl From<ws::Error> for Error {
    fn from(e: ws::Error) -> Self {
        Error::Websocket(Box::new(e))
    }
}

impl Error {
    /// The server's `Abort` body, as returned with an HTTP 400 during
    /// the handshake.
    pub(crate) fn server_abort(body: &[u8]) -> Self {
        match crate::proto::signaling::packet::Abort::decode(body) {
            Ok(abort) => Error::ServerAbort(AbortReason::try_from(abort.reason).unwrap_or_default()),
            Err(e) => Error::ProstDecode(e),
        }
    }
}

/// Whether an error is a transport-level hiccup that a reconnect might paper
/// over (websocket dropped, timed out, reset, EOF) as opposed to a definitive
/// protocol-level rejection (server abort, malformed/unexpected packet, bad
/// SDP). Only the former is worth retrying transparently.
fn is_transient(e: &Error) -> bool {
    match e {
        Error::Io(_) => true,
        Error::Websocket(e) => ws::is_transient(e),
        _ => false,
    }
}

/// The successful outcome of [`connect`]: the negotiated data channels and peer
/// connection, plus both ends' DTLS certificate fingerprints (raw SHA-256
/// digest bytes) as observed during the SDP exchange. The fingerprints let the
/// caller bind a later reconnect rendezvous to *this* connection's cryptographic
/// identities — per-connection, high-entropy, never persisted — rather than to a
/// value (like a game RNG seed) that might leak through other channels.
///
/// `local_fingerprint` is parsed from our own offer/answer SDP; `peer_fingerprint`
/// from the remote description libdatachannel verified against the peer's
/// certificate. Either may be empty if it couldn't be parsed — callers must
/// tolerate that.
pub struct Connected {
    pub channels: Vec<datachannel_wrapper::DataChannel>,
    pub peer_conn: datachannel_wrapper::PeerConnection,
    pub local_dtls_fingerprint: Vec<u8>,
    pub peer_dtls_fingerprint: Vec<u8>,
}

#[cfg(not(target_arch = "wasm32"))]
pub type Connecting = futures_util::future::BoxFuture<'static, Result<Connected, Error>>;

/// The same, minus `Send`: in a browser this future holds JS handles
/// pinned to their thread, and there is no other thread to send it to.
#[cfg(target_arch = "wasm32")]
pub type Connecting = futures_util::future::LocalBoxFuture<'static, Result<Connected, Error>>;

/// Parse a DTLS certificate fingerprint out of an SDP blob, returning the raw
/// SHA-256 digest bytes. SDP carries it as an `a=fingerprint:sha-256 <hex>`
/// attribute whose value is colon-separated, hex-encoded octets (e.g.
/// `AA:BB:...`). Returns `None` if there's no SHA-256 fingerprint line or it
/// doesn't decode; only `sha-256` is accepted (what libdatachannel emits).
fn parse_dtls_fingerprint(sdp: &str) -> Option<Vec<u8>> {
    for line in sdp.lines() {
        let Some(rest) = line.trim().strip_prefix("a=fingerprint:") else {
            continue;
        };
        let mut parts = rest.splitn(2, ' ');
        let algo = parts.next()?;
        if !algo.eq_ignore_ascii_case("sha-256") {
            continue;
        }
        let Some(hex) = parts.next() else { continue };
        let bytes: Option<Vec<u8>> = hex
            .split(':')
            .map(|octet| u8::from_str_radix(octet.trim(), 16).ok())
            .collect();
        match bytes {
            Some(b) if !b.is_empty() => return Some(b),
            _ => continue,
        }
    }
    None
}

/// Bring up a fresh signaling websocket end to end: connect, read the server's
/// `Hello`, build a new peer connection from the offered ICE servers, and send
/// our `Start`. This is the unit we re-run on a transparent reconnect, so every
/// attempt gets fresh ICE credentials and a brand-new local offer.
async fn establish(
    addr: &str,
    session_id: &str,
    use_relay: Option<bool>,
    protocol_version: u32,
    connection_id: &[u8],
    channels: &[ChannelSpec],
) -> Result<
    (
        SignalingStream,
        Vec<datachannel_wrapper::DataChannel>,
        datachannel_wrapper::EventReceiver,
        datachannel_wrapper::PeerConnection,
        String,
        Vec<String>,
    ),
    Error,
> {
    // Everything the server sees before the first frame goes in the query
    // string, on every target: a browser's `WebSocket` can't carry request
    // headers, so putting the protocol version in one natively would just give
    // the server two dialects of the same connection to understand.
    let mut url = url::Url::parse(addr)?;
    url.set_query(Some(
        &url::form_urlencoded::Serializer::new(String::new())
            .append_pair("session_id", session_id)
            .append_pair("protocol_version", &format!("{protocol_version:x}"))
            .finish(),
    ));

    let mut signaling_stream = ws::connect(&url).await?;

    let Some(raw) = signaling_stream.try_next().await? else {
        return Err(std::io::Error::new(std::io::ErrorKind::UnexpectedEof, "stream ended early").into());
    };

    let packet = match ws::classify(raw) {
        ws::Frame::Binary(d) => crate::proto::signaling::Packet::decode(d.as_slice())?,
        _ => return Err(Error::InvalidPacket),
    };

    let hello = match packet.which {
        Some(crate::proto::signaling::packet::Which::Hello(hello)) => hello,
        // A server with no intention of matchmaking for us — one that
        // won't speak our protocol version — has nothing to put in a
        // `Hello` and says so straight away. Read the reason here as
        // well as mid-stream, so a rejection that arrives before the
        // exchange has begun is still a reason rather than a surprise.
        Some(crate::proto::signaling::packet::Which::Abort(abort)) => {
            return Err(Error::ServerAbort(
                AbortReason::try_from(abort.reason).unwrap_or_default(),
            ))
        }
        // Rebuilt rather than matched by reference: `which` is moved by
        // the arms above, and the error wants the whole packet.
        which => return Err(Error::UnexpectedPacket(crate::proto::signaling::Packet { which })),
    };

    log::info!("hello received from signaling stream: {:?}", hello);

    let ice_urls: Vec<String> = hello
            .ice_servers
            .into_iter()
            .flat_map(|ice_server| {
                ice_server
                    .urls
                    .into_iter()
                    .flat_map(|url| {
                        let Some(colon_idx) = url.chars().position(|c| c == ':') else {
                            return vec![];
                        };

                        let proto = &url[..colon_idx];
                        let rest = &url[colon_idx + 1..];

                        if (proto == "turn" || proto == "turns") && use_relay == Some(false) {
                            return vec![];
                        }

                        // libdatachannel doesn't support TURN over TCP: in fact, it explodes!
                        if url.chars().skip_while(|c| *c != '?').collect::<String>() == "?transport=tcp" {
                            return vec![];
                        }

                        if let (Some(username), Some(credential)) = (&ice_server.username, &ice_server.credential) {
                            vec![format!(
                                "{}:{}:{}@{}",
                                proto,
                                urlencoding::encode(username),
                                urlencoding::encode(credential),
                                rest
                            )]
                        } else {
                            vec![format!("{}:{}", proto, rest)]
                        }
                    })
                    .collect::<Vec<_>>()
            })
            .collect();
    // tangoAW2: the relay-failover layer orders and extends the STUN / TURN list (see tango-net `endpoints`).
    let ice_urls = match ICE_FILTER.get() {
        Some(f) => f(ice_urls, use_relay),
        None => ice_urls,
    };
    let mut rtc_config = datachannel_wrapper::RtcConfig::new(&ice_urls);
    if use_relay == Some(true) {
        rtc_config.ice_transport_policy = datachannel_wrapper::TransportPolicy::Relay;
    }
    rtc_config.disable_auto_negotiation = true;
    let (dcs, event_rx, peer_conn, mut offer, early_candidates) = create_data_channels(rtc_config, channels).await?;
    offer.sdp = sdp_for(use_relay, offer.sdp);

    ws::send_binary(
        &mut signaling_stream,
        crate::proto::signaling::Packet {
            which: Some(crate::proto::signaling::packet::Which::Start(
                crate::proto::signaling::packet::Start {
                    protocol_version,
                    offer_sdp: offer.sdp.clone(),
                    connection_id: connection_id.to_vec(),
                },
            )),
        }
        .encode_to_vec(),
    )
    .await?;

    Ok((signaling_stream, dcs, event_rx, peer_conn, offer.sdp, early_candidates))
}

/// Outcome of waiting on a single signaling websocket for the peer to begin the
/// SDP exchange.
enum WaitOutcome {
    /// We received the peer's `Offer` (and answered it) or `Answer` (and applied
    /// it). The peer has committed to this handshake — `peer_conn` now holds the
    /// remote description and we proceed to the ICE phase. Carries both sides'
    /// SDP as exchanged.
    ///
    /// The SDPs come back rather than being read off the peer connection
    /// afterwards because a browser applies a description asynchronously —
    /// `set_remote_description` has only *queued* it by the time it returns,
    /// so reading it straight back finds nothing there. What crossed the wire
    /// is what both targets agree on.
    Exchanged {
        /// The answer we sent, when we were the polite side. `None` when we
        /// offered — the offer we already have stands as our local SDP.
        local_sdp: Option<String>,
        remote_sdp: String,
    },
    /// The websocket dropped (closed / reset / timed out / EOF) *before* the peer
    /// sent any SDP. Nothing is committed on either side, so it's safe to throw
    /// this connection away and reconnect from scratch.
    Dropped(Error),
}

/// Pump the signaling websocket, keeping it alive with pings, until either the
/// peer starts the SDP exchange or the connection drops underneath us.
///
/// The key invariant: once the peer has sent an `Offer` or `Answer`, both sides
/// are committed to *this* set of SDPs, so any subsequent failure is fatal and
/// propagates as `Err`. Only failures observed strictly before the peer says
/// anything become `Dropped`, which the caller may transparently reconnect.
async fn wait_for_exchange(
    signaling_stream: &mut SignalingStream,
    event_rx: &mut datachannel_wrapper::EventReceiver,
    peer_conn: &mut datachannel_wrapper::PeerConnection,
    pending_local_candidates: &mut Vec<String>,
    use_relay: Option<bool>,
) -> Result<WaitOutcome, Error> {
    let mut ping_interval = time::Ticker::every(PING_INTERVAL);

    loop {
        let raw = tokio::select! {
            // Drain our own ICE candidates as they gather, buffering them until
            // the SDP exchange completes (the peer can't accept them before it
            // has our offer/answer); they're flushed right after. No connection
            // state can change before a remote description exists, so anything
            // else is ignored.
            event = event_rx.next() => {
                if let Some(datachannel_wrapper::PeerConnectionEvent::IceCandidate(c)) = event {
                    pending_local_candidates.push(c.candidate);
                }
                continue;
            }
            _ = ping_interval.tick() => {
                if let Err(e) = ws::send_binary(
                    signaling_stream,
                    crate::proto::signaling::Packet {
                        which: Some(crate::proto::signaling::packet::Which::Ping(
                            crate::proto::signaling::packet::Ping {},
                        )),
                    }
                    .encode_to_vec(),
                )
                .await
                {
                    // Couldn't even send a keepalive: the socket is gone.
                    return Ok(WaitOutcome::Dropped(e.into()));
                }
                continue;
            }
            result = time::timeout(READ_TIMEOUT, signaling_stream.try_next()) => {
                match result {
                    // No traffic at all within the timeout: treat as a dead socket.
                    Err(_elapsed) => {
                        return Ok(WaitOutcome::Dropped(
                            std::io::Error::new(std::io::ErrorKind::TimedOut, "timed out").into(),
                        ));
                    }
                    // Read error off the socket.
                    Ok(Err(e)) => return Ok(WaitOutcome::Dropped(e.into())),
                    // Clean EOF before the peer said anything.
                    Ok(Ok(None)) => {
                        return Ok(WaitOutcome::Dropped(
                            std::io::Error::new(std::io::ErrorKind::UnexpectedEof, "stream ended early").into(),
                        ));
                    }
                    Ok(Ok(Some(raw))) => raw,
                }
            }
        };

        let packet = match ws::classify(raw) {
            ws::Frame::Binary(d) => crate::proto::signaling::Packet::decode(d.as_slice())?,
            // A ping is answered below this API — tungstenite queues the
            // pong itself, and a browser's socket never surfaces one.
            ws::Frame::Ignored => {
                continue;
            }
            // The server closed the socket on us before any exchange happened
            // (e.g. it dropped the session). Safe to reconnect.
            ws::Frame::Closed => {
                return Ok(WaitOutcome::Dropped(ws::closed().into()));
            }
        };

        match &packet.which {
            Some(crate::proto::signaling::packet::Which::Ping(_)) => continue,
            Some(crate::proto::signaling::packet::Which::Abort(abort)) => {
                return Err(Error::ServerAbort(
                    AbortReason::try_from(abort.reason).unwrap_or_default(),
                ))
            }
            Some(crate::proto::signaling::packet::Which::Offer(offer)) => {
                log::info!(
                    "received an offer, this is the polite side. rolling back our local description and switching to answer"
                );

                // From here on the peer has committed to this offer: any failure
                // is fatal, never a reconnect.
                peer_conn.set_local_description(datachannel_wrapper::SdpType::Rollback, None)?;
                peer_conn.set_remote_description(datachannel_wrapper::SessionDescription {
                    sdp_type: datachannel_wrapper::SdpType::Offer,
                    sdp: sdp_for(use_relay, offer.sdp.clone()),
                })?;
                // Auto-negotiation is off (see `create_data_channels`), so the
                // answer is generated explicitly rather than implied by applying
                // the remote offer — otherwise `local_description` below would be
                // read before the answer existed.
                peer_conn.set_local_description(datachannel_wrapper::SdpType::Answer, None)?;

                let local_description = await_local_description(event_rx, pending_local_candidates).await?;
                ws::send_binary(
                    signaling_stream,
                    crate::proto::signaling::Packet {
                        which: Some(crate::proto::signaling::packet::Which::Answer(
                            crate::proto::signaling::packet::Answer {
                                sdp: sdp_for(use_relay, local_description.sdp.clone()),
                            },
                        )),
                    }
                    .encode_to_vec(),
                )
                .await?;
                log::info!("sent answer to impolite side");
                return Ok(WaitOutcome::Exchanged {
                    local_sdp: Some(local_description.sdp),
                    remote_sdp: offer.sdp.clone(),
                });
            }
            Some(crate::proto::signaling::packet::Which::Answer(answer)) => {
                log::info!("received an answer, this is the impolite side");

                peer_conn.set_remote_description(datachannel_wrapper::SessionDescription {
                    sdp_type: datachannel_wrapper::SdpType::Answer,
                    sdp: sdp_for(use_relay, answer.sdp.clone()),
                })?;
                return Ok(WaitOutcome::Exchanged {
                    // We offered, so the offer we sent is still our local SDP.
                    local_sdp: None,
                    remote_sdp: answer.sdp.clone(),
                });
            }
            _ => {
                return Err(Error::UnexpectedPacket(packet));
            }
        }
    }
}

pub async fn connect(
    addr: &str,
    session_id: &str,
    use_relay: Option<bool>,
    protocol_version: u32,
    channels: Vec<ChannelSpec>,
) -> Result<Connecting, Error> {
    // A stable id for this logical connection attempt, sent with every `Start`.
    // It survives transparent reconnects, so when our offerer socket drops and
    // we re-dial with a fresh offer, the server recognizes the matching id and
    // replaces our stale offer instead of mistaking the new socket for the
    // answering peer.
    let connection_id: [u8; 16] = rand::random();

    // The initial dial surfaces failures to the caller (so "couldn't reach the
    // matchmaking server" is reported promptly); transparent reconnects only
    // kick in once we've successfully connected at least once.
    let (mut signaling_stream, mut dcs, mut event_rx, mut peer_conn, mut local_sdp, early_candidates) =
        establish(addr, session_id, use_relay, protocol_version, &connection_id, &channels).await?;

    let addr = addr.to_owned();
    let session_id = session_id.to_owned();

    Ok(Box::pin(async move {
        // Local ICE candidates gathered before the peer has our SDP — buffered by
        // `wait_for_exchange`, flushed once the exchange completes. Starts with
        // whatever gathered while we were waiting on the offer.
        let mut pending_local_candidates: Vec<String> = early_candidates;

        // Wait for the peer to start the SDP exchange. As long as the peer hasn't
        // started, a websocket drop is recoverable: tear everything down and dial
        // again with a fresh peer connection / offer.
        let remote_sdp = loop {
            match wait_for_exchange(
                &mut signaling_stream,
                &mut event_rx,
                &mut peer_conn,
                &mut pending_local_candidates,
                use_relay,
            )
            .await?
            {
                WaitOutcome::Exchanged {
                    local_sdp: answered,
                    remote_sdp,
                } => {
                    if let Some(answered) = answered {
                        local_sdp = answered;
                    }
                    break remote_sdp;
                }
                WaitOutcome::Dropped(reason) => {
                    log::warn!(
                        "signaling websocket dropped before the peer started exchanging ({reason}); reconnecting transparently"
                    );

                    let mut backoff = MIN_RECONNECT_BACKOFF;
                    loop {
                        match establish(
                            &addr,
                            &session_id,
                            use_relay,
                            protocol_version,
                            &connection_id,
                            &channels,
                        )
                        .await
                        {
                            Ok((s, d, e, p, sdp, early)) => {
                                signaling_stream = s;
                                dcs = d;
                                event_rx = e;
                                peer_conn = p;
                                local_sdp = sdp;
                                // Fresh peer connection → the old buffer is stale;
                                // what this attempt has gathered so far replaces it.
                                pending_local_candidates = early;
                                log::info!("signaling reconnected; still waiting for the peer");
                                break;
                            }
                            Err(e) if is_transient(&e) => {
                                log::warn!("signaling reconnect attempt failed ({e}); retrying in {backoff:?}");
                                time::sleep(backoff).await;
                                backoff = (backoff * 2).min(MAX_RECONNECT_BACKOFF);
                            }
                            // A protocol-level rejection won't fix itself on retry.
                            Err(e) => return Err(e),
                        }
                    }
                }
            }
        };

        // Both ends' DTLS fingerprints, parsed from the SDP each side
        // committed to. The caller pairs them to derive a rendezvous id both
        // ends agree on.
        let local_dtls_fingerprint = parse_dtls_fingerprint(&local_sdp).unwrap_or_default();
        let peer_dtls_fingerprint = parse_dtls_fingerprint(&remote_sdp).unwrap_or_default();

        log::debug!("local sdp: {local_sdp}");
        log::debug!("remote sdp: {remote_sdp}");

        // Trickle phase: both peers now hold each other's SDP. Flush the
        // candidates we buffered during the exchange, then keep the websocket
        // open to trickle new local candidates out and apply the peer's, until
        // our connection comes up. Each peer closes its own socket on `Connected`
        // (the server no longer closes them after the answer).
        for candidate in pending_local_candidates.drain(..) {
            let _ = send_signal(
                &mut signaling_stream,
                crate::proto::signaling::packet::Which::IceCandidate(crate::proto::signaling::packet::IceCandidate {
                    candidate,
                }),
            )
            .await;
        }

        let mut ping_interval = time::Ticker::every(PING_INTERVAL);

        let outcome: Result<(), Error> = loop {
            tokio::select! {
                // The peer connection's own events are the authority on when we're
                // up, and the source of the local candidates we trickle out.
                ev = event_rx.next() => match ev {
                    Some(datachannel_wrapper::PeerConnectionEvent::IceCandidate(c)) => {
                        let _ = send_signal(
                            &mut signaling_stream,
                            crate::proto::signaling::packet::Which::IceCandidate(
                                crate::proto::signaling::packet::IceCandidate { candidate: c.candidate },
                            ),
                        )
                        .await;
                    }
                    Some(datachannel_wrapper::PeerConnectionEvent::ConnectionStateChange(c)) => match c {
                        datachannel_wrapper::ConnectionState::Connected => break Ok(()),
                        datachannel_wrapper::ConnectionState::Disconnected => break Err(Error::PeerConnectionDisconnected),
                        datachannel_wrapper::ConnectionState::Failed => break Err(Error::PeerConnectionFailed),
                        datachannel_wrapper::ConnectionState::Closed => break Err(Error::PeerConnectionClosed),
                        _ => {}
                    },
                    Some(_) => {}
                    None => {
                        break Err(std::io::Error::new(
                            std::io::ErrorKind::UnexpectedEof,
                            "peer connection event stream ended",
                        )
                        .into())
                    }
                },
                // Incoming peer candidates over the websocket — best-effort: if
                // the socket dies here the already-exchanged candidates usually
                // suffice, so a read error isn't fatal; we keep waiting on the
                // connection state above.
                msg = time::timeout(READ_TIMEOUT, signaling_stream.try_next()) => {
                    if let Ok(Ok(Some(ws::Frame::Binary(d)))) = msg.map(|r| r.map(|m| m.map(ws::classify))) {
                        if let Ok(crate::proto::signaling::Packet {
                            which: Some(crate::proto::signaling::packet::Which::IceCandidate(c)),
                        }) = crate::proto::signaling::Packet::decode(d.as_slice())
                        {
                            // Logged rather than swallowed: a rejected candidate
                            // is invisible otherwise, and enough of them means a
                            // connection that never leaves `new`.
                            if use_relay == Some(true) && !is_relay_candidate(&c.candidate) {
                                // (relay only: the peer's host and server-reflexive candidates are not used)
                            } else if let Err(e) = peer_conn
                                .add_remote_candidate(datachannel_wrapper::IceCandidate { candidate: c.candidate })
                            {
                                log::warn!("signaling: peer candidate rejected: {e}");
                            }
                        }
                    }
                }
                _ = ping_interval.tick() => {
                    let _ = send_signal(
                        &mut signaling_stream,
                        crate::proto::signaling::packet::Which::Ping(crate::proto::signaling::packet::Ping {}),
                    )
                    .await;
                }
            }
        };

        // Connected or failed — either way we're done with signaling. Closing is
        // best-effort; losing the close race must not fail a healthy bring-up.
        ws::close(&mut signaling_stream).await;
        outcome?;

        // The peer connection's event stream is otherwise dropped once we return,
        // so a mid-match state change (the cause of a drop) would be invisible.
        // Keep draining it on a detached task that logs connection-state changes
        // for the life of the connection; it ends when the connection is dropped
        // (the event sender goes away).
        time::spawn(async move {
            while let Some(ev) = event_rx.next().await {
                if let datachannel_wrapper::PeerConnectionEvent::ConnectionStateChange(state) = ev {
                    log::info!("pvp peer connection state: {state:?}");
                }
            }
        });

        Ok(Connected {
            channels: dcs,
            peer_conn,
            local_dtls_fingerprint,
            peer_dtls_fingerprint,
        })
    }))
}
