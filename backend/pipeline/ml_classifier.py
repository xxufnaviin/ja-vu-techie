import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
import pandas as pd
import numpy as np
import joblib
from typing import Dict, List, Tuple
import json
from pathlib import Path
import logging
import PyPDF2
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import pdf2image
import cv2
import re
from dataclasses import dataclass

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(_name_)

@dataclass
class PDFClassificationResult:
    document_type: str  # "structured" or "unstructured"
    confidence: float
    evidence: Dict
    processing_method: str  # How to handle this PDF

class PDFStructureClassifier:
    """
    Classifies PDFs into:
    - STRUCTURED: Digital PDFs with extractable text, created digitally
    - UNSTRUCTURED: Scanned PDFs, images, handwriting, legacy documents, forms
    """
    
    def _init_(self):
        self.logger = logging.getLogger(_name_)
        
        # Thresholds for classification
        self.text_extraction_threshold = 0.8  # Minimum ratio of extractable text
        self.image_content_threshold = 0.3    # Maximum ratio of image content for structured
        self.ocr_confidence_threshold = 85    # OCR confidence threshold
        
    def classify_pdf(self, pdf_path: str) -> PDFClassificationResult:
        """Main classification function"""
        try:
            self.logger.info(f"Classifying PDF: {pdf_path}")
            
            # Step 1: Try direct text extraction
            text_extraction_result = self._extract_text_directly(pdf_path)
            
            # Step 2: Analyze document structure
            structure_analysis = self._analyze_document_structure(pdf_path)
            
            # Step 3: Check for images/scanned content
            image_analysis = self._analyze_image_content(pdf_path)
            
            # Step 4: OCR analysis if needed
            ocr_analysis = self._perform_ocr_analysis(pdf_path)
            
            # Step 5: Make final classification
            classification = self._make_classification_decision(
                text_extraction_result,
                structure_analysis, 
                image_analysis,
                ocr_analysis
            )
            
            return classification
            
        except Exception as e:
            self.logger.error(f"Error classifying PDF {pdf_path}: {str(e)}")
            return PDFClassificationResult(
                document_type="unstructured",
                confidence=0.5,
                evidence={"error": str(e)},
                processing_method="ocr_required"
            )
    
    def _extract_text_directly(self, pdf_path: str) -> Dict:
        """Try to extract text directly from PDF (works for digital PDFs)"""
        result = {
            "extractable_text": "",
            "page_count": 0,
            "text_length": 0,
            "extraction_success": False,
            "has_fonts": False,
            "metadata": {}
        }
        
        try:
            # Method 1: Using PyMuPDF (more comprehensive)
            doc = fitz.open(pdf_path)
            result["page_count"] = len(doc)
            result["metadata"] = doc.metadata
            
            all_text = []
            font_info = []
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # Extract text
                text = page.get_text()
                all_text.append(text)
                
                # Get font information (indicates digital PDF)
                try:
                    text_dict = page.get_text("dict")
                    for block in text_dict.get("blocks", []):
                        if "lines" in block:
                            for line in block["lines"]:
                                for span in line.get("spans", []):
                                    if span.get("font"):
                                        font_info.append(span["font"])
                except:
                    pass
            
            result["extractable_text"] = "\n".join(all_text)
            result["text_length"] = len(result["extractable_text"])
            result["has_fonts"] = len(font_info) > 0
            result["extraction_success"] = result["text_length"] > 50  # Minimum meaningful text
            
            doc.close()
            
        except Exception as e:
            self.logger.warning(f"Direct text extraction failed: {str(e)}")
            
            # Fallback: Try PyPDF2
            try:
                with open(pdf_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    result["page_count"] = len(pdf_reader.pages)
                    
                    text_content = []
                    for page in pdf_reader.pages:
                        text_content.append(page.extract_text())
                    
                    result["extractable_text"] = "\n".join(text_content)
                    result["text_length"] = len(result["extractable_text"])
                    result["extraction_success"] = result["text_length"] > 50
                    
            except Exception as e2:
                self.logger.error(f"PyPDF2 extraction also failed: {str(e2)}")
        
        return result
    
    def _analyze_document_structure(self, pdf_path: str) -> Dict:
        """Analyze document structure to detect digital vs scanned characteristics"""
        result = {
            "has_vector_graphics": False,
            "has_embedded_fonts": False,
            "has_form_fields": False,
            "has_annotations": False,
            "creation_method": "unknown",
            "digital_indicators": 0
        }
        
        try:
            doc = fitz.open(pdf_path)
            
            # Check metadata for creation method
            metadata = doc.metadata
            creator = metadata.get("creator", "").lower()
            producer = metadata.get("producer", "").lower()
            
            # Digital PDF indicators in metadata
            digital_creators = [
                "microsoft", "word", "excel", "powerpoint", "libreoffice", 
                "google docs", "latex", "pdflatex", "pandoc", "reportlab",
                "wkhtmltopdf", "chrome", "firefox", "safari"
            ]
            
            scan_indicators = [
                "scanner", "scan", "xerox", "canon", "hp scan", "epson",
                "acrobat capture", "omnipage", "readiris", "finereader"
            ]
            
            for creator_name in digital_creators:
                if creator_name in creator or creator_name in producer:
                    result["digital_indicators"] += 2
                    result["creation_method"] = "digital"
                    break
            
            for scan_name in scan_indicators:
                if scan_name in creator or scan_name in producer:
                    result["digital_indicators"] -= 2
                    result["creation_method"] = "scanned"
                    break
            
            # Check each page for digital indicators
            for page_num in range(min(3, len(doc))):  # Check first 3 pages
                page = doc[page_num]
                
                try:
                    # Check for form fields
                    widgets = page.widgets()
                    if widgets:
                        result["has_form_fields"] = True
                        result["digital_indicators"] += 1
                    
                    # Check for annotations
                    annotations = page.annots()
                    if annotations:
                        result["has_annotations"] = True
                        result["digital_indicators"] += 1
                except:
                    pass
            
            doc.close()
            
        except Exception as e:
            self.logger.warning(f"Document structure analysis failed: {str(e)}")
        
        return result
    
    def _analyze_image_content(self, pdf_path: str) -> Dict:
        """Analyze how much of the PDF consists of images vs text"""
        result = {
            "total_images": 0,
            "image_coverage_ratio": 0.0,
            "has_large_images": False,
            "likely_scanned": False,
            "page_analysis": []
        }
        
        try:
            doc = fitz.open(pdf_path)
            total_area = 0
            image_area = 0
            
            for page_num in range(min(3, len(doc))):  # Analyze first 3 pages
                page = doc[page_num]
                page_rect = page.rect
                page_area = page_rect.width * page_rect.height
                total_area += page_area
                
                page_image_area = 0
                page_images = 0
                
                # Get all images on the page
                image_list = page.get_images()
                
                for img_index, img in enumerate(image_list):
                    try:
                        # Get image info
                        img_info = doc.extract_image(img[0])
                        img_width = img_info.get("width", 0)
                        img_height = img_info.get("height", 0)
                        img_area = img_width * img_height
                        
                        page_image_area += img_area
                        
                        # Check if image is large (potential scanned page)
                        if img_area > (page_area * 0.5):  # Image covers >50% of page
                            result["has_large_images"] = True
                        
                        page_images += 1
                        
                    except Exception as e:
                        self.logger.debug(f"Error analyzing image {img_index}: {str(e)}")
                
                image_area += page_image_area
                result["total_images"] += page_images
                
                page_coverage = page_image_area / page_area if page_area > 0 else 0
                result["page_analysis"].append({
                    "page": page_num + 1,
                    "image_coverage": page_coverage,
                    "image_count": page_images
                })
            
            result["image_coverage_ratio"] = image_area / total_area if total_area > 0 else 0
            
            # High image coverage suggests scanned document
            if result["image_coverage_ratio"] > 0.3 or result["has_large_images"]:
                result["likely_scanned"] = True
            
            doc.close()
            
        except Exception as e:
            self.logger.warning(f"Image content analysis failed: {str(e)}")
        
        return result
    
    def _perform_ocr_analysis(self, pdf_path: str) -> Dict:
        """Perform OCR analysis to detect scanned content"""
        result = {
            "ocr_text": "",
            "ocr_confidence": 0.0,
            "text_vs_ocr_similarity": 0.0,
            "requires_ocr": False,
            "handwriting_detected": False
        }
        
        try:
            # Convert first page to image for OCR
            images = pdf2image.convert_from_path(pdf_path, first_page=1, last_page=1, dpi=150)
            
            if images:
                image = images[0]
                
                # Perform OCR with confidence scores
                ocr_data = pytesseract.image_to_data(
                    image, 
                    output_type=pytesseract.Output.DICT,
                    config='--psm 6'
                )
                
                # Extract text and calculate average confidence
                ocr_words = []
                confidences = []
                
                for i in range(len(ocr_data['text'])):
                    word = ocr_data['text'][i].strip()
                    conf = int(ocr_data['conf'][i])
                    
                    if word and conf > 0:
                        ocr_words.append(word)
                        confidences.append(conf)
                
                result["ocr_text"] = " ".join(ocr_words)
                result["ocr_confidence"] = np.mean(confidences) if confidences else 0
                
                # Detect handwriting patterns (low OCR confidence + specific characteristics)
                if result["ocr_confidence"] < 60:
                    result["handwriting_detected"] = True
                
                # Low OCR confidence suggests need for OCR processing
                if result["ocr_confidence"] < self.ocr_confidence_threshold:
                    result["requires_ocr"] = True
                    
        except Exception as e:
            self.logger.warning(f"OCR analysis failed: {str(e)}")
            result["requires_ocr"] = True  # Assume OCR needed if analysis fails
        
        return result
    
    def _make_classification_decision(self, text_result: Dict, structure_result: Dict, 
                                   image_result: Dict, ocr_result: Dict) -> PDFClassificationResult:
        """Make final classification decision based on all analyses"""
        
        evidence = {
            "text_extraction": text_result,
            "document_structure": structure_result,
            "image_analysis": image_result,
            "ocr_analysis": ocr_result
        }
        
        # Scoring system
        structured_score = 0
        confidence_factors = []
        
        # 1. Text extraction success (strong indicator of digital PDF)
        if text_result["extraction_success"] and text_result["text_length"] > 200:
            structured_score += 40
            confidence_factors.append("Direct text extraction successful")
            
            if text_result["has_fonts"]:
                structured_score += 20
                confidence_factors.append("Embedded fonts detected")
        
        # 2. Document structure indicators
        digital_indicators = structure_result["digital_indicators"]
        structured_score += digital_indicators * 5
        
        if structure_result["creation_method"] == "digital":
            structured_score += 30
            confidence_factors.append("Digital creation method detected")
        elif structure_result["creation_method"] == "scanned":
            structured_score -= 30
            confidence_factors.append("Scanned creation method detected")
        
        # 3. Image content analysis (negative indicator for structured)
        if image_result["likely_scanned"]:
            structured_score -= 40
            confidence_factors.append("High image content suggests scanned document")
        
        if image_result["has_large_images"]:
            structured_score -= 20
            confidence_factors.append("Large images detected")
        
        # 4. OCR analysis
        if ocr_result["requires_ocr"]:
            structured_score -= 30
            confidence_factors.append("Low OCR confidence, processing required")
        
        if ocr_result["handwriting_detected"]:
            structured_score -= 50
            confidence_factors.append("Handwriting detected")
        
        # 5. Make final decision
        if structured_score >= 30:
            document_type = "structured"
            processing_method = "direct_text_extraction"
            confidence = min(0.95, 0.5 + (structured_score / 100))
        else:
            document_type = "unstructured" 
            processing_method = "ocr_required"
            confidence = min(0.95, 0.5 + abs(structured_score) / 100)
        
        return PDFClassificationResult(
            document_type=document_type,
            confidence=confidence,
            evidence=evidence,
            processing_method=processing_method
        )

class PDFFeatureExtractor:
    """Extract features from PDFs for classification training"""
    
    def _init_(self):
        self.logger = logging.getLogger(_name_)
        self.classifier = PDFStructureClassifier()
    
    def extract_features(self, pdf_path: str) -> Dict:
        """Extract comprehensive features for ML training"""
        
        # Get all analysis results
        text_result = self.classifier._extract_text_directly(pdf_path)
        structure_result = self.classifier._analyze_document_structure(pdf_path)
        image_result = self.classifier._analyze_image_content(pdf_path)
        ocr_result = self.classifier._perform_ocr_analysis(pdf_path)
        
        # Create feature vector
        features = {
            # Text extraction features
            'text_length': text_result.get('text_length', 0),
            'extraction_success': int(text_result.get('extraction_success', False)),
            'has_fonts': int(text_result.get('has_fonts', False)),
            'page_count': text_result.get('page_count', 0),
            
            # Structure features
            'has_vector_graphics': int(structure_result.get('has_vector_graphics', False)),
            'has_embedded_fonts': int(structure_result.get('has_embedded_fonts', False)),
            'has_form_fields': int(structure_result.get('has_form_fields', False)),
            'has_annotations': int(structure_result.get('has_annotations', False)),
            'digital_indicators': structure_result.get('digital_indicators', 0),
            
            # Image features
            'total_images': image_result.get('total_images', 0),
            'image_coverage_ratio': image_result.get('image_coverage_ratio', 0.0),
            'has_large_images': int(image_result.get('has_large_images', False)),
            'likely_scanned': int(image_result.get('likely_scanned', False)),
            
            # OCR features
            'ocr_confidence': ocr_result.get('ocr_confidence', 0.0),
            'requires_ocr': int(ocr_result.get('requires_ocr', True)),
            'handwriting_detected': int(ocr_result.get('handwriting_detected', False)),
            
            # Derived features
            'text_to_page_ratio': text_result.get('text_length', 0) / max(text_result.get('page_count', 1), 1),
            'images_per_page': image_result.get('total_images', 0) / max(text_result.get('page_count', 1), 1),
        }
        
        return features

def create_sample_test():
    """Create a simple test without requiring actual PDF files"""
    print("PDF Structure Classification - Simple Test")
    print("="*50)
    
    # Initialize classifier
    classifier = PDFStructureClassifier()
    
    # Mock classification result for demonstration
    mock_result = PDFClassificationResult(
        document_type="structured",
        confidence=0.87,
        evidence={
            "text_extraction": {"extraction_success": True, "text_length": 1500, "has_fonts": True},
            "document_structure": {"digital_indicators": 3, "creation_method": "digital"},
            "image_analysis": {"likely_scanned": False, "total_images": 2},
            "ocr_analysis": {"requires_ocr": False, "handwriting_detected": False}
        },
        processing_method="direct_text_extraction"
    )
    
    print(f"Sample Classification Result:")
    print(f"Document Type: {mock_result.document_type}")
    print(f"Confidence: {mock_result.confidence:.3f}")
    print(f"Processing Method: {mock_result.processing_method}")
    
    if mock_result.document_type == 'structured':
        print(f"\nRecommended Pipeline:")
        print("1. ✓ Direct text extraction")
        print("2. ✓ Medical terminology normalization")
        print("3. ✓ Lightweight NER")
        print("4. ✓ Vectorization and indexing")
    else:
        print(f"\nRecommended Pipeline:")
        print("1. ✓ OCR processing")
        print("2. ✓ Claude Vision analysis")
        print("3. ✓ Medical terminology normalization")
        print("4. ✓ Enhanced NER")
        print("5. ✓ Vectorization and indexing")
    
    return mock_result

def test_with_actual_pdf(pdf_path: str):
    """Test with an actual PDF file if available"""
    if not Path(pdf_path).exists():
        print(f"PDF file not found: {pdf_path}")
        return None
    
    print(f"\nTesting with actual PDF: {pdf_path}")
    print("-" * 40)
    
    classifier = PDFStructureClassifier()
    result = classifier.classify_pdf(pdf_path)
    
    print(f"Classification: {result.document_type}")
    print(f"Confidence: {result.confidence:.3f}")
    print(f"Processing Method: {result.processing_method}")
    
    # Show evidence summary
    evidence = result.evidence
    print(f"\nEvidence Summary:")
    
    text_info = evidence.get("text_extraction", {})
    print(f"- Text extractable: {text_info.get('extraction_success', False)}")
    print(f"- Text length: {text_info.get('text_length', 0)} characters")
    print(f"- Has fonts: {text_info.get('has_fonts', False)}")
    
    image_info = evidence.get("image_analysis", {})
    print(f"- Total images: {image_info.get('total_images', 0)}")
    print(f"- Likely scanned: {image_info.get('likely_scanned', False)}")
    
    ocr_info = evidence.get("ocr_analysis", {})
    print(f"- Requires OCR: {ocr_info.get('requires_ocr', True)}")
    print(f"- Handwriting detected: {ocr_info.get('handwriting_detected', False)}")
    
    return result

def main():
    """Main function demonstrating the classification system"""
    
    print("PDF Structure Classification Pipeline")
    print("="*50)
    
    # Run simple test first
    create_sample_test()
    
    # Test with actual PDF if available
    sample_pdfs = [
        "sample_document.pdf",
        "test.pdf", 
        "document.pdf"
    ]
    
    pdf_tested = False
    for pdf_path in sample_pdfs:
        if Path(pdf_path).exists():
            test_with_actual_pdf(pdf_path)
            pdf_tested = True
            break
    
    if not pdf_tested:
        print(f"\nNo test PDF files found.")
        print("To test with actual PDFs, place a PDF file in the current directory")
        print("and name it 'sample_document.pdf' or update the sample_pdfs list.")
    
    print(f"\nClassification completed!")
    print("This classifier is ready to be integrated into your medical document pipeline.")

if _name_ == "_main_":
    main()