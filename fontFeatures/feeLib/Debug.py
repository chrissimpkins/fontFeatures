import warnings

from . import FEEVerb
from fontFeatures.feeLib import GlyphSelector

PARSEOPTS = dict(use_helpers=True)
GRAMMAR = ""
ShowClass_GRAMMAR = """
?start: action
action: glyphselector
"""
DumpClassNames_GRAMMAR = DumpClasses_GRAMMAR = """
?start: action
action:
"""
VERBS = ["ShowClass", "DumpClassNames", "DumpClasses"]

class DumpClasses(FEEVerb):
    def action(self, _):
        for c in self.parser.fontfeatures.namedClasses:
            ShowClass(self.parser).action((GlyphSelector({"classname":c}, [], None),))
        return

class DumpClassNames(FEEVerb):
    def action(self, _):
        warnings.warn(" ".join(self.parser.fontfeatures.namedClasses))

        return

class ShowClass(FEEVerb):
    def action(self, args):
        (classname,) = args
        warnings.warn(
            "%s = %s"
            % (
                classname.as_text(),
                " ".join(classname.resolve(self.parser.fontfeatures, self.parser.font)),
            )
        )
        return
