"""
Email Service for Invoice Workflow
Handles editor notifications and Bau-Leiter approval emails with audit logging.
"""
import logging
import os
import json
import hashlib
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List
from uuid import UUID

import jwt
from jinja2 import Environment, FileSystemLoader, BaseLoader, Template
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition

from .database import db_service

logger = logging.getLogger(__name__)

class StringTemplateLoader(BaseLoader):
    """Custom Jinja2 loader for string templates"""
    def __init__(self, templates: Dict[str, str]):
        self.templates = templates
    
    def get_source(self, environment, template):
        if template in self.templates:
            source = self.templates[template]
            return source, None, lambda: True
        raise FileNotFoundError(f"Template {template} not found")

class EmailService:
    """
    Professional email service for invoice workflow with security and audit logging.
    Uses SendGrid for reliable email delivery.
    """
    
    def __init__(self):
        self.sendgrid_api_key = os.getenv("SENDGRID_API_KEY")
        self.from_email = os.getenv("FROM_EMAIL")
        self.from_name = os.getenv("FROM_NAME", "Invoice System")
        self.jwt_secret = os.getenv("JWT_SECRET")
        if not self.jwt_secret or self.jwt_secret.startswith("your-"):
            logger.warning("⚠️  JWT_SECRET not properly configured - email approval links may be insecure")
        self.base_url = os.getenv("BASE_URL", "http://localhost:8001")
        
        # Demo mode configuration
        self.demo_mode = os.getenv("EMAIL_DEMO_MODE", "false").lower() == "true"
        
        # Validate SendGrid configuration
        if not self.sendgrid_api_key:
            if not self.demo_mode:
                logger.warning("⚠️  SENDGRID_API_KEY not configured - email functionality will be disabled")
            else:
                logger.info("📧 Demo mode enabled - emails will be logged instead of sent")
        if not self.from_email:
            logger.warning("⚠️  FROM_EMAIL not configured - using default fallback")
        
        # Initialize template environment
        self.templates = self._load_templates()
        self.jinja_env = Environment(
            loader=StringTemplateLoader(self.templates),
            autoescape=True
        )
    
    def _load_templates(self) -> Dict[str, str]:
        """Load email templates"""
        return {
            "editor_notification": """
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>✅ Prüfbericht - Rechnung erfolgreich bearbeitet</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; max-width: 900px; margin: 0 auto; padding: 20px; background-color: #f5f7fa; }
        .container { background: white; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); overflow: hidden; }
        .header { background: linear-gradient(135deg, #28a745 0%, #20c997 100%); color: white; padding: 30px; text-align: center; }
        .header h1 { margin: 0; font-size: 28px; font-weight: 300; }
        .header p { margin: 10px 0 0 0; opacity: 0.9; }
        .content { padding: 30px; }
        .success-summary { background: #d4edda; border-left: 4px solid #28a745; padding: 20px; margin: 20px 0; border-radius: 8px; }
        .invoice-details { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 25px 0; }
        .detail-section { background: #ffffff; border: 1px solid #e1e5e9; border-radius: 12px; padding: 25px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        .detail-section h3 { color: #28a745; margin-top: 0; margin-bottom: 20px; font-size: 18px; font-weight: 600; border-bottom: 3px solid #28a745; padding-bottom: 10px; display: flex; align-items: center; }
        .detail-section h3:before { content: ""; width: 4px; height: 20px; background: #28a745; margin-right: 10px; border-radius: 2px; }
        .detail-row { display: flex; justify-content: space-between; margin-bottom: 15px; padding: 12px 0; border-bottom: 1px solid #f5f7fa; align-items: center; }
        .detail-row:last-child { border-bottom: none; margin-bottom: 0; }
        .detail-label { font-weight: 600; color: #4a5568; min-width: 160px; font-size: 14px; }
        .detail-value { color: #2d3748; flex: 1; text-align: right; font-size: 14px; padding: 6px 12px; background: #f8f9fa; border-radius: 6px; border-left: 3px solid #28a745; }
        .detail-value.amount { font-weight: bold; color: #28a745; background: #f0f9f4; border-left-color: #28a745; }
        .detail-value.date { font-family: 'Courier New', monospace; background: #f8f9ff; border-left-color: #4299e1; }
        .detail-value.text { background: #fefefe; border-left-color: #718096; }
        .amount-highlight { background: #e6fffa; border: 2px solid #38b2ac; border-radius: 8px; padding: 15px; text-align: center; margin: 20px 0; }
        .amount-highlight .amount { font-size: 24px; font-weight: bold; color: #38b2ac; }
        .changes-section { background: #f0f8ff; border: 1px solid #b3d9ff; border-radius: 8px; padding: 20px; margin: 20px 0; }
        .change-item { background: white; padding: 12px; margin: 8px 0; border-left: 4px solid #4299e1; border-radius: 4px; }
        .pdf-link { background: #e6f7ff; border: 1px solid #91d5ff; border-radius: 8px; padding: 15px; margin: 20px 0; text-align: center; }
        .pdf-link a { color: #1890ff; text-decoration: none; font-weight: 600; }
        .next-steps { background: #f7fafc; border-radius: 12px; padding: 25px; text-align: center; margin: 30px 0; }
        .next-steps h3 { color: #2d3748; margin-bottom: 15px; }
        .view-btn { display: inline-block; padding: 12px 24px; background: linear-gradient(135deg, #4299e1 0%, #3182ce 100%); color: white; text-decoration: none; border-radius: 6px; margin: 10px; font-weight: 500; font-size: 14px; }
        .footer { background: #f7fafc; padding: 25px; border-top: 1px solid #e2e8f0; font-size: 13px; color: #718096; }
        .status-badge { display: inline-block; padding: 6px 12px; background: #28a745; color: white; border-radius: 20px; font-size: 12px; font-weight: 600; }
        @media (max-width: 768px) {
            .invoice-details { grid-template-columns: 1fr; }
            .detail-row { flex-direction: column; }
            .detail-value { text-align: left; margin-top: 5px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>✅ Prüfbericht - Rechnung erfolgreich bearbeitet</h1>
            <p><strong>Bearbeitet am:</strong> {{ completion_date }}</p>
            <p><strong>Bearbeiter:</strong> {{ editor_name }} ({{ editor_email }})</p>
        </div>
        
        <div class="content">
            <!-- Success Summary -->
            <div class="success-summary">
                <h2 style="margin: 0 0 15px 0; color: #155724;">🎉 Bearbeitung erfolgreich abgeschlossen</h2>
                <p style="margin: 0; font-size: 16px;"><strong>{{ invoice_display_name }}</strong> wurde vollständig erfasst und ist bereit für die Genehmigung.</p>
                <p style="margin: 5px 0 0 0; color: #155724;">Status: <span class="status-badge">{{ status }}</span></p>
            </div>

            <!-- Amount Highlight -->
            {% if total_amount %}
            <div class="amount-highlight">
                <div style="color: #4a5568; margin-bottom: 5px;">Rechnungsbetrag</div>
                <div class="amount">{{ total_amount }}{% if currency %} {{ currency }}{% else %} EUR{% endif %}</div>
                {% if skonto_prozent and skonto_datum %}
                <div style="color: #718096; font-size: 14px; margin-top: 8px;">
                    Skonto: {{ skonto_prozent }}% bis {{ skonto_datum }}
                </div>
                {% endif %}
            </div>
            {% endif %}

            <!-- Essential Invoice Details -->
            <div class="invoice-details">
                <!-- Basic Information -->
                <div class="detail-section">
                    <h3>📋 Rechnungsdaten</h3>
                    <div class="detail-row">
                        <span class="detail-label">Rechnungsempfänger:</span>
                        <span class="detail-value text">{{ rechnungsempfaenger or 'Nicht eingegeben' }}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Rechnungssteller:</span>
                        <span class="detail-value text">{{ rechnungssteller or supplier_name or 'Nicht eingegeben' }}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Rechnungsdatum:</span>
                        <span class="detail-value date">{{ invoice_date or 'Nicht eingegeben' }}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Rechnungseingang:</span>
                        <span class="detail-value date">{{ rechnungseingang or 'Nicht eingegeben' }}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Projekt:</span>
                        <span class="detail-value text">{{ projekt or 'Nicht eingegeben' }}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Gewerk:</span>
                        <span class="detail-value text">{{ gewerk or 'Nicht eingegeben' }}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Weiter berechnen an:</span>
                        <span class="detail-value text">{{ weiter_berechnen_an or 'Nicht eingegeben' }}</span>
                    </div>
                </div>

                <!-- Financial Information -->
                <div class="detail-section">
                    <h3>💰 Finanzdaten</h3>
                    <div class="detail-row">
                        <span class="detail-label">Rechnungsbetrag:</span>
                        <span class="detail-value amount"><strong>{{ total_amount or rechnungsbetrag or '0.00' }}{% if currency %} {{ currency }}{% else %} EUR{% endif %}</strong></span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Fälligkeit:</span>
                        <span class="detail-value date">{{ faelligkeit or 'Nicht eingegeben' }}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Skonto Datum:</span>
                        <span class="detail-value date">{{ skonto_datum or 'Nicht eingegeben' }}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Skonto Prozent:</span>
                        <span class="detail-value amount">{{ skonto_prozent or 'Nicht eingegeben' }}{% if skonto_prozent and skonto_prozent != 'Nicht eingegeben' %}%{% endif %}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Rechnungsart:</span>
                        <span class="detail-value text">{{ rechnungsart or 'Nicht eingegeben' }}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">KfW anrechenbar:</span>
                        <span class="detail-value text">{{ kfw_anrechenbare_kosten or 'Nicht eingegeben' }}</span>
                    </div>
                </div>
            </div>

            <!-- PDF Link - Visual Only -->
            {% if has_pdf %}
            <div class="pdf-link">
                <strong>📄 Original Rechnung anzeigen:</strong><br>
                <div style="display: inline-block; padding: 12px 24px; background: #e2e8f0; color: #718096; border-radius: 6px; margin: 10px; font-weight: 500; font-size: 14px; cursor: not-allowed;">PDF öffnen (Nicht verfügbar)</div>
                <p style="font-size: 12px; color: #718096; margin: 10px 0 0 0;">
                    Diese Funktion ist aktuell nicht verfügbar - PDF wird lokal gespeichert
                </p>
            </div>
            {% endif %}

            <!-- Simple Success Message -->
            <div class="changes-section">
                <h3 style="color: #28a745; margin-top: 0;">✅ Bearbeitung erfolgreich abgeschlossen</h3>
                <p style="color: #4a5568; margin-bottom: 15px; font-size: 16px;">
                    Die Rechnung wurde vollständig bearbeitet und alle erforderlichen Daten wurden erfasst. 
                    Das System hat die Änderungen gespeichert und die Rechnung ist bereit für den nächsten Schritt im Genehmigungsworkflow.
                </p>
                <div style="background: #d4edda; border: 1px solid #c3e6cb; border-radius: 8px; padding: 15px; margin: 15px 0;">
                    <strong>🎉 Status:</strong> Rechnung erfolgreich bearbeitet und gespeichert
                    <br><strong>📋 Bereit für:</strong> Genehmigung durch Bau-Leiter
                    <br><strong>⏰ Bearbeitet am:</strong> {{ completion_date }}
                </div>
            </div>

            <!-- Next Steps -->
            <div class="next-steps">
                <h3>🎯 Nächste Schritte</h3>
                <p style="color: #4a5568; margin-bottom: 15px;">
                    Die Rechnung wurde vollständig erfasst und ist bereit für den Genehmigungsworkflow.
                </p>
                <div style="background: #fff3cd; border: 1px solid #ffeaa7; border-radius: 6px; padding: 15px; margin: 15px 0;">
                    <strong>📋 Automatische Weiterleitung:</strong> Das System wird automatisch eine 
                    Benachrichtigung an den zuständigen Bau-Leiter senden, sobald alle Daten validiert wurden.
                </div>
                <p style="font-size: 14px; color: #718096;">
                    Sie erhalten eine weitere Benachrichtigung, sobald die Genehmigung erteilt oder abgelehnt wurde.
                </p>
            </div>
        </div>
        
        <!-- Footer -->
        <div class="footer">
            <p><strong>✅ Bearbeitung erfolgreich abgeschlossen</strong></p>
            <p><strong>Bearbeiter:</strong> {{ editor_name }} ({{ editor_email }})</p>
            <p><strong>Zeitstempel:</strong> {{ timestamp }}</p>
            <p><strong>Request ID:</strong> {{ request_id }}</p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 15px 0;">
            <p>Diese E-Mail wurde automatisch vom Rechnungsverarbeitungssystem generiert. Bitte antworten Sie nicht auf diese E-Mail.</p>
            <p><strong>Technischer Support:</strong> Bei Fragen zur Rechnungsverarbeitung kontaktieren Sie das IT-Team.</p>
        </div>
    </div>
</body>
</html>
            """,
            
            "bauleiter_approval": """
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Rechnung zur Genehmigung - {{ invoice_display_name or 'N/A' }}</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; max-width: 900px; margin: 0 auto; padding: 20px; background-color: #f5f7fa; }
        .container { background: white; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); overflow: hidden; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; }
        .header h1 { margin: 0; font-size: 28px; font-weight: 300; }
        .header p { margin: 10px 0 0 0; opacity: 0.9; }
        .content { padding: 30px; }
        .invoice-summary { background: #f8f9fc; border-left: 4px solid #667eea; padding: 20px; margin: 20px 0; border-radius: 8px; }
        .detail-section { background: #ffffff; border: 1px solid #e1e5e9; border-radius: 8px; padding: 20px; margin: 20px 0; }
        .detail-section h3 { color: #667eea; margin-top: 0; margin-bottom: 15px; font-size: 16px; font-weight: 600; border-bottom: 2px solid #f0f2f7; padding-bottom: 8px; }
        .amount-highlight { background: #e6fffa; border: 2px solid #38b2ac; border-radius: 8px; padding: 15px; text-align: center; margin: 20px 0; }
        .amount-highlight .amount { font-size: 24px; font-weight: bold; color: #38b2ac; }
        .changes-section { background: #fff5f5; border: 1px solid #fed7d7; border-radius: 8px; padding: 20px; margin: 20px 0; }
        .pdf-section { background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 6px; padding: 15px; margin: 20px 0; text-align: center; }
        .action-buttons { background: #f7fafc; border-radius: 12px; padding: 30px; text-align: center; margin: 30px 0; }
        .action-buttons h3 { color: #2d3748; margin-bottom: 20px; }
        .approve-btn { display: inline-block; padding: 16px 32px; background: linear-gradient(135deg, #48bb78 0%, #38a169 100%); color: white; text-decoration: none; border-radius: 8px; margin: 10px; font-weight: 600; font-size: 16px; box-shadow: 0 4px 6px rgba(72, 187, 120, 0.3); transition: all 0.3s ease; }
        .approve-btn:hover { box-shadow: 0 6px 8px rgba(72, 187, 120, 0.4); transform: translateY(-2px); }
        .reject-btn { display: inline-block; padding: 16px 32px; background: linear-gradient(135deg, #f56565 0%, #e53e3e 100%); color: white; text-decoration: none; border-radius: 8px; margin: 10px; font-weight: 600; font-size: 16px; box-shadow: 0 4px 6px rgba(245, 101, 101, 0.3); transition: all 0.3s ease; }
        .reject-btn:hover { box-shadow: 0 6px 8px rgba(245, 101, 101, 0.4); transform: translateY(-2px); }
        .footer { background: #f7fafc; padding: 25px; border-top: 1px solid #e2e8f0; font-size: 13px; color: #718096; }
        .security-notice { background: #fffbeb; border: 1px solid #f6e05e; border-radius: 8px; padding: 15px; margin: 20px 0; }
        .security-notice strong { color: #744210; }
        .status-badge { display: inline-block; padding: 4px 12px; background: #48bb78; color: white; border-radius: 20px; font-size: 12px; font-weight: 600; }
        .amount { color: #28a745 !important; font-weight: 600; }
        .date { color: #007bff !important; }
        .text { color: #333; }
        @media (max-width: 768px) {
            .detail-grid { grid-template-columns: 1fr !important; }
            .action-buttons { padding: 20px; }
            .approve-btn, .reject-btn { display: block; margin: 10px 0; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📋 Rechnung zur Genehmigung</h1>
            <p><strong>Eingereicht am:</strong> {{ submission_date }}</p>
            <p><strong>Bearbeitet von:</strong> {{ editor_name }} ({{ editor_email }})</p>
        </div>
        
        <div class="content">
            <!-- Invoice Summary -->
            <div class="invoice-summary">
                <h2 style="margin: 0 0 15px 0; color: #2d3748;">📄 {{ invoice_display_name }}</h2>
                <p style="margin: 0; font-size: 16px;"><strong>Lieferant:</strong> {{ supplier_name }}</p>
                <p style="margin: 5px 0 0 0; color: #718096;">Status: <span class="status-badge">Zur Genehmigung</span></p>
            </div>

            <!-- Amount Highlight -->
            {% if total_amount %}
            <div class="amount-highlight">
                <div style="color: #4a5568; margin-bottom: 5px;">Rechnungsbetrag</div>
                <div class="amount">{{ total_amount }}{% if currency %} {{ currency }}{% else %} EUR{% endif %}</div>
                {% if skonto_prozent and skonto_datum %}
                <div style="color: #718096; font-size: 14px; margin-top: 8px;">
                    Skonto: {{ skonto_prozent }}% bis {{ skonto_datum }}
                </div>
                {% endif %}
            </div>
            {% endif %}

            <!-- Rechnungsdaten Section -->
            <div class="detail-section">
                <h3>📋 Rechnungsdaten</h3>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 15px;" class="detail-grid">
                    <div>
                        <strong style="color: #495057; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px;">Rechnungsempfänger</strong>
                        <div style="margin-top: 4px; padding: 6px 0; color: #333; border-bottom: 1px solid #eee;" class="text">{{ rechnungsempfaenger }}</div>
                    </div>
                    <div>
                        <strong style="color: #495057; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px;">Rechnungssteller</strong>
                        <div style="margin-top: 4px; padding: 6px 0; color: #333; border-bottom: 1px solid #eee;" class="text">{{ rechnungssteller }}</div>
                    </div>
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 15px;" class="detail-grid">
                    <div>
                        <strong style="color: #495057; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px;">Rechnungsdatum</strong>
                        <div style="margin-top: 4px; padding: 6px 0; color: #333; border-bottom: 1px solid #eee;" class="date">{{ invoice_date }}</div>
                    </div>
                    <div>
                        <strong style="color: #495057; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px;">Rechnungseingang</strong>
                        <div style="margin-top: 4px; padding: 6px 0; color: #333; border-bottom: 1px solid #eee;" class="date">{{ rechnungseingang }}</div>
                    </div>
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;" class="detail-grid">
                    <div>
                        <strong style="color: #495057; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px;">Projekt</strong>
                        <div style="margin-top: 4px; padding: 6px 0; color: #333; border-bottom: 1px solid #eee;" class="text">{{ projekt }}</div>
                    </div>
                    <div>
                        <strong style="color: #495057; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px;">Gewerk</strong>
                        <div style="margin-top: 4px; padding: 6px 0; color: #333; border-bottom: 1px solid #eee;" class="text">{{ gewerk }}</div>
                    </div>
                </div>
            </div>

            <!-- Finanzdaten Section -->
            <div class="detail-section">
                <h3>💰 Finanzdaten</h3>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 15px;" class="detail-grid">
                    <div>
                        <strong style="color: #495057; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px;">Fälligkeit</strong>
                        <div style="margin-top: 4px; padding: 6px 0; color: #333; border-bottom: 1px solid #eee;" class="date">{{ faelligkeit }}</div>
                    </div>
                    <div>
                        <strong style="color: #495057; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px;">Skonto bis</strong>
                        <div style="margin-top: 4px; padding: 6px 0; color: #333; border-bottom: 1px solid #eee;" class="date">{{ skonto_datum }}</div>
                    </div>
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 15px;" class="detail-grid">
                    <div>
                        <strong style="color: #495057; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px;">Skonto</strong>
                        <div style="margin-top: 4px; padding: 6px 0; color: #333; border-bottom: 1px solid #eee;" class="amount">{{ skonto_prozent }}%</div>
                    </div>
                    <div>
                        <strong style="color: #495057; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px;">Rechnungsart</strong>
                        <div style="margin-top: 4px; padding: 6px 0; color: #333; border-bottom: 1px solid #eee;" class="text">{{ rechnungsart }}</div>
                    </div>
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;" class="detail-grid">
                    <div>
                        <strong style="color: #495057; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px;">Weiter berechnen an</strong>
                        <div style="margin-top: 4px; padding: 6px 0; color: #333; border-bottom: 1px solid #eee;" class="text">{{ weiter_berechnen_an }}</div>
                    </div>
                    <div>
                        <strong style="color: #495057; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px;">KfW anrechenbar</strong>
                        <div style="margin-top: 4px; padding: 6px 0; color: #333; border-bottom: 1px solid #eee;" class="text">{{ kfw_anrechenbare_kosten }}</div>
                    </div>
                </div>
            </div>

            <!-- PDF Link (Non-functional) -->
            {% if has_pdf %}
            <div class="pdf-section">
                <div style="display: inline-block; padding: 8px 16px; background: #6c757d; color: white; border-radius: 4px; font-size: 14px;">
                    📄 PDF nicht verfügbar
                </div>
                <p style="margin: 8px 0 0 0; font-size: 13px; color: #6c757d;">PDF-Ansicht wird nach der Unternehmens-Konfiguration verfügbar sein</p>
            </div>
            {% endif %}

            <!-- Processing Summary -->
            <div class="changes-section">
                <h3 style="color: #28a745; margin-top: 0;">✅ Rechnung bereit zur Genehmigung</h3>
                <p style="color: #4a5568; margin-bottom: 15px; font-size: 16px;">
                    Die Rechnung wurde vollständig bearbeitet und alle erforderlichen Daten wurden erfasst. 
                    Die Rechnung ist jetzt bereit für Ihre Prüfung und Genehmigung.
                </p>
                <div style="background: #e3f2fd; border: 1px solid #90caf9; border-radius: 8px; padding: 15px; margin: 15px 0;">
                    <strong>✅ Status:</strong> Bearbeitung abgeschlossen
                    <br><strong>👤 Bearbeitet von:</strong> {{ editor_name }} ({{ editor_email }})
                    <br><strong>📅 Bearbeitet am:</strong> {{ submission_date }}
                    <br><strong>⏱ Wartet auf:</strong> Ihre Genehmigung
                </div>
            </div>

            <!-- Action Buttons -->
            <div class="action-buttons">
                <h3>🎯 Genehmigung erforderlich</h3>
                <p style="color: #4a5568; margin-bottom: 25px;">
                    Bitte prüfen Sie die Rechnung und entscheiden Sie mit einem Klick:
                </p>
                <a href="{{ approve_url }}" style="display: inline-block; padding: 16px 32px; background: #38a169; color: #ffffff; text-decoration: none; border-radius: 8px; margin: 10px; font-weight: 600; font-size: 16px;">✅ RECHNUNG GENEHMIGEN</a>
                <a href="{{ reject_url }}" style="display: inline-block; padding: 16px 32px; background: #e53e3e; color: #ffffff; text-decoration: none; border-radius: 8px; margin: 10px; font-weight: 600; font-size: 16px;">❌ RECHNUNG ABLEHNEN</a>
                <br><br>
                <p style="font-size: 14px; color: #718096;">
                    Jeder Link kann nur einmal verwendet werden.
                </p>
            </div>

            <!-- Security Notice -->
            <div class="security-notice">
                <strong>🔒 Sicherheitshinweis:</strong> Diese Genehmigungslinks sind verschlüsselt und verfallen automatisch in 7 Tagen. 
                Klicken Sie nur auf Links in E-Mails, die Sie erwartet haben. Bei Verdacht auf Manipulation kontaktieren Sie sofort den System-Administrator.
            </div>
        </div>
        
        <!-- Footer -->
        <div class="footer">
            <p><strong>🤖 Automatisch generiert vom Rechnungsverarbeitungssystem</strong></p>
            <p><strong>Zeitstempel:</strong> {{ timestamp }}</p>
            <p><strong>Token gültig bis:</strong> {{ token_expires }}</p>
            <p><strong>E-Mail ID:</strong> {{ email_id or 'N/A' }}</p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 15px 0;">
            <p>Diese E-Mail wurde automatisch versendet. Bei Fragen oder Problemen wenden Sie sich an den System-Administrator.</p>
            <p><strong>Technischer Support:</strong> Für Unterstützung bei der Rechnungsverarbeitung kontaktieren Sie das IT-Team.</p>
        </div>
    </div>
</body>
</html>
            """,
            
            "dropdown_change_notification": """
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dropdown Changes Notification</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; }
        .header { background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
        .content { background: white; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px; }
        .changes-section { margin-top: 20px; }
        .change-item { padding: 10px; border-left: 4px solid #007bff; margin-bottom: 10px; background: #f8f9fa; }
        .change-add { border-left-color: #28a745; background: #f8fff9; }
        .change-delete { border-left-color: #dc3545; background: #fff8f8; }
        .footer { margin-top: 30px; padding: 20px; background: #f8f9fa; border-radius: 8px; font-size: 0.9em; color: #666; }
        .timestamp { font-size: 0.9em; color: #666; }
        .field-name { font-weight: bold; color: #007bff; }
    </style>
</head>
<body>
    <div class="header">
        <h1>📋 Dropdown Options Updated</h1>
        <p><strong>Date:</strong> {{ timestamp }}</p>
        <p><strong>Updated by:</strong> {{ user_email }}</p>
        <p><strong>Total changes:</strong> {{ changes|length }}</p>
    </div>
    
    <div class="content">
        <h2>Changes Summary</h2>
        <div class="changes-section">
            {% for change in changes %}
            <div class="change-item change-{{ change.type }}">
                <h4>
                    {% if change.type == 'add' %}
                        ➕ Added new option
                    {% elif change.type == 'delete' %}
                        ➖ Deleted option
                    {% endif %}
                </h4>
                <p><strong>Field:</strong> <span class="field-name">{{ change.fieldName }}</span></p>
                <p><strong>Option:</strong> {{ change.optionLabel }}</p>
                <p><strong>Value:</strong> <code>{{ change.optionValue }}</code></p>
                <p class="timestamp"><strong>Time:</strong> {{ change.timestamp }}</p>
                {% if change.success is defined %}
                    <p><strong>Status:</strong> 
                        {% if change.success %}
                            <span style="color: #28a745;">✅ Success</span>
                        {% else %}
                            <span style="color: #dc3545;">❌ Failed</span>
                        {% endif %}
                    </p>
                {% endif %}
            </div>
            {% endfor %}
        </div>
        
        <div class="footer">
            <p><strong>System Information:</strong></p>
            <p>This notification confirms that dropdown options have been updated in the invoice management system.</p>
            <p>All changes are tracked for audit purposes.</p>
            <p><strong>Timestamp:</strong> {{ iso_timestamp }}</p>
        </div>
    </div>
</body>
</html>
            """,
        
        "skonto_reminder": """
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🎯 Skonto-Erinnerung - Handlung erforderlich</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; max-width: 900px; margin: 0 auto; padding: 20px; background-color: #f5f7fa; }
        .container { background: white; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); overflow: hidden; }
        .header { background: linear-gradient(135deg, #f39c12, #e67e22); color: white; padding: 30px; border-radius: 8px 8px 0 0; text-align: center; }
        .header h1 { margin: 0; font-size: 28px; font-weight: 600; }
        .header p { margin: 10px 0 0 0; opacity: 0.9; font-size: 18px; }
        .content { padding: 30px; }
        .alert-box { background: #fff3cd; border-left: 4px solid #f39c12; padding: 20px; border-radius: 8px; margin: 20px 0; }
        .invoice-summary { background: #f8f9fc; border-left: 4px solid #f39c12; padding: 20px; margin: 20px 0; border-radius: 8px; }
        .detail-section { background: #ffffff; border: 1px solid #e1e5e9; border-radius: 8px; padding: 20px; margin: 20px 0; }
        .detail-section h3 { color: #f39c12; margin-top: 0; margin-bottom: 15px; font-size: 18px; font-weight: 600; border-bottom: 3px solid #f39c12; padding-bottom: 10px; }
        .skonto-highlight { background: #e8f5e8; border: 2px solid #28a745; border-radius: 8px; padding: 20px; text-align: center; margin: 20px 0; }
        .skonto-highlight .amount { font-size: 24px; font-weight: bold; color: #28a745; }
        .savings-calculation { background: #f0f8ff; border: 1px solid #b3d9ff; padding: 20px; border-radius: 8px; margin: 20px 0; text-align: center; }
        .action-buttons { background: #f7fafc; border-radius: 12px; padding: 30px; text-align: center; margin: 30px 0; }
        .deadline-warning { background: #ffecec; border: 1px solid #ff9999; padding: 20px; border-radius: 8px; margin: 20px 0; color: #d63031; text-align: center; }
        .footer { background: #f7fafc; padding: 25px; border-top: 1px solid #e2e8f0; font-size: 13px; color: #718096; }
        .security-notice { background: #fffbeb; border: 1px solid #f6e05e; border-radius: 8px; padding: 15px; margin: 20px 0; }
        .amount { color: #28a745 !important; font-weight: 600; }
        .date { color: #007bff !important; }
        .text { color: #333; }
        @media (max-width: 768px) {
            .detail-grid { grid-template-columns: 1fr !important; }
            .action-buttons { padding: 20px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎯 Skonto-Erinnerung</h1>
            <p>Handlung erforderlich - Skonto läuft bald ab!</p>
        </div>
        
        <div class="content">
            <div class="alert-box">
                <strong>⏰ ZEITKRITISCH:</strong> Das Skonto für diese Rechnung läuft in {{ days_until_expiry }} Tag(en) ab. 
                Eine Entscheidung wäre erforderlich, um potenzielle Einsparungen nicht zu verpassen.
            </div>

            <!-- Invoice Summary -->
            <div class="invoice-summary">
                <h2 style="margin: 0 0 15px 0; color: #2d3748;">📄 {{ invoice_display_name }}</h2>
                <p style="margin: 0; font-size: 16px;"><strong>Lieferant:</strong> {{ supplier_name }}</p>
                <p style="margin: 5px 0 0 0; color: #718096;">Rechnungsdatum: {{ invoice_date }}</p>
            </div>

            <!-- Skonto Highlight -->
            {% if potential_savings %}
            <div class="skonto-highlight">
                <div style="color: #4a5568; margin-bottom: 5px;">Potenzielle Skonto-Einsparung</div>
                <div class="amount">{{ potential_savings }} {{ currency }}</div>
                <div style="color: #718096; font-size: 14px; margin-top: 8px;">
                    {{ skonto_prozent }}% Skonto bis {{ skonto_datum }}
                </div>
            </div>
            {% endif %}

            <!-- Invoice Details -->
            <div class="detail-section">
                <h3>📋 Rechnungsdetails</h3>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 15px;" class="detail-grid">
                    <div>
                        <strong style="color: #495057; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px;">Rechnungsbetrag</strong>
                        <div style="margin-top: 4px; padding: 6px 0; color: #333; border-bottom: 1px solid #eee;" class="amount">{{ total_amount }}{% if currency %} {{ currency }}{% endif %}</div>
                    </div>
                    <div>
                        <strong style="color: #495057; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px;">Rechnungsdatum</strong>
                        <div style="margin-top: 4px; padding: 6px 0; color: #333; border-bottom: 1px solid #eee;" class="date">{{ invoice_date }}</div>
                    </div>
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;" class="detail-grid">
                    <div>
                        <strong style="color: #495057; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px;">Skonto Prozent</strong>
                        <div style="margin-top: 4px; padding: 6px 0; color: #333; border-bottom: 1px solid #eee;" class="amount">{{ skonto_prozent }}%</div>
                    </div>
                    <div>
                        <strong style="color: #495057; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px;">Skonto bis</strong>
                        <div style="margin-top: 4px; padding: 6px 0; color: #333; border-bottom: 1px solid #eee;" class="date">{{ skonto_datum }}</div>
                    </div>
                </div>
            </div>

            {% if potential_savings %}
            <div class="savings-calculation">
                <h4 style="margin: 0 0 15px 0; color: #28a745;">📊 Einsparungsberechnung</h4>
                <p style="font-size: 18px; font-weight: bold; color: #28a745; margin: 10px 0;">
                    {{ potential_savings }} {{ currency }}
                </p>
                <small style="color: #666;">Berechnung: {{ total_amount }} × {{ skonto_prozent }}% = {{ potential_savings }} {{ currency }}</small>
            </div>
            {% endif %}

            {% if days_until_expiry <= 3 %}
            <div class="deadline-warning">
                <strong>🚨 DRINGEND: Nur noch {{ days_until_expiry }} Tag(en) bis zum Skonto-Ablauf!</strong>
            </div>
            {% endif %}

            <!-- Action Buttons -->
            <div class="action-buttons">
                <h3>🎯 Entscheidung erforderlich</h3>
                <p style="color: #4a5568; margin-bottom: 25px;">
                    Soll das Skonto genutzt werden?
                </p>
                <a href="{{ take_skonto_url }}" style="display: inline-block; padding: 16px 32px; background: #38a169; color: #ffffff; text-decoration: none; border-radius: 8px; margin: 10px; font-weight: 600; font-size: 16px;">✅ SKONTO NEHMEN</a>
                <a href="{{ skip_skonto_url }}" style="display: inline-block; padding: 16px 32px; background: #718096; color: #ffffff; text-decoration: none; border-radius: 8px; margin: 10px; font-weight: 600; font-size: 16px;">⏭️ SKONTO ÜBERSPRINGEN</a>
                <br><br>
                <p style="font-size: 14px; color: #718096;">
                    Jeder Link kann nur einmal verwendet werden.
                </p>
            </div>

            <div class="security-notice">
                <strong>🔒 Sicherheitshinweis:</strong> Diese Funktionen werden nach der Unternehmens-Konfiguration verfügbar sein. 
                Das System wird dann automatische Skonto-Entscheidungen und Benachrichtigungen unterstützen.
            </div>
        </div>
        
        <div class="footer">
            <p><strong>🤖 Automatisch generiert vom Rechnungsverarbeitungssystem</strong></p>
            <p><strong>Zeitstempel:</strong> {{ timestamp }}</p>
            <p><strong>E-Mail ID:</strong> {{ email_id or 'N/A' }}</p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 15px 0;">
            <p>Diese E-Mail wurde automatisch versendet. Bei Fragen oder Problemen wenden Sie sich an den System-Administrator.</p>
            <p><strong>Skonto-Verwaltung:</strong> Für Unterstützung bei Skonto-Entscheidungen kontaktieren Sie die Buchhaltung.</p>
        </div>
    </div>
</body>
</html>
        """,
        
        "editor_summary": """
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📝 Rechnung bearbeitet - Zusammenfassung bisher</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; max-width: 900px; margin: 0 auto; padding: 20px; background-color: #f5f7fa; }
        .container { background: white; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); overflow: hidden; }
        .header { background: linear-gradient(135deg, #4299e1 0%, #3182ce 100%); color: white; padding: 30px; text-align: center; }
        .header h1 { margin: 0; font-size: 28px; font-weight: 300; }
        .header p { margin: 10px 0 0 0; opacity: 0.9; }
        .content { padding: 30px; }
        .progress-summary { background: #ebf8ff; border-left: 4px solid #4299e1; padding: 20px; margin: 20px 0; border-radius: 8px; }
        .invoice-details { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 25px 0; }
        .detail-section { background: #ffffff; border: 1px solid #e1e5e9; border-radius: 8px; padding: 20px; }
        .detail-section h3 { color: #4299e1; margin-top: 0; margin-bottom: 15px; font-size: 16px; font-weight: 600; border-bottom: 2px solid #f0f2f7; padding-bottom: 8px; }
        .detail-row { display: flex; justify-content: space-between; margin-bottom: 12px; padding: 8px 0; border-bottom: 1px solid #f5f7fa; }
        .detail-label { font-weight: 600; color: #4a5568; min-width: 140px; }
        .detail-value { color: #2d3748; flex: 1; text-align: right; }
        .empty-value { color: #a0aec0; font-style: italic; }
        .amount-highlight { background: #e6fffa; border: 2px solid #38b2ac; border-radius: 8px; padding: 15px; text-align: center; margin: 20px 0; }
        .amount-highlight .amount { font-size: 24px; font-weight: bold; color: #38b2ac; }
        .pdf-link { background: #e6f7ff; border: 1px solid #91d5ff; border-radius: 8px; padding: 15px; margin: 20px 0; text-align: center; }
        .pdf-link a { color: #1890ff; text-decoration: none; font-weight: 600; }
        .next-steps { background: #f7fafc; border-radius: 12px; padding: 25px; text-align: center; margin: 30px 0; }
        .next-steps h3 { color: #2d3748; margin-bottom: 15px; }
        .view-btn { display: inline-block; padding: 12px 24px; background: linear-gradient(135deg, #4299e1 0%, #3182ce 100%); color: white; text-decoration: none; border-radius: 6px; margin: 10px; font-weight: 500; font-size: 14px; }
        .footer { background: #f7fafc; padding: 25px; border-top: 1px solid #e2e8f0; font-size: 13px; color: #718096; }
        .status-badge { display: inline-block; padding: 6px 12px; background: #4299e1; color: white; border-radius: 20px; font-size: 12px; font-weight: 600; }
        @media (max-width: 768px) {
            .invoice-details { grid-template-columns: 1fr; }
            .detail-row { flex-direction: column; }
            .detail-value { text-align: left; margin-top: 5px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📝 Rechnung bearbeitet - Zusammenfassung bisher</h1>
            <p><strong>Bearbeitet am:</strong> {{ completion_date }}</p>
            <p><strong>Bearbeiter:</strong> {{ editor_name }} ({{ editor_email }})</p>
        </div>
        
        <div class="content">
            <!-- Progress Summary -->
            <div class="progress-summary">
                <h2 style="margin: 0 0 15px 0; color: #2b6cb0;">📋 Aktueller Stand der Bearbeitung</h2>
                <p style="margin: 0; font-size: 16px;"><strong>{{ invoice_number or 'Rechnung ohne Nummer' }}</strong> wurde bearbeitet und zwischengespeichert.</p>
                <p style="margin: 5px 0 0 0; color: #2b6cb0;">Status: <span class="status-badge">In Bearbeitung</span></p>
                <p style="margin: 10px 0 0 0; color: #4a5568; font-size: 14px;">Die Rechnung ist noch nicht abgeschlossen. Dies ist eine Zwischenmitteilung über die bisherigen Eingaben.</p>
            </div>

            <!-- Amount Highlight -->
            {% if total_amount %}
            <div class="amount-highlight">
                <div style="color: #4a5568; margin-bottom: 5px;">Rechnungsbetrag</div>
                <div class="amount">{{ total_amount }}{% if currency %} {{ currency }}{% else %} EUR{% endif %}</div>
                {% if skonto_prozent and skonto_datum %}
                <div style="color: #718096; font-size: 14px; margin-top: 8px;">
                    Skonto: {{ skonto_prozent }}% bis {{ skonto_datum }}
                </div>
                {% endif %}
            </div>
            {% endif %}

            <!-- Essential Invoice Details -->
            <div class="invoice-details">
                <!-- Basic Information -->
                <div class="detail-section">
                    <h3>📋 Rechnungsdaten</h3>
                    <div class="detail-row">
                        <span class="detail-label">Rechnungsempfänger:</span>
                        <span class="detail-value {% if not rechnungsempfaenger %}empty-value{% endif %}">{{ rechnungsempfaenger or 'Noch nicht eingegeben' }}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Rechnungssteller:</span>
                        <span class="detail-value {% if not (rechnungssteller or supplier_name) %}empty-value{% endif %}">{{ rechnungssteller or supplier_name or 'Noch nicht eingegeben' }}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Projekt:</span>
                        <span class="detail-value {% if not projekt %}empty-value{% endif %}">{{ projekt or 'Projekt auswählen...' }}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Gewerk:</span>
                        <span class="detail-value {% if not gewerk %}empty-value{% endif %}">{{ gewerk or 'Gewerk auswählen...' }}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Weiter berechnen an:</span>
                        <span class="detail-value {% if not weiter_berechnen_an %}empty-value{% endif %}">{{ weiter_berechnen_an or 'Abteilung oder Kontakt auswählen...' }}</span>
                    </div>
                </div>

                <!-- Financial Information -->
                <div class="detail-section">
                    <h3>💰 Finanzdaten</h3>
                    <div class="detail-row">
                        <span class="detail-label">Rechnungsbetrag:</span>
                        <span class="detail-value {% if not (total_amount or rechnungsbetrag) %}empty-value{% endif %}"><strong>{{ total_amount or rechnungsbetrag or '0.00' }}{% if currency %} {{ currency }}{% else %} EUR{% endif %}</strong></span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Rechnungseingang:</span>
                        <span class="detail-value {% if not rechnungseingang %}empty-value{% endif %}">{{ rechnungseingang or 'dd.mm.yyyy' }}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Fälligkeit:</span>
                        <span class="detail-value {% if not faelligkeit %}empty-value{% endif %}">{{ faelligkeit or 'dd.mm.yyyy' }}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Skonto Datum:</span>
                        <span class="detail-value {% if not skonto_datum %}empty-value{% endif %}">{{ skonto_datum or 'dd.mm.yyyy' }}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Skonto Prozent:</span>
                        <span class="detail-value {% if not skonto_prozent %}empty-value{% endif %}">{{ skonto_prozent or '0.00' }}%</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Rechnungsart:</span>
                        <span class="detail-value {% if not rechnungsart %}empty-value{% endif %}">{{ rechnungsart or 'Typ auswählen...' }}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">KfW anrechenbar:</span>
                        <span class="detail-value {% if not kfw_anrechenbare_kosten %}empty-value{% endif %}">{{ kfw_anrechenbare_kosten or 'Nicht angegeben' }}</span>
                    </div>
                </div>
            </div>

            <!-- PDF Link -->
            {% if pdf_url %}
            <div class="pdf-link">
                <strong>📄 Original Rechnung anzeigen:</strong><br>
                <a href="{{ pdf_url }}" target="_blank" class="view-btn">PDF öffnen</a>
                <p style="font-size: 12px; color: #718096; margin: 10px 0 0 0;">
                    Klicken Sie hier, um die Original-Rechnung als PDF zu öffnen
                </p>
            </div>
            {% endif %}

            <!-- Next Steps -->
            <div class="next-steps">
                <h3>🎯 Nächste Schritte</h3>
                <p style="color: #4a5568; margin-bottom: 15px;">
                    Die Rechnung ist noch in Bearbeitung. Sie können weitere Felder ausfüllen oder korrigieren.
                </p>
                <div style="background: #e6f7ff; border: 1px solid #91d5ff; border-radius: 6px; padding: 15px; margin: 15px 0;">
                    <strong>⚠️ Hinweis:</strong> Dies ist eine Zwischenmitteilung. Die Rechnung ist noch nicht abgeschlossen und wird nicht an den Bau-Leiter weitergeleitet.
                </div>
                <p style="font-size: 14px; color: #718096;">
                    Klicken Sie auf "Complete" im System, um die Bearbeitung abzuschließen und die Rechnung zur Genehmigung zu senden.
                </p>
            </div>
        </div>
        
        <!-- Footer -->
        <div class="footer">
            <p><strong>📝 Zwischenspeicherung erfolgreich</strong></p>
            <p><strong>Bearbeiter:</strong> {{ editor_name }} ({{ editor_email }})</p>
            <p><strong>Zeitstempel:</strong> {{ timestamp }}</p>
            <p><strong>Request ID:</strong> {{ request_id }}</p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 15px 0;">
            <p>Diese E-Mail wurde automatisch vom Rechnungsverarbeitungssystem generiert. Bitte antworten Sie nicht auf diese E-Mail.</p>
            <p><strong>Technischer Support:</strong> Bei Fragen zur Rechnungsverarbeitung kontaktieren Sie das IT-Team.</p>
        </div>
    </div>
</body>
</html>
        """
        }
    
    async def send_editor_notification(
        self, 
        invoice_data: Dict[str, Any], 
        editor_email: str, 
        editor_name: str,
        changes_summary: Optional[List[Dict[str, Any]]] = None,
        request_id: Optional[str] = None,
        is_completion: bool = False
    ) -> Dict[str, Any]:
        """
        Send professional HTML email notification to editor after invoice completion.
        Only marks invoice as completed after successful email send.
        """
        try:
            # Helper function to clean placeholder values
            def clean_field_value(value):
                """Replace placeholder/default values with 'Nicht eingegeben'"""
                if not value or value in [
                    'Projekt auswählen...', 'Gewerk auswählen...', 'Abteilung oder Kontakt auswählen...',
                    'Typ auswählen...', 'dd.mm.yyyy', 'mm.yyyy', 'yyyy', '0.00', '0,00'
                ]:
                    return 'Nicht eingegeben'
                return value

            # Helper function to get display name (filename fallback)
            def get_display_name(invoice_data):
                """Get display name for invoice - use filename if invoice number is missing"""
                invoice_number = clean_field_value(invoice_data.get("rechnungsnummer"))
                if invoice_number == 'Nicht eingegeben' and invoice_data.get("file_path"):
                    # Extract filename from file_path
                    filename = invoice_data["file_path"].split("/")[-1]
                    # Remove file extension for cleaner display
                    if filename.endswith('.pdf'):
                        filename = filename[:-4]
                    return filename
                return invoice_number if invoice_number != 'Nicht eingegeben' else 'Rechnung ohne Nummer'

            # Prepare comprehensive template context with ALL invoice fields
            context = {
                # Editor and timing information
                "editor_name": editor_name,
                "editor_email": editor_email,
                "completion_date": datetime.now().strftime("%d.%m.%Y um %H:%M"),
                "timestamp": datetime.now().isoformat(),
                "request_id": request_id or "N/A",
                
                # Basic invoice information with filename fallback
                "invoice_number": clean_field_value(invoice_data.get("rechnungsnummer")),
                "invoice_display_name": get_display_name(invoice_data),
                "supplier_name": clean_field_value(invoice_data.get("lieferant")),
                "invoice_date": clean_field_value(invoice_data.get("rechnungsdatum")),
                "total_amount": invoice_data.get("rechnungsbetrag"),
                "currency": invoice_data.get("currency", "EUR"),
                "status": "Bearbeitung abgeschlossen",
                
                # Comprehensive invoice fields
                "rechnungsempfaenger": clean_field_value(invoice_data.get("rechnungsempfaenger")),
                "rechnungssteller": clean_field_value(invoice_data.get("rechnungssteller")),
                "rechnungseingang": clean_field_value(invoice_data.get("rechnungseingang")),
                
                # Project and trade information
                "projekt": clean_field_value(invoice_data.get("projekt")),
                "gewerk": clean_field_value(invoice_data.get("gewerk")),
                "kostenstelle": clean_field_value(invoice_data.get("kostenstelle")),
                "weiter_berechnen_an": clean_field_value(invoice_data.get("weiter_berechnen_an")),
                
                # Financial details
                "rechnungsbetrag": invoice_data.get("rechnungsbetrag"),
                "faelligkeit": clean_field_value(invoice_data.get("faelligkeit")),
                "skonto_datum": clean_field_value(invoice_data.get("skonto_datum")),
                "skonto_prozent": clean_field_value(invoice_data.get("skonto_prozent")),
                "rechnungsart": clean_field_value(invoice_data.get("rechnungsart")),
                "kfw_anrechenbare_kosten": clean_field_value(invoice_data.get("kfw_anrechenbare_kosten")),
                
                # Additional information
                "netto_brutto": clean_field_value(invoice_data.get("netto_brutto")),
                "mwst_satz": clean_field_value(invoice_data.get("mwst_satz")),
                "kontierung": clean_field_value(invoice_data.get("kontierung")),
                
                # Workflow information
                "bauleiter_email": clean_field_value(invoice_data.get("bauleiter_email")),
                "rechnungspruefung_email": clean_field_value(invoice_data.get("rechnungspruefung_email")),
                
                # PDF link - keep visual but make non-functional
                "pdf_url": None,
                "has_pdf": bool(invoice_data.get("file_path")),
                
                # Changes summary
                "changes_summary": changes_summary or []
            }
            
            # Generate PDF URL if file path exists
            if invoice_data.get("file_path"):
                from services.pdf_url_service import pdf_url_service
                context["pdf_url"] = pdf_url_service.get_pdf_url(invoice_data["file_path"])
            
            # Choose template and subject based on completion status
            if is_completion:
                # Formal completion email
                template = self.jinja_env.get_template("editor_notification")
                subject = f"{context['invoice_display_name']}"
                context["status"] = "Bearbeitung abgeschlossen"
            else:
                # Summary so far email
                template = self.jinja_env.get_template("editor_summary")
                subject = f"{context['invoice_display_name']}"
                context["status"] = "In Bearbeitung"
            
            html_content = template.render(**context)
            
            # Send email
            result = await self._send_email(
                to_email=editor_email,
                to_name=editor_name,
                subject=subject,
                html_content=html_content,
                email_type="editor_notification",
                invoice_id=invoice_data.get("id"),
                template_used="editor_notification"
            )
            
            if result["success"]:
                # Update invoice status and log email send
                await self._update_invoice_after_email_send(
                    invoice_id=invoice_data["id"],
                    email_type="editor_notification",
                    result=result
                )
                
                logger.info(f"Editor notification sent successfully to {editor_email} for invoice {invoice_data.get('id')}")
                
            return result
            
        except Exception as e:
            logger.error(f"Failed to send editor notification: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message_id": None
            }
    
    async def send_bauleiter_approval_request(
        self,
        invoice_data: Dict[str, Any],
        bauleiter_email: str,
        editor_name: str,
        editor_email: str,
        changes_summary: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Send approval request to Bau-Leiter with secure approval/rejection links.
        """
        try:
            # Generate secure approval tokens
            approve_token = await self._generate_approval_token(
                invoice_id=invoice_data["id"],
                action="approve",
                user_email=bauleiter_email
            )
            
            reject_token = await self._generate_approval_token(
                invoice_id=invoice_data["id"],
                action="reject",
                user_email=bauleiter_email
            )
            
            # Build approval URLs
            approve_url = f"{self.base_url}/api/approval/{approve_token}"
            reject_url = f"{self.base_url}/api/approval/{reject_token}"
            
            # Generate PDF URL if file path exists
            pdf_url = None
            if invoice_data.get("file_path"):
                from services.pdf_url_service import pdf_url_service
                pdf_url = pdf_url_service.get_pdf_url(invoice_data["file_path"])
            
            # Helper function to clean placeholder values
            def clean_field_value(value):
                """Replace placeholder/default values with 'Nicht eingegeben'"""
                if not value or value in [
                    'Projekt auswählen...', 'Gewerk auswählen...', 'Abteilung oder Kontakt auswählen...',
                    'Typ auswählen...', 'dd.mm.yyyy', 'mm.yyyy', 'yyyy', '0.00', '0,00'
                ]:
                    return 'Nicht eingegeben'
                return value

            # Helper function to get display name (filename fallback)
            def get_display_name(invoice_data):
                """Get display name for invoice - use filename if invoice number is missing"""
                invoice_number = clean_field_value(invoice_data.get("rechnungsnummer"))
                if invoice_number == 'Nicht eingegeben' and invoice_data.get("file_path"):
                    # Extract filename from file_path
                    filename = invoice_data["file_path"].split("/")[-1]
                    # Remove file extension for cleaner display
                    if filename.endswith('.pdf'):
                        filename = filename[:-4]
                    return filename
                return invoice_number if invoice_number != 'Nicht eingegeben' else 'Rechnung ohne Nummer'

            # Prepare comprehensive template context with ALL invoice fields
            context = {
                # Email metadata
                "submission_date": datetime.now().strftime("%d.%m.%Y um %H:%M"),
                "editor_name": editor_name,
                "editor_email": editor_email,
                "timestamp": datetime.now().isoformat(),
                "email_id": f"INV-{invoice_data.get('id', 'N/A')}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "changes_summary": changes_summary or [],
                "approve_url": approve_url,
                "reject_url": reject_url,
                "token_expires": (datetime.now() + timedelta(days=7)).strftime("%d.%m.%Y um %H:%M"),
                "pdf_url": pdf_url,
                "has_pdf": bool(invoice_data.get("file_path")),
                
                # Basic invoice information with filename fallback
                "invoice_number": clean_field_value(invoice_data.get("rechnungsnummer")),
                "invoice_display_name": get_display_name(invoice_data),
                "supplier_name": clean_field_value(invoice_data.get("lieferant")),
                "invoice_date": clean_field_value(invoice_data.get("rechnungsdatum")),
                "total_amount": invoice_data.get("rechnungsbetrag"),
                "currency": invoice_data.get("currency", "EUR"),
                
                # German business fields - comprehensive invoice data
                "rechnungsempfaenger": clean_field_value(invoice_data.get("rechnungsempfaenger")),
                "rechnungssteller": clean_field_value(invoice_data.get("rechnungssteller")),
                "projekt": clean_field_value(invoice_data.get("projekt")),
                "gewerk": clean_field_value(invoice_data.get("gewerk")),
                "kostenstelle": clean_field_value(invoice_data.get("kostenstelle")),
                "rechnungseingang": invoice_data.get("rechnungseingang"),
                "faelligkeit": invoice_data.get("faelligkeit"),
                "skonto_datum": invoice_data.get("skonto_datum"),
                "skonto_prozent": invoice_data.get("skonto_prozent"),
                "kfw_anrechenbare_kosten": invoice_data.get("kfw_anrechenbare_kosten"),
                "weiter_berechnen_an": invoice_data.get("weiter_berechnen_an"),
                
                # Additional financial information
                "material_kosten": invoice_data.get("material_kosten"),
                "lohn_kosten": invoice_data.get("lohn_kosten"),
                "bestellnummer": invoice_data.get("bestellnummer"),
                "liefertermin": invoice_data.get("liefertermin"),
                "aufmass_datum": invoice_data.get("aufmass_datum"),
                
                # Status and workflow information
                "status": invoice_data.get("status", "zur_genehmigung"),
                "review_status": invoice_data.get("review_status", "pending"),
                "created_at": invoice_data.get("created_at"),
                "updated_at": invoice_data.get("updated_at")
            }
            
            # Render template
            template = self.jinja_env.get_template("bauleiter_approval")
            html_content = template.render(**context)
            
            # Email details
            subject = f"{context['invoice_display_name']}"
            
            # Send email
            result = await self._send_email(
                to_email=bauleiter_email,
                to_name="Bau-Leiter",
                subject=subject,
                html_content=html_content,
                email_type="bauleiter_approval",
                invoice_id=invoice_data.get("id"),
                template_used="bauleiter_approval"
            )
            
            if result["success"]:
                # Update invoice status
                await self._update_invoice_after_bauleiter_email(
                    invoice_id=invoice_data["id"],
                    bauleiter_email=bauleiter_email,
                    result=result
                )
                
                logger.info(f"Bau-Leiter approval request sent to {bauleiter_email} for invoice {invoice_data.get('id')}")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to send Bau-Leiter approval request: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message_id": None
            }
    
    async def send_dropdown_change_notification(
        self,
        user_email: str,
        changes: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Send notification email about dropdown option changes.
        """
        try:
            # Prepare template context
            context = {
                "user_email": user_email,
                "changes": changes,
                "timestamp": datetime.now().strftime("%d.%m.%Y um %H:%M"),
                "iso_timestamp": datetime.now().isoformat()
            }
            
            # Render template
            template = self.jinja_env.get_template("dropdown_change_notification")
            html_content = template.render(**context)
            
            # Email details
            subject = f"Dropdown Options Updated - {len(changes)} changes"
            
            # Send email
            result = await self._send_email(
                to_email=user_email,
                to_name=user_email.split('@')[0].title(),
                subject=subject,
                html_content=html_content,
                email_type="dropdown_change_notification",
                invoice_id=None,
                template_used="dropdown_change_notification"
            )
            
            if result["success"]:
                logger.info(f"Dropdown change notification sent successfully to {user_email}")
                
            return result
            
        except Exception as e:
            logger.error(f"Failed to send dropdown change notification: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message_id": None
            }
    
    async def send_skonto_reminder(
        self,
        invoice_data: Dict[str, Any],
        recipient_email: str,
        recipient_name: str = None,
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send Skonto reminder email to stakeholder.
        
        Args:
            invoice_data: Invoice data including Skonto information
            recipient_email: Email address to send reminder to
            recipient_name: Name of recipient (optional)
            request_id: Request ID for tracking (optional)
        """
        try:
            # Validate Skonto data
            skonto_datum = invoice_data.get("skonto_datum")
            skonto_prozent = invoice_data.get("skonto_prozent")
            total_amount = invoice_data.get("rechnungsbetrag")
            
            if not skonto_datum or not skonto_prozent or not total_amount:
                return {
                    "success": False,
                    "error": "Missing required Skonto data (datum, prozent, or total_amount)"
                }
            
            # Calculate days until expiry
            from datetime import datetime, timedelta
            try:
                if isinstance(skonto_datum, str):
                    # Handle different date formats
                    if "." in skonto_datum:
                        skonto_date = datetime.strptime(skonto_datum, "%d.%m.%Y")
                    elif "-" in skonto_datum:
                        skonto_date = datetime.strptime(skonto_datum, "%Y-%m-%d")
                    else:
                        skonto_date = datetime.strptime(skonto_datum, "%Y%m%d")
                else:
                    skonto_date = skonto_datum
                
                days_until_expiry = (skonto_date - datetime.now()).days
            except (ValueError, TypeError) as e:
                logger.error(f"Failed to parse Skonto date {skonto_datum}: {e}")
                return {
                    "success": False,
                    "error": f"Invalid Skonto date format: {skonto_datum}"
                }
            
            # Calculate potential savings
            try:
                potential_savings = round(float(total_amount) * float(skonto_prozent) / 100, 2)
            except (ValueError, TypeError):
                potential_savings = 0
            
            # Create approval tokens for Skonto actions
            token_data = {
                "action_type": "skonto_decision",
                "invoice_id": invoice_data.get("id"),
                "recipient_email": recipient_email,
                "metadata": {
                    "potential_savings": potential_savings,
                    "skonto_prozent": skonto_prozent,
                    "skonto_datum": skonto_datum
                }
            }
            
            # Create tokens for take and skip actions using the helper method
            try:
                take_token = await self._generate_approval_token(
                    invoice_id=UUID(invoice_data.get("id")),
                    action="skonto_taken",
                    user_email=recipient_email
                )
                skip_token = await self._generate_approval_token(
                    invoice_id=UUID(invoice_data.get("id")),
                    action="skonto_missed",
                    user_email=recipient_email
                )
                
                # Set token expiry (7 days from now)
                token_expires = (datetime.now() + timedelta(days=7)).isoformat()
                
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Failed to create approval tokens for Skonto decision: {str(e)}"
                }
            
            # Build action URLs
            take_skonto_url = f"{self.base_url}/api/email/skonto-decision?token={take_token}&decision=taken"
            skip_skonto_url = f"{self.base_url}/api/email/skonto-decision?token={skip_token}&decision=missed"
            
            # Helper function to clean placeholder values
            def clean_field_value(value):
                """Replace placeholder/default values with 'Nicht eingegeben'"""
                if not value or value in [
                    'Projekt auswählen...', 'Gewerk auswählen...', 'Abteilung oder Kontakt auswählen...',
                    'Typ auswählen...', 'dd.mm.yyyy', 'mm.yyyy', 'yyyy', '0.00', '0,00'
                ]:
                    return 'Nicht eingegeben'
                return value

            # Helper function to get display name (filename fallback)
            def get_display_name(invoice_data):
                """Get display name for invoice - use filename if invoice number is missing"""
                invoice_number = clean_field_value(invoice_data.get("rechnungsnummer"))
                if invoice_number == 'Nicht eingegeben' and invoice_data.get("file_path"):
                    # Extract filename from file_path
                    filename = invoice_data["file_path"].split("/")[-1]
                    # Remove file extension for cleaner display
                    if filename.endswith('.pdf'):
                        filename = filename[:-4]
                    return filename
                return invoice_number if invoice_number != 'Nicht eingegeben' else 'Rechnung ohne Nummer'

            # Prepare template context
            context = {
                "recipient_name": recipient_name or recipient_email.split("@")[0],
                "recipient_email": recipient_email,
                "timestamp": datetime.now().isoformat(),
                "request_id": request_id or "N/A",
                "invoice_number": clean_field_value(invoice_data.get("rechnungsnummer")),
                "invoice_display_name": get_display_name(invoice_data),
                "supplier_name": clean_field_value(invoice_data.get("lieferant")),
                "invoice_date": clean_field_value(invoice_data.get("rechnungsdatum")),
                "total_amount": total_amount,
                "currency": invoice_data.get("currency", "EUR"),
                "skonto_datum": skonto_datum,
                "skonto_prozent": skonto_prozent,
                "days_until_expiry": days_until_expiry,
                "potential_savings": potential_savings,
                "take_skonto_url": take_skonto_url,
                "skip_skonto_url": skip_skonto_url,
                "token_expires": token_expires,
                "email_id": f"SKONTO-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            }
            
            # Render email template
            template = self.jinja_env.get_template("skonto_reminder")
            html_content = template.render(**context)
            
            # Determine subject urgency
            if days_until_expiry <= 1:
                urgency = "🚨 DRINGEND"
            elif days_until_expiry <= 3:
                urgency = "⚠️ WICHTIG"
            else:
                urgency = "📋"
                
            subject = f"{context['invoice_display_name']}"
            
            # Send email
            result = await self._send_email(
                to_email=recipient_email,
                to_name=recipient_name or recipient_email.split("@")[0],
                subject=subject,
                html_content=html_content,
                invoice_id=invoice_data.get("id"),
                email_type="skonto_reminder",
                template_used="skonto_reminder"
            )
            
            if result["success"]:
                # Update database with reminder sent status
                reminder_result = db_service.update_skonto_reminder_sent(
                    invoice_id=invoice_data.get("id")
                )
                
                if not reminder_result["success"]:
                    logger.warning(f"Failed to update Skonto reminder status: {reminder_result.get('error')}")
                
                logger.info(f"✅ Skonto reminder sent successfully to {recipient_email} for invoice {invoice_data.get('id')}")
                return {
                    "success": True,
                    "message": f"Skonto reminder sent successfully to {recipient_email}",
                    "message_id": result.get("message_id"),
                    "timestamp": datetime.now().isoformat(),
                    "potential_savings": potential_savings,
                    "days_until_expiry": days_until_expiry
                }
            else:
                logger.error(f"❌ Failed to send Skonto reminder: {result.get('error')}")
                return result
                
        except Exception as e:
            logger.error(f"❌ Exception in send_skonto_reminder: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    # =============================================================================
    # PRIVATE HELPER METHODS
    # =============================================================================
    async def _send_email(
        self,
        to_email: str,
        to_name: str,
        subject: str,
        html_content: str,
        email_type: str,
        invoice_id: Optional[UUID] = None,
        template_used: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send email using configured provider with audit logging.
        """
        start_time = datetime.now()
        email_size = len(html_content.encode('utf-8'))
        
        try:
            # Demo mode - just log the email
            if self.demo_mode:
                logger.info(f"📧 DEMO MODE: Email would be sent to {to_email}")
                logger.info(f"   Subject: {subject}")
                logger.info(f"   Type: {email_type}")
                # Keep a copy so the links in the mail can be clicked locally
                outbox_dir = Path(os.getenv("EMAIL_OUTBOX_DIR", "outbox"))
                outbox_dir.mkdir(parents=True, exist_ok=True)
                outbox_file = outbox_dir / f"{start_time:%Y%m%d_%H%M%S}_{email_type}.html"
                outbox_file.write_text(html_content, encoding="utf-8")
                logger.info(f"   Saved to: {outbox_file.resolve()}")
                return {
                    "success": True,
                    "provider": "demo",
                    "message_id": f"demo-{secrets.token_hex(8)}",
                    "response": {"demo_mode": True, "logged_only": True}
                }
            
            # Check if SendGrid is configured
            if not self.sendgrid_api_key:
                raise ValueError("SendGrid API key not configured. Please set SENDGRID_API_KEY environment variable.")
            
            # Send via SendGrid only
            result = await self._send_via_sendgrid(to_email, to_name, subject, html_content)
            
            if result["success"]:
                result["provider"] = "sendgrid"
                logger.info(f"✅ Email sent successfully via SendGrid to {to_email}")
            else:
                raise Exception(f"SendGrid failed: {result.get('error', 'Unknown error')}")
            
            # Log email send attempt
            await self._log_email_send(
                invoice_id=invoice_id,
                email_type=email_type,
                recipient_email=to_email,
                subject=subject,
                send_success=result["success"],
                provider_message_id=result.get("message_id"),
                provider_response=result.get("response"),
                template_used=template_used,
                email_size_bytes=email_size
            )
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Email send failed: {str(e)}")
            
            # Log failed send attempt
            await self._log_email_send(
                invoice_id=invoice_id,
                email_type=email_type,
                recipient_email=to_email,
                subject=subject,
                send_success=False,
                provider_message_id=None,
                provider_response={"error": str(e)},
                template_used=template_used,
                email_size_bytes=email_size
            )
            
            return {
                "success": False,
                "error": str(e),
                "provider": "sendgrid"
            }
    
    async def _send_via_sendgrid(self, to_email: str, to_name: str, subject: str, html_content: str) -> Dict[str, Any]:
        """Send email via SendGrid"""
        try:
            # Fix SSL certificate issue by setting the CA bundle
            import certifi
            import os
            
            # Set the CA bundle path for SSL verification
            original_ca_bundle = os.environ.get('REQUESTS_CA_BUNDLE')
            os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
            os.environ['SSL_CERT_FILE'] = certifi.where()
            
            try:
                sg = SendGridAPIClient(api_key=self.sendgrid_api_key)
                message = Mail(
                    from_email=(self.from_email, self.from_name),
                    to_emails=[(to_email, to_name)],
                    subject=subject,
                    html_content=html_content
                )
                
                response = sg.send(message)
                
            finally:
                # Restore original environment
                if original_ca_bundle:
                    os.environ['REQUESTS_CA_BUNDLE'] = original_ca_bundle
                else:
                    os.environ.pop('REQUESTS_CA_BUNDLE', None)
            
            return {
                "success": True,
                "message_id": response.headers.get("X-Message-Id"),
                "response": {
                    "status_code": response.status_code,
                    "headers": dict(response.headers)
                }
            }
            
        except Exception as e:
            logger.error(f"SendGrid send failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "response": None
            }

    
    async def _generate_approval_token(self, invoice_id: UUID, action: str, user_email: str) -> str:
        """Generate secure approval token with database storage"""
        try:
            # Generate secure token components
            token_data = {
                "invoice_id": str(invoice_id),
                "action": action,
                "user_email": user_email,
                "nonce": secrets.token_hex(16),
                "created_at": datetime.now().isoformat()
            }
            
            # Create JWT token
            jwt_token = jwt.encode(
                token_data,
                self.jwt_secret,
                algorithm="HS256"
            )
            
            # Hash token for database storage
            token_hash = hashlib.sha256(jwt_token.encode()).hexdigest()
            
            # Store in database using database service method
            expires_at = datetime.now() + timedelta(days=7)
            
            # Use database service to create approval token
            token_result = db_service.create_approval_token(
                token_hash=token_hash,
                invoice_id=str(invoice_id),
                action=action,
                user_email=user_email,
                expires_at=expires_at,
                nonce=token_data["nonce"]
            )
            
            if not token_result.get("success"):
                raise Exception(f"Failed to store approval token: {token_result.get('error')}")
            
            return jwt_token
            
        except Exception as e:
            logger.error(f"Failed to generate approval token: {str(e)}")
            raise e
    
    async def _update_invoice_after_email_send(self, invoice_id: UUID, email_type: str, result: Dict[str, Any]):
        """Update invoice email-related fields after successful email send (NO status changes)"""
        try:
            if email_type == "editor_notification":
                # Use database service to update ONLY email-related fields, not status
                email_log_entry = json.dumps([{
                    "type": "editor_notification",
                    "sent_at": datetime.now().isoformat(),
                    "success": result["success"],
                    "message_id": result.get("message_id")
                }])
                
                # Call database service method for email logging (no status change)
                update_result = db_service.log_email_send(
                    invoice_id=str(invoice_id),
                    email_type=email_type,
                    log_entry=email_log_entry
                )
                
                if not update_result.get("success"):
                    logger.warning(f"Failed to log email send: {update_result.get('error')}")
                
        except Exception as e:
            logger.error(f"Failed to update invoice after email send: {str(e)}")
            raise e
    
    async def _update_invoice_after_bauleiter_email(self, invoice_id: UUID, bauleiter_email: str, result: Dict[str, Any]):
        """Update invoice email-related fields after Bau-Leiter email send (NO status changes)"""
        try:
            # Use database service to update ONLY email-related fields, not status
            email_log_entry = json.dumps([{
                "type": "bauleiter_approval",
                "sent_at": datetime.now().isoformat(),
                "success": result["success"],
                "message_id": result.get("message_id")
            }])
            
            # Call database service method to update email fields only
            update_result = db_service.update_bauleiter_email_sent(
                invoice_id=str(invoice_id),
                bauleiter_email=bauleiter_email,
                log_entry=email_log_entry
            )
            
            if not update_result.get("success"):
                logger.warning(f"Failed to log Bauleiter email send: {update_result.get('error')}")
            
        except Exception as e:
            logger.error(f"Failed to update invoice after Bau-Leiter email: {str(e)}")
            raise e
    
    async def _log_email_send(
        self,
        invoice_id: Optional[UUID],
        email_type: str,
        recipient_email: str,
        subject: str,
        send_success: bool,
        provider_message_id: Optional[str] = None,
        provider_response: Optional[Dict] = None,
        template_used: Optional[str] = None,
        email_size_bytes: Optional[int] = None
    ):
        """Log email send attempt to audit table"""
        try:
            # Skip audit logging for test emails without invoice_id
            if not invoice_id and email_type == 'test':
                logger.info(f"📧 Skipping audit log for test email to {recipient_email}")
                return
                
            # Use database service to create email audit log
            audit_result = db_service.create_email_audit_log(
                invoice_id=str(invoice_id) if invoice_id else None,
                email_type=email_type,
                recipient_email=recipient_email,
                subject=subject,
                send_success=send_success,
                provider_message_id=provider_message_id,
                provider_response=provider_response,
                template_used=template_used,
                email_size_bytes=email_size_bytes
            )
            
            if not audit_result.get("success"):
                logger.warning(f"Failed to log email audit: {audit_result.get('error')}")
            
        except Exception as e:
            logger.error(f"Failed to log email send: {str(e)}")
            # Don't raise - this is audit logging and shouldn't break the main flow

# Global email service instance
email_service = EmailService()
