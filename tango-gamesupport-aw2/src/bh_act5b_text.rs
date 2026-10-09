//! The design bible's dialogue for M23-M28 and M31 (docs/BH_CAMPAIGN.md 4.6, 4.7a), converted by a script from the
//! voice-reviewed design: a row is one box, `@IF CO` groups are `.only` / `.with` lines, `@IF OTHER` one line for each other CO.

#![allow(unused_imports)]

use crate::bh_campaign::roster;
use crate::custom_campaign::{co, colour, unit, *};

fn troop(text: &'static str) -> Line {
    Line::soldier(colour::BLACK_HOLE, text)
}
fn say(c: u8, text: &'static str) -> Line {
    Line::say(c, text)
}
fn happy(c: u8, text: &'static str) -> Line {
    Line::feel(c, Mood::Happy, text)
}
fn sad(c: u8, text: &'static str) -> Line {
    Line::feel(c, Mood::Sad, text)
}

pub fn m23_pre() -> Vec<Line> {
    vec![
        troop("Orange Star. Laboratory 7. Glass halls, humming walls."),
        say(co::LASH, "Heehee! Visitors! Do you know how long it has been?"),
        say(co::LASH, "The Ethics Board shut my projects. Seventeen! Pooh!"),
        say(co::LASH, "But my toys? Still here!"),
        say(co::LASH, "Meet Oozium! And Black Bomb! And... other nouns!"),
        say(co::LASH, "Impress me and I will consider your funding."),
        say(co::LASH, "Lose, and I will consider your brain."),
        say(co::JUGGER, "SCIENTIFIC SUBJECT: LASH. FASCINATING.").only(co::JUGGER),
        say(co::LASH, "Ooh, a talking robot! Can I open him? Only a little!").only(co::JUGGER),
        say(co::JUGGER, "NEGATIVE. YOU FIRST.").only(co::JUGGER),
        say(co::VON_BOLT, "Funding! Did she say funding? Not mine.").only(co::VON_BOLT),
        say(co::LASH, "Old man! You smell like money! Come, come!").only(co::VON_BOLT),
        troop("Ma'am, is that Oozium looking at me?"),
        say(co::LASH, "Oh yes. He is hungry."),
        troop("...Gerald, behind me."),
    ]
}

pub fn m23_day_5() -> Vec<Line> {
    vec![
        say(co::LASH, "Black Bomb away! Count to three! Heehee!"),
    ]
}

pub fn m23_day_11() -> Vec<Line> {
    vec![
        say(co::LASH, "Another test! Another screaming! Perfect!"),
    ]
}

pub fn m23_post() -> Vec<Line> {
    vec![
        sad(co::LASH, "Oh no! Oh no, oh no... no, wait. That was excellent!"),
        say(co::LASH, "You beat my toys! I am so happy! Why would I join?"),
        say(co::JUGGER, "BECAUSE I AM A TOY YOU HAVE NOT OPENED.").only(co::JUGGER),
        say(co::JUGGER, "FUNDING: UNLIMITED. ETHICS BOARD: ABSENT.").only(co::JUGGER),
        say(co::LASH, "Unlimited?! Absent?! Say it again!").only(co::JUGGER),
        say(co::JUGGER, "UNLIMITED. ABSENT.").only(co::JUGGER),
        say(co::LASH, "Eeeeee!").only(co::JUGGER),
        say(co::VON_BOLT, "Funding, child? Kehh! A loan! At interest. Show returns.").only(co::VON_BOLT),
        say(co::LASH, "A loan? No board, no rules? Ooh, yes!").only(co::VON_BOLT),
        say(co::VON_BOLT, "I like returns. Show me a death ray.").only(co::VON_BOLT),
        say(co::LASH, "I will show you ten!").only(co::VON_BOLT),
        say(co::STURM, "Black Hole has no board. No limits. No complaints.").only(co::STURM),
        say(co::HAWKE, "Black Hole has no board. No limits. No complaints.").only(co::HAWKE),
        say(co::KOAL, "Black Hole has no board. No limits. No complaints.").only(co::KOAL),
        say(co::KINDLE, "Black Hole has no board. No limits. No complaints.").only(co::KINDLE),
        say(co::FLAK, "Black Hole has no board. No limits. No complaints.").only(co::FLAK),
        say(co::LASH, "No complaints? That is suspicious. I love it!").only(co::STURM),
        say(co::LASH, "No complaints? That is suspicious. I love it!").only(co::HAWKE),
        say(co::LASH, "No complaints? That is suspicious. I love it!").only(co::KOAL),
        say(co::LASH, "No complaints? That is suspicious. I love it!").only(co::KINDLE),
        say(co::LASH, "No complaints? That is suspicious. I love it!").only(co::FLAK),
        say(co::LASH, "I accept! I get a lab. And the Oozium. Keep Oozium!"),
        troop("Ma'am, may I keep my biscuit?"),
        say(co::LASH, "What biscuit? Ooh. ...Can I study it?"),
        troop("No."),
        say(co::LASH, "Aww."),
        say(co::LASH, "Oh! Sub-basement four has someone. A cancelled project."),
        say(co::LASH, "Project Echo. He is very sad."),
        say(co::HAWKE, "Remember that. And keep the toys indoors."),
        say(co::LASH, "Heehee. Never."),
    ]
}

pub fn m23_map() -> Vec<Line> {
    vec![
        say(co::LASH, "Corporal Crumb! Your biscuit's half-life?"),
        troop("He's a Private biscuit, ma'am."),
        say(co::LASH, "Ooh, a loophole!"),
        say(co::JUGGER, "SUBJECT'S BISCUIT: STILL DEFENDED. ADMIRABLE."),
        troop("A poster says Mr Adder loves capes and a captain."),
        troop("Lady Kindle and the Marshal, sir. Both tall."),
    ]
}

pub fn m24_pre() -> Vec<Line> {
    vec![
        troop("The Orange Star Sky Gala. Cameras. Cheering."),
        say(co::ADDER, "Ladies and gentlemen! Behold: the show!"),
        say(co::ADDER, "I am Adder. You may admire me."),
        say(co::ADDER, "Orange Star employs me to look good in front of planes."),
        say(co::ADDER, "I would like to look good in front of an audience."),
        say(co::ADDER, "A real one. With stakes."),
        say(co::ADDER, "Win in the sky and I shall consider joining."),
        say(co::KINDLE, "Adder, darling. You have put on weight.").only(co::KINDLE),
        say(co::ADDER, "That is CAPE, Kindle!").only(co::KINDLE),
        say(co::KINDLE, "Of course it is.").only(co::KINDLE),
        say(co::HAWKE, "Pilots are marketing. The useful ones are rare.").only(co::HAWKE),
        say(co::ADDER, "The useful ones are rare. Flattering!").only(co::HAWKE),
    ]
}

pub fn m24_day_4() -> Vec<Line> {
    vec![
        say(co::ADDER, "My profile! Photograph me from the left!"),
    ]
}

pub fn m24_day_9() -> Vec<Line> {
    vec![
        say(co::ADDER, "Do you see the grace? The line of the dive?"),
    ]
}

pub fn m24_post() -> Vec<Line> {
    vec![
        sad(co::ADDER, "My hair. My perfect hair. You ruined the shot."),
        say(co::ADDER, "Well? Why join the dark side? Look at it."),
        say(co::KINDLE, "Because I outshine you there. Come and see.").only(co::KINDLE),
        say(co::ADDER, "Impossible!").only(co::KINDLE),
        say(co::KINDLE, "Join. Try.").only(co::KINDLE),
        say(co::ADDER, "...Only to prove you wrong.").only(co::KINDLE),
        say(co::HAWKE, "Black Hole has a sky no one else may fly. Yours.").only(co::HAWKE),
        say(co::HAWKE, "And a medal for every sortie.").only(co::HAWKE),
        say(co::ADDER, "Every sortie?").only(co::HAWKE),
        say(co::HAWKE, "With a cape.").only(co::HAWKE),
        say(co::ADDER, "Where do I sign?").only(co::HAWKE),
        say(co::STURM, "Our sky is empty. We need a star. Be it.").only(co::STURM),
        say(co::VON_BOLT, "Our sky is empty. We need a star. Be it.").only(co::VON_BOLT),
        say(co::KOAL, "Our sky is empty. We need a star. Be it.").only(co::KOAL),
        say(co::JUGGER, "Our sky is empty. We need a star. Be it.").only(co::JUGGER),
        say(co::FLAK, "Our sky is empty. We need a star. Be it.").only(co::FLAK),
        say(co::LASH, "Our sky is empty. We need a star. Be it.").only(co::LASH),
        say(co::ADDER, "A star. Hmm. Yes.").only(co::STURM),
        say(co::ADDER, "A star. Hmm. Yes.").only(co::VON_BOLT),
        say(co::ADDER, "A star. Hmm. Yes.").only(co::KOAL),
        say(co::ADDER, "A star. Hmm. Yes.").only(co::JUGGER),
        say(co::ADDER, "A star. Hmm. Yes.").only(co::FLAK),
        say(co::ADDER, "A star. Hmm. Yes.").only(co::LASH),
        say(co::ADDER, "I accept. My profile deserves better."),
        say(co::ADDER, "Let it be known: the villains finally have style."),
        say(co::KINDLE, "Do not push your luck, darling."),
    ]
}

pub fn m24_map() -> Vec<Line> {
    vec![
        troop("Mr Adder signed my helmet!"),
        say(co::ADDER, "I signed it \"Adder, the star\". You are welcome."),
        troop("It's very shiny."),
        troop("Gerald asked for one, too."),
        say(co::ADDER, "A biscuit autograph. ...Charming."),
    ]
}

pub fn m25_pre() -> Vec<Line> {
    vec![
        say(co::SAMI, "Orange Star Port! You will not pass my soldiers!"),
        say(co::SAMI, "Boots first, grunts! Armour is support. Move out!"),
        say(co::HACHI, "Welcome, kid! Hachi's Shop! Closing-down sale!"),
        say(co::HACHI, "Tell young Andy his wrench is on my shelf. Free rental!"),
        say(co::HACHI, "Everything half off! Even the second front!"),
        say(co::SAMI, "Hachi, this is a battle."),
        say(co::HACHI, "Battles have customers! ...Mostly bad ones."),
        say(co::HAWKE, "A harbour and a market. Choose your hands."),
    ]
}

pub fn m25_day() -> Vec<Line> {
    vec![
        say(co::STURM, "The market is ours. Reporting to the harbour.").only_partner(co::STURM),
        say(co::VON_BOLT, "The market is ours. Reporting to the harbour.").only_partner(co::VON_BOLT),
        say(co::HAWKE, "The market is ours. Reporting to the harbour.").only_partner(co::HAWKE),
        say(co::KOAL, "The market is ours. Reporting to the harbour.").only_partner(co::KOAL),
        say(co::KINDLE, "The market is ours. Reporting to the harbour.").only_partner(co::KINDLE),
        say(co::JUGGER, "The market is ours. Reporting to the harbour.").only_partner(co::JUGGER),
        say(co::FLAK, "The market is ours. Reporting to the harbour.").only_partner(co::FLAK),
        say(co::LASH, "The market is ours. Reporting to the harbour.").only_partner(co::LASH),
        say(co::ADDER, "The market is ours. Reporting to the harbour.").only_partner(co::ADDER),
    ]
}

pub fn m25_day_6() -> Vec<Line> {
    vec![
        say(co::HACHI, "Special offer! Buy two tanks, get a third angry!"),
    ]
}

pub fn m25_post() -> Vec<Line> {
    vec![
        sad(co::SAMI, "Retreat to the Gate! I will stand there myself!"),
        say(co::HACHI, "Sorry, sorry! The shop is closed! Permanently!"),
        say(co::SAMI, "Hachi!"),
        say(co::HACHI, "I mean... for today."),
    ]
}

pub fn m25_map() -> Vec<Line> {
    vec![
        troop("I found a hat in the shop! For Dennis the tank!"),
        troop("It's a colander."),
        troop("It's a fancy hat."),
    ]
}

pub fn m26_pre() -> Vec<Line> {
    vec![
        say(co::JAKE, "Yo! Jake's in the house! Hottest CO in Orange Star!"),
        say(co::COLIN, "I-I'm Colin! I've got, um, lots of money! Hi!"),
        say(co::GRIMM, "Grimm's here! Hit first, ask later! Or never! Har!"),
        say(co::JAKE, "Together we're unbeatable! Right? Guys? ...Guys?"),
        say(co::COLIN, "Y-yeah! ...Was that a threat?"),
        say(co::GRIMM, "Ha! Black Hole is afraid!"),
        say(co::HAWKE, "Three boys. Three flags. Defeat them in detail."),
        say(co::ADDER, "Children. A shame to hit them.").with(co::ADDER),
        say(co::JAKE, "Hey! I heard that, old man!").with(co::ADDER),
        say(co::ADDER, "I am a gentleman, thank you.").with(co::ADDER),
    ]
}

pub fn m26_day_8() -> Vec<Line> {
    vec![
        say(co::JAKE, "This is my plan! It's amazing!"),
        say(co::COLIN, "Whoa, it is!"),
        say(co::GRIMM, "It's just \"charge\"."),
        say(co::JAKE, "It's AMAZING charge!"),
    ]
}

pub fn m26_post() -> Vec<Line> {
    vec![
        sad(co::JAKE, "Fall back! Fall back, guys! Strategic fall back!"),
        say(co::COLIN, "We all fall back? T-together?"),
        say(co::GRIMM, "One more punch first! Then I retreat. Maybe!"),
        say(co::NELL, "Boys. Come home. ...Please come home."),
        say(co::JAKE, "...Yes, ma'am."),
        say(co::HAWKE, "She calls them boys. It is effective."),
    ]
}

pub fn m26_map() -> Vec<Line> {
    vec![
        troop("Sir, that Nell lady scares me."),
        troop("Why?"),
        troop("She did not shout. She asked."),
        troop("...Yes. That is worse."),
        troop("Sir, the clone fellow likes anyone who was made."),
        troop("Sir Sturm. And Doctor Lash, who made him, I think."),
    ]
}

pub fn m27_pre() -> Vec<Line> {
    vec![
        troop("Sunrise Plains. Wheat, a windmill, an Orange Star base."),
        say(co::ANDY, "I'm not scared! I'm just double-checking!"),
        say(co::ANDY, "Black Hole! You came to Orange Star! Not on my watch!"),
        happy(co::CLONE_ANDY, "Hey! It's my watch too, you know!"),
        say(co::ANDY, "...What?"),
        say(co::CLONE_ANDY, "I mean, it's OUR watch. Right? We're both Andy."),
        say(co::ANDY, "You're not Andy."),
        say(co::CLONE_ANDY, "Then who am I?"),
        say(co::ANDY, "...An Andy. A spare. Don't make me say it."),
        sad(co::CLONE_ANDY, "A spare. Yeah. Everyone says that."),
        say(co::LASH, "Project Echo! You look so well!").only(co::LASH),
        say(co::CLONE_ANDY, "Doctor Lash? You changed uniforms.").only(co::LASH),
        say(co::LASH, "Coats are coats! Come join us! Please?").only(co::LASH),
        say(co::STURM, "You were made. A made thing is a tool. I own tools.").only(co::STURM),
        say(co::CLONE_ANDY, "...Are you made, too?").only(co::STURM),
        say(co::STURM, "Not told. Not asked. I chose the world. Choose yours.").only(co::STURM),
        troop("Hello, sir. I am Crumb."),
        say(co::CLONE_ANDY, "I'm— I can fix any— ...uh. I'm Andy. Sort of."),
        say(co::CLONE_ANDY, "Everybody calls me Andy. It is not mine."),
        troop("Pick one you would answer to at three in the morning."),
        say(co::CLONE_ANDY, "Three in the morning..."),
    ]
}

pub fn m27_day_5() -> Vec<Line> {
    vec![
        say(co::ANDY, "He has my moves! ...He IS my moves!"),
    ]
}

pub fn m27_day_10() -> Vec<Line> {
    vec![
        happy(co::CLONE_ANDY, "Hey, I fixed your tank! ...Oops. That was yours."),
    ]
}

pub fn m27_post() -> Vec<Line> {
    vec![
        sad(co::CLONE_ANDY, "I lost. I'm... actually relieved?"),
        sad(co::ANDY, "Clone... come home."),
        say(co::CLONE_ANDY, "Home is a drawer, Andy. You know where I sleep."),
        say(co::ANDY, "...I didn't know that."),
        say(co::CLONE_ANDY, "Nobody did."),
        say(co::CLONE_ANDY, "Black Hole. Why should I join you?"),
        say(co::STURM, "Because I do not ask who you were copied from.").only(co::STURM),
        say(co::STURM, "I ask what you take next.").only(co::STURM),
        say(co::CLONE_ANDY, "...What I take next.").only(co::STURM),
        say(co::STURM, "Be useful. Walk with me.").only(co::STURM),
        say(co::CLONE_ANDY, "Okay. Okay! That I can do.").only(co::STURM),
        say(co::LASH, "Because I wrote your first line. Edit it!").only(co::LASH),
        say(co::LASH, "I made you. Un-make me by being better.").only(co::LASH),
        say(co::CLONE_ANDY, "...You are weirdly moving, Doctor.").only(co::LASH),
        say(co::LASH, "Thank you. Heehee.").only(co::LASH),
        say(co::VON_BOLT, "We have no copies. Only soldiers. Join us.").only(co::VON_BOLT),
        say(co::HAWKE, "We have no copies. Only soldiers. Join us.").only(co::HAWKE),
        say(co::KOAL, "We have no copies. Only soldiers. Join us.").only(co::KOAL),
        say(co::KINDLE, "We have no copies. Only soldiers. Join us.").only(co::KINDLE),
        say(co::JUGGER, "We have no copies. Only soldiers. Join us.").only(co::JUGGER),
        say(co::FLAK, "We have no copies. Only soldiers. Join us.").only(co::FLAK),
        say(co::ADDER, "We have no copies. Only soldiers. Join us.").only(co::ADDER),
        say(co::CLONE_ANDY, "No copies... I will try. Okay.").only(co::VON_BOLT),
        say(co::CLONE_ANDY, "No copies... I will try. Okay.").only(co::HAWKE),
        say(co::CLONE_ANDY, "No copies... I will try. Okay.").only(co::KOAL),
        say(co::CLONE_ANDY, "No copies... I will try. Okay.").only(co::KINDLE),
        say(co::CLONE_ANDY, "No copies... I will try. Okay.").only(co::JUGGER),
        say(co::CLONE_ANDY, "No copies... I will try. Okay.").only(co::FLAK),
        say(co::CLONE_ANDY, "No copies... I will try. Okay.").only(co::ADDER),
        happy(co::CLONE_ANDY, "Call me what the others call me. Clone Andy."),
        say(co::CLONE_ANDY, "Clone Andy. It's a name. It's MINE."),
        troop("Three in the morning, sir?"),
        say(co::CLONE_ANDY, "I would answer it at three in the morning. Yes!"),
        sad(co::ANDY, "He has a name. I never thought of that."),
    ]
}

pub fn m27_map() -> Vec<Line> {
    vec![
        say(co::STURM, "Corporal."),
        say(co::CLONE_ANDY, "Sir? I'm a Private!"),
        say(co::STURM, "Not for long. Walk with me."),
        happy(co::CLONE_ANDY, "Always, sir."),
        troop("Gerald says that is the start of a tag team."),
    ]
}

pub fn m28_map_before_the_mission() -> Vec<Line> {
    vec![
        troop("Sir! Alarm from home! The depot is surrounded!"),
        troop("Four armies at once! Orange, blue, green, yellow!"),
        say(co::HAWKE, "Nell. She sent them the moment we left."),
        say(co::HAWKE, "A diversion. And a test. She wants us home."),
        say(co::VON_BOLT, "My vault! The vault!"),
        troop("Sir! I left the flag at the depot!"),
        say(co::STURM, "Then we take it back."),
    ]
}

pub fn m28_pre() -> Vec<Line> {
    vec![
        troop("The Black Hole continent. The Black Wastes. Home."),
        say(co::RACHEL, "By the book: surround the fortress. No gaps."),
        say(co::OLAF, "Blue Moon is here! Ice for the Obelisk!"),
        say(co::EAGLE, "Green Earth owns the sky! Let's finish this, Sturm!"),
        say(co::KANBEI, "Yellow Comet's honour will not break!"),
        say(co::HAWKE, "Four armies, one centre. Every invention we own."),
        say(co::HAWKE, "If I were choosing the pair: Sturm and Clone Andy."),
        say(co::STURM, "This is my continent. Mine.").with(co::STURM),
        say(co::CLONE_ANDY, "Is this where you're from? It's... cosy.").with(co::CLONE_ANDY),
        say(co::VON_BOLT, "Who is near my vault?"),
        troop("Sir! I hold the flag at the Obelisk!"),
    ]
}

pub fn m28_day_5() -> Vec<Line> {
    vec![
        troop("The Onyx fires. A white column falls on the ridge."),
        say(co::RACHEL, "Rules say we win! Rule 4: do not lose!"),
    ]
}

pub fn m28_day_10() -> Vec<Line> {
    vec![
        say(co::OLAF, "The Onyx! The sky is watching! Fire at it!"),
        troop("The Onyx fires again. The ridge goes white."),
    ]
}

pub fn m28_day_15() -> Vec<Line> {
    vec![
        say(co::EAGLE, "Silos! Launch! Take that satellite down!"),
    ]
}

pub fn m28_onyx_hit1() -> Vec<Line> {
    vec![
        say(co::EAGLE, "Direct hit! One down! Keep launching!"),
    ]
}

pub fn m28_onyx_hit2() -> Vec<Line> {
    vec![
        say(co::OLAF, "Two! The sky is cracking!"),
    ]
}

pub fn m28_onyx_hit3() -> Vec<Line> {
    vec![
        say(co::KANBEI, "Three. Honour demands the fourth."),
    ]
}

pub fn m28_onyx_destroyed() -> Vec<Line> {
    vec![
        troop("The Onyx breaks apart and falls in white fire."),
        say(co::HAWKE, "The uplink is gone. The Obelisk is flickering."),
        say(co::VON_BOLT, "My satellite! My lovely satellite!"),
        say(co::OLAF, "Ha! Down she goes!"),
        say(co::STURM, "Hold the Gate."),
    ]
}

pub fn m28_day_20() -> Vec<Line> {
    vec![
        say(co::KANBEI, "Hold! Hold the line! Honour is not ammunition!"),
    ]
}

pub fn m28_post() -> Vec<Line> {
    vec![
        sad(co::RACHEL, "Rule five. When outnumbered... retreat."),
        sad(co::RACHEL, "Sister... I tried. I really tried."),
        say(co::OLAF, "Back to the ships! Back!"),
        say(co::EAGLE, "This was not supposed to go like this!"),
        say(co::KANBEI, "Fall back. We will fight at the Orange Gate."),
        say(co::HAWKE, "The coalition breaks. And Nell's door is open."),
        say(co::HAWKE, "She wanted us to see it."),
        say(co::VON_BOLT, "Is the vault safe?"),
        troop("The flag is up, sir! Gerald is safe!"),
        say(co::STURM, "Noted."),
    ]
}

pub fn m28_map() -> Vec<Line> {
    vec![
        say(co::CLONE_ANDY, "Sir? That was my first home defence."),
        say(co::STURM, "It will not be the last."),
        say(co::CLONE_ANDY, "...Good. I like it here."),
    ]
}

pub fn m28_promotion() -> Vec<Line> {
    vec![
        troop("The Obelisk, at dusk. The flag still stands. So does he."),
        say(co::STURM, "Hobb. Step forward."),
        troop("Sir! Yes, sir! Is it about the flag, sir? I can explain!"),
        say(co::STURM, "You held it at the Obelisk against four armies."),
        troop("I was holding it so it would not blow away, sir..."),
        say(co::STURM, "You held what is mine. Black Hole does not forget its own."),
        say(co::STURM, "I do not give ranks. I take them. Today I take you one."),
        say(co::STURM, "Kneel."),
        troop("Sir?!"),
        say(co::STURM, "Kneel, Commander Hobb."),
        troop("...Commander?"),
        troop("Is it all right if I... faint? Just a little?"),
        say(co::HAWKE, "The commission exists. I wrote it during the siege."),
        say(co::VON_BOLT, "Another mouth on the payroll. Kehh. Prorated."),
        troop("C-Commander? Me? But I'm a Private! Gerald, did you hear?"),
        say(co::STURM, "You will command. Your men will not run dry."),
        say(co::STURM, "I promote what I can use. You are useful."),
        troop("Yes, sir! I mean, yes, Commander sir! I mean...!"),
        troop("Gerald, we're a CO!"),
        say(co::STURM, "The biscuit does not outrank you."),
        troop("He outranks everybody, sir. It's the age."),
        say(co::STURM, "...Noted."),
    ]
}

pub fn m31_pre() -> Vec<Line> {
    vec![
        troop("The Black Hole continent, after the war. A quiet night."),
        troop("Sir! The vault door is open. And the guard was me."),
        say(co::VON_BOLT, "My VAULT! My vault! Someone has been in it!"),
        say(co::VON_BOLT, "Forty tons of gold! Gone! The ledgers! Gone!"),
        say(co::VON_BOLT, "And a NOTE, on my own desk, in my own ink!"),
        say(co::VON_BOLT, "\"Dear Colonel. Come and get it. I will be watching.\""),
        say(co::VON_BOLT, "Signed \"S.\" Signed!"),
        troop("A lady offered me a biscuit, sir."),
        say(co::VON_BOLT, "A BISCUIT?!"),
        troop("A better one than Gerald."),
        troop("...Sorry, Gerald."),
        say(co::SONJA, "Good evening. Your vault is lovely. Very full."),
        say(co::SONJA, "And the Colonel's ledgers are so informative."),
        say(co::HAWKE, "Sonja. A heist at the worst possible hour."),
        say(co::SONJA, "The best, Marshal. You won. Everyone relaxes."),
        say(co::SONJA, "My ship sails when the eighth sun sets. Do chase me."),
        say(co::STURM, "Recover my vault."),
        say(co::HAWKE, "The docks lie east. Two roads, a ford, a coast."),
        say(co::KOAL, "Both roads are mine. I will drive them."),
        say(co::KINDLE, "Darlings, I shall supply the fireworks for the chase."),
        say(co::JUGGER, "TRACKING. ESCAPE ETA: EIGHT DAYS. STOP HER."),
        say(co::FLAK, "Flak hits lady! Gently!"),
        say(co::LASH, "Ooh! A chase! I brought three new toys!"),
        say(co::ADDER, "Make way. The star is arriving."),
        say(co::CLONE_ANDY, "I'll watch the south road, sir. Lane by lane!"),
        say(co::STURM, "Go."),
    ]
}

pub fn m31_day_2() -> Vec<Line> {
    vec![
        say(co::SONJA, "The first truck is out. Do keep up. I time everything."),
    ]
}

pub fn m31_day_3() -> Vec<Line> {
    vec![
        say(co::SONJA, "Two roads, two trucks. Only one is real. Place your bets."),
    ]
}

pub fn m31_day_5() -> Vec<Line> {
    vec![
        say(co::SONJA, "Fog tonight, ninety per cent. I chose the night for it."),
    ]
}

pub fn m31_when_the_first_vault_truck_is_destroyed() -> Vec<Line> {
    vec![
        say(co::VON_BOLT, "One truck! A third of my gold!"),
        say(co::SONJA, "Sunk cost, Colonel. Think of the tax relief."),
    ]
}

pub fn m31_post() -> Vec<Line> {
    vec![
        say(co::SONJA, "You caught me. ...As I intended."),
        say(co::VON_BOLT, "Intended?! You ROBBED me!"),
        say(co::SONJA, "I auditioned, Colonel. Black Hole does not advertise."),
        say(co::HAWKE, "An audition. In our own vault."),
        say(co::SONJA, "In a sealed room, an honest person shows herself."),
        say(co::STURM, "Explain."),
        say(co::SONJA, "A year of notes. Every wall, every guard, every key."),
        say(co::SONJA, "You never chased the gold."),
        say(co::SONJA, "You chased the boy who was guarding it."),
        troop("Ma'am?"),
        say(co::VON_BOLT, "...The boot boy."),
        say(co::SONJA, "One private, and an army turned round. Cold men do not."),
        say(co::STURM, "Do not mistake me."),
        say(co::SONJA, "I never do. That is why I came."),
        say(co::SONJA, "Last shelf in the vault. A crate. It hums."),
        say(co::SONJA, "It hums at your voice, Sturm. Only yours."),
        say(co::VON_BOLT, "That crate is NOTHING."),
        say(co::SONJA, "Then why do you sweat, Colonel?"),
        say(co::HAWKE, "Interesting. And unwelcome."),
    ]
}

pub fn m31_map() -> Vec<Line> {
    vec![
        troop("Gerald, I was bribed by a better biscuit. Forgive me."),
        troop("He is a biscuit."),
        troop("He is very forgiving."),
        troop("Go to bed, Crumb."),
    ]
}

pub fn m31_defect() -> Vec<Line> {
    vec![
        say(co::SONJA, "I did not come to rob you. I came to be recruited."),
        say(co::SONJA, "My father's code is a wall. I have counted its bricks."),
        say(co::SONJA, "Yours is a storm. I have not found its edge."),
        say(co::STURM, "You are not Black Hole."),
        say(co::SONJA, "Not yet. Test me."),
        say(co::STURM, "Why."),
        say(co::SONJA, "Because something under your voice answers that crate."),
        say(co::SONJA, "I want to hear what it says."),
        say(co::HAWKE, "A spy asks to join the house she robbed."),
        say(co::SONJA, "A spy who has read every ledger in it."),
        say(co::HAWKE, "I do not trust her."),
        say(co::STURM, "Nor do I. Keep her close. What I own, I watch."),
        say(co::VON_BOLT, "She held my keys. She will audit me. I feel it."),
        say(co::SONJA, "Fifteen per cent, Colonel, of everything you find."),
        say(co::VON_BOLT, "Ten!"),
        say(co::SONJA, "Fifteen. And I keep the receipts. All of them."),
        say(co::VON_BOLT, "...Fifteen."),
        troop("Welcome, ma'am. Gerald forgives you. He does that."),
        say(co::SONJA, "...Thank you, Private."),
        troop("Sonja joins the roll (Free Play): Vault Breakers."),
        say(co::STURM, "What does the crate say?"),
        say(co::SONJA, "Not yet. It speaks when you stop being afraid."),
        say(co::STURM, "I am not afraid."),
        say(co::SONJA, "Then it will speak soon."),
        troop("Far below the vault, the humming changes pitch."),
    ]
}

pub fn m31_kanbei() -> Vec<Line> {
    vec![
        troop("Comet Keep. A courier brings a sealed letter."),
        say(co::KANBEI, "From Sonja! She writes so rarely. Sensei, listen!"),
        say(co::KANBEI, "\"Father. I have joined Black Hole. Do not follow.\""),
        sad(co::KANBEI, "Joined. Black. Hole."),
        say(co::SENSEI, "Kanbei..."),
        say(co::KANBEI, "A feint! She tests me! It is strategy!"),
        say(co::SENSEI, "She signed it, Kanbei. The strongroom is empty."),
        say(co::SENSEI, "She took the receipts."),
        sad(co::KANBEI, "...Sonja. You took the receipts?"),
        say(co::KANBEI, "I taught her honour. She learned the audit."),
        say(co::SENSEI, "You taught her to read everything."),
        say(co::KANBEI, "...Yes. I did."),
        say(co::KANBEI, "Then I shall write back. Eat well. Wear a scarf."),
        say(co::SENSEI, "She is the enemy."),
        sad(co::KANBEI, "She is my daughter. Both are true, old friend."),
        say(co::KANBEI, "Set a place at the table. She will want her seat."),
        say(co::SENSEI, "And the honour of the Keep?"),
        say(co::KANBEI, "Honour has no manual for this. Then we write one."),
    ]
}
