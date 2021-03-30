import io
import fontFeatures
from fontTools.feaLib.parser import Parser
import fontTools.feaLib.ast as ast
from warnings import warn

class FeaParser:
    """Turns a AFDKO feature file or string into a FontFeatures object.

    Args:
        featurefile: File object or string.
        font: Optionally, a TTFont object.
    """
    def __init__(self, featurefile, font=None):

        self.ff = fontFeatures.FontFeatures()
        self.markclasses = {}
        self.currentFeature = None
        self.currentRoutine = None
        self.gensym = 1
        self.glyphmap = ()
        self.currentLanguage = None
        if font:
            self.glyphmap = font.getReverseGlyphMap()
        if isinstance(featurefile, str):
            featurefile = io.StringIO(featurefile)
        self.featurefile = featurefile
        self.parser = Parser(self.featurefile, self.glyphmap)
        self.parser.ast.ValueRecord = fontFeatures.ValueRecord

    def parse(self):
        """Parse the feature code.

        Returns:
            A ``FontFeatures`` object containing the rules of this file.
        """

        # Borrow glyph classes
        for name, members in self.ff.namedClasses.items():
            glyphclass = ast.GlyphClassDefinition(
                name, ast.GlyphClass([m for m in members])
            )
            self.parser.glyphclasses_.define(name, glyphclass)

        parsetree = self.parser.parse()

        # Return glyph classes
        if len(self.parser.glyphclasses_.scopes_):
            for name, definition in self.parser.glyphclasses_.scopes_[-1].items():
                if isinstance(definition, ast.MarkClass):
                    pass
                    # self.ff.namedClasses[name] = list(definition.glyphs.keys())
                else:
                    self.ff.namedClasses[name] = definition.glyphs.glyphs

        self.features_ = {}
        parsetree.build(self)
        return self.ff

    def find_named_routine(self, name):
        candidates = list(filter(lambda x: x.name == name, self.ff.routines))
        if not candidates:
            raise ValueError("Reference to undefined routine " + name)
        if len(candidates) > 1:
            raise ValueError("This can't happen")
        return candidates[0]

    def _start_routine_if_necessary(self, location):
        if not self.currentRoutine:
            self._start_routine(location, "")

    def _start_routine(self, location, name):
        location = "%s:%i:%i" % (location)
        # print("Starting routine at "+location)
        self._discard_empty_routine()
        self.currentRoutine = fontFeatures.Routine(name=name, address=location)
        if not name:
            self.currentRoutine.name = "unnamed_routine_%i" % self.gensym
            self.gensym = self.gensym + 1
        self.currentRoutineFlag = 0
        if self.currentFeature:
            reference = self.ff.referenceRoutine(self.currentRoutine)
            self.ff.addFeature(self.currentFeature, [reference])
        else:
            self.ff.routines.append(self.currentRoutine)

    def start_lookup_block(self, location, name):
        self._start_routine(location, name)

    def start_feature(self, location, name):
        self.currentFeature = name

    def set_font_revision(self, location, revision):
        pass

    def add_name_record(self, *args):
        pass

    def add_featureName(self, tag):
        # XXX support this
        pass

    def set_script(self, location, script):
        self.currentLanguage = [(script, "*")]

    def set_language(self, location, language, include_default, required):
        self.currentLanguage = [(self.currentLanguage[0][0], language)]

    def add_single_subst(self, location, prefix, suffix, mapping, forceChain):
        self._start_routine_if_necessary(location)
        location = "%s:%i:%i" % (location)
        s = fontFeatures.Substitution(
            input_=[list(mapping.keys())],
            replacement=[list(mapping.values())],
            precontext= [[str(g) for g in group] for group in prefix],
            postcontext= [[str(g) for g in group] for group in suffix],
            address=location,
            languages=self.currentLanguage
        )
        self.currentRoutine.addRule(s)


    def add_reverse_chain_single_subst(self, location, prefix, suffix, mapping):
        self._start_routine_if_necessary(location)
        location = "%s:%i:%i" % (location)
        s = fontFeatures.Substitution(
            input_=[list(mapping.keys())],
            replacement=[list(mapping.values())],
            precontext= [[str(g) for g in group] for group in prefix],
            postcontext= [[str(g) for g in group] for group in suffix],
            address=location,
            languages=self.currentLanguage,
            reverse=True
        )
        self.currentRoutine.addRule(s)

    def add_multiple_subst(
        self, location, prefix, glyph, suffix, replacements, forceChain
    ):
        self._start_routine_if_necessary(location)
        location = "%s:%i:%i" % (location)
        s = fontFeatures.Substitution(
            input_=[[glyph]],
            replacement=[[g] for g in replacements],
            precontext= [[str(g) for g in group] for group in prefix],
            postcontext= [[str(g) for g in group] for group in suffix],
            address=location,
            languages=self.currentLanguage
        )
        self.currentRoutine.addRule(s)

    def add_alternate_subst(self, location, prefix, glyph, suffix, replacement):
        self._start_routine_if_necessary(location)
        location = "%s:%i:%i" % (location)
        s = fontFeatures.Substitution(
            input_=[[glyph]],
            replacement=[replacement],
            precontext= [[str(g) for g in group] for group in prefix],
            postcontext= [[str(g) for g in group] for group in suffix],
            address=location,
            languages=self.currentLanguage
        )
        self.currentRoutine.addRule(s)

    def add_ligature_subst(
        self, location, prefix, glyphs, suffix, replacement, forceChain
    ):
        self._start_routine_if_necessary(location)
        location = "%s:%i:%i" % (location)
        s = fontFeatures.Substitution(
            input_=[list(x) for x in glyphs],
            replacement=[[replacement]],
            precontext= [[str(g) for g in group] for group in prefix],
            postcontext= [[str(g) for g in group] for group in suffix],
            address=location,
            languages=self.currentLanguage
        )
        self.currentRoutine.addRule(s)

    def add_chain_context_subst(self, location, prefix, glyphs, suffix, lookups):
        self._start_routine_if_necessary(location)
        location = "%s:%i:%i" % (location)
        # Find named feature
        mylookups = []
        for x in lookups:
            if x:
                mylookups.append([self.find_named_routine(y.name) for y in x])
            else:
                mylookups.append(None)
        s = fontFeatures.Chaining(
            input_=[list(x) for x in glyphs],
            precontext= [[str(g) for g in group] for group in prefix],
            postcontext= [[str(g) for g in group] for group in suffix],
            lookups=mylookups,
            address=location,
            languages=self.currentLanguage
        )
        self.currentRoutine.addRule(s)

    add_chain_context_pos = add_chain_context_subst

    def add_single_pos(self, location, prefix, suffix, pos, forceChain):
        self._start_routine_if_necessary(location)
        location = "%s:%i:%i" % (location)
        s = fontFeatures.Positioning(
            glyphs=[p[0] for p in pos],
            valuerecords=[p[1] for p in pos],
            precontext= [[str(g) for g in group] for group in prefix],
            postcontext= [[str(g) for g in group] for group in suffix],
            address=location,
            languages=self.currentLanguage
        )
        self.currentRoutine.addRule(s)

    def add_specific_pair_pos(self, location, glyph1, value1, glyph2, value2):
        self._start_routine_if_necessary(location)
        location = "%s:%i:%i" % (location)
        s = fontFeatures.Positioning(
            glyphs=[[glyph1], [glyph2]], valuerecords=[value1, value2], address=location,
            languages=self.currentLanguage
        )
        self.currentRoutine.addRule(s)

    def add_class_pair_pos(self, location, glyphclass1, value1, glyphclass2, value2):
        self._start_routine_if_necessary(location)
        location = "%s:%i:%i" % (location)
        s = fontFeatures.Positioning(
            glyphs=[glyphclass1, glyphclass2],
            valuerecords=[value1, value2],
            address=location,
            languages=self.currentLanguage
        )
        self.currentRoutine.addRule(s)

    def add_cursive_pos(self, location, glyphclass, entryAnchor, exitAnchor):
        self._start_routine_if_necessary(location)
        location = "%s:%i:%i" % (location)
        basedict, markdict = {}, {}
        if entryAnchor:
            basedict = {g: (entryAnchor.x, entryAnchor.y) for g in glyphclass}
        if exitAnchor:
            markdict = {g: (exitAnchor.x, exitAnchor.y) for g in glyphclass}
        s = fontFeatures.Attachment(
            base_name="cursive_entry",
            mark_name="cursive_exit",
            bases=basedict,
            marks=markdict,
            address=location,
            languages=self.currentLanguage
        )
        self.currentRoutine.addRule(s)

    def add_mark_base_pos(self, location, bases, marks):
        self._start_routine_if_necessary(location)
        location = "%s:%i:%i" % (location)
        for baseanchor, markclass in marks:
            assert len(markclass.definitions) == 1
            markanchor = markclass.definitions[0].anchor
            s = fontFeatures.Attachment(
                base_name=markclass.name,
                mark_name=markclass.name,
                bases={g: (baseanchor.x, baseanchor.y) for g in bases},
                marks={
                    g: (markanchor.x, markanchor.y) for g in markclass.glyphs.keys()
                },
                address=location,
            languages=self.currentLanguage
            )
            s.fontfeatures = self.ff
        self.currentRoutine.addRule(s)

    add_mark_mark_pos = add_mark_base_pos

    def set_lookup_flag(self, location, value, markAttach, markFilter):
        if self.currentRoutine and value == self.currentRoutineFlag:
            return
        # If we're mid-feature, start a new routine here
        if self.currentFeature:
            self.end_lookup_block()
            self._discard_empty_routine()
            self._start_routine(location, None)
        self.currentRoutineFlag = value

    def add_language_system(self, location, script, language):
        pass

    def add_lookup_call(self, lookup_name):

        routine = self.find_named_routine(lookup_name)
        if self.currentFeature:
            self._discard_empty_routine()
            self.ff.addFeature(self.currentFeature, [routine])
        else:
            raise ValueError("Huh?")

    def end_lookup_block(self):
        if self.currentRoutine:
            for rule in self.currentRoutine.rules:
                rule.flags = self.currentRoutineFlag

    def end_feature(self):
        self._discard_empty_routine()
        self.currentFeature = None
        if self.currentRoutine:
            for rule in self.currentRoutine.rules:
                rule.flags = self.currentRoutineFlag

    def _discard_empty_routine(self):
        if not self.currentFeature:
            return
        if self.currentRoutine and not self.currentRoutine.rules:
            if self.currentRoutine not in  self.ff.routines:
                # print("%s escaped!" % self.currentRoutine.name)
                return
            del(self.ff.routines[self.ff.routines.index(self.currentRoutine)])
            if self.currentFeature in self.ff.features:
                del(self.ff.features[self.currentFeature][-1])
        pass

    def add_feature_reference(self, location, featurename):
        # XXX
        pass
