"""One-time static OFL font derivative, not a production font compiler."""

import sys

from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

font = instantiateVariableFont(TTFont(sys.argv[1]), {"wght": 400}, inplace=False)
for record in font["name"].names:
    if record.nameID in {1, 4, 6, 16}:
        name = "TreasuryTallyReportSans" if record.nameID == 6 else "TreasuryTally Report Sans"
        record.string = name.encode(record.getEncoding())
font.save(sys.argv[2])
