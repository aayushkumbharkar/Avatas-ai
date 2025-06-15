import io
from typing import Dict, Any, List

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch

def format_value(value: Any) -> str:
    """Helper to format values for the PDF, especially floats."""
    if isinstance(value, float):
        return f"{value:.4f}"
    if value is None:
        return "N/A"
    return str(value)

def generate_bias_report_pdf(analysis_results: Dict[str, Any]) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            rightMargin=inch, leftMargin=inch,
                            topMargin=inch, bottomMargin=inch)

    styles = getSampleStyleSheet()
    # Custom styles
    styles.add(ParagraphStyle(name='Justify', alignment=0, parent=styles['Normal'])) # Justify = TA_JUSTIFY
    styles.add(ParagraphStyle(name='WarningStyle', parent=styles['Normal'], textColor=colors.red))
    styles.add(ParagraphStyle(name='SubtleHeading', parent=styles['h3'], fontSize=10, spaceBefore=0.2*inch, textColor=colors.darkgrey))


    Story: List[Any] = []

    # Title
    Story.append(Paragraph("Bias Analysis Report", styles['h1']))
    Story.append(Spacer(1, 0.25*inch))

    # Data Summary Section
    Story.append(Paragraph("Data Summary", styles['h2']))
    data_summary = analysis_results.get("data_summary", {})

    summary_data_table = [
        ["Item", "Details"],
        ["Data Shape", format_value(data_summary.get("data_shape"))],
        ["Label Name", format_value(data_summary.get("label_name"))],
        ["Protected Attributes", format_value(", ".join(data_summary.get("protected_attributes", [])))],
        ["Favorable Label (Processed)", format_value(data_summary.get("favorable_label_processed"))],
        ["Unfavorable Label (Processed)", format_value(data_summary.get("unfavorable_label_processed"))],
    ]
    if data_summary.get("favorable_label_original") != "N/A (was numeric)": # Only show if mapping occurred
        summary_data_table.insert(4, ["Favorable Label (Original)", format_value(data_summary.get("favorable_label_original"))])
        summary_data_table.insert(5, ["Unfavorable Label (Original)", format_value(data_summary.get("unfavorable_label_original"))])

    # Assumed groups could be long, handle them separately
    assumed_priv_groups = data_summary.get("assumed_privileged_groups", [])
    assumed_unpriv_groups = data_summary.get("assumed_unprivileged_groups", [])

    summary_table = Table(summary_data_table, colWidths=[2*inch, 4.5*inch])
    summary_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('BACKGROUND', (0,0), (0,-1), colors.lightgrey),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), # Header row bold
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    Story.append(summary_table)
    Story.append(Spacer(1, 0.1*inch))

    Story.append(Paragraph("Assumed Privileged Groups:", styles['SubtleHeading']))
    for group in assumed_priv_groups:
        Story.append(Paragraph(f"- {format_value(group)}", styles['Normal']))
    Story.append(Paragraph("Assumed Unprivileged Groups:", styles['SubtleHeading']))
    for group in assumed_unpriv_groups:
        Story.append(Paragraph(f"- {format_value(group)}", styles['Normal']))

    Story.append(Spacer(1, 0.25*inch))

    # Bias Metrics Section
    Story.append(Paragraph("Bias Metrics", styles['h2']))
    metrics = analysis_results.get("metrics", {})

    metrics_data = [
        ["Metric", "Value"],
        ["Demographic Parity Difference", format_value(metrics.get("demographic_parity_difference"))],
        ["Average Odds Difference", format_value(metrics.get("average_odds_difference"))],
    ]
    metrics_table = Table(metrics_data, colWidths=[3*inch, 1.5*inch])
    metrics_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('BACKGROUND', (0,0), (0,-1), colors.lightgrey),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('ALIGN', (1,1), (1,-1), 'RIGHT'), # Align values to the right
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    Story.append(metrics_table)
    Story.append(Spacer(1, 0.25*inch))

    # Statistical Significance Section
    Story.append(Paragraph("Statistical Significance (p-values)", styles['h2']))
    significance = metrics.get("statistical_significance", {})

    sig_data = [
        ["Metric Comparison", "p-value"],
        ["Demographic Parity", format_value(significance.get("demographic_parity_p_value"))],
        ["True Positive Rate Difference", format_value(significance.get("true_positive_rate_difference_p_value"))],
        ["False Positive Rate Difference", format_value(significance.get("false_positive_rate_difference_p_value"))],
    ]
    sig_table = Table(sig_data, colWidths=[3*inch, 1.5*inch])
    sig_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('BACKGROUND', (0,0), (0,-1), colors.lightgrey),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('ALIGN', (1,1), (1,-1), 'RIGHT'), # Align values to the right
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    Story.append(sig_table)
    Story.append(Spacer(1, 0.25*inch))

    # Warnings Section
    Story.append(Paragraph("Warnings & Assumptions", styles['h2']))
    warnings_list = analysis_results.get("warnings", [])
    if warnings_list:
        for warning_text in warnings_list:
            Story.append(Paragraph(warning_text, styles['WarningStyle']))
            Story.append(Spacer(1, 0.05*inch))
    else:
        Story.append(Paragraph("No warnings.", styles['Normal']))

    doc.build(Story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
