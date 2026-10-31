/**
 * SearchableDropdown Component
 * A reusable dropdown component with search functionality and "Add New" capability
 */
'use client';

import React, { useState, useRef, useEffect, useId } from 'react';
import { ChevronDown, Plus, X, Trash2 } from 'lucide-react';
import { DropdownOption } from '@/services/dropdown';
import { toast } from 'react-hot-toast';
import { useDialog } from './ui/DialogProvider';

interface SearchableDropdownProps {
  label: string;
  value: string;
  options: DropdownOption[];
  onChange: (value: string) => void;
  onAddNew?: (newValue: string) => void;
  onDelete?: (optionValue: string) => void;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
  showAddNew?: boolean;
  showDelete?: boolean;
}

export const SearchableDropdown: React.FC<SearchableDropdownProps> = ({
  label,
  value,
  options,
  onChange,
  onAddNew,
  onDelete,
  placeholder = "Option auswählen...",
  disabled = false,
  className = "",
  showAddNew = true,
  showDelete = true
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const dialog = useDialog();
  const [searchTerm, setSearchTerm] = useState('');
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [newOptionValue, setNewOptionValue] = useState('');
  const dropdownRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const id = useId();
  const labelId = `${id}-label`;
  const valueId = `${id}-value`;
  const listId = `${id}-list`;
  const dialogTitleId = `${id}-dialog-title`;
  const newOptionInputId = `${id}-new-option`;

  // Typing should start in the search box as soon as the list opens
  useEffect(() => {
    if (isOpen) inputRef.current?.focus();
  }, [isOpen]);

  // Filter options based on search term
  const filteredOptions = options.filter(option =>
    option.label.toLowerCase().includes(searchTerm.toLowerCase()) ||
    option.value.toLowerCase().includes(searchTerm.toLowerCase())
  );

  // Get display value for selected option
  const selectedOption = options.find(opt => opt.value === value);
  const displayValue = selectedOption ? selectedOption.label : value;

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
        setSearchTerm('');
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelect = (optionValue: string) => {
    onChange(optionValue);
    setIsOpen(false);
    setSearchTerm('');
  };

  const handleAddNew = async () => {
    if (newOptionValue.trim() && onAddNew) {
      const trimmedValue = newOptionValue.trim();
      
      // Check for exact duplicates first
      const exactDuplicate = options.find(option => 
        option.value.toLowerCase() === trimmedValue.toLowerCase() ||
        option.label.toLowerCase() === trimmedValue.toLowerCase()
      );
      
      if (exactDuplicate) {
        toast.error(`„${exactDuplicate.label}“ gibt es bereits.`);
        return;
      }
      
      // Check for similar options (case-insensitive)
      const similarOptions = options.filter(option => 
        option.label.toLowerCase().includes(trimmedValue.toLowerCase()) ||
        trimmedValue.toLowerCase().includes(option.label.toLowerCase())
      );
      
      if (similarOptions.length > 0) {
        const similarLabels = similarOptions.map(opt => opt.label).join(', ');
        const confirmed = await dialog.confirm({
          title: 'Ähnliche Option vorhanden',
          message: `Es gibt bereits: ${similarLabels}. „${trimmedValue}“ trotzdem hinzufügen?`,
          confirmLabel: 'Trotzdem hinzufügen',
        });
        if (!confirmed) {
          return;
        }
      }
      
      onAddNew(trimmedValue);
      setNewOptionValue('');
      setShowAddDialog(false);
      setIsOpen(false);
    }
  };

  const handleDelete = async (optionValue: string, optionLabel: string, isDefault: boolean, e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent dropdown from closing
    
    if (onDelete) {
      const confirmed = await dialog.confirm({
        title: 'Option löschen?',
        message: `„${optionLabel}“${isDefault ? ' ist eine Standardoption und' : ''} wird für alle Benutzer aus der Liste entfernt. Bereits erfasste Rechnungen behalten ihren Wert.`,
        confirmLabel: 'Löschen',
        tone: 'danger',
      });
      if (confirmed) {
        onDelete(optionValue);
      }
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && filteredOptions.length === 1) {
      handleSelect(filteredOptions[0].value);
    } else if (e.key === 'Escape') {
      setIsOpen(false);
      setSearchTerm('');
      triggerRef.current?.focus();
    }
  };

  return (
    <div className={`relative ${className}`} ref={dropdownRef}>
      <span id={labelId} className="block text-sm font-medium text-gray-700 mb-1">
        {label}
      </span>
      
      {/* Main dropdown trigger */}
      <div className="relative">
        <button
          ref={triggerRef}
          type="button"
          onClick={() => !disabled && setIsOpen(!isOpen)}
          disabled={disabled}
          aria-labelledby={`${labelId} ${valueId}`}
          aria-haspopup="true"
          aria-expanded={isOpen}
          aria-controls={isOpen ? listId : undefined}
          className={`
            w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm bg-white text-left
            ${disabled ? 'bg-gray-100 cursor-not-allowed' : 'hover:border-gray-400 cursor-pointer'}
            ${isOpen ? 'border-blue-500 ring-1 ring-blue-500' : ''}
            focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500
          `}
        >
          <span id={valueId} className={`block truncate ${!displayValue ? 'text-gray-500' : ''}`}>
            {displayValue || placeholder}
          </span>
          <ChevronDown
            aria-hidden="true"
            className={`absolute right-2 top-2.5 h-4 w-4 text-gray-400 transition-transform
              ${isOpen ? 'rotate-180' : ''}
            `}
          />
        </button>

        {/* Dropdown menu */}
        {isOpen && (
          <div id={listId} className="absolute z-10 w-full mt-1 bg-white border border-gray-300 rounded-md shadow-lg">
            {/* Search input */}
            <div className="p-2 border-b border-gray-200">
              <input
                ref={inputRef}
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Optionen durchsuchen…"
                aria-label={`${label}: Optionen durchsuchen`}
                className="w-full px-2 py-1 border border-gray-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>

            {/* Options list */}
            <div className="max-h-60 overflow-y-auto">
              {filteredOptions.length > 0 ? (
                filteredOptions.map((option, index) => (
                  <div
                    key={`${option.value}_${index}_${option.is_default ? 'default' : 'custom'}`}
                    className={`
                      flex items-center justify-between hover:bg-blue-50 group
                      ${value === option.value ? 'bg-blue-100 text-blue-900' : 'text-gray-900'}
                    `}
                  >
                    <button
                      type="button"
                      onClick={() => handleSelect(option.value)}
                      className="flex-1 px-3 py-2 text-left flex items-center justify-between"
                    >
                      <span>
                        {option.label}
                        {value === option.value && <span className="sr-only"> (ausgewählt)</span>}
                      </span>
                      {option.is_default && (
                        <span className="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded mr-2">
                          Standard
                        </span>
                      )}
                    </button>
                    
                    {/* Delete button for ALL options */}
                    {showDelete && onDelete && (
                      <button
                        type="button"
                        onClick={(e) => handleDelete(option.value, option.label, option.is_default, e)}
                        className="opacity-0 group-hover:opacity-100 focus:opacity-100 mr-2 p-1 text-red-500 hover:text-red-700 hover:bg-red-50 rounded transition-opacity"
                        title={`„${option.label}“ löschen`}
                        aria-label={`${label}: Option „${option.label}“ löschen`}
                      >
                        <Trash2 className="h-4 w-4" aria-hidden="true" />
                      </button>
                    )}
                  </div>
                ))
              ) : (
                <div className="px-3 py-2 text-gray-500 text-sm">
                  Keine Optionen gefunden
                </div>
              )}
            </div>

            {/* Add new option button */}
            {showAddNew && onAddNew && (
              <div className="border-t border-gray-200 p-2">
                <button
                  type="button"
                  onClick={() => setShowAddDialog(true)}
                  className="w-full px-3 py-2 text-left text-blue-600 hover:bg-blue-50 flex items-center gap-2 text-sm"
                >
                  <Plus className="h-4 w-4" aria-hidden="true" />
                  Neue Option hinzufügen
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Add new option dialog */}
      {showAddDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
          <div role="dialog" aria-modal="true" aria-labelledby={dialogTitleId} className="bg-white rounded-lg p-6 w-96 max-w-md mx-4">
            <div className="flex items-center justify-between mb-4">
              <h3 id={dialogTitleId} className="text-lg font-medium text-gray-900">
                Neue {label} hinzufügen
              </h3>
              <button
                onClick={() => {
                  setShowAddDialog(false);
                  setNewOptionValue('');
                }}
                className="text-gray-400 hover:text-gray-600"
                aria-label="Schließen"
              >
                <X className="h-5 w-5" aria-hidden="true" />
              </button>
            </div>

            <div className="mb-4">
              <label htmlFor={newOptionInputId} className="block text-sm font-medium text-gray-700 mb-2">
                Name der Option
              </label>
              <input
                id={newOptionInputId}
                type="text"
                value={newOptionValue}
                onChange={(e) => setNewOptionValue(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleAddNew()}
                placeholder={`Neue ${label.toLowerCase()} eingeben`}
                className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
                autoFocus
              />
            </div>

            <div className="flex gap-3 justify-end">
              <button
                onClick={() => {
                  setShowAddDialog(false);
                  setNewOptionValue('');
                }}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200"
              >
                Abbrechen
              </button>
              <button
                onClick={handleAddNew}
                disabled={!newOptionValue.trim()}
                className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
              >
                Option hinzufügen
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
