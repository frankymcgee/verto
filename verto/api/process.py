import json
import frappe
from verto.utils.word_processing import process_document

@frappe.whitelist()
def generate_document(input_file, company_name, managing_director, company_logo, replacement_id,abbreviation,publish_date,review_date):
    # Directly use the input_file as it already contains the full path
    input_file_path = frappe.get_site_path(input_file.lstrip('/'))  # Ensure it works both with and without leading slash
    
    # Define the output file path
    output_file_name = f"generated_{input_file.split('/')[-1]}"
    output_file_path = frappe.get_site_path("private", "files", output_file_name)
    
    # Define the merge fields
    merge_fields = {
        "company_name": company_name,
        "managing_director": managing_director,
        "abbreviation": abbreviation,
        "publish_date": publish_date,
        "review_date": review_date
    }

    # Define the image replacements
    image_replacements = {}
    if company_logo:
        company_logo_path = frappe.get_site_path(company_logo.lstrip('/'))
        image_replacements[replacement_id] = company_logo_path
    
    # Process the document
    process_document(input_file_path, output_file_path, merge_fields, image_replacements)
    
    # Create a file record in the File Manager
    file_doc = frappe.get_doc({
        "doctype": "File",
        "file_url": f"/private/files/{output_file_name}",
        "file_name": output_file_name,
        "is_private": 1,
        "attached_to_doctype": "Generated Documents",
        "attached_to_name": frappe.session.user  # Or set to the appropriate document if necessary
    })
    file_doc.insert()
    
    # Return the URL of the generated document
    return {
        "url": file_doc.file_url
    }
