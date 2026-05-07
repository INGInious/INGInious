# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.


class Tag:
    """
    This class represents a tag. A tag is a kind of badge that represents a concept.
    The 'type' represents the behaviour of the tag:
    - 0: Skill tags. It appear in blue. When the tag is activated it becomes green. We can perform tasks search on this tag.
    - 1: Misconception tags. It does not appear until it is activated. It appear in red when activated. We can NOT perform tasks search on this tag.
                        The tags are useful to highlight errors or misconceptions.
    - 2: Category tags. Never appear. Only used for organisation and when we perform tasks search.
    """

    def __init__(self, tag_id, tag_dict, gettext):
        self._id = tag_id
        self._name = tag_dict["name"]
        self._visible = tag_dict.get("visible", False)
        self._description = tag_dict.get("description", "")
        self._type = tag_dict.get("type", 0)
        self._gettext = gettext

    def __eq__(self, other):
        return self._id == other._id and self._name == other._name

    def __hash__(self):
        return hash((self._id, self._name))

    def get_name(self, language):
        """Returns the name of this tag"""
        return self._gettext(language, self._name) if self._name else ""

    def get_id(self):
        """Returns the id of this tag"""
        return self._id

    def is_visible_for_student(self):
        """Returns True is the tag should be visible to students"""
        return self._visible

    def get_description(self, language):
        """
        Returns the description of this tag
        translated=True can be use to avoid getting garbage when calling _() with an empty string since the description of a tag CAN be empty
        """
        return self._gettext(language, self._name) if self._name else ""

    def is_organisational(self):
        """Returns True if this tag is for organisational purposes"""
        return self._type == 2

    def is_misconception(self):
        """Returns True if this tag is an misconception"""
        return self._type == 1

    def get_type_as_str(self):
        """Return a textual description of the type"""
        if self.get_type() == 0:
            return _("Skill")
        elif self.get_type() == 1:
            return _("Misconception")
        elif self.get_type() == 2:
            return _("Category")
        else:
            return _("Unknown type")

    def get_type(self):
        return self._type
