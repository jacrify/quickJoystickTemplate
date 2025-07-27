import sys
import xml.etree.ElementTree as ET
import re
from xml.sax.saxutils import escape, unescape
import logging
import os
from datetime import datetime
from pathlib import Path
import base64
from typing import Dict, Optional
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class GremlinParser:
    """
    Parses a Joystick Gremlin XML file to extract key-value mappings
    from the 'description' attributes of elements.
    """

    def __init__(self, xml_file: Path):
        """
        Initializes the parser with the path to the XML file.

        :param xml_file: The path to the Joystick Gremlin XML file.
        """
        self.xml_file = xml_file
        self.mappings = self._parse()

    def _parse(self) -> Optional[Dict[str, str]]:
        """
        Parses the XML file and extracts the mappings.

        The description attribute is parsed as a pipe-separated string of
        key-value pairs. For example, "KEY1|Value1|KEY2|Value2".

        :return: A dictionary of the mappings found in the file.
        """
        mappings = {}
        try:
            with open(self.xml_file, 'r', encoding='utf-8-sig') as f:
                tree = ET.parse(f)
            root = tree.getroot()

            for element in root.iter():
                if 'description' in element.attrib:
                    description = element.attrib['description'].strip()
                    if not description:
                        continue

                    parts = description.split('|')
                    # Process in pairs
                    for i in range(0, len(parts), 2):
                        key = parts[i].strip()
                        if key and i + 1 < len(parts):
                            value = parts[i+1].strip()
                            mappings[key] = value
                        elif key:
                            mappings[key] = "" # Handle keys with no value
        except ET.ParseError as e:
            logging.error(f"Error parsing XML file: {e}")
            return None
        except FileNotFoundError:
            logging.error(f"Error: XML file not found at {self.xml_file}")
            return None
        
        if not mappings:
            logging.warning("No mappings were found in the XML file.")
        return mappings

class SvgTemplate:
    """
    Handles reading, modifying, and saving an SVG template file.
    """

    def __init__(self, svg_file: Path):
        """
        Initializes the template with the path to the SVG file.

        :param svg_file: The path to the SVG template file.
        """
        self.svg_file = svg_file
        with open(svg_file, 'r', encoding='utf-8') as f:
            self.raw_data = f.read()

    def _sanitize_string_for_svg(self, value_to_sanitize: str) -> str:
        """Safely sanitize string for SVG display"""
        return escape(unescape(value_to_sanitize))

    def replace_fields(self, mappings: Dict[str, str], xml_filename: str):
        """
        Replaces fields in the SVG data based on the provided mappings.

        :param mappings: A dictionary of fields to replace, where the key
                         is the placeholder and the value is the replacement text.
        :param xml_filename: The name of the input XML file.
        """
        # Replace TEMPLATE_NAME and CURRENT_DATE
        template_name = os.path.splitext(os.path.basename(xml_filename))[0]
        current_date = datetime.now().strftime("%d/%m/%Y")
        self.raw_data = self.raw_data.replace("TEMPLATE_NAME", template_name)
        self.raw_data = self.raw_data.replace("CURRENT_DATE", current_date)

        replacements_made = 0
        
        # Sort keys by length, descending, to handle cases like 'B10' and 'B1'
        sorted_keys = sorted(mappings.keys(), key=len, reverse=True)

        # Iterate through the mappings and replace keys with values in the SVG
        for key in sorted_keys:
            value = mappings[key]
            # This regex finds the key when it's the sole content of a tag,
            # allowing for surrounding whitespace.
            search_pattern = re.compile(rf">\s*{re.escape(key)}\s*<", re.IGNORECASE)
            replacement_value = self._sanitize_string_for_svg(value)
            replacement_string = f">{replacement_value}<"
            
            # Check if the key exists before replacing
            if search_pattern.search(self.raw_data):
                logging.info(f"Found key '{key}' in SVG. Replacing with '{replacement_value}'.")
                self.raw_data = search_pattern.sub(replacement_string, self.raw_data)
                replacements_made += 1
            else:
                logging.warning(f"Key '{key}' not found in SVG.")

        if replacements_made > 0:
            logging.info(f"Total of {replacements_made} replacements were made.")
        else:
            logging.warning("No replacements were made in the SVG file.")

    def _get_driver(self):
        """Configure and return a headless Chrome webdriver."""
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        driver = webdriver.Chrome(options=chrome_options)
        return driver

    def save_pdf(self, output_path: Path):
        """
        Saves the modified SVG data to a new PDF file using a headless browser.

        :param output_path: The path to save the new PDF file.
        """
        driver = self._get_driver()
        temp_svg_path = None
        try:
            # Use a temporary file to render the SVG
            temp_svg_path = output_path.with_suffix('.temp.svg')
            with open(temp_svg_path, 'w', encoding='utf-8') as f:
                f.write(self.raw_data)

            driver.get(f"file:///{temp_svg_path.resolve()}")

            # Get the exact dimensions of the SVG element
            dimensions = driver.execute_script(
                "const svg = document.querySelector('svg');"
                "if (svg) {"
                "    const width = svg.getAttribute('width');"
                "    const height = svg.getAttribute('height');"
                "    return {width: parseFloat(width), height: parseFloat(height)};"
                "} else { return null; }"
            )

            if not dimensions or not dimensions.get('width') or not dimensions.get('height'):
                raise Exception("Could not determine SVG dimensions.")

            # Convert pixel dimensions to inches for printing (assuming 96 DPI)
            dpi = 96
            paper_width = dimensions['width'] / dpi
            paper_height = dimensions['height'] / dpi
            
            # Use Chrome's DevTools Protocol to print to PDF in landscape
            print_settings = {
                "landscape": True,
                "printBackground": True,
                "marginTop": 0,
                "marginBottom": 0,
                "marginLeft": 0,
                "marginRight": 0,
                "pageRanges": "1",
            }
            result = driver.execute_cdp_cmd("Page.printToPDF", print_settings)
            pdf_data = base64.b64decode(result['data'])
            
            with open(output_path, 'wb') as f:
                f.write(pdf_data)

            print(f"Successfully converted SVG to PDF and saved to {output_path}")
        finally:
            driver.quit()
            if temp_svg_path and temp_svg_path.exists():
                os.remove(temp_svg_path)


def main():
    if len(sys.argv) not in [3, 4]:
        print("Usage: python diagram_generator.py <gremlin_xml_file> <svg_template_file> [output_dir]")
        sys.exit(1)

    xml_file = Path(sys.argv[1])
    svg_file = Path(sys.argv[2])
    
    output_dir = Path('.')
    if len(sys.argv) == 4:
        output_dir = Path(sys.argv[3])
        output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / xml_file.with_suffix('.pdf').name

    parser = GremlinParser(xml_file)
    mappings = parser.mappings
    
    if mappings is not None:
        try:
            template = SvgTemplate(svg_file)
            template.replace_fields(mappings, str(xml_file))
            template.save_pdf(output_file)

        except FileNotFoundError:
            logging.error(f"Error: SVG file not found at {svg_file}")
        except Exception as e:
            logging.error(f"An error occurred during file generation: {e}")


if __name__ == "__main__":
    main()