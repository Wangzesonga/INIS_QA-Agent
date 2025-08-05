#!/usr/bin/env python3
"""
Auto Correction Processor
========================

Processes QA reports and applies automatic corrections to records where possible.
Saves corrected records to dated folders for review and potential upload.

Author: Brian Bales (enhanced by Claude)
"""

import os
import json
import logging
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote
import re

logger = logging.getLogger(__name__)

class AutoCorrectionProcessor:
    def __init__(self, invenio_url: str, output_dir: str, azure_config: Optional[Dict] = None):
        """
        Initialize the auto-correction processor.
        
        Args:
            invenio_url: Base URL of the Invenio system
            output_dir: Directory to save corrected records
            azure_config: Azure OpenAI configuration (for future enhancements)
        """
        self.invenio_url = invenio_url
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.azure_config = azure_config or {}
        
        # Statistics
        self.stats = {
            "records_processed": 0,
            "records_corrected": 0,
            "title_corrections": 0,
            "affiliation_corrections": 0,
            "abstract_corrections": 0, 
            "descriptor_corrections": 0,
            "date_corrections": 0,
            "errors": 0
        }
        
    def curl_json(self, url: str) -> Dict:
        """Fetch JSON data from URL using curl."""
        try:
            proc = subprocess.run(
                ["curl", "-sS", "--fail", "-H", "Accept: application/json", url],
                capture_output=True,
                text=True,
                check=True,
            )
            return json.loads(proc.stdout)
        except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
            logger.error(f"Error fetching data from {url}: {e}")
            return {}
            
    def fetch_record(self, record_id: str) -> Optional[Dict]:
        """Fetch a record from the Invenio system."""
        url = f"{self.invenio_url}/api/records/{record_id}"
        record_data = self.curl_json(url)
        
        if not record_data:
            logger.error(f"Could not fetch record {record_id}")
            return None
            
        return record_data
        
    def apply_title_correction(self, record: Dict, correction: str) -> bool:
        """Apply title correction to record."""
        try:
            if "metadata" not in record:
                record["metadata"] = {}
                
            old_title = record["metadata"].get("title", "")
            record["metadata"]["title"] = correction
            
            logger.info(f"Title correction applied: '{old_title}' -> '{correction}'")
            return True
            
        except Exception as e:
            logger.error(f"Error applying title correction: {e}")
            return False
            
    def apply_abstract_correction(self, record: Dict, correction: str) -> bool:
        """Apply abstract correction to record."""
        try:
            if "metadata" not in record:
                record["metadata"] = {}
                
            # Add or update the description field
            old_description = record["metadata"].get("description", "")
            record["metadata"]["description"] = correction
            
            logger.info(f"Abstract correction applied: '{old_description[:50]}...' -> '{correction[:50]}...'")
            return True
            
        except Exception as e:
            logger.error(f"Error applying abstract correction: {e}")
            return False
            
    def apply_affiliation_corrections(self, record: Dict, corrections: List[Dict]) -> bool:
        """Apply affiliation corrections to record."""
        try:
            metadata = record.get("metadata", {})
            creators = metadata.get("creators", [])
            
            corrections_applied = 0
            
            for correction in corrections:
                old_affiliation = correction.get("old_affiliation", "")
                new_affiliation = correction.get("recommended_affiliation", "")
                
                if not old_affiliation or not new_affiliation:
                    continue
                    
                # Find and update matching affiliations
                for creator in creators:
                    affiliations = creator.get("affiliations", [])
                    for i, affiliation in enumerate(affiliations):
                        if affiliation.get("name", "") == old_affiliation:
                            affiliations[i]["name"] = new_affiliation
                            corrections_applied += 1
                            logger.info(f"Affiliation corrected: '{old_affiliation}' -> '{new_affiliation}'")
                            
            return corrections_applied > 0
            
        except Exception as e:
            logger.error(f"Error applying affiliation corrections: {e}")
            return False
            
    def apply_descriptor_deletions(self, record: Dict, deletions: List[str]) -> bool:
        """Remove specified descriptors from record."""
        try:
            custom_fields = record.get("custom_fields", {})
            descriptors = custom_fields.get("iaea:descriptors_cai_text", [])
            
            if not descriptors:
                return False
                
            original_count = len(descriptors)
            
            # Remove specified descriptors (case-insensitive)
            deletions_lower = [d.lower() for d in deletions]
            descriptors[:] = [d for d in descriptors if d.lower() not in deletions_lower]
            
            removed_count = original_count - len(descriptors)
            
            if removed_count > 0:
                logger.info(f"Removed {removed_count} descriptors: {deletions}")
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Error applying descriptor deletions: {e}")
            return False
            
    def apply_date_correction(self, record: Dict, correction: str) -> bool:
        """Apply publication date correction to record."""
        try:
            if "metadata" not in record:
                record["metadata"] = {}
                
            old_date = record["metadata"].get("publication_date", "")
            record["metadata"]["publication_date"] = correction
            
            logger.info(f"Date correction applied: '{old_date}' -> '{correction}'")
            return True
            
        except Exception as e:
            logger.error(f"Error applying date correction: {e}")
            return False
            
    def add_related_identifier(self, record: Dict, identifier_data: Dict) -> bool:
        """Add a related identifier (e.g., DOI) to the record."""
        try:
            metadata = record.get("metadata", {})
            if "related_identifiers" not in metadata:
                metadata["related_identifiers"] = []
                
            # Check if identifier already exists
            existing_identifiers = [
                ri.get("identifier", "") for ri in metadata["related_identifiers"]
            ]
            
            new_identifier = identifier_data.get("identifier", "")
            if new_identifier and new_identifier not in existing_identifiers:
                metadata["related_identifiers"].append(identifier_data)
                logger.info(f"Added related identifier: {new_identifier}")
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Error adding related identifier: {e}")
            return False
            
    def process_qa_report(self, report_path: Path) -> Optional[Dict]:
        """Process a single QA report and apply corrections."""
        try:
            # Load QA report
            with open(report_path, 'r', encoding='utf-8') as f:
                qa_data = json.load(f)
                
            record_id = qa_data.get("record_id")
            if not record_id:
                logger.error(f"No record_id found in {report_path}")
                return None
                
            # Fetch the original record
            original_record = self.fetch_record(record_id)
            if not original_record:
                logger.error(f"Could not fetch record {record_id}")
                return None
                
            # Create a copy for corrections
            corrected_record = json.loads(json.dumps(original_record))
            corrections_applied = 0
            
            # Apply corrections
            corrections = qa_data.get("corrections", {})
            
            # Title correction
            if qa_data.get("title_corrected") and "title" in corrections:
                if self.apply_title_correction(corrected_record, corrections["title"]):
                    corrections_applied += 1
                    self.stats["title_corrections"] += 1
                    
            # Abstract correction
            if qa_data.get("abstract_corrected") and "abstract" in corrections:
                if self.apply_abstract_correction(corrected_record, corrections["abstract"]):
                    corrections_applied += 1
                    self.stats["abstract_corrections"] += 1
                    
            # Affiliation corrections
            if qa_data.get("affiliation_correction_recommended"):
                affiliation_corrections = qa_data.get("affiliation_corrections", [])
                if affiliation_corrections and self.apply_affiliation_corrections(corrected_record, affiliation_corrections):
                    corrections_applied += 1
                    self.stats["affiliation_corrections"] += 1
                    
            # Descriptor deletions
            if qa_data.get("descriptor_corrected") and "delete_descriptor" in corrections:
                deletions = corrections["delete_descriptor"]
                if isinstance(deletions, str):
                    deletions = [deletions]
                if deletions and self.apply_descriptor_deletions(corrected_record, deletions):
                    corrections_applied += 1
                    self.stats["descriptor_corrections"] += 1
                    
            # Date correction
            if qa_data.get("date_corrected") and "publication_date" in corrections:
                if self.apply_date_correction(corrected_record, corrections["publication_date"]):
                    corrections_applied += 1
                    self.stats["date_corrections"] += 1
                    
            # Related identifiers
            if "related_identifiers" in corrections:
                identifiers = corrections["related_identifiers"]
                if not isinstance(identifiers, list):
                    identifiers = [identifiers]
                for identifier in identifiers:
                    if self.add_related_identifier(corrected_record, identifier):
                        corrections_applied += 1
                        
            # Save corrected record if any corrections were applied
            if corrections_applied > 0:
                output_file = self.output_dir / f"{record_id}_corrected.json"
                
                # Create correction metadata
                correction_metadata = {
                    "original_record_id": record_id,
                    "correction_date": datetime.now().isoformat(),
                    "corrections_applied": corrections_applied,
                    "qa_report_source": str(report_path),
                    "corrections_summary": corrections
                }
                
                # Save both the corrected record and metadata
                corrected_data = {
                    "corrected_record": corrected_record,
                    "correction_metadata": correction_metadata,
                    "original_record": original_record
                }
                
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(corrected_data, f, indent=2, ensure_ascii=False)
                    
                logger.info(f"Saved corrected record: {output_file}")
                self.stats["records_corrected"] += 1
                
                return corrected_data
                
            else:
                logger.info(f"No automatic corrections applied for record {record_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error processing QA report {report_path}: {e}")
            self.stats["errors"] += 1
            return None
            
    def process_qa_reports(self, report_files: List[Path]) -> int:
        """Process multiple QA reports and apply corrections."""
        logger.info(f"Processing {len(report_files)} QA reports")
        
        corrections_applied = 0
        
        for report_file in report_files:
            self.stats["records_processed"] += 1
            
            try:
                result = self.process_qa_report(report_file)
                if result:
                    corrections_applied += 1
                    
            except Exception as e:
                logger.error(f"Error processing {report_file}: {e}")
                self.stats["errors"] += 1
                
        # Save processing statistics
        stats_file = self.output_dir / "correction_statistics.json"
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump({
                "processing_date": datetime.now().isoformat(),
                "statistics": self.stats,
                "processed_files": [str(f) for f in report_files]
            }, f, indent=2)
            
        logger.info(f"Processing complete. Statistics: {self.stats}")
        return corrections_applied
        
    def create_upload_package(self) -> Optional[Path]:
        """Create a package of corrected records ready for upload."""
        try:
            # Find all corrected record files
            corrected_files = list(self.output_dir.glob("*_corrected.json"))
            
            if not corrected_files:
                logger.info("No corrected records found to package")
                return None
                
            # Create upload package directory
            package_dir = self.output_dir / "upload_package"
            package_dir.mkdir(exist_ok=True)
            
            # Extract just the corrected records for upload
            for corrected_file in corrected_files:
                with open(corrected_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                record_id = data["correction_metadata"]["original_record_id"]
                corrected_record = data["corrected_record"]
                
                # Save just the corrected record data
                upload_file = package_dir / f"{record_id}.json"
                with open(upload_file, 'w', encoding='utf-8') as f:
                    json.dump(corrected_record, f, indent=2, ensure_ascii=False)
                    
            # Create summary file
            summary = {
                "package_created": datetime.now().isoformat(),
                "total_records": len(corrected_files),
                "records": [f.stem.replace("_corrected", "") for f in corrected_files],
                "statistics": self.stats
            }
            
            summary_file = package_dir / "upload_summary.json"
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2)
                
            logger.info(f"Upload package created: {package_dir}")
            return package_dir
            
        except Exception as e:
            logger.error(f"Error creating upload package: {e}")
            return None

def main():
    """Main entry point for standalone usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description="INIS Auto-Correction Processor")
    parser.add_argument("qa_reports_dir", help="Directory containing QA report JSON files")
    parser.add_argument("--output-dir", default="./corrected_records", help="Output directory for corrected records")
    parser.add_argument("--invenio-url", default="https://inis.iaea.org", help="Invenio base URL")
    parser.add_argument("--create-package", action="store_true", help="Create upload package after processing")
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # Initialize processor
        processor = AutoCorrectionProcessor(args.invenio_url, args.output_dir)
        
        # Find QA report files
        qa_reports_dir = Path(args.qa_reports_dir)
        if not qa_reports_dir.exists():
            logger.error(f"QA reports directory does not exist: {qa_reports_dir}")
            return 1
            
        report_files = list(qa_reports_dir.glob("*-report.json"))
        if not report_files:
            logger.warning(f"No QA report files found in {qa_reports_dir}")
            return 0
            
        # Process reports
        corrections_applied = processor.process_qa_reports(report_files)
        
        # Create upload package if requested
        if args.create_package and corrections_applied > 0:
            package_dir = processor.create_upload_package()
            if package_dir:
                print(f"Upload package created: {package_dir}")
                
        print(f"Processing complete. {corrections_applied} records corrected.")
        return 0
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1

if __name__ == "__main__":
    exit(main())