#!/usr/bin/env python
import pylatex as pl


class ThreePartTable(pl.base_classes.Environment):
    """ThreePartTable implementation"""

    packages = [pl.Package('threeparttablex', options=['referable'])]
    _latex_name = 'ThreePartTable'


class TableNotes(pl.lists.List):
    """TableNotes implementation"""

    packages = [pl.Package('threeparttablex', options=['referable'])]
    _latex_name = 'TableNotes'

    def __init__(self, *args, prefix=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._prefix = prefix

    def add_item(self, s, l):
        self.append(TableNoteItem(s, l, prefix=self._prefix))


class Footnotesize(pl.base_classes.CommandBase):
    pass


class TableNoteItem(pl.base_classes.ContainerCommand):
    content_separator = ' '

    def __init__(self, s, l, prefix=None, data=None):
        super().__init__(data)
        if prefix is None:
            self._prefix = ''
        else:
            self._prefix = f'{prefix}:'

        self.append(pl.Command('item', options=s))
        self.append(pl.Label('{prefix}{s}'.format(
            prefix=self._prefix,
            s=s,
        )))
        self.append(l)

    def dumps(self):
        content = self.dumps_content()

        if not content.strip() and self.omit_if_empty:
            return ''
        else:
            return content


class Span(pl.base_classes.ContainerCommand):
    content_separator = ' '

    def __init__(self, data=None):
        super().__init__(data)

    def dumps(self):
        content = self.dumps_content()

        if not content.strip() and self.omit_if_empty:
            return ''
        else:
            return content


class myLongTable(pl.LongTable):
    _latex_name = 'longtable'

    def dumps_content(self, **kwargs):
        content = ''

        content += super(
            pl.base_classes.Environment,
            self
        ).dumps_content(**kwargs)

        return pl.NoEscape(content)
