"""
Report Formatter - Converts semantic markers to HTML for display
This module handles the conversion of clean semantic markers to properly formatted HTML
"""

import re
from typing import Optional

class ReportFormatter:
    """Converts semantic markdown-like syntax to HTML for report display"""
    
    @staticmethod
    def format_to_html(text: str) -> str:
        """
        Convert semantic markers to HTML
        
        Supported markers:
        # Main title -> <h1>
        ## Section -> <h2>  
        ### Subsection -> <h3>
        #### Minor -> <h4>
        **Bold** -> <strong>
        *Italic* -> <em>
        - Bullet -> <ul><li>
        1. Number -> <ol><li>
        --- -> <hr>
        """
        if not text:
            return ""
            
        # Split into lines for processing
        lines = text.split('\n')
        html_lines = []
        in_ul = False
        in_ol = False
        ul_items = []
        ol_items = []
        
        for line in lines:
            stripped = line.strip()
            
            # Skip empty lines but preserve them for spacing
            if not stripped:
                # Close any open lists before empty line
                if in_ul:
                    html_lines.append('<ul>')
                    html_lines.extend(f'<li>{item}</li>' for item in ul_items)
                    html_lines.append('</ul>')
                    ul_items = []
                    in_ul = False
                if in_ol:
                    html_lines.append('<ol>')
                    html_lines.extend(f'<li>{item}</li>' for item in ol_items)
                    html_lines.append('</ol>')
                    ol_items = []
                    in_ol = False
                html_lines.append('')
                continue
            
            # Process headings
            if stripped.startswith('#### '):
                # Close any open lists
                if in_ul:
                    html_lines.append('<ul>')
                    html_lines.extend(f'<li>{item}</li>' for item in ul_items)
                    html_lines.append('</ul>')
                    ul_items = []
                    in_ul = False
                if in_ol:
                    html_lines.append('<ol>')
                    html_lines.extend(f'<li>{item}</li>' for item in ol_items)
                    html_lines.append('</ol>')
                    ol_items = []
                    in_ol = False
                html_lines.append(f'<h4>{ReportFormatter._format_inline(stripped[5:])}</h4>')
                
            elif stripped.startswith('### '):
                # Close any open lists
                if in_ul:
                    html_lines.append('<ul>')
                    html_lines.extend(f'<li>{item}</li>' for item in ul_items)
                    html_lines.append('</ul>')
                    ul_items = []
                    in_ul = False
                if in_ol:
                    html_lines.append('<ol>')
                    html_lines.extend(f'<li>{item}</li>' for item in ol_items)
                    html_lines.append('</ol>')
                    ol_items = []
                    in_ol = False
                html_lines.append(f'<h3>{ReportFormatter._format_inline(stripped[4:])}</h3>')
                
            elif stripped.startswith('## '):
                # Close any open lists
                if in_ul:
                    html_lines.append('<ul>')
                    html_lines.extend(f'<li>{item}</li>' for item in ul_items)
                    html_lines.append('</ul>')
                    ul_items = []
                    in_ul = False
                if in_ol:
                    html_lines.append('<ol>')
                    html_lines.extend(f'<li>{item}</li>' for item in ol_items)
                    html_lines.append('</ol>')
                    ol_items = []
                    in_ol = False
                html_lines.append(f'<h2>{ReportFormatter._format_inline(stripped[3:])}</h2>')
                
            elif stripped.startswith('# '):
                # Close any open lists
                if in_ul:
                    html_lines.append('<ul>')
                    html_lines.extend(f'<li>{item}</li>' for item in ul_items)
                    html_lines.append('</ul>')
                    ul_items = []
                    in_ul = False
                if in_ol:
                    html_lines.append('<ol>')
                    html_lines.extend(f'<li>{item}</li>' for item in ol_items)
                    html_lines.append('</ol>')
                    ol_items = []
                    in_ol = False
                html_lines.append(f'<h1>{ReportFormatter._format_inline(stripped[2:])}</h1>')
                
            # Process horizontal rules
            elif stripped == '---':
                # Close any open lists
                if in_ul:
                    html_lines.append('<ul>')
                    html_lines.extend(f'<li>{item}</li>' for item in ul_items)
                    html_lines.append('</ul>')
                    ul_items = []
                    in_ul = False
                if in_ol:
                    html_lines.append('<ol>')
                    html_lines.extend(f'<li>{item}</li>' for item in ol_items)
                    html_lines.append('</ol>')
                    ol_items = []
                    in_ol = False
                html_lines.append('<hr>')
                
            # Process bullet points
            elif stripped.startswith('- '):
                if in_ol:
                    # Close ordered list first
                    html_lines.append('<ol>')
                    html_lines.extend(f'<li>{item}</li>' for item in ol_items)
                    html_lines.append('</ol>')
                    ol_items = []
                    in_ol = False
                
                in_ul = True
                ul_items.append(ReportFormatter._format_inline(stripped[2:]))
                
            # Process numbered lists  
            elif re.match(r'^\d+\. ', stripped):
                if in_ul:
                    # Close unordered list first
                    html_lines.append('<ul>')
                    html_lines.extend(f'<li>{item}</li>' for item in ul_items)
                    html_lines.append('</ul>')
                    ul_items = []
                    in_ul = False
                
                in_ol = True
                # Remove the number and period
                content = re.sub(r'^\d+\. ', '', stripped)
                ol_items.append(ReportFormatter._format_inline(content))
                
            # Regular paragraph
            else:
                # Close any open lists before paragraph
                if in_ul:
                    html_lines.append('<ul>')
                    html_lines.extend(f'<li>{item}</li>' for item in ul_items)
                    html_lines.append('</ul>')
                    ul_items = []
                    in_ul = False
                if in_ol:
                    html_lines.append('<ol>')
                    html_lines.extend(f'<li>{item}</li>' for item in ol_items)
                    html_lines.append('</ol>')
                    ol_items = []
                    in_ol = False
                    
                html_lines.append(f'<p>{ReportFormatter._format_inline(stripped)}</p>')
        
        # Close any remaining open lists
        if in_ul:
            html_lines.append('<ul>')
            html_lines.extend(f'<li>{item}</li>' for item in ul_items)
            html_lines.append('</ul>')
        if in_ol:
            html_lines.append('<ol>')
            html_lines.extend(f'<li>{item}</li>' for item in ol_items)
            html_lines.append('</ol>')
            
        return '\n'.join(html_lines)
    
    @staticmethod
    def _format_inline(text: str) -> str:
        """Format inline elements like bold and italic"""
        if not text:
            return ""
            
        # Convert **bold** to <strong>
        text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
        
        # Convert *italic* to <em> (but not if it's already part of **)
        text = re.sub(r'(?<!\*)\*([^*]+?)\*(?!\*)', r'<em>\1</em>', text)
        
        return text

# Convenience function for easy import
def format_report_to_html(text: str) -> str:
    """Convert semantic markers to HTML - convenience function"""
    return ReportFormatter.format_to_html(text)