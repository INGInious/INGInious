# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Contains AccessibleTime, class that represents the period of time when a course/task is accessible """

from datetime import datetime


def parse_date(date, default=None):
    """
        Parse a valid date
        :param date: string, date to parse
        :param default: datetime object, optionnal, default value to return if date is empty
        :return: datetime object of the parsed date
    """
    if date == "":
        if default is not None:
            return default
        else:
            raise Exception("Empty date given to AccessibleTime")

    if date == "0001-01-01 00:00:00":
        return datetime.min
    if date == "9999-12-31 23:59:59":
        return datetime.max.replace(microsecond=0)

    for format_type in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d %H", "%Y-%m-%d", "%d/%m/%Y %H:%M:%S",
                        "%d/%m/%Y %H:%M", "%d/%m/%Y %H", "%d/%m/%Y"]:
        try:
            return datetime.strptime(date, format_type)
        except ValueError:
            pass
    raise Exception("Unknown format for " + date)


class AccessibleTime(object):
    """ represents the period of time when a course/task is accessible """

    def __init__(self, period):
        """
            Used to represent the period of time when a course/task is accessible.
            :param period : dict, contains start, end and optionally soft_end as datetime objects or strings
                            (for frontend use through templates).
                            Can be a boolean, None or string if using the legacy format "start/soft_end/end"
        """

        self.max = datetime.max.replace(microsecond=0)
        self.min = datetime.min

        if not isinstance(period, (dict, str, bool, type(None))):  # add None check
            raise Exception("Wrong period given to AccessibleTime")

        # if legacy format (start/soft_end/end string, empty string, bool)
        if isinstance(period, str):
            period = self.legacy_string_structure_to_dict(period)
        if isinstance(period, (bool, type(None))):
            if period is (True or None):
                period = {"start": self.min, "soft_end": self.max, "end": self.max}
            else:
                period = {"start": self.max, "soft_end": self.max, "end": self.max}

        # transforming strings into datetimes in case AccessibleTime is used in html files, where datetime objects are not supported
        for key, date in period.items():
            if not isinstance(date, (datetime, str)):
                raise Exception("Wrong period given to AccessibleTime")
            if isinstance(date, str):
                period[key] = parse_date(date)

        self._start = period["start"]
        self._end = period["end"]
        if "soft_end" in period:
            if period["soft_end"] == self.max:
                self._soft_end = self.max
            else:
                soft_end = min(period["soft_end"], period["end"])
                self._soft_end = soft_end

    def legacy_string_structure_to_dict(self, legacy_date):
        """
            Convert the legacy string structure to a dictionary. The legacy structure follows "start/soft_end/end" for
            tasks or "start/end" for courses with some of the values being optional. Sometimes only a start date is
            given as a string (ex: "start//end", "start//", "//end", "start/end", "start", "/end", ...).
            :param legacy_date: string, legacy date structure
            :return period: dict, containing the start, soft_end and end as strings
        """
        period = {}

        values = legacy_date.split("/")
        if len(values) == 1:
            period["start"] = parse_date(values[0].strip(), self.min)
            period["soft_end"] = self.max
            period["end"] = self.max
        elif len(values) == 2:
            # Has start time and hard deadline
            period["start"] = parse_date(values[0].strip(), self.min)
            period["end"] = parse_date(values[1].strip(), self.max)
            period["soft_end"] = period["end"]
        else:
            # Has start time, soft deadline and hard deadline
            period["start"] = parse_date(values[0].strip(), self.min)
            period["soft_end"] = parse_date(values[1].strip(), self.max)
            period["end"] = parse_date(values[2].strip(), self.max)
        return period

    def before_start(self, when=None):
        """ Returns True if the task/course is not yet accessible """
        if when is None:
            when = datetime.now()

        return self._start > when

    def after_start(self, when=None):
        """ Returns True if the task/course is or have been accessible in the past """
        return not self.before_start(when)

    def is_open(self, when=None):
        """ Returns True if the course/task is still open """
        if when is None:
            when = datetime.now()

        return self._start <= when <= self._end

    def is_open_with_soft_deadline(self, when=None):
        """ Returns True if the course/task is still open with the soft deadline """
        if when is None:
            when = datetime.now()

        return self._start <= when <= self._soft_end

    def is_always_accessible(self):
        """ Returns true if the course/task is always accessible """
        return self._start == self.min and self._end == self.max

    def is_never_accessible(self):
        """ Returns true if the course/task is never accessible """
        return self._start == self.max and self._end == self.max

    def get_std_start_date(self):
        """ If the date is custom, return the start datetime with the format %4Y-%m-%d %H:%M:%S. Else, returns "". """
        if self._start not in [self.min, self.max]:
            return self._start.strftime("%4Y-%m-%d %H:%M:%S")
        return ""

    def get_std_end_date(self):
        """ If the date is custom, return the end datetime with the format %4Y-%m-%d %H:%M:%S. Else, returns "". """
        if self._end != self.max:
            return self._end.strftime("%4Y-%m-%d %H:%M:%S")
        return ""

    def get_std_soft_end_date(self):
        """ If the date is custom, return the soft datetime with the format %4Y-%m-%d %H:%M:%S. Else, returns "". """
        if self._soft_end != self.max:
            return self._soft_end.strftime("%4Y-%m-%d %H:%M:%S")
        return ""

    def get_start_date(self):
        """ Return a datetime object, representing the date when the task/course become accessible """
        return self._start

    def get_end_date(self):
        """ Return a datetime object, representing the deadline for accessibility """
        return self._end

    def get_soft_end_date(self):
        """ Return a datetime object, representing the soft deadline for accessibility """
        return self._soft_end

    def string_date(self, date):
        """ Returns the date as a string """
        return date.strftime("%4Y-%m-%d %H:%M:%S")

    def get_string_dict(self):
        """ Returns a dictionary with the start, end and soft_end as strings """
        return {
            "start": self.string_date(self._start),
            "soft_end": self.string_date(self._soft_end),
            "end": self.string_date(self._end)
        }
