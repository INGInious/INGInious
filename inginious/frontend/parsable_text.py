# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Tools to parse text """
import html
import re
import gettext
import flask
import tidylib

from datetime import datetime, timezone
from urllib.parse import urlparse
from docutils import core, nodes
from docutils.parsers.rst import directives, roles, Directive
from docutils.parsers.rst.directives.admonitions import BaseAdmonition
from docutils.parsers.rst.directives.body import CodeBlock
from docutils.statemachine import StringList
from docutils.writers import html4css1

from inginious.frontend.accessible_time import parse_date
from inginious.frontend.i18n import gettext as _


class EmptiableCodeBlock(CodeBlock):
    def run(self):
        if not self.content:
            self.content = [_("[no content]")]
        return super(EmptiableCodeBlock, self).run()


class CustomBaseAdmonition(BaseAdmonition):
    """ A custom admonition that can have a title """
    option_spec = {'class': directives.class_option,
                   'name': directives.unchanged,
                   'title': directives.unchanged}


class CustomAdmonition(CustomBaseAdmonition):
    """ A custom admonition with a specific class if needed """
    required_arguments = 1
    node_class = nodes.admonition


class HiddenUntilDirective(Directive, object):
    required_arguments = 1
    has_content = True
    optional_arguments = 1
    option_spec = {}

    def run(self):
        self.assert_has_content()

        hidden_until = " ".join(self.arguments)  #join date and optional time argument
        try:
            hidden_until = parse_date(hidden_until)
        except:
            raise self.error('Unknown date format in the "%s" directive; '
                             '%s' % (self.name, hidden_until))

        force_show = self.state.document.settings.force_show_hidden_until

        after_deadline = hidden_until <= datetime.now(timezone.utc)
        if after_deadline or force_show:
            output = []

            # Add a warning for teachers/tutors/...
            if not after_deadline and force_show:
                node = nodes.caution()
                self.add_name(node)
                text = _("The feedback below will be hidden to the students until :time:`{}`.").format(hidden_until.isoformat())
                self.state.nested_parse(StringList(text.split("\n")), 0, node)
                output.append(node)

            text = '\n'.join(self.content)
            node = nodes.compound(text)
            self.add_name(node)
            self.state.nested_parse(self.content, self.content_offset, node)
            output.append(node)

            return output
        else:
            node = nodes.caution()
            self.add_name(node)
            text = _(
                "A part of this feedback is hidden until {}. Please come back later and reload the submission to see the full feedback.").format(
                hidden_until.isoformat())
            self.state.nested_parse(StringList(text.split("\n")), 0, node)
            return [node]


class _CustomHTMLWriter(html4css1.Writer, object):
    """ A custom HTML writer that fixes some defaults of docutils... """

    def __init__(self):
        html4css1.Writer.__init__(self)
        self.translator_class = self._CustomHTMLTranslator

    class _CustomHTMLTranslator(html4css1.HTMLTranslator, object):  # pylint: disable=abstract-method
        """ A custom HTML translator """

        def visit_container(self, node):
            """ Custom version of visit_container that do not put 'container' in div class"""
            self.body.append(self.starttag(node, 'div'))

        def visit_literal(self, node):
            """ A custom version of visit_literal that uses the balise <code> instead of <tt>. """
            # special case: "code" role
            classes = node.get('classes', [])
            if 'code' in classes:
                # filter 'code' from class arguments
                node['classes'] = [cls for cls in classes if cls != 'code']
                self.body.append(self.starttag(node, 'code', ''))
                return
            self.body.append(
                self.starttag(node, 'code', '', CLASS='docutils literal'))
            text = node.astext()
            for token in self.words_and_spaces.findall(text):
                if token.strip():
                    # Protect text like "--an-option" and the regular expression
                    # ``[+]?(\d+(\.\d*)?|\.\d+)`` from bad line wrapping
                    if self.in_word_wrap_point.search(token):
                        self.body.append('<span class="pre">%s</span>'
                                         % self.encode(token))
                    else:
                        self.body.append(self.encode(token))
                elif token in ('\n', ' '):
                    # Allow breaks at whitespace:
                    self.body.append(token)
                else:
                    # Protect runs of multiple spaces; the last space can wrap:
                    self.body.append('&nbsp;' * (len(token) - 1) + ' ')
            self.body.append('</code>')
            # Content already processed:
            raise nodes.SkipNode

        def starttag(self, node, tagname, suffix='\n', empty=False, **attributes):
            """ Ensures all links to outside this instance of INGInious have target='_blank' """
            if tagname == 'a' and "href" in attributes and not attributes["href"].startswith('#'):
                attributes["target"] = "_blank"
            # Rewrite paths if we are in LTI mode
            # TODO: this should be an argument passed through all the functions
            if flask.has_app_context() and flask.request.args.get('session_id'):
                if tagname == 'a' and 'href' in attributes:
                    attributes['href'] = self.rewrite_lti_url(attributes['href'])
                elif tagname == 'img' and 'src' in attributes:
                    attributes['src'] = self.rewrite_lti_url(attributes['src'])
            return html4css1.HTMLTranslator.starttag(self, node, tagname, suffix, empty, **attributes)

        @staticmethod
        def rewrite_lti_url(url):
            if urlparse(url).netloc: # If URL is absolute, don't do anything
                return url
            return 'asset/' + url + '?session_id=' + flask.request.args['session_id']

        def visit_table(self, node):
            """ Remove needless borders """
            self.context.append(self.compact_p)
            self.compact_p = True
            classes = ['docutils', 'table', 'table-bordered', self.settings.table_style]
            if 'align' in node:
                classes.append('align-%s' % node['align'])
            self.body.append(
                self.starttag(node, 'table', CLASS=' '.join(classes)))

        def visit_tbody(self, node):
            """ Remove needless valign"""
            self.body.append(self.starttag(node, 'tbody'))

        def visit_thead(self, node):
            """ Remove needless valign, add bootstrap class """
            self.body.append(self.starttag(node, 'thead', CLASS='thead-light'))

        def visit_admonition(self, node):
            """ Support for bootstrap alert/cards """
            node['classes'].insert(0, 'admonition')
            converter = {
                'danger': 'danger',
                'attention': 'warning',
                'caution': 'warning',
                'error': 'danger',
                'hint': 'info',
                'important': 'warning',
                'note': 'default',
                'tip': 'info',
                'warning': 'warning',
                'success': 'success',
                'info': 'info',
                'primary': 'primary',
                'secondary': 'secondary',
                'light': 'light',
                'dark': 'dark'
            }
            cls = [x if not x.startswith('admonition-') else x[11:] for x in node['classes']]
            cls = [converter.get(x) for x in cls if converter.get(x) is not None]
            if len(cls) == 0:
                cls = 'info'
            else:
                cls = cls[0]

            if "title" in node and node['title'] != "":
                self.body.append(self.starttag(node, 'div', CLASS='card mb-3 border-' + cls))

                card_color = "bg-" + cls
                if cls not in ['default', 'light', 'secondary']:
                    card_color += ' text-white'

                self.body.append(self.starttag(node, 'div', CLASS='card-header ' + card_color))
                self.body.append(self.encode(node['title']))
                self.body.append('</div>\n')
                self.body.append(self.starttag(node, 'div', CLASS='card-body'))
            else:
                if cls == "default":
                    cls = 'light'
                self.body.append(self.starttag(node, 'div', CLASS='alert alert-' + cls))
            self.set_first_last(node)

            # drop unneeded title
            node.children = node.children[1:]

        def depart_admonition(self, node):
            if "title" in node and node['title'] != "":
                self.body.append('</div>\n')
            self.body.append('</div>\n')

        def visit_time(self, node):
            self.body.append(self.starttag(node, 'time', datetime=node.children[0]))

        def depart_time(self, node):
            self.body.append('</time>')

class ParsableText(object):
    """Allow to parse a string with different parsers"""

    def __init__(self, content, mode="rst", show_everything=False):
        """
            content             The string to be parsed.
            mode                The parser to be used. Currently, only rst(reStructuredText) and HTML are supported.
            show_everything     Shows things that are normally hidden, such as the hidden-util directive.
        """
        mode = mode.lower()
        if mode not in ["rst", "html"]:
            raise Exception("Unknown text parser: " + mode)
        self._content = content
        self._parsed = None
        self._mode = mode
        self._show_everything = show_everything

    def original_content(self):
        """ Returns the original content """
        return self._content

    def parse(self, debug=False):
        """Returns parsed text"""
        if self._parsed is None:
            try:
                if self._mode == "html":
                    self._parsed = self.html(self._content, self._show_everything)
                else:
                    self._parsed = self.rst(self._content, self._show_everything, debug=debug)
            except Exception as e:
                if debug:
                    raise BaseException("Parsing failed") from e
                else:
                    self._parsed = _("<b>Parsing failed</b>: <pre>{}</pre>").format(html.escape(self._content))
        return self._parsed

    def __str__(self):
        """Returns parsed text"""
        return self.parse()

    def __unicode__(self):
        """Returns parsed text"""
        return self.parse()

    @classmethod
    def html(cls, string, show_everything=False):  # pylint: disable=unused-argument
        """Parses HTML"""
        out, _ = tidylib.tidy_fragment(string)
        return out

    @classmethod
    def rst(cls, string, show_everything=False, initial_header_level=3, debug=False):
        """Parses reStructuredText"""
        overrides = {
            'initial_header_level': initial_header_level,
            'doctitle_xform': False,
            'syntax_highlight': 'none',
            'force_show_hidden_until': show_everything,
            'raw_enabled': True,
            'file_insertion_enabled': False,
            'math_output': 'MathJax /this/does/not/need/to/exist.js',
            'line_length_limit': len(string)  # Use string size to be safe.
        }
        if debug:
            overrides['halt_level'] = 2
            overrides['traceback'] = True
        parts = core.publish_parts(source=string, writer=_CustomHTMLWriter(),
                                   settings_overrides=overrides)
        return parts['body_pre_docinfo'] + parts['fragment']


# override base directives
def _gen_admonition_cls(cls):
    class GenAdm(CustomBaseAdmonition):
        node_class = cls
    return GenAdm


class time(nodes.Inline, nodes.TextElement):
    pass


def time_role(name, rawtext, text, lineno, inliner, options={}, content=[]):
    node = time(rawtext, text, **options)
    return [node], []


directives.register_directive("admonition", CustomAdmonition)
directives.register_directive("attention", _gen_admonition_cls(nodes.attention))
directives.register_directive("caution", _gen_admonition_cls(nodes.caution))
directives.register_directive("danger", _gen_admonition_cls(nodes.danger))
directives.register_directive("error", _gen_admonition_cls(nodes.error))
directives.register_directive("hint", _gen_admonition_cls(nodes.hint))
directives.register_directive("important", _gen_admonition_cls(nodes.important))
directives.register_directive("note", _gen_admonition_cls(nodes.note))
directives.register_directive("tip", _gen_admonition_cls(nodes.tip))
directives.register_directive("warning", _gen_admonition_cls(nodes.warning))
directives.register_directive("hidden-until", HiddenUntilDirective)
directives.register_directive("code-block", EmptiableCodeBlock)
roles.register_local_role("time", time_role)
