# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

from inginious.frontend.parsable_text import ParsableText


class TestParsableText(object):
    def test_code(self):
        rendered = ParsableText.rst("""``test``""")
        assert "<code" in rendered and "</code>" in rendered

    def test_str(self):
        rendered = str(ParsableText.rst("""``test``"""))
        assert "<code" in rendered and "</code>" in rendered

    def test_unicode(self):
        rendered = str(ParsableText.rst("""``😁``"""))
        assert "<code" in rendered and "</code>" in rendered and "😁" in rendered

    def test_html_tidy(self):
        rendered = ParsableText.html("<non existing tag></...>")
        assert "<non existing tag>" not in rendered

    def test_parsable_text_once(self):
        def fake_parser(
            string,
            show_everything=False,
            translation=None,
            initial_header_level=3,
            debug=False,
        ):
            fake_parser.count += 1
            return ""

        fake_parser.count = 0
        orig_rst = ParsableText.rst
        ParsableText.rst = fake_parser

        pt = ParsableText("""``test``""", "rst")
        pt.rst = fake_parser

        pt.parse()
        str(pt)
        str(pt)

        ParsableText.rst = orig_rst

        assert fake_parser.count == 1

    def test_wrong_rst_injection(self):
        rendered = str(
            ParsableText.rst(
                """
            makefail_
            <script type="text/javascript">alert('Eh, XSS injection!');</script>
            """
            )
        )
        assert "&lt;script type=&quot;text/javascript&quot;&gt;" in rendered

    def test_failing_parser_injection(self):
        def fake_parser(input):
            raise Exception()

        fake_parser.count = 0
        orig_rst = ParsableText.rst
        ParsableText.rst = fake_parser

        pt = ParsableText(
            """<script type="text/javascript">alert('Eh, XSS injection!');</script>"""
        )
        rendered = pt.parse()

        ParsableText.rst = orig_rst

        assert "&lt;script " in rendered

    def test_hidden_until_after(self):
        assert "Something" in ParsableText.rst("""
        .. hidden-until:: 22/05/2002

            Something
        """)

    def test_hidden_until_before(self):
        assert "Something" not in ParsableText.rst("""
        .. hidden-until:: 22/05/2102

            Something
        """)

    def test_hidden_until_before_admin(self):
        assert "Something" in ParsableText.rst(
            """
            .. hidden-until:: 22/05/2102

                Something
            """,
            show_everything=True,
        )
