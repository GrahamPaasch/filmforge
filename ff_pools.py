#!/usr/bin/env python3
"""Genre configuration: large scene pools + image style + music mode + camera feel."""

NATURE_STYLE = ", cinematic nature photography, epic landscape, volumetric light, ultra detailed, 8k, serene, awe-inspiring, professional color grading"
NATURE_NEG = "people, person, human, text, watermark, logo, cartoon, anime, blurry, lowres, oversaturated, deformed, frame, border"
HORROR_STYLE = ", cinematic horror film still, eerie, unsettling, ominous, volumetric fog, dramatic low key lighting, desaturated cold palette, dread, highly detailed, 8k, anamorphic, film grain"
HORROR_NEG = "text, watermark, logo, cartoon, anime, cute, cheerful, bright, colorful, saturated, deformed, extra limbs, blurry, lowres, frame, border, people faces"

NATURE_POOL = [
    "misty pine forest at dawn, sun rays breaking through fog",
    "still alpine lake mirroring snow-capped mountains at sunrise",
    "powerful waterfall in a lush green canyon, mist rising",
    "golden autumn birch forest, fallen leaves, soft light",
    "dramatic ocean cliffs with crashing waves at golden hour",
    "red rock desert canyon glowing at sunset, deep shadows",
    "aurora borealis over a snowy spruce forest at night",
    "wildflower alpine meadow beneath towering peaks, summer",
    "wide river winding through a green mountain valley, aerial",
    "rugged rocky coastline with turquoise waves and sea foam",
    "sunbeams streaming through a towering redwood grove",
    "snow-covered mountain summit under a clear cold blue sky",
    "endless purple lavender field rolling to the horizon at dusk",
    "foggy lake at sunrise, silhouetted reeds, pink sky reflection",
    "quiet bamboo forest with soft dappled green light",
    "emerald river cutting through a deep slot canyon",
    "tropical jungle waterfall into a clear blue plunge pool",
    "golden savanna grassland under vast dramatic clouds",
    "blue glacier ice cave glowing from within",
    "coastal tide pools at sunset reflecting orange sky",
    "cherry blossom trees along a gentle mountain stream",
    "milky way galaxy arching over jagged silhouetted peaks",
    "rolling emerald green hills under scattered clouds",
    "dramatic storm clouds and lightning over open prairie",
    "tranquil zen pond with lily pads and morning mist",
    "moss-covered rainforest creek with smooth stones",
    "windswept sand dunes at golden hour, rippling ridgelines",
    "frozen waterfall and icicles in a blue winter gorge",
    "sunset over a calm fjord between steep green cliffs",
    "field of tall grass glowing backlit at golden hour",
    "terraced rice fields at dawn wrapped in mist",
    "a lone oak on a rolling hill under a dramatic sky",
    "turquoise glacial lake ringed by pine and granite",
    "autumn maple canopy over a red wooden footbridge",
    "vast salt flats mirroring a pastel twilight sky",
    "a waterfall plunging into a mossy emerald grotto",
    "snowy pine forest under soft falling snow at blue hour",
    "sea stacks in ocean fog at sunrise, long exposure",
    "a meadow of golden wheat rippling in the wind",
    "canyon river bend seen from a high desert overlook",
    "alpine tarn reflecting pink alpenglow on the peaks",
    "a misty valley of rolling tea plantations at dawn",
    "ancient mossy forest with ferns and shafts of light",
    "a calm beach with bioluminescent waves under stars",
    "rolling fog pouring over a green coastal mountain ridge",
]

HORROR_POOL = [
    "a vast derelict alien monolith looming in a fog-choked wasteland at dusk",
    "a dead petrified forest under a blood-red sky, twisted black branches",
    "an abandoned cathedral interior swallowed by mist, shafts of sickly light",
    "a colossal eldritch structure emerging from a black storm-wracked ocean",
    "a bioluminescent cave lined with countless faintly glowing eyes in the dark",
    "a cracked salt desert stretching to a monolithic obelisk under a huge alien moon",
    "a flooded ruined city street, half-submerged, silhouettes standing motionless in fog",
    "a writhing mass of shadow tendrils rising from a chasm of dim red light",
    "an endless corridor of rusted metal, flickering lights, something wrong in the distance",
    "a frozen tundra with a towering black spire and a swirling green aurora of dread",
    "a decaying overgrown asylum ward, peeling walls, a single tipped wheelchair in fog",
    "a swarm of black winged silhouettes blotting out a pale sickly sun",
    "an alien swamp of pulsing organic pods under a churning violet sky",
    "a cavern with an immense fossilized skeleton of an unknown leviathan",
    "a lighthouse on jagged rocks stabbing at a boiling black sea, storm and lightning",
    "a field of pale withered stalks under thick low fog, a distant humanoid shape",
    "a subterranean lake of ink reflecting a hanging inverted city of bone",
    "a shattered moon bleeding light over a scorched obsidian mountain range",
    "a narrow canyon of flesh-like red rock walls, mist pooling in the depths",
    "an abandoned carnival at night, broken carousel, fog rolling through empty stalls",
    "a colossal eye opening within a swirling nebula above a dead planet",
    "a drowned forest, dead trees rising from still black water, thick mist",
    "an ancient stone circle on a moor at night, ground fog, unnatural glow at the center",
    "a derelict spacecraft interior overtaken by dark organic growth, dripping shadows",
    "a mountainside of countless pale standing figures facing away into the fog",
    "a rift in the sky tearing open over a ruined skyline, cold light pouring out",
    "an underground tunnel ending in a wall of writhing darkness and faint teeth",
    "a vast hall of hanging chrysalis pods glistening in dim red emergency light",
    "a barren shore of black sand under twin dying suns, a beached alien colossus",
    "a foggy graveyard of tilted monoliths stretching beyond sight, faint blue mist",
    "a rotting pier stretching into a black sea beneath a sky of dead stars",
    "a ruined temple half-consumed by a pulsing red crystalline growth",
    "an abandoned hospital corridor flooded ankle-deep, fog and flickering light",
    "a colossal hand of stone rising from a fog-drowned bog at twilight",
    "a spiral staircase descending endlessly into red-lit darkness",
    "a dead city of black towers under a churning green sky",
    "a frozen sea with a vast dark shape trapped beneath cracking ice",
    "a forest of pale bone-white trees under a starless void",
    "a cathedral of alien ribs arching over a lake of tar",
    "an empty desert highway vanishing into an approaching wall of black fog",
    "a derelict observatory dome open to a bleeding aurora and wrong constellations",
    "a cavern mouth ringed with monolithic teeth exhaling cold mist",
    "a swamp shrine draped in tattered shrouds under a sick yellow moon",
    "a ruined factory of rusted machinery bleeding shadow into red pools",
    "a vast field of black monoliths humming under a fractured violet sky",
]

# ---------------------------------------------------------------------------
# pastoral — spec 01. NOT a scene pool: an ordered journey, one place, one
# morning, water running downhill. Never sample from this; walk it in order.
# Each entry is (still_prompt, motion_prompt): the still feeds the RealVisXL
# keyframe, the motion prompt feeds Wan 2.2 image-to-video.
# ---------------------------------------------------------------------------

PASTORAL_STYLE = (", cinematic nature photography, alpine spring morning, volumetric light, "
                  "shallow depth of field, ultra detailed, 8k, serene, natural color grading, "
                  "anamorphic, subtle film grain")
PASTORAL_NEG = ("people, person, human, hands, animals, buildings, road, text, watermark, logo, "
                "signature, cartoon, anime, illustration, blurry, lowres, oversaturated, deformed, "
                "frame, border, split screen, collage")
# Wan needs to be told what motion NOT to invent. Camera whip / scene changes break continuity.
PASTORAL_MOTION_NEG = ("static image, still frame, frozen, slideshow, jump cut, scene change, "
                       "camera shake, fast motion, time lapse, zoom burst, warping, morphing, "
                       "flicker, people, text, watermark, distorted, low quality")

# Light ladder: index into the FULL journey decides time of day, so a six-shot
# proof-of-concept from the head of the river is still first light, not noon.
PASTORAL_LIGHT = [
    (0.08, "pre-dawn blue hour, cold blue light, sun not yet risen"),
    (0.20, "first light, the very first warm gold touching the highest rock"),
    (0.34, "early sunrise, low raking gold light, long blue shadows"),
    (0.50, "sunrise, warm gold light spilling down the slope"),
    (0.66, "early morning, clear warm light, mist burning off"),
    (0.82, "mid morning, bright clear light, soft haze in the air"),
    (1.01, "full morning, high clear light, warm and open"),
]

PASTORAL_JOURNEY = [
    # --- I. the summit snowfield: where it starts (shots 0-11) -------------
    ("a high granite summit ridge under a wide empty sky, old snowfield clinging to the rock",
     "slow steady push in toward the ridge, thin wisps of cloud drifting left to right, snow surface still"),
    ("the crusted surface of an alpine snowfield, wind-carved ripples in the old snow",
     "gentle slow drift across the snow surface, faint spindrift lifting and settling"),
    ("the melting lip of a snow cornice, granular wet snow, dark rock beneath",
     "meltwater beading and swelling at the snow lip, a single drop growing heavier"),
    ("extreme close up of a single meltwater drop hanging from the edge of the snow",
     "the drop trembles, stretches, and falls out of frame; another begins to form"),
    ("a dark wet granite slab beneath the snow edge, water beading on the stone",
     "drops striking the wet stone one after another, each impact ringing out a small ripple"),
    ("a thin sheen of meltwater spreading across bare granite, sky reflected in the film of water",
     "the sheet of water creeps forward across the stone, reflections sliding with it"),
    ("tiny meltwater rivulets threading down through granular snow, blue shadow in the channels",
     "threads of water working downward through the snow, cutting their channels deeper"),
    ("water emerging from beneath the edge of a snowfield onto wet gravel",
     "water pulses out from under the snow, gravel shifting slightly in the flow"),
    ("a first small channel cut through coarse alpine gravel, clear water running",
     "clear water running steadily down the gravel channel, small stones trembling in the current"),
    ("a small clear pool at the foot of a snowfield, granite grit on the bottom",
     "the pool surface rippling as inflow disturbs it, sediment swirling slowly"),
    ("water spilling from a small pool over a lip of pale stone",
     "a thin sheet of water pouring over the stone lip, catching light as it falls"),
    ("a rivulet gathering pace down a scree slope of broken granite",
     "water accelerating between the loose rocks, braiding and rejoining"),

    # --- II. the trickle over rock (12-23) ---------------------------------
    ("a trickle of clear water running over pale granite slabs streaked with mineral",
     "water running steadily across the slab, light glinting and moving along the flow"),
    ("water threading between rounded boulders on an open alpine slope",
     "the stream weaving between the boulders, small standing waves holding steady"),
    ("a miniature waterfall a hand's width tall, dropping into a stone basin",
     "water pouring into the basin, the surface churning and settling in a loop"),
    ("cushions of bright green alpine moss growing beside running water on rock",
     "moss fronds nodding in the current, water sliding past them"),
    ("clear water running over a bed of red and grey pebbles",
     "the current pushing over the pebbles, light patterns dancing on the stones below"),
    ("the first hardy alpine wildflowers on a wet rock ledge above the stream",
     "flowers stirring gently in a light breeze, water moving past below"),
    ("a stream cutting a narrow groove into solid rock over ages",
     "water rushing through the narrow groove, spray lifting at the edges"),
    ("a clear plunge pool below a small drop, air bubbles rising through the water",
     "water pounding into the pool, bubble curtains rising and drifting away"),
    ("the stream widening across a bench of flat rock, sky reflected",
     "water spreading and sliding across the flat rock, reflections rippling"),
    ("the first stunted pines appearing at the edge of the water, treeline",
     "pine branches swaying gently, the stream running past their roots"),
    ("the stream entering the top of the treeline, dark conifers ahead",
     "slow forward drift downstream toward the trees, water running beneath"),
    ("morning mist drifting low across running water at the edge of the forest",
     "mist rolling slowly across the water surface, drifting downstream"),

    # --- III. the forest creek (24-35) -------------------------------------
    ("a clear creek running through a dark old conifer forest, moss on every stone",
     "water running over the mossy stones, light shifting through the branches above"),
    ("shafts of morning sunlight breaking through conifers onto a forest creek",
     "sunbeams sliding slowly across the water as branches move overhead"),
    ("a fallen mossy log spanning a forest creek, water running beneath",
     "water rushing under the log, foam curling and sliding downstream"),
    ("ferns and moss crowding the bank of a clear woodland creek",
     "ferns swaying in the draught off the water, current running past"),
    ("a bend in a forest creek where the water darkens and slows into a pool",
     "the pool turning slowly, leaves circling on the surface"),
    ("smooth water-worn stones on the bed of a shallow clear creek",
     "clear water flowing over the stones, refracted light rippling across them"),
    ("a small cascade over a moss-covered rock step in the forest",
     "water tumbling down the step, spray drifting into the shaft of light"),
    ("roots of old conifers exposed along an undercut creek bank",
     "water working past the roots, small eddies spinning and releasing"),
    ("golden light on the water where the forest canopy opens overhead",
     "the creek running through the bright patch, light glittering on the ripples"),
    ("a side spring joining the creek from a mossy hollow, the flow doubling",
     "two flows meeting and mixing, turbulence smoothing out downstream"),
    ("the creek broadening as the forest begins to thin, more sky above",
     "wider water moving steadily, canopy shadows drifting across it"),
    ("the last of the conifers giving way to open ground ahead, creek running out of the trees",
     "slow forward drift downstream, the trees opening out to bright meadow light"),

    # --- IV. the meadow brook (36-47) --------------------------------------
    ("a clear brook winding through a green alpine meadow, morning dew on the grass",
     "grass rippling in a light breeze, the brook running steadily through it"),
    ("wildflowers crowding both banks of a meadow brook, yellow and white",
     "flowers nodding in the breeze, water moving past beneath them"),
    ("dew on tall meadow grass backlit by low morning sun beside running water",
     "grass swaying, dew catching the light, brook running behind"),
    ("a wide shallow riffle where the brook runs fast and bright over gravel",
     "water racing over the gravel, sunlight scattering off the broken surface"),
    ("the brook curving in a long slow bend through open meadow",
     "the current sweeping around the bend, grasses trailing in the water"),
    ("thin morning mist lying over a meadow, the brook cutting through it",
     "mist drifting and thinning over the water as the light strengthens"),
    ("reeds and sedge standing in the shallow margin of a meadow brook",
     "reeds leaning and recovering in the breeze, water sliding past their stems"),
    ("a small gravel bar splitting the brook into two clear channels",
     "both channels running, rejoining below the bar in a smooth seam"),
    ("the brook running out of the meadow toward broader open country",
     "steady forward drift downstream, the valley opening ahead"),
    ("a low bluff of grass and stone where the brook drops into the valley floor",
     "water spilling down the low drop, the valley wide and bright beyond"),
    ("the brook joining a larger flow at the head of a wide green valley",
     "two flows meeting, the combined current broadening and slowing"),
    ("a broad slow reach of water reflecting the valley walls and morning sky",
     "the reflection rippling and settling as the wide current moves through"),

    # --- V. the valley river: home (48-59) ---------------------------------
    ("a wide clear river running through a broad green mountain valley in full morning light",
     "the river moving steadily, light dancing across the whole width of the water"),
    ("the river surface close up, deep and clear, gravel visible far below",
     "the deep current sliding past, sunlight patterns wavering on the riverbed"),
    ("a long gravel bar along the inside of a wide river bend",
     "the river sweeping around the bend past the gravel bar, steady and broad"),
    ("cottonwoods and willows lining the bank of a wide valley river",
     "leaves shimmering in the morning breeze, the river running past below"),
    ("morning light on the riffles of a broad river, the whole surface glittering",
     "the riffles breaking and reforming, light scattering across the water"),
    ("the river seen from the bank looking downstream, valley walls falling away",
     "slow forward drift downstream, the valley opening wider ahead"),
    ("a wide calm reach of river mirroring the mountains it came from",
     "the mirrored peaks rippling gently as the current passes"),
    ("the river braiding into several broad channels across a wide valley floor",
     "all the channels running together downstream, unhurried and certain"),
    ("a high wide view of the river winding away through the green valley",
     "slow steady aerial drift following the river downstream, valley scrolling past"),
    ("the river running out toward the far end of the valley under a wide morning sky",
     "the river moving steadily away, morning light broad and even across the land"),
    ("a distant view of the whole valley, the river a bright thread from the snow peaks above",
     "very slow pull back, the snow summit visible far behind where the water began"),
    ("the wide river filling the frame, moving steadily onward in full clear morning light",
     "the water moving through frame, unhurried, going only one direction"),
]


def pastoral_shot(i, total=None):
    """Return (still_prompt, motion_prompt) for journey index i, with the time of
    day fixed by position in the WHOLE journey (not in a shortened POC slice)."""
    total = total or len(PASTORAL_JOURNEY)
    still, motion = PASTORAL_JOURNEY[i % len(PASTORAL_JOURNEY)]
    p = i / max(1, total - 1)
    light = next(phrase for t, phrase in PASTORAL_LIGHT if p < t)
    return f"{still}, {light}", motion


GENRES = {
    'nature': {
        'pool': NATURE_POOL, 'style': NATURE_STYLE, 'neg': NATURE_NEG,
        'cfg': 5.0, 'music': 'orchestral', 'xfade_kind': 'fade', 'motion': 'gentle',
        'label': 'nature-orchestral',
    },
    'horror': {
        'pool': HORROR_POOL, 'style': HORROR_STYLE, 'neg': HORROR_NEG,
        'cfg': 5.5, 'music': 'horror', 'xfade_kind': 'fadeblack', 'motion': 'creep',
        'label': 'alien-horror',
    },
    # Real generated motion, not Ken Burns. Walks PASTORAL_JOURNEY in order.
    'pastoral': {
        'journey': PASTORAL_JOURNEY, 'style': PASTORAL_STYLE, 'neg': PASTORAL_NEG,
        'motion_neg': PASTORAL_MOTION_NEG, 'shot': pastoral_shot,
        'cfg': 5.0, 'music': 'pastoral', 'pipeline': 'video',
        'xfade_kind': 'fade', 'label': 'pastoral-river',
    },
}
