from PyPDF2 import PdfFileReader
from PyPDF2.utils import PdfReadError


def open_file(path):
    input1 = PdfFileReader(open(path, "rb"))

    if input1.isEncrypted:
        input1.decrypt('')

    # sometimes we must decode pdf file with another method
    try:
        input1.getPage(0)
        catalog = input1.trailer["/Root"].getObject()
        if '/StructTreeRoot' in catalog:
            catalog.get('/StructTreeRoot').getObject()
    except PdfReadError:
        import os, shutil, tempfile
        from subprocess import check_call

        try:
            tempdir = tempfile.mkdtemp(dir=os.path.dirname(path))
            temp_out = os.path.join(tempdir, 'qpdf_out.pdf')
            check_call(['qpdf', "--password=", '--decrypt', path, temp_out])
            shutil.move(temp_out, path)
        finally:
            shutil.rmtree(tempdir)
    return input1


files = [
    "PDF_Samples/AutoCad_Diagram.pdf",
    "PDF_Samples/tables/sample123.pdf",
    "PDF_Samples/tables/GeoBase_NHNC1_Data_Model_UML_EN.pdf",
    "PDF_Samples/tables/table_libr.pdf",
    "PDF_Samples/tables/book7.pdf",
    "PDF_Samples/tables/table.pdf",
]

for file in files:
    print('file:', file)
    reader = open_file(file)
    tables = reader.search_tables()
    for table in tables:
        # print(table.get_data())
        table.show()
