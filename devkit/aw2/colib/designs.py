"""The original portrait designs (docs/dev/co-kit.md): per CO, four lettered designs, each a function that draws a figure (128 x 160) and the four expression faces (48 x 48), then
the small face (32 x 24) and the HUD face (32 x 16) are cut from the face. Palettes are per design (slot name -> RRGGBB, at most 15 colours after sharing)."""
import math
from .draw import Art
from . import heads, bodies as B

EXPRS = ("normal", "happy", "sad", "angry")


def pal(**kw):
    return kw


# shared colour families (original colours of this repository)
SKIN = {"tan": ("f6cfa6", "e2a276", "b86f4c"), "olive": ("f0c79a", "d99f70", "a8683f"), "fair": ("fbdcc0", "efb792", "c9805e"), "pale": ("fde6d2", "f3c5a6", "d08e72"), "bronze": ("eebf8f", "d08a58", "9a5434")}
SAGE = ("e2e8c8", "aab68c", "636c4c")
RED = ("e65a66", "c42a3a", "86182a")
GOLD = ("ffe486", "e8bc4c", "a87828")
CREAM = ("fff6e2", "f0e2c4", "c8b690")
LEATHER = ("c89a62", "9c6a3c", "62402a")
PURPLE = ("b878b0", "8e4a8c", "5e2c62")
LEAF = ("92c860", "4c8a3a")


def colours(skin, hair, ol="2a1c24", **extra):
    c = {"ol": ol, "wh": "ffffff", "ey": ol, "lip": SKIN[skin][2]}
    for n, v in zip(("sk_h", "sk_m", "sk_s"), SKIN[skin]):
        c[n] = v
    for n, v in zip(("ha_h", "ha_m", "ha_s"), hair):
        c[n] = v
    for fam, pre in (("st", SAGE), ("rd", RED), ("gd", GOLD), ("cr", CREAM), ("lt", LEATHER), ("pu", PURPLE)):
        pass
    c.update(extra)
    return c


def fam(prefix, ramp):
    return {f"{prefix}_{t}": v for t, v in zip("hms", ramp)}


class Design:
    def __init__(self, co, letter, title, desc, colours, build_body, head, collar=None, mug_dy=0):
        self.co, self.letter, self.title, self.desc, self.colours, self.build_body, self.head, self.collar, self.mug_dy = co, letter, title, desc, colours, build_body, head, collar, mug_dy


def draw_head(art, p, h, expr):
    """Draw a head from its spec dict `h` (jaw, hair, beard, gear, brow, mouth, smirk, wrinkles, lashes, eye_dy, half_lid, hair_ramp, scars, neck)."""
    hr = h.get("hair_ramp", heads.HA)
    heads.hair_back(art, p, h.get("hair", "none"), hr)
    heads.draw_neck(art, p, width=h.get("neck", 10.5), to=h.get("neck_to", 30 if p.s > 1.0 else 40))
    heads.draw_face(art, p, h.get("jaw", "square"))
    if h.get("beard"):
        heads.beard(art, p, h["beard"], hr)
    mouth = h.get("mouth")
    if expr == "normal" and h.get("normal_mouth"):
        mouth = h["normal_mouth"]
    heads.draw_features(art, p, expr, brow=h.get("brow", "stern"), mouth=mouth if expr == "normal" else None, smirk=h.get("smirk", False) and expr == "normal", wrinkles=h.get("wrinkles", False),
                        half_lid=h.get("half_lid", False) and expr == "normal", lashes=h.get("lashes", False), eye_dy=h.get("eye_dy", 0))
    for sc in h.get("scars", []):
        x, y = p.i(*sc[0])
        for k in range(sc[1]):
            art.dot(x + k, y + k, "sk_s" if k % 2 == 0 else "sk_h")
    gear = h.get("gear")
    if gear == "galea":
        heads.galea(art, p, crest_kind=h.get("crest", "transverse"), crest_h=h.get("crest_h", 9), cheek=h.get("cheek", True))
    else:
        heads.hair_front(art, p, h.get("hair", "none"), hr)
    if h.get("laurel"):
        heads.laurel(art, p)  # (y: the brow)
    if h.get("diadem"):
        for dx in range(-14, 15):
            x, y = p.i(dx * 1.0, -12 - abs(dx) * 0.12)
            art.dot(x, y, "gd_m")
        art.dot(*p.i(0, -13), "rd_m")
    for extra in h.get("extras", []):
        extra(art, p)


def build(design, expr="normal", upto=None):
    """-> (figure Art 128 x 160, mug Art 48 x 48)."""
    h = design.head
    B.FEM = bool(h.get("fem"))
    fig = Art(128, 160)
    p = heads.P(*h.get("body_pos", (64, 38, 1.1)))
    order = ("back", "torso", "head", "front")
    last = order.index(upto) if upto else 3
    design.build_body(fig, p, expr, "back")
    if last >= 1:
        design.build_body(fig, p, expr, "torso")
    if last >= 2:
        draw_head(fig, p, h, expr)
    if last >= 3:
        design.build_body(fig, p, expr, "front")
    fig.outline_pass()
    mug = Art(48, 48)
    mp = heads.P(*h.get("mug_pos", (27, 23, 1.0)))
    if design.collar:
        design.collar(mug, mp, "back")
    draw_head(mug, mp, h, expr)
    if design.collar:
        design.collar(mug, mp, "front")
    mug.outline_pass()
    return fig, mug


def small_faces(mug):
    mini = mug.crop(8, 12, 32, 24)
    hud = mug.crop(8, 18, 32, 16)
    return mini, hud




def collar_plain(ramp, trim=None):
    def f(art, p, stage):
        if stage == "back":
            return
        m = art.poly([(0, 45), (10, 43), (38, 43), (48, 45), (48, 48), (0, 48)])
        art.paint(m, ramp, hi=1, lo=1)
        art.line([(2, 46), (46, 46)], ramp[2], 1)
        if trim:
            art.dot(24, 43, trim)
    return f


def arm(art, pts, width, ramp, wrist=None, hand_ramp=B.SK, bracer=True, hand_r=4.6):
    m = B.limb(art, pts, width, ramp, hi=1, lo=1)
    if bracer:
        a, b = pts[-2], pts[-1]
        mid = (a[0] + (b[0] - a[0]) * 0.55, a[1] + (b[1] - a[1]) * 0.55)
        B.bracer(art, mid, b, max(6, width - 3))
    if hand_r:
        B.hand(art, pts[-1][0], pts[-1][1], hand_r)
    return m


# ================================================================ KLAUS ====================================================================================================

def klaus_a_body(art, p, expr, stage):
    if stage == "back":
        m = art.poly([(24, 62), (50, 54), (80, 54), (104, 62), (112, 110), (108, 160), (14, 160), (18, 110)])
        art.paint(m, B.RD, hi=2, lo=3)
        for k in range(6):
            art.line([(30 + k * 14, 70 + k), (26 + k * 16, 158)], "rd_s", 1)
    elif stage == "torso":
        B.lorica(art)
        B.pteruges(art, 38, 90, 122, 8, 22)
        B.belt(art, 34, 114, 94, 122, plates=4)
        B.fibula(art, 90, 66, 4)
        B.limb(art, [(30, 70), (22, 98), (36, 120)], 12, B.RD, hi=1, lo=1)
        B.bracer(art, (28, 110), (36, 120), 9)
        B.hilt(art, 42, 112)
        B.hand(art, 39, 119, 5)
    elif stage == "front":
        B.gorget(art)


def klaus_b_body(art, p, expr, stage):
    if stage == "torso":
        B.tunic(art, B.RD)
        B.muscle_cuirass(art, B.GD)
        B.pteruges(art, 36, 94, 122, 9, 22)
        B.belt(art, 34, 114, 94, 122, plates=4)
        # shoulder pteruges over the upper arms
        for sx, sgn in ((34, -1), (94, 1)):
            for k in range(4):
                B.pteruges(art, sx - 11 + k * 0, sx + 11, 64 + k * 5, 3, 12, slant=sgn)
        # arms crossed: the far forearm first, then the near one over it
        arm(art, [(96, 70), (102, 102), (52, 98)], 13, B.RD)
        arm(art, [(30, 70), (24, 104), (88, 94)], 13, B.RD)
    elif stage == "front":
        B.gorget(art, ramp=B.GD)


def klaus_c_body(art, p, expr, stage):
    if stage == "back":
        m = art.poly([(24, 64), (50, 56), (80, 56), (104, 64), (108, 120), (100, 160), (22, 160), (18, 120)])
        art.paint(m, B.RD, hi=2, lo=3)
    elif stage == "torso":
        B.muscle_cuirass(art, B.ST)
        B.pteruges(art, 36, 94, 122, 9, 24, ramp=B.RD, studs="gd_m")
        B.belt(art, 34, 114, 94, 122, ramp=B.RD, plates=3)
        # a toga drape across the near side, arm raised holding the orders
        drape = art.poly([(24, 64), (50, 60), (66, 96), (50, 126), (22, 160), (14, 160), (12, 100)])
        art.paint(drape, B.CR, hi=2, lo=3)
        art.line([(50, 61), (66, 96), (50, 126), (30, 158)], "pu_m", 3)
        for k in range(4):
            art.line([(24 + k * 6, 78 + k * 4), (20 + k * 6, 156)], "cr_s", 1)
        arm(art, [(94, 70), (104, 96), (82, 106)], 13, B.RD, bracer=True)
        B.scroll(art, 66, 108, 28, -0.2)
        B.hand(art, 78, 107, 5)
    elif stage == "front":
        B.gorget(art, ramp=B.ST)


def klaus_d_body(art, p, expr, stage):
    if stage == "torso":
        B.tunic(art, B.RD)
        B.scale_armour(art)
        B.pteruges(art, 38, 90, 122, 8, 22)
        B.belt(art, 34, 114, 94, 122, plates=3)
        B.sheath(art, 38, 112, 22, 150)
        for sx, sgn in ((34, -1), (94, 1)):
            B.pteruges(art, sx - 12, sx + 12, 64, 3, 16, slant=sgn)
        # the near fist on the hip, the far arm out, pointing the way
        arm(art, [(30, 70), (20, 96), (38, 118)], 13, B.RD, hand_r=5)
        arm(art, [(94, 70), (112, 82), (126, 80)], 12, B.RD, hand_r=4)
    elif stage == "front":
        B.gorget(art)


SAGE_HAIR_GREY = ("c4c4cc", "8e8e9c", "54545e")
base = lambda skin, hair, **kw: {**colours(skin, hair), **fam("st", SAGE), **fam("rd", RED), **fam("gd", GOLD), **fam("lt", LEATHER), **fam("cr", CREAM), **fam("pu", PURPLE), "lf_h": LEAF[0], "lf_m": LEAF[1], **kw}

KLAUS = {
    "A": Design("klaus", "A", "The Legate",
                "A grey-bearded veteran in lorica segmentata and a crimson paludamentum clasped with gold, one hand on his gladius: stern, tired, immovable.",
                base("tan", SAGE_HAIR_GREY), klaus_a_body, dict(jaw="square", hair="crop", beard="full", brow="stern", wrinkles=True, scars=[((-9, 0), 4)]), collar=collar_plain(B.ST)),
    "B": Design("klaus", "B", "The Centurion",
                "Clean-shaven and scarred under a crested galea: a bronze muscle cuirass, red pteruges and folded, braced arms. A commander who leads from the front line.",
                base("bronze", ("7a5a48", "4a2e24", "2e1a18")), klaus_b_body,
                dict(jaw="square", gear="galea", crest="transverse", crest_h=7, brow="sharp" if False else "stern", scars=[((-8, 2), 5)], body_pos=(64, 41, 1.05), neck_to=24, mouth="firm", hair="none"),
                collar=collar_plain(B.GD)),
    "C": Design("klaus", "C", "The Triumphator",
                "A shaved head under a laurel crown, stubble and a deep stare; muscle cuirass under a cream toga with a purple border, the Senate's orders rolled in his fist.",
                base("tan", ("a8a8b0", "76767e", "4a4a52")), klaus_c_body, dict(jaw="angular", hair="bald", laurel=True, beard="stubble", brow="stern", wrinkles=True), collar=collar_plain(B.CR)),
    "D": Design("klaus", "D", "The Marshal",
                "Grey fringe, heavy brow, a thick neck: scale armour and shoulder pteruges, one fist on the hip and the other arm pointing the way. The old soldier's order to march.",
                base("olive", ("b8b0a8", "847c78", "544e4c")), klaus_d_body, dict(jaw="round", hair="caesar", brow="sharp", wrinkles=True, scars=[((-7, -6), 3)], neck=12), collar=collar_plain(B.ST)),
}


# ================================================================ AURELIA ==================================================================================================

def aurelia_a_body(art, p, expr, stage):
    if stage == "torso":
        B.tunic(art, B.CR)
        B.apron(art)
        # tool belt: a leather band with hammers and a rolled cord
        B.belt(art, 40, 112, 88, 119, plates=0)
        art.paint(art.thick([(70, 120), (74, 142)], 4, False), B.LT, hi=1, lo=1)
        art.paint(art.rect(68, 138, 78, 143), B.GD, hi=1, lo=1)
        for sx, sgn in ((36, -1), (92, 1)):
            art.paint(art.ellipse(sx, 66, 9, 6), B.CR, hi=1, lo=1)
        arm(art, [(34, 68), (26, 94), (44, 104)], 11, B.SK, hand_r=0)
        arm(art, [(92, 68), (100, 92), (78, 92)], 11, B.SK, hand_r=0)
        B.compass(art, 62, 90, 20)
        B.hand(art, 45, 104, 4.6), B.hand(art, 76, 92, 4.6)
    elif stage == "front":
        B.gorget(art, ramp=B.CR, rx=15, ry=4)


def aurelia_b_body(art, p, expr, stage):
    if stage == "back":
        pass
    elif stage == "torso":
        B.tunic(art, B.CR)
        B.sash(art, (38, 64), (88, 118), B.RD, 8)
        B.belt(art, 40, 112, 90, 119, plates=0)
        for sx in (36, 92):
            art.paint(art.ellipse(sx, 66, 9, 6), B.CR, hi=1, lo=1)
        arm(art, [(34, 68), (24, 96), (40, 112)], 11, B.CR, bracer=True)
        arm(art, [(92, 68), (104, 90), (84, 98)], 11, B.CR, bracer=True)
        B.scroll(art, 66, 108, 34, -0.25)
        B.hand(art, 42, 112, 4.6), B.hand(art, 84, 98, 4.6)
    elif stage == "front":
        B.gorget(art, ramp=B.CR, rx=15, ry=4)


def aurelia_c_body(art, p, expr, stage):
    if stage == "torso":
        B.tunic(art, B.RD)
        B.sash(art, (40, 64), (90, 116), B.LT, 6)
        B.belt(art, 40, 112, 90, 119, plates=3)
        B.mallet(art, 100, 70, 40)
        # mail shoulder guard on the far shoulder, a bare near shoulder
        art.paint(art.ellipse(90, 68, 15, 9), B.ST, hi=1, lo=1)
        for k in range(3):
            art.paint(art.ellipse(94 + k, 74 + k * 4, 11 - k, 4), B.ST, hi=1, lo=1)
        arm(art, [(34, 68), (24, 94), (46, 108)], 11, B.SK, hand_r=5)
        arm(art, [(94, 74), (108, 88), (98, 66)], 12, B.RD, hand_r=5)
        B.pteruges(art, 40, 90, 122, 7, 20)
    elif stage == "front":
        B.gorget(art, ramp=B.LT, rx=15, ry=4)


def aurelia_d_body(art, p, expr, stage):
    if stage == "torso":
        B.tunic(art, B.RD)
        B.scale_armour(art, B.GD, 64, 112, 34, 94)
        B.belt(art, 40, 112, 90, 119, plates=3)
        arm(art, [(34, 68), (22, 96), (44, 110)], 11, B.RD, bracer=True)
        arm(art, [(92, 68), (102, 92), (70, 98)], 11, B.RD, bracer=True)
        B.tablet(art, 56, 90, 20, 24)
        B.hand(art, 46, 110, 4.6), B.hand(art, 68, 100, 4.6)
        B.pteruges(art, 40, 90, 122, 7, 20)
    elif stage == "front":
        B.gorget(art, ramp=B.GD, rx=15, ry=4)


FEMH = dict(fem=True, jaw="pointed", lashes=True, brow="arch", neck=9)
DARK = ("5a4638", "362618", "1e140e")
AUBURN = ("c8683c", "9a4424", "5e2814")
BLACK = ("5e5a74", "322e44", "1a1626")

AURELIA = {
    "A": Design("aurelia", "A", "The Sapper",
                "Hair pinned in a tight braided crown, soot on the cheek, a leather apron over a linen tunic, a pair of bronze dividers in her hand: she measures walls before she breaks them.",
                base("olive", DARK), aurelia_a_body, {**FEMH, "hair": "bun", "brow": "sharp", "mouth": "calm", "smirk": True, "body_pos": (64, 36, 1.08), "extras": [lambda a, p: a.dot(*p.i(-6, 8), "sk_s")]},
                collar=collar_plain(B.CR)),
    "B": Design("aurelia", "B", "The Architect",
                "A long low tail tied with a red band, a diagonal sash and the plans of the next siege rolled under her fingers: clever, quick, a little impatient with everyone.",
                base("olive", AUBURN), aurelia_b_body, {**FEMH, "hair": "ponytail", "brow": "arch", "mouth": "smirk", "smirk": True, "normal_mouth": "smirk"}, collar=collar_plain(B.CR)),
    "C": Design("aurelia", "C", "The Siege-Master",
                "Cropped hair, a bare arm and a mail guard on the other shoulder, a war mallet and a grin: the engineer who likes the noise.",
                base("bronze", BLACK), aurelia_c_body, {**FEMH, "hair": "crop", "brow": "flat", "mouth": "smirk", "normal_mouth": "smirk", "smirk": True, "half_lid": True, "body_pos": (64, 36, 1.08)}, collar=collar_plain(B.RD)),
    "D": Design("aurelia", "D", "The Surveyor",
                "A long braid over one shoulder, a bronze circlet and a wax tablet of figures: scale armour for the field, a sceptical eyebrow for everything the plan leaves out.",
                base("fair", DARK), aurelia_d_body, {**FEMH, "hair": "braid_long", "brow": "arch", "mouth": "calm", "diadem": True}, collar=collar_plain(B.GD)),
}

# ================================================================ CASSIUS ==================================================================================================

def cassius_a_body(art, p, expr, stage):
    if stage == "back":
        m = art.poly([(14, 70), (44, 56), (96, 56), (112, 74), (114, 130), (104, 160), (18, 160)])
        art.paint(m, B.RD, hi=2, lo=3)
    elif stage == "torso":
        B.tunic(art, B.RD)
        B.muscle_cuirass(art, B.GD)
        B.pteruges(art, 36, 94, 122, 9, 22)
        B.belt(art, 34, 114, 94, 122, plates=3)
        B.fibula(art, 24, 70, 4)
        arm(art, [(94, 70), (112, 96), (96, 118)], 13, B.RD, hand_r=5)     # fist on the hip
        arm(art, [(30, 70), (20, 96), (40, 112)], 13, B.RD, hand_r=5)
    elif stage == "front":
        B.gorget(art, ramp=B.GD)


def cassius_b_body(art, p, expr, stage):
    if stage == "torso":
        B.bare_chest(art)
        B.harness(art)
        B.belt(art, 38, 114, 90, 122, plates=3)
        B.pteruges(art, 38, 90, 122, 8, 22, ramp=B.RD)
        arm(art, [(96, 72), (104, 100), (56, 100)], 14, B.SK, bracer=True, hand_r=5)
        arm(art, [(30, 72), (24, 104), (82, 94)], 14, B.SK, bracer=True, hand_r=5)
    elif stage == "front":
        pass


def cassius_c_body(art, p, expr, stage):
    if stage == "torso":
        B.tunic(art, B.RD)
        B.scale_armour(art, B.ST)
        B.pteruges(art, 38, 90, 122, 8, 22)
        B.belt(art, 34, 114, 94, 122, plates=3)
        # a red scarf (focale) and the reins in one fist
        art.paint(art.poly([(48, 62), (80, 60), (84, 72), (64, 80), (46, 72)]), B.RD, hi=1, lo=1)
        art.paint(art.poly([(56, 74), (66, 80), (62, 100), (54, 98)]), B.RD, hi=1, lo=1)
        arm(art, [(30, 70), (20, 96), (40, 108)], 13, B.RD, hand_r=5)
        arm(art, [(94, 70), (106, 92), (88, 102)], 13, B.RD, hand_r=5)
        art.line([(88, 102), (110, 118), (124, 150)], "lt_m", 2)
    elif stage == "front":
        B.gorget(art, ramp=B.RD)


def cassius_d_body(art, p, expr, stage):
    if stage == "back":
        m = art.poly([(40, 60), (80, 56), (108, 70), (110, 150), (92, 160), (40, 160)])
        art.paint(m, ("lt_h", "pu_m", "pu_s"), hi=2, lo=3)
    elif stage == "torso":
        B.tunic(art, B.CR)
        for x in (44, 84):
            art.line([(x, 64), (x + 2, 160)], "pu_m", 2)
        B.belt(art, 36, 114, 92, 122, plates=3)
        arm(art, [(30, 70), (20, 98), (36, 114)], 13, B.CR, bracer=False, hand_r=5)
        arm(art, [(94, 70), (106, 94), (86, 86)], 13, B.CR, bracer=False, hand_r=5)
        B.goblet(art, 82, 82)
        B.fibula(art, 96, 70, 4)
    elif stage == "front":
        B.gorget(art, ramp=B.CR, rx=16, ry=4)


MALE = dict(jaw="angular", neck=10.5)
BRN = ("7a5236", "52301e", "2e180e")
BLONDE = ("f0d890", "c8a458", "8a6a30")
INK = ("5e5a74", "322e44", "1a1626")

CASSIUS = {
    "A": Design("cassius", "A", "The Rival",
                "Tousled dark curls, a smirk and a fist on his hip: bronze cuirass, a crimson cloak thrown back with an easy shrug. He expects to be obeyed and expects you to be impressed.",
                base("fair", INK), cassius_a_body, {**MALE, "hair": "curls", "brow": "haughty", "mouth": "smirk", "smirk": True, "half_lid": True, "normal_mouth": "smirk"}, collar=collar_plain(B.GD)),
    "B": Design("cassius", "B", "The Champion",
                "A self-awarded laurel and a bare chest in a harness of gold phalerae: arms folded, eyebrow cocked. Everything about him says that the medals were earned and the doubt is yours.",
                base("tan", BLONDE), cassius_b_body, {**MALE, "hair": "slick", "brow": "haughty", "laurel": True, "mouth": "smirk", "smirk": True, "normal_mouth": "smirk", "half_lid": True}, collar=collar_plain(B.SK)),
    "C": Design("cassius", "C", "The Cavalryman",
                "A plumed galea, scale armour and a red scarf, the reins looped round his fist: the dash of the legion's horse, with a grin that has never lost a bet.",
                base("olive", BRN), cassius_c_body, {**MALE, "gear": "galea", "crest": "plume", "crest_h": 7, "mouth": "smirk", "normal_mouth": "smirk", "smirk": True, "brow": "arch", "body_pos": (64, 41, 1.05), "neck_to": 24, "hair": "none"},
                collar=collar_plain(B.RD)),
    "D": Design("cassius", "D", "The Heir",
                "A senator's son: a linen tunic with purple stripes, a dark cloak, a gold cup lifted in a lazy toast. Fringe tossed, eyes half-lidded, a young man with all the time in the world.",
                base("pale", ("d0a060", "9a6a34", "5e3a1a")), cassius_d_body, {**MALE, "hair": "caesar", "brow": "haughty", "mouth": "smirk", "smirk": True, "normal_mouth": "smirk", "half_lid": True}, collar=collar_plain(B.CR)),
}

# ================================================================ LIVIA ====================================================================================================

def livia_a_body(art, p, expr, stage):
    if stage == "torso":
        B.stola(art, B.CR, B.PU)
        B.palla(art, B.PU)
        arm(art, [(34, 68), (24, 96), (46, 110)], 11, B.CR, bracer=False, hand_r=0)
        arm(art, [(92, 68), (102, 94), (80, 106)], 11, B.CR, bracer=False, hand_r=0)
        B.tablet(art, 52, 92, 18, 22)
        B.hand(art, 48, 108, 4.4), B.hand(art, 74, 104, 4.4)
        # a gold necklace
        art.line([(52, 66), (58, 72), (64, 74), (70, 72), (76, 66)], "gd_m", 1)
    elif stage == "front":
        B.gorget(art, ramp=B.CR, rx=14, ry=3)


def livia_b_body(art, p, expr, stage):
    if stage == "back":
        m = art.poly([(36, 14), (72, 8), (92, 24), (104, 66), (110, 130), (100, 160), (20, 160), (24, 100), (30, 50)])
        art.paint(m, B.PU, hi=2, lo=3)
    elif stage == "torso":
        B.stola(art, B.CR, B.PU)
        arm(art, [(34, 68), (24, 96), (50, 108)], 11, B.CR, bracer=False, hand_r=0)
        B.purse(art, 40, 112, 8)
        B.hand(art, 52, 108, 4.4)
        arm(art, [(92, 68), (104, 92), (88, 78)], 11, B.CR, bracer=False, hand_r=0)
        B.coin(art, 80, 70, 3.5)
        B.hand(art, 84, 74, 4.4)
    elif stage == "front":
        B.gorget(art, ramp=B.PU, rx=14, ry=3)


def livia_c_body(art, p, expr, stage):
    if stage == "back":
        m = art.poly([(22, 66), (50, 56), (84, 56), (106, 66), (112, 120), (104, 160), (18, 160), (14, 120)])
        art.paint(m, B.PU, hi=2, lo=3)
    elif stage == "torso":
        B.toga(art, B.CR, B.PU)
        arm(art, [(92, 68), (100, 98), (70, 96)], 11, B.CR, bracer=False, hand_r=0)
        arm(art, [(34, 68), (26, 98), (58, 104)], 11, B.CR, bracer=False, hand_r=0)
        B.abacus(art, 46, 96, 28, 14)
        B.hand(art, 60, 106, 4.4), B.hand(art, 74, 100, 4.4)
    elif stage == "front":
        B.gorget(art, ramp=B.PU, rx=14, ry=3)


def livia_d_body(art, p, expr, stage):
    if stage == "torso":
        B.stola(art, B.RD, B.GD)
        art.line([(46, 80), (82, 78)], "gd_m", 2)
        arm(art, [(34, 68), (24, 96), (44, 112)], 11, B.RD, bracer=False, hand_r=0)
        arm(art, [(92, 68), (104, 84), (96, 58)], 11, B.RD, bracer=False, hand_r=0)
        B.scales(art, 96, 50, 12)
        B.hand(art, 96, 58, 4.4), B.hand(art, 46, 112, 4.4)
    elif stage == "front":
        B.gorget(art, ramp=B.GD, rx=14, ry=3)


LIVIA = {
    "A": Design("livia", "A", "The Quaestor",
                "Braids coiled and pinned with gold, a cream stola edged in senatorial purple, a wax tablet and a stylus held like a verdict: poised, courteous, already adding it up.",
                base("pale", DARK), livia_a_body, {**FEMH, "hair": "braid_crown", "brow": "arch", "mouth": "calm", "smirk": True}, collar=collar_plain(B.CR)),
    "B": Design("livia", "B", "The Matron",
                "A purple palla drawn over a low coil of hair and ringlets, a coin purse in one hand and a gold coin between the fingers of the other: she will tell you the price.",
                base("fair", ("6a3c28", "42241a", "26120c")), livia_b_body, {**FEMH, "hair": "ringlets", "brow": "arch", "mouth": "pursed", "normal_mouth": "pursed", "smirk": True, "half_lid": True}, collar=collar_plain(B.PU)),
    "C": Design("livia", "C", "The Senator",
                "A sleek twist under a gold laurel, a toga with a purple border, an abacus in her hands and a stare that has already won the vote.",
                base("olive", BLACK), livia_c_body, {**FEMH, "hair": "slick", "laurel": True, "brow": "stern", "mouth": "calm", "jaw": "angular"}, collar=collar_plain(B.CR)),
    "D": Design("livia", "D", "The Treasurer",
                "Coiled hair under a gold diadem, a red stola and the golden scales raised in one hand: the army's accounts, held up to the light.",
                base("pale", AUBURN), livia_d_body, {**FEMH, "hair": "melon", "diadem": True, "brow": "arch", "mouth": "calm", "smirk": True}, collar=collar_plain(B.RD)),
}
