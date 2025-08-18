#!/usr/bin/env python3
"""
Auto Correction Applier
=======================

Applies corrections directly to INIS production system based on QA reports.
This script reads QA reports and applies trusted corrections including:
- Title corrections
- Affiliation corrections  
- Organizational author corrections

Usage:
    python auto_correction_applier.py [--apply] [--token TOKEN] [--qa-folder FOLDER]
    
    --apply: Apply changes to production (default is dry-run mode)
    --token: INIS API access token (or set ACCESS_TOKEN env var)
    --qa-folder: Folder containing QA report JSON files
"""

import os
import sys
import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Optional
import argparse

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

class INISCorrectionApplier:
    def __init__(self, access_token: str, base_url: str = "https://inis.iaea.org/api/records", dry_run: bool = True):
        """
        Initialize the INIS correction applier.
        
        Args:
            access_token: INIS API access token
            base_url: INIS API base URL
            dry_run: If True, only simulate changes without applying them
        """
        self.access_token = access_token
        self.base_url = base_url
        self.dry_run = dry_run
        
        self.stats = {
            "records_processed": 0,
            "records_updated": 0,
            "records_qa_checked_only": 0,
            "title_corrections": 0,
            "affiliation_corrections": 0,
            "organizational_author_corrections": 0,
            "errors": 0
        }
        
        print("** DRY RUN MODE **" if dry_run else "** APPLYING CHANGES **", flush=True)
        logger.info("** DRY RUN MODE **" if dry_run else "** APPLYING CHANGES **")
        
    def curl_get(self, url: str) -> Dict:
        """Make GET request using curl with authorization."""
        try:
            cmd = ['curl', '-s', '-H', f'Authorization: Bearer {self.access_token}', url]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            if result.returncode != 0:
                logger.error(f"GET request failed: {result.stderr}")
                return {}
                
            return json.loads(result.stdout)
        except Exception as e:
            logger.error(f"Error in GET request to {url}: {e}")
            return {}
    
    def curl_post(self, url: str) -> Dict:
        """Make POST request using curl with authorization."""
        try:
            cmd = ['curl', '-s', '-X', 'POST', '-H', f'Authorization: Bearer {self.access_token}', url]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            if result.returncode != 0:
                logger.error(f"POST request failed: {result.stderr}")
                return {}
                
            return json.loads(result.stdout)
        except Exception as e:
            logger.error(f"Error in POST request to {url}: {e}")
            return {}
    
    def curl_put(self, url: str, payload: Dict) -> str:
        """Make PUT request using curl with authorization and JSON payload."""
        try:
            cmd = [
                'curl', '-s', '-X', 'PUT',
                '-H', f'Authorization: Bearer {self.access_token}',
                '-H', 'Content-Type: application/json',
                '--data-binary', json.dumps(payload),
                url
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            if result.returncode != 0:
                logger.error(f"PUT request failed: {result.stderr}")
                
            return result.stdout
        except Exception as e:
            logger.error(f"Error in PUT request to {url}: {e}")
            return ""
    
    def apply_title_correction(self, record_data: Dict, new_title: str) -> bool:
        """Apply title correction to record data."""
        try:
            if "metadata" not in record_data:
                record_data["metadata"] = {}
            
            old_title = record_data["metadata"].get("title", "")
            record_data["metadata"]["title"] = new_title
            logger.info(f"✏️  Updated title: '{old_title}' -> '{new_title}'")
            return True
        except Exception as e:
            logger.error(f"Error applying title correction: {e}")
            return False
    
    def apply_affiliation_corrections(self, record_data: Dict, corrections: List[Dict]) -> bool:
        """Apply affiliation corrections to record data."""
        try:
            applied_count = 0
            creators = record_data.get("metadata", {}).get("creators", [])
            
            for creator in creators:
                affiliations = creator.get("affiliations", [])
                for affiliation in affiliations:
                    current_name = affiliation.get("name", "")
                    
                    # Check if this affiliation needs correction
                    for correction in corrections:
                        old_aff = correction.get("old_affiliation", "")
                        new_aff = correction.get("recommended_affiliation", "")
                        
                        if current_name == old_aff and new_aff:
                            affiliation["name"] = new_aff
                            logger.info(f"🏷️  Updated affiliation: '{old_aff}' -> '{new_aff}'")
                            applied_count += 1
                            
            return applied_count > 0
        except Exception as e:
            logger.error(f"Error applying affiliation corrections: {e}")
            return False
    
    def apply_organizational_author_corrections(self, record_data: Dict, corrections: List[Dict]) -> bool:
        """Apply organizational author corrections to record data."""
        try:
            applied_count = 0
            creators = record_data.get("metadata", {}).get("creators", [])
            
            for creator in creators:
                person_org = creator.get("person_or_org", {})
                if person_org.get("type") == "organizational":
                    current_name = person_org.get("name", "")
                    
                    # Check if this organizational author needs correction
                    for correction in corrections:
                        old_org = correction.get("old_organizational_author", "")
                        new_org = correction.get("recommended_organizational_author", "")
                        
                        if current_name == old_org and new_org:
                            person_org["name"] = new_org
                            logger.info(f"🏢 Updated org author: '{old_org}' -> '{new_org}'")
                            applied_count += 1
                            
            return applied_count > 0
        except Exception as e:
            logger.error(f"Error applying organizational author corrections: {e}")
            return False
    
    def mark_qa_checked(self, record_data: Dict):
        """Mark record as QA checked."""
        if "custom_fields" not in record_data:
            record_data["custom_fields"] = {}
        record_data["custom_fields"]["iaea:qa_checked"] = True
    
    def mark_record_as_qa_checked_only(self, record_id: str) -> bool:
        """Mark a record as QA checked without applying any other corrections."""
        try:
            logger.info(f"\nMarking {record_id} as QA checked...")
            self.stats["records_processed"] += 1
            
            # Create draft
            draft_url = f"{self.base_url}/{record_id}/draft"
            draft_resp = self.curl_post(draft_url)
            
            if 'id' not in draft_resp:
                logger.error(f"❌ Failed to create draft for {record_id}: {draft_resp}")
                self.stats["errors"] += 1
                return False
            
            # Get full draft data
            full_draft = self.curl_get(draft_url)
            if not full_draft:
                logger.error(f"❌ Failed to get draft data for {record_id}")
                self.stats["errors"] += 1
                return False
            
            # Mark as QA checked
            self.mark_qa_checked(full_draft)
            
            # Apply changes if not in dry-run mode
            if not self.dry_run:
                # Update draft
                put_resp = self.curl_put(draft_url, full_draft)
                
                # Publish draft
                publish_url = f"{draft_url}/actions/publish"
                pub_resp = self.curl_post(publish_url)
                
                if pub_resp and "id" in pub_resp:
                    logger.info(f"✅ Marked {record_id} as QA checked")
                    self.stats["records_updated"] += 1
                    self.stats["records_qa_checked_only"] += 1
                    return True
                else:
                    logger.error(f"❌ Failed to publish {record_id}: {pub_resp}")
                    self.stats["errors"] += 1
                    return False
            else:
                logger.info(f"Dry-run: Would mark {record_id} as QA checked")
                self.stats["records_updated"] += 1
                self.stats["records_qa_checked_only"] += 1
                return True
                
        except Exception as e:
            logger.error(f"Error marking record {record_id} as QA checked: {e}")
            self.stats["errors"] += 1
            return False
    
    def update_record(self, record_id: str, corrections_data: Dict) -> bool:
        """Update a single record with corrections."""
        try:
            logger.info(f"\nProcessing {record_id}...")
            self.stats["records_processed"] += 1
            
            # Create draft
            draft_url = f"{self.base_url}/{record_id}/draft"
            draft_resp = self.curl_post(draft_url)
            
            if 'id' not in draft_resp:
                logger.error(f"❌ Failed to create draft for {record_id}: {draft_resp}")
                self.stats["errors"] += 1
                return False
            
            # Get full draft data
            full_draft = self.curl_get(draft_url)
            if not full_draft:
                logger.error(f"❌ Failed to get draft data for {record_id}")
                self.stats["errors"] += 1
                return False
            
            corrections_applied = 0
            
            # Apply title correction
            if "title" in corrections_data.get("corrections", {}):
                new_title = corrections_data["corrections"]["title"]
                if self.apply_title_correction(full_draft, new_title):
                    corrections_applied += 1
                    self.stats["title_corrections"] += 1
            
            # Apply affiliation corrections
            aff_corrections = corrections_data.get("affiliation_corrections", [])
            if aff_corrections and self.apply_affiliation_corrections(full_draft, aff_corrections):
                corrections_applied += 1
                self.stats["affiliation_corrections"] += 1
            
            # Apply organizational author corrections
            org_corrections = corrections_data.get("organizational_author_corrections", [])
            if org_corrections and self.apply_organizational_author_corrections(full_draft, org_corrections):
                corrections_applied += 1
                self.stats["organizational_author_corrections"] += 1
            
            # Mark as QA checked
            self.mark_qa_checked(full_draft)
            
            if corrections_applied == 0:
                logger.info(f"No corrections applied for {record_id}, but marking as QA checked")
            
            # Apply changes if not in dry-run mode
            if not self.dry_run:
                # Update draft
                put_resp = self.curl_put(draft_url, full_draft)
                
                # Publish draft
                publish_url = f"{draft_url}/actions/publish"
                pub_resp = self.curl_post(publish_url)
                
                if pub_resp and "id" in pub_resp:
                    logger.info(f"✅ Published {record_id}")
                    self.stats["records_updated"] += 1
                    return True
                else:
                    logger.error(f"❌ Failed to publish {record_id}: {pub_resp}")
                    self.stats["errors"] += 1
                    return False
            else:
                logger.info(f"Dry-run: Changes not applied for {record_id}")
                self.stats["records_updated"] += 1
                return True
                
        except Exception as e:
            logger.error(f"Error updating record {record_id}: {e}")
            self.stats["errors"] += 1
            return False
    
    def process_qa_folder(self, qa_folder: Path) -> bool:
        """Process all QA reports in the specified folder."""
        try:
            if not qa_folder.exists():
                logger.error(f"QA folder does not exist: {qa_folder}")
                return False
            
            json_files = list(qa_folder.glob("*.json"))
            if not json_files:
                logger.warning(f"No JSON files found in {qa_folder}")
                return False
            
            logger.info(f"Processing {len(json_files)} QA report files")
            
            for json_file in json_files:
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        report_data = json.load(f)
                    
                    record_id = report_data.get("record_id")
                    if not record_id:
                        logger.warning(f"⚠️ No record_id in {json_file.name}")
                        continue
                    
                    # Check if this report has any corrections that should be applied
                    has_applicable_corrections = (
                        "title" in report_data.get("corrections", {}) or
                        report_data.get("affiliation_corrections") or
                        report_data.get("organizational_author_corrections")
                    )
                    
                    if has_applicable_corrections:
                        self.update_record(record_id, report_data)
                    else:
                        # Even if no corrections needed, still mark as QA checked
                        logger.info(f"No corrections needed for {record_id}, but marking as QA checked")
                        self.mark_record_as_qa_checked_only(record_id)
                        
                except json.JSONDecodeError:
                    logger.error(f"⚠️ Invalid JSON in {json_file.name}")
                    self.stats["errors"] += 1
                except Exception as e:
                    logger.error(f"Error processing {json_file.name}: {e}")
                    self.stats["errors"] += 1
            
            # Print final statistics
            logger.info("\n" + "="*50)
            logger.info("FINAL STATISTICS")
            logger.info("="*50)
            for key, value in self.stats.items():
                logger.info(f"{key}: {value}")
            logger.info("="*50)
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing QA folder: {e}")
            return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Apply corrections to INIS records based on QA reports",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run (default)
  python auto_correction_applier.py --qa-folder /path/to/qa/reports
  
  # Apply changes to production
  python auto_correction_applier.py --apply --qa-folder /path/to/qa/reports
  
  # Use custom token and folder
  python auto_correction_applier.py --apply --token YOUR_TOKEN --qa-folder /path/to/qa
        """
    )
    
    parser.add_argument(
        "--apply", 
        action="store_true", 
        help="Apply changes to production (default is dry-run mode)"
    )
    
    parser.add_argument(
        "--token",
        default=os.getenv("ACCESS_TOKEN"),
        help="INIS API access token (default from ACCESS_TOKEN env var)"
    )
    
    parser.add_argument(
        "--qa-folder",
        default=os.getenv("QA_FOLDER", "./QA"),
        help="Folder containing QA report JSON files (default: ./QA)"
    )
    
    parser.add_argument(
        "--base-url",
        default="https://inis.iaea.org/api/records",
        help="INIS API base URL"
    )
    
    args = parser.parse_args()
    
    # Validate token
    if not args.token:
        logger.error("No access token provided. Use --token or set ACCESS_TOKEN environment variable.")
        return 1
    
    # Initialize applier
    dry_run = not args.apply
    applier = INISCorrectionApplier(
        access_token=args.token,
        base_url=args.base_url,
        dry_run=dry_run
    )
    
    # Process QA folder
    qa_folder = Path(args.qa_folder)
    success = applier.process_qa_folder(qa_folder)
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
