import binascii
import os
import sys
import unittest

from PyPDF2 import PdfFileReader, PdfFileWriter

# Configure path environment
TESTS_ROOT = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT = os.path.dirname(TESTS_ROOT)
RESOURCE_ROOT = os.path.join(PROJECT_ROOT, 'Resources')
TABLES_ROOT = os.path.join(PROJECT_ROOT, 'PDF_Samples', 'tables')

sys.path.append(PROJECT_ROOT)


class PdfReaderTestCases(unittest.TestCase):
    def test_PdfReaderFileLoad(self):
        '''
        Test loading and parsing of a file. Extract text of the file and compare to expected
        textual output. Expected outcome: file loads, text matches expected.
        '''

        with open(os.path.join(RESOURCE_ROOT, 'crazyones.pdf'), 'rb') as inputfile:
            # Load PDF file from file
            ipdf = PdfFileReader(inputfile)
            ipdf_p1 = ipdf.getPage(0)

            # Retrieve the text of the PDF
            with open(os.path.join(RESOURCE_ROOT, 'crazyones.txt'), 'rb') as pdftext_file:
                pdftext = pdftext_file.read()

            ipdf_p1_text = ipdf_p1.extractText().replace('\n', '').encode('utf-8')

            # Compare the text of the PDF to a known source
            self.assertEqual(ipdf_p1_text, pdftext,
                             msg='PDF extracted text differs from expected value.\n\nExpected:\n\n%r\n\nExtracted:\n\n%r\n\n'
                                 % (pdftext, ipdf_p1_text))

    def test_PdfReaderJpegImage(self):
        '''
        Test loading and parsing of a file. Extract the image of the file and compare to expected
        textual output. Expected outcome: file loads, image matches expected.
        '''

        with open(os.path.join(RESOURCE_ROOT, 'jpeg.pdf'), 'rb') as inputfile:
            # Load PDF file from file
            ipdf = PdfFileReader(inputfile)

            # Retrieve the text of the image
            with open(os.path.join(RESOURCE_ROOT, 'jpeg.txt'), 'r') as pdftext_file:
                imagetext = pdftext_file.read()

            ipdf_p0 = ipdf.getPage(0)
            xObject = ipdf_p0['/Resources']['/XObject'].getObject()
            data = xObject['/Im4'].getData()

            # Compare the text of the PDF to a known source
            self.assertEqual(binascii.hexlify(data).decode(), imagetext,
                             msg='PDF extracted image differs from expected value.\n\nExpected:\n\n%r\n\nExtracted:\n\n%r\n\n'
                                 % (imagetext, binascii.hexlify(data).decode()))


class AddJsTestCase(unittest.TestCase):
    def setUp(self):
        ipdf = PdfFileReader(os.path.join(RESOURCE_ROOT, 'crazyones.pdf'))
        self.pdf_file_writer = PdfFileWriter()
        self.pdf_file_writer.appendPagesFromReader(ipdf)

    def test_add(self):
        self.pdf_file_writer.addJS("this.print({bUI:true,bSilent:false,bShrinkToFit:true});")

        self.assertIn('/Names', self.pdf_file_writer._root_object,
                      "addJS should add a name catalog in the root object.")
        self.assertIn('/JavaScript', self.pdf_file_writer._root_object['/Names'],
                      "addJS should add a JavaScript name tree under the name catalog.")
        self.assertIn('/OpenAction', self.pdf_file_writer._root_object,
                      "addJS should add an OpenAction to the catalog.")

    def test_overwrite(self):
        self.pdf_file_writer.addJS("this.print({bUI:true,bSilent:false,bShrinkToFit:true});")
        first_js = self.get_javascript_name()

        self.pdf_file_writer.addJS("this.print({bUI:true,bSilent:false,bShrinkToFit:true});")
        second_js = self.get_javascript_name()

        self.assertNotEqual(first_js, second_js, "addJS should overwrite the previous script in the catalog.")

    def get_javascript_name(self):
        self.assertIn('/Names', self.pdf_file_writer._root_object)
        self.assertIn('/JavaScript', self.pdf_file_writer._root_object['/Names'])
        self.assertIn('/Names', self.pdf_file_writer._root_object['/Names']['/JavaScript'])
        return self.pdf_file_writer._root_object['/Names']['/JavaScript']['/Names'][0]


class TablesPdfReader(unittest.TestCase):
    def test_file_with_structured_tables(self):
        with open(os.path.join(TABLES_ROOT, 'sample123.pdf'), 'rb') as input_file:
            # Load PDF file from file
            pdf = PdfFileReader(input_file)

            tables = pdf.search_tables()
            self.assertEqual(len(tables), 28)
            # test first table
            table1 = tables[0]
            table_data = table1.get_data()
            # count rows
            self.assertEqual(len(table_data), 3)
            row1 = table_data[0]
            self.assertEqual(row1[0], 'Column header (TH)')
            self.assertEqual(row1[1], 'Column header (TH)')
            self.assertEqual(row1[2], 'Column header (TH)')
            row2 = table_data[1]
            self.assertEqual(row2[0], 'Row header (TH)')
            self.assertEqual(row2[1], 'Data cell (TD)')
            self.assertEqual(row2[2], 'Data cell (TD)')
            row3 = table_data[2]
            self.assertEqual(row3[0], 'Row header(TH)')
            self.assertEqual(row3[1], 'Data cell (TD)')
            self.assertEqual(row3[2], 'Data cell (TD)')

            table4 = tables[3]
            table_data = table4.get_data()
            # count rows
            self.assertEqual(len(table_data), 7)
            row1 = table_data[0]
            self.assertEqual(row1[0], 'Role')
            self.assertEqual(row1[1], 'Actor')
            row2 = table_data[1]
            self.assertEqual(row2[0], 'Main character')
            self.assertEqual(row2[1], 'Daniel Radcliffe')
            row7 = table_data[6]
            self.assertEqual(row7[0], 'Headmaster')
            self.assertEqual(row7[1], 'Richard Harris')

            table21 = tables[20]
            table_data = table21.get_data()
            self.assertEqual(len(table_data), 8)
            row1 = table_data[0]
            self.assertEqual(row1[0], 'Expenditure by function £million')
            self.assertEqual(row1[1], '2009/10')
            self.assertEqual(row1[2], '2010/11')
            row2 = table_data[1]
            self.assertEqual(row2[0], 'Policy functions')
            self.assertEqual(row2[1], 'Financial')
            self.assertEqual(row2[2], '22.5')
            self.assertEqual(row2[3], '30.57')
            row8 = table_data[7]
            self.assertEqual(row8[0], 'Other')
            self.assertEqual(row8[1], '12.69')
            self.assertEqual(row8[2], '10.32')

    def test_file_without_structured_tables(self):
        with open(os.path.join(TABLES_ROOT, 'book7.pdf'), 'rb') as input_file:
            # this file created from excel and all data stored in cell table
            pdf = PdfFileReader(input_file)
            tables = pdf.search_tables()
            self.assertEqual(len(tables), 3)
            # first table
            table1 = tables[0]
            table_data = table1.get_data()
            self.assertEqual(len(table_data), 2)
            row1 = table_data[0]
            self.assertEqual(row1[0], 'test1')
            self.assertEqual(row1[1], 'test2')
            self.assertEqual(row1[2], 'test3')
            row2 = table_data[1]
            self.assertEqual(row2[0], 'test4')
            self.assertEqual(row2[1], 'test4')
            self.assertEqual(row2[2], 'test5')
            # third table
            table3 = tables[2]
            table_data = table3.get_data()
            self.assertEqual(len(table_data), 2)
            row1 = table_data[0]
            self.assertEqual(row1[0], 'table1')
            self.assertEqual(row1[1], 'table2')
            row2 = table_data[1]
            self.assertEqual(row2[0], 'table3')
            self.assertEqual(row2[1], 'table4')
