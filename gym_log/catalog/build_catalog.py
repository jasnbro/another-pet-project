"""Build gym_log/data/catalog.csv: Workout Guide 1.0.0 exercises + training metadata.

Metadata comes from ExerciseAPI dataset 1.1.0 (CC BY 4.0) where an exercise maps
cleanly, otherwise from the hand-written annotations below. Every row records
its source in `metadata_source`. See README.md in this folder.

Usage (from gym_log/):  uv run python catalog/build_catalog.py
"""
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "sources" / "workout-guide-1.0.0" / "manifest.json"
EXERCISEAPI = HERE / "sources" / "exerciseapi-1.1.0" / "exercises.json"
OUT = HERE.parent / "data" / "catalog.csv"

# Workout Guide slug -> ExerciseAPI id (same movement, close enough equipment).
EA_MAP = {
    "bench-press": "barbell_bench_press", "incline-bench-press": "incline_barbell_press",
    "incline-dumbbell-press": "incline_dumbbell_press", "dumbbell-bench-press": "dumbbell_bench_press",
    "decline-bench-press": "decline_barbell_press", "machine-chest-press": "chest_press_machine",
    "pec-deck": "pec_deck_fly", "cable-fly": "cable_fly", "push-up": "pushup",
    "overhead-press": "overhead_press", "seated-dumbbell-press": "seated_dumbbell_press",
    "arnold-press": "arnold_press", "lateral-raise": "dumbbell_lateral_raise",
    "cable-lateral-raise": "cable_lateral_raise", "rear-delt-fly": "dumbbell_rear_delt_fly",
    "bent-over-rear-delt-raise": "dumbbell_rear_delt_fly", "reverse-pec-deck": "reverse_pec_deck",
    "face-pull": "face_pull", "deadlift": "conventional_deadlift", "romanian-deadlift": "romanian_deadlift",
    "barbell-row": "barbell_row", "t-bar-row": "t_bar_row", "one-arm-dumbbell-row": "single_arm_dumbbell_row",
    "chest-supported-row": "chest_supported_dumbbell_row", "seated-row": "seated_cable_row",
    "lat-pulldown": "lat_pulldown", "close-grip-lat-pulldown": "neutral_grip_pulldown",
    "straight-arm-pulldown": "straight_arm_pulldown", "pull-up": "bodyweight_pullup",
    "assisted-pull-up": "assisted_pullup", "weighted-pull-up": "weighted_pullup", "shrug": "barbell_shrug",
    "squat": "barbell_back_squat", "front-squat": "front_squat", "hack-squat": "hack_squat",
    "leg-press": "leg_press", "bulgarian-split-squat": "bulgarian_split_squat",
    "walking-lunge": "walking_lunge", "step-up": "step_up", "leg-extension": "leg_extension",
    "lying-leg-curl": "lying_leg_curl", "seated-leg-curl": "seated_leg_curl", "hip-thrust": "barbell_hip_thrust",
    "good-morning": "good_morning", "standing-calf-raise": "standing_calf_raise",
    "seated-calf-raise": "seated_calf_raise", "hammer-curl": "dumbbell_hammer_curl",
    "preacher-curl": "preacher_curl", "cable-curl": "cable_curl", "reverse-curl": "reverse_ez_bar_curl",
    "wrist-curl": "barbell_wrist_curl", "tricep-pushdown": "cable_triceps_pushdown",
    "overhead-tricep-extension": "overhead_cable_triceps_extension", "skull-crusher": "ez_bar_skullcrusher",
    "close-grip-bench-press": "close_grip_bench_press", "dip": "dip", "plank": "plank",
    "hanging-leg-raise": "hanging_leg_raise", "cable-crunch": "cable_crunch", "ab-wheel": "ab_wheel_rollout",
    "dumbbell-fly": "dumbbell_fly_flat", "landmine-press": "landmine_press",
    "machine-shoulder-press": "shoulder_press_machine", "push-press": "push_press",
    "machine-lateral-raise": "machine_lateral_raise", "cable-rear-delt-fly": "cable_rear_delt_fly",
    "pendlay-row": "pendlay_row", "inverted-row": "inverted_row", "meadows-row": "meadows_row",
    "rack-pull": "rack_pull", "back-extension": "back_extension", "dumbbell-shrug": "dumbbell_shrug",
    "goblet-squat": "goblet_squat", "smith-machine-squat": "smith_machine_squat", "belt-squat": "belt_squat",
    "nordic-hamstring-curl": "nordic_curl", "single-leg-romanian-deadlift": "single_leg_rdl",
    "reverse-lunge": "reverse_lunge", "cable-pull-through": "cable_pull_through",
    "dumbbell-hip-thrust": "dumbbell_hip_thrust", "dumbbell-romanian-deadlift": "dumbbell_rdl",
    "reverse-hyperextension": "reverse_hyper", "leg-press-calf-raise": "leg_press_calf_raise",
    "incline-dumbbell-curl": "incline_dumbbell_curl", "concentration-curl": "dumbbell_concentration_curl",
    "ez-bar-curl": "ez_bar_curl", "spider-curl": "spider_curl", "rope-hammer-curl": "cable_hammer_curl",
    "dumbbell-overhead-tricep-extension": "dumbbell_overhead_extension", "bench-dip": "bench_dip",
    "pallof-press": "pallof_press", "weighted-crunch": "weighted_crunch", "lying-leg-raise": "lying_leg_raise",
    "hollow-body-hold": "hollow_body_hold", "pike-push-up": "pike_pushup",
    "feet-elevated-pike-push-up": "elevated_pike_pushup", "wall-handstand-push-up": "wall_handstand_pushup",
    "handstand-push-up": "freestanding_hspu", "diamond-push-up": "diamond_pushup",
    "incline-push-up": "incline_pushup", "decline-push-up": "incline_pushup_feet_low",
    "negative-pull-up": "negative_pullup", "l-sit-pull-up": "lsit_pullup", "pistol-squat": "full_pistol_squat",
    "assisted-pistol-squat": "assisted_squat", "shrimp-squat": "shrimp_squat", "sissy-squat": "sissy_squat",
    "calf-raise": "bodyweight_calf_raise", "l-sit-hold": "full_lsit", "bird-dog": "bird_dog",
    "cable-standing-hip-abduction": "cable_hip_abduction", "banded-glute-bridge": "band_glute_bridge",
    "banded-face-pull": "band_face_pull", "banded-row": "band_seated_row",
    "banded-lat-pulldown": "band_lat_pulldown", "captains-chair-knee-raise": "captains_chair_leg_raise",
    "single-leg-box-squat": "box_pistol_squat",
}

# Mapped rows where ExerciseAPI's substitution group breaks e1RM comparability.
GROUP_OVERRIDES = {
    "deadlift": ("hip_hinge_deadlift", "EA files it under lower_back_extension with back extensions"),
    "dip": ("dip_vertical_push", "EA splits dips between triceps_extension and dip_vertical_push"),
    "close-grip-bench-press": ("chest_horizontal_press", "a pressing e1RM, not comparable to pushdowns"),
    "hammer-curl": ("biceps_curl", "EA groups it with wrist curls"),
    "rope-hammer-curl": ("biceps_curl", "EA groups it with wrist curls"),
    "inverted-row": ("back_horizontal_row", "EA files it in the front-lever chain"),
    "meadows-row": ("back_horizontal_row", "EA files it under vertical pulls"),
}

# Unmapped rows: slug | substitution_group | modality | sfr | rep_low | rep_high  ("-" = null)
CLAUDE_ROWS = """
weighted-push-up|chest_horizontal_press|hypertrophy|moderate|6|12
front-raise|front_delt_raise|hypertrophy|moderate|10|15
upright-row|side_delt_raise|hypertrophy|moderate|8|12
dumbbell-bent-over-row|back_horizontal_row|hypertrophy|moderate|8|12
machine-row|back_horizontal_row|hypertrophy|high|8|12
chin-up|lats_vertical_pull|hypertrophy|moderate|5|12
glute-bridge|glute_hip_thrust|hypertrophy|moderate|12|25
bicep-curl|biceps_curl|hypertrophy|high|8|12
leg-curl|hamstring_curl|hypertrophy|high|10|15
assisted-dip|dip_vertical_push|hypertrophy|high|8|12
side-plank|core_anti_lateral|hypertrophy|moderate|20|45
incline-cable-fly|chest_fly|hypertrophy|high|10|15
decline-dumbbell-press|chest_horizontal_press|hypertrophy|moderate|8|12
smith-machine-bench-press|chest_horizontal_press|hypertrophy|high|6|12
chest-dip|dip_vertical_push|hypertrophy|moderate|6|12
weighted-dip|dip_vertical_push|hypertrophy|moderate|6|10
standing-dumbbell-press|shoulder_vertical_press|hypertrophy|moderate|6|12
cable-front-raise|front_delt_raise|hypertrophy|moderate|10|15
plate-front-raise|front_delt_raise|hypertrophy|moderate|10|15
single-arm-cable-row|back_horizontal_row|hypertrophy|high|10|15
wide-grip-lat-pulldown|lats_vertical_pull|hypertrophy|high|8|12
neutral-grip-pull-up|lats_vertical_pull|hypertrophy|moderate|5|12
assisted-chin-up|lats_vertical_pull|hypertrophy|high|8|12
weighted-chin-up|lats_vertical_pull|hypertrophy|moderate|5|10
sumo-deadlift|hip_hinge_deadlift|hypertrophy|low|3|8
trap-bar-deadlift|hip_hinge_deadlift|hypertrophy|moderate|4|8
dumbbell-sumo-deadlift|hip_hinge_deadlift|hypertrophy|moderate|8|12
smith-machine-romanian-deadlift|hamstring_hinge|hypertrophy|moderate|8|12
kettlebell-romanian-deadlift|hamstring_hinge|hypertrophy|moderate|10|15
landmine-romanian-deadlift|hamstring_hinge|hypertrophy|moderate|8|12
cable-kickback|glute_kickback|hypertrophy|high|12|20
machine-glute-kickback|glute_kickback|hypertrophy|high|10|15
hip-abduction-machine|glute_abduction|hypertrophy|high|12|20
single-leg-glute-bridge|glute_hip_thrust|hypertrophy|moderate|10|20
barbell-glute-bridge|glute_hip_thrust|hypertrophy|high|8|15
dumbbell-glute-bridge|glute_hip_thrust|hypertrophy|high|10|20
smith-machine-hip-thrust|glute_hip_thrust|hypertrophy|high|8|12
cable-standing-hip-adduction|hip_adduction|hypertrophy|high|12|20
hip-adduction-machine|hip_adduction|hypertrophy|high|12|20
smith-machine-bulgarian-split-squat|quad_lunge|hypertrophy|moderate|8|12
smith-machine-reverse-lunge|quad_lunge|hypertrophy|moderate|8|12
smith-machine-split-squat|quad_lunge|hypertrophy|moderate|8|12
split-squat|quad_lunge|hypertrophy|moderate|8|12
heel-elevated-goblet-squat|quad_squat|hypertrophy|high|10|15
dumbbell-sumo-squat|quad_squat|hypertrophy|moderate|10|15
front-foot-elevated-split-squat|quad_lunge|hypertrophy|moderate|8|12
deficit-reverse-lunge|quad_lunge|hypertrophy|moderate|8|12
dumbbell-lateral-lunge|quad_lunge|hypertrophy|moderate|8|12
dumbbell-curtsy-lunge|quad_lunge|hypertrophy|moderate|10|15
landmine-squat|quad_squat|hypertrophy|moderate|8|12
kettlebell-swing|hip_hinge_ballistic|conditioning|-|15|25
glute-focused-back-extension|lower_back_extension|hypertrophy|high|12|20
donkey-calf-raise|calf_standing|hypertrophy|high|10|15
wall-sit|quad_isometric|conditioning|-|30|60
jump-squat|plyometric|conditioning|-|8|15
drag-curl|biceps_curl|hypertrophy|moderate|8|12
rope-tricep-pushdown|triceps_extension|hypertrophy|high|10|15
dumbbell-skull-crusher|triceps_extension|hypertrophy|moderate|8|12
single-dumbbell-skullcrusher|triceps_extension|hypertrophy|moderate|10|15
single-arm-dumbbell-tricep-extension|triceps_extension|hypertrophy|moderate|10|15
tricep-kickback|triceps_extension|hypertrophy|moderate|12|20
wrist-extension|forearm_extension|hypertrophy|high|15|25
farmer-carry|loaded_carry|conditioning|-|-|-
crunch|abs_flexion|hypertrophy|moderate|12|25
reverse-crunch|abs_flexion|hypertrophy|moderate|10|20
russian-twist|core_rotation|hypertrophy|low|10|20
bicycle-crunch|abs_flexion|hypertrophy|moderate|12|25
mountain-climber|conditioning_bodyweight|conditioning|-|20|40
dead-bug|abs_anti_extension|hypertrophy|moderate|8|15
cable-woodchop|core_rotation|hypertrophy|high|10|15
half-kneeling-pallof-press|abs_anti_extension|hypertrophy|high|10|15
cable-pallof-hold|abs_anti_extension|hypertrophy|moderate|20|40
hanging-knee-raise|abs_flexion|hypertrophy|moderate|10|15
decline-sit-up|abs_flexion|hypertrophy|moderate|10|20
weighted-russian-twist|core_rotation|hypertrophy|low|10|20
dumbbell-side-bend|core_anti_lateral|hypertrophy|moderate|10|15
knee-push-up|chest_horizontal_press|hypertrophy|moderate|8|20
wide-push-up|chest_horizontal_press|hypertrophy|moderate|8|20
archer-push-up|chest_horizontal_press|calisthenics|moderate|5|10
typewriter-push-up|chest_horizontal_press|calisthenics|moderate|5|10
explosive-push-up|plyometric|conditioning|-|5|10
hindu-push-up|chest_horizontal_press|hypertrophy|low|8|15
scapular-push-up|scapular_prehab|prehab|-|10|15
push-up-shoulder-tap|abs_anti_extension|hypertrophy|moderate|10|20
wall-push-up|chest_horizontal_press|hypertrophy|moderate|10|20
wall-walk|handstand_vertical_push|calisthenics|moderate|3|8
chair-dip|dip_vertical_push|hypertrophy|moderate|10|20
doorway-row|back_horizontal_row|hypertrophy|moderate|10|20
towel-row|back_horizontal_row|hypertrophy|moderate|10|20
prone-y-raise|scapular_prehab|prehab|-|10|15
prone-t-raise|scapular_prehab|prehab|-|10|15
superman|lower_back_extension|hypertrophy|moderate|10|20
superman-hold|lower_back_extension|hypertrophy|moderate|20|40
reverse-snow-angel|scapular_prehab|prehab|-|10|15
dead-hang|grip_hang|conditioning|-|20|60
active-hang|grip_hang|conditioning|-|20|45
scapular-pull-up|scapular_prehab|prehab|-|8|12
commando-pull-up|lats_vertical_pull|calisthenics|moderate|4|10
towel-pull-up|lats_vertical_pull|calisthenics|low|3|8
bodyweight-squat|quad_squat|hypertrophy|moderate|15|25
cossack-squat|quad_lunge|hypertrophy|moderate|6|12
forward-lunge|quad_lunge|hypertrophy|moderate|10|15
lateral-lunge|quad_lunge|hypertrophy|moderate|10|15
curtsy-lunge|quad_lunge|hypertrophy|moderate|10|20
skater-squat|single_leg_squat_progression|calisthenics|moderate|5|12
step-down|single_leg_squat_progression|calisthenics|moderate|8|15
single-leg-calf-raise|calf_standing|hypertrophy|high|10|20
glute-bridge-march|glute_activation|prehab|-|10|20
frog-pump|glute_hip_thrust|hypertrophy|moderate|15|30
donkey-kick|glute_kickback|hypertrophy|low|12|20
fire-hydrant|glute_abduction|hypertrophy|low|12|20
clamshell|glute_abduction|hypertrophy|low|15|25
hip-airplane|glute_activation|prehab|-|5|10
side-lying-hip-abduction|glute_abduction|hypertrophy|low|15|25
side-lying-leg-raise|glute_abduction|hypertrophy|low|15|25
lying-hamstring-walkout|hamstring_curl|hypertrophy|moderate|8|12
towel-hamstring-curl|hamstring_curl|hypertrophy|moderate|8|15
stability-ball-hamstring-curl|hamstring_curl|hypertrophy|high|10|15
banded-hip-thrust|glute_hip_thrust|hypertrophy|high|15|25
banded-frog-pump|glute_hip_thrust|hypertrophy|moderate|20|30
banded-clamshell|glute_abduction|hypertrophy|moderate|15|25
banded-lateral-walk|glute_abduction|hypertrophy|moderate|10|20
banded-monster-walk|glute_abduction|hypertrophy|moderate|10|20
banded-squat|quad_squat|hypertrophy|low|15|25
banded-donkey-kick|glute_kickback|hypertrophy|moderate|12|20
banded-fire-hydrant|glute_abduction|hypertrophy|moderate|12|20
banded-kickback|glute_kickback|hypertrophy|moderate|12|20
banded-standing-hip-abduction|glute_abduction|hypertrophy|high|15|25
banded-seated-hip-abduction|glute_abduction|hypertrophy|high|15|25
band-pull-apart|rear_delt_fly|hypertrophy|high|15|25
banded-pallof-press|abs_anti_extension|hypertrophy|high|10|15
banded-woodchop|core_rotation|hypertrophy|moderate|10|15
banded-dead-bug|abs_anti_extension|hypertrophy|moderate|8|15
hollow-rock|core_anti_extension_progression|calisthenics|moderate|10|20
v-up|abs_flexion|hypertrophy|moderate|10|20
flutter-kick|abs_flexion|hypertrophy|low|20|40
toe-touch|abs_flexion|hypertrophy|low|12|25
heel-tap|abs_flexion|hypertrophy|low|15|30
plank-shoulder-tap|abs_anti_extension|hypertrophy|moderate|10|20
plank-jack|conditioning_bodyweight|conditioning|-|20|40
bear-plank|abs_anti_extension|hypertrophy|moderate|20|45
bear-crawl|conditioning_bodyweight|conditioning|-|20|40
crab-walk|conditioning_bodyweight|conditioning|-|20|40
inchworm|warmup|mobility|-|5|10
seated-knee-tuck|abs_flexion|hypertrophy|moderate|10|20
side-plank-hip-dip|core_anti_lateral|hypertrophy|moderate|10|15
copenhagen-plank|hip_adduction|hypertrophy|moderate|15|30
dragon-flag|core_anti_extension_progression|calisthenics|moderate|3|8
"""

# Exercises Gym Log uses that Workout Guide lacks. No illustration frames.
CUSTOM_ROWS = [
    dict(id="dumbbell-floor-press", name="Dumbbell Floor Press", exercise_type="weight_reps", equipment="Dumbbell",
         primary_muscle="Chest", secondary_muscles="Triceps|Shoulders", is_stretch=False, frame_paths="",
         substitution_group="chest_horizontal_press", modality="hypertrophy", sfr_class="moderate",
         default_rep_low=8, default_rep_high=12),
    dict(id="dumbbell-pullover", name="Dumbbell Pullover", exercise_type="weight_reps", equipment="Dumbbell",
         primary_muscle="Lats", secondary_muscles="Chest|Triceps", is_stretch=False, frame_paths="",
         substitution_group="lats_pullover", modality="hypertrophy", sfr_class="moderate",
         default_rep_low=10, default_rep_high=15),
    dict(id="prone-band-leg-curl", name="Prone Band Leg Curl", exercise_type="bodyweight_reps",
         equipment="Resistance Band", primary_muscle="Hamstrings", secondary_muscles="Calves", is_stretch=False,
         frame_paths="", substitution_group="hamstring_curl", modality="hypertrophy", sfr_class="moderate",
         default_rep_low=12, default_rep_high=20),
]

CARDIO = {"running", "walking", "cycling", "rowing", "stair-climber", "elliptical", "swimming", "jump-rope",
          "assault-bike", "skierg", "hiking", "treadmill-incline-walk", "battle-ropes"}
CONDITIONING = {"burpee", "half-burpee", "squat-thrust", "high-knees", "jumping-jack", "skater-hop",
                "lateral-shuffle", "fast-feet", "sprawl", "seal-jack"}

SFR_ORDER = {"high": 0, "moderate": 1, "low": 2}
EQUIP_ORDER = {"Barbell": 0, "Dumbbell": 1, "Machine": 2, "Cable": 3, "Kettlebell": 4, "Plate": 5}
RANKED_MODALITIES = {"hypertrophy", "calisthenics"}


def nullable(v):
    return None if v == "-" else (int(v) if v.isdigit() else v)


def main(out: Path = OUT):
    wg = json.loads(MANIFEST.read_text(encoding="utf-8"))
    ea = {e["id"]: e for e in json.loads(EXERCISEAPI.read_text(encoding="utf-8"))}
    claude = {}
    for line in CLAUDE_ROWS.strip().splitlines():
        slug, group, modality, sfr, lo, hi = line.split("|")
        claude[slug] = dict(substitution_group=group, modality=modality, sfr_class=nullable(sfr),
                            default_rep_low=nullable(lo), default_rep_high=nullable(hi))

    rows, problems = [], []
    for e in wg:
        slug = e["slug"]
        row = dict(id=slug, name=e["name"], exercise_type=e["exerciseType"], equipment=e["equipment"],
                   primary_muscle=e["primaryMuscle"], secondary_muscles="|".join(e["secondaryMuscles"]),
                   is_stretch=e["isStretch"],
                   frame_paths="|".join(f["path"].replace("assets/", "", 1) for f in e["frames"]))
        ea_id = EA_MAP.get(slug)
        if ea_id:
            if ea_id not in ea:
                problems.append(f"{slug}: unknown EA id {ea_id}")
                continue
            src = ea[ea_id]
            group, note = src["e1rm_substitution_group"], ""
            if slug in GROUP_OVERRIDES:
                group, note = GROUP_OVERRIDES[slug]
            row.update(substitution_group=group, modality=src["modality"], sfr_class=src["sfr_class"],
                       default_rep_low=src["default_rep_low"], default_rep_high=src["default_rep_high"],
                       exerciseapi_id=ea_id, ea_rank=src["preferred_rank"],
                       metadata_source="exerciseapi+override" if note else "exerciseapi", override_note=note)
        elif slug in claude:
            row.update(claude[slug], exerciseapi_id=None, ea_rank=None, metadata_source="claude",
                       override_note="")
        elif slug in CARDIO or slug in CONDITIONING or e["isStretch"]:
            group, modality = (("cardio", "conditioning") if slug in CARDIO else
                               ("conditioning_bodyweight", "conditioning") if slug in CONDITIONING else
                               ("mobility", "mobility"))
            lo, hi = (30, 60) if e["isStretch"] else (None, None)
            row.update(substitution_group=group, modality=modality, sfr_class=None, default_rep_low=lo,
                       default_rep_high=hi, exerciseapi_id=None, ea_rank=None, metadata_source="claude",
                       override_note="")
        else:
            problems.append(f"{slug}: no metadata")
            continue
        row["rep_unit"] = (None if row["default_rep_low"] is None else
                           "seconds" if e["exerciseType"] == "duration" else "reps")
        rows.append(row)

    for c in CUSTOM_ROWS:
        rows.append(dict(c, exerciseapi_id=None, ea_rank=None, metadata_source="custom", override_note="",
                         rep_unit="reps"))

    # preferred_rank: 1-based within substitution_group, hypertrophy/calisthenics only.
    # Order: SFR class, then ExerciseAPI's curator rank where inherited, then loadable equipment first.
    by_group = defaultdict(list)
    for r in rows:
        if r["modality"] in RANKED_MODALITIES and r["sfr_class"]:
            by_group[r["substitution_group"]].append(r)
    for members in by_group.values():
        members.sort(key=lambda r: (SFR_ORDER[r["sfr_class"]], r["ea_rank"] or 50,
                                    EQUIP_ORDER.get(r["equipment"], 9), r["id"]))
        for i, r in enumerate(members, 1):
            r["preferred_rank"] = i
    for r in rows:
        r.setdefault("preferred_rank", None)
        del r["ea_rank"]

    if problems:
        sys.exit("\n".join(problems))
    unused = set(EA_MAP) - {r["id"] for r in rows}
    if unused:
        sys.exit(f"EA_MAP slugs not in manifest: {sorted(unused)}")

    cols = ["id", "name", "exercise_type", "equipment", "primary_muscle", "secondary_muscles", "is_stretch",
            "modality", "substitution_group", "sfr_class", "preferred_rank", "default_rep_low",
            "default_rep_high", "rep_unit", "frame_paths", "metadata_source", "exerciseapi_id", "override_note"]
    with Path(out).open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} rows -> {out}")


if __name__ == "__main__":
    main()
