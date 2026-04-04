import os
from decimal import Decimal

from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML

from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.plan import Plan

# Template directory
TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")

env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=select_autoescape(["html"]),
)


def generate_invoice_pdf(invoice: Invoice, customer: Customer, plan: Plan, payments: list, total_paid: Decimal) -> bytes:
    """Generate a PDF invoice and return bytes."""
    template = env.get_template("invoice.html")
    balance = invoice.amount - total_paid

    html_content = template.render(
        invoice=invoice,
        customer=customer,
        plan=plan,
        payments=payments,
        total_paid=total_paid,
        balance=balance,
    )

    pdf_bytes = HTML(string=html_content).write_pdf()
    return pdf_bytes
