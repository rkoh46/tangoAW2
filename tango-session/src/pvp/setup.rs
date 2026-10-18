//! Assemble a session's shared state, transport, drivers, and recording.

use super::driver::{BootPieces, DriveContext};
use super::recording::build_replay_writer;
use super::supervisor::{spawn_primed_announcer, spawn_room_primed_announcer, spawn_supervisor, Pauses, RoomCtx, SupGroup, SupervisorContext};
use super::{EndState, Metrics, PvpBoot, PvpSession, PvpSessionArgs, Seat, TpsCounter};
use std::sync::atomic::{AtomicBool, AtomicU32, Ordering};
use std::sync::{Arc, Mutex};
use tango_net_protocol::derive::pick_local_player_index;

use super::IN_MATCH_HEARTBEAT;

impl PvpSession {
    /// Build the live match from [`PvpSessionArgs`].
    ///
    /// Async because the lobby loop holds the data-channel `Receiver`
    /// until it observes its cancellation and exits (`Link::bring_up`
    /// awaits its handback). Everything slow happens after this
    /// returns: the session is live as soon as the exchange is, and the
    /// pair is booted and primed on the drive loop underneath it (see
    /// [`PvpBoot`]).
    ///
    /// Hands back the session, the thing the host drives, and the
    /// session's audio stream — the local core's samples at the args'
    /// `sample_rate`, rate control following the drive loop's published
    /// fps target, silent until the boot lands.
    pub async fn new(args: PvpSessionArgs<'_>) -> Result<(Self, PvpBoot, crate::audio::Stream), crate::Error> {
        let PvpSessionArgs {
            local,
            remote,
            pre_match,
            frame_delay,
            disable_bgm,
            replays,
            stats_sink,
            sample_rate,
            room,
        } = args;
        let Seat {
            game: local_game,
            rom: local_rom,
            sram: local_sram,
        } = local;
        let Seat {
            game: remote_game,
            rom: remote_rom,
            sram: remote_sram,
        } = remote;
        let expected_fps = crate::local::native_fps(local_game);
        let cancellation_token = tokio_util::sync::CancellationToken::new();

        // The engine gets a head start on the pair the boot will run —
        // the awaits below (handoff, transport bring-up) are where a
        // browser's worker threads get the event-loop turns their
        // startup needs.
        let players = room.as_ref().map_or(2, |r| r.players.len().clamp(2, tango_match::MAX_SEATS));
        local_game.pvp.prepare(2);

        // Player index off the shared RNG seed, same negotiation as ever:
        // both peers derive the same assignment, mirrored.
        use rand::SeedableRng;
        let mut rng = rand_pcg::Mcg128Xsl64::from_seed(pre_match.terms.rng_seed);
        let drawn = pick_local_player_index(&mut rng, pre_match.terms.is_offerer);
        // A room made in a game's own lobby: its host takes seat 0.
        let local_player_index = tango_net_protocol::control::room_host_seat(
            pre_match.terms.local_settings.match_type.1,
            pre_match.terms.remote_settings.match_type.1,
        )
        .unwrap_or(drawn);
        // A room's seats are its roster's order.
        let local_player_index = room.as_ref().map_or(local_player_index, |r| r.seat as u8);

        // The match clock, pinned into both carts' RTC and recorded in the
        // replay metadata so playback re-primes to the identical state.
        let rtc_time = std::time::UNIX_EPOCH + std::time::Duration::from_millis(pre_match.terms.match_ts);

        // Replay writer. Failing to open it shouldn't kill the
        // match — log and continue without recording.
        // (a match resumed from a saved state cannot be replayed from its start: it is not recorded)
        let resumed = room.as_ref().is_some_and(|r| r.resume_state.is_some());
        let (replay_writer, replay_path) = match replays.filter(|_| !resumed) {
            None => (None, None),
            Some(store) => {
                match build_replay_writer(
                    store,
                    &pre_match,
                    local_game,
                    remote_game,
                    local_player_index,
                    &local_sram,
                    &remote_sram,
                    room.as_ref().map(|r| r.players.as_slice()),
                ) {
                    Ok((writer, path)) => (Some(writer), Some(path)),
                    Err(e) => {
                        log::warn!("pvp: replay writer open failed: {e}");
                        (None, None)
                    }
                }
            }
        };

        // Assemble the peer link from the lobby handoff — this awaits the
        // lobby loop releasing the reliable receiver (typically a few ms after
        // take_pre_match flipped the cancel) and starts the in-match
        // retransmit heartbeat.
        let room_host = room.as_ref().is_some_and(|r| r.is_host) && players > 2;
        let solo_host = room.as_ref().is_some_and(|r| r.is_host) && players == 2;
        let room_meta = room.as_ref().map(|r| (r.players.clone(), r.seat, r.host_seat, r.is_host, r.match_id));
        let resume_state = room.as_ref().and_then(|r| r.resume_state.clone());
        let resumed_match = resume_state.is_some().then(|| room.as_ref().map_or(0, |r| r.match_id));
        let suspend_sink = room.as_ref().and_then(|r| r.suspend_sink.clone());
        let extra_parts = room.map(|r| r.extra_links).unwrap_or_default();
        let mut links = vec![Arc::new(
            tango_net::link::Link::bring_up(pre_match.link_parts, IN_MATCH_HEARTBEAT, cancellation_token.clone())
                .await?,
        )];
        for parts in extra_parts {
            links.push(Arc::new(
                tango_net::link::Link::bring_up(parts, IN_MATCH_HEARTBEAT, cancellation_token.clone()).await?,
            ));
        }
        let link = links[0].clone();
        let in_matches: Vec<tango_net::InMatchTx> = links.iter().map(|l| l.in_match().clone()).collect();

        let end = EndState::default();
        if let Some(m) = room_meta.as_ref() {
            end.host_seat.store(m.2 as u8, Ordering::Release);
        }
        let local_input = crate::InputCell::new();
        let completed = Arc::new(AtomicBool::new(false));
        // All screens until the host says which it is arranging to show.
        let displayed_screens = Arc::new(std::sync::atomic::AtomicU8::new(u8::MAX));
        let frame_delay = Arc::new(AtomicU32::new(frame_delay));
        let metrics = Arc::new(Metrics::default());
        // Seeded rather than left at zero: the host paces the boot
        // itself off this, and the audio stream's rate control reads it
        // from the moment the host binds the stream — both of which
        // start before the drive loop first publishes a target.
        metrics.fps_target.store(expected_fps.to_bits(), Ordering::Relaxed);
        let drive_paused = Arc::new(crate::PauseGate::new(false));
        // ~1 s window at 60 Hz.
        let tps_counter = Arc::new(Mutex::new(TpsCounter::new(60)));
        let layout = local_game.pvp.screen_layout(tango_match::SessionMode::PvP {
            match_type: pre_match.terms.match_type,
        });
        let screen = crate::Framebuffer::new(&layout);
        let wake = Arc::new(tokio::sync::Notify::new());
        // The two-sided ready gate. Priming takes as long as the machine
        // running it takes, so each peer announces when its own pair
        // reaches the link battle and neither ticks until both have.
        let local_primed = Arc::new(AtomicBool::new(false));
        let boot_cancel = Arc::new(AtomicBool::new(false));
        let peer_primed: Vec<Arc<AtomicBool>> = links.iter().map(|l| l.peer_primed()).collect();
        let announce_primed = Arc::new(tokio::sync::Notify::new());

        // A game whose engine reports no chip events folds the rest of
        // the stats without them — the aggregator is the same for all.
        let stats = Arc::new(Mutex::new(tango_match::analysis::StatsBuilder::new()));

        // Remote input events flow receive-task → drive thread over this
        // queue; the rennet reassembly in PvpReceiver already ordered and
        // deduplicated them (one Input per remote tick, in tick order).
        let (event_tx, event_rx) = std::sync::mpsc::channel::<(usize, tango_net::data::Input)>();

        // The sender pump: the drive thread pushes one Input per advance;
        // the pump ships each as a rennet frame over the unreliable channel.
        let senders: Vec<Option<tango_net::PvpSender>> =
            in_matches.iter().map(|im| Some(tango_net::PvpSender::new(im.clone()))).collect();

        // Pair-order arrays: core 0 always runs player 0's game, on both
        // peers, so priming and simulation are bit-identical across the pair.
        let (roms, saves, supports) = if local_player_index == 0 {
            (
                [local_rom.as_ref().clone(), remote_rom.as_ref().clone()],
                [local_sram, remote_sram],
                [local_game.pvp, remote_game.pvp],
            )
        } else {
            (
                [remote_rom.as_ref().clone(), local_rom.as_ref().clone()],
                [remote_sram, local_sram],
                [remote_game.pvp, local_game.pvp],
            )
        };

        // Everything the match needs to boot, handed back for the host
        // to drive: the pair is single-threaded by design and priming it
        // is seconds of emulation, so *where* that happens is the host's
        // call — a drive thread on a desktop, the event loop in a
        // browser. Either way the session is already on screen for it.
        let pieces = BootPieces {
            roms,
            saves,
            pvp: supports,
            peer_rom: tango_match::PeerRom {
                code: *remote_game.rom_code,
                revision: remote_game.revision,
            },
            match_type: pre_match.terms.match_type,
            rng_seed: pre_match.terms.rng_seed,
            rtc: rtc_time,
            local_player: local_player_index as usize,
            players,
            present_delay: frame_delay.load(Ordering::Relaxed),
            disable_bgm,
            resume_state,
        };
        let mailbox = Arc::new(super::migrate::Mailbox::default());
        let drive = DriveContext {
            mig: mailbox.clone(),
            local_input: local_input.clone(),
            frame_delay: frame_delay.clone(),
            metrics: metrics.clone(),
            drive_paused: drive_paused.clone(),
            cancel: cancellation_token.clone(),
            completed: completed.clone(),
            displayed_screens: displayed_screens.clone(),
            end: end.clone(),
            event_rx,
            senders,
            room_host,
            solo_host,
            in_matches: in_matches.clone(),
            replay_writer,
            stats: stats.clone(),
            stats_key: replay_path.clone(),
            stats_sink,
            tps_counter: tps_counter.clone(),
            screen: screen.clone(),
            wake: wake.clone(),
            local_primed: local_primed.clone(),
            peer_primed: peer_primed.clone(),
            announce_primed: announce_primed.clone(),
            local_player: local_player_index as usize,
            boot_cancel: boot_cancel.clone(),
            host_seat: room_meta.as_ref().map_or(0, |m| m.2),
            suspend: room_meta.as_ref().zip(suspend_sink).map(|(m, sink)| super::driver::SuspendCtx {
                match_id: m.4,
                players: m.0.clone(),
                seat: m.1,
                match_ts: pre_match.terms.match_ts,
                match_type: pre_match.terms.match_type,
                save: pre_match.terms.local_save_data.clone(),
                sim_version: local_game.pvp.sim_version(),
                sink,
            }),
        };

        // The session's audio ring, made before the pair that feeds it
        // exists: the host binds this stream at construction, and the
        // ring simply reads empty — so the stream primes — through the
        // seconds of priming walk the boot below runs.
        let (audio_in, audio_out) = crate::audio::ring();
        let audio = crate::audio::Stream::new(
            audio_out,
            expected_fps,
            {
                let metrics = metrics.clone();
                move || f32::from_bits(metrics.fps_target.load(Ordering::Relaxed))
            },
            sample_rate,
        );
        let prime_error = Arc::new(Mutex::new(None));
        let boot = PvpBoot {
            pending: Some((pieces, drive)),
            driver: None,
            audio: Some(audio_in),
            prime_error: prime_error.clone(),
            expected_fps,
            metrics: metrics.clone(),
            wake: wake.clone(),
            backend: local_game.pvp,
        };

        // Announce our own prime as soon as the boot finishes. It rides
        // the reliable control channel, so an accepted send is a
        // delivered one; a rejected send means that channel is gone and
        // ends the match. (The supervisor re-announces after a
        // reconnect, whose rebuild drops anything undelivered.)
        if room_host {
            spawn_room_primed_announcer(
                links.clone(),
                local_primed.clone(),
                announce_primed,
                end.clone(),
                cancellation_token.clone(),
            );
        } else {
            spawn_primed_announcer(
                link.clone(),
                local_primed.clone(),
                announce_primed,
                end.clone(),
                cancellation_token.clone(),
            );
        }

        // Receive pump + link supervisor: reads peer frames into the event
        // queue, watches for stalls, and runs the transparent reconnect.
        let supervisor_done = tokio_util::sync::CancellationToken::new();
        let group = Arc::new(SupGroup::new(supervisor_done.clone()));
        let pauses = Arc::new(Pauses::new(drive_paused.clone()));
        let room_ctx = room_meta.as_ref().map(|m| {
            Arc::new(RoomCtx {
                players: m.0.clone(),
                host_seat: m.2,
                is_host: m.3,
                links: links.clone(),
                clock: web_time::Instant::now(),
            })
        });
        let links_shared = Arc::new(Mutex::new(links.clone()));
        // A room of more than two players whose links come from the matchmaking server can go on without its host.
        let mig = room_meta
            .as_ref()
            .filter(|m| m.0.len() > 2)
            .zip(link.matchmaking())
            .map(|(m, (endpoint, use_relay, seed))| {
                Arc::new(super::migrate::MigHandle {
                    end: end.clone(),
                    pauses: pauses.clone(),
                    wake: wake.clone(),
                    cancel: cancellation_token.clone(),
                    completed: completed.clone(),
                    metrics: metrics.clone(),
                    event_tx: event_tx.clone(),
                    local_primed: local_primed.clone(),
                    mailbox: mailbox.clone(),
                    links: links_shared.clone(),
                    group: group.clone(),
                    players: m.0.clone(),
                    my_seat: m.1,
                    seed,
                    endpoint,
                    use_relay,
                    heartbeat: IN_MATCH_HEARTBEAT,
                    links_pending: Mutex::new(None),
                })
            });
        for (link_idx, (link, in_match)) in links.iter().zip(in_matches.iter()).enumerate() {
            group.add();
            spawn_supervisor(SupervisorContext {
                link: link.clone(),
                in_match: in_match.clone(),
                link_idx,
                peer_seat: room_ctx.as_ref().map_or(0, |r| r.seat_of_link(link_idx)),
                event_tx: event_tx.clone(),
                end: end.clone(),
                completed: completed.clone(),
                cancel: cancellation_token.clone(),
                metrics: metrics.clone(),
                pauses: pauses.clone(),
                wake: wake.clone(),
                room: room_ctx.clone(),
                last_rx: Arc::new(std::sync::atomic::AtomicU64::new(0)),
                local_primed: local_primed.clone(),
                group: group.clone(),
                mig: mig.clone(),
            });
        }
        drop(event_tx);

        let session = Self {
            local_game,
            local_player_index,
            local_input,
            completed,
            displayed_screens: displayed_screens.clone(),
            end,
            tps_counter,
            cancellation_token,
            supervisor_done,
            links: links_shared,
            players,
            local_primed,
            peer_primed,
            prime_error,
            boot_cancel,
            metrics,
            resumed_match,
            link_code: pre_match.terms.link_code,
            remote_nickname: pre_match.terms.remote_settings.nickname,
            frame_delay,
            stats,
            replay_path,
            layout,
            screen,
            wake,
            started_at: web_time::Instant::now(),
        };
        Ok((session, boot, audio))
    }
}
