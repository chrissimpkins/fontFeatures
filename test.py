from pathlib import Path
from fontTools.ttLib import TTFont

import fontFeatures


def is_encoded_glyph_available(tt, hex):
    return hex in tt.getBestCmap()


REQUIRED_BASE_YORUBA = [0x1ECD]
REQUIRED_BASE_YORUBA_NAME = ["uni1ECD"]
REQUIRED_MARK_YORUBA = [0x0300, 0x0301]
REQUIRED_MARK_YORUBA_NAME = ["gravecomb", "acutecomb"]

REQUIRED_LANGS = [("DFLT", "dflt"), ("latn", "dflt"), ("latn", "yor")]

fontpath = Path("Montserrat-Regular.ttf")

tt = TTFont(fontpath)
ff = fontFeatures.ttLib.unparse(tt)

# confirm base forms are available
for hex in REQUIRED_BASE_YORUBA:
    assert is_encoded_glyph_available(tt, hex)

print("Found all required base forms")

# confirm mark forms are available
for hex in REQUIRED_MARK_YORUBA:
    assert is_encoded_glyph_available(tt, hex)

print("Found all required mark forms")

filtered_routines = [
    routine
    for routine in ff.routines
    if (REQUIRED_LANGS[0] in routine.languages)
    or (REQUIRED_LANGS[1] in routine.languages)
    or (REQUIRED_LANGS[2] in routine.languages)
]


mark2base = [
    routine for routine in filtered_routines if routine.lookupType == "MarkToBase"
]

for routine in mark2base:
    for rule in routine.rules:
        for base, base_metrics in rule.bases.items():
            if base == REQUIRED_BASE_YORUBA_NAME[0]:
                # print(f"Found {base} : {base_metrics}")

                for mark_glyph, mark_metrics in rule.marks.items():
                    if mark_glyph in REQUIRED_MARK_YORUBA_NAME:
                        print(
                            f"Found anchor for {base}:{mark_glyph} ==> {base_metrics}:{mark_metrics}"
                        )
                        print(f"{rule.base_name}, {rule.mark_name}")
