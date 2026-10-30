/**
 * The operating company's details for the Impressum and privacy notice.
 * Set them per deployment; the placeholders make a missing value obvious.
 */
const env = (value: string | undefined, placeholder: string) => value?.trim() || placeholder;

export const COMPANY = {
  name: env(process.env.NEXT_PUBLIC_COMPANY_NAME, '[Firmenname GmbH]'),
  street: env(process.env.NEXT_PUBLIC_COMPANY_STREET, '[Straße Hausnummer]'),
  city: env(process.env.NEXT_PUBLIC_COMPANY_CITY, '[PLZ Ort]'),
  representative: env(process.env.NEXT_PUBLIC_COMPANY_REPRESENTATIVE, '[Geschäftsführung]'),
  register: env(process.env.NEXT_PUBLIC_COMPANY_REGISTER, '[Amtsgericht, HRB-Nummer]'),
  vatId: env(process.env.NEXT_PUBLIC_COMPANY_VAT_ID, '[USt-IdNr.]'),
  email: env(process.env.NEXT_PUBLIC_COMPANY_EMAIL, '[kontakt@firma.de]'),
  phone: env(process.env.NEXT_PUBLIC_COMPANY_PHONE, '[Telefon]'),
  privacyContact: env(process.env.NEXT_PUBLIC_PRIVACY_CONTACT, '[datenschutz@firma.de]'),
} as const;
