# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Contains AccessibleTime, class that represents the period of time when a course/task is accessible """
import zoneinfo
from datetime import datetime, timezone


def parse_date(date, default=None):
    """ Parse a valid date """
    if date == "":
        if default is not None:
            return default
        else:
            raise Exception("Unknown format for " + date)

    try:
        return datetime.fromisoformat(date).astimezone()
    except ValueError:
        for format_type in ["%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y %H", "%d/%m/%Y"]:
            try:
                return datetime.strptime(date, format_type).astimezone()
            except ValueError:
                pass
    raise Exception("Unknown format for " + date)


class AccessibleTime(object):
    """ represents the period of time when a course/task is accessible """

    def __init__(self, val=None):
        """
            Parse a string/a boolean to get the correct time period.
            Correct values for val:
            True (task always open)
            False (task always closed)
            2014-07-16 11:24:00 (task is open from 2014-07-16 at 11:24:00)
            2014-07-16 (task is open from 2014-07-16)
            / 2014-07-16 11:24:00 (task is only open before the 2014-07-16 at 11:24:00)
            / 2014-07-16 (task is only open before the 2014-07-16)
            2014-07-16 11:24:00 / 2014-07-20 11:24:00 (task is open from 2014-07-16 11:24:00 and will be closed the 2014-07-20 at 11:24:00)
            2014-07-16 / 2014-07-20 11:24:00 (...)
            2014-07-16 11:24:00 / 2014-07-20 (...)
            2014-07-16 / 2014-07-20 (...)
            2014-07-16 11:24:00 / 2014-07-20 11:24:00 / 2014-07-20 12:24:00 (task is open from 2014-07-16 11:24:00, has a soft deadline set at 2014-07-20 11:24:00 and will be closed the 2014-07-20 at 11:24:00)
            2014-07-16 / 2014-07-20 11:24:00 / 2014-07-21 (...)
            2014-07-16 / 2014-07-20 / 2014-07-21 (...)
        """
        self.date_min = datetime.min.replace(tzinfo=timezone.max)
        self.date_max = datetime.max.replace(tzinfo=timezone.min)

        if val is None or val == "" or val is True:
            self._val = [self.date_min, self.date_max]
            self._soft_end = self.date_max
        elif val is False:
            self._val = [self.date_max, self.date_max]
            self._soft_end = self.date_max
        else:  # str
            values = val.split("/")
            if len(values) == 1:
                self._val = [parse_date(values[0].strip(), self.date_min), self.date_max]
                self._soft_end = self.date_max
            elif len(values) == 2:
                # Has start time and hard deadline
                self._val = [parse_date(values[0].strip(), self.date_min), parse_date(values[1].strip(), self.date_max)]
                self._soft_end = self._val[1]
            else:
                # Has start time, soft deadline and hard deadline
                self._val = [parse_date(values[0].strip(), self.date_min), parse_date(values[2].strip(), self.date_max)]
                self._soft_end = parse_date(values[1].strip(), self.date_max)

        # Having a soft deadline after the hard one does not make sense, make soft-deadline same as hard-deadline
        if self._soft_end > self._val[1]:
            self._soft_end = self._val[1]

    def before_start(self, when=None):
        """ Returns True if the task/course is not yet accessible """
        if when is None:
            when = datetime.now().astimezone()

        return self._val[0] > when

    def after_start(self, when=None):
        """ Returns True if the task/course is or have been accessible in the past """
        return not self.before_start(when)

    def is_open(self, when=None):
        """ Returns True if the course/task is still open """
        if when is None:
            when = datetime.now().astimezone()

        return self._val[0] <= when <= self._val[1]

    def is_open_with_soft_deadline(self, when=None):
        """ Returns True if the course/task is still open with the soft deadline """
        if when is None:
            when = datetime.now().astimezone()

        return self._val[0] <= when <= self._soft_end

    def is_always_accessible(self):
        """ Returns true if the course/task is always accessible """
        return self._val[0] == self.date_min and self._val[1] == self.date_max

    def is_never_accessible(self):
        """ Returns true if the course/task is never accessible """
        return self._val[0] == self.date_max and self._val[1] == self.date_max

    def get_std_start_date(self):
        """ If the date is custom, return the start datetime in ISO format. Else, returns "". """
        first, _ = self._val
        if first != self.date_min and first != self.date_max:
            return first.isoformat()
        else:
            return ""

    def get_std_end_date(self):
        """ If the date is custom, return the end datetime in ISO format. Else, returns "". """
        _, second = self._val
        if second != self.date_max:
            return second.isoformat()
        else:
            return ""

    def get_std_soft_end_date(self):
        """ If the date is custom, return the soft datetime in ISO format. Else, returns "". """
        if self._soft_end != self.date_max:
            return self._soft_end.isoformat()
        else:
            return ""

    def get_start_date(self):
        """ Return a datetime object, representing the date when the task/course become accessible """
        return self._val[0]

    def get_end_date(self):
        """ Return a datetime object, representing the deadline for accessibility """
        return self._val[1]

    def get_soft_end_date(self):
        """ Return a datetime object, representing the soft deadline for accessibility """
        return self._soft_end
