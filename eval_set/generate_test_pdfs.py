import os
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable

def create_gst_certificate(filename: str, legal_name: str, gstin: str):
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    styles = getSampleStyleSheet()

    header_style = ParagraphStyle(
        name="GSTHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=20,
        alignment=1, # Center
        textColor=colors.HexColor("#1A365D")
    )
    
    sub_header_style = ParagraphStyle(
        name="GSTSubHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        alignment=1,
        textColor=colors.HexColor("#2C5282")
    )
    
    body_style = ParagraphStyle(
        name="GSTBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.black
    )
    
    bold_style = ParagraphStyle(
        name="GSTBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=14,
        textColor=colors.black
    )

    story = []

    story.append(Paragraph("Government of India", header_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph("Form GST REG-06", sub_header_style))
    story.append(Paragraph("<b>Registration Certificate</b>", sub_header_style))
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1A365D"), spaceAfter=15))

    details_data = [
        [Paragraph("<b>Registration Number (GSTIN)</b>", bold_style), Paragraph(f"<b>{gstin}</b>", bold_style)],
        [Paragraph("<b>1. Legal Name</b>", body_style), Paragraph(legal_name, body_style)],
        [Paragraph("<b>2. Trade Name, if any</b>", body_style), Paragraph(legal_name, body_style)],
        [Paragraph("<b>3. Constitution of Business</b>", body_style), Paragraph("Private Limited Company", body_style)],
        [Paragraph("<b>4. Address of Principal Place of Business</b>", body_style), Paragraph("123 Industrial Area, Phase II, New Delhi, Delhi, 110020", body_style)],
        [Paragraph("<b>5. Date of Liability</b>", body_style), Paragraph("01/07/2017", body_style)],
        [Paragraph("<b>6. Period of Validity</b>", body_style), Paragraph("From: 01/07/2017 &nbsp;&nbsp;&nbsp;&nbsp; To: Permanent", body_style)],
        [Paragraph("<b>7. Type of Registration</b>", body_style), Paragraph("Regular", body_style)],
    ]

    t = Table(details_data, colWidths=[200, 340])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#A0AEC0")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(t)
    story.append(Spacer(1, 25))

    auth_data = [
        [Paragraph("<b>Jurisdictional Office:</b> Ward 101, Delhi", body_style), Paragraph("<b>Signature:</b> <i>Digitally Signed</i>", body_style)],
        [Paragraph("<b>Date of Issue of Certificate:</b> 01/07/2017", body_style), Paragraph("<b>Name:</b> Assistant Commissioner of State Tax", body_style)],
    ]
    t_auth = Table(auth_data, colWidths=[270, 270])
    t_auth.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t_auth)
    story.append(Spacer(1, 20))
    story.append(Paragraph("<i>Note: The registration certificate is required to be prominently displayed at all places of business.</i>", ParagraphStyle(
        name="GSTNote",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=8,
        alignment=1,
        textColor=colors.gray
    )))

    doc.build(story)
    print(f"Generated GST certificate: {filename}")


def create_menu(filename: str):
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        name="MenuTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=28,
        alignment=1,
        textColor=colors.HexColor("#9B2C2C")
    )
    
    tagline_style = ParagraphStyle(
        name="MenuTagline",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=12,
        leading=16,
        alignment=1,
        textColor=colors.HexColor("#742A2A")
    )

    section_style = ParagraphStyle(
        name="MenuSection",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#9B2C2C"),
        spaceBefore=10,
        spaceAfter=5
    )

    item_name_style = ParagraphStyle(
        name="MenuItemName",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=colors.black
    )

    item_desc_style = ParagraphStyle(
        name="MenuItemDesc",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#4A5568")
    )

    price_style = ParagraphStyle(
        name="MenuPrice",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        alignment=2, # Right
        textColor=colors.HexColor("#9B2C2C")
    )

    story = []

    story.append(Paragraph("MARIO'S PIZZERIA & TRATTORIA", title_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph("Authentic Wood-Fired Artisanal Pizzas & Fresh Italian Delights", tagline_style))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#9B2C2C"), spaceAfter=12))

    story.append(Paragraph("CLASSIC & ARTISANAL PIZZAS (12\")", section_style))

    pizzas = [
        ("Margherita Classica", "San Marzano tomato sauce, fresh buffalo mozzarella, fresh basil, extra virgin olive oil", "$14.00"),
        ("Pepperoni Supreme", "Italian spicy pepperoni, crushed tomato sauce, fresh mozzarella, oregano", "$16.50"),
        ("Quattro Formaggi", "Creamy gorgonzola, aged parmesan, fresh mozzarella, ricotta, roasted garlic", "$17.00"),
        ("Truffle Wild Mushroom", "Sautéed porcini & cremini mushrooms, truffle cream sauce, fior di latte, fresh thyme", "$18.50"),
        ("Diavola Piccante", "Spicy Calabrian salami, chili oil, red onion, smoked provolone, fresh mozzarella", "$17.50"),
        ("Garden Veggie Supreme", "Fire-roasted bell peppers, baby spinach, kalamata olives, artichoke hearts, mozzarella", "$15.50"),
    ]

    pizza_table_data = []
    for name, desc, price in pizzas:
        desc_cell = [
            Paragraph(f"<b>{name}</b>", item_name_style),
            Paragraph(desc, item_desc_style)
        ]
        pizza_table_data.append([desc_cell, Paragraph(price, price_style)])

    t_pizzas = Table(pizza_table_data, colWidths=[440, 100])
    t_pizzas.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor("#EDF2F7")),
    ]))
    story.append(t_pizzas)
    story.append(Spacer(1, 10))

    story.append(Paragraph("APPETIZERS, SIDES & BEVERAGES", section_style))

    sides = [
        ("Garlic Herb Breadsticks", "Served warm with house-made marinara dipping sauce", "$6.50"),
        ("Crispy Truffle Fries", "Tossed with parmesan reggiano, herbs, and truffle aioli", "$7.50"),
        ("Classic Caesar Salad", "Crisp romaine, shaved parmesan, house garlic croutons, Caesar dressing", "$8.50"),
        ("Traditional Tiramisu", "Espresso-soaked ladyfingers, mascarpone cream, cocoa dust", "$7.00"),
        ("Italian Sparkling Mineral Water (750ml)", "San Pellegrino chilled sparkling water", "$4.00"),
    ]

    sides_table_data = []
    for name, desc, price in sides:
        desc_cell = [
            Paragraph(f"<b>{name}</b>", item_name_style),
            Paragraph(desc, item_desc_style)
        ]
        sides_table_data.append([desc_cell, Paragraph(price, price_style)])

    t_sides = Table(sides_table_data, colWidths=[440, 100])
    t_sides.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor("#EDF2F7")),
    ]))
    story.append(t_sides)

    doc.build(story)
    print(f"Generated Pizza menu: {filename}")


def main():
    eval_dir = Path(__file__).parent.resolve()
    eval_dir.mkdir(parents=True, exist_ok=True)

    # 1. valid_gst.pdf
    valid_gst_path = str(eval_dir / "valid_gst.pdf")
    create_gst_certificate(
        filename=valid_gst_path,
        legal_name="ACME CORP",
        gstin="07AAAAA0000A1Z5"
    )

    # 2. mismatch_gst.pdf
    mismatch_gst_path = str(eval_dir / "mismatch_gst.pdf")
    create_gst_certificate(
        filename=mismatch_gst_path,
        legal_name="ACME CORP",
        gstin="07BBBBB9999B1Z5"
    )

    # 3. menu.pdf
    menu_path = str(eval_dir / "menu.pdf")
    create_menu(filename=menu_path)

    print("All test PDFs generated successfully in:", eval_dir)


if __name__ == "__main__":
    main()
