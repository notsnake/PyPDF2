from collections import defaultdict

from PyPDF2.generic import ByteStringObject, TextStringObject, DictionaryObject, IndirectObject
from PyPDF2.utils import b_, u_


def convert(words):
    words = words.hex()
    try:
        result = bytes.fromhex(words).decode('utf-16-be')
    except UnicodeDecodeError:
        result = '?'
    return result


class CashObject:
    _instance = None
    _objects = {}

    def __new__(cls, *args, **kwargs):
        if CashObject._instance is None:
            CashObject._instance = super(CashObject, cls).__new__(cls, *args, **kwargs)
        return CashObject._instance

    def get_objects(self):
        return self._objects

    def get_object(self, obj_id):
        return self._objects.get(obj_id)

    def add(self, obj_id, data):
        self._objects[obj_id] = data

    def clean(self):
        self._objects = {}


class TextConverter:
    def __init__(self, fonts=None, text_to_hex=True):
        self.fonts = fonts
        self.text_to_hex = text_to_hex
        self.cash = CashObject()

    def set_fonts(self, fonts):
        self.fonts = fonts

    def read_unicode(self, obj):
        from PyPDF2.pdf import ContentStream
        content = None
        table = {}
        if not isinstance(obj, ContentStream):
            try:
                content = ContentStream(obj, obj.pdf)
            except ValueError:
                pass
        if content is not None:
            for operands, operator in content.operations:
                if operator == b'endbfchar' or operator == b'endbfrange':
                    count_el = 2 if operator == b'endbfchar' else 3
                    # table has two or three elements
                    for index in range(0, len(operands), count_el):
                        key = operands[index]
                        if not isinstance(operands[index], ByteStringObject):
                            key = key.get_original_bytes()
                        key = key.hex()
                        value = operands[index + count_el - 1]
                        if not isinstance(value, ByteStringObject):
                            value = value.get_original_bytes()
                        value = convert(value)
                        table[key] = value
                        if count_el == 3 and operands[index] != operands[index + 1]:
                            # иногда указан диапазон значений, поэтому таблицу шрифтов
                            # дополняем динамически
                            for i in range(ord(operands[index]) + 1, ord(operands[index + 1]) + 2):
                                key = str(chr(i))
                                value = chr(ord(value) + 1)
                                table[key] = value

        return table

    def process_fonts(self, id_num, obj):
        # if table has structure and page has several tables then
        # we save fonts for this page object
        obj = obj.getObject()
        if id_num not in self.cash.get_objects():
            fonts_data = self.search_fonts(obj)
            self.cash.add(id_num, fonts_data)
        self.fonts = self.cash.get_object(id_num)

    def search_fonts(self, obj):
        result_fonts = {}
        fonts = obj.get('/Resources').getObject().get('/Font')
        if isinstance(fonts, IndirectObject):
            fonts = fonts.getObject()
        for name, obj in fonts.items():
            obj_unicode = obj.getObject().get('/ToUnicode')
            if obj_unicode:
                table_unicode = self.read_unicode(obj.getObject().get('/ToUnicode'))
                if table_unicode:
                    result_fonts[name] = table_unicode
        return result_fonts

    def process_text_objects(self, operands, current_font):
        text = u_("")
        if operands:
            if isinstance(operands, list):
                items = operands[0] if isinstance(operands[0], list) else operands
                for item in items:
                    text += self.process_text_object(item, current_font)
            else:
                text += self.process_text_object(operands, current_font)
        return text

    def process_text_object(self, item, current_font):
        def extract_text(self, item):
            item = item.hex()
            font = self.fonts.get(current_font, {})
            elem_length = len(list(font.keys())[0]) if font else 1
            items = [item[index: index + elem_length] for index in range(0, len(item), elem_length)]

            return ''.join([font.get(item, '?') for item in items if item in font])

        text = u_("")
        if isinstance(item, TextStringObject):
            if self.text_to_hex:
                item = item.get_original_bytes()
                text = extract_text(self, item)
            else:
                text = item
        elif isinstance(item, ByteStringObject):
            text = extract_text(self, item)
        return text


class StructuredTableFinder:
    def __init__(self, root):
        self.root = root
        self.tables = []

    def search(self):
        struct_tree_root = self.root.getObject()
        children = struct_tree_root.get('/K')
        self.search_tables(children)
        CashObject().clean()
        return self.tables

    def process_table(self, child):
        if not isinstance(child, int):
            child = child.getObject()
            if child.get('/S') and child.get('/S').lower() == '/table':
                self.tables.append(StructuredTable(child.get('/K'), self))

            elif child.get('/K'):
                new_children = child.get('/K')
                self.search_tables(new_children)

    def search_tables(self, children):
        if isinstance(children, list):
            for child in children:
                self.process_table(child)
        else:
            self.process_table(children)


class StructuredTable:
    def __init__(self, children, finder):
        self.children = children
        self.finder = finder
        self.rows = []
        self.caption_id = None
        self.content_table_id = None
        self.table = defaultdict(str)
        self.converter = TextConverter(text_to_hex=False)

        self.process()

    def set_table_id(self, row):
        # TR tags sometimes don't have tag Pg, then we must finding it in other tags
        if self.content_table_id is None and row.get('/Pg'):
            pg_obj = row.get('/Pg')
            self.content_table_id = pg_obj.getObject().get('/Contents')

            self.converter.process_fonts(pg_obj.idnum, pg_obj)
            self.process_content_object(self.content_table_id)

    def process_content_object(self, objects):
        from PyPDF2.pdf import ContentStream
        content = ContentStream(objects, self.finder)

        last_id = None
        last_font = None

        if content is not None:
            for operands, operator in content.operations:
                text = u_("")
                curr_id = self.get_id(operands)
                if curr_id is not None:
                    last_id = curr_id
                elif operator == b_("Tf"):
                    last_font = operands[0]
                elif operator == b_("Tj") or operator == b_("TJ"):
                    text += self.converter.process_text_objects(operands, last_font)
                elif operator == b_("T*"):
                    text += "\n"
                elif operator == b_("'"):
                    text += "\n"
                    _text = operands[0]
                    if isinstance(_text, TextStringObject):
                        text += operands[0]
                elif operator == b_('"'):
                    _text = operands[2]
                    if isinstance(_text, TextStringObject):
                        text += "\n"
                        text += _text

                if last_id is not None:
                    self.table[last_id] += text

    def get_id(self, data):
        result = None
        if isinstance(data, list):
            for obj in data:
                if isinstance(obj, DictionaryObject) and '/MCID' in obj:
                    result = obj.get('/MCID')
                    break
        elif isinstance(data, dict) and '/MCID' in data:
            result = data.get('/MCID')

        return result

    def is_processed(self):
        return len(self.rows) > 0

    def process(self):
        for row in self.children:
            row = row.getObject()

            if self.content_table_id is None:
                self.set_table_id(row)

            type_row = row.get('/S')
            if type_row and type_row.lower() == '/tr':
                # process row
                self.process_row(row.get('/K'))
            elif type_row and type_row.lower() == '/caption':
                # set table caption
                self.set_caption(row)

    def set_caption(self, obj):
        caption_id = obj.get('/K')
        if caption_id is not None and isinstance(caption_id, int):
            self.caption_id = caption_id

    def process_row(self, row_children):
        row = []
        if isinstance(row_children, list):
            # several table td
            for td in row_children:
                row.append(self.process_td(td))
        else:
            row.append(self.process_td(row_children))
        self.rows.append(row)

    def process_td(self, td):
        td = td.getObject()

        if self.content_table_id is None:
            self.set_table_id(td)

        td_list = []
        td_children = td.get('/K')
        if td_children and isinstance(td_children, list):
            for td_child in td_children:
                td_list.extend(self.process_td_text(td_child))
        else:
            td_list.extend(self.process_td_text(td_children))
        return td_list

    def process_td_text(self, td):
        # one td can content several texts in several objects
        result = []
        if td:
            if not isinstance(td, int):
                td_children = td.getObject()
                td_children_text_id = td_children.get('/K')
                result = self.check_indirect_objects(td_children_text_id)
                if not result:
                    result = td_children_text_id if isinstance(td_children_text_id, list) else [td_children_text_id]
            else:
                result = [td, ]

        return result

    def check_indirect_objects(self, objects):
        result = []
        if isinstance(objects, list):
            for indirect_object in objects:
                td = self.check_indirect_object(indirect_object)
                if td:
                    result.extend(td)
        else:
            td = self.check_indirect_object(objects)
            if td:
                result.extend(td)
        return result

    def check_indirect_object(self, obj):
        return self.process_td(obj.getObject()) if isinstance(obj, IndirectObject) else None

    def show(self):
        if self.caption_id is not None:
            print(self.table.get(self.caption_id, ''))

        if self.rows:
            for row in self.rows:
                for td_elements in row:
                    for td in td_elements:
                        # print(td, self.table.get(td, None), end=' ')
                        print(self.table.get(td, ''), end='')
                    print('|', end=' ')
                print()

    def get_data(self):
        data = []
        if self.rows:
            for row in self.rows:
                data.append([self.table.get(td, '') for td_elements in row for td in td_elements])
        return data


class PdfOfficeTableFinder:
    def __init__(self, pdf):
        self.pdf = pdf
        self.converter = TextConverter()
        self.tables = TableContainer()

    def search(self):
        from PyPDF2.pdf import ContentStream

        for num in range(self.pdf.getNumPages()):
            page = self.pdf.getPage(num)
            self.converter.process_fonts(num, page)

            content = page["/Contents"].getObject()
            if not isinstance(content, ContentStream):
                content = ContentStream(content, page)

            last_font = None
            last_x = None
            last_y = None
            re = None
            # re = rectangle

            for operands, operator in content.operations:
                text = u_("")
                if operator == b_("re"):
                    re = operands
                elif operator == b_("Tf"):
                    last_font = operands[0]
                elif operator == b_("Tj") or operator == b_("TJ"):
                    text += self.converter.process_text_objects(operands, last_font)
                elif operator == b_("T*"):
                    text += "\n"
                elif operator == b_("'"):
                    text += "\n"
                    _text = operands[0]
                    if isinstance(_text, TextStringObject):
                        text += operands[0]
                elif operator == b_('"'):
                    _text = operands[2]
                    if isinstance(_text, TextStringObject):
                        text += "\n"
                        text += _text
                elif operator == b_("Td"):
                    # text coordinates
                    last_x, last_y = operands
                elif operator == b_("cm"):
                    # text coordinates
                    *_, last_x, last_y = operands

                if text:
                    # print(text)
                    self.tables.process(re, text, last_x, last_y)
                    # re = None

        CashObject().clean()
        return self.tables.get_tables()


class Row:
    def __init__(self, y):
        self.y = y
        self.cells = []

    def add_cell(self, cell):
        # if x_min <= cell.x <= x_max and y_min <= cell.y <= y_max:
        self.cells.append(cell)


class Cell:
    def __init__(self, x, y, data):
        self.x = x
        self.y = y
        self.data = data


class Table:
    def __init__(self, x, y, x2, y2):
        # row represents y coordinate and appropriate Row object
        self.rows = {}
        self.min_x = x
        self.min_y = y
        self.max_x = x2
        self.max_y = y2

    def show(self):
        for rows in self.rows.values():
            for cell in rows.cells:
                print(cell.data, end='|')
            print('')

    def get_data(self):
        data = []
        if self.rows:
            for rows in self.rows.values():
                data.append([cell.data for cell in rows.cells])
        return data

    def is_empty(self):
        return len(self.rows) == 0

    def get_row(self, y):
        if y not in self.rows:
            self.rows[y] = Row(y)
        return self.rows[y]

    def check_coords(self, x, y, width, height):
        if self.min_x <= x <= self.max_x and self.min_y <= y + height <= self.max_y:
            self.min_y = y
            return True

        return False

    def __repr__(self):
        return "{}, {}, {}, {}".format(self.min_x, self.min_y, self.max_x, self.max_y)


class TableContainer:
    def __init__(self):
        self.tables = []

    def add_table(self, table):
        self.tables.append(table)

    def show(self):
        for table in self.tables:
            print('Table: ')
            table.show()

    def is_empty(self):
        return len(self.tables) == 0

    def create_table(self, x, y, width, height):
        table = Table(x, y, x + width, y + height)
        self.tables.append(table)
        return table

    def get_table_by_coords(self, x, y, width, height):
        if self.tables:
            for table in self.tables:
                if table.check_coords(x, y, width, height):
                    return table
            else:
                return self.create_table(x, y, width, height)
        else:
            return self.create_table(x, y, width, height)

    def process(self, rect, text, text_x, text_y):
        table = self.get_table_by_coords(*rect)
        r = table.get_row(text_y)
        r.add_cell(Cell(text_x, text_y, text))

    def get_tables(self):
        return self.tables
