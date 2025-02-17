"""
Class Definitions
=================

To define a named glyph class in the FEE language, use the ``DefineClass``
verb. This takes three arguments: the first is a class name, which must start
with the ``@`` character; the second is the symbol ``=``; the third is a glyph
selector as described above::

    DefineClass @upper_alts = @upper.alt;
    DefineClass @lower = /^[a-z]$/;
    DefineClass @upper_and_lower = [A B C D E F G @lower];

In addition, glyph classes can be *combined* within the ``DefineClass``
statement using intersection (``|``) and union (``&``) operators::

    DefineClass @all_marks = @lower_marks | @upper_marks;
    DefineClass @uppercase_vowels = @uppercase & @vowels;

As well as subtracted (``-``):

    DefineClass @ABCD = A | B | C | D;
    DefineClass @ABC = @ABCD - D;

Glyph classes can also be defined using the Unicode codepoints that the glyphs
map to in the font. For example:

    DefineClass @Q = U+51;

In the PostScript standard, the ASCII digits don't have regex friendly names,
so you may wish to select them with a Unicode range selector:

    DefineClass @digits = U+30=>U+39;

Finally, glyph classes can be filtered through the use of one or more
*predicates*, which take the form ``and`` followed by a bracketed relationship,
and which tests the properties of the glyphs against the expression given::

    DefineClass @short_behs = /^BE/ and (width < 200);

- The first part of the relationship is a metric, which can be one of

  - ``width`` (advance width)
  - ``lsb`` (left side bearing)
  - ``rsb`` (right side bearing)
  - ``xMin`` (minimum X coordinate)
  - ``xMax`` (maximum X coordinate)
  - ``yMin`` (minimum Y coordinate)
  - ``yMax`` (maximum Y coordinate)
  - ``rise`` (difference in Y coordinate between cursive entry and exit)
  - ``fullwidth`` (``xMax``-``xMin``)

- The second part is a comparison operator (``>=``, ``<=``, ``=``, ``<``, or
  ``>``).

- The third is either an integer or a metric name and the name of a single
  glyph in brackets.

This last form is best understood by example. The following definition selects
all members of the glyph class ``@alpha`` whose advance width is less than the
advance width of the ``space`` glyph::

    DefineClass @shorter_than_space = @alpha and (width < width(space));

- As well as testing for glyph metrics, the following other relationships
  are defined:

  - ``hasglyph(regex string)`` (true if glyph after replacement of regex by
    string exists in the font)
  - ``hasanchor(anchorname)`` (true if the glyph has the named anchor)
  - ``category(base)`` (true if the glyph has the given category)

Binned Definitions
------------------

Sometimes it is useful to split up a large glyph class into a number of
smaller classes according to some metric, in order to treat them
differently. For example, when performing an i-matra substitution in
Devanagari, you would generally want to split your base glyphs by width,
and apply the appropriate matra for each set of glyphs. FEE calls the
operation of organising glyphs into groups of similar metrics "binning".

The ``ClassDefinition`` plugin also provides the ``DefineClassBinned`` verb,
which generated a set of related glyph classes. The arguments of ``DefineClassBinned``
are identical to that of ``DefineClass``, except that after the class name
you must specify an open square bracket, the metric to be used to bin the
glyphs, a comma, the number of bins to create, and a close bracket, like so::

    DefineClassBinned @bases[width,5] = @bases;

This will create five classes, called ``@bases_width1`` .. ``@bases_width5``,
grouped in increasing order of advance width. Note that the size of the bins is
not guaranteed to be equal, but glyphs are clustered according to the similarity
of their metric. For example, if the advance widths are 99, 100, 110, 120,
500, and 510 and two bins are created, four glyphs will be in one bin and two
will be in the second.

(This is just an example for the purpose of explaining binning. We'll show a
better way to handle the i-matra question later.)

Glyph Class Debugging
---------------------

The combination of the above rules allows for extreme flexibility in creating
glyph classes, to the extent that it may become difficult to understand the
final composition of glyph classes! To alleviate this, the verb ``ShowClass``
will take any glyph selector and display its contents on standard error.

"""

import lark
import re
from glyphtools import get_glyph_metrics, bin_glyphs_by_metric

import warnings

from . import FEEVerb
from . import TESTVALUE_METRICS
from .util import compare
from fontFeatures.feeLib import GlyphSelector

GRAMMAR = """
has_glyph_predicate: "hasglyph(" REGEX MIDGLYPHNAME* ")"
has_anchor_predicate: "hasanchor(" BARENAME ")"
category_predicate: "category(" BARENAME ")"
predicate: has_glyph_predicate | has_anchor_predicate | category_predicate | metric_comparison
negated_predicate: "not" predicate

CONJUNCTOR: "&" | "|" | "-"
primary_action: glyphselector | conjunction | predicate | negated_predicate
primary: primary_action | ("(" primary_action ")")
conjunction: primary CONJUNCTOR primary

"""

DefineClass_GRAMMAR = """
?start: action
action: CLASSNAME "=" primary
"""

DefineClassBinned_GRAMMAR = """
?start: action
action: CLASSNAME "[" METRIC "," NUMBER "]" "=" primary
"""

PARSEOPTS = dict(use_helpers=True)
VERBS = ["DefineClass", "DefineClassBinned"]

class DefineClass(FEEVerb):
    def _add_glyphs_to_named_class(self, glyphs, classname):
        self.parser.fontfeatures.namedClasses[classname] = glyphs

    def has_glyph_predicate(self, args):
        glyphre, withs = args
        value = {"replace": re.compile(glyphre.value[1:-1]), "with": withs.value}
        return {"predicate": "hasglyph", "value": value, "inverted": False}

    def has_anchor_predicate(self, args):
        (barename,) = args
        return {"predicate": "hasanchor", "value": barename.value, "inverted": False}

    def category_predicate(self, args):
        (barename,) = args
        return {"predicate": "category", "value": barename.value, "inverted": False}

    def _get_metrics(self, glyph, metric=None):
        metrics = get_glyph_metrics(self.parser.font, glyph)
        if metric is not None:
            if metric not in TESTVALUE_METRICS:
                raise ValueError("Unknown metric '%s'" % metric)
            else:
                return metrics[metric]
        else:
            return metrics

    def metric_comparison(self, args):
        (metric, comparator, comp_value) = args
        metric = metric.value
        comparator = comparator.value
        return lambda metrics, glyphname: compare(metrics[metric], comparator, comp_value)

    def predicate(self, args):
        (predicate,) = args

        if callable(predicate): # if it's a comparison
            return predicate
        else:
            return lambda _, glyphname: self.meets_predicate(glyphname, predicate, self.parser)

    def negated_predicate(self, args):
        (predicate,) = args
        return lambda metrics, glyphname: not predicate(metrics, glyphname)

    def primary_action(self, args):
        return args[0]

    def primary(self, args):
        (primary,) = args
        if isinstance(primary, GlyphSelector) or (isinstance(primary, dict) and "conjunction" in primary):
            glyphs = self.resolve_definition(self.parser, primary)
            return glyphs
        else: # we're holding a predicate, apply it to all glyphs
            glyphs = self._predicate_for_all_glyphs(primary)
            return glyphs

    def _predicate_for_all_glyphs(self, predicate):
        all_glyphs = list(self.parser.font.glyphOrder)
        return [g for g in all_glyphs if predicate(self._get_metrics(g), g)]

    def conjunction(self, args):
        l, conjunctor, r = args

        if isinstance(l, list) and callable(r):
            return [g for g in l if r(self._get_metrics(g), g)]

        return {"conjunction": {"&":"and","|":"or","-":"subtract"}[conjunctor], "left": l, "right": r}

    def action(self, args):
        parser = self.parser
        classname, glyphs = args
        classname = classname[1:] # -@

        self._add_glyphs_to_named_class(glyphs, classname)

        return args[0]

    @classmethod
    def resolve_definition(self, parser, primary):
        if isinstance(primary, dict) and "conjunction" in primary:
            left = set(primary["left"])
            right = set(primary["right"])
            if primary["conjunction"] == "or":
                return list(left | right)
            elif primary["conjunction"] == "and":
                return list(left & right)
            else: #subtract
                return set(left) - set(right)
        else:
            return primary.resolve(parser.fontfeatures, parser.font)

    @classmethod
    def meets_predicate(self, glyphname, predicate, parser):
        metric = predicate["predicate"]
        if metric == "hasanchor":
            anchor = predicate["value"]
            truth = glyphname in parser.fontfeatures.anchors and anchor in parser.fontfeatures.anchors[glyphname]
        elif metric == "category":
            cat = predicate["value"]
            truth = parser.font[glyphname].category == cat
        elif metric == "hasglyph":
            truth = re.sub(predicate["value"]["replace"], predicate["value"]["with"], glyphname) in parser.font
        else:
            raise ValueError("Unknown metric {}".format(metric))
        return truth

class DefineClassBinned(DefineClass):
    def action(self, args):
        # glyphs is already resolved, because this class has functions of DefineClass, which resolves `primary`
        classname, (metric, bincount), glyphs = args[0], (args[1].value, args[2].value), args[3]
        binned = bin_glyphs_by_metric(self.parser.font, glyphs, metric, bincount=int(bincount))
        for i in range(1, int(bincount) + 1):
            self.parser.fontfeatures.namedClasses["%s_%s%i" % (classname, metric, i)] = tuple(binned[i - 1][0])

        return classname, (metric, bincount), glyphs

"""
class DefineClassBinned(DefineClass):
    @classmethod
    def action(self, parser, metric, bincount, classname, definition):
        glyphs = self.resolve_definition(parser, definition[0])
        predicates = definition[1]
        for p in predicates:
            glyphs = list(filter(lambda x: self.meets_predicate(x, p, parser), glyphs))

        binned = bin_glyphs_by_metric(parser.font, glyphs, metric, bincount=int(bincount))
        for i in range(1, int(bincount) + 1):
            parser.fontfeatures.namedClasses["%s_%s%i" % (classname["classname"], metric, i)] = tuple(binned[i - 1][0])
"""
