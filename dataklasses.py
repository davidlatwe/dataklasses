# dataklasses.py
# 
#     https://github.com/dabeaz/dataklasses
#
# Author: David Beazley (@dabeaz). 
#         http://www.dabeaz.com
#
# Copyright (C) 2021-2022.
#
# Permission is granted to use, copy, and modify this code in any
# manner as long as this copyright message and disclaimer remain in
# the source code.  There is no warranty.  Try to use the code for the
# greater good.

__all__ = ['dataklass']

import sys
from functools import lru_cache, reduce


def codegen(func):
    @lru_cache()
    def make_func_code(numfields):
        names = [f'_{n}' for n in range(numfields)]
        d = dict()
        exec(func(names), globals(), d)
        return d.popitem()[1]

    return make_func_code


# Following code object replace backport implementation is referenced
# from https://github.com/HypothesisWorks/hypothesis/pull/1944
# specifically, commit: 8f47297fa2e19c426a42b06bb5f8bf1406b8f0f3
_CODE_FIELD_ORDER = [
    "co_argcount",
    "co_kwonlyargcount",
    "co_nlocals",
    "co_stacksize",
    "co_flags",
    "co_code",
    "co_consts",
    "co_names",
    "co_varnames",
    "co_filename",
    "co_name",
    "co_firstlineno",
    "co_lnotab",
    "co_freevars",
    "co_cellvars",
]
if sys.version_info >= (3, 8, 0):
    # PEP 570 added "positional only arguments"
    _CODE_FIELD_ORDER.insert(1, "co_posonlyargcount")


def code_replace(code, **kwargs):
    """Python 3.8 CodeType.replace backport

    Related links:
    https://docs.python.org/3/library/types.html#types.CodeType.replace
    https://docs.python.org/3/whatsnew/3.8.html#other-language-changes
    https://bugs.python.org/issue37032

    Implementation reference:
    https://github.com/pganssle/hypothesis/blob/ffcec4f/hypothesis-python/src/hypothesis/internal/compat.py#L400-L413

    """
    unpacked = [getattr(code, name) for name in _CODE_FIELD_ORDER]
    for k, v in kwargs.items():
        unpacked[_CODE_FIELD_ORDER.index(k)] = v
    return type(code)(*unpacked)


def patch_args_and_attributes(func, fields, start=0):
    return type(func)(
        code_replace(
            func.__code__,
            co_names=(*func.__code__.co_names[:start], *fields),
            co_varnames=('self', *fields),
        ),
        func.__globals__
    )


def patch_attributes(func, fields, start=0):
    return type(func)(
        code_replace(
            func.__code__,
            co_names=(*func.__code__.co_names[:start], *fields)
        ),
        func.__globals__
    )


def all_hints(cls):
    return reduce(lambda x, y: {**getattr(y, '__annotations__', {}), **x}, cls.__mro__, {})


@codegen
def make__init__(fields):
    code = 'def __init__(self, ' + ','.join(fields) + '):\n'
    return code + '\n'.join(f' self.{name} = {name}\n' for name in fields)


@codegen
def make__repr__(fields):
    return 'def __repr__(self):\n' \
           ' return f"{type(self).__name__}(' + \
           ', '.join('{self.' + name + '!r}' for name in fields) + ')"\n'


@codegen
def make__eq__(fields):
    selfvals = ','.join(f'self.{name}' for name in fields)
    othervals = ','.join(f'other.{name}' for name in fields)
    return f"""def __eq__(self, other):
    if self.__class__ is other.__class__:
        return ({selfvals},) == ({othervals},)
    else:
        return NotImplemented
    """


@codegen
def make__iter__(fields):
    return 'def __iter__(self):\n' + '\n'.join(f'   yield self.{name}' for name in fields)


@codegen
def make__hash__(fields):
    self_tuple = '(' + ','.join(f'self.{name}' for name in fields) + ',)'
    return 'def __hash__(self):\n' \
           f'    return hash({self_tuple})\n'


def dataklass(cls):
    """A different spin on dataclasses.

    Example:
        >>> @dataklass
        ... class Coordinates:
        ...     x: int
        ...     y: int
        >>>
        >>> a = Coordinates(2, 3)
        >>> b = Coordinates(2, 3)
        >>> assert a == b

    :param cls:
    :return:
    """
    fields = all_hints(cls)
    nfields = len(fields)
    clsdict = vars(cls)
    if not '__init__' in clsdict: cls.__init__ = patch_args_and_attributes(make__init__(nfields), fields)
    if not '__repr__' in clsdict: cls.__repr__ = patch_attributes(make__repr__(nfields), fields, 2)
    if not '__eq__' in clsdict: cls.__eq__ = patch_attributes(make__eq__(nfields), fields, 1)
    # if not '__iter__' in clsdict:  cls.__iter__ = patch_attributes(make__iter__(nfields), fields)
    # if not '__hash__' in clsdict:  cls.__hash__ = patch_attributes(make__hash__(nfields), fields, 1)
    cls.__match_args__ = tuple(fields)
    return cls


if __name__ == '__main__':
    import doctest
    doctest.testmod(optionflags=doctest.FAIL_FAST)
