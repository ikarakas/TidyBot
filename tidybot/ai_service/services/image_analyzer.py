from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from PIL import Image, ExifTags
import pytesseract
import cv2
import numpy as np
from datetime import datetime
import logging
from transformers import pipeline, BlipProcessor, BlipForConditionalGeneration
import torch
import io
import base64

logger = logging.getLogger(__name__)


class ImageAnalyzer:
    def __init__(self, use_gpu: bool = False):
        self.use_gpu = use_gpu and torch.cuda.is_available()
        self.device = "cuda" if self.use_gpu else "cpu"
        self.caption_model = None
        self.object_detector = None
        self._initialize_models()
    
    def _initialize_models(self):
        try:
            self.processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
            self.caption_model = BlipForConditionalGeneration.from_pretrained(
                "Salesforce/blip-image-captioning-base"
            ).to(self.device)
            
            self.object_detector = pipeline(
                "object-detection",
                model="facebook/detr-resnet-50",
                device=0 if self.use_gpu else -1
            )
            
            logger.info("Image analysis models initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize models: {e}")
            self.caption_model = None
            self.object_detector = None
    
    async def analyze(self, file_path: Path) -> Dict[str, Any]:
        try:
            image = Image.open(file_path)
            
            analysis_result = {
                "type": "image",
                "dimensions": image.size,
                "mode": image.mode,
                "format": image.format,
                "metadata": self._extract_metadata(image),
                "ocr_text": await self._extract_text(file_path),
                "dominant_colors": self._get_dominant_colors(image),
                "brightness": self._calculate_brightness(image),
                "sharpness": self._calculate_sharpness(file_path)
            }
            
            if self.caption_model:
                analysis_result["caption"] = self._generate_caption(image)
            
            if self.object_detector:
                analysis_result["objects"] = self._detect_objects(image)
            
            analysis_result["is_screenshot"] = self._is_screenshot(analysis_result)
            analysis_result["quality_score"] = self._calculate_quality_score(analysis_result)
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"Error analyzing image {file_path}: {e}")
            return {"error": str(e), "type": "image"}
    
    def _extract_metadata(self, image: Image.Image) -> Dict[str, Any]:
        metadata = {}
        
        if hasattr(image, '_getexif') and image._getexif():
            exif = image._getexif()
            for tag_id, value in exif.items():
                tag = ExifTags.TAGS.get(tag_id, tag_id)
                if tag in ['DateTime', 'DateTimeOriginal', 'DateTimeDigitized']:
                    try:
                        metadata[tag] = datetime.strptime(value, "%Y:%m:%d %H:%M:%S").isoformat()
                    except:
                        metadata[tag] = str(value)
                elif tag in ['Make', 'Model', 'Software', 'Artist', 'Copyright']:
                    metadata[tag] = str(value)
                elif tag == 'GPSInfo':
                    metadata['has_gps'] = True
        
        return metadata
    
    async def _extract_text(self, file_path: Path) -> str:
        try:
            image = cv2.imread(str(file_path))
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            denoised = cv2.fastNlMeansDenoising(gray)
            
            _, thresh = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            text = pytesseract.image_to_string(thresh, lang='eng')
            return text.strip()
        except Exception as e:
            logger.warning(f"OCR failed for {file_path}: {e}")
            return ""
    
    def _get_dominant_colors(self, image: Image.Image, num_colors: int = 5) -> List[str]:
        try:
            image_rgb = image.convert('RGB')
            image_small = image_rgb.resize((150, 150))
            
            pixels = np.array(image_small).reshape(-1, 3)
            
            from sklearn.cluster import KMeans
            kmeans = KMeans(n_clusters=min(num_colors, len(pixels)), random_state=42)
            kmeans.fit(pixels)
            
            colors = kmeans.cluster_centers_.astype(int)
            hex_colors = ['#{:02x}{:02x}{:02x}'.format(r, g, b) for r, g, b in colors]
            
            return hex_colors
        except Exception as e:
            logger.warning(f"Color extraction failed: {e}")
            return []
    
    def _calculate_brightness(self, image: Image.Image) -> float:
        try:
            grayscale = image.convert('L')
            pixels = np.array(grayscale)
            return float(np.mean(pixels) / 255.0)
        except:
            return 0.5
    
    def _calculate_sharpness(self, file_path: Path) -> float:
        try:
            image = cv2.imread(str(file_path), cv2.IMREAD_GRAYSCALE)
            laplacian_var = cv2.Laplacian(image, cv2.CV_64F).var()
            return min(1.0, laplacian_var / 500.0)
        except:
            return 0.5
    
    def _generate_caption(self, image: Image.Image) -> str:
        try:
            inputs = self.processor(image, return_tensors="pt").to(self.device)
            out = self.caption_model.generate(**inputs, max_length=50)
            caption = self.processor.decode(out[0], skip_special_tokens=True)
            return caption
        except Exception as e:
            logger.warning(f"Caption generation failed: {e}")
            return ""
    
    def _detect_objects(self, image: Image.Image) -> List[Dict[str, Any]]:
        try:
            results = self.object_detector(image)
            
            objects = []
            for item in results:
                if item['score'] > 0.5:
                    objects.append({
                        'label': item['label'],
                        'confidence': float(item['score']),
                        'box': item['box']
                    })
            
            return objects
        except Exception as e:
            logger.warning(f"Object detection failed: {e}")
            return []
    
    def _is_screenshot(self, analysis: Dict[str, Any]) -> bool:
        indicators = 0
        
        if analysis.get('ocr_text'):
            text = analysis['ocr_text'].lower()
            screenshot_keywords = ['screenshot', 'screen capture', 'snip', 'window', 'desktop']
            if any(keyword in text for keyword in screenshot_keywords):
                indicators += 1
        
        if not analysis.get('metadata', {}).get('Make'):
            indicators += 1
        
        dimensions = analysis.get('dimensions', (0, 0))
        common_resolutions = [
            (1920, 1080), (1366, 768), (1440, 900), (1680, 1050),
            (2560, 1440), (3840, 2160), (1280, 720), (1024, 768)
        ]
        if dimensions in common_resolutions:
            indicators += 1
        
        return indicators >= 2
    
    def _calculate_quality_score(self, analysis: Dict[str, Any]) -> float:
        score = 0.5
        
        if analysis.get('sharpness', 0) > 0.7:
            score += 0.2
        elif analysis.get('sharpness', 0) < 0.3:
            score -= 0.2
        
        brightness = analysis.get('brightness', 0.5)
        if 0.3 <= brightness <= 0.7:
            score += 0.1
        else:
            score -= 0.1
        
        dimensions = analysis.get('dimensions', (0, 0))
        if dimensions[0] * dimensions[1] > 1000000:
            score += 0.1
        
        if analysis.get('metadata', {}).get('Make'):
            score += 0.1
        
        return max(0.0, min(1.0, score))