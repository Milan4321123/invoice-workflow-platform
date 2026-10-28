"""Database-backed dropdown options management with fallback to hardcoded options"""
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any, Optional
import logging
from pydantic import BaseModel

# Import centralized database service
from services.database import db_service
from services.dropdown_labels import invalidate as invalidate_labels

router = APIRouter()
logger = logging.getLogger(__name__)

class DropdownOption(BaseModel):
    """Model for dropdown option"""
    value: str
    label: str
    is_default: bool = False

class AddOptionRequest(BaseModel):
    """Model for adding new option to dropdown"""
    field_name: str
    value: str
    label: Optional[str] = None

class UpdateOptionRequest(BaseModel):
    """Model for updating an existing dropdown option"""
    field_name: str
    old_value: str
    new_value: str
    new_label: Optional[str] = None

# Fallback hardcoded options (used when database is unavailable)
# These serve as both fallback data and initial migration data
FALLBACK_DROPDOWN_OPTIONS = {
    "rechnungsempfaenger": [
        {"value": "acme_construction", "label": "ACME Construction GmbH", "is_default": True},
        {"value": "baumeister_gmbh", "label": "Baumeister GmbH", "is_default": True},
        {"value": "hochbau_services", "label": "Hochbau Services AG", "is_default": True},
        {"value": "zimmerei_mueller", "label": "Zimmerei Müller & Co", "is_default": True},
        {"value": "stadtwerke_berlin", "label": "Stadtwerke Berlin", "is_default": True},
    ],
    "rechnungssteller": [
        {"value": "elektro_wagner", "label": "Elektro Wagner GmbH", "is_default": True},
        {"value": "sanitaer_schmidt", "label": "Sanitär Schmidt & Söhne", "is_default": True},
        {"value": "dach_decken_pro", "label": "Dach & Decken Pro GmbH", "is_default": True},
        {"value": "heizung_klima_expert", "label": "Heizung & Klima Expert", "is_default": True},
        {"value": "baumarkt_zentrale", "label": "Baumarkt Zentrale AG", "is_default": True},
        {"value": "malerbetrieb_weiss", "label": "Malerbetrieb Weiß", "is_default": True},
    ],
    "projekt": [
        {"value": "wohnbau_mitte_2024", "label": "Wohnbau Mitte 2024", "is_default": True},
        {"value": "buerocomplex_nord", "label": "Bürokomplex Nord", "is_default": True},
        {"value": "sanierung_altbau_sued", "label": "Sanierung Altbau Süd", "is_default": True},
        {"value": "neubau_kindergarten", "label": "Neubau Kindergarten", "is_default": True},
        {"value": "umbau_fabrikhalle", "label": "Umbau Fabrikhalle", "is_default": True},
        {"value": "energetische_sanierung", "label": "Energetische Sanierung Ost", "is_default": True},
    ],
    "gewerk": [
        {"value": "elektroinstallation", "label": "Elektroinstallation", "is_default": True},
        {"value": "sanitaerinstallation", "label": "Sanitärinstallation", "is_default": True},
        {"value": "heizung_lueftung", "label": "Heizung & Lüftung", "is_default": True},
        {"value": "dacharbeiten", "label": "Dacharbeiten", "is_default": True},
        {"value": "maurerarbeiten", "label": "Maurerarbeiten", "is_default": True},
        {"value": "malerarbeiten", "label": "Malerarbeiten", "is_default": True},
        {"value": "bodenverlegung", "label": "Bodenverlegung", "is_default": True},
        {"value": "fenster_tueren", "label": "Fenster & Türen", "is_default": True},
        {"value": "zimmerei", "label": "Zimmerei", "is_default": True},
        {"value": "geruestbau", "label": "Gerüstbau", "is_default": True},
    ],
    "weiter_berechnen_an": [
        {"value": "bauleitung", "label": "Bauleitung", "is_default": True},
        {"value": "projektmanagement", "label": "Projektmanagement", "is_default": True},
        {"value": "buchhaltung", "label": "Buchhaltung", "is_default": True},
        {"value": "auftraggeber", "label": "Auftraggeber", "is_default": True},
        {"value": "externe_pruefung", "label": "Externe Prüfung", "is_default": True},
    ]
}

# No in-memory storage - using only Supabase database

# Database helper functions
def _get_dropdown_options_from_db(field_name: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
    """Get dropdown options from database"""
    db_options = db_service.get_dropdown_options(field_name)
    
    if not db_options:
        logger.warning("Database unavailable, using fallback options")
        if field_name:
            return {field_name: FALLBACK_DROPDOWN_OPTIONS.get(field_name, [])}
        return FALLBACK_DROPDOWN_OPTIONS
    
    return db_options

def _add_dropdown_option_to_db(field_name: str, value: str, label: str, is_default: bool = False, metadata: Dict = None) -> Dict[str, Any]:
    """Add a new dropdown option to database"""
    result = db_service.add_dropdown_option(field_name, value, label, is_default, metadata)
    invalidate_labels()
    return result

def _delete_dropdown_option_from_db(field_name: str, value: str) -> Dict[str, Any]:
    """Delete a dropdown option from database (soft delete - set is_active=false)"""
    result = db_service.delete_dropdown_option(field_name, value)
    invalidate_labels()
    return result

def _get_valid_field_names() -> List[str]:
    """Get list of valid field names (from fallback or database)"""
    return list(FALLBACK_DROPDOWN_OPTIONS.keys())

def _get_all_options_for_field(field_name: str) -> List[Dict[str, Any]]:
    """Get all options from database only"""
    if field_name not in _get_valid_field_names():
        return []
    
    # Get options from database only
    db_options = _get_dropdown_options_from_db(field_name)
    return db_options.get(field_name, [])

@router.get("/dropdowns/stats")
async def get_dropdown_stats():
    """Get statistics about dropdown options"""
    stats = {}
    total_options = 0
    valid_field_names = _get_valid_field_names()
    
    for field_name in valid_field_names:
        # Get options from database only
        db_options = _get_dropdown_options_from_db(field_name)
        all_options = db_options.get(field_name, [])
        
        default_count = len([opt for opt in all_options if opt.get("is_default", False)])
        custom_count = len([opt for opt in all_options if not opt.get("is_default", False)])
        field_total = len(all_options)
        
        stats[field_name] = {
            "default_options": default_count,
            "custom_options": custom_count,
            "total_options": field_total
        }
        total_options += field_total
    
    return {
        "field_stats": stats,
        "total_options": total_options,
        "total_fields": len(valid_field_names)
    }

@router.get("/dropdowns/{field_name}")
async def get_dropdown_options(field_name: str):
    """Get all dropdown options for a specific field"""
    if field_name not in _get_valid_field_names():
        raise HTTPException(status_code=400, detail=f"Invalid field name: {field_name}")
    
    all_options = _get_all_options_for_field(field_name)
    
    return {
        "field_name": field_name,
        "options": all_options,
        "total": len(all_options)
    }

@router.get("/dropdowns")
async def get_all_dropdown_options():
    """Get all dropdown options for all fields"""
    valid_field_names = _get_valid_field_names()

    # One query for all fields instead of one per field
    db_options = _get_dropdown_options_from_db()
    all_dropdowns = {
        field_name: db_options.get(field_name) or FALLBACK_DROPDOWN_OPTIONS[field_name]
        for field_name in valid_field_names
    }
    
    return {
        "dropdowns": all_dropdowns,
        "field_names": valid_field_names
    }

@router.post("/dropdowns/add-option")
async def add_dropdown_option(request: AddOptionRequest):
    """Add a new option to a dropdown field"""
    if request.field_name not in _get_valid_field_names():
        raise HTTPException(status_code=400, detail=f"Invalid field name: {request.field_name}")
    
    if not request.value or not request.value.strip():
        raise HTTPException(status_code=400, detail="Option value cannot be empty")
    
    # Use label or default to value
    label = request.label if request.label and request.label.strip() else request.value
    
    # Generate a safe value from the label if not provided
    safe_value = request.value.lower().replace(" ", "_").replace("&", "and").replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    
    # Get existing options to check for exact duplicates
    existing_options = _get_all_options_for_field(request.field_name)
    existing_values = [opt["value"] for opt in existing_options]
    
    # Check for exact value duplicate
    if safe_value in existing_values:
        existing_option = next(opt for opt in existing_options if opt["value"] == safe_value)
        return {
            "success": True,
            "message": f"Option already exists in {request.field_name}",
            "option": existing_option
        }
    
    # Add the new option
    new_option = {
        "value": safe_value,
        "label": label,
        "is_default": False
    }
    
    # Try to persist to database
    db_result = _add_dropdown_option_to_db(request.field_name, safe_value, label, is_default=False)
    
    if not db_result.get("success"):
        raise HTTPException(status_code=500, detail=f"Failed to add option to database: {db_result.get('error', 'Unknown error')}")
    
    logger.info(f"Successfully added option to database: {request.field_name} - {label}")
    
    return {
        "success": True,
        "message": f"Option added to {request.field_name}",
        "option": new_option
    }

@router.delete("/dropdowns/{field_name}/{option_value}")
async def delete_dropdown_option(field_name: str, option_value: str):
    """Delete a custom dropdown option (cannot delete default options)"""
    if field_name not in _get_valid_field_names():
        raise HTTPException(status_code=400, detail=f"Invalid field name: {field_name}")
    
    # Get all options from database 
    db_options = _get_dropdown_options_from_db(field_name)
    all_options = db_options.get(field_name, [])
    
    # Find the option to delete
    option_to_delete = None
    for opt in all_options:
        if opt["value"] == option_value:
            option_to_delete = opt
            break
    
    if not option_to_delete:
        raise HTTPException(status_code=404, detail=f"Option '{option_value}' not found in {field_name}")
    
    # Allow deletion of ALL options (removed default option protection)
    # Delete from database (soft delete)
    db_result = _delete_dropdown_option_from_db(field_name, option_value)
    
    if not db_result.get("success"):
        raise HTTPException(status_code=500, detail=f"Failed to delete option from database: {db_result.get('error', 'Unknown error')}")
    
    option_type = "default" if option_to_delete.get("is_default", False) else "custom"
    logger.info(f"Deleted {option_type} option from {field_name}: {option_value}")
    
    return {
        "success": True,
        "message": f"Option '{option_value}' deleted from {field_name}",
        "deleted_option": option_value,
        "deleted_from_db": True
    }

@router.put("/dropdowns/update-option")
async def update_dropdown_option(request: UpdateOptionRequest):
    """Update an existing dropdown option"""
    if request.field_name not in _get_valid_field_names():
        raise HTTPException(status_code=400, detail=f"Invalid field name: {request.field_name}")
    
    if not request.new_value or not request.new_value.strip():
        raise HTTPException(status_code=400, detail="New option value cannot be empty")
    
    # Generate safe value for the new value
    safe_new_value = request.new_value.lower().replace(" ", "_").replace("&", "and").replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    new_label = request.new_label if request.new_label and request.new_label.strip() else request.new_value
    
    # Check if the old option exists
    db_options = _get_dropdown_options_from_db(request.field_name)
    all_options = db_options.get(request.field_name, [])
    
    old_option = None
    for opt in all_options:
        if opt["value"] == request.old_value:
            old_option = opt
            break
    
    if not old_option:
        raise HTTPException(status_code=404, detail=f"Option '{request.old_value}' not found in {request.field_name}")
    
    # Check if new value already exists (and it's not the same option)
    if safe_new_value != request.old_value:
        existing_values = [opt["value"] for opt in all_options]
        if safe_new_value in existing_values:
            raise HTTPException(status_code=400, detail=f"Option with value '{safe_new_value}' already exists in {request.field_name}")
    
    # Update in database
    db_result = db_service.update_dropdown_option(request.field_name, request.old_value, safe_new_value, new_label)
    invalidate_labels()
    
    if not db_result.get("success"):
        raise HTTPException(status_code=500, detail=f"Failed to update option in database: {db_result.get('error', 'Unknown error')}")
    
    logger.info(f"Updated option in {request.field_name}: {request.old_value} -> {safe_new_value}")
    
    return {
        "success": True,
        "message": f"Option updated in {request.field_name}",
        "old_option": {"value": request.old_value, "label": old_option["label"]},
        "new_option": {"value": safe_new_value, "label": new_label, "is_default": old_option.get("is_default", False)}
    }