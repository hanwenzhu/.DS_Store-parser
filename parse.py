# MIT License
# Copyright (c) 2019 Thomas Zhu

# TODO: Support older versions of Python by not using f-strings
# TODO: Support writing to .DS_Stores
# TODO: Documentation
# TODO: macOS alias

import datetime
import plistlib
import sys
import warnings


with open('README.md') as readme:
    __doc__ = readme.read()


# The Python types used for the different .DS_Store types:
# 'bool': bool
# 'shor': int
# 'long': int
# 'comp': int
# 'dutc': int
# 'type': str (of length 4)
# 'blob': bytes
# 'ustr': str


def show_date(timestamp):
    date = (datetime.datetime.fromtimestamp(timestamp)
            - datetime.datetime.fromtimestamp(0)
            + datetime.datetime(1904, 1, 1))
    return date.strftime('%B %-d, %Y at %-I:%M %p')


def show_bytes(data):
    if data.startswith(b'bplist') and data[6:8].isdecimal():
        return show(plistlib.loads(data))
    elif data.startswith(b'book'):
        # TODO
        return f'(in macOS alias type, unparsed) {data!r}'
    elif data.startswith(b'Bud1'):
        return show('\n'.join(DSStore(b'\x00\x00\x00\x01'
                                      + data).human_readable()))
    else:
        return f'0x{data.hex()}'


def is_inline(data):
    return not isinstance(data, (dict, tuple, list))


def show(data, tab_depth=0):
    tabs = '\t' * tab_depth
    if isinstance(data, dict):
        for key, value in data.items():
            if is_inline(value):
                yield f'{tabs}{key}: {show_one(value)}'
            else:
                yield f'{tabs}{key}:'
                yield from show(value, tab_depth=tab_depth + 1)
    elif isinstance(data, (tuple, list)):
        for value in data:
            if is_inline(value):
                yield f'{tabs}- {show_one(value)}'
            else:
                yield f'{tabs}-'
                yield from show(value, tab_depth=tab_depth + 1)
    elif isinstance(data, bytes):
        yield f'{tabs}{show_bytes(data)}'
    elif isinstance(data, (bool, int, str)):
        yield f'{tabs}{data!s}'
    else:
        yield f'{tabs}{data!r}'


def show_one(data):
    return next(show(data))


class Record:

    def __init__(self, name, *args, **kwargs):
        self.name = name
        self.fields = dict(*args, **kwargs)

    def update(self, *args, **kwargs):
        self.fields.update(*args, **kwargs)

    def __repr__(self):
        kwargs = "".join(f", {key}={value!r}"
                         for key, value in self.fields.items())
        return (f'Record({self.name!r}{kwargs})')

    def validate_type(self, field, data, data_type, *acceptable_lengths):
        if not isinstance(data, data_type):
            raise TypeError(f'{self} {field} {data!r} not of type {data_type}')
        if acceptable_lengths and len(data) not in acceptable_lengths:
            warnings.warn(f'{self} {field} {show_one(data)} not of length'
                          f' {" or ".join(acceptable_lengths)}')

    def human_readable(self):
        # TODO: interpret the parsed plists
        for field, data in self.fields.items():
            if field == 'BKGD':
                # BKGD supplanted by TODO in later versions
                self.validate_type(field, data, bytes, 12)
                background_type = data[:4].decode('ascii')
                if background_type == 'DefB':
                    yield 'Background: Default'
                elif background_type == 'ClrB':
                    hex_color = data[4:10].hex()
                    yield f'Background: Color #{hex_color}'
                elif background_type == 'PctB':
                    yield f'Background: Picture, see "Picture" field'
                else:
                    warnings.warn('Unrecognized background type'
                                  f' {background_type}')
                    yield f'Background (unrecognized): {show_one(data)}'
            elif field == 'GRP0':
                self.validate_type(field, data, str)
                yield f'{field} (unknown): {data}'
            elif field == 'ICVO':
                self.validate_type(field, data, bool)
                yield f'{field} (unknown): {data}'
            elif field == 'Iloc':
                self.validate_type(field, data, bytes, 16)
                x = int.from_bytes(data[0:4], 'big', signed=False)
                y = int.from_bytes(data[4:8], 'big', signed=False)
                # Don't know what data[8:16] is for, but it's variable
                rest = data[8:16]
                yield f'Icon location: x {x}px, y {y}px, {show_one(rest)}'
            elif field == 'LSVO':
                self.validate_type(field, data, bool)
                yield f'{field} (unknown): {data}'
            elif field == 'bwsp':
                self.validate_type(field, data, bytes)
                yield 'Layout property list:'
                yield from show(plistlib.loads(data), tab_depth=1)
            elif field == 'cmmt':
                self.validate_type(field, data, str)
                yield f'Comments: {data}'
            elif field == 'dilc':
                self.validate_type(field, data, bytes, 32)
                x = int.from_bytes(data[16:20], 'big', signed=False)
                y = int.from_bytes(data[20:24], 'big', signed=False)
                # They appear to be percentages with 0.001 accuracy
                x /= 1000
                y /= 1000
                # Don't know what data[0:16] and data[24:32] are for
                before = data[0:16]
                after = data[24:32]
                yield (f'Icon location on desktop: x {x}%, y {y}%'
                       f', {show_one(before)}, {show_one(after)}')
            elif field == 'dscl':
                self.validate_type(field, data, bool)
                yield f'Open in list view: {data}'
            elif field == 'extn':
                self.validate_type(field, data, str)
                yield f'Extension: {data}'
            elif field == 'fwi0':
                # fwi0 somewhat supplanted by vstl, bwsp, lsvp, lsvP later
                self.validate_type(field, data, bytes, 16)
                yield 'Finder window information:'
                top = int.from_bytes(data[0:2], 'big', signed=False)
                left = int.from_bytes(data[2:4], 'big', signed=False)
                bottom = int.from_bytes(data[4:6], 'big', signed=False)
                right = int.from_bytes(data[6:8], 'big', signed=False)
                yield (f'\tWindow rectangle: top {top}, left {left}, bottom'
                       f' {bottom}, right {right}')
                # Coverflow view not in Mojave now
                # Similarly there's no Gallery view back then
                views = {'icnv': 'Icon view',
                         'clmv': 'Column view',
                         'Nlsv': 'List view',
                         'Flwv': 'Coverflow view'}
                view_raw = data[8:12].decode('ascii')
                view = views.get(view_raw, f'(unrecognized) {view_raw}')
                yield f'View style (might be overtaken): {view}'
                # Don't know what data[12:16] is for
                yield f'{show_one(data[12:16])}'
            elif field == 'fwsw':
                self.validate_type(field, data, int)
                yield f'Finder window sidebar width: {data}'
            elif field == 'fwvh':
                self.validate_type(field, data, int)
                yield ('Finder window vertical height (overrides Finder window'
                       f' information): {data}')
            elif field == 'icgo':
                self.validate_type(field, data, bytes, 8)
                yield f'{field} (unknown): {show_one(data)}'
            elif field == 'icsp':
                self.validate_type(field, data, bytes, 8)
                yield f'{field} (unknown): {show_one(data)}'
            elif field == 'icvo':
                # icvo supplanted by icvp in later versions
                self.validate_type(field, data, bytes)
                yield 'Icon view options:'
                icvo_type = data[0:4].decode('ascii')
                arranges = {'none': 'None', 'grid': 'Snap to Grid'}
                labels = {'botm': 'Bottom', 'rght': 'Right'}
                if icvo_type == 'icvo':
                    self.validate_type(field, data, bytes, 18)
                    flags = data[4:12]
                    size = int.from_bytes(data[12:14], 'big', signed=False)
                    arrange_raw = data[14:18].decode('ascii')
                    arrange = arranges.get(arrange_raw,
                                           f'(unknown) {arrange_raw}')
                    yield f'\tFlags (?): {show_one(flags)}'
                    yield f'\tSize: {size}px'
                    yield f'\tKeep arranged by: {arrange}'
                elif icvo_type == 'icv4':
                    self.validate_type(field, data, bytes, 26)
                    size = int.from_bytes(data[4:6], 'big', signed=False)
                    arrange_raw = data[6:10].decode('ascii')
                    arrange = arranges.get(arrange_raw,
                                           f'(unknown) {arrange_raw}')
                    label_raw = data[10:14].decode('ascii')
                    label = labels.get(label_raw, f'(unknown) {label_raw}')
                    flags = data[14:26]
                    info = bool(flags[1] & 0x01)
                    preview = bool(flags[11] & 0x01)
                    yield f'\tSize: {size}px'
                    yield f'\tKeep arranged by: {arrange}'
                    yield f'\tLabel position: {label}'
                    yield '\tFlags (partially known):'
                    yield f'\t\tRaw flags: {show_one(flags)}'
                    yield f'\t\tShow item info: {info}'
                    yield f'\t\tShow icon preview: {preview}'
                else:
                    warnings.warn('Unrecognized icon view options type'
                                  f' {icvo_type}')
                    yield f'\t(unrecognized): {show_one(data)}'
            elif field == 'icvp':
                self.validate_type(field, data, bytes)
                yield 'Icon view property list:'
                yield from show(plistlib.loads(data), tab_depth=1)
            elif field == 'info':
                self.validate_type(field, data, bytes)
                yield f'{field} (unknown): {show_one(data)}'
            elif field in {'logS', 'lg1S'}:
                # logS supplanted by lg1S for unknown reasons
                self.validate_type(field, data, int)
                yield f'Logical size: {data}B'
            elif field == 'lssp':
                self.validate_type(field, data, bytes, 8)
                yield (f'{field} (unknown, List view scroll position?):'
                       f' {show_one(data)}')
            elif field == 'lsvC':
                self.validate_type(field, data, bytes)
                yield 'List view properties, alternative:'
                yield from show(plistlib.loads(data), tab_depth=1)
            elif field == 'lsvP':
                self.validate_type(field, data, bytes)
                yield 'List view properties, other alternative:'
                yield from show(plistlib.loads(data), tab_depth=1)
            elif field == 'lsvo':
                # lsvo supplanted by lsvp / lsvP
                self.validate_type(field, data, bytes, 76)
                yield f'List view options (format unknown): {show_one(data)}'
            elif field == 'lsvp':
                self.validate_type(field, data, bytes)
                yield 'List view properties:'
                yield from show(plistlib.loads(data), tab_depth=1)
            elif field == 'lsvt':
                # lsvt supplanted by lsvp / lsvP
                self.validate_type(field, data, int)
                yield f'List view text size: {data}pt'
            # Following 2 may appear at the same time, but difference unknown
            # They were originally dutc, but now they use blob
            # When dutc, it's the number of 1 / 65536 seconds from 1904
            # Otherwise, it's TODO
            elif field == 'moDD':
                self.validate_type(field, data, (int, bytes))
                if isinstance(data, int):
                    date = data / 65536
                    yield f'Modification date: {show_date(date)}'
                elif isinstance(data, bytes):
                    # Little endian for some reason
                    date = int.from_bytes(data, 'little')
                    yield ('Modification date (timestamp, format unknown:'
                           f' {date}')
            elif field == 'modD':
                self.validate_type(field, data, (int, bytes))
                if isinstance(data, int):
                    date = data / 65536
                    yield f'Modification date, alternative: {show_date(date)}'
                elif isinstance(data, bytes):
                    # Little endian for some reason
                    date = int.from_bytes(data, 'little')
                    yield ('Modification date, alternative (timestamp, format'
                           f' unknown): {date}')
            elif field in {'ph1S', 'phyS'}:
                # phyS supplanted by ph1S for unknown reasons
                self.validate_type(field, data, int)
                yield f'Physical size: {data}B'
            elif field == 'pict':
                # pict, with BKGD, supplanted by TODO in later versions
                # pict in format of Apple Finder alias
                yield f'Picture: {show_one(data)}'
            elif field == 'vSrn':
                self.validate_type(field, data, int)
                yield f'{field} (unknown): {data}'
            elif field == 'vstl':
                self.validate_type(field, data, str)
                # Coverflow view not in Mojave now
                # Similarly there's no Gallery view back then
                views = {'icnv': 'Icon view',
                         'clmv': 'Column view',
                         'glyv': 'Gallery view',
                         'Nlsv': 'List view',
                         'Flwv': 'Coverflow view'}
                view = views.get(data, f'(unrecognized) {data}')
                yield f'View style: {view}'
            else:
                yield f'{field} (unrecognized): {data!r}'


class DSStore:

    def __init__(self, content):
        self.cursor = 0
        self.content = content
        self.records = []
        self.parse()

    def read(self):
        return self.records

    def next_byte(self):
        data = content[self.cursor]
        self.cursor += 1
        return data

    def next_bytes(self, n):
        data = content[self.cursor:self.cursor + n]
        self.cursor += n
        return data

    def next_uint32(self):
        data = int.from_bytes(self.next_bytes(4), 'big', signed=False)
        return data

    def next_uint64(self):
        data = int.from_bytes(self.next_bytes(8), 'big', signed=False)
        return data

    def parse_header(self):
        # Alignment int
        alignment = self.next_uint32()
        if alignment != 0x00000001:
            warnings.warn(f'Alignment int {hex(alignment)} not 0x00000001')

        # Magic bytes
        magic = self.next_uint32()
        if magic != 0x42756431:
            warnings.warn(f'Magic bytes {hex(magic)} not 0x42756431 (Bud1)')

        # Buddy allocator position & length
        # 0x4 for the alignment int
        self.allocator_offset = 0x4 + self.next_uint32()
        self.allocator_length = self.next_uint32()
        allocator_offset_repeat = 0x4 + self.next_uint32()
        if allocator_offset_repeat != self.allocator_offset:
            warnings.warn(f'Allocator offsets {hex(self.allocator_offset)} and'
                          f' {hex(allocator_offset_repeat)} unequal')

    def parse_allocator(self):
        self.cursor = self.allocator_offset

        # Offsets
        num_offsets = self.next_uint32()
        second = self.next_uint32()
        if second != 0:
            warnings.warn(f'Second int of allocator {hex(second)}'
                          ' not 0x00000000')
        self.offsets = [self.next_uint32() for _ in range(num_offsets)]

        self.cursor = self.allocator_offset + 0x408

        # Table of contents
        self.directory = {}
        num_keys = self.next_uint32()
        for _ in range(num_keys):
            key_length = self.next_byte()
            key = self.next_bytes(key_length).decode('ascii')
            self.directory[key] = self.next_uint32()
            if key != 'DSDB':
                warnings.warn(f"Directory contains non-'DSDB' key {key!r} and"
                              f' value {hex(self.directory[key])}')

        # Master node ID & offset
        if 'DSDB' not in self.directory:
            raise ValueError("Key 'DSDB' not found in table of contents")
        self.master_id = self.directory['DSDB']

        # Free list
        self.freelist = {}
        for i in range(32):
            values_length = self.next_uint32()
            self.freelist[1 << i] = [self.next_uint32()
                                     for _ in range(values_length)]

    def parse_tree(self, *, node_id=None):
        # The master node points to the root node and contains metadata
        # The B-tree contains nodes, which contain records of file properties
        # or nodes
        if node_id is None:
            master = True
            node_id = self.master_id
        else:
            master = False

        offset_and_size = self.offsets[node_id]
        self.cursor = 0x4 + (offset_and_size >> 0x5 << 0x5)
        # node size is 1 << (offset_and_size & 0x1f) TODO VALIDATE

        if master:
            # Master node
            self.root_id = self.next_uint32()
            self.tree_height = self.next_uint32()
            self.num_records = self.next_uint32()
            self.num_nodes = self.next_uint32()
            fifth = self.next_uint32()  # TODO: tree node page size?
            if fifth != 0x00001000:
                warnings.warn(f'Fifth int of master {hex(fifth)}'
                              ' not 0x00001000')
            self.parse_tree(node_id=self.root_id)
        else:
            next_id = self.next_uint32()
            num_records = self.next_uint32()
            for _ in range(num_records):
                if next_id:
                    # Has children
                    child_id = self.next_uint32()
                    current_cursor = self.cursor
                    self.parse_tree(node_id=child_id)
                    self.cursor = current_cursor

                name_length = self.next_uint32()
                name = self.next_bytes(name_length * 2).decode('utf-16be')
                field = self.next_bytes(4).decode('ascii')
                data = self.parse_data()
                for record in self.records:
                    if record.name == name:
                        record.update({field: data})
                        break
                else:
                    self.records.append(Record(name, {field: data}))

            if next_id:
                self.parse_tree(node_id=next_id)

    def parse_data(self):
        data_type = self.next_bytes(4).decode('ascii')
        if data_type == 'bool':
            return bool(self.next_byte() & 0x01)
        elif data_type in {'shor', 'long'}:
            # short is also 4, with 2 0x00 bytes padding, for some reason
            return self.next_uint32()
        elif data_type == 'comp':
            return self.next_uint64()
        elif data_type == 'dutc':
            return self.next_uint64()
        elif data_type == 'type':
            return self.next_bytes(4).decode('ascii')
        elif data_type == 'blob':
            data_length = self.next_uint32()
            return self.next_bytes(data_length)
        elif data_type == 'ustr':
            data_length = self.next_uint32()
            return self.next_bytes(2 * data_length).decode('utf-16be')
        else:
            raise NotImplementedError(f'Unrecognized data type {data_type}')

    def parse(self):
        self.parse_header()
        self.parse_allocator()
        self.parse_tree()


if __name__ == '__main__':
    if len(sys.argv) == 2:
        filename = sys.argv[1]
    elif len(sys.argv) == 1:
        print(f'File unspecified. Use python3 {sys.argv[0]} <.DS_Store file>'
              ' to specify file. Defaulting to .DS_Store in the current'
              ' directory...', file=sys.stderr)
        filename = '.DS_Store'
    else:
        print(f'Usage: python3 {sys.argv[0]} <.DS_Store file>')
    with open(filename, 'rb') as file:
        content = file.read()
    ds_store = DSStore(content)
    for record in ds_store.read():
        print(record.name)
        for description in record.human_readable():
            print(f'\t{description}')
