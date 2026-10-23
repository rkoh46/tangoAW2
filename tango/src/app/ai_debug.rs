//! The app's half of the AI debug channel (`tango_library::ai_debug`, see tools/aidebug/README.md). Off unless
//! `TANGOAW2_AI_DEBUG=<port | socket path>` (or the hidden `ai_debug` key of config.json) is set: then nothing here
//! runs, no thread exists and no subscription ticks. When on, a 16 ms tick (a) hands the pad word the channel's
//! injector made to the session's normal input path, (b) tells the channel what kind of session this is and how its
//! network is doing, (c) turns changes of the network into events, and (d) runs the few commands only the app can
//! (the window picture, typing into the lobby, starting a session, network faults in test mode).

#[cfg(feature = "gamesupport-aw2")]
mod on {
    use super::super::{App, Message};
    use serde_json::{json, Value};
    use std::sync::mpsc::Receiver;
    use std::sync::Mutex;
    use std::time::Instant;
    use tango_library::ai_debug as dbg;
    use tango_library::ai_debug::server::AppCall;

    #[derive(Default)]
    pub struct AiDebug {
        rx: Option<Mutex<Receiver<AppCall>>>,
        prev: Option<Prev>,
    }

    #[derive(Clone, PartialEq)]
    struct Prev {
        health: Vec<(&'static str, bool)>,
        route: Vec<Option<String>>,
        reconnecting: bool,
        remote_disconnected: bool,
        host_seat: usize,
        migrations: u32,
        migrating: Option<(String, bool)>,
        holds: Vec<(u8, String)>,
        booting: bool,
        waiting_for_peer: bool,
    }

    impl AiDebug {
        pub fn enabled(&self) -> bool {
            self.rx.is_some()
        }

        /// Starts the channel when asked to (see the module docs).
        pub fn start(config: &crate::config::Config) -> Self {
            let boot_ckpt = std::env::var("TANGOAW2_BOOT_CHECKPOINT").ok().filter(|s| !s.is_empty());
            let listen = std::env::var("TANGOAW2_AI_DEBUG").ok().or_else(|| config.ai_debug.clone()).filter(|s| !s.is_empty());
            if listen.is_none() && boot_ckpt.is_none() {
                return Self::default();
            }
            dbg::enable(&config.data_path.join("checkpoints"));
            dbg::set_boot_checkpoint(boot_ckpt);
            let Some(listen) = listen else { return Self::default() };
            let (tx, rx) = std::sync::mpsc::channel();
            let flag = |k: &str| std::env::var(k).is_ok_and(|v| v == "1");
            let settings = dbg::server::Settings {
                listen,
                token: std::env::var("TANGOAW2_AI_DEBUG_TOKEN").ok().filter(|t| !t.is_empty()),
                test_mode: flag("TANGOAW2_AI_DEBUG_TEST"),
                write_online: flag("TANGOAW2_AI_DEBUG_WRITE"),
                app_version: format!("{} build {}", env!("CARGO_PKG_VERSION"), env!("TANGOAW2_BUILD")),
            };
            let token = settings.token.is_some();
            let test = settings.test_mode;
            match dbg::server::start(settings, tx) {
                Ok(at) => {
                    log::warn!("ai-debug: channel ON at {at} (loopback only, token {}, fault injection {})", if token { "required" } else { "none" }, if test { "ALLOWED" } else { "off" });
                    // (the line a tool reads to find the port)
                    println!("AI_DEBUG_LISTENING {at}");
                    Self { rx: Some(Mutex::new(rx)), prev: None }
                }
                Err(e) => {
                    log::error!("ai-debug: cannot listen: {e}");
                    Self::default()
                }
            }
        }
    }

    fn ms(v: Option<f32>) -> Value {
        v.map_or(Value::Null, |x| json!((x as f64 * 10.0).round() / 10.0))
    }

    /// The `state.link` object (and the source of the network events).
    fn net_json(r: &tango_session::pvp::NetReport) -> Value {
        let (lat, jit, loss, drop_left, freeze_left) = tango_net::netdbg::status();
        let ratio = if r.frames_sent > 0 { r.resends as f64 / r.frames_sent as f64 } else { 0.0 };
        json!({
            "players": r.players,
            "local_player": r.local_player,
            "host_seat": r.host_seat,
            "is_host": r.host_seat == r.local_player as usize,
            "migrations": r.migrations,
            "migrating": r.migrating.as_ref().map(|(n, me)| json!({"successor": n, "is_me": me})),
            "waiting_for": r.waiting_for.as_ref().map(|(n, s)| json!({"name": n, "seconds_left": s})),
            "rejoin_holds": r.rejoin_holds.iter().map(|(seat, n, s)| json!({"seat": seat, "name": n, "seconds_left": s})).collect::<Vec<_>>(),
            "reconnecting": r.reconnecting,
            "silence": r.reconnecting || r.waiting_for_peer,
            "remote_disconnected": r.remote_disconnected,
            "booting": r.booting,
            "waiting_for_peer": r.waiting_for_peer,
            "gone_seats": (0..8).filter(|s| r.gone_mask & (1 << s) != 0).collect::<Vec<_>>(),
            "input_delay": r.frame_delay,
            "skew": r.skew,
            "lead": r.lead,
            "rollback": {"last_depth": r.depth, "count": r.rollbacks, "ticks_resimulated": r.rolled_ticks},
            "tps": (r.tps as f64 * 10.0).round() / 10.0,
            "fps_target": (r.fps_target as f64 * 10.0).round() / 10.0,
            "frames_sent": r.frames_sent,
            "resends": r.resends,
            "resend_ratio": (ratio * 1000.0).round() / 1000.0,
            "links": r.links.iter().map(|l| json!({
                "index": l.index,
                "rtt_ms": ms(l.rtt_ms), "rtt_median_ms": ms(l.rtt_median_ms), "jitter_ms": ms(l.jitter_ms),
                "health": l.health, "give_up_in_s": ms(l.give_up_in_s), "given_up": l.given_up,
                "path": l.route.as_ref().map(|x| if x.relayed { "relay" } else { "direct" }),
                "ice": l.route.as_ref().map(|x| json!({
                    "local_type": x.local_type, "remote_type": x.remote_type,
                    "local_candidates": x.local_candidates, "remote_candidates": x.remote_candidates,
                    "candidate_counts": "host/srflx/prflx/relay",
                })),
            })).collect::<Vec<_>>(),
            "faults": {"latency_ms": lat, "jitter_ms": jit, "loss_pct": loss, "drop_left_s": drop_left, "freeze_left_s": freeze_left,
                       "injected_drops": tango_net::netdbg::INJECTED_DROPS.load(std::sync::atomic::Ordering::Relaxed),
                       "injected_delayed": tango_net::netdbg::INJECTED_DELAYED.load(std::sync::atomic::Ordering::Relaxed)},
        })
    }

    impl App {
        pub(in crate::app) fn ai_debug_tick(&mut self) -> iced::Task<Message> {
            if !self.ai.enabled() {
                return iced::Task::none();
            }
            let mut tasks: Vec<iced::Task<Message>> = Vec::new();
            let solo = self.session.active_as::<crate::session::singleplayer::SinglePlayerSession>().is_some();
            let pvp = self.session.active_as::<crate::session::pvp::PvpSession>();
            let report = pvp.map(|p| p.net_report());
            let depth_max = pvp.map_or(0, |p| p.take_depth_max());
            let session = if solo {
                "offline"
            } else if pvp.is_some() {
                "online"
            } else if self.session.is_active() {
                "other"
            } else {
                "none"
            };
            dbg::set_local(
                dbg::LocalInfo { session: session.into(), seat: tango_library::online::room_local_seat() },
                report.as_ref().map_or(Value::Null, net_json),
            );
            if let Some(r) = report.as_ref() {
                if depth_max > 0 {
                    dbg::push_event(json!({"event": "rollback", "max_depth": depth_max, "count": r.rollbacks, "ticks_resimulated": r.rolled_ticks}));
                }
                let now = Prev {
                    health: r.links.iter().map(|l| (l.health, l.given_up)).collect(),
                    route: r.links.iter().map(|l| l.route.as_ref().map(|x| format!("{}->{}", x.local_type, x.remote_type))).collect(),
                    reconnecting: r.reconnecting,
                    remote_disconnected: r.remote_disconnected,
                    host_seat: r.host_seat,
                    migrations: r.migrations,
                    migrating: r.migrating.clone(),
                    holds: r.rejoin_holds.iter().map(|h| (h.0, h.1.clone())).collect(),
                    booting: r.booting,
                    waiting_for_peer: r.waiting_for_peer,
                };
                if let Some(prev) = self.ai.prev.as_ref() {
                    if prev != &now {
                        if prev.health != now.health || prev.route != now.route || prev.reconnecting != now.reconnecting
                            || prev.remote_disconnected != now.remote_disconnected || prev.booting != now.booting || prev.waiting_for_peer != now.waiting_for_peer
                        {
                            dbg::push_event(json!({"event": "link", "reconnecting": now.reconnecting, "remote_disconnected": now.remote_disconnected,
                                "booting": now.booting, "waiting_for_peer": now.waiting_for_peer,
                                "links": net_json(r)["links"]}));
                        }
                        if prev.host_seat != now.host_seat || prev.migrations != now.migrations || prev.migrating != now.migrating {
                            dbg::push_event(json!({"event": "migration", "host_seat": now.host_seat, "migrations": now.migrations,
                                "migrating": now.migrating.as_ref().map(|(n, me)| json!({"successor": n, "is_me": me}))}));
                        }
                        if prev.holds != now.holds {
                            dbg::push_event(json!({"event": "rejoin", "holds": r.rejoin_holds.iter().map(|(seat, n, s)| json!({"seat": seat, "name": n, "seconds_left": s})).collect::<Vec<_>>()}));
                        }
                    }
                }
                self.ai.prev = Some(now);
            } else {
                self.ai.prev = None;
            }
            // (a) the pad
            if let Some(word) = dbg::pad_word(Instant::now()) {
                self.session.set_scripted_keys(word);
            }
            // a checkpoint to boot into: once the first offline session is up
            if solo && dbg::boot_checkpoint_pending() {
                if let Some(name) = dbg::take_boot_checkpoint() {
                    match dbg::ask_console(dbg::CoreReq::CheckpointLoad { name: name.clone() }, std::time::Duration::from_secs(5)) {
                        Ok(v) => log::info!("ai-debug: booted into checkpoint {name}: hash match {}", v["match"]),
                        Err(e) => log::error!("ai-debug: boot checkpoint {name}: {e}"),
                    }
                }
            }
            // (d) the commands of the app
            let calls: Vec<AppCall> = match self.ai.rx.as_ref() {
                Some(rx) => {
                    let rx = rx.lock().unwrap();
                    std::iter::from_fn(|| rx.try_recv().ok()).collect()
                }
                None => Vec::new(),
            };
            for call in calls {
                let out = match call.name.as_str() {
                    "screenshot" => self.ai_screenshot(),
                    "type" => self.ai_type(call.args["text"].as_str().unwrap_or("")),
                    "start_offline" => {
                        tasks.push(iced::Task::done(Message::Play(crate::tabs::play::Message::PlayOfflinePressed)));
                        Ok(json!({"starting": true}))
                    }
                    "inject" => ai_inject(&call.args),
                    other => Err(format!("the app has no `{other}`")),
                };
                let _ = call.reply.send(out);
            }
            iced::Task::batch(tasks)
        }

        fn ai_screenshot(&self) -> Result<Value, String> {
            let s = self.session.active().ok_or("no session")?;
            let (mut w, mut h) = s.frame_size();
            let rgba = s.frame();
            // (the Dual Strike tilt draws a larger picture: a whole multiple of the console's)
            if rgba.len() != (w * h * 4) as usize && w * h > 0 {
                let k = ((rgba.len() as f64 / (w * h * 4) as f64).sqrt().round()) as u32;
                (w, h) = (w * k, h * k);
            }
            let img = image::RgbaImage::from_raw(w, h, rgba).ok_or("the frame is not (yet) w x h")?;
            let mut png = Vec::new();
            img.write_to(&mut std::io::Cursor::new(&mut png), image::ImageFormat::Png).map_err(|e| e.to_string())?;
            Ok(json!({"width": w, "height": h, "png_b64": dbg::server::b64(&png),
                      "what": "the session's own window picture (the game frame only)",
                      "raw_console_frame": false}))
        }

        fn ai_type(&self, text: &str) -> Result<Value, String> {
            let solo = self.session.active_as::<crate::session::singleplayer::SinglePlayerSession>().ok_or("typing works in an offline session (the in-game lobby's entry pages)")?;
            let mut read = |a: u32, b: &mut [u8]| {
                solo.peek(a, b);
            };
            let mut write = |a: u32, b: &[u8]| {
                solo.poke(a, b);
            };
            let taken = tango_library::online::type_chars(&mut read, &mut write, text.as_bytes());
            Ok(json!({"typed": taken, "chars": text.len()}))
        }
    }

    /// `inject`: network faults, runtime. `op`: `latency` (latency_ms, jitter_ms, loss_pct), `drop` (seconds: this side's
    /// sends vanish: a dead link), `freeze` (seconds: they are held and released together), `clear`, `status`.
    fn ai_inject(a: &Value) -> Result<Value, String> {
        use tango_net::netdbg as n;
        if !n::test_mode() {
            return Err("refused: not started with TANGOAW2_AI_DEBUG_TEST=1".into());
        }
        let f = |k: &str| a[k].as_f64();
        match a["op"].as_str().unwrap_or("") {
            "latency" => n::set_link(f("latency_ms").unwrap_or(0.0) as u32, f("jitter_ms").unwrap_or(0.0) as u32, f("loss_pct").unwrap_or(0.0) as f32),
            "drop" => n::drop_for(f("seconds").ok_or("`seconds` is required")?),
            "freeze" => n::freeze_for(f("seconds").ok_or("`seconds` is required")?),
            "clear" => n::clear(),
            "status" => {}
            other => return Err(format!("unknown op `{other}` (latency, drop, freeze, clear, status)")),
        }
        log::warn!("ai-debug: inject {a}");
        let (latency_ms, jitter_ms, loss_pct, drop_left_s, freeze_left_s) = n::status();
        Ok(json!({"latency_ms": latency_ms, "jitter_ms": jitter_ms, "loss_pct": loss_pct, "drop_left_s": drop_left_s, "freeze_left_s": freeze_left_s,
                  "note": "affects what THIS peer sends; the other peer sees a slow, lossy or silent link"}))
    }
}

#[cfg(feature = "gamesupport-aw2")]
pub use on::AiDebug;

#[cfg(not(feature = "gamesupport-aw2"))]
#[derive(Default)]
pub struct AiDebug;

#[cfg(not(feature = "gamesupport-aw2"))]
impl AiDebug {
    pub fn enabled(&self) -> bool {
        false
    }
    pub fn start(_: &crate::config::Config) -> Self {
        Self
    }
}

#[cfg(not(feature = "gamesupport-aw2"))]
impl super::App {
    pub(in crate::app) fn ai_debug_tick(&mut self) -> iced::Task<super::Message> {
        iced::Task::none()
    }
}
