'use client';

import React, { useState, useEffect } from 'react';
import { SearchableDropdown } from './SearchableDropdown';
import { dropdownService, DropdownOption } from '@/services/dropdown';
import { getApiUrl } from '@/config/api';
import { authFetch } from '@/lib/authFetch';
import TaxDetailsSection from './compliance/TaxDetailsSection';
import ComplianceChecklist from './compliance/ComplianceChecklist';

// German invoice field types
export interface GermanInvoiceFields {
  rechnungsempfaenger?: string;
  rechnungssteller?: string;
  projekt?: string;
  gewerk?: string;
  rechnungsbetrag?: number;
  rechnungseingang?: string;
  faelligkeit?: string;
  skonto_datum?: string;
  skonto_prozent?: number;
  rechnungsart?: string;
  kfw_anrechenbar?: boolean;
  rechnungspruefung_email?: string;
  weiter_berechnen_an?: string;
  // §14 Abs. 4 UStG, §13b UStG, §48b EStG
  rechnungsnummer?: string;
  rechnungsdatum?: string;
  leistungsdatum?: string;
  nettobetrag?: number | '';
  ust_satz?: number | '';
  ust_betrag?: number | '';
  lieferant_ust_id?: string;
  lieferant_steuernummer?: string;
  lieferant_iban?: string;
  reverse_charge_13b?: boolean;
  freistellung_48b_gueltig_bis?: string;
}

// Change tracking interfaces
interface PendingChange {
  type: 'add' | 'delete';
  fieldName: string;
  optionValue: string;
  optionLabel: string;
  timestamp: string;
}

interface CleanInvoiceFormProps {
  invoiceId?: string;
  fields: GermanInvoiceFields;
  onFieldChange: (fieldName: string, value: any) => void;
  onSave: () => void;
  onComplete?: () => void;
  isSaving?: boolean;
  isCompleting?: boolean;
  className?: string;
}

const CleanInvoiceForm: React.FC<CleanInvoiceFormProps> = ({
  invoiceId,
  fields,
  onFieldChange,
  onSave,
  onComplete,
  isSaving = false,
  isCompleting = false,
  className = ""
}) => {
  const [dropdownOptions, setDropdownOptions] = useState<Record<string, DropdownOption[]>>({
    rechnungsempfaenger: [],
    rechnungssteller: [],
    projekt: [],
    gewerk: [],
    weiter_berechnen_an: []
  });
  const [pendingChanges, setPendingChanges] = useState<PendingChange[]>([]);
  const [isCommittingChanges, setIsCommittingChanges] = useState(false);
  const [showPendingChangesDetails, setShowPendingChangesDetails] = useState(false);
  const [showSaveConfirmation, setShowSaveConfirmation] = useState(false);
  const [showInvoiceSaveConfirmation, setShowInvoiceSaveConfirmation] = useState(false);
  const [showInvoiceCompleteConfirmation, setShowInvoiceCompleteConfirmation] = useState(false);
  const [confirmationText, setConfirmationText] = useState('');

  // Load dropdown options from API
  const loadDropdownOptions = async () => {
    try {
      const response = await dropdownService.getAllDropdownOptions();
      setDropdownOptions(response.dropdowns);
    } catch (error) {
      console.error('Failed to load dropdown options:', error);
    }
  };

  useEffect(() => {
    loadDropdownOptions();
  }, []);

  // Helper function to get German field labels
  const getFieldLabel = (fieldName: string): string => {
    const labels: Record<string, string> = {
      'rechnungsempfaenger': 'Rechnungsempfänger',
      'rechnungssteller': 'Rechnungssteller',
      'projekt': 'Projekt',
      'gewerk': 'Gewerk',
      'weiter_berechnen_an': 'Weiter berechnen an'
    };
    return labels[fieldName] || fieldName;
  };

  // Helper function to group pending changes by field
  const groupPendingChangesByField = () => {
    const grouped: Record<string, PendingChange[]> = {};
    pendingChanges.forEach(change => {
      if (!grouped[change.fieldName]) {
        grouped[change.fieldName] = [];
      }
      grouped[change.fieldName].push(change);
    });
    return grouped;
  };

  // Helper function to format change summary
  const formatChangeDescription = (change: PendingChange): string => {
    const action = change.type === 'add' ? 'Hinzufügen' : 'Löschen';
    return `${action}: "${change.optionLabel}"`;
  };

  // Show save confirmation dialog
  const showSaveConfirmationDialog = () => {
    if (pendingChanges.length === 0) {
      alert('Keine ausstehenden Änderungen zum Speichern.');
      return;
    }
    setShowSaveConfirmation(true);
    setConfirmationText('');
  };

  // Handle confirmed save
  const handleConfirmedSave = async () => {
    if (confirmationText.toLowerCase() !== 'bestätigen') {
      alert('Bitte geben Sie "bestätigen" ein, um die Änderungen zu speichern.');
      return;
    }
    
    setShowSaveConfirmation(false);
    setConfirmationText('');
    await commitPendingChanges();
  };

  // Check if user has provided email before allowing changes
  const requireEmailForChanges = (): boolean => {
    const userEmail = fields.rechnungspruefung_email?.trim();
    if (!userEmail) {
      alert('Bitte geben Sie zuerst Ihre E-Mail-Adresse im Feld "Rechnungsprüfung Email" ein, bevor Sie Dropdown-Optionen bearbeiten können.');
      return false;
    }
    
    // Basic email validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(userEmail)) {
      alert('Bitte geben Sie eine gültige E-Mail-Adresse ein.');
      return false;
    }
    
    return true;
  };

  // Check if user has provided email before allowing save/complete actions
  const validateEmailForAction = (actionName: string): boolean => {
    const userEmail = fields.rechnungspruefung_email?.trim();
    if (!userEmail) {
      alert(`Bitte geben Sie zuerst Ihre E-Mail-Adresse im Feld "Rechnungsprüfung Email" ein, bevor Sie ${actionName} können.`);
      return false;
    }
    
    // Basic email validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(userEmail)) {
      alert('Bitte geben Sie eine gültige E-Mail-Adresse ein, um fortzufahren.');
      return false;
    }
    
    return true;
  };

  // Enhanced save handler with email validation and confirmation
  const handleSave = () => {
    if (!validateEmailForAction('die Rechnung zu speichern')) {
      return;
    }
    setShowInvoiceSaveConfirmation(true);
    setConfirmationText('');
  };

  // Enhanced complete handler with email validation and confirmation
  const handleComplete = () => {
    if (!validateEmailForAction('die Bearbeitung abschließen')) {
      return;
    }
    setShowInvoiceCompleteConfirmation(true);
    setConfirmationText('');
  };

  // Handle confirmed invoice save
  const handleConfirmedInvoiceSave = () => {
    if (confirmationText.toLowerCase() !== 'bestätigen') {
      alert('Bitte geben Sie "bestätigen" ein, um die Rechnung zu speichern.');
      return;
    }
    
    setShowInvoiceSaveConfirmation(false);
    setConfirmationText('');
    onSave();
  };

  // Handle confirmed invoice complete
  const handleConfirmedInvoiceComplete = () => {
    if (confirmationText.toLowerCase() !== 'bestätigen') {
      alert('Bitte geben Sie "bestätigen" ein, um die Bearbeitung abzuschließen.');
      return;
    }
    
    setShowInvoiceCompleteConfirmation(false);
    setConfirmationText('');
    if (onComplete) {
      onComplete();
    }
  };

  // Add change to pending list
  const addPendingChange = (change: Omit<PendingChange, 'timestamp'>) => {
    const newChange: PendingChange = {
      ...change,
      timestamp: new Date().toISOString()
    };
    
    setPendingChanges(prev => [...prev, newChange]);
  };

  // Remove individual pending change
  const removePendingChange = (changeIndex: number) => {
    setPendingChanges(prev => prev.filter((_, index) => index !== changeIndex));
  };

  // Remove all pending changes for a specific field
  const removePendingChangesForField = (fieldName: string) => {
    const fieldLabel = getFieldLabel(fieldName);
    const changeCount = pendingChanges.filter(change => change.fieldName === fieldName).length;
    
    if (confirm(`Möchten Sie wirklich alle ${changeCount} Änderung${changeCount !== 1 ? 'en' : ''} für "${fieldLabel}" entfernen?`)) {
      setPendingChanges(prev => prev.filter(change => change.fieldName !== fieldName));
    }
  };

  // Handle adding new dropdown option (staged)
  const handleAddNewOption = async (fieldName: string, newValue: string) => {
    if (!requireEmailForChanges()) {
      return;
    }

    // Add to local state immediately for UI feedback
    const newOption = {
      value: newValue.toLowerCase().replace(/\s+/g, '_'),
      label: newValue,
      is_default: false
    };

    setDropdownOptions(prev => ({
      ...prev,
      [fieldName]: [...prev[fieldName], newOption]
    }));

    // Track the change for later commit
    addPendingChange({
      type: 'add',
      fieldName,
      optionValue: newOption.value,
      optionLabel: newValue
    });

    // Set the new value in the form
    onFieldChange(fieldName, newOption.value);
  };

  // Handle deleting dropdown option (staged)
  const handleDeleteOption = async (fieldName: string, optionValue: string) => {
    const option = dropdownOptions[fieldName]?.find(opt => opt.value === optionValue);
    if (!option) return;

    if (!requireEmailForChanges()) {
      return;
    }

    // Remove from local state immediately for UI feedback
    setDropdownOptions(prev => ({
      ...prev,
      [fieldName]: prev[fieldName].filter(option => option.value !== optionValue)
    }));

    // Track the change for later commit
    addPendingChange({
      type: 'delete',
      fieldName,
      optionValue: option.value,
      optionLabel: option.label
    });

    // Clear field value if it was the deleted option
    if (fields[fieldName as keyof GermanInvoiceFields] === optionValue) {
      onFieldChange(fieldName, '');
    }
  };

  // Send email notification
  const sendChangeNotificationEmail = async (email: string, changes: any[]) => {
    console.log('🚀 sendChangeNotificationEmail called with:', { email, changes });
    
    try {
      console.log('📧 Making email request to /api/email/dropdown-change-notification');
      
      const response = await authFetch(`${getApiUrl()}/api/email/dropdown-change-notification`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_email: email,
          changes
        })
      });
      
      console.log('📨 Email response status:', response.status);
      
      if (!response.ok) {
        const errorData = await response.json();
        console.error('❌ Email response error:', errorData);
        throw new Error(errorData.detail || 'Failed to send email notification');
      }
      
      const result = await response.json();
      console.log('✅ Email notification sent successfully:', result.message_id);
      
    } catch (error) {
      console.error('❌ Email notification failed:', error);
      const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
      alert(`❌ Email failed: ${errorMessage}`);
    }
  };

  // Commit all pending changes to database and send email notification
  const commitPendingChanges = async () => {
    const userEmail = fields.rechnungspruefung_email?.trim();
    if (!userEmail) {
      alert('Bitte geben Sie zuerst Ihre E-Mail-Adresse im Feld "Rechnungsprüfung Email" ein.');
      return;
    }

    if (pendingChanges.length === 0) {
      return; // No changes to commit
    }

    setIsCommittingChanges(true);
    
    try {
      const results = [];
      
      for (const change of pendingChanges) {
        if (change.type === 'add') {
          const response = await dropdownService.addDropdownOption({
            field_name: change.fieldName,
            value: change.optionValue,
            label: change.optionLabel
          });
          results.push({...change, success: response.success});
        } else if (change.type === 'delete') {
          try {
            await dropdownService.deleteDropdownOption(change.fieldName, change.optionValue);
            results.push({...change, success: true});
          } catch (error) {
            results.push({...change, success: false, error: error});
          }
        }
      }

      // Send email notification
      await sendChangeNotificationEmail(userEmail, results);
      
      // Clear pending changes
      setPendingChanges([]);

      alert(`Änderungen erfolgreich gespeichert! Bestätigungs-E-Mail wurde an ${userEmail} gesendet.`);
      
    } catch (error) {
      console.error('Failed to commit changes:', error);
      alert('Fehler beim Speichern der Änderungen. Bitte versuchen Sie es erneut.');
    } finally {
      setIsCommittingChanges(false);
    }
  };

  return (
    <div className={`h-full flex flex-col ${className}`}>
      {/* Only Pending Changes Indicator - Floating */}
      {pendingChanges.length > 0 && (
        <div className="absolute top-4 right-4 z-10">
          <button
            onClick={() => setShowPendingChangesDetails(!showPendingChangesDetails)}
            className="flex items-center gap-2 px-3 py-1 bg-yellow-50 border border-yellow-200 rounded-lg hover:bg-yellow-100 transition-colors cursor-pointer shadow-lg"
            title="Klicken um Details zu sehen"
          >
            <div className="w-2 h-2 bg-yellow-500 rounded-full animate-pulse"></div>
            <span className="text-sm font-medium text-yellow-700">
              {pendingChanges.length}
            </span>
            <svg 
              className={`w-4 h-4 text-yellow-600 transition-transform ${showPendingChangesDetails ? 'rotate-180' : ''}`} 
              fill="none" 
              stroke="currentColor" 
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
        </div>
      )}

      {/* Pending Changes Details Panel */}
      {pendingChanges.length > 0 && showPendingChangesDetails && (
        <div className="bg-yellow-50 border-l-4 border-yellow-400 p-4 mx-6 mb-4 rounded-r-lg">
          <div className="flex items-start">
            <div className="flex-shrink-0">
              <svg className="h-5 w-5 text-yellow-400" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
              </svg>
            </div>
            <div className="ml-3 flex-1">
              <h3 className="text-sm font-medium text-yellow-800">
                Ausstehende Dropdown-Änderungen ({pendingChanges.length})
              </h3>
              <div className="mt-2 text-sm text-yellow-700">
                <p className="mb-3">Diese Änderungen werden gespeichert, wenn Sie auf „Dropdown-Änderungen speichern“ klicken:</p>
                
                {Object.entries(groupPendingChangesByField()).map(([fieldName, changes]) => (
                  <div key={fieldName} className="mb-3 last:mb-0">
                    <div className="flex items-center justify-between mb-1 group">
                      <div className="font-medium text-yellow-800">
                        📝 {getFieldLabel(fieldName)} ({changes.length} Änderung{changes.length !== 1 ? 'en' : ''}):
                      </div>
                      <button
                        onClick={() => removePendingChangesForField(fieldName)}
                        className="opacity-0 group-hover:opacity-100 transition-opacity text-xs px-2 py-1 text-red-600 hover:text-red-800 hover:bg-red-50 rounded"
                        title={`Alle ${getFieldLabel(fieldName)}-Änderungen entfernen`}
                      >
                        <svg className="w-3 h-3 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                        Alle entfernen
                      </button>
                    </div>
                    <ul className="ml-4 space-y-1">
                      {changes.map((change, changeIndex) => {
                        // Find the global index for this specific change
                        const globalIndex = pendingChanges.findIndex(
                          pc => pc.fieldName === change.fieldName && 
                                pc.optionValue === change.optionValue && 
                                pc.timestamp === change.timestamp
                        );
                        
                        return (
                          <li key={`${change.fieldName}-${change.optionValue}-${change.timestamp}`} className="flex items-center gap-2 group">
                            {change.type === 'add' ? (
                              <span className="text-green-600 font-medium">+ Hinzufügen:</span>
                            ) : (
                              <span className="text-red-600 font-medium">- Löschen:</span>
                            )}
                            <span className="font-mono bg-white px-2 py-1 rounded text-xs flex-1">
                              „{change.optionLabel}“
                            </span>
                            <span className="text-xs text-yellow-600">
                              ({new Date(change.timestamp).toLocaleTimeString('de-DE')})
                            </span>
                            <button
                              onClick={() => removePendingChange(globalIndex)}
                              className="opacity-0 group-hover:opacity-100 transition-opacity ml-2 p-1 text-red-500 hover:text-red-700 hover:bg-red-50 rounded"
                              title="Diese Änderung entfernen"
                            >
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                              </svg>
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                ))}
                
                <div className="mt-4 pt-3 border-t border-yellow-200 flex items-center gap-4">
                  <button
                    onClick={() => {
                      setShowPendingChangesDetails(false);
                      showSaveConfirmationDialog();
                    }}
                    disabled={isCommittingChanges}
                    className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors disabled:bg-gray-400"
                  >
                    {isCommittingChanges ? (
                      <>
                        <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                        <span>Wird gespeichert...</span>
                      </>
                    ) : (
                      <>
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                        <span>Jetzt speichern</span>
                      </>
                    )}
                  </button>
                  
                  <button
                    onClick={() => {
                      if (confirm(`Möchten Sie wirklich alle ${pendingChanges.length} ausstehenden Änderungen verwerfen?`)) {
                        setPendingChanges([]);
                        setShowPendingChangesDetails(false);
                        loadDropdownOptions(); // Reload to reset UI
                      }
                    }}
                    className="flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg font-medium transition-colors"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                    <span>Alle verwerfen</span>
                  </button>
                  
                  <button
                    onClick={() => setShowPendingChangesDetails(false)}
                    className="flex items-center gap-2 px-3 py-2 text-yellow-700 hover:text-yellow-800 transition-colors"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
                    </svg>
                    <span>Ausblenden</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Form Content - Full Height Scrollable */}
      <div 
        className="flex-1 overflow-y-auto bg-gray-50 relative pb-24"
      >
        <div className="p-6">
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            
            {/* Pending Changes Notification Banner */}
            {pendingChanges.length > 0 && !showPendingChangesDetails && (
              <div className="mb-4 bg-gradient-to-r from-yellow-50 to-orange-50 border border-yellow-200 rounded-lg p-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 bg-yellow-500 rounded-full animate-pulse"></div>
                      <span className="text-sm font-medium text-yellow-800">
                        {pendingChanges.length} ungespeicherte Dropdown-Änderung{pendingChanges.length !== 1 ? 'en' : ''}
                      </span>
                    </div>
                    <span className="text-xs text-yellow-600 bg-yellow-100 px-2 py-1 rounded-full">
                      Klicken Sie oben auf die gelbe Benachrichtigung um Details zu sehen
                    </span>
                  </div>
                  <button
                    onClick={() => setShowPendingChangesDetails(true)}
                    className="text-yellow-600 hover:text-yellow-700 text-sm font-medium"
                  >
                    Details anzeigen →
                  </button>
                </div>
              </div>
            )}
        
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Dropdown Fields */}
          <div className="space-y-6">
            <SearchableDropdown
              label="Rechnungsempfänger"
              value={fields.rechnungsempfaenger || ''}
              options={dropdownOptions.rechnungsempfaenger}
              onChange={(value) => onFieldChange('rechnungsempfaenger', value)}
              onAddNew={(newValue) => handleAddNewOption('rechnungsempfaenger', newValue)}
              onDelete={(optionValue) => handleDeleteOption('rechnungsempfaenger', optionValue)}
              placeholder="Empfänger auswählen..."
            />

            <SearchableDropdown
              label="Rechnungssteller"
              value={fields.rechnungssteller || ''}
              options={dropdownOptions.rechnungssteller}
              onChange={(value) => onFieldChange('rechnungssteller', value)}
              onAddNew={(newValue) => handleAddNewOption('rechnungssteller', newValue)}
              onDelete={(optionValue) => handleDeleteOption('rechnungssteller', optionValue)}
              placeholder="Aussteller auswählen..."
            />

            <SearchableDropdown
              label="Projekt"
              value={fields.projekt || ''}
              options={dropdownOptions.projekt}
              onChange={(value) => onFieldChange('projekt', value)}
              onAddNew={(newValue) => handleAddNewOption('projekt', newValue)}
              onDelete={(optionValue) => handleDeleteOption('projekt', optionValue)}
              placeholder="Projekt auswählen..."
            />

            <SearchableDropdown
              label="Gewerk"
              value={fields.gewerk || ''}
              options={dropdownOptions.gewerk}
              onChange={(value) => onFieldChange('gewerk', value)}
              onAddNew={(newValue) => handleAddNewOption('gewerk', newValue)}
              onDelete={(optionValue) => handleDeleteOption('gewerk', optionValue)}
              placeholder="Gewerk auswählen..."
            />

            <SearchableDropdown
              label="Weiter berechnen an"
              value={fields.weiter_berechnen_an || ''}
              options={dropdownOptions.weiter_berechnen_an}
              onChange={(value) => onFieldChange('weiter_berechnen_an', value)}
              onAddNew={(newValue) => handleAddNewOption('weiter_berechnen_an', newValue)}
              onDelete={(optionValue) => handleDeleteOption('weiter_berechnen_an', optionValue)}
              placeholder="Abteilung oder Kontakt auswählen..."
            />
          </div>

          {/* Input Fields */}
          <div className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Rechnungsbetrag
              </label>
              <div className="relative">
                <span className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-500">€</span>
                <input
                  type="number"
                  step="0.01"
                  value={fields.rechnungsbetrag || ''}
                  onChange={(e) => onFieldChange('rechnungsbetrag', parseFloat(e.target.value) || 0)}
                  className="w-full pl-8 pr-3 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  placeholder="0.00"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Rechnungseingang
              </label>
              <input
                type="date"
                value={fields.rechnungseingang || ''}
                onChange={(e) => onFieldChange('rechnungseingang', e.target.value)}
                className="w-full px-3 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Fälligkeit
              </label>
              <input
                type="date"
                value={fields.faelligkeit || ''}
                onChange={(e) => onFieldChange('faelligkeit', e.target.value)}
                className="w-full px-3 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Skonto Datum
                </label>
                <input
                  type="date"
                  value={fields.skonto_datum || ''}
                  onChange={(e) => onFieldChange('skonto_datum', e.target.value)}
                  className="w-full px-3 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Skonto Prozent
                </label>
                <div className="relative">
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    max="100"
                    value={fields.skonto_prozent || ''}
                    onChange={(e) => onFieldChange('skonto_prozent', parseFloat(e.target.value) || 0)}
                    className="w-full px-3 pr-8 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    placeholder="0.00"
                  />
                  <span className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-500">%</span>
                </div>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Rechnungsart
              </label>
              <select
                value={fields.rechnungsart || ''}
                onChange={(e) => onFieldChange('rechnungsart', e.target.value)}
                className="w-full px-3 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="">Typ auswählen...</option>
                <option value="rechnung">Rechnung</option>
                <option value="gutschrift">Gutschrift</option>
                <option value="mahnung">Mahnung</option>
              </select>
            </div>

            <div className="flex items-center p-4 bg-gray-50 rounded-lg">
              <input
                type="checkbox"
                checked={fields.kfw_anrechenbar || false}
                onChange={(e) => onFieldChange('kfw_anrechenbar', e.target.checked)}
                className="h-5 w-5 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
              />
              <label className="ml-3 block text-sm font-medium text-gray-700">
                KfW anrechenbar
              </label>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2 flex items-center gap-2">
                <span className="text-red-500">*</span>
                Rechnungsprüfung Email
                <span className="text-xs text-red-600 font-normal">(Pflichtfeld)</span>
              </label>
              <input
                type="email"
                value={fields.rechnungspruefung_email || ''}
                onChange={(e) => onFieldChange('rechnungspruefung_email', e.target.value)}
                className={`w-full px-3 py-3 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 ${
                  !fields.rechnungspruefung_email?.trim() 
                    ? 'border-red-300 bg-red-50' 
                    : 'border-gray-300'
                }`}
                placeholder="email@beispiel.de"
                required
              />
              <p className="text-xs text-gray-500 mt-2 flex items-center gap-1">
                <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                </svg>
                Erforderlich für Speichern, Abschließen und Dropdown-Änderungen
              </p>
              {!fields.rechnungspruefung_email?.trim() && (
                <p className="text-xs text-red-600 mt-1 flex items-center gap-1">
                  <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                  </svg>
                  Bitte geben Sie eine gültige E-Mail-Adresse ein
                </p>
              )}
              
              {/* Highlighted warning to prevent email mistakes and SendGrid bounce issues */}
              <div className="mt-3 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
                <p className="text-sm font-semibold text-yellow-800 flex items-center gap-2">
                  <span className="text-lg">⚠️</span>
                  Wichtiger Hinweis zur E-Mail-Adresse
                </p>
                <p className="text-xs text-yellow-700 mt-1">
                  Bitte geben Sie eine <strong>korrekte E-Mail-Adresse</strong> ein. Diese wird für alle Erinnerungen und Benachrichtigungen verwendet. 
                  Falsche E-Mail-Adressen führen zu fehlgeschlagenen Zustellungen.
                </p>
              </div>
            </div>
          </div>
        </div>

        <TaxDetailsSection fields={fields} onFieldChange={onFieldChange} />
        {invoiceId && <ComplianceChecklist invoiceId={invoiceId} fields={fields} />}

        {/* Discard Changes Option */}
        {pendingChanges.length > 0 && (
          <div className="mt-8 pt-6 border-t border-gray-200">
            <button
              onClick={() => {
                if (confirm(`Möchten Sie wirklich alle ${pendingChanges.length} ausstehenden Änderungen verwerfen?`)) {
                  setPendingChanges([]);
                  loadDropdownOptions(); // Reload to reset UI
                }
              }}
              className="flex items-center gap-2 text-red-600 hover:text-red-700 font-medium transition-colors"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
              <span>Alle Änderungen verwerfen</span>
            </button>
          </div>
        )}

        {/* Static Action Bar at Bottom */}
        <div className="mt-8 pt-6 border-t border-gray-200">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {/* Status Indicators */}
              {!fields.rechnungspruefung_email?.trim() && (
                <div className="flex items-center gap-2 px-2 py-1 bg-red-50 border border-red-200 rounded text-red-700 text-xs">
                  <svg className="w-3 h-3 text-red-500" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                  </svg>
                  <span className="font-medium">E-Mail erforderlich</span>
                </div>
              )}
            </div>
            
            {/* Compact Action Buttons */}
            <div className="flex items-center gap-2">
              {/* Dropdown Changes Save Button */}
              {pendingChanges.length > 0 && (
                <button
                  onClick={showSaveConfirmationDialog}
                  disabled={isCommittingChanges}
                  className="flex items-center gap-1 px-3 py-1.5 rounded text-xs font-medium transition-all duration-300 bg-blue-600 hover:bg-blue-700 text-white"
                >
                  {isCommittingChanges ? (
                    <>
                      <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                      <span>Speichern...</span>
                    </>
                  ) : (
                    <>
                      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                      </svg>
                      <span>Dropdown-Änderungen ({pendingChanges.length})</span>
                    </>
                  )}
                </button>
              )}

              {/* Main Invoice Save Button */}
              <button
                onClick={handleSave}
                disabled={isSaving || isCompleting || !fields.rechnungspruefung_email?.trim()}
                className={`flex items-center gap-1 px-3 py-1.5 rounded text-xs font-medium transition-all duration-300 ${
                  !fields.rechnungspruefung_email?.trim()
                    ? 'bg-gray-400 cursor-not-allowed'
                    : 'bg-green-600 hover:bg-green-700 text-white'
                } disabled:bg-gray-400`}
              >
                {isSaving ? (
                  <>
                    <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                    <span>Speichern...</span>
                  </>
                ) : (
                  <>
                    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    <span>Rechnung speichern</span>
                  </>
                )}
              </button>

              {/* Complete Invoice Button */}
              {onComplete && (
                <button
                  onClick={handleComplete}
                  disabled={isSaving || isCompleting || !fields.rechnungspruefung_email?.trim()}
                  className={`flex items-center gap-1 px-3 py-1.5 rounded text-xs font-medium transition-all duration-300 ${
                    !fields.rechnungspruefung_email?.trim()
                      ? 'bg-gray-400 cursor-not-allowed'
                      : 'bg-blue-600 hover:bg-blue-700 text-white'
                  } disabled:bg-gray-400`}
                >
                  {isCompleting ? (
                    <>
                      <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                      <span>Abschließen...</span>
                    </>
                  ) : (
                    <>
                      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      <span>Bearbeitung abschließen</span>
                    </>
                  )}
                </button>
              )}
            </div>
          </div>
        </div>
          </div>
        </div>
      </div>

      {/* Save Confirmation Dialog */}
      {showSaveConfirmation && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4 shadow-xl">
            <div className="flex items-center mb-4">
              <div className="flex-shrink-0">
                <svg className="h-6 w-6 text-yellow-400" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
              </div>
              <div className="ml-3">
                <h3 className="text-lg font-medium text-gray-900">
                  Dropdown-Änderungen bestätigen
                </h3>
              </div>
            </div>
            
            <div className="mb-4">
              <p className="text-sm text-gray-600 mb-3">
                Sie sind dabei, <strong>{pendingChanges.length} Dropdown-Änderung{pendingChanges.length !== 1 ? 'en' : ''}</strong> zu speichern. 
                Bitte überprüfen Sie Ihre Änderungen sorgfältig:
              </p>
              
              <div className="bg-gray-50 rounded-lg p-3 max-h-32 overflow-y-auto mb-4">
                {Object.entries(groupPendingChangesByField()).map(([fieldName, changes]) => (
                  <div key={fieldName} className="mb-2 last:mb-0">
                    <div className="text-xs font-medium text-gray-700 mb-1">
                      {getFieldLabel(fieldName)}:
                    </div>
                    <ul className="ml-2 space-y-1">
                      {changes.map((change, index) => (
                        <li key={index} className="text-xs text-gray-600">
                          {change.type === 'add' ? '+ ' : '- '}
                          {change.optionLabel}
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
              
              <div className="border-t pt-3">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Geben Sie <span className="font-mono bg-gray-100 px-1 py-0.5 rounded text-red-600">„bestätigen“</span> ein, um fortzufahren:
                </label>
                <input
                  type="text"
                  value={confirmationText}
                  onChange={(e) => setConfirmationText(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && confirmationText.toLowerCase() === 'bestätigen') {
                      handleConfirmedSave();
                    }
                  }}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  placeholder="bestätigen"
                  autoFocus
                />
                {confirmationText && confirmationText.toLowerCase() !== 'bestätigen' && (
                  <p className="text-xs text-red-600 mt-1">
                    Bitte geben Sie genau „bestätigen“ ein (ohne Anführungszeichen)
                  </p>
                )}
              </div>
            </div>
            
            <div className="flex justify-end space-x-3">
              <button
                onClick={() => {
                  setShowSaveConfirmation(false);
                  setConfirmationText('');
                }}
                className="px-4 py-2 text-gray-600 hover:text-gray-800 transition-colors"
              >
                Abbrechen
              </button>
              <button
                onClick={handleConfirmedSave}
                disabled={confirmationText.toLowerCase() !== 'bestätigen' || isCommittingChanges}
                className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                  confirmationText.toLowerCase() === 'bestätigen' && !isCommittingChanges
                    ? 'bg-blue-600 hover:bg-blue-700 text-white'
                    : 'bg-gray-300 text-gray-500 cursor-not-allowed'
                }`}
              >
                {isCommittingChanges ? (
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                    <span>Wird gespeichert...</span>
                  </div>
                ) : (
                  'Änderungen speichern'
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Invoice Save Confirmation Dialog */}
      {showInvoiceSaveConfirmation && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4 shadow-xl">
            <div className="flex items-center mb-4">
              <div className="flex-shrink-0">
                <svg className="h-6 w-6 text-green-400" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
              </div>
              <div className="ml-3">
                <h3 className="text-lg font-medium text-gray-900">
                  Rechnung speichern bestätigen
                </h3>
              </div>
            </div>
            
            <div className="mb-4">
              <p className="text-sm text-gray-600 mb-3">
                Sie sind dabei, die <strong>Rechnung zu speichern</strong>. 
                Die eingegebenen Daten werden in der Datenbank gespeichert.
              </p>
              
              <div className="border-t pt-3">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Geben Sie <span className="font-mono bg-gray-100 px-1 py-0.5 rounded text-red-600">„bestätigen“</span> ein, um fortzufahren:
                </label>
                <input
                  type="text"
                  value={confirmationText}
                  onChange={(e) => setConfirmationText(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && confirmationText.toLowerCase() === 'bestätigen') {
                      handleConfirmedInvoiceSave();
                    }
                  }}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  placeholder="bestätigen"
                  autoFocus
                />
                {confirmationText && confirmationText.toLowerCase() !== 'bestätigen' && (
                  <p className="text-xs text-red-600 mt-1">
                    Bitte geben Sie genau „bestätigen“ ein (ohne Anführungszeichen)
                  </p>
                )}
              </div>
            </div>
            
            <div className="flex justify-end space-x-3">
              <button
                onClick={() => {
                  setShowInvoiceSaveConfirmation(false);
                  setConfirmationText('');
                }}
                className="px-4 py-2 text-gray-600 hover:text-gray-800 transition-colors"
              >
                Abbrechen
              </button>
              <button
                onClick={handleConfirmedInvoiceSave}
                disabled={confirmationText.toLowerCase() !== 'bestätigen' || isSaving}
                className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                  confirmationText.toLowerCase() === 'bestätigen' && !isSaving
                    ? 'bg-green-600 hover:bg-green-700 text-white'
                    : 'bg-gray-300 text-gray-500 cursor-not-allowed'
                }`}
              >
                {isSaving ? (
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                    <span>Wird gespeichert...</span>
                  </div>
                ) : (
                  'Rechnung speichern'
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Invoice Complete Confirmation Dialog */}
      {showInvoiceCompleteConfirmation && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4 shadow-xl">
            <div className="flex items-center mb-4">
              <div className="flex-shrink-0">
                <svg className="h-6 w-6 text-blue-400" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-8.293l-3-3a1 1 0 00-1.414 1.414L10.586 9.5 8.707 7.621a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4a1 1 0 00-1.414-1.414L10.586 9.5z" clipRule="evenodd" />
                </svg>
              </div>
              <div className="ml-3">
                <h3 className="text-lg font-medium text-gray-900">
                  Bearbeitung abschließen bestätigen
                </h3>
              </div>
            </div>
            
            <div className="mb-4">
              <p className="text-sm text-gray-600 mb-3">
                Sie sind dabei, die <strong>Bearbeitung abzuschließen</strong>. 
                Die Rechnung wird als „Abgeschlossen“ markiert und der Status wird aktualisiert.
              </p>
              
              <div className="border-t pt-3">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Geben Sie <span className="font-mono bg-gray-100 px-1 py-0.5 rounded text-red-600">„bestätigen“</span> ein, um fortzufahren:
                </label>
                <input
                  type="text"
                  value={confirmationText}
                  onChange={(e) => setConfirmationText(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && confirmationText.toLowerCase() === 'bestätigen') {
                      handleConfirmedInvoiceComplete();
                    }
                  }}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  placeholder="bestätigen"
                  autoFocus
                />
                {confirmationText && confirmationText.toLowerCase() !== 'bestätigen' && (
                  <p className="text-xs text-red-600 mt-1">
                    Bitte geben Sie genau „bestätigen“ ein (ohne Anführungszeichen)
                  </p>
                )}
              </div>
            </div>
            
            <div className="flex justify-end space-x-3">
              <button
                onClick={() => {
                  setShowInvoiceCompleteConfirmation(false);
                  setConfirmationText('');
                }}
                className="px-4 py-2 text-gray-600 hover:text-gray-800 transition-colors"
              >
                Abbrechen
              </button>
              <button
                onClick={handleConfirmedInvoiceComplete}
                disabled={confirmationText.toLowerCase() !== 'bestätigen' || isCompleting}
                className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                  confirmationText.toLowerCase() === 'bestätigen' && !isCompleting
                    ? 'bg-blue-600 hover:bg-blue-700 text-white'
                    : 'bg-gray-300 text-gray-500 cursor-not-allowed'
                }`}
              >
                {isCompleting ? (
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                    <span>Wird abgeschlossen...</span>
                  </div>
                ) : (
                  'Bearbeitung abschließen'
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default CleanInvoiceForm;
