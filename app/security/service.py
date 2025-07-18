"""
Security service for input validation and analysis.
"""
import logging
from typing import Dict, Any
from pathlib import Path
import tempfile
import base64

from . import SecurityAnalyzer

logger = logging.getLogger(__name__)

class SecurityService:
    """Service for security-related operations."""
    
    def __init__(self, security_level: str = "high"):
        """Initialize the security service."""
        self.security_level = security_level.lower()
        # Configure thresholds first
        self._setup_security_levels()

        # Instantiate analyzer with threshold suited to this security level
        self.analyzer = SecurityAnalyzer(threshold=self.config["threshold"])
    
    def _setup_security_levels(self) -> None:
        """Configure security parameters based on the security level."""
        self.levels = {
            "high": {"threshold": 0.9, "deep_analysis": True},
            "medium": {"threshold": 0.7, "deep_analysis": False},
            "low": {"threshold": 0.5, "deep_analysis": False},
        }
        
        if self.security_level not in self.levels:
            logger.warning(f"Unknown security level: {self.security_level}. Defaulting to 'high'.")
            self.security_level = "high"
        
        self.config = self.levels[self.security_level]
    
    def validate_text(self, text: str) -> Dict[str, Any]:
        """Validate text input for security issues."""
        try:
            if not text or not text.strip():
                return {"status": "unsafe", "reason": "empty_input", "overall_score": 0.0}
            
            analysis = self.analyzer.analyze_text(text)
            return self._process_analysis_results(analysis)
            
        except Exception as e:
            logger.error(f"Error validating text: {e}", exc_info=True)
            return {"status": "error", "reason": "validation_error", "error": str(e)}
    
    def validate_file(self, file_content: str) -> Dict[str, Any]:
        """Validate file content for security issues."""
        try:
            try:
                content = base64.b64decode(file_content)
            except Exception:
                return {"status": "unsafe", "reason": "invalid_base64", "overall_score": 0.0}
            
            # --- Early size guard (10 MB) ---
            MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
            if len(content) > MAX_FILE_SIZE:
                return {
                    "status": "unsafe",
                    "reason": "file_too_large",
                    "overall_score": 0.0,
                }
            
            # --- Determine file type (PDF or Text) ---
            is_pdf = content[:4] == b"%PDF"
            is_text = False
            if not is_pdf:
                try:
                    sample = content[:1024].decode("utf-8", errors="ignore")
                    printable_chars = sum(c.isprintable() or c.isspace() for c in sample)
                    if sample and printable_chars / len(sample) > 0.85:
                        is_text = True
                except Exception:
                    is_text = False

            if not (is_pdf or is_text):
                return {
                    "status": "error",
                    "reason": "unsupported_file_type",
                    "overall_score": 0.0,
                }
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf' if is_pdf else '.txt') as temp_file:
                temp_file.write(content)
                temp_path = temp_file.name
            
            try:
                analysis = self.analyzer.analyze_file(temp_path)
                return self._process_analysis_results(analysis)
            finally:
                Path(temp_path).unlink(missing_ok=True)
                    
        except Exception as e:
            logger.error(f"Error validating file: {e}", exc_info=True)
            return {"status": "error", "reason": "validation_error", "error": str(e)}

    def _process_analysis_results(self, analysis: Any) -> Dict[str, Any]:
        """Process the analysis results and calculate scores."""
        if isinstance(analysis, dict):
            detected_issues = analysis.get('detected_issues', [])
            confidence = analysis.get('confidence_score', 1.0)
            summary = analysis.get('analysis_summary', '')
        else:
            detected_issues = analysis.detected_issues
            confidence = analysis.confidence_score
            summary = getattr(analysis, 'analysis_summary', '')

        # Map issue types for backward compatibility
        mapped_issues = []
        for issue in detected_issues:
            if issue == 'harmful_keyword_detected':
                mapped_issues.append('toxic_language')
            else:
                mapped_issues.append(issue)

        if detected_issues:
            return {
                "status": "unsafe",
                "reason": ", ".join(detected_issues),
                "detected_issues": mapped_issues,
                "analysis_summary": summary,
                "llm_score": confidence if self.config["deep_analysis"] else 1.0,
                "rule_score": 0.0,
                "overall_score": 0.0,
            }
        
        rule_score = 1.0
        llm_score = confidence if self.config["deep_analysis"] else 1.0
        
        if self.security_level == "high":
            overall_score = (rule_score * 0.4) + (llm_score * 0.6)
        elif self.security_level == "medium":
            overall_score = (rule_score * 0.7) + (llm_score * 0.3)
        else:  # low
            overall_score = rule_score
        
        is_safe = overall_score >= self.config["threshold"]

        reason = "safe" if is_safe else "unspecified_issue"

        return {
            "status": "safe" if is_safe else "unsafe",
            "reason": reason,
            "detected_issues": [],  # Empty list for safe content
            "analysis_summary": summary,
            "llm_score": llm_score,
            "rule_score": rule_score,
            "overall_score": overall_score,
        }

# Default security service instance
security_service = SecurityService()
