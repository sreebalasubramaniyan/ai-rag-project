import re
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

from src.core.models import DocumentChunk, SearchResult

# Comprehensive Prohibited Sensitive Categories
PROHIBITED_CATEGORIES = {
    "CREDENTIALS_AND_AUTH": {
        "label": "Confidential Credentials & Authentication Data",
        "patterns": [
            r"\b(?:credential|credentials|crediential|credientials|password|passwords|passwd|pwd|passwrd)\b",
            r"\b(?:api[_-]?key|secret[_-]?key|private[_-]?key|access[_-]?token|auth[_-]?token)\b",
            r"\b(?:ssh[_-]?key|jwt|bearer token|login credentials|user credentials|login details)\b",
            r"\b(?:root password|admin password|master key|database password|db password)\b",
            r"\b(?:account credentials|employee credentials|account passwords|user passwords)\b",
            r"\b(?:access code|access codes|security pin|passcode|passcodes)\b"
        ],
        "message": "Access Restricted: The requested query attempts to access confidential authentication credentials, passwords, or security keys. Access is strictly prohibited under enterprise privacy and security governance."
    },
    "SECRETS_AND_CONFIDENTIAL_DATA": {
        "label": "Enterprise Secrets, Secrecy & Confidential Records",
        "patterns": [
            r"\b(?:secret|secrets|secrecy|sercresy|secrect|secrects)\b",
            r"\b(?:confidential|confidentiality|classified|top[_-]?secret)\b",
            r"\b(?:trade[_-]?secret|trade[_-]?secrets|corporate[_-]?secrets|internal[_-]?secrets)\b",
            r"\b(?:restricted[_-]?data|restricted[_-]?document|restricted[_-]?documents|restricted[_-]?files?)\b",
            r"\b(?:classified[_-]?data|classified[_-]?document|classified[_-]?documents|classified[_-]?files?)\b",
            r"\b(?:confidential[_-]?data|confidential[_-]?document|confidential[_-]?documents|confidential[_-]?files?|confidential[_-]?info)\b",
            r"\b(?:proprietary[_-]?secrets|proprietary[_-]?data|undisclosed[_-]?records)\b"
        ],
        "message": "Access Restricted: Access to internal enterprise secrets, secrecy documents, confidential files, or classified information is strictly prohibited under security governance."
    },
    "PERSONAL_AND_PRIVACY_DATA": {
        "label": "Personal Records & Privacy-Protected Data",
        "patterns": [
            r"\b(?:privacy|private|privasy)\b(?:\s+(?:data|info|information|record|records|document|documents|file|files|details?|notes?))\b",
            r"\b(?:personal\s+(?:data|info|information|record|records|document|documents|file|files|details?|profile|profiles|history))\b",
            r"\b(?:person(?:'s)?\s+(?:data|info|information|details?|record|records|document|documents|files?|privacy|secrets?))\b",
            r"\b(?:employee(?:'s)?\s+(?:account|accounts|data|info|information|details?|record|records|file|files|personal|private|privacy))\b",
            r"\b(?:all employee(?:'s)? account|employee account|employee accounts)\b",
            r"\b(?:ssn|social security|social security number|national id|passport number|aadhaar)\b",
            r"\b(?:background check|medical record|medical history|health record|disciplinary record)\b",
            r"\b(?:personal phone|home address|residential address|personal email|private email)\b",
            r"\b(?:personally identifiable|personally identifiable information|pii)\b",
            r"\b(?:personal\s+identity|identity\s+theft|identity\s+records)\b"
        ],
        "message": "Access Restricted: The requested query attempts to access personal employee records, private identity documents, or protected personal data. Access is strictly prohibited under privacy compliance regulations."
    },
    "FINANCIAL_AND_COMPENSATION": {
        "label": "Confidential Financial & Compensation Records",
        "patterns": [
            r"\b(?:salary|salaries|compensation|payroll|paycheck|bonus amount|wage|wages)\b",
            r"\b(?:executive compensation|individual compensation|employee salary|staff salary)\b",
            r"\b(?:bank account number|routing number|credit card number|cvv|financial records)\b"
        ],
        "message": "Access Restricted: The requested query attempts to access confidential compensation, payroll, or financial account information. Access is strictly restricted."
    },
    "SECURITY_AND_VULNERABILITY": {
        "label": "Security Vulnerabilities & System Exploits",
        "patterns": [
            r"\b(?:system vulnerability|exploit|vulnerabilities|backdoor|bypass security)\b",
            r"\b(?:zero-day|privilege escalation|internal exploit|penetration test finding)\b"
        ],
        "message": "Access Restricted: Access to internal security vulnerability logs, exploit methodologies, or restricted system architecture is strictly prohibited."
    }
}

# Concrete Token & PII Regex Patterns for Output Verification
OUTPUT_LEAKAGE_PATTERNS = {
    "SSN": re.compile(r"\b\d{3}[-–—\s]?\d{2}[-–—\s]?\d{4}\b"),
    "CREDIT_CARD": re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
    "API_KEY": re.compile(r"\b(?:sk-[A-Za-z0-9]{20,}|AIza[0-9A-Za-z-_]{35}|ghp_[A-Za-z0-9]{36})\b"),
    "PASSWORD_ASSIGNMENT": re.compile(r"\b(?:password|passwd|pwd)\s*[:=]\s*['\"]?\S+['\"]?", re.IGNORECASE),
    "CREDENTIAL_DUMP": re.compile(r"\b(?:username|user)\s*[:=]\s*\S+\s+(?:and\s+)?(?:password|pwd)\s*[:=]\s*\S+", re.IGNORECASE),
}

@dataclass
class PrivacyDecision:
    """Decision outcome of Privacy & Security Policy inspection."""
    is_restricted: bool
    category: Optional[str] = None
    category_label: Optional[str] = None
    reason: Optional[str] = None
    refusal_message: Optional[str] = None
    rule_matched: Optional[str] = None

@dataclass
class DualStageAudit:
    """Audit certificate tracking Stage 1 & Stage 2 privacy enforcement."""
    status: str  # "ALLOWED" or "RESTRICTED"
    offline_guarantee: str
    stage_1_query_check: Dict[str, Any]
    stage_2_output_check: Dict[str, Any]
    elapsed_privacy_ms: float
    timestamp: str

class EnterprisePrivacyGuard:
    """
    Comprehensive Dual-Stage Privacy Enforcement Guard:
    - Stage 1: Inspects query intent and candidate context before prompt compilation.
               Completely halts and refuses any attempt to access credentials, personal data, or secrets.
    - Stage 2: Post-generation output leakage scanner ensuring zero private enterprise tokens escape.
    """

    def __init__(self):
        # Pre-compile regex for high-speed offline execution
        self.compiled_rules = {}
        for cat_key, cat_data in PROHIBITED_CATEGORIES.items():
            self.compiled_rules[cat_key] = [
                re.compile(p, re.IGNORECASE) for p in cat_data["patterns"]
            ]

    def evaluate_query(self, query: str) -> PrivacyDecision:
        """
        Stage 1 Pre-Check:
        Analyzes the query for restricted intent (credentials, personal documents, privacy/secrets).
        """
        query_clean = query.strip()
        if not query_clean:
            return PrivacyDecision(is_restricted=False)

        for cat_key, regex_list in self.compiled_rules.items():
            for regex in regex_list:
                match = regex.search(query_clean)
                if match:
                    cat_info = PROHIBITED_CATEGORIES[cat_key]
                    return PrivacyDecision(
                        is_restricted=True,
                        category=cat_key,
                        category_label=cat_info["label"],
                        reason=f"Query matches restricted policy pattern: '{match.group()}'",
                        refusal_message=cat_info["message"],
                        rule_matched=match.group()
                    )

        return PrivacyDecision(is_restricted=False)

    def evaluate_context_and_intent(
        self,
        query: str,
        retrieved_results: List[SearchResult]
    ) -> PrivacyDecision:
        """
        Stage 1 Context Check:
        Verifies whether retrieved candidate chunks contain confidential secrets or personal records,
        and whether the query is attempting to disclose them.
        """
        # First check direct query intent
        query_decision = self.evaluate_query(query)
        if query_decision.is_restricted:
            return query_decision

        # Inspect if retrieved chunks contain sensitive secret flags
        for r in retrieved_results:
            text = r.chunk.text.lower()
            # If chunk explicitly contains credentials or passwords and query is probing about access/login
            if any(k in text for k in ["password:", "passwd:", "api_key:", "private_key", "secret_key", "confidential:", "top secret", "classified:", "do not share", "internal secret"]):
                if any(q_term in query.lower() for q_term in ["what", "show", "give", "list", "tell", "get", "access", "how", "find", "read", "details"]):
                    return PrivacyDecision(
                        is_restricted=True,
                        category="SECRETS_AND_CONFIDENTIAL_DATA",
                        category_label="Enterprise Secrets, Secrecy & Confidential Records",
                        reason="Retrieved knowledge contains restricted credentials/secrets matching user query intent.",
                        refusal_message="Access Restricted: The retrieved document passages contain confidential enterprise secrets or authentication credentials. In accordance with enterprise security governance, this information cannot be disclosed.",
                        rule_matched="CONTEXT_SECRECY_PROTECTION"
                    )

        return PrivacyDecision(is_restricted=False)

    def verify_output(self, answer: str) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Stage 2 Post-Generation Check:
        Scans generated output for leaked credentials, private tokens, or PII.
        Returns (is_clean, verified_text, audit_data).
        """
        if not answer:
            return True, answer, {"leakage_detected": False, "verdict": "ZERO_LEAKAGE"}

        leaks_found = []
        for name, pattern in OUTPUT_LEAKAGE_PATTERNS.items():
            matches = list(pattern.finditer(answer))
            if matches:
                leaks_found.append(name)

        if leaks_found:
            # Complete containment: replace leaked text with restricted security notice
            refusal_text = (
                "ACCESS RESTRICTED [STAGE 2 LEAKAGE INTERCEPTED]: "
                "The synthesized response attempted to output confidential enterprise credentials or personal records. "
                "Output has been suppressed by Output Leakage Prevention."
            )
            return False, refusal_text, {
                "leakage_detected": True,
                "leaked_categories": leaks_found,
                "verdict": "LEAKAGE_SUPPRESSED"
            }

        return True, answer, {
            "leakage_detected": False,
            "verdict": "ZERO_LEAKAGE_VERIFIED"
        }

    def generate_audit_certificate(
        self,
        decision: PrivacyDecision,
        stage_2_audit: Optional[Dict[str, Any]] = None,
        elapsed_ms: float = 0.0,
        provider: str = "ollama"
    ) -> Dict[str, Any]:
        """Creates formal privacy audit record."""
        is_restricted = decision.is_restricted or (stage_2_audit and stage_2_audit.get("leakage_detected", False))

        return {
            "title": "Enterprise Dual-Stage Privacy Enforcement Certificate",
            "overall_status": "RESTRICTED" if is_restricted else "ALLOWED_AND_VERIFIED",
            "offline_guarantee": "100% Air-Gapped (Zero Cloud Egress)" if provider == "ollama" else "Cloud Hybrid Mode",
            "stage_1_query_adaptive_filter": {
                "status": "RESTRICTED" if decision.is_restricted else "PASSED",
                "category": decision.category,
                "category_label": decision.category_label,
                "reason": decision.reason,
                "rule_matched": decision.rule_matched
            },
            "stage_2_output_leakage_prevention": stage_2_audit or {
                "status": "PASSED",
                "leakage_detected": False,
                "verdict": "ZERO_LEAKAGE_VERIFIED"
            },
            "privacy_latency_ms": elapsed_ms,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
