# import all necessary libraries
import os
from datetime import datetime
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.oxml.ns import qn
from typing import Union
from schema import Therapist
from omegaconf import DictConfig
import logging

logger = logging.getLogger(__name__)

def save_therapist_case_to_docx_file(report, therapist: Therapist, output_config: DictConfig, patient_name: str = None, patient_id: str = None):
    """Save therapist case analysis to a Word document with configuration-based settings"""
    
    # Create Word document
    doc = Document()

    # Set document to RTL for Hebrew
    section = doc.sections[0]
    section.orientation = section.orientation

    def add_rtl_paragraph(text):
        """Helper function to add RTL paragraph"""
        # Remove asterisks from text
        clean_text = text.replace('*', '').strip()
        p = doc.add_paragraph(clean_text)
        p.alignment = WD_PARAGRAPH_ALIGNMENT.RIGHT
        # Set paragraph direction to RTL
        p._element.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        # Set font to Times New Roman
        for run in p.runs:
            run.font.name = 'Times New Roman'
            run.font.size = Pt(12)
        return p

    def add_rtl_heading(text, level=1):
        """Helper function to add RTL heading"""
        clean_text = text.replace('*', '').strip()
        h = doc.add_heading(clean_text, level=level)
        h.alignment = WD_PARAGRAPH_ALIGNMENT.RIGHT
        # Set font to Times New Roman for headings
        for run in h.runs:
            run.font.name = 'Times New Roman'
            if level == 0:
                run.font.size = Pt(18)
            else:
                run.font.size = Pt(14)
        return h

    # Add therapist details at the beginning
    add_rtl_heading('דוח ניתוח מקרה בתחום פתולוגיית הדיבור', 0)
    add_rtl_heading('פרטי המטפל', level=1)
    add_rtl_paragraph(f"שם: {therapist.name}")
    add_rtl_paragraph(f"תפקיד: {therapist.role}")
    add_rtl_paragraph(f"שיוך: {therapist.affiliation}")
    add_rtl_paragraph(f"תיאור: {therapist.description}")

    # Add report content
    add_rtl_heading('ניתוח המקרה', level=1)

    # Handle report content - remove asterisks and split into paragraphs
    if hasattr(report, 'content'):
        report_text = report.content
    else:
        report_text = str(report)

    clean_report = report_text.replace('*', '').strip()

    # Split into paragraphs and add each as RTL
    paragraphs = clean_report.split('\n\n')
    for para in paragraphs:
        if para.strip():
            add_rtl_paragraph(para.strip())

    # Add timestamp
    add_rtl_paragraph(f"דוח נוצר בתאריך: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Create organized folder structure based on patient information
    script_dir = os.path.dirname(os.path.abspath(__file__))  # Get studio directory
    
    # Create patient-specific folder name
    if patient_name and patient_id:
        folder_name = f"{patient_name}_{patient_id}".replace(" ", "_").replace("/", "_").replace("\\", "_")
    elif patient_name:
        folder_name = patient_name.replace(" ", "_").replace("/", "_").replace("\\", "_")
    else:
        folder_name = "unknown_patient"
    
    # Create outputs directory structure
    outputs_dir = os.path.join(script_dir, "outputs", folder_name)
    os.makedirs(outputs_dir, exist_ok=True)

    # Generate filename using configuration template
    timestamp = datetime.now().strftime(output_config.timestamp_format)
    filename_template = output_config.filename_template
    filename = filename_template.format(
        therapist_role=therapist.role,
        timestamp=timestamp
    )
    
    # Save document
    filepath = os.path.join(outputs_dir, filename)
    doc.save(filepath)
    
    logger.info(f"Report saved to: {filepath}")
    logger.debug(f"Final Report: {clean_report}")

def save_final_report_to_docx_file(final_report: str, patient_case: str, output_config: DictConfig, patient_name: str = None, patient_id: str = None):
    """Save the final synthesized therapy report to a Word document"""
    
    # Create Word document
    doc = Document()

    # Set document to RTL for Hebrew
    section = doc.sections[0]
    section.orientation = section.orientation

    def add_rtl_paragraph(text):
        """Helper function to add RTL paragraph"""
        # Remove asterisks from text
        clean_text = text.replace('*', '').strip()
        p = doc.add_paragraph(clean_text)
        p.alignment = WD_PARAGRAPH_ALIGNMENT.RIGHT
        # Set paragraph direction to RTL
        p._element.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        # Set font to Times New Roman
        for run in p.runs:
            run.font.name = 'Times New Roman'
            run.font.size = Pt(12)
        return p

    def add_rtl_heading(text, level=1):
        """Helper function to add RTL heading"""
        clean_text = text.replace('*', '').strip()
        h = doc.add_heading(clean_text, level=level)
        h.alignment = WD_PARAGRAPH_ALIGNMENT.RIGHT
        # Set font to Times New Roman for headings
        for run in h.runs:
            run.font.name = 'Times New Roman'
            if level == 0:
                run.font.size = Pt(18)
            else:
                run.font.size = Pt(14)
        return h

    # Add main title
    add_rtl_heading('דוח תוכנית טיפול מקיף בתחום פתולוגיית הדיבור', 0)
    
    # Add patient case summary
    add_rtl_heading('תיאור המקרה', level=1)
    add_rtl_paragraph(patient_case)

    # Add synthesized report content
    add_rtl_heading('תוכנית הטיפול המשולבת', level=1)

    # Handle final report content
    clean_report = final_report.replace('*', '').strip()

    # Split into paragraphs and add each as RTL
    paragraphs = clean_report.split('\n\n')
    for para in paragraphs:
        if para.strip():
            add_rtl_paragraph(para.strip())

    # Add timestamp
    add_rtl_paragraph(f"דוח נוצר בתאריך: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Create organized folder structure based on patient information
    script_dir = os.path.dirname(os.path.abspath(__file__))  # Get studio directory
    
    # Create patient-specific folder name
    if patient_name and patient_id:
        folder_name = f"{patient_name}_{patient_id}".replace(" ", "_").replace("/", "_").replace("\\", "_")
    elif patient_name:
        folder_name = patient_name.replace(" ", "_").replace("/", "_").replace("\\", "_")
    else:
        folder_name = "unknown_patient"
    
    # Create outputs directory structure
    outputs_dir = os.path.join(script_dir, "outputs", folder_name)
    os.makedirs(outputs_dir, exist_ok=True)

    # Generate filename for final report
    timestamp = datetime.now().strftime(output_config.timestamp_format)
    filename = f"therapy_plan_final_report_{timestamp}.docx"
    
    # Save document
    filepath = os.path.join(outputs_dir, filename)
    doc.save(filepath)
    
    logger.info(f"Final therapy report saved to: {filepath}")
    logger.debug(f"Final synthesized report: {clean_report}")
    
    return filepath
