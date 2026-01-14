Optional dependencies

This project supports exporting reports as PDF using xhtml2pdf. The PDF generation dependency is optional and is only required when you want to download PDF reports.

To enable PDF export, install the package:

pip install xhtml2pdf

If xhtml2pdf is not installed, the application will still run and the reports view will render as HTML. The code performs a lazy import and will show an install hint when a user attempts to generate a PDF.
