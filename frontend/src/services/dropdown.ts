/**
 * Dropdown options service for German invoice fields
 * Handles API communication for dropdown functionality
 */

import { API_CONFIG, buildApiUrl } from '@/config/api';
import { authFetch } from '@/lib/authFetch';

export interface DropdownOption {
  value: string;
  label: string;
  is_default: boolean;
}

export interface DropdownResponse {
  field_name: string;
  options: DropdownOption[];
  total: number;
}

export interface AllDropdownsResponse {
  dropdowns: Record<string, DropdownOption[]>;
  field_names: string[];
}

export interface AddOptionRequest {
  field_name: string;
  value: string;
  label?: string;
}

export interface AddOptionResponse {
  success: boolean;
  message?: string;
  option?: DropdownOption;
}

class DropdownService {
  /**
   * Get dropdown options for a specific field
   */
  async getDropdownOptions(fieldName: string): Promise<DropdownResponse> {
    const response = await authFetch(buildApiUrl(API_CONFIG.ENDPOINTS.DROPDOWNS.BY_FIELD(fieldName)));
    
    if (!response.ok) {
      throw new Error(`Failed to fetch dropdown options for ${fieldName}: ${response.statusText}`);
    }
    
    return response.json();
  }

  /**
   * Get all dropdown options for all fields
   */
  async getAllDropdownOptions(): Promise<AllDropdownsResponse> {
    const response = await authFetch(buildApiUrl(API_CONFIG.ENDPOINTS.DROPDOWNS.BASE));
    
    if (!response.ok) {
      throw new Error(`Failed to fetch all dropdown options: ${response.statusText}`);
    }
    
    return response.json();
  }

  /**
   * Add a new option to a dropdown field
   */
  async addDropdownOption(request: AddOptionRequest): Promise<AddOptionResponse> {
    const response = await authFetch(buildApiUrl(API_CONFIG.ENDPOINTS.DROPDOWNS.ADD_OPTION), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to add dropdown option');
    }
    
    return response.json();
  }

  /**
   * Delete a custom dropdown option (cannot delete default options)
   */
  async deleteDropdownOption(fieldName: string, optionValue: string): Promise<{ success: boolean }> {
    const response = await authFetch(buildApiUrl(API_CONFIG.ENDPOINTS.DROPDOWNS.DELETE_OPTION(fieldName, optionValue)), {
      method: 'DELETE',
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to delete dropdown option');
    }
    
    return response.json();
  }

  /**
   * Get German field labels for display
   */
  getFieldLabel(fieldName: string): string {
    const labels: Record<string, string> = {
      'rechnungsempfaenger': 'Rechnungsempfänger',
      'rechnungssteller': 'Rechnungssteller',
      'projekt': 'Projekt',
      'gewerk': 'Gewerk',
      'weiter_berechnen_an': 'Weiter berechnen an'
    };
    
    return labels[fieldName] || fieldName;
  }

  /**
   * Get all supported German field names
   */
  getSupportedFields(): string[] {
    return ['rechnungsempfaenger', 'rechnungssteller', 'projekt', 'gewerk', 'weiter_berechnen_an'];
  }
}

export const dropdownService = new DropdownService();
