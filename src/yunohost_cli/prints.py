#!/usr/bin/env python3

from json.encoder import JSONEncoder
from collections import OrderedDict
from datetime import date, datetime
import os

CLI_COLOR_TEMPLATE = "\033[{:d}m\033[1m"
END_CLI_COLOR = "\033[m"

colors_codes = {
    "red": CLI_COLOR_TEMPLATE.format(31),
    "green": CLI_COLOR_TEMPLATE.format(32),
    "yellow": CLI_COLOR_TEMPLATE.format(33),
    "blue": CLI_COLOR_TEMPLATE.format(34),
    "purple": CLI_COLOR_TEMPLATE.format(35),
    "cyan": CLI_COLOR_TEMPLATE.format(36),
    "white": CLI_COLOR_TEMPLATE.format(37),
}


def colorize(astr, color):
    """Colorize a string

    Return a colorized string for printing in shell with style ;)

    Keyword arguments:
        - astr -- String to colorize
        - color -- Name of the color

    """
    if os.isatty(1):
        return "{:s}{:s}{:s}".format(colors_codes[color], astr, END_CLI_COLOR)
    else:
        return astr


def plain_print_dict(d, depth=0):
    """Print in a plain way a dictionary recursively

    Print a dictionary recursively for scripting usage to the standard output.

    Output formatting:
      >>> d = {'key': 'value', 'list': [1,2], 'dict': {'key2': 'value2'}}
      >>> plain_print_dict(d)
      #key
      value
      #list
      1
      2
      #dict
      ##key2
      value2

    Keyword arguments:
        - d -- The dictionary to print
        - depth -- The recursive depth of the dictionary

    """
    # skip first key printing
    if depth == 0 and (isinstance(d, dict) and len(d) == 1):
        _, d = d.popitem()
    if isinstance(d, (tuple, set)):
        d = list(d)
    if isinstance(d, list):
        for v in d:
            plain_print_dict(v, depth + 1)
    elif isinstance(d, dict):
        for k, v in d.items():
            print("{}{}".format("#" * (depth + 1), k))
            plain_print_dict(v, depth + 1)
    else:
        print(d)


def pretty_date(_date):
    """Display a date in the current time zone without ms and tzinfo

    Argument:
        - date -- The date or datetime to display
    """
    import pytz  # Lazy loading, this takes like 3+ sec on a RPi2 ?!

    # Deduce system timezone
    nowutc = datetime.now(tz=pytz.utc)
    nowtz = datetime.now()
    nowtz = nowtz.replace(tzinfo=pytz.utc)
    offsetHour = nowutc - nowtz
    offsetHour = int(round(offsetHour.total_seconds() / 3600))
    localtz = "Etc/GMT%+d" % offsetHour

    # Transform naive date into UTC date
    if _date.tzinfo is None:
        _date = _date.replace(tzinfo=pytz.utc)

    # Convert UTC date into system locale date
    _date = _date.astimezone(pytz.timezone(localtz))
    if isinstance(_date, datetime):
        return _date.strftime("%Y-%m-%d %H:%M:%S")
    else:
        return _date.strftime("%Y-%m-%d")


def pretty_print_dict(d, depth=0):
    """Print in a pretty way a dictionary recursively

    Print a dictionary recursively with colors to the standard output.

    Keyword arguments:
        - d -- The dictionary to print
        - depth -- The recursive depth of the dictionary

    """
    keys = d.keys()
    if not isinstance(d, OrderedDict):
        keys = sorted(keys)
    for k in keys:
        v = d[k]
        k = colorize(str(k), "purple")
        if isinstance(v, (tuple, set)):
            v = list(v)
        if isinstance(v, list) and len(v) == 1:
            v = v[0]
        if isinstance(v, dict):
            print("{:s}{}: ".format("  " * depth, k))
            pretty_print_dict(v, depth + 1)
        elif isinstance(v, list):
            print("{:s}{}: ".format("  " * depth, k))
            for key, value in enumerate(v):
                if isinstance(value, tuple):
                    pretty_print_dict({value[0]: value[1]}, depth + 1)
                elif isinstance(value, dict):
                    pretty_print_dict({key: value}, depth + 1)
                else:
                    if isinstance(v, date):
                        v = pretty_date(v)
                    print("{:s}- {}".format("  " * (depth + 1), value))
        else:
            if isinstance(v, date):
                v = pretty_date(v)
            print("{:s}{}: {}".format("  " * depth, k, v))




class JSONExtendedEncoder(JSONEncoder):
    """Extended JSON encoder

    Extend default JSON encoder to recognize more types and classes. It will
    never raise an exception if the object can't be encoded and return its repr
    instead.

    The following objects and types are supported:
        - set: converted into list

    """

    def default(self, o):
        import pytz  # Lazy loading, this takes like 3+ sec on a RPi2 ?!

        """Return a serializable object"""
        # Convert compatible containers into list
        if isinstance(o, set) or (hasattr(o, "__iter__") and hasattr(o, "next")):
            return list(o)

        # Display the date in its iso format ISO-8601 Internet Profile (RFC 3339)
        if isinstance(o, datetime.date):
            if o.tzinfo is None:
                o = o.replace(tzinfo=pytz.utc)
            return o.isoformat()

        # Return the repr for object that json can't encode
        logger.warning(
            "cannot properly encode in JSON the object %s, " "returned repr is: %r",
            type(o),
            o,
        )
        return repr(o)
