#[cfg(feature = "client")]
mod client;
/// The signaling websocket, per target: tungstenite over rustls
/// natively, the page's own `WebSocket` in a browser.
#[cfg(feature = "client")]
mod time;
mod ws;

#[cfg(feature = "client")]
pub use client::*;

// The `proto` feature exports the protobuf module for out-of-tree
// consumers (the signaling server lives in its own repo); the client
// in this workspace only uses it internally.
#[cfg(feature = "proto")]
pub mod proto;

#[cfg(not(feature = "proto"))]
mod proto;
